"""Build the recording of one boot and write it the same way every time.

A recording is one JSON document. It is written deterministically (UTF-8,
LF line ends, two-space indent, sorted keys, lowercase hex) so that two
identical boots give files that differ only in the fields listed in
`MAY_VARY`.
"""
import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from recorder import eventlog, storymap
from recorder.banks import PcrBanks, banks_to_hex
from recorder.errors import FormatError
from recorder.eventlog import Event

RECORDING_FORMAT = "lux-recording/1"

# The complete list of fields a comparison ignores. Everything else must be
# equal between two normal runs.
MAY_VARY: tuple[str, ...] = (
    "provenance.recorded_at",
    "run.name",
    "timing.seconds_to_pause",
    "timing.seconds_to_trigger",
)


@dataclass(frozen=True)
class RunFacts:
    """Everything about one boot that goes into its recording."""

    name: str
    experiment: str
    experiment_sha256: str                    # fingerprint of the experiment's description
    kind: str
    change: str
    change_detail: dict[str, object] | None   # proof of what was changed; None for no change
    provenance: dict[str, object]
    outcome: dict[str, object]
    timing: dict[str, float]
    console: list[str]                        # firmware lines and the loader's status lines
    loader_report: list[str]                  # the loader's memory map and table dump
    events: tuple[Event, ...]
    pcrs: PcrBanks
    event_log_bytes: bytes
    vars_after_sha256: str
    gate: dict[str, object]


def event_row(event: Event) -> dict[str, object]:
    """One event in the shape the recording stores."""
    stop, rule = storymap.assign_stop(event)
    return {
        "index": event.index,
        "pcr": event.pcr,
        "type": eventlog.type_name(event.type_code),
        "type_code": f"0x{event.type_code:08x}",
        "digest_sha256": event.digests.get("sha256", b"").hex(),
        "summary": eventlog.summarise(event),
        "stop": stop,
        "stop_rule": rule,
    }


def build_recording(facts: RunFacts) -> dict[str, object]:
    """Assemble the recording document from the facts of one boot."""
    return {
        "format": RECORDING_FORMAT,
        "run": {"name": facts.name, "experiment": facts.experiment,
                "experiment_sha256": facts.experiment_sha256,
                "kind": facts.kind, "change": facts.change,
                "change_detail": facts.change_detail},
        "provenance": facts.provenance,
        "outcome": facts.outcome,
        "timing": facts.timing,
        "console": facts.console,
        "loader_report": facts.loader_report,
        "events": [event_row(event) for event in facts.events],
        "pcrs": banks_to_hex(facts.pcrs),
        "event_log": {
            "sha256": hashlib.sha256(facts.event_log_bytes).hexdigest(),
            "bytes": len(facts.event_log_bytes),
            "events": len(facts.events),
        },
        "vars_after_sha256": facts.vars_after_sha256,
        "gate": facts.gate,
        "may_vary": list(MAY_VARY),
    }


def dumps(document: dict[str, object]) -> str:
    """The one way a document becomes text: sorted keys, two spaces, LF, final newline."""
    return json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


def write_json(path: Path, document: dict[str, object]) -> None:
    """Write a document as UTF-8 with LF line ends, whatever the platform."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(dumps(document).encode("utf-8"))


def load_json(path: Path, expected_format: str) -> dict[str, object]:
    """Read a document and check its `format` field."""
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise FormatError(f"cannot read {path.name}: {error}") from error
    if not isinstance(document, dict) or document.get("format") != expected_format:
        raise FormatError(f"{path.name} is not a '{expected_format}' document")
    return document


def sha256_of_file(path: Path) -> str:
    """SHA-256 of a file's bytes, as lowercase hex."""
    return hashlib.sha256(path.read_bytes()).hexdigest()
