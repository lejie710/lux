"""Turn the raw artifacts of one boot into Python values. Parsers only.

Four artifacts come out of a boot:

* the serial console file the guest wrote,
* the software TPM's debug log, which contains every command the firmware
  sent to the TPM (including each "extend"),
* the TPM's answers to a final "read all registers" request,
* a file holding the guest's memory, somewhere inside which the firmware's
  event log lies.

Nothing in this module starts a process or opens a socket.

The TPM debug log format is undocumented. It is pinned by a real log kept as
a test fixture; the replay of the commands found in it must match the live
register values, which is what makes the reading trustworthy.
"""
import re
import struct
from dataclasses import dataclass

from recorder.banks import ALGORITHMS
from recorder.errors import FormatError
from recorder.eventlog import HEADER_SIGNATURE, SIGNATURE_OFFSET, EventLog, read_event_log

FINAL_MARKER = "LUX-FINAL-MARKER"
REFUSAL_PATTERN = re.compile(r"BdsDxe: failed to load [^\r\n]*")

TPM_CC_PCR_EXTEND = 0x00000182
TPM_CC_PCR_READ = 0x0000017E
_TPM_HEADER_SIZE = 10            # tag (2), total size (4), command or response code (4)
_TPM_TAG_NO_SESSIONS = 0x8001

_ESCAPE_SEQUENCE = re.compile(rb"\x1b\[[0-9;=?]*[A-Za-z]")
_MESSAGE_START = re.compile(r"\s*SWTPM_IO_(Read|Write): length (\d+)")
_HEX_LINE = re.compile(r"\s*([0-9A-Fa-f]{2}\s+)*[0-9A-Fa-f]{2}\s*")


# ---------------------------------------------------------------- console

def clean_console(raw: bytes) -> list[str]:
    """The serial output as text lines, without terminal control codes.

    The firmware sends cursor and colour codes and the odd zero byte. They
    carry no information about the boot, so they are removed, and empty
    lines are dropped. Line order is kept.
    """
    text = _ESCAPE_SEQUENCE.sub(b"", raw.replace(b"\0", b"")).replace(b"\r", b"")
    lines = text.decode("utf-8", errors="replace").split("\n")
    return [line for line in lines if line.strip()]


def classify_outcome(console: list[str]) -> str:
    """Decide from the console text how the boot ended.

    `accepted`: the loader printed its final marker, so the firmware started
    it and it finished its work. `refused`: the firmware printed that it
    failed to load the boot option. `timeout`: neither line appeared.
    """
    text = "\n".join(console)
    if FINAL_MARKER in text:
        return "accepted"
    if REFUSAL_PATTERN.search(text):
        return "refused"
    return "timeout"


# ---------------------------------------------------------------- TPM log

@dataclass(frozen=True)
class TpmMessage:
    """One message on the TPM's data channel as the debug log shows it."""

    direction: str        # "command" (firmware to TPM) or "response"
    data: bytes
    stated_length: int    # the length the log line announced


@dataclass(frozen=True)
class Extend:
    """One extend command found in the TPM log, with the TPM's answer."""

    pcr: int
    digests: dict[str, bytes]   # bank name -> digest
    response_code: int          # 0 means the TPM performed the extend


def parse_tpm_log(text: str) -> list[TpmMessage]:
    """Collect the command and response messages from the TPM debug log.

    The log prints ``SWTPM_IO_Read: length N`` for a command it received and
    ``SWTPM_IO_Write: length N`` for its answer, each followed by lines of
    hex bytes. Everything else in the log is skipped.
    """
    lines = text.split("\n")
    messages: list[TpmMessage] = []
    position = 0
    while position < len(lines):
        start = _MESSAGE_START.match(lines[position])
        position += 1
        if not start:
            continue
        stated_length = int(start.group(2))
        data = bytearray()
        while (len(data) < stated_length and position < len(lines)
               and _HEX_LINE.fullmatch(lines[position])):
            data += bytes.fromhex(lines[position].replace(" ", ""))
            position += 1
        direction = "command" if start.group(1) == "Read" else "response"
        messages.append(TpmMessage(direction, bytes(data), stated_length))
    return messages


def extends_from_messages(messages: list[TpmMessage]) -> list[Extend]:
    """Pick the extend commands out of the message list, in order.

    Raises `FormatError` when a message is shorter than the log announced,
    because a truncated log could silently lose an extend.
    """
    extends: list[Extend] = []
    for position, message in enumerate(messages):
        if len(message.data) != message.stated_length:
            raise FormatError(
                f"TPM log message {position} has {len(message.data)} bytes, "
                f"but the log announced {message.stated_length}")
        if message.direction != "command" or len(message.data) < _TPM_HEADER_SIZE:
            continue
        (command_code,) = struct.unpack_from(">I", message.data, 6)
        if command_code != TPM_CC_PCR_EXTEND:
            continue
        answer = messages[position + 1] if position + 1 < len(messages) else None
        extends.append(_decode_extend(message.data, answer))
    return extends


def _decode_extend(command: bytes, answer: TpmMessage | None) -> Extend:
    """Decode one extend command and the response code that followed it.

    Command layout after the 10-byte header: register handle (4), size of
    the authorisation area (4), that area, digest count (4), then for each
    digest the algorithm identifier (2) and the digest bytes.
    """
    pcr, authorisation_size = struct.unpack_from(">II", command, _TPM_HEADER_SIZE)
    cursor = _TPM_HEADER_SIZE + 8 + authorisation_size
    (digest_count,) = struct.unpack_from(">I", command, cursor)
    cursor += 4
    digests: dict[str, bytes] = {}
    for _ in range(digest_count):
        (algorithm_id,) = struct.unpack_from(">H", command, cursor)
        if algorithm_id not in ALGORITHMS:
            raise FormatError(f"extend command uses unknown algorithm 0x{algorithm_id:04x}")
        bank, size = ALGORITHMS[algorithm_id]
        digests[bank] = command[cursor + 2:cursor + 2 + size]
        cursor += 2 + size
    response_code = -1
    if answer is not None and answer.direction == "response" and len(answer.data) >= _TPM_HEADER_SIZE:
        (response_code,) = struct.unpack_from(">I", answer.data, 6)
    return Extend(pcr, digests, response_code)


# ---------------------------------------------------------------- live read

def build_pcr_read_command(algorithm_id: int, first_pcr: int) -> bytes:
    """A raw TPM command that reads eight registers of one bank.

    `first_pcr` must be 0, 8 or 16; the command selects registers
    `first_pcr` to `first_pcr + 7`. The TPM returns at most eight values per
    command, so reading a whole bank takes three commands.
    """
    if first_pcr not in (0, 8, 16):
        raise ValueError("first_pcr must be 0, 8 or 16")
    selection = bytearray(3)
    selection[first_pcr // 8] = 0xFF
    body = struct.pack(">IHB", 1, algorithm_id, 3) + bytes(selection)
    header = struct.pack(">HII", _TPM_TAG_NO_SESSIONS, _TPM_HEADER_SIZE + len(body), TPM_CC_PCR_READ)
    return header + body


def parse_pcr_read_response(response: bytes) -> dict[int, bytes]:
    """Decode the answer to a register read: register index -> value.

    Response layout after the 10-byte header: update counter (4), selection
    count (4), per selection the algorithm (2), a bitmap size (1) and the
    bitmap of registers returned; then the value count (4) and each value
    prefixed by its size (2). Raises `FormatError` on a failure code.
    """
    if len(response) < _TPM_HEADER_SIZE:
        raise FormatError("TPM response shorter than its header")
    (response_code,) = struct.unpack_from(">I", response, 6)
    if response_code != 0:
        raise FormatError(f"the TPM refused the register read, code 0x{response_code:x}")
    cursor = _TPM_HEADER_SIZE + 4
    (selection_count,) = struct.unpack_from(">I", response, cursor)
    cursor += 4
    indexes: list[int] = []
    for _ in range(selection_count):
        _, bitmap_size = struct.unpack_from(">HB", response, cursor)
        bitmap = response[cursor + 3:cursor + 3 + bitmap_size]
        cursor += 3 + bitmap_size
        indexes += [bit for bit in range(bitmap_size * 8) if bitmap[bit // 8] >> (bit % 8) & 1]
    (value_count,) = struct.unpack_from(">I", response, cursor)
    cursor += 4
    if value_count != len(indexes):
        raise FormatError("the register read returned a different number of values than selected")
    values: dict[int, bytes] = {}
    for index in indexes:
        (size,) = struct.unpack_from(">H", response, cursor)
        values[index] = response[cursor + 2:cursor + 2 + size]
        cursor += 2 + size
    return values


# ---------------------------------------------------------------- event log in memory

@dataclass(frozen=True)
class LogCandidate:
    """A place in guest memory that parses as an event log."""

    offset: int
    log: EventLog


def find_event_logs(memory: bytes) -> list[LogCandidate]:
    """Find every place in a memory image that parses as an event log.

    The header text ``Spec ID Event03`` also occurs in places that are not a
    log (for example inside the firmware's own code). A hit counts as a
    candidate only when a valid header is there and at least one event
    follows it. The caller must then insist on exactly one candidate; the
    log is chosen by its structure and never because its replay happens to
    match the registers.
    """
    candidates: list[LogCandidate] = []
    position = memory.find(HEADER_SIGNATURE)
    while position >= 0:
        start = position - SIGNATURE_OFFSET
        try:
            log = read_event_log(memory, start)
        except FormatError:
            log = None
        if log is not None and log.events:
            candidates.append(LogCandidate(start, log))
        position = memory.find(HEADER_SIGNATURE, position + 1)
    return candidates
