"""Record one named run from start to finish.

This is the only place where the steps meet, in this order:

1. the prediction gate (a counted experiment without a committed prediction
   stops here, before anything is staged or started);
2. staging the run directory;
3. the boot itself;
4. parsing what the boot left behind;
5. the agreement gate (disagreeing readings stop here, nothing is written);
6. building the recording.

Everything that touches a process arrives through `Environment`, so tests
replace the virtual machine, the clock and git with fakes.
"""
import mmap
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from recorder import capture, experiments, gate, keys, normalise, prediction, recording, staging
from recorder.banks import PcrBanks
from recorder.errors import FormatError, GateFailure, StagingRefused
from recorder.eventlog import Event
from recorder.session import ENDING_PAUSED, Clock, Limits, Machine, Observation, run_boot

_RUN_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,40}")
TEMPLATE_PATH = Path("template") / "vars-template.fd"


@dataclass(frozen=True)
class Environment:
    """Where things are, and the replaceable parts that touch the outside world."""

    testkeys_directory: Path
    predictions_directory: Path
    work_directory: Path                                   # on a Linux file system
    machine_factory: Callable[[Path, Path], Machine]       # (run directory, firmware)
    clock: Clock
    limits: Limits
    tool_versions: Callable[[], dict[str, str]]
    host_os: str
    git: prediction.GitQuery


@dataclass(frozen=True)
class RunRequest:
    """What the caller asks for."""

    name: str                        # for example "normal-1"
    experiment: str                  # an identifier from `experiments`
    recorded_at: str                 # the date, passed in as data
    firmware_override: Path | None = None


@dataclass(frozen=True)
class RunResult:
    """A finished run: the recording and the raw event log it was built from."""

    document: dict[str, object]
    event_log: bytes


@dataclass(frozen=True)
class _Evidence:
    events: tuple[Event, ...]
    event_log: bytes
    live: PcrBanks
    report: gate.GateReport
    console: list[str]


def _cut_event_log(memory_file: Path) -> tuple[int, tuple[Event, ...], bytes]:
    """Find the event log in saved guest memory, then delete the memory file.

    Returns how many places parsed as a log, and the events and raw bytes of
    the log when there is exactly one. Guest memory is never kept.
    """
    try:
        with open(memory_file, "rb") as handle, \
                mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as memory:
            candidates = capture.find_event_logs(memory)
            if len(candidates) != 1:
                return len(candidates), (), b""
            found = candidates[0]
            raw = bytes(memory[found.offset:found.offset + found.log.byte_length])
            return 1, found.log.events, raw
    finally:
        memory_file.unlink(missing_ok=True)


def _collect_evidence(observation: Observation) -> _Evidence:
    """Parse the artifacts of one boot and run the agreement gate over them."""
    if observation.ending != ENDING_PAUSED or observation.memory_file is None \
            or observation.live_pcrs is None:
        if observation.memory_file is not None:
            observation.memory_file.unlink(missing_ok=True)
        raise GateFailure("the guest ended by itself, so the registers could not be read")
    candidate_count, events, raw_log = _cut_event_log(observation.memory_file)
    extends = capture.extends_from_messages(capture.parse_tpm_log(observation.tpm_log))
    report = gate.evaluate(events, extends, observation.live_pcrs, candidate_count)
    gate.require(report)
    console = capture.clean_console(observation.console_raw)
    return _Evidence(events, raw_log, observation.live_pcrs, report, console)


def _provenance(request: RunRequest, env: Environment, staged: staging.StagedRun,
                machine: Machine, prediction_ref: prediction.PredictionRef | None) -> dict[str, object]:
    """The provenance block: everything needed to reproduce the run."""
    run_directory = str(staged.run_directory)
    return {
        "recorded_at": request.recorded_at,
        "tools": env.tool_versions(),
        "host_os": env.host_os,
        "firmware": {"file": staged.firmware.name,
                     "sha256": recording.sha256_of_file(staged.firmware)},
        "vars_template_sha256": staged.vars_template_sha256,
        "loader": {"file_sha256": staged.loader_sha256,
                   "authenticode_sha256": staged.loader_authenticode_sha256},
        "keys": keys.fingerprints(env.testkeys_directory),
        "qemu_command_line": normalise.mask_run_directory(machine.qemu_command_line, run_directory),
        "swtpm_command_line": normalise.mask_run_directory(machine.swtpm_command_line, run_directory),
        "prediction": prediction_ref.as_document() if prediction_ref else None,
    }


def _assets(env: Environment) -> staging.Assets:
    """The fixed inputs, checked against the committed manifest."""
    manifest = keys.verify(env.testkeys_directory)
    template = env.work_directory / TEMPLATE_PATH
    if not template.is_file():
        raise StagingRefused("no variable store template found; run the prepare command first")
    if recording.sha256_of_file(template) != manifest.get("vars_template_sha256"):
        raise StagingRefused("the variable store template differs from the committed manifest")
    return staging.Assets(env.testkeys_directory / keys.SIGNED_LOADER_NAME, template)


def record_run(request: RunRequest, env: Environment) -> RunResult:
    """Record one run. Raises a `LuxError` subclass instead of writing a doubtful result."""
    experiment = experiments.get(request.experiment)
    prediction_ref = None
    if experiment.kind == experiments.KIND_COUNTED:
        prediction_ref = prediction.require_committed(
            experiment.identifier, env.predictions_directory, env.git)
    if not _RUN_NAME.fullmatch(request.name):
        raise StagingRefused("a run name uses lowercase letters, digits and hyphens only")

    run_directory = env.work_directory / "runs" / request.name
    staged = staging.stage_run(experiment, run_directory, _assets(env), request.firmware_override)
    machine = env.machine_factory(staged.run_directory, staged.firmware)
    observation = run_boot(machine, env.clock, env.limits)
    evidence = _collect_evidence(observation)

    facts = recording.RunFacts(
        name=request.name,
        experiment=experiment.identifier,
        kind=experiment.kind,
        change=experiment.change,
        provenance=_provenance(request, env, staged, machine, prediction_ref),
        outcome={"result": capture.classify_outcome(evidence.console),
                 "trigger": observation.trigger,
                 "ending": observation.ending,
                 "settle_rule": env.limits.settle_rule},
        timing={"seconds_to_trigger": normalise.round_seconds(observation.seconds_to_trigger),
                "seconds_to_pause": normalise.round_seconds(observation.seconds_to_pause)},
        console=evidence.console,
        events=evidence.events,
        pcrs=evidence.live,
        event_log_bytes=evidence.event_log,
        vars_after_sha256=recording.sha256_of_file(run_directory / "vars.fd"),
        gate=gate.gate_block(evidence.report),
    )
    document = recording.build_recording(facts)
    leaked = normalise.find_host_paths(document)
    if leaked:
        raise FormatError("a host path would be written into the recording at: " + ", ".join(leaked))
    return RunResult(document, evidence.event_log)
