"""Compare two recordings on the compared fields and say where they differ.

The comparison is the evidence for both parts of the measure:

* two normal runs must come out `identical` (the repeat precondition);
* a changed run is described by its first differing event, the registers
  that differ, and the events present in only one of the runs.

The list of ignored fields is `recording.MAY_VARY` and nothing else. A
recording cannot hide a field by listing it in its own `may_vary`: that list
is itself compared against the fixed one.

Some pairs must not be compared at all, because the result would look like
evidence and be none: a recording with itself or with a copy of itself, a
recording whose agreement gate did not pass, a baseline that is not a normal
run. `require_comparable` refuses those, and `require_repeat` checks that a
comparison really is the repeat precondition.
"""
from collections import Counter

from recorder.banks import BANK_NAMES, PCR_COUNT
from recorder.errors import ComparisonRefused
from recorder.recording import MAY_VARY

COMPARISON_FORMAT = "lux-comparison/1"
NORMAL_EXPERIMENT = "normal"

# Top-level parts that get their own block in the comparison document.
_OWN_BLOCKS = ("events", "pcrs", "console", "loader_report")
# Fields reported in the comparison's own `outcome` and `refusal_lines` blocks.
_OUTCOME_FIELDS = ("outcome.result", "outcome.refusal_lines")
# What the experiment is. These differ between a normal and a changed run by
# definition, and the comparison names both experiments in its header, so
# listing them again among the differences would only be noise.
_EXPERIMENT_IDENTITY = ("run.experiment", "run.experiment_sha256", "run.kind",
                        "run.change", "run.change_detail")

EventKey = tuple[int, str, str]


def _event_key(row: dict[str, object]) -> EventKey:
    """Events are matched by register, type and SHA-256 digest."""
    return (int(row["pcr"]), str(row["type"]), str(row["digest_sha256"]))


def _event_view(row: dict[str, object] | None) -> dict[str, object] | None:
    """The three matching fields of an event, or None when the run has no such event."""
    if row is None:
        return None
    return {"pcr": row["pcr"], "type": row["type"], "digest_sha256": row["digest_sha256"]}


def first_differing_event(baseline: list[dict], changed: list[dict]) -> dict[str, object] | None:
    """The first position at which the two event lists differ, in log order."""
    for position in range(max(len(baseline), len(changed))):
        left = baseline[position] if position < len(baseline) else None
        right = changed[position] if position < len(changed) else None
        if left is None or right is None or _event_key(left) != _event_key(right):
            stop_source = left if left is not None else right
            return {
                "index": position + 1,
                "stop": stop_source["stop"],
                "baseline": _event_view(left),
                "changed": _event_view(right),
            }
    return None


def events_only_in(first: list[dict], second: list[dict]) -> list[dict[str, object]]:
    """Events of `first` that have no equal partner in `second`, in log order.

    An event that occurs twice in one run and once in the other is listed
    once: partners are used up one by one.
    """
    available = Counter(_event_key(row) for row in second)
    alone: list[dict[str, object]] = []
    for row in first:
        key = _event_key(row)
        if available[key] > 0:
            available[key] -= 1
        else:
            alone.append({"index": row["index"], **_event_view(row)})
    return alone


def compare_pcrs(baseline: dict, changed: dict) -> tuple[dict[str, list[int]], dict[str, list[int]]]:
    """Per bank, which register indexes differ and which are the same."""
    differing: dict[str, list[int]] = {}
    same: dict[str, list[int]] = {}
    for bank in BANK_NAMES:
        left, right = baseline.get(bank, {}), changed.get(bank, {})
        differing[bank] = [
            index for index in range(PCR_COUNT)
            if left.get(str(index)) is None or left.get(str(index)) != right.get(str(index))
        ]
        same[bank] = [index for index in range(PCR_COUNT) if index not in differing[bank]]
    return differing, same


def first_differing_line(baseline: list[str], changed: list[str]) -> int | None:
    """Number of the first console line that differs (starting at 1), or None."""
    for position in range(max(len(baseline), len(changed))):
        left = baseline[position] if position < len(baseline) else None
        right = changed[position] if position < len(changed) else None
        if left != right:
            return position + 1
    return None


def _leaves(value: object, prefix: str = "") -> dict[str, object]:
    """Flatten nested dictionaries into dotted paths; lists stay whole values."""
    if not isinstance(value, dict):
        return {prefix: value}
    flat: dict[str, object] = {}
    for key, item in value.items():
        flat.update(_leaves(item, f"{prefix}.{key}" if prefix else str(key)))
    return flat


def other_fields_differing(baseline: dict, changed: dict) -> list[str]:
    """Every remaining field that differs, as sorted dotted paths.

    Skipped: the fixed `MAY_VARY` list, the parts reported in their own
    blocks (events, registers, console, loader report, outcome), and the
    fields that say which experiment a run is.
    """
    left = _leaves({k: v for k, v in baseline.items() if k not in _OWN_BLOCKS})
    right = _leaves({k: v for k, v in changed.items() if k not in _OWN_BLOCKS})
    skipped = (*MAY_VARY, *_OUTCOME_FIELDS, *_EXPERIMENT_IDENTITY)

    def is_skipped(path: str) -> bool:
        """True for a skipped field and for everything nested inside one."""
        return any(path == field or path.startswith(field + ".") for field in skipped)

    missing = object()
    differing = {
        path for path in set(left) | set(right)
        if not is_skipped(path) and left.get(path, missing) != right.get(path, missing)
    }
    if any(document.get("may_vary") != list(MAY_VARY) for document in (baseline, changed)):
        differing.add("may_vary")
    return sorted(differing)


def _header(document: dict, recording_sha256: str) -> dict[str, object]:
    """Which recording one side of the comparison is."""
    run = document["run"]
    return {"run": run["name"], "experiment": run["experiment"], "kind": run["kind"],
            "recording_sha256": recording_sha256}


def require_comparable(baseline: dict, changed: dict,
                       baseline_sha256: str, changed_sha256: str) -> None:
    """Raise `ComparisonRefused` for a pair whose comparison would prove nothing.

    Two files with the same hash are one recording. Two recordings with the
    same recording time are a recording and its copy (the name and the time
    are the fields a comparison ignores, so a renamed copy would otherwise
    compare as identical). A recording whose agreement gate did not pass is
    not evidence. The baseline is always a normal run.
    """
    if baseline_sha256 == changed_sha256:
        raise ComparisonRefused("both files are the same recording")
    if baseline["provenance"]["recorded_at"] == changed["provenance"]["recorded_at"]:
        raise ComparisonRefused("both recordings carry the same recording time, so one is "
                                "a copy of the other and not a second boot")
    for side, document in (("baseline", baseline), ("changed", changed)):
        if document["gate"].get("passed") is not True:
            raise ComparisonRefused(f"the {side} recording did not pass the agreement gate")
    if baseline["run"]["experiment"] != NORMAL_EXPERIMENT:
        raise ComparisonRefused("the baseline must be a recording of the normal run")


def require_repeat(repeat: dict, baseline_sha256: str) -> None:
    """Raise `ComparisonRefused` unless `repeat` proves the normal run repeats.

    The repeat precondition: two different recordings of the normal run are
    identical on every compared field. `baseline_sha256` is the recording a
    changed run is measured against; the proof must be about that one.
    """
    sides = (repeat["baseline"], repeat["changed"])
    if any(side.get("experiment") != NORMAL_EXPERIMENT for side in sides):
        raise ComparisonRefused("the repeat comparison is not between two normal runs")
    if repeat["baseline"]["recording_sha256"] == repeat["changed"]["recording_sha256"]:
        raise ComparisonRefused("the repeat comparison compares a recording with itself")
    if repeat["identical"] is not True:
        raise ComparisonRefused("the two normal runs are not identical, so no experiment counts")
    if repeat["baseline"]["recording_sha256"] != baseline_sha256:
        raise ComparisonRefused("the repeat comparison was made for another baseline recording")


def compare_recordings(baseline: dict, changed: dict,
                       baseline_sha256: str, changed_sha256: str) -> dict[str, object]:
    """Build the comparison document for a baseline and a changed recording."""
    pcrs_differing, pcrs_same = compare_pcrs(baseline["pcrs"], changed["pcrs"])
    first_event = first_differing_event(baseline["events"], changed["events"])
    console_line = first_differing_line(baseline["console"], changed["console"])
    report_line = first_differing_line(baseline["loader_report"], changed["loader_report"])
    other = other_fields_differing(baseline, changed)
    outcome = {"baseline": baseline["outcome"]["result"], "changed": changed["outcome"]["result"]}
    refusals = {"baseline": baseline["outcome"]["refusal_lines"],
                "changed": changed["outcome"]["refusal_lines"]}
    identical = (
        first_event is None and console_line is None and report_line is None and not other
        and outcome["baseline"] == outcome["changed"]
        and refusals["baseline"] == refusals["changed"]
        and not any(pcrs_differing.values())
    )
    return {
        "format": COMPARISON_FORMAT,
        "baseline": _header(baseline, baseline_sha256),
        "changed": _header(changed, changed_sha256),
        "identical": identical,
        "outcome": outcome,
        "refusal_lines": refusals,
        "first_differing_event": first_event,
        "pcrs_differing": pcrs_differing,
        "pcrs_same": pcrs_same,
        "events_only_in_baseline": events_only_in(baseline["events"], changed["events"]),
        "events_only_in_changed": events_only_in(changed["events"], baseline["events"]),
        "console_first_differing_line": console_line,
        "loader_report_first_differing_line": report_line,
        "other_fields_differing": other,
    }
