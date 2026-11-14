"""Assign each logged event to one of the seven stops of the story.

The site tells a boot as seven stops: 1 reset, 2 SEC, 3 PEI, 4 DXE, 5 BDS,
6 load and verify, 7 handoff. The event log carries no timestamps and no
phase markers, and the UEFI specification does not define those phase names,
so this mapping is the project's own. Every rule is declared here with the
basis it rests on. Stops 1 and 2 have no events.

Exactly one rule must match an event. An event that matches none (or more
than one) gets no stop, and a test fails if that happens in a committed
recording.
"""
from collections.abc import Callable
from dataclasses import dataclass

from recorder import eventlog
from recorder.eventlog import Event

_OBSERVED_ORDER = ("log order observed on this firmware; the phase attribution comes from "
                   "EDK II documentation and is not yet confirmed in its source")


@dataclass(frozen=True)
class StopRule:
    """One declared rule: which events it claims, the stop, and why."""

    name: str
    stop: int
    basis: str
    matches: Callable[[Event], bool]


def _action_starts(event: Event, prefix: str) -> bool:
    text = eventlog.action_text(event)
    return text is not None and text.startswith(prefix)


def _is_firmware_measurement(event: Event) -> bool:
    return event.pcr == 0 and event.type_code in (
        eventlog.EV_S_CRTM_VERSION, eventlog.EV_EFI_PLATFORM_FIRMWARE_BLOB)


def _is_policy_measurement(event: Event) -> bool:
    return event.pcr == 7 and event.type_code in (
        eventlog.EV_EFI_VARIABLE_DRIVER_CONFIG, eventlog.EV_SEPARATOR)


def _is_configuration_measurement(event: Event) -> bool:
    return event.pcr == 1 and event.type_code in (
        eventlog.EV_PLATFORM_CONFIG_FLAGS, eventlog.EV_EFI_VARIABLE_BOOT)


def _is_boot_attempt(event: Event) -> bool:
    if event.type_code == eventlog.EV_SEPARATOR:
        return event.pcr <= 6
    return _action_starts(event, "Calling EFI Application")


def _is_authorisation(event: Event) -> bool:
    if event.type_code == eventlog.EV_EFI_VARIABLE_AUTHORITY:
        return event.pcr == 7
    if event.type_code == eventlog.EV_EFI_BOOT_SERVICES_APPLICATION:
        return event.pcr == 4
    return _action_starts(event, "Returning from EFI Application")


def _is_exit_boot_services(event: Event) -> bool:
    return event.pcr == 5 and _action_starts(event, "Exit Boot Services")


RULES: tuple[StopRule, ...] = (
    StopRule("pcr0-firmware", 3, _OBSERVED_ORDER, _is_firmware_measurement),
    StopRule("pcr7-policy", 4, _OBSERVED_ORDER, _is_policy_measurement),
    StopRule("pcr1-config", 5, _OBSERVED_ORDER, _is_configuration_measurement),
    StopRule("boot-attempt", 5, "observed position, directly before the load", _is_boot_attempt),
    StopRule("authorise", 6,
             "observed: present when the loader is accepted, absent or replaced when refused",
             _is_authorisation),
    StopRule("exit-boot-services", 7, "observed: only after the loader's exit call",
             _is_exit_boot_services),
)


def assign_stop(event: Event) -> tuple[int | None, str | None]:
    """The stop and rule name for one event, or (None, None) without a single match."""
    matching = [rule for rule in RULES if rule.matches(event)]
    if len(matching) != 1:
        return None, None
    return matching[0].stop, matching[0].name
