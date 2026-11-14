"""Collect what a reader needs to reproduce a run: tool versions and hashes.

The date of a recording is never read here. It is passed in by the caller,
so that no function that builds compared fields also looks at the clock.
"""
import base64
import hashlib
import platform
import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

from recorder.errors import ToolMissing

# Name shown in the recording -> the distribution package that provides it.
PACKAGES: dict[str, str] = {
    "qemu": "qemu-system-x86",
    "ovmf": "ovmf",
    "swtpm": "swtpm",
    "tpm2-tools": "tpm2-tools",
    "sbsigntool": "sbsigntool",
    "efitools": "efitools",
    "binutils": "binutils",
}
REQUIRED_PROGRAMS: tuple[str, ...] = (
    "qemu-system-x86_64", "swtpm", "timeout", "as", "ld", "openssl",
    "sbsign", "cert-to-efi-sig-list", "sign-efi-sig-list",
)
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


def require_programs(find: Callable[[str], str | None] = shutil.which) -> None:
    """Raise `ToolMissing` naming every required program that is not installed."""
    missing = [name for name in REQUIRED_PROGRAMS if find(name) is None]
    if missing:
        raise ToolMissing("these programs are not installed: " + ", ".join(missing))


def tool_versions(run: Callable[[list[str]], str] = run_command) -> dict[str, str]:
    """Package versions as the package manager reports them, plus the Python version."""
    versions: dict[str, str] = {}
    for name, package in PACKAGES.items():
        try:
            versions[name] = run(["dpkg-query", "-W", "-f=${Version}", package]).strip()
        except ToolMissing:
            versions[name] = _NOT_REPORTED
    versions["python"] = platform.python_version()
    return versions


def host_os(release_file: Path = Path("/etc/os-release")) -> str:
    """The operating system's own name for itself, for example 'Ubuntu 24.04.1 LTS'."""
    try:
        for line in release_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("PRETTY_NAME="):
                return line.split("=", 1)[1].strip().strip('"')
    except OSError:
        pass
    return platform.system()


def sha256_file(path: Path) -> str:
    """SHA-256 of a file's bytes, as lowercase hex."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def certificate_fingerprint(pem_text: str) -> str:
    """SHA-256 of a certificate's binary (DER) form, read from its PEM text."""
    begin, end = "-----BEGIN CERTIFICATE-----", "-----END CERTIFICATE-----"
    if begin not in pem_text or end not in pem_text:
        raise ValueError("no certificate found in the PEM text")
    body = pem_text.split(begin, 1)[1].split(end, 1)[0]
    return hashlib.sha256(base64.b64decode("".join(body.split()))).hexdigest()
