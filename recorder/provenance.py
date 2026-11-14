"""Facts about the host a run depends on: tool versions and the system's name.

Only what a run actually uses is reported, because every value here is a
compared field: two normal runs must agree on it. Tools that were used once
to create the committed key set are listed separately (`KEY_TOOL_PACKAGES`)
and recorded in the key manifest, where they are a fixed fact.

Versions are read with `dpkg-query`, so this module works on Debian and
Ubuntu only. The date of a recording is never read here. It is passed in by
the caller, so that no function that builds compared fields also looks at
the clock.
"""
import base64
import hashlib
import platform
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from recorder.errors import ToolMissing

# Runs a command and returns its output; raises `ToolMissing` if it fails.
RunCommand = Callable[[list[str]], str]

# Name shown in the recording -> the distribution package that provides it.
# These are the packages every run uses.
PACKAGES: dict[str, str] = {
    "qemu": "qemu-system-x86",
    "ovmf": "ovmf",
    "swtpm": "swtpm",
    "binutils": "binutils",
}
# Used once, to create the committed key set and sign the loader.
KEY_TOOL_PACKAGES: dict[str, str] = {
    "openssl": "openssl",
    "sbsigntool": "sbsigntool",
    "efitools": "efitools",
}
# Needed for every preparation and every run.
REQUIRED_PROGRAMS: tuple[str, ...] = ("qemu-system-x86_64", "swtpm", "timeout", "as", "ld")
# Needed only to create a new key set, which a clone of the repository never does.
KEY_GENERATION_PROGRAMS: tuple[str, ...] = (
    "openssl", "sbsign", "cert-to-efi-sig-list", "sign-efi-sig-list")
_NOT_REPORTED = "not reported by the package manager"


def run_command(arguments: list[str]) -> str:
    """Run a program and return what it printed. Raises `ToolMissing` if it fails."""
    try:
        done = subprocess.run(arguments, capture_output=True, text=True, timeout=120, check=False)
    except (OSError, subprocess.SubprocessError) as error:
        raise ToolMissing(f"cannot run {arguments[0]}: {error}") from error
    if done.returncode != 0:
        detail = (done.stderr or done.stdout).strip()[-300:]
        raise ToolMissing(f"{arguments[0]} failed with exit code {done.returncode}: {detail}")
    return done.stdout + done.stderr


def require_programs(programs: tuple[str, ...] = REQUIRED_PROGRAMS,
                     find: Callable[[str], str | None] = shutil.which) -> None:
    """Raise `ToolMissing` naming every listed program that is not installed."""
    missing = [name for name in programs if find(name) is None]
    if missing:
        raise ToolMissing("these programs are not installed: " + ", ".join(missing))


def package_versions(packages: dict[str, str], run: RunCommand = run_command) -> dict[str, str]:
    """Versions of the given packages as the package manager reports them."""
    versions: dict[str, str] = {}
    for name, package in packages.items():
        try:
            versions[name] = run(["dpkg-query", "-W", "-f=${Version}", package]).strip()
        except ToolMissing:
            versions[name] = _NOT_REPORTED
    return versions


def tool_versions(run: RunCommand = run_command) -> dict[str, str]:
    """Versions of the packages every run uses, plus the Python version."""
    versions = package_versions(PACKAGES, run)
    versions["python"] = platform.python_version()
    return versions


def host_os(release_file: Path = Path("/etc/os-release")) -> str:
    """The operating system's name and release number, for example 'Ubuntu 24.04'.

    The point release ('24.04.5') is left out on purpose: it changes with
    ordinary updates that do not touch anything a run uses, and this value
    is a compared field.
    """
    fields: dict[str, str] = {}
    try:
        for line in release_file.read_text(encoding="utf-8").splitlines():
            key, separator, value = line.partition("=")
            if separator:
                fields[key] = value.strip().strip('"')
    except OSError:
        return platform.system()
    if "NAME" in fields and "VERSION_ID" in fields:
        return f"{fields['NAME']} {fields['VERSION_ID']}"
    return fields.get("NAME") or platform.system()


def certificate_fingerprint(pem_text: str) -> str:
    """SHA-256 of a certificate's binary (DER) form, read from its PEM text."""
    begin, end = "-----BEGIN CERTIFICATE-----", "-----END CERTIFICATE-----"
    if begin not in pem_text or end not in pem_text:
        raise ValueError("no certificate found in the PEM text")
    body = pem_text.split(begin, 1)[1].split(end, 1)[0]
    return hashlib.sha256(base64.b64decode("".join(body.split()))).hexdigest()
