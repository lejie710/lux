"""The committed Secure Boot test keys.

Secure Boot uses three levels of keys: PK (platform key), KEK (key exchange
key) and db (the list of signers the firmware accepts). This project has its
own test set of all three, generated once and committed, private halves
included, in `recorder/testkeys/`.

**Why they are committed.** The firmware measures the certificates into TPM
register 7. A machine with different keys can never reproduce a recording.

**Why this module refuses to regenerate.** New keys would silently change
register 7 in every future recording and make every committed one
unreproducible. So generation only happens through an explicit request, and
only into a directory that holds no key material yet. A hash manifest pins
every file; `verify` raises if anything differs.

These are public test keys for this virtual machine only. Never trust them.
"""
import json
import shutil
from dataclasses import dataclass
from pathlib import Path

from recorder import varstore
from recorder.enrol import VariableWrite
from recorder.errors import KeysRefused
from recorder.provenance import RunCommand, certificate_fingerprint
from recorder.recording import sha256_of_file

# Owner identifier used for every signature list this project writes.
OWNER_GUID = "11111111-2222-3333-4444-555555555555"
KEY_NAMES: tuple[str, ...] = ("PK", "KEK", "db")
MANIFEST_NAME = "MANIFEST.json"
SIGNED_LOADER_NAME = "loader-signed.efi"
MANIFEST_FORMAT = "lux-testkeys/1"
# Timestamp inside every signed key update. Fixed so the updates are repeatable.
UPDATE_TIMESTAMP = "2026-01-01 00:00:00"
_SUFFIXES = (".key", ".crt", ".esl", ".auth")
_NOT_KEY_MATERIAL = ("README.md",)


@dataclass(frozen=True)
class Pins:
    """The values the manifest pins besides the key files themselves.

    `created_with` names the versions of the tools that made the key set and
    signed the loader. They are a fact about the past: no later run uses
    those tools, so they are recorded here once and not in every recording.
    """

    loader_authenticode_sha256: str
    vars_template_sha256: str          # empty until the first enrolment boot
    firmware_file: str                 # file name of the packaged firmware
    firmware_sha256: str
    created_with: dict[str, str]


def pins_of(manifest: dict[str, object]) -> Pins:
    """The pinned values of a verified manifest."""
    firmware = manifest["firmware"]
    return Pins(str(manifest["loader_authenticode_sha256"]), str(manifest["vars_template_sha256"]),
                str(firmware["file"]), str(firmware["sha256"]),
                dict(manifest.get("created_with", {})))


def key_material_present(directory: Path) -> list[str]:
    """Names of everything in the directory except its README."""
    if not directory.is_dir():
        return []
    return sorted(p.name for p in directory.iterdir() if p.name not in _NOT_KEY_MATERIAL)


def generation_commands(directory: Path) -> list[list[str]]:
    """The commands that create the three keys and their signed updates.

    Per key: a self-signed certificate, a signature list holding it, and a
    signed update the firmware will accept. PK signs itself and KEK; KEK
    signs db. That chain is what Secure Boot's key hierarchy means.
    """
    def path(name: str, suffix: str) -> str:
        return str(directory / f"{name}{suffix}")

    commands: list[list[str]] = []
    for name in KEY_NAMES:
        commands.append([
            "openssl", "req", "-new", "-x509", "-newkey", "rsa:2048", "-nodes", "-sha256",
            "-days", "3650", "-subj", f"/CN=Lux public test key {name} - never trust/",
            "-keyout", path(name, ".key"), "-out", path(name, ".crt")])
        commands.append(["cert-to-efi-sig-list", "-g", OWNER_GUID, path(name, ".crt"), path(name, ".esl")])
    for name, signer in (("PK", "PK"), ("KEK", "PK"), ("db", "KEK")):
        commands.append([
            "sign-efi-sig-list", "-t", UPDATE_TIMESTAMP, "-k", path(signer, ".key"),
            "-c", path(signer, ".crt"), name, path(name, ".esl"), path(name, ".auth")])
    return commands


def generate(directory: Path, scratch: Path, run: RunCommand) -> None:
    """Create a new key set. Refuses when the directory already holds anything.

    The keys are made in a scratch directory first and copied over only when
    every command succeeded, so a failure never leaves half a key set.
    """
    present = key_material_present(directory)
    if present:
        raise KeysRefused(
            "test keys already exist (" + ", ".join(present[:3]) + ", ...). New keys would change "
            "register 7 in every recording, so they are never regenerated in place.")
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True)
    for command in generation_commands(scratch):
        run(command)
    directory.mkdir(parents=True, exist_ok=True)
    for name in KEY_NAMES:
        for suffix in _SUFFIXES:
            shutil.copyfile(scratch / f"{name}{suffix}", directory / f"{name}{suffix}")
    shutil.rmtree(scratch)


def sign_loader_command(directory: Path, unsigned_loader: Path, output: Path) -> list[str]:
    """The command that signs the loader with the db key."""
    return ["sbsign", "--key", str(directory / "db.key"), "--cert", str(directory / "db.crt"),
            "--output", str(output), str(unsigned_loader)]


def write_manifest(directory: Path, pins: Pins) -> dict[str, object]:
    """Pin every file of the key set, the signed loader, the template and the firmware by hash."""
    names = [f"{name}{suffix}" for name in KEY_NAMES for suffix in _SUFFIXES] + [SIGNED_LOADER_NAME]
    manifest: dict[str, object] = {
        "format": MANIFEST_FORMAT,
        "owner_guid": OWNER_GUID,
        "update_timestamp": UPDATE_TIMESTAMP,
        "files": {name: sha256_of_file(directory / name) for name in sorted(names)},
        "loader_authenticode_sha256": pins.loader_authenticode_sha256,
        "vars_template_sha256": pins.vars_template_sha256,
        "firmware": {"file": pins.firmware_file, "sha256": pins.firmware_sha256},
        "created_with": dict(pins.created_with),
    }
    text = json.dumps(manifest, indent=2, sort_keys=True) + "\n"
    (directory / MANIFEST_NAME).write_bytes(text.encode("utf-8"))
    return manifest


def verify(directory: Path) -> dict[str, object]:
    """Check the key set against its manifest and return the manifest.

    Raises `KeysRefused` when the manifest is missing or unreadable, when a
    pinned file is missing or changed, or when an unpinned file sits in the
    directory.
    """
    try:
        manifest = json.loads((directory / MANIFEST_NAME).read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise KeysRefused(f"the test keys have no readable manifest: {error}") from error
    if manifest.get("format") != MANIFEST_FORMAT or not isinstance(manifest.get("files"), dict):
        raise KeysRefused("the test key manifest has an unknown format")
    firmware = manifest.get("firmware")
    if not isinstance(firmware, dict) or not firmware.get("sha256"):
        raise KeysRefused("the test key manifest does not pin the firmware file")
    for name, expected in manifest["files"].items():
        path = directory / name
        if not path.is_file() or sha256_of_file(path) != expected:
            raise KeysRefused(f"test key file {name} is missing or differs from the manifest")
    unpinned = set(key_material_present(directory)) - set(manifest["files"]) - {MANIFEST_NAME}
    if unpinned:
        raise KeysRefused("files not listed in the manifest: " + ", ".join(sorted(unpinned)))
    return manifest


def fingerprints(directory: Path) -> dict[str, str]:
    """SHA-256 fingerprint of each certificate, for the recording's provenance."""
    return {
        name: certificate_fingerprint((directory / f"{name}.crt").read_text(encoding="ascii"))
        for name in KEY_NAMES
    }


def enrolment_writes(directory: Path) -> list[VariableWrite]:
    """The three variable writes that enrol the keys: db, then KEK, then PK.

    This is the order that was tested. PK goes last because enrolling the
    platform key is the step that ends the firmware's setup mode.
    """
    def write(name: str, vendor: str) -> VariableWrite:
        payload = (directory / f"{name}.auth").read_bytes()
        return VariableWrite(name, vendor, varstore.SECURE_VARIABLE_ATTRIBUTES, payload)

    return [
        write("db", varstore.IMAGE_SECURITY_DATABASE_GUID),
        write("KEK", varstore.GLOBAL_VARIABLE_GUID),
        write("PK", varstore.GLOBAL_VARIABLE_GUID),
    ]
