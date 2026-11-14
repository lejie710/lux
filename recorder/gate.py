"""The agreement gate: three readings of one boot must tell the same story.

1. Replay of the event log: start every register at its start value, then
   apply each logged event in order.
2. Replay of the extend commands found in the software TPM's log.
3. The register values read from the TPM after the guest was paused.

If these disagree anywhere, in any of the 24 registers of any of the four
hash banks, the recording would show a register table that does not follow
from its own event list. Such a run is refused: `require` raises
`GateFailure` and nothing is written.
"""
from dataclasses import dataclass

from recorder.banks import BANK_NAMES, PCR_COUNT, PcrBanks, extend, start_banks
from recorder.capture import Extend
from recorder.errors import GateFailure
from recorder.eventlog import Event, content_digests_match


@dataclass(frozen=True)
class GateReport:
    """Result of the gate: each named check, and the reasons for any failure."""

    checks: dict[str, bool | int]
    failures: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """True when no check failed."""
        return not self.failures


def replay_events(events: tuple[Event, ...] | list[Event]) -> PcrBanks:
    """Register values that follow from the event log alone."""
    banks = start_banks()
    for event in events:
        if not event.is_extended:
            continue
        for bank, digest in event.digests.items():
            if bank in banks:
                banks[bank][event.pcr] = extend(bank, banks[bank][event.pcr], digest)
    return banks


def replay_extends(extends: list[Extend]) -> PcrBanks:
    """Register values that follow from the extend commands the TPM accepted."""
    banks = start_banks()
    for item in extends:
        if item.response_code != 0:
            continue
        for bank, digest in item.digests.items():
            banks[bank][item.pcr] = extend(bank, banks[bank][item.pcr], digest)
    return banks


def differing_registers(first: PcrBanks, second: PcrBanks) -> dict[str, list[int]]:
    """Per bank, the register indexes at which two sets of values differ.

    A bank or register missing on either side counts as different.
    """
    result: dict[str, list[int]] = {}
    for bank in BANK_NAMES:
        left, right = first.get(bank, []), second.get(bank, [])
        differing = [
            index for index in range(PCR_COUNT)
            if index >= len(left) or index >= len(right) or left[index] != right[index]
        ]
        if differing:
            result[bank] = differing
    return result


def _same_sequence(events: list[Event], extends: list[Extend]) -> bool:
    """True when extend n carries the register and digests of logged event n."""
    logged = [(event.pcr, event.digests) for event in events]
    sent = [(item.pcr, item.digests) for item in extends]
    return logged == sent


def evaluate(events: tuple[Event, ...], extends: list[Extend], live: PcrBanks,
             log_candidates: int) -> GateReport:
    """Run every check and collect the results.

    `log_candidates` is how many places in guest memory parsed as an event
    log. Exactly one is required, so that the log was chosen by structure.
    """
    extended_events = [event for event in events if event.is_extended]
    recomputed = [content_digests_match(event) for event in events]
    log_vs_live = differing_registers(replay_events(events), live)
    extends_vs_live = differing_registers(replay_extends(extends), live)

    checks: dict[str, bool | int] = {
        "event_log_replay_equals_live": not log_vs_live,
        "extend_list_replay_equals_live": not extends_vs_live,
        "event_sequence_equals_extend_sequence": _same_sequence(extended_events, extends),
        "all_extends_answered_ok": all(item.response_code == 0 for item in extends),
        "content_digests_match": False not in recomputed,
        "content_digests_recomputed": recomputed.count(True),
        "log_candidates_parsed": log_candidates,
    }
    failures = [name for name, value in checks.items() if value is False]
    if log_candidates != 1:
        failures.append(f"log_candidates_parsed is {log_candidates}, exactly 1 is required")
    if log_vs_live:
        failures.append(f"event log replay differs from the live read at {log_vs_live}")
    if extends_vs_live:
        failures.append(f"extend list replay differs from the live read at {extends_vs_live}")
    return GateReport(checks, tuple(failures))


def require(report: GateReport) -> None:
    """Raise `GateFailure` unless every check passed."""
    if not report.passed:
        raise GateFailure("the readings of this boot disagree: " + "; ".join(report.failures))


def gate_block(report: GateReport) -> dict[str, object]:
    """The gate result in the shape the recording stores."""
    return {
        "passed": report.passed,
        "banks": len(BANK_NAMES),
        "pcrs_per_bank": PCR_COUNT,
        "checks": dict(report.checks),
    }
