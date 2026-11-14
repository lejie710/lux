"""Record one named run from start to finish.

This is the only place where the steps meet, in this order:

1. the prediction gate (a counted experiment without a committed prediction
   stops here, before anything is staged or started), and for a counted
   experiment the repeat precondition (two identical normal runs on file);
2. staging the run directory, with the parameters of the committed prediction;
3. the boot itself;
4. parsing what the boot left behind;
5. the agreement gate (disagreeing readings stop here, nothing is written);
6. the outcome rule (a boot whose end was not seen, or a normal run that was
   not accepted, stops here, nothing is written);
7. building the recording, and a last search of it for host paths.

Everything that touches a process arrives through `Environment`, so tests
replace the virtual machine, the clock and git with fakes.
"""
import mmap
import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from recorder import capture, experiments, gate, keys, normalise, prediction, recording, staging
from recorder.banks import BANK_NAMES, PcrBanks
from recorder.errors import FormatError, GateFailure, RunIncomplete, StagingRefused
from recorder.eventlog import Event
from recorder.experiments import Experiment
from recorder.session import ENDING_PAUSED, Clock, Limits, Machine, Observation, run_boot
from recorder.staging import TEMPLATE_PATH

_RUN_NAME = re.compile(r"[a-z0-9][a-z0-9-]{0,40}")


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
    # Raises `ComparisonRefused` unless two identical normal runs are on file.
    # Called for counted experiments only, before anything is staged.
    require_repeat: Callable[[], None]


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
    lines: list[str]              # every cleaned console line, in order


@dataclass(frozen=True)
class _CutLog:
    """What was found in saved guest memory."""

    candidates: int               # how many places parsed as an event log
    events: tuple[Event, ...]     # empty unless there was exactly one
    raw: bytes
    banks: tuple[str, ...]        # the hash banks the log's header declares


def _cut_event_log(memory_file: Path) -> _CutLog:
    """Find the event log in saved guest memory, then delete the memory file.

    The log is returned only when exactly one place parses as a log. Guest
    memory is never kept.
    """
    try:
        with open(memory_file, "rb") as handle, \
                mmap.mmap(handle.fileno(), 0, access=mmap.ACCESS_READ) as memory:
            candidates = capture.find_event_logs(memory)
            if len(candidates) != 1:
                return _CutLog(len(candidates), (), b"", ())
            found = candidates[0]
            raw = bytes(memory[found.offset:found.offset + found.log.byte_length])
            return _CutLog(1, found.log.events, raw, tuple(found.log.digest_sizes))
    finally:
        memory_file.unlink(missing_ok=True)


def _collect_evidence(observation: Observation) -> _Evidence:
    """Parse the artifacts of one boot and run the agreement gate over them."""
    if observation.ending != ENDING_PAUSED or observation.memory_file is None \
            or observation.live_pcrs is None:
        if observation.memory_file is not None:
            observation.memory_file.unlink(missing_ok=True)
        raise GateFailure("the guest ended by itself, so the registers could not be read")
    cut = _cut_event_log(observation.memory_file)
    extends = capture.extends_from_messages(capture.parse_tpm_log(observation.tpm_log))
    report = gate.evaluate(cut.events, extends, observation.live_pcrs, cut.candidates,
                           cut.banks or BANK_NAMES)
    gate.require(report)
    lines = capture.clean_console(observation.console_raw)
    return _Evidence(cut.events, cut.raw, observation.live_pcrs, report, lines)


def _outcome(observation: Observation, lines: list[str], limits: Limits) -> dict[str, object]:
    """The outcome block: how the boot ended and by which rule its end was decided."""
    return {
        "result": capture.classify_outcome(lines),
        "refusal_lines": capture.refusal_lines(lines),
        "trigger": observation.trigger,
        "ending": observation.ending,
        "settled": observation.settled,
        "settle_rule": limits.settle_rule,
    }


def _require_allowed_outcome(experiment: Experiment, outcome: dict[str, object]) -> None:
    """Refuse a boot that may not become a recording. Raises `RunIncomplete`.

    Two rules. A boot whose end was not seen in time may have been paused in
    the middle of its work, so it is never recorded. And the normal run has
    exactly one allowed result: a hung or refused "normal" run is a broken
    setup, and two of them would otherwise satisfy the repeat precondition.
    A changed run that reached neither line is recorded as `timeout`,
    because that can be the true result of the change.
    """
    if not outcome["settled"]:
        raise RunIncomplete("the end of the boot was not seen in time (" + str(outcome["settle_rule"])
                            + "), so the run is not recorded")
    if experiment.kind == experiments.KIND_NORMAL and outcome["result"] != capture.OUTCOME_ACCEPTED:
        raise RunIncomplete(f"the normal run ended as '{outcome['result']}'; only 'accepted' is "
                            "a normal run, so nothing is recorded")


def _provenance(request: RunRequest, env: Environment, staged: staging.StagedRun,
                machine: Machine, prediction_ref: prediction.PredictionRef | None) -> dict[str, object]:
    """The provenance block: everything needed to reproduce the run."""
    run_directory = str(staged.run_directory)
    return {
        "recorded_at": request.recorded_at,
        "tools": env.tool_versions(),
        "host_os": env.host_os,
        "firmware": {"file": staged.firmware.name, "sha256": staged.firmware_sha256},
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
    pins = keys.pins_of(keys.verify(env.testkeys_directory))
    template = env.work_directory / TEMPLATE_PATH
    if not template.is_file():
        raise StagingRefused("no variable store template found; run the prepare command first")
    if recording.sha256_of_file(template) != pins.vars_template_sha256:
        raise StagingRefused("the variable store template differs from the committed manifest")
    return staging.Assets(env.testkeys_directory / keys.SIGNED_LOADER_NAME, template,
                          pins.firmware_sha256)


def record_run(request: RunRequest, env: Environment) -> RunResult:
    """Record one run. Raises a `LuxError` subclass instead of writing a doubtful result."""
    experiment = experiments.get(request.experiment)
    prediction_ref = None
    if experiment.kind == experiments.KIND_COUNTED:
        prediction_ref = prediction.require_committed(experiment, env.predictions_directory, env.git)
        env.require_repeat()
    if not _RUN_NAME.fullmatch(request.name):
        raise StagingRefused("a run name uses lowercase letters, digits and hyphens only")

    run_directory = env.work_directory / "runs" / request.name
    parameters = prediction_ref.parameters if prediction_ref else {}
    staged = staging.stage_run(experiment, run_directory, _assets(env), parameters,
                               request.firmware_override)
    machine = env.machine_factory(staged.run_directory, staged.firmware)
    observation = run_boot(machine, env.clock, env.limits)
    evidence = _collect_evidence(observation)
    outcome = _outcome(observation, evidence.lines, env.limits)
    _require_allowed_outcome(experiment, outcome)
    console, loader_report = capture.split_console(evidence.lines)

    facts = recording.RunFacts(
        name=request.name,
        experiment=experiment.identifier,
        experiment_sha256=experiments.fingerprint(experiment),
        kind=experiment.kind,
        change=experiment.change,
        change_detail=staged.change_detail(),
        provenance=_provenance(request, env, staged, machine, prediction_ref),
        outcome=outcome,
        timing={"seconds_to_trigger": normalise.round_seconds(observation.seconds_to_trigger),
                "seconds_to_pause": normalise.round_seconds(observation.seconds_to_pause)},
        console=console,
        loader_report=loader_report,
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
