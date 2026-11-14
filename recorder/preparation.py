"""Prepare everything the runs share: keys, loader and variable store template.

Steps, in order:

1. Keys. Normally the committed test keys are only verified. They are
   generated when, and only when, the caller asks for it explicitly and no
   keys exist yet.
2. Loader. The unsigned loader is built with the installed assembler and
   linker, and its Authenticode digest must equal the committed signed
   loader's. That proves this machine builds the same loader.
3. Firmware. The packaged firmware file must have the hash the manifest
   pins. A package update would change the earliest measurements, and every
   recording with them, without any other visible cause.
4. Template. The firmware's empty variable store is booted once with the
   enrolment program, which writes the keys. The store after that boot is
   the template every recorded run starts from, so every recorded run is the
   second boot of the same store. Its hash must equal the manifest's.

5. Template with two boot entries. A second enrolment boot of the empty
   store, whose program first creates the boot entries A and B and writes
   `BootOrder` (A, then B), and then writes the keys. Its hash is pinned in
   `bootentries`. The boot order experiments' normal runs start from it.

The enrolment boot is a preparation boot, not a recorded run: its program
is unsigned and runs while no platform key is enrolled yet, and it powers
the machine off itself.

A third template, with `BootOrder` listing B before A, is the changed
configuration of a counted experiment. `prepare` never makes it;
`prepare_changed_boot_order` does, and the command line calls that only
after a boot order prediction is committed. It is made the same way, by one
enrolment boot of the empty store, so the changed order is written by the
firmware's own `SetVariable` service and the machine is switched off before
the recorded boot begins.
"""
import shutil
from collections.abc import Callable
from dataclasses import dataclass, replace
from pathlib import Path

from recorder import (bootentries, capture, enrol, keys, loader, pe, provenance, recording,
                      staging, varstore)
from recorder.errors import KeysRefused, StagingRefused
from recorder.session import Clock, Limits, Machine, run_boot
from recorder.staging import B_FIRST_TEMPLATE_PATH, TEMPLATE_PATH, TWO_ENTRY_TEMPLATE_PATH

EMPTY_STORE = Path("/usr/share/OVMF/OVMF_VARS_4M.fd")
LOADER_SOURCE = Path(__file__).parent / "guest" / "loader.s"
_ENROLLED_VARIABLES = ("PK", "KEK", "db")


@dataclass(frozen=True)
class PrepareEnvironment:
    """Paths and the replaceable parts that touch the outside world."""

    testkeys_directory: Path
    work_directory: Path
    run: provenance.RunCommand
    machine_factory: Callable[[Path, Path], Machine]
    clock: Clock
    limits: Limits
    empty_store: Path = EMPTY_STORE
    firmware: Path = staging.PACKAGED_FIRMWARE
    two_entry_template_sha256: str = bootentries.TEMPLATE_SHA256
    second_loader: Path = loader.SECOND_LOADER_PATH


def _ensure_keys(env: PrepareEnvironment, generate_keys: bool) -> bool:
    """Generate the key set if asked and allowed. Returns True when new keys were made."""
    present = keys.key_material_present(env.testkeys_directory)
    if generate_keys:
        keys.generate(env.testkeys_directory, env.work_directory / "new-keys", env.run)
        return True
    if not present:
        raise KeysRefused("no test keys found; they are generated once with the "
                          "--generate-keys option and then committed")
    return False


def _check_template(store: bytes) -> None:
    """The template must hold the three keys and have Secure Boot switched on."""
    for name in _ENROLLED_VARIABLES:
        if varstore.live_variable(store, name) is None:
            raise StagingRefused(f"the enrolment boot did not write the variable '{name}'")
    if varstore.read_data(store, "SecureBootEnable") != b"\x01":
        raise StagingRefused("Secure Boot is not switched on in the variable store template")


def _enrolment_boot(env: PrepareEnvironment, run_name: str = "prep-enrol",
                    boot_order: tuple[int, ...] | None = None) -> bytes:
    """Boot the empty store once with the enrolment program; return the store afterwards.

    With `boot_order`, the program first creates the two boot entries and
    writes that order, and then writes the keys. The keys go last because
    enrolling the platform key ends the firmware's setup mode.
    """
    run_directory = env.work_directory / "runs" / run_name
    if run_directory.exists():
        shutil.rmtree(run_directory)
    boot_directory = run_directory / "esp" / "EFI" / "BOOT"
    boot_directory.mkdir(parents=True)
    (run_directory / "tpm").mkdir()
    writes = keys.enrolment_writes(env.testkeys_directory)
    if boot_order is not None:
        writes = bootentries.variable_writes(boot_order) + writes
    program = enrol.build_enrol_program(writes)
    (boot_directory / "BOOTX64.EFI").write_bytes(program)
    shutil.copyfile(env.empty_store, run_directory / "vars.fd")

    machine = env.machine_factory(run_directory, env.firmware)
    observation = run_boot(machine, env.clock, env.limits)
    if observation.memory_file is not None:
        observation.memory_file.unlink(missing_ok=True)
    console = capture.clean_console(observation.console_raw)
    succeeded = [line for line in console if line.startswith("LUX-SETVAR") and "status=00" in line]
    if len(succeeded) != len(writes) or enrol.DONE_LINE not in console:
        raise StagingRefused(f"the enrolment boot did not report {len(writes)} successful writes: "
                             + " | ".join(console[-(len(writes) + 3):]))
    return (run_directory / "vars.fd").read_bytes()


def _ensure_template(env: PrepareEnvironment) -> Path:
    """Reuse the work directory's template, or make it with one enrolment boot."""
    template = env.work_directory / TEMPLATE_PATH
    if not template.is_file():
        store = _enrolment_boot(env)
        _check_template(store)
        template.parent.mkdir(parents=True, exist_ok=True)
        template.write_bytes(store)
    else:
        _check_template(template.read_bytes())
    return template


def _ensure_two_entry_template(env: PrepareEnvironment) -> Path:
    """Reuse the template with two boot entries, or make it with one enrolment boot.

    Its hash must equal the pinned one; a store that differs is discarded,
    because recordings made from it would not be comparable with the
    committed ones.
    """
    template = env.work_directory / TWO_ENTRY_TEMPLATE_PATH
    if not template.is_file():
        store = _enrolment_boot(env, "prep-two-entries", bootentries.ORDER_A_FIRST)
        _check_template(store)
        staging.require_two_entries(store, bootentries.ORDER_A_FIRST)
        template.parent.mkdir(parents=True, exist_ok=True)
        template.write_bytes(store)
    else:
        store = template.read_bytes()
        _check_template(store)
        staging.require_two_entries(store, bootentries.ORDER_A_FIRST)
    if recording.sha256_of_file(template) != env.two_entry_template_sha256:
        template.unlink()
        raise StagingRefused("the enrolment boot produced a different two-entry variable store "
                             "than the pinned one; the template was discarded")
    return template


def prepare_changed_boot_order(env: PrepareEnvironment) -> dict[str, str]:
    """Make the template whose `BootOrder` lists entry B before entry A.

    This store is the changed configuration of the boot order experiments.
    The caller must have checked that a prediction for one of them is
    committed; this function only makes the store. One enrolment boot of the
    empty store writes both entries, the changed order and the keys. The
    result is kept only if it differs from the two-entry template in the
    value of `BootOrder` and in nothing else. The store is never booted here.
    """
    original = env.work_directory / TWO_ENTRY_TEMPLATE_PATH
    if not original.is_file():
        raise StagingRefused("no variable store template with two boot entries found; "
                             "run the prepare command first")
    if recording.sha256_of_file(original) != env.two_entry_template_sha256:
        raise StagingRefused("the two-entry variable store template differs from the pinned one")
    staging.require_firmware(env.firmware, keys.pins_of(keys.verify(env.testkeys_directory)).firmware_sha256)
    changed = env.work_directory / B_FIRST_TEMPLATE_PATH
    if not changed.is_file():
        store = _enrolment_boot(env, "prep-two-entries-b-first", bootentries.ORDER_B_FIRST)
        _check_template(store)
        staging.require_only_boot_order_differs(original.read_bytes(), store)
        changed.write_bytes(store)
    else:
        staging.require_only_boot_order_differs(original.read_bytes(), changed.read_bytes())
    return {
        "two_entry_template_sha256": recording.sha256_of_file(original),
        "changed_boot_order_template_sha256": recording.sha256_of_file(changed),
        "boot_order": " ".join(bootentries.option_names(bootentries.ORDER_B_FIRST)),
    }


def prepare(env: PrepareEnvironment, generate_keys: bool = False) -> dict[str, str]:
    """Make the work directory ready for recording. Returns the pinned hashes."""
    new_keys = _ensure_keys(env, generate_keys)
    unsigned = loader.build_loader(LOADER_SOURCE, env.work_directory / "build", env.run)
    unsigned_digest = pe.authenticode_sha256(unsigned.read_bytes())
    signed = env.testkeys_directory / keys.SIGNED_LOADER_NAME
    if new_keys:
        env.run(keys.sign_loader_command(env.testkeys_directory, unsigned, signed))
        # Pin the keys at once; the template hash is added after the enrolment boot.
        keys.write_manifest(env.testkeys_directory, keys.Pins(
            unsigned_digest, "", env.firmware.name, recording.sha256_of_file(env.firmware),
            provenance.package_versions(provenance.KEY_TOOL_PACKAGES, env.run)))
        stale = env.work_directory / TEMPLATE_PATH
        stale.unlink(missing_ok=True)          # a template made with other keys is useless
    manifest = keys.verify(env.testkeys_directory)
    pins = keys.pins_of(manifest)
    if pins.loader_authenticode_sha256 != unsigned_digest:
        raise StagingRefused("this assembler and linker build a different loader than "
                             "the committed signed one; recordings would not be comparable")
    staging.require_firmware(env.firmware, pins.firmware_sha256)

    template = _ensure_template(env)
    template_hash = recording.sha256_of_file(template)
    if pins.vars_template_sha256 == "":
        keys.write_manifest(env.testkeys_directory, replace(pins, vars_template_sha256=template_hash))
    elif pins.vars_template_sha256 != template_hash:
        template.unlink()
        raise StagingRefused("the enrolment boot produced a different variable store than the "
                             "committed manifest records; the template was discarded")
    summary = {
        "loader_authenticode_sha256": unsigned_digest,
        "signed_loader_sha256": recording.sha256_of_file(signed),
        "vars_template_sha256": template_hash,
        "firmware_sha256": pins.firmware_sha256,
        "keys": "generated" if new_keys else "verified",
    }
    if new_keys:
        # The second loader and the pinned two-entry template belong to the
        # committed key set; a new key set has neither yet.
        return summary
    loader.verify_second_loader(env.second_loader.read_bytes(), signed.read_bytes())
    two_entry_template = _ensure_two_entry_template(env)
    summary["second_loader_sha256"] = recording.sha256_of_file(env.second_loader)
    summary["two_entry_template_sha256"] = recording.sha256_of_file(two_entry_template)
    return summary
