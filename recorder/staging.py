"""Turn an experiment description into a run directory, without starting anything.

A staged run directory holds:

* `esp/EFI/BOOT/BOOTX64.EFI`: the loader variant, on what becomes the boot disk;
* `vars.fd`: a fresh copy of the variable store template, with the
  experiment's edits applied;
* `tpm/`: an empty directory for a brand-new software TPM.

Run directories must live on a Linux file system, because the unix sockets
the virtual machine uses do not work on a Windows-mounted drive.
"""
import hashlib
import shutil
from dataclasses import dataclass
from pathlib import Path

from recorder import experiments, loader, pe, varstore
from recorder.errors import StagingRefused
from recorder.experiments import Experiment

PACKAGED_FIRMWARE = Path("/usr/share/OVMF/OVMF_CODE_4M.secboot.fd")
# Owner identifier used for every signature list this project writes.
OWNER_GUID = "11111111-2222-3333-4444-555555555555"


@dataclass(frozen=True)
class Assets:
    """The fixed inputs every run starts from."""

    signed_loader: Path
    vars_template: Path


@dataclass(frozen=True)
class StagedRun:
    """A prepared run directory and the facts about what was put in it."""

    run_directory: Path
    firmware: Path
    loader_sha256: str
    loader_authenticode_sha256: str
    vars_template_sha256: str
    loader_change: loader.ByteChange | None


def _loader_variant(experiment: Experiment, signed: bytes) -> tuple[bytes, loader.ByteChange | None]:
    """The loader bytes this experiment puts on the disk."""
    if experiment.loader == experiments.LOADER_SIGNED:
        return signed, None
    if experiment.loader == experiments.LOADER_CONTENT_BYTE:
        return loader.change_content_byte(signed)
    if experiment.loader == experiments.LOADER_SIGNATURE_BYTE:
        if experiment.signature_area_offset is None:
            raise StagingRefused(
                "the byte inside the signature area is not chosen yet; it must be "
                "named in the experiment's description when its prediction is written")
        return loader.change_signature_byte(signed, experiment.signature_area_offset)
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
            varstore.sha256_signature_list(OWNER_GUID, digest))
    raise StagingRefused(f"unknown variable store edit '{edit}'")


def _firmware_for(experiment: Experiment, firmware_override: Path | None) -> Path:
    """The firmware file the run boots."""
    if experiment.firmware == experiments.FIRMWARE_PACKAGED:
        if firmware_override is not None:
            raise StagingRefused(f"experiment '{experiment.identifier}' uses the packaged firmware")
        return PACKAGED_FIRMWARE
    if firmware_override is None or not firmware_override.is_file():
        raise StagingRefused("this experiment needs the path of a rebuilt firmware file")
    return firmware_override


def stage_run(experiment: Experiment, run_directory: Path, assets: Assets,
              firmware_override: Path | None = None) -> StagedRun:
    """Create a fresh run directory for one experiment.

    An existing directory of the same name is removed first: a run directory
    is scratch space, and leftovers from an earlier boot must never mix in.
    """
    firmware = _firmware_for(experiment, firmware_override)
    signed = assets.signed_loader.read_bytes()
    template = assets.vars_template.read_bytes()
    loader_bytes, change = _loader_variant(experiment, signed)
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
        loader_sha256=hashlib.sha256(loader_bytes).hexdigest(),
        loader_authenticode_sha256=pe.authenticode_sha256(loader_bytes),
        vars_template_sha256=hashlib.sha256(template).hexdigest(),
        loader_change=change,
    )
