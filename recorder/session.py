"""Boot the virtual machine once and end the boot the same way every time.

Two programs run for one boot: `swtpm` (the software TPM) and QEMU (the
virtual machine). The firmware inside QEMU talks to swtpm through a socket.

**Why every run ends by pause, capture, kill.** If the guest powers off,
QEMU tells swtpm to shut down and the register values are gone before they
can be read. So the guest loader never powers off; it idles. The recorder
then pauses the guest, saves its memory to a file, and kills QEMU while it
is paused. QEMU never gets to say goodbye to swtpm, so swtpm is still alive
and can be asked for its registers. A refused boot ends by the same path.

The waiting logic (`run_boot`) only talks to a `Machine` and a `Clock`, so
tests drive it with fakes and never boot anything. `QemuMachine` is the real
thing and needs Linux.
"""
import json
import os
import signal
import socket
import struct
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from recorder import capture
from recorder.banks import ALGORITHMS, PCR_COUNT, PcrBanks
from recorder.errors import ToolMissing

MEMORY_MIB = 512
QEMU_TIMEOUT_SECONDS = 300
TRIGGER_MARKER = "final-marker"
TRIGGER_REFUSAL = "refusal-line"
TRIGGER_NONE = "none"
ENDING_PAUSED = "paused-then-killed"
ENDING_GUEST = "guest-ended"

_SWTPM_CMD_SET_DATAFD = 16


@dataclass(frozen=True)
class Limits:
    """How long the recorder waits. All values are seconds."""

    trigger: float = 270.0        # give up waiting for a marker or a refusal
    quiet: float = 3.0            # both logs must stand still this long
    settle_max: float = 30.0      # stop waiting for quiet after this long
    poll: float = 0.25

    @property
    def settle_rule(self) -> str:
        """The end condition in words, stored in every recording."""
        return (f"no growth of the console file or the TPM log for {self.quiet:.1f} s "
                f"(at most {self.settle_max:.0f} s)")


class Clock(Protocol):
    """Time source, so tests can run without waiting."""

    def now(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


class SystemClock:
    """The real clock."""

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


class Machine(Protocol):
    """Everything `run_boot` needs from a virtual machine and its TPM."""

    qemu_command_line: str
    swtpm_command_line: str

    def start(self) -> None: ...
    def vm_running(self) -> bool: ...
    def console_bytes(self) -> bytes: ...
    def activity(self) -> tuple[int, int]: ...
    def pause_and_save_memory(self) -> Path: ...
    def kill_vm(self) -> None: ...
    def read_pcrs(self) -> PcrBanks: ...
    def tpm_log_text(self) -> str: ...
    def stop(self) -> None: ...


@dataclass(frozen=True)
class Observation:
    """What one boot left behind, before any parsing."""

    trigger: str
    ending: str
    seconds_to_trigger: float
    seconds_to_pause: float
    console_raw: bytes
    tpm_log: str
    memory_file: Path | None        # None when the guest ended by itself
    live_pcrs: PcrBanks | None      # None when the guest ended by itself


def find_trigger(console_raw: bytes) -> str:
    """Which end-of-boot line the console shows so far, if any."""
    text = console_raw.decode("utf-8", errors="replace")
    if capture.FINAL_MARKER in text:
        return TRIGGER_MARKER
    if capture.REFUSAL_PATTERN.search(text):
        return TRIGGER_REFUSAL
    return TRIGGER_NONE


def _wait_for_trigger(machine: Machine, clock: Clock, limits: Limits, started: float) -> str:
    """Poll the console until a trigger line appears, the guest ends, or time is up."""
    while clock.now() - started < limits.trigger and machine.vm_running():
        trigger = find_trigger(machine.console_bytes())
        if trigger != TRIGGER_NONE:
            return trigger
        clock.sleep(limits.poll)
    return find_trigger(machine.console_bytes())


def _wait_until_quiet(machine: Machine, clock: Clock, limits: Limits) -> None:
    """Wait until the console file and the TPM log have both stopped growing.

    The firmware keeps extending registers for a moment after the trigger
    line (a refused boot tries the next boot option, for example). Pausing
    too early would cut those extends off and make the run look shorter.
    """
    settle_started = clock.now()
    last_activity = machine.activity()
    quiet_since = clock.now()
    while machine.vm_running() and clock.now() - settle_started < limits.settle_max:
        clock.sleep(limits.poll)
        activity = machine.activity()
        if activity != last_activity:
            last_activity, quiet_since = activity, clock.now()
        elif clock.now() - quiet_since >= limits.quiet:
            return


def run_boot(machine: Machine, clock: Clock, limits: Limits) -> Observation:
    """Boot once, wait for the end of the boot, capture, and always clean up."""
    started = clock.now()
    memory_file: Path | None = None
    live_pcrs: PcrBanks | None = None
    ending = ENDING_GUEST
    try:
        machine.start()
        trigger = _wait_for_trigger(machine, clock, limits, started)
        seconds_to_trigger = clock.now() - started
        _wait_until_quiet(machine, clock, limits)
        seconds_to_pause = clock.now() - started
        if machine.vm_running():
            memory_file = machine.pause_and_save_memory()
            machine.kill_vm()
            live_pcrs = machine.read_pcrs()
            ending = ENDING_PAUSED
    finally:
        machine.stop()
    return Observation(trigger, ending, seconds_to_trigger, seconds_to_pause,
                       machine.console_bytes(), machine.tpm_log_text(), memory_file, live_pcrs)


# ---------------------------------------------------------------- the real machine

def qemu_arguments(run_directory: Path, firmware: Path) -> list[str]:
    """The full QEMU command line. Only the run directory differs between runs.

    Every choice that could change a measurement is spelled out: machine
    type, CPU model, software emulation, memory size and a fixed clock. The
    firmware file is read-only flash unit 0; the variable store is unit 1.
    """
    run = str(run_directory)
    return [
        "timeout", "-s", "KILL", str(QEMU_TIMEOUT_SECONDS),
        "qemu-system-x86_64",
        "-machine", "pc-q35-8.2,smm=on,accel=tcg",
        "-cpu", "qemu64",
        "-smp", "1",
        "-m", str(MEMORY_MIB),
        "-rtc", "base=2026-01-01T00:00:00,clock=vm",
        "-display", "none", "-vga", "std", "-net", "none", "-no-reboot", "-monitor", "none",
        "-global", "driver=cfi.pflash01,property=secure,value=on",
        "-drive", f"if=pflash,format=raw,unit=0,readonly=on,file={firmware}",
        "-drive", f"if=pflash,format=raw,unit=1,file={run}/vars.fd",
        "-chardev", f"socket,id=chrtpm,path={run}/swtpm.sock",
        "-tpmdev", "emulator,id=tpm0,chardev=chrtpm",
        "-device", "tpm-tis,tpmdev=tpm0",
        "-drive", f"format=raw,file=fat:rw:{run}/esp",
        "-qmp", f"unix:{run}/qmp.sock,server=on,wait=off",
        "-pidfile", f"{run}/qemu.pid",
        "-serial", f"file:{run}/serial.log",
    ]


def swtpm_arguments(run_directory: Path) -> list[str]:
    """The swtpm command line: a fresh TPM 2.0 with its debug log switched on."""
    run = str(run_directory)
    return [
        "swtpm", "socket", "--tpm2",
        "--tpmstate", f"dir={run}/tpm",
        "--ctrl", f"type=unixio,path={run}/swtpm.sock",
        "--log", f"file={run}/swtpm.log,level=20",
    ]


class QemuMachine:
    """One swtpm process and one QEMU process in a run directory."""

    def __init__(self, run_directory: Path, firmware: Path) -> None:
        self._run = run_directory
        self._qemu_argv = qemu_arguments(run_directory, firmware)
        self._swtpm_argv = swtpm_arguments(run_directory)
        self.qemu_command_line = " ".join(self._qemu_argv)
        self.swtpm_command_line = " ".join(self._swtpm_argv)
        self._swtpm: subprocess.Popen | None = None
        self._qemu: subprocess.Popen | None = None

    # -- start and status

    def start(self) -> None:
        """Start swtpm, wait for its socket, then start QEMU."""
        try:
            self._swtpm = subprocess.Popen(self._swtpm_argv, stdin=subprocess.DEVNULL)
            self._wait_for_file(self._run / "swtpm.sock", "the software TPM's socket")
            with open(self._run / "qemu.err", "wb") as errors:
                self._qemu = subprocess.Popen(self._qemu_argv, stdin=subprocess.DEVNULL,
                                              stdout=subprocess.DEVNULL, stderr=errors)
        except OSError as error:
            raise ToolMissing(f"cannot start the virtual machine: {error}") from error

    def _wait_for_file(self, path: Path, what: str) -> None:
        for _ in range(100):
            if path.exists():
                return
            time.sleep(0.1)
        raise ToolMissing(f"{what} did not appear")

    def vm_running(self) -> bool:
        return self._qemu is not None and self._qemu.poll() is None

    def console_bytes(self) -> bytes:
        try:
            return (self._run / "serial.log").read_bytes()
        except FileNotFoundError:
            return b""

    def activity(self) -> tuple[int, int]:
        """Sizes of the console file and the TPM log; growth means the boot is still busy."""
        log = self._run / "swtpm.log"
        return len(self.console_bytes()), log.stat().st_size if log.exists() else 0

    def tpm_log_text(self) -> str:
        try:
            return (self._run / "swtpm.log").read_text(errors="replace")
        except FileNotFoundError:
            return ""

    # -- the one ending

    def pause_and_save_memory(self) -> Path:
        """Pause the guest over QMP and write its whole memory to a file."""
        memory_file = self._run / "mem.bin"
        with self._open_qmp() as channel:
            self._qmp(channel, "stop")
            status = self._qmp(channel, "query-status")
            if status.get("return", {}).get("status") != "paused":
                raise ToolMissing(f"the guest did not pause: {status}")
            saved = self._qmp(channel, "pmemsave", val=0, size=MEMORY_MIB * 1024 * 1024,
                              filename=str(memory_file))
            if "error" in saved or not memory_file.exists():
                raise ToolMissing(f"guest memory was not saved: {saved}")
        return memory_file

    def _open_qmp(self) -> socket.SocketIO:
        """Connect to QEMU's control socket and finish its greeting."""
        connection = socket.socket(socket.AF_UNIX)
        connection.settimeout(120)
        for attempt in range(100):
            try:
                connection.connect(str(self._run / "qmp.sock"))
                break
            except OSError:
                if attempt == 99:
                    raise ToolMissing("QEMU's control socket never accepted a connection") from None
                time.sleep(0.1)
        channel = connection.makefile("rwb", buffering=0)
        connection.close()
        channel.readline()
        self._qmp(channel, "qmp_capabilities")
        return channel

    @staticmethod
    def _qmp(channel: socket.SocketIO, command: str, **arguments: object) -> dict:
        """Send one QMP command and return its answer, skipping event messages."""
        message: dict[str, object] = {"execute": command}
        if arguments:
            message["arguments"] = arguments
        channel.write(json.dumps(message).encode() + b"\n")
        while True:
            line = channel.readline()
            if not line:
                raise ToolMissing(f"QEMU closed its control socket during '{command}'")
            answer = json.loads(line)
            if "return" in answer or "error" in answer:
                return answer

    def kill_vm(self) -> None:
        """Kill QEMU at once, so it cannot tell swtpm to shut down."""
        pid_file = self._run / "qemu.pid"
        try:
            os.kill(int(pid_file.read_text()), signal.SIGKILL)
            pid_file.unlink()          # never signal a recycled process number later
        except (OSError, ValueError):
            pass
        if self._qemu is not None:
            self._qemu.kill()
            self._qemu.wait()

    def read_pcrs(self) -> PcrBanks:
        """Read all 24 registers of all four banks from the still-running swtpm.

        QEMU owned the TPM's data channel and is gone, so swtpm is handed a
        new data channel through its control socket, and raw read commands
        are sent over it.
        """
        if self._swtpm is None or self._swtpm.poll() is not None:
            raise ToolMissing("the software TPM is not running; its registers cannot be read")
        banks: PcrBanks = {}
        with socket.socket(socket.AF_UNIX) as control:
            control.settimeout(5)
            control.connect(str(self._run / "swtpm.sock"))
            ours, theirs = socket.socketpair()
            with ours, theirs:
                socket.send_fds(control, [struct.pack(">I", _SWTPM_CMD_SET_DATAFD)], [theirs.fileno()])
                if control.recv(16)[:4] != bytes(4):
                    raise ToolMissing("the software TPM refused a new data channel")
                ours.settimeout(5)
                for algorithm_id, (bank, _) in ALGORITHMS.items():
                    banks[bank] = self._read_bank(ours, algorithm_id)
        return banks

    @staticmethod
    def _read_bank(channel: socket.socket, algorithm_id: int) -> list[bytes]:
        values: dict[int, bytes] = {}
        for first in (0, 8, 16):
            channel.sendall(capture.build_pcr_read_command(algorithm_id, first))
            values.update(capture.parse_pcr_read_response(channel.recv(4096)))
        if sorted(values) != list(range(PCR_COUNT)):
            raise ToolMissing("the software TPM did not return all 24 registers")
        return [values[index] for index in range(PCR_COUNT)]

    # -- cleanup

    def stop(self) -> None:
        """Make sure neither process survives, and remove the sockets. Safe to repeat."""
        self.kill_vm()
        if self._swtpm is not None:
            if self._swtpm.poll() is None:
                self._swtpm.terminate()
                try:
                    self._swtpm.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._swtpm.kill()
                    self._swtpm.wait()
        for name in ("qmp.sock", "swtpm.sock", "qemu.pid"):
            try:
                (self._run / name).unlink()
            except OSError:
                pass
