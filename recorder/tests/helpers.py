"""Shared test helpers: fixture access, small builders, and fakes.

The fixtures in `fixtures/` are real data from two boots made with an
earlier, throwaway key set: one accepted boot ("normal") and one refused
boot ("e2"). Per boot: the raw event log, the registers read from the TPM,
the raw console file, the TPM command traffic from the software TPM's debug
log, and the event type names exactly as tpm2-tools printed them.
"""
import hashlib
import json
import shutil
import struct
from pathlib import Path

from recorder import bootentries, keys, varstore
from recorder.banks import ALGORITHMS, DIGEST_SIZES, PcrBanks, banks_from_hex
from recorder.capture import Extend
from recorder.eventlog import EV_NO_ACTION, HEADER_SIGNATURE, Event

FIXTURES = Path(__file__).parent / "fixtures"
REPOSITORY = Path(__file__).resolve().parent.parent.parent
TESTKEYS = REPOSITORY / "recorder" / "testkeys"

# Known digests of the loader and of its one-byte-changed copy, computed
# independently of this package with efitools (hash-to-efi-sig-list).
LOADER_AUTHENTICODE = "00c5018d3157edb92f96a08ba685a1c5913c5dd5fa2228b021dd9d4970eee50f"
CHANGED_LOADER_AUTHENTICODE = "cef0a97471078a2922c8a96d3ce30512b368882b041d2d148bb9c26704891432"


def fixture_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


def fixture_text(name: str) -> str:
    return (FIXTURES / name).read_text(encoding="utf-8")


def live_banks(tag: str) -> PcrBanks:
    """The registers read from the TPM in the fixture boot `tag`."""
    return banks_from_hex(json.loads(fixture_text(f"{tag}-live-pcrs.json")))


def all_digests(data: bytes) -> dict[str, bytes]:
    """The digest of `data` in each of the four banks."""
    return {bank: hashlib.new(bank, data).digest() for bank in DIGEST_SIZES}


def make_event(pcr: int, type_code: int, data: bytes, index: int = 1,
               digests: dict[str, bytes] | None = None) -> Event:
    """An event whose digests are the hashes of its data, unless given."""
    return Event(index, pcr, type_code, digests or all_digests(data), data)


def encode_log(events: list[Event]) -> bytes:
    """Encode events as a crypto-agile event log, header included."""
    spec = HEADER_SIGNATURE + struct.pack("<IBBBBI", 0, 0, 2, 0, 2, len(ALGORITHMS))
    for algorithm_id, (_, size) in ALGORITHMS.items():
        spec += struct.pack("<HH", algorithm_id, size)
    spec += b"\x00"
    out = struct.pack("<II", 0, EV_NO_ACTION) + bytes(20) + struct.pack("<I", len(spec)) + spec
    ids = {name: algorithm_id for algorithm_id, (name, _) in ALGORITHMS.items()}
    for event in events:
        out += struct.pack("<III", event.pcr, event.type_code, len(event.digests))
        for bank, digest in event.digests.items():
            out += struct.pack("<H", ids[bank]) + digest
        out += struct.pack("<I", len(event.data)) + event.data
    return out


def _hex_lines(data: bytes) -> list[str]:
    return [" " + " ".join(f"{b:02X}" for b in data[i:i + 16]) + " " for i in range(0, len(data), 16)]


def encode_tpm_log(extends: list[Extend]) -> str:
    """A TPM debug log holding one extend command and its answer per item."""
    ids = {name: algorithm_id for algorithm_id, (name, _) in ALGORITHMS.items()}
    lines: list[str] = []
    for item in extends:
        body = struct.pack(">II", item.pcr, 9) + bytes(9) + struct.pack(">I", len(item.digests))
        for bank, digest in item.digests.items():
            body += struct.pack(">H", ids[bank]) + digest
        command = struct.pack(">HII", 0x8002, 10 + len(body), 0x182) + body
        answer = struct.pack(">HII", 0x8001, 10, item.response_code)
        lines += [f" SWTPM_IO_Read: length {len(command)}", *_hex_lines(command)]
        lines += [f" SWTPM_IO_Write: length {len(answer)}", *_hex_lines(answer)]
    return "\n".join(lines) + "\n"


def extends_for(events: list[Event]) -> list[Extend]:
    """The extend commands a TPM would have received for these events."""
    return [Extend(e.pcr, dict(e.digests), 0) for e in events if e.is_extended]


def make_store(variables: list[tuple[str, bytes]], size: int = 8192) -> bytes:
    """A small variable store file holding the given (name, data) variables."""
    store = bytearray(b"\xff" * size)
    store[0:100] = bytes(100)
    struct.pack_into("<H", store, 48, 72)        # firmware volume header length
    result = bytes(store)
    for name, data in variables:
        result = varstore.append_variable(result, name, varstore.GLOBAL_VARIABLE_GUID, 0x07, data)
    return result


def template_store() -> bytes:
    """A store shaped like the real template: keys enrolled, Secure Boot on, two boot entries."""
    return make_store([
        ("PK", b"pk"), ("KEK", b"kek"), ("db", b"db"),
        ("SecureBootEnable", b"\x01"), ("BootOrder", b"\x00\x00\x01\x00"),
    ])


def two_entry_store(order: tuple[int, ...] = bootentries.ORDER_A_FIRST) -> bytes:
    """A store shaped like the two-entry template: keys, the firmware's own two options, A and B."""
    variables = [("PK", b"pk"), ("KEK", b"kek"), ("db", b"db"), ("SecureBootEnable", b"\x01"),
                 ("Boot0000", b"the firmware's setup application"), ("Boot0001", b"the disk")]
    variables += [(entry.variable, varstore.load_option(entry.description, entry.firmware_path))
                  for entry in bootentries.ENTRIES]
    variables.append(("BootOrder", varstore.boot_order_data(order)))
    return make_store(variables)


FIRMWARE_BYTES = b"firmware image"


def test_pins(template: bytes, firmware: bytes = FIRMWARE_BYTES) -> keys.Pins:
    """Manifest pins for a test key directory: the given template and firmware bytes."""
    return keys.Pins(LOADER_AUTHENTICODE, hashlib.sha256(template).hexdigest(), "firmware.fd",
                     hashlib.sha256(firmware).hexdigest(), {"openssl": "test"})


def copy_testkeys(target: Path, template: bytes) -> Path:
    """A copy of the committed test keys whose manifest pins the given template."""
    shutil.copytree(TESTKEYS, target)
    keys.write_manifest(target, test_pins(template))
    return target


class FakeGit:
    """Answers the recorder's git questions from a small table.

    By default it describes a file that is committed and unchanged: the
    committed content it hands out is whatever the file on disk holds.
    `blob` overrides that content, which is how a file edited behind git's
    back is played.
    """

    def __init__(self, tracked: bool = True, status: str = "", commit: str = "abc123\n",
                 code: int = 0, ancestor: bool = True, blob: bytes | None = None) -> None:
        self.tracked, self.status, self.commit, self.code = tracked, status, commit, code
        self.ancestor, self.blob = ancestor, blob
        self.asked: list[str] = []

    def __call__(self, arguments: list[str], directory: Path) -> tuple[int, bytes]:
        self.asked.append(arguments[0])
        if self.code:
            return self.code, b""
        if arguments[0] == "ls-files":
            return (0 if self.tracked else 1), b""
        if arguments[0] == "status":
            return 0, self.status.encode()
        if arguments[0] == "log":
            return 0, self.commit.encode()
        if arguments[0] == "merge-base":
            return (0 if self.ancestor else 1), b""
        if arguments[0] == "rev-parse":
            return 0, b"predictions/\n"
        if arguments[0] == "cat-file":
            name = arguments[-1].rsplit("/", 1)[-1]
            return 0, self.blob if self.blob is not None else (directory / name).read_bytes()
        return 1, b""


class FakeClock:
    """A clock that only moves when something sleeps."""

    def __init__(self) -> None:
        self.time = 0.0

    def now(self) -> float:
        return self.time

    def sleep(self, seconds: float) -> None:
        self.time += seconds


class FakeMachine:
    """A scripted virtual machine. Nothing is started; every call is recorded.

    `console_at` maps a time to the console bytes present from that time on.
    `activity_until` is the time until which the TPM log keeps growing.
    `exits_at` makes the guest end by itself at that time.
    """

    qemu_command_line = "qemu-system-x86_64 -serial file:RUN/serial.log"
    swtpm_command_line = "swtpm socket --tpmstate dir=RUN/tpm"

    def __init__(self, clock: FakeClock, run_directory: Path, console_at: dict[float, bytes],
                 tpm_log: str = "", memory: bytes = b"", live: PcrBanks | None = None,
                 activity_until: float = 0.0, exits_at: float | None = None,
                 fail_on: str | None = None, error_text: str = "") -> None:
        self.clock, self.run_directory = clock, run_directory
        self.console_at, self.tpm_log, self.memory, self.live = console_at, tpm_log, memory, live
        self.activity_until, self.exits_at, self.fail_on = activity_until, exits_at, fail_on
        self.error_text = error_text
        self.calls: list[str] = []
        self.killed = False
        self.paused_at: float | None = None
        self.qemu_command_line = self.qemu_command_line.replace("RUN", str(run_directory))
        self.swtpm_command_line = self.swtpm_command_line.replace("RUN", str(run_directory))

    def _call(self, name: str) -> None:
        self.calls.append(name)
        if self.fail_on == name:
            raise RuntimeError(f"scripted failure in {name}")

    def start(self) -> None:
        self._call("start")

    def vm_running(self) -> bool:
        if self.killed:
            return False
        return self.exits_at is None or self.clock.now() < self.exits_at

    def console_bytes(self) -> bytes:
        present = [text for moment, text in sorted(self.console_at.items()) if moment <= self.clock.now()]
        return present[-1] if present else b""

    def activity(self) -> tuple[int, int]:
        return len(self.console_bytes()), int(min(self.clock.now(), self.activity_until) * 100)

    def pause_and_save_memory(self) -> Path:
        self.paused_at = self.clock.now()
        self.run_directory.mkdir(parents=True, exist_ok=True)
        path = self.run_directory / "mem.bin"
        path.write_bytes(self.memory or b"\x00")     # written even when the step then fails
        self._call("pause_and_save_memory")
        return path

    def discard_memory(self) -> None:
        (self.run_directory / "mem.bin").unlink(missing_ok=True)

    def failure_text(self) -> str:
        return self.error_text

    def kill_vm(self) -> None:
        self._call("kill_vm")
        self.killed = True

    def read_pcrs(self) -> PcrBanks:
        self._call("read_pcrs")
        assert self.live is not None
        return self.live

    def tpm_log_text(self) -> str:
        return self.tpm_log

    def stop(self) -> None:
        self.calls.append("stop")
        self.killed = True
