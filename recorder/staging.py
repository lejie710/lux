"""Turn an experiment description into a run directory, without starting anything.

A staged run directory holds:

* `esp/EFI/BOOT/BOOTX64.EFI`: the loader variant, on what becomes the boot disk;
* `vars.fd`: a fresh copy of the variable store template, with the
  experiment's edits applied;
* `tpm/`: an empty directory for a brand-new software TPM.

Run directories must live on a Linux file system, because the unix sockets
the virtual machine uses do not work on a Windows-mounted drive.

Two inputs decide what a boot measures and are therefore checked here, before
anything is written:

* the firmware file must have the hash that is pinned for it (the key
  manifest pins the packaged one; a counted experiment's prediction pins a
  rebuilt one);
* a value that decides what a counted experiment tests (which byte of the
  signature area) is read from the committed prediction's parameters, never
  from the code or the command line.
"""
import hashlib
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from recorder import experiments, keys, loader, pe, varstore
from recorder.errors import StagingRefused
from recorder.experiments import Experiment

PACKAGED_FIRMWARE = Path("/usr/share/OVMF/OVMF_CODE_4M.secboot.fd")
# Where the variable store template lives inside the work directory.
TEMPLATE_PATH = Path("template") / "vars-template.fd"

Parameters = Mapping[str, object]


@dataclass(frozen=True)
class Assets:
    """The fixed inputs every run starts from."""

    signed_loader: Path
    vars_template: Path
    firmware_sha256: str          # the pinned hash of the packaged firmware


@dataclass(frozen=True)
class StagedRun:
    """A prepared run directory and the facts about what was put in it."""

    run_directory: Path
    firmware: Path
    firmware_sha256: str
    loader_sha256: str
    loader_authenticode_sha256: str
    vars_template_sha256: str
    loader_change: loader.ByteChange | None
    store_edits: tuple[str, ...]
    firmware_replaced: bool       # True when a rebuilt firmware file was booted

    def change_detail(self) -> dict[str, object] | None:
        """What exactly was changed, in the shape the recording stores.

        None for a run that changes nothing. Otherwise the proof of the one
        changed loader byte (file offset, old and new value, and the area
        the file's own headers place it in), the names of the edits made to
        the variable store, and whether another firmware file was booted.
        """
        if self.loader_change is None and not self.store_edits and not self.firmware_replaced:
            return None
        return {
            "loader_byte": self.loader_change.as_document() if self.loader_change else None,
            "store_edits": list(self.store_edits),
            "firmware_replaced": self.firmware_replaced,
        }


def _loader_variant(experiment: Experiment, signed: bytes,
                    parameters: Parameters) -> tuple[bytes, loader.ByteChange | None]:
    """The loader bytes this experiment puts on the disk."""
    if experiment.loader == experiments.LOADER_SIGNED:
        return signed, None
    if experiment.loader == experiments.LOADER_CONTENT_BYTE:
        return loader.change_content_byte(signed)
    if experiment.loader == experiments.LOADER_SIGNATURE_BYTE:
        offset = parameters.get(experiments.PARAMETER_SIGNATURE_OFFSET)
        if not isinstance(offset, int) or isinstance(offset, bool):
            raise StagingRefused(
                "the byte inside the signature area is not chosen; the committed "
                f"prediction must name it as '{experiments.PARAMETER_SIGNATURE_OFFSET}'")
        return loader.change_signature_byte(signed, offset)
    raise StagingRefused(f"unknown loader variant '{experiment.loader}'")


def _apply_store_edit(edit: str, store: bytes, signed_loader: bytes) -> bytes:
    """Apply one named edit to the variable store."""
    if edit == experiments.EDIT_SECURE_BOOT_OFF:
        return varstore.switch_secure_boot_off(store)
    if edit == experiments.EDIT_REVERSE_BOOT_ORDER:
        return varstore.reverse_boot_order(store)
    if edit == experiments.EDIT_REVOKE_LOADER_HASH:
        digest = bytes.fromhex(pe.authenticode_sha256(signed_loader))
        return varstore.append_variable(
            store, "dbx", varstore.IMAGE_SECURITY_DATABASE_GUID,
            varstore.SECURE_VARIABLE_ATTRIBUTES,
            varstore.sha256_signature_list(keys.OWNER_GUID, digest))
    raise StagingRefused(f"unknown variable store edit '{edit}'")


def require_firmware(firmware: Path, expected_sha256: str) -> str:
    """Check that a firmware file exists and has the pinned hash; return the hash.

    The firmware's own bytes are the first thing measured in a boot. A
    silently different file (a package update, for example) would change
    every recording with no other visible cause.
    """
    if not firmware.is_file():
        raise StagingRefused(f"the firmware file {firmware.name} does not exist")
    actual = hashlib.sha256(firmware.read_bytes()).hexdigest()
    if actual != expected_sha256:
        raise StagingRefused(
            f"the firmware file {firmware.name} has SHA-256 {actual}, but {expected_sha256} "
            "is pinned; recordings made with it would not be comparable")
    return actual


def _firmware_for(experiment: Experiment, firmware_override: Path | None, assets: Assets,
                  parameters: Parameters) -> tuple[Path, str]:
    """The firmware file the run boots, and its checked hash."""
    if experiment.firmware == experiments.FIRMWARE_PACKAGED:
        if firmware_override is not None:
            raise StagingRefused(f"experiment '{experiment.identifier}' uses the packaged firmware")
        return PACKAGED_FIRMWARE, require_firmware(PACKAGED_FIRMWARE, assets.firmware_sha256)
    if firmware_override is None:
        raise StagingRefused("this experiment needs the path of a rebuilt firmware file")
    expected = parameters.get(experiments.PARAMETER_FIRMWARE_SHA256)
    if not isinstance(expected, str):
        raise StagingRefused(
            "the rebuilt firmware is not pinned; the committed prediction must carry "
            f"its SHA-256 as '{experiments.PARAMETER_FIRMWARE_SHA256}'")
    return firmware_override, require_firmware(firmware_override, expected)


def stage_run(experiment: Experiment, run_directory: Path, assets: Assets,
              parameters: Parameters | None = None,
              firmware_override: Path | None = None) -> StagedRun:
    """Create a fresh run directory for one experiment.

    `parameters` are the values of the experiment's committed prediction (an
    empty mapping for a run that needs none). An existing directory of the
    same name is removed first: a run directory is scratch space, and
    leftovers from an earlier boot must never mix in.
    """
    parameters = parameters or {}
    firmware, firmware_sha256 = _firmware_for(experiment, firmware_override, assets, parameters)
    signed = assets.signed_loader.read_bytes()
    template = assets.vars_template.read_bytes()
    loader_bytes, change = _loader_variant(experiment, signed, parameters)
    store = template
    for edit in experiment.store_edits:
        store = _apply_store_edit(edit, store, signed)

    if run_directory.exists():
        shutil.rmtree(run_directory)
    boot_directory = run_directory / "esp" / "EFI" / "BOOT"
    boot_directory.mkdir(parents=True)
    (run_directory / "tpm").mkdir()
    (boot_directory / "BOOTX64.EFI").write_bytes(loader_bytes)
    (run_directory / "vars.fd").write_bytes(store)
    return StagedRun(
        run_directory=run_directory,
        firmware=firmware,
        firmware_sha256=firmware_sha256,
        loader_sha256=hashlib.sha256(loader_bytes).hexdigest(),
        loader_authenticode_sha256=pe.authenticode_sha256(loader_bytes),
        vars_template_sha256=hashlib.sha256(template).hexdigest(),
        loader_change=change,
        store_edits=experiment.store_edits,
        firmware_replaced=experiment.firmware != experiments.FIRMWARE_PACKAGED,
    )
