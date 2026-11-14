"""The command line: prepare, record, compare, check.

    python3 -m recorder prepare
    python3 -m recorder record normal-1 --experiment normal
    python3 -m recorder compare recordings/normal-1/recording.json \\
        recordings/e2/recording.json --out recordings/comparisons/normal-1_vs_e2.json
    python3 -m recorder check COMPARISON --prediction PREDICTION --recording RECORDING

Every failure the recorder understands ends with one plain sentence on the
error stream and exit code 1. Exit code 2 is a wrong command line.
"""
import argparse
import datetime
import os
import sys
from pathlib import Path

from recorder import compare, prediction, preparation, provenance, recording, runner
from recorder.errors import FormatError, LuxError
from recorder.session import Limits, QemuMachine, SystemClock

REPOSITORY = Path(__file__).resolve().parent.parent
TESTKEYS = REPOSITORY / "recorder" / "testkeys"
WORK_DIRECTORY_VARIABLE = "LUX_WORK_DIR"


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
    prepare.add_argument("--work-dir", type=Path, default=None)

    record = commands.add_parser("record", help="boot once and write a recording")
    record.add_argument("name", help="run name, for example normal-1")
    record.add_argument("--experiment", required=True)
    record.add_argument("--out", type=Path, default=REPOSITORY / "recordings")
    record.add_argument("--firmware-file", type=Path, default=None)
    record.add_argument("--work-dir", type=Path, default=None)

    comparison = commands.add_parser("compare", help="compare two recordings")
    comparison.add_argument("baseline", type=Path)
    comparison.add_argument("changed", type=Path)
    comparison.add_argument("--out", type=Path, required=True)

    check = commands.add_parser("check", help="score a comparison against its prediction")
    check.add_argument("comparison", type=Path)
    check.add_argument("--prediction", type=Path, required=True)
    check.add_argument("--recording", type=Path, required=True,
                       help="the changed run's recording, which names its prediction")
    return parser


def _prepare(arguments: argparse.Namespace) -> int:
    provenance.require_programs()
    env = preparation.PrepareEnvironment(
        testkeys_directory=TESTKEYS,
        work_directory=arguments.work_dir or default_work_directory(),
        run=provenance.run_command,
        machine_factory=QemuMachine,
        clock=SystemClock(),
        limits=Limits(),
    )
    summary = preparation.prepare(env, generate_keys=arguments.generate_keys)
    for key, value in sorted(summary.items()):
        print(f"{key}: {value}")
    print("prepared")
    return 0


def _record(arguments: argparse.Namespace) -> int:
    provenance.require_programs()
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
    )
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    request = runner.RunRequest(arguments.name, arguments.experiment, now, arguments.firmware_file)
    result = runner.record_run(request, env)
    target = arguments.out / arguments.name
    recording.write_json(target / "recording.json", result.document)
    (target / "eventlog.bin").write_bytes(result.event_log)
    outcome, gate = result.document["outcome"], result.document["gate"]
    print(f"run {arguments.name}: {outcome['result']}, {len(result.document['events'])} events, "
          f"agreement gate {'passed' if gate['passed'] else 'FAILED'}")
    print(f"written: {target / 'recording.json'}")
    return 0


def _compare(arguments: argparse.Namespace) -> int:
    baseline = recording.load_json(arguments.baseline, recording.RECORDING_FORMAT)
    changed = recording.load_json(arguments.changed, recording.RECORDING_FORMAT)
    document = compare.compare_recordings(
        baseline, changed,
        recording.sha256_of_file(arguments.baseline), recording.sha256_of_file(arguments.changed))
    recording.write_json(arguments.out, document)
    print(f"identical: {str(document['identical']).lower()}")
    print(f"registers differing (sha256): {document['pcrs_differing']['sha256']}")
    print(f"written: {arguments.out}")
    return 0


def _check(arguments: argparse.Namespace) -> int:
    comparison = recording.load_json(arguments.comparison, compare.COMPARISON_FORMAT)
    changed = recording.load_json(arguments.recording, recording.RECORDING_FORMAT)
    if comparison["changed"]["recording_sha256"] != recording.sha256_of_file(arguments.recording):
        raise FormatError("the comparison was not made from this recording")
    if not prediction.unchanged_since_run(changed, arguments.prediction):
        raise FormatError("the prediction file is not the one this run was recorded under "
                          "(a pilot has none; an edited prediction no longer matches)")
    result = prediction.score(prediction.load(arguments.prediction), comparison)
    print(f"specification-required rows met: {result['required_met']} of {result['required_total']}")
    print(f"open rows predicted correctly: {result['open_correct']} of {result['open_total']}")
    print("mismatches: " + (", ".join(result["mismatches"]) or "none"))
    return 0


def main(argv: list[str]) -> int:
    """Run one command; return the process exit code."""
    arguments = _parser().parse_args(argv)
    handlers = {"prepare": _prepare, "record": _record, "compare": _compare, "check": _check}
    try:
        return handlers[arguments.command](arguments)
    except LuxError as error:
        print(f"refused: {error}", file=sys.stderr)
        return 1
