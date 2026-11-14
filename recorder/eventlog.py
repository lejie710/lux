"""Parse the firmware's event log and describe each event in plain words.

While it boots, the firmware keeps a list of everything it measured into the
TPM: one entry ("event") per measurement, with the register it extended, a
type, one digest per hash bank, and a little data saying what was measured.
The recorder cuts that list out of saved guest memory; this module turns the
bytes into Python values.

Layout parsed here (the "crypto agile" format):

* one header event in the older fixed layout, whose data starts with the
  text ``Spec ID Event03`` and lists the hash algorithms and digest sizes;
* then events of the form: register index, type, digest count, the digests
  (each prefixed by its algorithm identifier), data size, data.

Type names are the ones the tpm2-tools program `tpm2_eventlog` prints. They
are tool names, not citations of a specification.
"""
import hashlib
import struct
from dataclasses import dataclass

from recorder.banks import ALGORITHMS
from recorder.errors import FormatError

HEADER_SIGNATURE = b"Spec ID Event03\x00"
# The signature sits this many bytes after the start of the log:
# register index (4) + type (4) + SHA-1 digest (20) + data size (4).
SIGNATURE_OFFSET = 32

EV_NO_ACTION = 0x00000003
EV_SEPARATOR = 0x00000004
EV_S_CRTM_VERSION = 0x00000008
EV_PLATFORM_CONFIG_FLAGS = 0x0000000A
EV_EFI_VARIABLE_DRIVER_CONFIG = 0x80000001
EV_EFI_VARIABLE_BOOT = 0x80000002
EV_EFI_BOOT_SERVICES_APPLICATION = 0x80000003
EV_EFI_ACTION = 0x80000007
EV_EFI_PLATFORM_FIRMWARE_BLOB = 0x80000008
EV_EFI_VARIABLE_AUTHORITY = 0x800000E0

TYPE_NAMES: dict[int, str] = {
    EV_NO_ACTION: "EV_NO_ACTION",
    EV_SEPARATOR: "EV_SEPARATOR",
    EV_S_CRTM_VERSION: "EV_S_CRTM_VERSION",
    EV_PLATFORM_CONFIG_FLAGS: "EV_PLATFORM_CONFIG_FLAGS",
    EV_EFI_VARIABLE_DRIVER_CONFIG: "EV_EFI_VARIABLE_DRIVER_CONFIG",
    EV_EFI_VARIABLE_BOOT: "EV_EFI_VARIABLE_BOOT",
    EV_EFI_BOOT_SERVICES_APPLICATION: "EV_EFI_BOOT_SERVICES_APPLICATION",
    EV_EFI_ACTION: "EV_EFI_ACTION",
    EV_EFI_PLATFORM_FIRMWARE_BLOB: "EV_EFI_PLATFORM_FIRMWARE_BLOB",
    EV_EFI_VARIABLE_AUTHORITY: "EV_EFI_VARIABLE_AUTHORITY",
}

_VARIABLE_TYPES = (EV_EFI_VARIABLE_DRIVER_CONFIG, EV_EFI_VARIABLE_BOOT, EV_EFI_VARIABLE_AUTHORITY)
# Event types whose digest is the hash of the whole event data (observed on
# this firmware and recomputed for every recording).
_DIGEST_OF_WHOLE_DATA = (
    EV_EFI_VARIABLE_DRIVER_CONFIG, EV_EFI_VARIABLE_AUTHORITY,
    EV_SEPARATOR, EV_EFI_ACTION, EV_S_CRTM_VERSION,
)
_MAX_DIGESTS_PER_EVENT = 8
_MAX_EVENT_DATA = 0x100000
_HIGHEST_PCR = 23


@dataclass(frozen=True)
class Event:
    """One measurement the firmware logged."""

    index: int                 # position in the log, starting at 1
    pcr: int                   # the register that was extended
    type_code: int
    digests: dict[str, bytes]  # bank name -> digest
    data: bytes                # what the firmware wrote next to the digests

    @property
    def is_extended(self) -> bool:
        """False for `EV_NO_ACTION`: logged for information, never extended."""
        return self.type_code != EV_NO_ACTION


@dataclass(frozen=True)
class EventLog:
    """A parsed event log."""

    digest_sizes: dict[str, int]   # bank name -> digest size, from the header
    events: tuple[Event, ...]      # the header event is not included
    byte_length: int               # how many bytes the log occupies


def read_event_log(buffer: bytes, start: int = 0) -> EventLog:
    """Parse the event log that begins at `buffer[start]`.

    Reading stops at the first position that cannot be an event, which is how
    the end is found inside a memory image (the log has no length field).
    Raises `FormatError` when the header is not a valid log header.
    """
    digest_sizes, position = _read_header(buffer, start)
    sizes_by_id = {_algorithm_id(name): size for name, size in digest_sizes.items()}
    events: list[Event] = []
    while True:
        parsed = _read_event(buffer, position, sizes_by_id, len(events) + 1)
        if parsed is None:
            break
        event, position = parsed
        events.append(event)
    return EventLog(digest_sizes, tuple(events), position - start)


def parse_event_log(data: bytes) -> EventLog:
    """Parse a byte string that must be exactly one event log, start to end."""
    log = read_event_log(data, 0)
    if log.byte_length != len(data):
        raise FormatError(
            f"event log ends after {log.byte_length} bytes, but {len(data)} bytes were given")
    return log


def _bank_name(algorithm_id: int) -> str:
    """Bank name for a TPM algorithm identifier; unknown ones keep their number."""
    if algorithm_id in ALGORITHMS:
        return ALGORITHMS[algorithm_id][0]
    return f"alg-0x{algorithm_id:04x}"


def _algorithm_id(bank: str) -> int:
    """The reverse of `_bank_name`."""
    for algorithm_id, (name, _) in ALGORITHMS.items():
        if name == bank:
            return algorithm_id
    return int(bank.removeprefix("alg-"), 16)


def _read_header(buffer: bytes, start: int) -> tuple[dict[str, int], int]:
    """Check the header event; return the digest sizes and where events begin."""
    if start < 0 or start + SIGNATURE_OFFSET + 29 > len(buffer):
        raise FormatError("too short to hold an event log header")
    pcr, type_code = struct.unpack_from("<II", buffer, start)
    (data_size,) = struct.unpack_from("<I", buffer, start + 28)
    data_start = start + SIGNATURE_OFFSET
    if buffer[data_start:data_start + 16] != HEADER_SIGNATURE:
        raise FormatError("the header signature 'Spec ID Event03' is missing")
    if pcr != 0 or type_code != EV_NO_ACTION:
        raise FormatError("the header event is not an EV_NO_ACTION event for register 0")
    (algorithm_count,) = struct.unpack_from("<I", buffer, data_start + 24)
    if not 1 <= algorithm_count <= _MAX_DIGESTS_PER_EVENT:
        raise FormatError(f"implausible number of hash algorithms: {algorithm_count}")
    if data_size < 28 + 4 * algorithm_count + 1 or data_start + data_size > len(buffer):
        raise FormatError("the header event's size does not fit its content")
    sizes: dict[str, int] = {}
    for index in range(algorithm_count):
        algorithm_id, size = struct.unpack_from("<HH", buffer, data_start + 28 + 4 * index)
        sizes[_bank_name(algorithm_id)] = size
    return sizes, data_start + data_size


def _read_event(buffer: bytes, position: int, sizes_by_id: dict[int, int],
                index: int) -> tuple[Event, int] | None:
    """Read one event at `position`; None when the bytes there are not an event."""
    if position + 12 > len(buffer):
        return None
    pcr, type_code, digest_count = struct.unpack_from("<III", buffer, position)
    if pcr > _HIGHEST_PCR or not 1 <= digest_count <= _MAX_DIGESTS_PER_EVENT:
        return None
    cursor = position + 12
    digests: dict[str, bytes] = {}
    for _ in range(digest_count):
        if cursor + 2 > len(buffer):
            return None
        (algorithm_id,) = struct.unpack_from("<H", buffer, cursor)
        size = sizes_by_id.get(algorithm_id)
        if size is None or cursor + 2 + size > len(buffer):
            return None
        digests[_bank_name(algorithm_id)] = bytes(buffer[cursor + 2:cursor + 2 + size])
        cursor += 2 + size
    if cursor + 4 > len(buffer):
        return None
    (data_size,) = struct.unpack_from("<I", buffer, cursor)
    if data_size > _MAX_EVENT_DATA or cursor + 4 + data_size > len(buffer):
        return None
    data = bytes(buffer[cursor + 4:cursor + 4 + data_size])
    return Event(index, pcr, type_code, digests, data), cursor + 4 + data_size


def type_name(type_code: int) -> str:
    """The event type's name as tpm2-tools prints it, or a marked number."""
    return TYPE_NAMES.get(type_code, f"UNKNOWN_0x{type_code:08x}")


def variable_parts(event: Event) -> tuple[str, bytes] | None:
    """Name and value of the UEFI variable a variable event describes.

    Event data layout: vendor identifier (16 bytes), name length in
    characters (8), value length in bytes (8), the name in UTF-16, the value.
    Returns None when the event is not a variable event or is too short.
    """
    if event.type_code not in _VARIABLE_TYPES or len(event.data) < 32:
        return None
    name_length, value_length = struct.unpack_from("<QQ", event.data, 16)
    name_end = 32 + 2 * name_length
    if name_end + value_length > len(event.data):
        return None
    name = event.data[32:name_end].decode("utf-16le", errors="replace")
    return name, event.data[name_end:name_end + value_length]


def action_text(event: Event) -> str | None:
    """The text of an action event, or None for any other type."""
    if event.type_code != EV_EFI_ACTION:
        return None
    return event.data.decode("ascii", errors="replace")


def summarise(event: Event) -> str:
    """One plain line saying what the event measured, taken from its own data."""
    variable = variable_parts(event)
    if variable is not None:
        return f"variable {variable[0]}, {len(variable[1])} data bytes"
    code, data = event.type_code, event.data
    if code == EV_EFI_ACTION:
        return f"action: {action_text(event)}"
    if code == EV_S_CRTM_VERSION:
        return "firmware version string " + data.decode("utf-16le", errors="replace").rstrip("\0")
    if code == EV_EFI_PLATFORM_FIRMWARE_BLOB and len(data) >= 16:
        base, length = struct.unpack_from("<QQ", data, 0)
        return f"firmware blob at 0x{base:x}, length 0x{length:x}"
    if code == EV_EFI_BOOT_SERVICES_APPLICATION and len(data) >= 16:
        base, length = struct.unpack_from("<QQ", data, 0)
        return f"image loaded at 0x{base:x}, length 0x{length:x}"
    if code == EV_SEPARATOR:
        return "separator, data " + data.hex()
    if code == EV_PLATFORM_CONFIG_FLAGS:
        return "platform configuration: " + data.decode("ascii", errors="replace").rstrip("\0")
    return f"{len(data)} data bytes"


def content_digests_match(event: Event) -> bool | None:
    """Recompute an event's digests from its own data, where that is possible.

    For some event types the digest is defined by the data written next to it.
    Recomputing it proves the log describes what was actually extended:

    * policy variables, the authority record, separators, action texts and
      the version string: digest = hash of the whole event data;
    * boot variables: digest = hash of the variable's value only.

    Returns None for types whose digest covers something outside the log
    (for example a firmware blob or a loaded image).
    """
    if event.type_code in _DIGEST_OF_WHOLE_DATA:
        measured = event.data
    elif event.type_code == EV_EFI_VARIABLE_BOOT:
        variable = variable_parts(event)
        if variable is None:
            return False
        measured = variable[1]
    else:
        return None
    return all(
        hashlib.new(bank, measured).digest() == digest
        for bank, digest in event.digests.items()
        if not bank.startswith("alg-")
    )
