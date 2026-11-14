"""Compare two recordings on the compared fields and say where they differ.

The comparison is the evidence for both parts of the measure:

* two normal runs must come out `identical` (the repeat precondition);
* a changed run is described by its first differing event, the registers
  that differ, and the events present in only one of the runs.

The list of ignored fields is `recording.MAY_VARY` and nothing else. A
recording cannot hide a field by listing it in its own `may_vary`: that list
is itself compared against the fixed one.
"""
from collections import Counter

from recorder.banks import BANK_NAMES, PCR_COUNT
from recorder.recording import MAY_VARY

COMPARISON_FORMAT = "lux-comparison/1"

# Top-level parts that get their own block in the comparison document.
_OWN_BLOCKS = ("events", "pcrs", "console")
_OUTCOME_RESULT = "outcome.result"

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

    Skipped: the fixed `MAY_VARY` list, and the parts reported in their own
    blocks (events, registers, console, the outcome result).
    """
    left = _leaves({k: v for k, v in baseline.items() if k not in _OWN_BLOCKS})
    right = _leaves({k: v for k, v in changed.items() if k not in _OWN_BLOCKS})
    skipped = set(MAY_VARY) | {_OUTCOME_RESULT}
    missing = object()
    differing = {
        path for path in set(left) | set(right)
        if path not in skipped and left.get(path, missing) != right.get(path, missing)
    }
    if any(document.get("may_vary") != list(MAY_VARY) for document in (baseline, changed)):
        differing.add("may_vary")
    return sorted(differing)


def compare_recordings(baseline: dict, changed: dict,
                       baseline_sha256: str, changed_sha256: str) -> dict[str, object]:
    """Build the comparison document for a baseline and a changed recording."""
    pcrs_differing, pcrs_same = compare_pcrs(baseline["pcrs"], changed["pcrs"])
    first_event = first_differing_event(baseline["events"], changed["events"])
    console_line = first_differing_line(baseline["console"], changed["console"])
    other = other_fields_differing(baseline, changed)
    outcome = {"baseline": baseline["outcome"]["result"], "changed": changed["outcome"]["result"]}
    identical = (
        first_event is None and console_line is None and not other
        and outcome["baseline"] == outcome["changed"]
        and not any(pcrs_differing.values())
    )
    return {
        "format": COMPARISON_FORMAT,
        "baseline": {"run": baseline["run"]["name"], "recording_sha256": baseline_sha256},
        "changed": {"run": changed["run"]["name"], "recording_sha256": changed_sha256},
        "identical": identical,
        "outcome": outcome,
        "first_differing_event": first_event,
        "pcrs_differing": pcrs_differing,
        "pcrs_same": pcrs_same,
        "events_only_in_baseline": events_only_in(baseline["events"], changed["events"]),
        "events_only_in_changed": events_only_in(changed["events"], baseline["events"]),
        "console_first_differing_line": console_line,
        "other_fields_differing": other,
    }
