"""Turn an experiment description into a run directory, without starting anything.

A staged run directory holds:

* `esp/`: what becomes the boot disk. A run with the firmware's own boot
  options has one loader at `EFI/BOOT/BOOTX64.EFI`, the file the firmware
  looks for by default. A run with two boot entries has one loader per
  entry, at `EFI/LUX/A.EFI` and `EFI/LUX/B.EFI`;
* `vars.fd`: a fresh copy of the variable store template the experiment
  starts from, with the experiment's edits applied;
* `tpm/`: an empty directory for a brand-new software TPM.

Run directories must live on a Linux file system, because the unix sockets
the virtual machine uses do not work on a Windows-mounted drive.

Three inputs decide what a boot measures and are therefore checked here,
before anything is written:

* the firmware file must have the hash that is pinned for it (the key
  manifest pins the packaged one; a counted experiment's prediction pins a
  rebuilt one);
* a value that decides what a counted experiment tests (which byte of the
  signature area) is read from the committed prediction's parameters, never
  from the code or the command line;
* the store with the changed boot order must differ from the store with the
  original order in the value of `BootOrder` and in nothing else, and that
  value must be the original one with entries A and B exchanged.
"""
import hashlib
import shutil
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from recorder import bootentries, experiments, keys, loader, pe, varstore
from recorder.errors import FormatError, StagingRefused
from recorder.experiments import Experiment

PACKAGED_FIRMWARE = Path("/usr/share/OVMF/OVMF_CODE_4M.secboot.fd")
# Where the variable store templates live inside the work directory.
TEMPLATE_PATH = Path("template") / "vars-template.fd"
TWO_ENTRY_TEMPLATE_PATH = Path("template") / "vars-template-two-entries.fd"
B_FIRST_TEMPLATE_PATH = Path("template") / "vars-template-two-entries-b-first.fd"
# The file the firmware starts when a boot option names a disk and no file.
DEFAULT_LOADER_PATH: tuple[str, ...] = ("EFI", "BOOT", "BOOTX64.EFI")

Parameters = Mapping[str, object]


@dataclass(frozen=True)
class Assets:
    """The fixed inputs every run starts from.

    The last three are needed only by experiments with two boot entries.
    """

    signed_loader: Path
    vars_template: Path
    firmware_sha256: str          # the pinned hash of the packaged firmware
    second_loader: Path | None = None
    two_entry_template: Path | None = None
    b_first_template: Path | None = None


@dataclass(frozen=True)
class EntryFile:
    """The loader file behind one boot entry of a staged run."""

    entry: str                    # "A" or "B"
    option: str                   # the Boot#### variable
    path: str                     # the file's path as the option stores it
    file_sha256: str
    authenticode_sha256: str

    def as_document(self) -> dict[str, str]:
        """The entry in the shape the recording stores."""
        return {"entry": self.entry, "option": self.option, "path": self.path,
                "file_sha256": self.file_sha256, "authenticode_sha256": self.authenticode_sha256}


@dataclass(frozen=True)
class StagedRun:
    """A prepared run directory and the facts about what was put in it."""

    run_directory: Path
    firmware: Path
    firmware_sha256: str
    loader_sha256: str            # the loader behind the default path, or behind entry A
    loader_authenticode_sha256: str
    vars_template_sha256: str
    loader_change: loader.ByteChange | None
    store_edits: tuple[str, ...]
    firmware_replaced: bool       # True when a rebuilt firmware file was booted
    boot_entries: tuple[EntryFile, ...] = ()      # empty unless the run has two entries
    boot_order: tuple[str, ...] = ()              # the order in the staged store, likewise
    boot_order_changed: bool = False              # True when that order is not the original one

    def change_detail(self) -> dict[str, object] | None:
        """What exactly was changed, in the shape the recording stores.

        None for a run that changes nothing. Otherwise the proof of the one
        changed loader byte (file offset, old and new value, and the area
        the file's own headers place it in), the names of the edits made to
        the variable store, and whether another firmware file was booted. A
        run whose boot order was changed also carries that order.
        """
        if (self.loader_change is None and not self.store_edits and not self.firmware_replaced
                and not self.boot_order_changed):
            return None
        detail: dict[str, object] = {
            "loader_byte": self.loader_change.as_document() if self.loader_change else None,
            "store_edits": list(self.store_edits),
            "firmware_replaced": self.firmware_replaced,
        }
        if self.boot_order_changed:
            detail["boot_order"] = list(self.boot_order)
        return detail


def _loader_variant(experiment: Experiment, signed: bytes,
                    parameters: Parameters) -> tuple[bytes, loader.ByteChange | None]:
    """The loader bytes this experiment puts behind the default path or entry A."""
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


def _loader_behind_entry_b(experiment: Experiment, signed: bytes, assets: Assets) -> bytes:
    """The loader bytes a two-entry experiment puts behind entry B."""
    if experiment.loader_b == experiments.LOADER_SIGNED:
        return signed
    if experiment.loader_b == experiments.LOADER_SECOND:
        if assets.second_loader is None or not assets.second_loader.is_file():
            raise StagingRefused("the second signed loader is missing")
        second = assets.second_loader.read_bytes()
        loader.verify_second_loader(second, signed)
        return second
    raise StagingRefused(f"experiment '{experiment.identifier}' does not say which loader "
                         "entry B holds")


def _apply_store_edit(edit: str, store: bytes, signed_loader: bytes) -> bytes:
    """Apply one named edit to the variable store."""
    if edit == experiments.EDIT_SECURE_BOOT_OFF:
        return varstore.switch_secure_boot_off(store)
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


def require_two_entries(store: bytes, order: tuple[int, ...]) -> None:
    """Check that a store holds both boot entries and lists them in the given order.

    Raises `StagingRefused` when an entry is missing, holds another value
    than this project writes, or `BootOrder` reads differently.
    """
    try:
        found = tuple(varstore.read_boot_order(store))
    except FormatError as error:
        raise StagingRefused(f"the variable store template is not usable: {error}") from error
    if found != order:
        raise StagingRefused(
            "the variable store template lists its boot options as "
            f"{bootentries.option_names(found)}, not {bootentries.option_names(order)}")
    for entry in bootentries.ENTRIES:
        expected = varstore.load_option(entry.description, entry.firmware_path)
        if varstore.read_data(store, entry.variable) != expected:
            raise StagingRefused(f"the variable store template does not hold boot entry "
                                 f"{entry.letter} ({entry.variable}) as this project writes it")
    for number in bootentries.FIRMWARE_OPTIONS:
        if varstore.live_variable(store, varstore.option_name(number)) is None:
            raise StagingRefused("the variable store template lacks the firmware's own boot "
                                 f"option {varstore.option_name(number)}")


def require_only_boot_order_differs(original: bytes, changed: bytes) -> None:
    """Check that the changed-order store differs from the original in `BootOrder` alone.

    Both stores come from a preparation boot of their own. This is the
    proof, taken from the two files before any boot, that the experiment
    changes exactly one thing: every byte outside the value of `BootOrder`
    is equal, and that value lists entry B before entry A. Raises
    `StagingRefused` otherwise.
    """
    require_two_entries(original, bootentries.ORDER_A_FIRST)
    require_two_entries(changed, bootentries.ORDER_B_FIRST)
    if not varstore.only_this_variable_differs(original, changed, "BootOrder"):
        raise StagingRefused("the store with the changed boot order differs from the store "
                             "with the original order in more than the value of BootOrder")


def _template_for(experiment: Experiment, assets: Assets) -> tuple[bytes, tuple[int, ...]]:
    """The template store an experiment starts from, and its boot order if it has two entries."""
    if experiment.store == experiments.STORE_ONE_ENTRY:
        return assets.vars_template.read_bytes(), ()
    if experiment.store not in experiments.TWO_ENTRY_STORES:
        raise StagingRefused(f"unknown variable store '{experiment.store}'")
    if assets.two_entry_template is None or not assets.two_entry_template.is_file():
        raise StagingRefused("no variable store template with two boot entries found; "
                             "run the prepare command first")
    original = assets.two_entry_template.read_bytes()
    if experiment.store == experiments.STORE_TWO_ENTRIES:
        require_two_entries(original, bootentries.ORDER_A_FIRST)
        return original, bootentries.ORDER_A_FIRST
    if assets.b_first_template is None or not assets.b_first_template.is_file():
        raise StagingRefused("no variable store template with the changed boot order found; "
                             "it is made by the prepare command with --changed-boot-order")
    changed = assets.b_first_template.read_bytes()
    require_only_boot_order_differs(original, changed)
    return changed, bootentries.ORDER_B_FIRST


def _write_disk(run_directory: Path, experiment: Experiment, loader_bytes: bytes,
                signed: bytes, assets: Assets) -> tuple[EntryFile, ...]:
    """Write the loader files onto what becomes the boot disk."""
    disk = run_directory / "esp"
    if experiment.store == experiments.STORE_ONE_ENTRY:
        target = disk.joinpath(*DEFAULT_LOADER_PATH)
        target.parent.mkdir(parents=True)
        target.write_bytes(loader_bytes)
        return ()
    contents = {bootentries.ENTRY_A.letter: loader_bytes,
                bootentries.ENTRY_B.letter: _loader_behind_entry_b(experiment, signed, assets)}
    directory = disk.joinpath(*bootentries.DISK_DIRECTORY)
    directory.mkdir(parents=True)
    files = []
    for entry in bootentries.ENTRIES:
        data = contents[entry.letter]
        (directory / entry.file_name).write_bytes(data)
        files.append(EntryFile(entry.letter, entry.variable, entry.firmware_path,
                               hashlib.sha256(data).hexdigest(), pe.authenticode_sha256(data)))
    return tuple(files)


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
    template, order = _template_for(experiment, assets)
    loader_bytes, change = _loader_variant(experiment, signed, parameters)
    if experiment.store != experiments.STORE_ONE_ENTRY:
        _loader_behind_entry_b(experiment, signed, assets)     # refuse before anything is written
    store = template
    for edit in experiment.store_edits:
        store = _apply_store_edit(edit, store, signed)

    if run_directory.exists():
        shutil.rmtree(run_directory)
    run_directory.mkdir(parents=True)
    (run_directory / "tpm").mkdir()
    entry_files = _write_disk(run_directory, experiment, loader_bytes, signed, assets)
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
        boot_entries=entry_files,
        boot_order=tuple(bootentries.option_names(order)),
        boot_order_changed=experiment.store == experiments.STORE_TWO_ENTRIES_B_FIRST,
    )
