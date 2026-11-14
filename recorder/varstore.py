"""Read and edit the firmware's variable store file while nothing is running.

UEFI variables (boot order, Secure Boot keys and so on) survive a power cycle
because the firmware keeps them in flash. In the virtual machine that flash
is an ordinary file. This module reads the records in that file and makes
the few edits an experiment needs.

Layout, as written by the EDK II firmware and checked while parsing:

* a firmware volume header; its length is a 16-bit value at offset 48;
* a variable store header of 28 bytes;
* variable records, each starting with the marker 0x55AA, aligned to four
  bytes; unused space after the last record is filled with 0xFF.

Record header (60 bytes): marker (2), state (1), reserved (1), attributes
(4), monotonic count (8), timestamp (16), key index (4), name size (4), data
size (4), vendor identifier (16). The name (UTF-16) and the data follow.

Which edits have been proven against a boot: switching `SecureBootEnable`
off (recordings `e1` and `e4`) and appending a `dbx` record (recording `e5`);
in both the firmware read the edited store and acted on it. Reversing
`BootOrder` has not been booted: it stages an experiment whose run waits for
a committed prediction.
"""
import struct
import uuid
from dataclasses import dataclass

from recorder.errors import FormatError, StagingRefused

_RECORD_MARKER = 0x55AA
_RECORD_HEADER_SIZE = 60
_STORE_HEADER_SIZE = 28
STATE_LIVE = 0x3F

GLOBAL_VARIABLE_GUID = "8be4df61-93ca-11d2-aa0d-00e098032b8c"
IMAGE_SECURITY_DATABASE_GUID = "d719b2cb-3d3a-4596-a3bc-dad00e67656f"
CERT_SHA256_GUID = "c1c41626-504c-4092-aca9-41f936934328"
# Non-volatile, boot service, runtime, and time-based authenticated write.
SECURE_VARIABLE_ATTRIBUTES = 0x27


@dataclass(frozen=True)
class Variable:
    """One variable record in the store file."""

    name: str
    vendor_guid: str
    attributes: int
    state: int
    record_offset: int
    data_offset: int
    data_size: int

    @property
    def is_live(self) -> bool:
        """False for records the firmware has marked as deleted or replaced."""
        return self.state == STATE_LIVE


def _first_record_offset(store: bytes) -> int:
    if len(store) < 64:
        raise FormatError("too short to be a variable store file")
    (volume_header_length,) = struct.unpack_from("<H", store, 48)
    return volume_header_length + _STORE_HEADER_SIZE


def _walk(store: bytes) -> tuple[list[Variable], int]:
    """All records in file order, and the offset of the first unused byte."""
    offset = _first_record_offset(store)
    variables: list[Variable] = []
    while offset + _RECORD_HEADER_SIZE <= len(store):
        marker, state = struct.unpack_from("<HB", store, offset)
        if marker != _RECORD_MARKER:
            break
        (attributes,) = struct.unpack_from("<I", store, offset + 4)
        name_size, data_size = struct.unpack_from("<II", store, offset + 36)
        vendor = str(uuid.UUID(bytes_le=bytes(store[offset + 44:offset + 60])))
        name_start = offset + _RECORD_HEADER_SIZE
        data_start = name_start + name_size
        if data_start + data_size > len(store):
            raise FormatError(f"variable record at 0x{offset:x} runs past the end of the file")
        name = store[name_start:data_start].decode("utf-16le", errors="replace").rstrip("\0")
        variables.append(Variable(name, vendor, attributes, state, offset, data_start, data_size))
        offset = (data_start + data_size + 3) & ~3
    return variables, offset


def parse_store(store: bytes) -> list[Variable]:
    """Every variable record in the file, live or not, in file order."""
    return _walk(store)[0]


def live_variable(store: bytes, name: str) -> Variable | None:
    """The one live record with this name, or None. Two live records is an error."""
    found = [v for v in parse_store(store) if v.name == name and v.is_live]
    if len(found) > 1:
        raise FormatError(f"variable '{name}' has {len(found)} live records")
    return found[0] if found else None


def read_data(store: bytes, name: str) -> bytes | None:
    """The value of a live variable, or None when it does not exist."""
    variable = live_variable(store, name)
    if variable is None:
        return None
    return bytes(store[variable.data_offset:variable.data_offset + variable.data_size])


def replace_data(store: bytes, name: str, new_data: bytes) -> bytes:
    """A copy of the store with a variable's value overwritten in place.

    Only a value of the same size can be written this way; anything else
    would need the record chain to be rebuilt, and is refused.
    """
    variable = live_variable(store, name)
    if variable is None:
        raise StagingRefused(f"the variable store has no live variable '{name}'")
    if len(new_data) != variable.data_size:
        raise StagingRefused(
            f"variable '{name}' holds {variable.data_size} bytes; "
            f"an in-place edit cannot write {len(new_data)}")
    edited = bytearray(store)
    edited[variable.data_offset:variable.data_offset + variable.data_size] = new_data
    return bytes(edited)


def reverse_boot_order(store: bytes) -> bytes:
    """A copy of the store whose `BootOrder` lists its entries in reverse.

    `BootOrder` is a list of 16-bit option numbers. Refused when it has
    fewer than two entries, because reversing would then change nothing.
    """
    current = read_data(store, "BootOrder")
    if current is None or len(current) < 4 or len(current) % 2:
        raise StagingRefused("BootOrder is missing or lists fewer than two entries")
    entries = [current[i:i + 2] for i in range(0, len(current), 2)]
    return replace_data(store, "BootOrder", b"".join(reversed(entries)))


def switch_secure_boot_off(store: bytes) -> bytes:
    """A copy of the store with the firmware's own enable switch set to 0.

    `SecureBootEnable` is this firmware's private one-byte switch; the keys
    stay enrolled. Refused unless the switch is currently 1.
    """
    if read_data(store, "SecureBootEnable") != b"\x01":
        raise StagingRefused("SecureBootEnable is not a one-byte variable holding 1")
    return replace_data(store, "SecureBootEnable", b"\x00")


def sha256_signature_list(owner_guid: str, digest: bytes) -> bytes:
    """A signature list holding one SHA-256 hash, the form a revocation entry takes.

    Layout: list type (16), list size (4), header size (4), entry size (4),
    then the entry: owner identifier (16) and the 32-byte hash.
    """
    if len(digest) != 32:
        raise ValueError("a SHA-256 digest has 32 bytes")
    entry = uuid.UUID(owner_guid).bytes_le + digest
    header = uuid.UUID(CERT_SHA256_GUID).bytes_le + struct.pack("<III", 28 + len(entry), 0, len(entry))
    return header + entry


def append_variable(store: bytes, name: str, vendor_guid: str, attributes: int,
                    data: bytes, timestamp: bytes = bytes(16)) -> bytes:
    """A copy of the store with one new live record written after the last one.

    Refused when a live variable of that name exists, or when the space
    after the last record is not empty flash (all 0xFF) and large enough.
    """
    if live_variable(store, name) is not None:
        raise StagingRefused(f"variable '{name}' already exists in the store")
    if len(timestamp) != 16:
        raise ValueError("a variable timestamp has 16 bytes")
    _, free = _walk(store)
    encoded_name = (name + "\0").encode("utf-16le")
    record = struct.pack("<HBBIQ", _RECORD_MARKER, STATE_LIVE, 0, attributes, 0)
    record += timestamp + struct.pack("<III", 0, len(encoded_name), len(data))
    record += uuid.UUID(vendor_guid).bytes_le + encoded_name + data
    if set(store[free:free + len(record)]) != {0xFF} or free + len(record) > len(store):
        raise StagingRefused("no empty space after the last variable record")
    edited = bytearray(store)
    edited[free:free + len(record)] = record
    return bytes(edited)
