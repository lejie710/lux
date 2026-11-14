"""The command line: prepare, record, compare, check.

    python3 -m recorder prepare
    python3 -m recorder prepare --changed-boot-order
    python3 -m recorder record my-normal --experiment normal
    python3 -m recorder compare recordings/normal-1/recording.json \\
        recordings/e2/recording.json --out recordings/comparisons/normal-1_vs_e2.json
    python3 -m recorder check COMPARISON --prediction PREDICTION --recording RECORDING \\
        --baseline BASELINE --repeat REPEAT --out SCORE

Exit codes:

* 0: done. For `check` this means "scored", not "every row held".
* 1: refused. One plain sentence on the error stream says why.
* 2: a wrong command line.
* 3: `record` wrote a recording of a changed run that reached neither the
  loader's final line nor a refusal (`timeout`). The file is kept, because
  that can be the true result of a change, and the exit code makes sure a
  script does not take it for an ordinary run.
"""
import argparse
import datetime
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from recorder import (capture, compare, experiments, prediction, preparation, provenance,
                      recording, runner)
from recorder.errors import (ComparisonRefused, FormatError, LuxError, PredictionMissing,
                             RecordingExists, StagingRefused)
from recorder.experiments import Experiment
from recorder.session import Limits, QemuMachine, SystemClock

REPOSITORY = Path(__file__).resolve().parent.parent
TESTKEYS = REPOSITORY / "recorder" / "testkeys"
WORK_DIRECTORY_VARIABLE = "LUX_WORK_DIR"
# The comparison of the two committed normal runs, inside the recordings directory.
REPEAT_COMPARISON = Path("comparisons") / "normal-1_vs_normal-2.json"


def repeat_comparison(baseline: str) -> Path:
    """Where the comparison of a normal run's two recordings lives, inside the recordings directory."""
    return Path("comparisons") / f"{baseline}-1_vs_{baseline}-2.json"

EXIT_DONE = 0
EXIT_REFUSED = 1
EXIT_TIMEOUT_RECORDED = 3


def default_work_directory() -> Path:
    """Scratch space for run directories: `$LUX_WORK_DIR`, else `~/lux-work`.

    It must be on a Linux file system; unix sockets do not work on a
    Windows-mounted drive.
    """
    return Path(os.environ.get(WORK_DIRECTORY_VARIABLE) or Path.home() / "lux-work")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python3 -m recorder", description=__doc__.split("\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser("prepare", help="verify keys, build the loader, make the template")
    prepare.add_argument("--generate-keys", action="store_true",
                         help="create the test keys; refused when keys already exist")
    prepare.add_argument("--changed-boot-order", action="store_true",
                         help="make the variable store with the changed boot order; refused "
                              "unless a boot order prediction is committed")
    prepare.add_argument("--work-dir", type=Path, default=None)

    record = commands.add_parser("record", help="boot once and write a recording")
    record.add_argument("name", help="run name, for example my-normal")
    record.add_argument("--experiment", required=True)
    record.add_argument("--out", type=Path, default=REPOSITORY / "recordings",
                        help="directory that holds one folder per recording")
    record.add_argument("--replace", action="store_true",
                        help="overwrite an existing recording of this name; never allowed "
                             "for a counted experiment")
    record.add_argument("--for-the-record", action="store_true",
                        help="needed for a counted experiment: says that this boot is its "
                             "one run, made on purpose")
    record.add_argument("--repeat", type=Path, default=None,
                        help="comparison of two normal runs, needed before a counted "
                             "experiment (default: <out>/comparisons/<normal run>-1_vs_"
                             "<normal run>-2.json, for the normal run the experiment changes)")
    record.add_argument("--firmware-file", type=Path, default=None,
                        help="rebuilt firmware; its hash must be pinned in the prediction")
    record.add_argument("--work-dir", type=Path, default=None)

    comparison = commands.add_parser("compare", help="compare two recordings")
    comparison.add_argument("baseline", type=Path, help="a recording of the normal run")
    comparison.add_argument("changed", type=Path)
    comparison.add_argument("--out", type=Path, required=True)

    check = commands.add_parser("check", help="score a comparison against its prediction")
    check.add_argument("comparison", type=Path)
    check.add_argument("--prediction", type=Path, required=True)
    check.add_argument("--recording", type=Path, required=True,
                       help="the changed run's recording, which names its prediction")
    check.add_argument("--baseline", type=Path, required=True,
                       help="the normal run's recording the comparison was made against")
    check.add_argument("--repeat", type=Path, default=None,
                       help="comparison of two normal runs; required for a counted run")
    check.add_argument("--out", type=Path, default=None, help="write the score document here")
    return parser


def _shown(path: Path) -> str:
    """A path as printed: relative to the current directory when it lies inside it."""
    try:
        return path.resolve().relative_to(Path.cwd().resolve()).as_posix()
    except ValueError:
        return str(path)


@contextmanager
def _complete_documents() -> Iterator[None]:
    """Turn a missing or misshapen field of a loaded document into a `FormatError`.

    A file can have the right `format` line and still lack a field. That is
    a refusal with a sentence, not a Python traceback.
    """
    try:
        yield
    except (KeyError, TypeError, AttributeError) as error:
        raise FormatError(f"a document lacks a field this command needs: {error!r}") from error


# ---------------------------------------------------------------- prepare

def _prepare(arguments: argparse.Namespace) -> int:
    provenance.require_programs()
    if arguments.generate_keys:
        provenance.require_programs(provenance.KEY_GENERATION_PROGRAMS)
    env = preparation.PrepareEnvironment(
        testkeys_directory=TESTKEYS,
        work_directory=arguments.work_dir or default_work_directory(),
        run=provenance.run_command,
        machine_factory=QemuMachine,
        clock=SystemClock(),
        limits=Limits(),
    )
    if arguments.changed_boot_order:
        _require_boot_order_prediction()
        summary = preparation.prepare_changed_boot_order(env)
    else:
        summary = preparation.prepare(env, generate_keys=arguments.generate_keys)
    for key, value in sorted(summary.items()):
        print(f"{key}: {value}")
    print("prepared")
    return EXIT_DONE


def _require_boot_order_prediction() -> None:
    """Refuse to make the changed boot order unless a prediction for it is committed.

    The store with the changed order is the changed configuration of a
    counted experiment. Nothing of it is made before the prediction exists,
    so that it cannot be tried out first. Raises `PredictionMissing`.
    """
    uses_it = [experiment for experiment in experiments.EXPERIMENTS.values()
               if experiment.store == experiments.STORE_TWO_ENTRIES_B_FIRST]
    refusals: list[PredictionMissing] = []
    for experiment in uses_it:
        try:
            prediction.require_committed(experiment, REPOSITORY / "predictions", prediction.run_git)
            return
        except PredictionMissing as error:
            refusals.append(error)
    raise PredictionMissing("the changed boot order is not prepared: " + str(refusals[0]))


# ---------------------------------------------------------------- record

def _require_free_target(target: Path, experiment: Experiment, replace: bool) -> None:
    """Refuse to overwrite a recording. Raises `RecordingExists`.

    A recording is evidence. Writing over it by accident would lose it, and
    writing over a counted run would allow an experiment to be repeated
    until its result pleases. So an existing name needs `--replace`, and a
    counted experiment's recording is never replaced.
    """
    if not target.exists():
        return
    if experiment.kind == experiments.KIND_COUNTED:
        raise RecordingExists(f"a recording named '{target.name}' exists, and a counted "
                              "experiment is recorded once; choose another run name")
    if not replace:
        raise RecordingExists(f"a recording named '{target.name}' exists; choose another "
                              "run name, or pass --replace to overwrite it on purpose")


def _require_repeat_on_file(repeat_file: Path, recordings: Path,
                            baseline: str = compare.NORMAL_EXPERIMENT) -> None:
    """The repeat precondition, checked against the files on disk.

    The comparison must say that two recordings of the normal run `baseline`
    are identical, and both recordings it names must still be there with the
    hashes it stored.
    """
    if not repeat_file.is_file():
        raise ComparisonRefused(
            f"no comparison of two normal runs at {_shown(repeat_file)}; record the normal "
            "run twice and compare the two before any counted experiment")
    repeat = recording.load_json(repeat_file, compare.COMPARISON_FORMAT)
    with _complete_documents():
        for side in (repeat["baseline"], repeat["changed"]):
            file = recordings / side["run"] / "recording.json"
            if not file.is_file() or recording.sha256_of_file(file) != side["recording_sha256"]:
                raise ComparisonRefused(f"the recording '{side['run']}' named by the repeat "
                                        "comparison is missing or has changed")
        compare.require_repeat(repeat, repeat["baseline"]["recording_sha256"], baseline)


def _require_meant(experiment: Experiment, for_the_record: bool) -> None:
    """Refuse to boot a counted experiment unless the caller says this is its one run.

    Once a prediction is committed, nothing else stands between a typed
    command and the single boot a counted experiment gets. So the command
    line must say it in so many words. Raises `StagingRefused` before the
    prediction is looked at and before anything is staged.
    """
    if experiment.kind == experiments.KIND_COUNTED and not for_the_record:
        raise StagingRefused(
            f"experiment '{experiment.identifier}' is counted: it is booted once, for the "
            "record. Pass --for-the-record when this boot is meant to be that one run")


def _record(arguments: argparse.Namespace) -> int:
    provenance.require_programs()
    experiment = experiments.get(arguments.experiment)
    _require_meant(experiment, arguments.for_the_record)
    target = arguments.out / arguments.name
    _require_free_target(target, experiment, arguments.replace)
    repeat_file = arguments.repeat or arguments.out / repeat_comparison(experiment.baseline)
    env = runner.Environment(
        testkeys_directory=TESTKEYS,
        predictions_directory=REPOSITORY / "predictions",
        work_directory=arguments.work_dir or default_work_directory(),
        machine_factory=QemuMachine,
        clock=SystemClock(),
        limits=Limits(),
        tool_versions=provenance.tool_versions,
        host_os=provenance.host_os(),
        git=prediction.run_git,
        require_repeat=lambda: _require_repeat_on_file(repeat_file, arguments.out,
                                                       experiment.baseline),
    )
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    request = runner.RunRequest(arguments.name, arguments.experiment, now, arguments.firmware_file)
    result = runner.record_run(request, env)
    recording.write_json(target / "recording.json", result.document)
    (target / "eventlog.bin").write_bytes(result.event_log)
    outcome = result.document["outcome"]
    print(f"run {arguments.name}: {outcome['result']}, {len(result.document['events'])} events, "
          "agreement gate passed")
    print(f"written: {_shown(target / 'recording.json')}")
    if outcome["result"] == capture.OUTCOME_TIMEOUT:
        print("attention: this boot reached neither the loader's final line nor a refusal; "
              "it was recorded as 'timeout'", file=sys.stderr)
        return EXIT_TIMEOUT_RECORDED
    return EXIT_DONE


# ---------------------------------------------------------------- compare

def _compare(arguments: argparse.Namespace) -> int:
    baseline = recording.load_json(arguments.baseline, recording.RECORDING_FORMAT)
    changed = recording.load_json(arguments.changed, recording.RECORDING_FORMAT)
    baseline_sha256 = recording.sha256_of_file(arguments.baseline)
    changed_sha256 = recording.sha256_of_file(arguments.changed)
    with _complete_documents():
        compare.require_comparable(baseline, changed, baseline_sha256, changed_sha256)
        document = compare.compare_recordings(baseline, changed, baseline_sha256, changed_sha256)
    recording.write_json(arguments.out, document)
    print(f"identical: {str(document['identical']).lower()}")
    print(f"registers differing (sha256): {document['pcrs_differing']['sha256']}")
    print(f"written: {_shown(arguments.out)}")
    return EXIT_DONE


# ---------------------------------------------------------------- check

def _require_scorable(arguments: argparse.Namespace, comparison: dict, changed: dict,
                      baseline: dict) -> str | None:
    """Everything that must hold before a score means anything.

    Returns the SHA-256 of the repeat comparison for a counted run, None for
    any other. Raises `ComparisonRefused` or `FormatError`.
    """
    if comparison["changed"]["recording_sha256"] != recording.sha256_of_file(arguments.recording):
        raise ComparisonRefused("the comparison was not made from this recording")
    if comparison["baseline"]["recording_sha256"] != recording.sha256_of_file(arguments.baseline):
        raise ComparisonRefused("the comparison was not made against this baseline recording")
    if baseline["run"]["kind"] != compare.NORMAL_KIND or baseline["run"]["experiment"] != \
            compare.baseline_experiment(changed["run"]["experiment"]):
        raise ComparisonRefused("the baseline must be a recording of the normal run this "
                                "experiment changes")
    if not prediction.unchanged_since_run(changed, arguments.prediction):
        raise FormatError("the prediction file is not the one this run was recorded under "
                          "(a pilot has none; an edited prediction no longer matches)")
    experiment = experiments.get(changed["run"]["experiment"])
    if experiments.fingerprint(experiment) != changed["run"]["experiment_sha256"]:
        raise ComparisonRefused("the experiment's description was changed after this run")
    if experiment.kind != experiments.KIND_COUNTED:
        return None
    if arguments.repeat is None:
        raise ComparisonRefused("a counted run is scored only together with --repeat, the "
                                "comparison that shows two normal runs are identical")
    repeat = recording.load_json(arguments.repeat, compare.COMPARISON_FORMAT)
    compare.require_repeat(repeat, comparison["baseline"]["recording_sha256"], experiment.baseline)
    return recording.sha256_of_file(arguments.repeat)


def _check(arguments: argparse.Namespace) -> int:
    comparison = recording.load_json(arguments.comparison, compare.COMPARISON_FORMAT)
    changed = recording.load_json(arguments.recording, recording.RECORDING_FORMAT)
    baseline = recording.load_json(arguments.baseline, recording.RECORDING_FORMAT)
    with _complete_documents():
        repeat_sha256 = _require_scorable(arguments, comparison, changed, baseline)
        predicted = prediction.load(arguments.prediction)
        if not prediction.fits_baseline(predicted, comparison):
            raise ComparisonRefused("the prediction was written against another baseline "
                                    "recording than the one this comparison uses")
        result = prediction.score(predicted, comparison)
        document = prediction.score_document(result, {
            "run": changed["run"]["name"],
            "prediction": changed["provenance"]["prediction"],
            "comparison_sha256": recording.sha256_of_file(arguments.comparison),
            "baseline_recording_sha256": comparison["baseline"]["recording_sha256"],
            "changed_recording_sha256": comparison["changed"]["recording_sha256"],
            "repeat_comparison_sha256": repeat_sha256,
        })
    print(f"specification-required rows met: {result['required_met']} of {result['required_total']}")
    print(f"open rows predicted correctly: {result['open_correct']} of {result['open_total']}")
    print("mismatches: " + (", ".join(result["mismatches"]) or "none"))
    if arguments.out is not None:
        recording.write_json(arguments.out, document)
        print(f"written: {_shown(arguments.out)}")
    return EXIT_DONE


def main(argv: list[str]) -> int:
    """Run one command; return the process exit code."""
    arguments = _parser().parse_args(argv)
    handlers = {"prepare": _prepare, "record": _record, "compare": _compare, "check": _check}
    try:
        return handlers[arguments.command](arguments)
    except LuxError as error:
        print(f"refused: {error}", file=sys.stderr)
        return EXIT_REFUSED
