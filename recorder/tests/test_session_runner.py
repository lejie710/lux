"""The boot's ending path and a whole run, driven with fakes. Nothing is booted."""
import hashlib
import io
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path, PurePosixPath
from unittest import mock

from recorder import cli, compare, preparation, recording, runner, session, staging, storymap
from recorder import eventlog as eventlog_module
from recorder.errors import (ComparisonRefused, GateFailure, KeysRefused, MachineFailure,
                             PredictionMissing, RunIncomplete, StagingRefused)
from recorder.tests import helpers
from recorder.tests.helpers import FakeGit
from recorder.tests.test_compare_prediction import (PREDICTION, recording_from_fixture,
                                                    signature_prediction)

MARKER = b"BdsDxe: starting Boot0001\r\nLUX-FINAL-MARKER loader idle after ExitBootServices\r\n"
REFUSAL = b"BdsDxe: failed to load Boot0001 \"disk\": Access Denied\r\n"
REFUSAL_END = b"BdsDxe: No bootable option or device was found.\r\n"
LIMITS = session.Limits()


class RunBoot(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.clock = helpers.FakeClock()

    def _machine(self, **arguments: object) -> helpers.FakeMachine:
        arguments.setdefault("live", helpers.live_banks("normal"))
        return helpers.FakeMachine(self.clock, self.directory, **arguments)

    def test_accepted_boot_ends_by_pause_save_kill_read_stop(self) -> None:
        machine = self._machine(console_at={5.0: MARKER})
        observation = session.run_boot(machine, self.clock, LIMITS)
        self.assertEqual(machine.calls, ["start", "pause_and_save_memory", "kill_vm", "read_pcrs", "stop"])
        self.assertEqual(observation.trigger, session.TRIGGER_MARKER)
        self.assertEqual(observation.ending, session.ENDING_PAUSED)
        self.assertEqual(observation.seconds_to_trigger, 5.0)
        self.assertEqual(observation.seconds_to_pause, 8.0)          # trigger plus 3 s of quiet
        self.assertEqual(observation.live_pcrs, helpers.live_banks("normal"))
        self.assertTrue(observation.settled)

    def test_refused_boot_takes_the_same_path(self) -> None:
        machine = self._machine(console_at={6.0: REFUSAL + REFUSAL_END})
        observation = session.run_boot(machine, self.clock, LIMITS)
        self.assertEqual(machine.calls, ["start", "pause_and_save_memory", "kill_vm", "read_pcrs", "stop"])
        self.assertEqual(observation.trigger, session.TRIGGER_REFUSAL)
        self.assertTrue(observation.settled)

    def test_pause_waits_until_the_tpm_log_stops_growing(self) -> None:
        machine = self._machine(console_at={6.0: REFUSAL + REFUSAL_END}, activity_until=10.0)
        session.run_boot(machine, self.clock, LIMITS)
        self.assertGreaterEqual(machine.paused_at, 13.0)             # last growth plus 3 s
        self.assertLess(machine.paused_at, 13.6)

    def test_a_refused_boot_is_not_over_before_the_firmware_says_so(self) -> None:
        """A slow host: 10 quiet seconds pass between the refusal and the firmware's last line."""
        machine = self._machine(console_at={6.0: REFUSAL, 16.0: REFUSAL + REFUSAL_END})
        observation = session.run_boot(machine, self.clock, LIMITS)
        self.assertGreaterEqual(machine.paused_at, 19.0)             # the last line plus 3 s
        self.assertTrue(observation.settled)

    def test_a_refusal_whose_end_never_comes_is_not_settled(self) -> None:
        machine = self._machine(console_at={6.0: REFUSAL})
        observation = session.run_boot(machine, self.clock, LIMITS)
        self.assertFalse(observation.settled)
        self.assertAlmostEqual(observation.seconds_to_pause, 6.0 + LIMITS.settle_max, delta=0.5)

    def test_failed_to_start_is_a_trigger_too(self) -> None:
        text = b"BdsDxe: failed to start Boot0001 \"disk\": Aborted\r\n"
        self.assertEqual(session.find_trigger(text), session.TRIGGER_REFUSAL)

    def test_settling_gives_up_after_its_maximum_and_says_so(self) -> None:
        machine = self._machine(console_at={1.0: MARKER}, activity_until=10_000.0)
        observation = session.run_boot(machine, self.clock, LIMITS)
        self.assertAlmostEqual(observation.seconds_to_pause, 1.0 + LIMITS.settle_max, delta=0.5)
        self.assertFalse(observation.settled)

    def test_no_trigger_ends_after_the_time_limit_and_is_still_captured(self) -> None:
        machine = self._machine(console_at={0.0: b"BdsDxe: loading Boot0001\r\n"})
        observation = session.run_boot(machine, self.clock, LIMITS)
        self.assertEqual(observation.trigger, session.TRIGGER_NONE)
        self.assertAlmostEqual(observation.seconds_to_trigger, LIMITS.trigger_timeout, delta=0.5)
        self.assertIn("pause_and_save_memory", machine.calls)

    def test_the_recorder_always_pauses_before_the_outer_kill_can_land(self) -> None:
        self.assertLess(LIMITS.trigger_timeout + LIMITS.settle_max + 10, session.QEMU_TIMEOUT_SECONDS)

    def test_a_machine_that_ends_without_any_output_is_a_machine_failure(self) -> None:
        machine = self._machine(console_at={}, exits_at=1.0, error_text="qemu: could not open firmware")
        with self.assertRaises(MachineFailure) as caught:
            session.run_boot(machine, self.clock, LIMITS)
        self.assertIn("could not open firmware", str(caught.exception))
        self.assertEqual(machine.calls[-1], "stop")

    def test_a_response_cut_into_pieces_is_read_whole(self) -> None:
        whole = bytes.fromhex("80010000000e00000000") + b"abcd"
        pieces = [whole[:3], whole[3:10], whole[10:12], whole[12:], b"next response"]
        self.assertEqual(session.receive_response(lambda count: pieces.pop(0)[:count]), whole)
        ended = [whole[:6], b""]
        with self.assertRaises(MachineFailure):
            session.receive_response(lambda count: ended.pop(0))

    def test_guest_that_powers_off_is_not_paused_and_has_no_live_read(self) -> None:
        machine = self._machine(console_at={2.0: b"LUX-SETVAR done\r\n"}, exits_at=4.0)
        observation = session.run_boot(machine, self.clock, LIMITS)
        self.assertEqual(machine.calls, ["start", "stop"])
        self.assertEqual(observation.ending, session.ENDING_GUEST)
        self.assertIsNone(observation.live_pcrs)
        self.assertIsNone(observation.memory_file)

    def test_both_processes_are_stopped_when_any_step_fails(self) -> None:
        for step in ("start", "pause_and_save_memory", "kill_vm", "read_pcrs"):
            self.clock = helpers.FakeClock()
            machine = self._machine(console_at={1.0: MARKER}, fail_on=step)
            with self.assertRaises(RuntimeError):
                session.run_boot(machine, self.clock, LIMITS)
            self.assertEqual(machine.calls[-1], "stop", step)
            self.assertFalse((self.directory / "mem.bin").exists(), step)   # guest memory is never kept

    def test_trigger_is_read_from_guest_output_only(self) -> None:
        self.assertEqual(session.find_trigger(b"BdsDxe: loading Boot0001"), session.TRIGGER_NONE)
        self.assertEqual(session.find_trigger(MARKER), session.TRIGGER_MARKER)
        self.assertEqual(session.find_trigger(REFUSAL), session.TRIGGER_REFUSAL)

    def test_command_lines_are_explicit_and_differ_only_in_the_run_directory(self) -> None:
        firmware = PurePosixPath("/usr/share/OVMF/OVMF_CODE_4M.secboot.fd")
        first = session.qemu_arguments(PurePosixPath("/work/runs/a"), firmware)
        second = session.qemu_arguments(PurePosixPath("/work/runs/b"), firmware)
        self.assertEqual(first[:4], ["timeout", "-s", "KILL", "300"])
        self.assertNotIn("-pidfile", first)          # cleanup kills the process group instead
        self.assertEqual([x.replace("/work/runs/a", "R") for x in first],
                         [x.replace("/work/runs/b", "R") for x in second])
        joined = " ".join(first)
        for needed in ("pc-q35-8.2,smm=on,accel=tcg", "-cpu qemu64", "-m 512", "clock=vm",
                       f"unit=0,readonly=on,file={firmware}", "-no-reboot"):
            self.assertIn(needed, joined)
        self.assertIn("level=20", " ".join(session.swtpm_arguments(PurePosixPath("/work/runs/a"))))


class WholeRun(unittest.TestCase):
    """`record_run` from the prediction gate to the finished recording."""

    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        template = helpers.template_store()
        self.work = self.temp / "work"
        (self.work / "template").mkdir(parents=True)
        (self.work / "template" / "vars-template.fd").write_bytes(template)
        self.testkeys = helpers.copy_testkeys(self.temp / "testkeys", template)
        self.predictions = self.temp / "predictions"
        self.predictions.mkdir()
        firmware = self.temp / "firmware.fd"
        firmware.write_bytes(helpers.FIRMWARE_BYTES)
        patcher = mock.patch.object(staging, "PACKAGED_FIRMWARE", firmware)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.machines: list[helpers.FakeMachine] = []
        self.memory = (bytes(512) + b"\x90" * 40 + eventlog_module.HEADER_SIGNATURE + b"\x90" * 64
                       + helpers.fixture_bytes("normal-eventlog.bin") + b"\xff" * 128)
        self.live = helpers.live_banks("normal")
        self.tpm_log = helpers.fixture_text("normal-tpm.log")
        self.console = helpers.fixture_bytes("normal-serial.log")
        self.activity_until = 0.0
        self.repeat_checks = 0

    def _factory(self, run_directory: Path, firmware: Path) -> helpers.FakeMachine:
        machine = helpers.FakeMachine(
            helpers.FakeClock(), run_directory, {5.0: self.console},
            tpm_log=self.tpm_log, memory=self.memory, live=self.live,
            activity_until=self.activity_until)
        self.machines.append(machine)
        return machine

    def _repeat_holds(self) -> None:
        self.repeat_checks += 1

    def _env(self, git=None, require_repeat=None) -> runner.Environment:
        clock = helpers.FakeClock()

        def factory(run_directory: Path, firmware: Path) -> helpers.FakeMachine:
            machine = self._factory(run_directory, firmware)
            machine.clock = clock
            return machine

        return runner.Environment(
            testkeys_directory=self.testkeys, predictions_directory=self.predictions,
            work_directory=self.work, machine_factory=factory, clock=clock, limits=LIMITS,
            tool_versions=lambda: {"qemu": "test"}, host_os="test os", git=git or FakeGit(),
            require_repeat=require_repeat or self._repeat_holds)

    def _record(self, name: str, experiment: str = "normal", **arguments: object) -> runner.RunResult:
        request = runner.RunRequest(name, experiment, "2026-01-01T00:00:00Z")
        return runner.record_run(request, self._env(**arguments))

    def test_a_run_becomes_a_recording_built_from_real_evidence(self) -> None:
        result = self._record("normal-1")
        document = result.document
        self.assertEqual(result.event_log, helpers.fixture_bytes("normal-eventlog.bin"))
        self.assertEqual(document["outcome"]["result"], "accepted")
        self.assertEqual(document["outcome"]["ending"], "paused-then-killed")
        self.assertEqual(len(document["events"]), 28)
        self.assertEqual((len(document["console"]), len(document["loader_report"])), (10, 148))
        self.assertTrue(document["gate"]["passed"])
        self.assertEqual(document["gate"]["counts"], {"log_candidates_parsed": 1,
                                                      "content_digests_recomputed": 21})
        self.assertEqual(set(document["gate"]["checks"].values()), {True})
        self.assertEqual(document["outcome"]["refusal_lines"], [])
        self.assertIs(document["outcome"]["settled"], True)
        self.assertIsNone(document["run"]["change_detail"])
        self.assertEqual(self.repeat_checks, 0)                  # only counted runs need it
        self.assertEqual(document["provenance"]["loader"]["authenticode_sha256"], helpers.LOADER_AUTHENTICODE)
        self.assertEqual(document["provenance"]["firmware"]["sha256"],
                         hashlib.sha256(b"firmware image").hexdigest())
        self.assertIsNone(document["provenance"]["prediction"])
        self.assertEqual(document["provenance"]["recorded_at"], "2026-01-01T00:00:00Z")

    def test_no_host_path_and_no_memory_file_survive(self) -> None:
        document = self._record("normal-1").document
        self.assertIn("<run-dir>/serial.log", document["provenance"]["qemu_command_line"])
        self.assertNotIn(str(self.temp), recording.dumps(document))
        self.assertEqual(list(self.work.rglob("mem.bin")), [])

    def test_two_runs_are_identical_on_every_compared_field(self) -> None:
        first = self._record("normal-1").document
        second = runner.record_run(
            runner.RunRequest("normal-2", "normal", "2027-02-02T02:02:02Z"), self._env()).document
        result = compare.compare_recordings(first, second, "a", "b")
        self.assertTrue(result["identical"], result)

    def test_every_event_of_a_recording_has_exactly_one_stop_rule(self) -> None:
        for row in self._record("normal-1").document["events"]:
            self.assertIsNotNone(row["stop"], row)
        # Every rule except the one for a returning boot option occurs in an accepted boot.
        self.assertEqual({rule.name for rule in storymap.RULES} - {"boot-return"},
                         {row["stop_rule"] for row in self._record("n").document["events"]})

    def test_disagreeing_readings_raise_and_leave_no_memory_file(self) -> None:
        self.live["sha256"][7] = bytes(32)
        with self.assertRaises(GateFailure):
            self._record("normal-1")
        self.assertEqual(list(self.work.rglob("mem.bin")), [])

    def test_two_log_candidates_raise(self) -> None:
        self.memory += helpers.fixture_bytes("normal-eventlog.bin") + b"\xff" * 64
        with self.assertRaises(GateFailure):
            self._record("normal-1")

    def test_no_log_in_memory_raises(self) -> None:
        self.memory = bytes(4096)
        with self.assertRaises(GateFailure):
            self._record("normal-1")

    def test_guest_that_ended_by_itself_is_not_recorded(self) -> None:
        env = self._env()
        original = env.machine_factory

        def exiting(run_directory: Path, firmware: Path) -> helpers.FakeMachine:
            machine = original(run_directory, firmware)
            machine.console_at = {1.0: self.console}     # it printed, then powered off
            machine.exits_at = 2.0
            return machine

        env = runner.Environment(**{**env.__dict__, "machine_factory": exiting})
        with self.assertRaises(GateFailure):
            runner.record_run(runner.RunRequest("normal-1", "normal", "now"), env)

    # ---- outcomes that may not become a recording

    def test_a_normal_run_that_was_not_accepted_is_not_recorded(self) -> None:
        """A hung boot must not pass as a normal run: two of them would compare as identical."""
        self.console = b"BdsDxe: loading Boot0001\r\n"
        with self.assertRaises(RunIncomplete) as caught:
            self._record("normal-1")
        self.assertIn("'timeout'", str(caught.exception))
        self.console = REFUSAL + REFUSAL_END
        with self.assertRaises(RunIncomplete):
            self._record("normal-1")

    def test_a_changed_run_that_reached_neither_line_is_recorded_as_timeout(self) -> None:
        self.console = b"BdsDxe: loading Boot0001\r\n"
        document = self._record("pilot", "e2").document
        self.assertEqual(document["outcome"]["result"], "timeout")
        self.assertEqual(document["outcome"]["trigger"], session.TRIGGER_NONE)

    def test_a_boot_whose_end_was_not_seen_is_never_recorded(self) -> None:
        self.activity_until = 10_000.0                           # the TPM log never stands still
        for experiment in ("normal", "e2"):
            with self.assertRaises(RunIncomplete) as caught:
                self._record("unsettled", experiment)
            self.assertIn("not seen in time", str(caught.exception))
        self.assertEqual(list(self.work.rglob("mem.bin")), [])

    def test_the_change_of_a_pilot_is_proven_in_its_recording(self) -> None:
        run = self._record("pilot", "e2").document["run"]
        self.assertEqual(run["change_detail"]["loader_byte"],
                         {"file_offset": 0x85E, "old_value": 0x41, "new_value": 0x42,
                          "area": "section .data"})
        self.assertEqual(len(run["experiment_sha256"]), 64)

    # ---- the prediction gate

    def test_counted_experiment_without_prediction_is_refused_before_anything_starts(self) -> None:
        for experiment in ("boot-order", "signature-byte", "rebuilt-firmware"):
            with self.assertRaises(PredictionMissing):
                self._record("blind", experiment)
        self.assertEqual(self.machines, [])
        self.assertFalse((self.work / "runs").exists())

    def test_counted_experiment_with_uncommitted_prediction_is_refused(self) -> None:
        import json
        (self.predictions / "boot-order.json").write_bytes(json.dumps(PREDICTION).encode())
        for git in (FakeGit(tracked=False), FakeGit(status="M  boot-order.json")):
            with self.assertRaises(PredictionMissing):
                self._record("blind", "boot-order", git=git)
        self.assertEqual(self.machines, [])

    def test_counted_experiment_with_committed_prediction_runs_and_names_it(self) -> None:
        import json
        path = self.predictions / "boot-order.json"
        path.write_bytes(json.dumps(PREDICTION).encode())
        # The fake machine replays the normal boot; only the gate and the bookkeeping are under test.
        document = self._record("blind", "boot-order", git=FakeGit(commit="feedbeef\n")).document
        self.assertEqual(len(self.machines), 1)
        self.assertEqual(document["provenance"]["prediction"], {
            "path": "predictions/boot-order.json", "parameters": {},
            "sha256": recording.sha256_of_file(path), "commit": "feedbeef"})
        self.assertEqual(document["run"]["kind"], "counted")
        self.assertEqual(self.repeat_checks, 1)

    def test_counted_experiment_is_refused_when_the_normal_run_does_not_repeat(self) -> None:
        import json
        (self.predictions / "boot-order.json").write_bytes(json.dumps(PREDICTION).encode())

        def no_repeat() -> None:
            raise ComparisonRefused("the two normal runs are not identical")

        with self.assertRaises(ComparisonRefused):
            self._record("blind", "boot-order", require_repeat=no_repeat)
        self.assertEqual(self.machines, [])
        self.assertFalse((self.work / "runs").exists())

    def test_the_changed_byte_comes_from_the_committed_prediction_and_is_recorded(self) -> None:
        import json
        path = self.predictions / "signature-byte.json"
        path.write_bytes(json.dumps(signature_prediction(signature_area_offset=64)).encode())
        document = self._record("blind", "signature-byte").document
        self.assertEqual(document["provenance"]["prediction"]["parameters"], {"signature_area_offset": 64})
        self.assertEqual(document["run"]["change_detail"]["loader_byte"]["area"], "signature area")
        path.write_bytes(json.dumps(signature_prediction()).encode())        # no byte named
        with self.assertRaises(PredictionMissing):
            self._record("blind-2", "signature-byte")
        self.assertEqual(len(self.machines), 1)

    def test_a_prediction_edited_behind_git_is_refused_before_anything_starts(self) -> None:
        import json
        (self.predictions / "boot-order.json").write_bytes(json.dumps(PREDICTION).encode())
        with self.assertRaises(PredictionMissing):
            self._record("blind", "boot-order", git=FakeGit(blob=b"the committed text was another"))
        self.assertEqual(self.machines, [])

    def test_pilot_and_normal_runs_need_no_prediction(self) -> None:
        git = FakeGit(tracked=False)
        self.assertEqual(self._record("e2", "e2", git=git).document["run"]["kind"], "pilot")
        self.assertEqual(git.asked, [])

    # ---- other refusals

    def test_bad_run_name_missing_template_and_changed_keys_are_refused(self) -> None:
        for name in ("Normal", "../x", "", "a b"):
            with self.assertRaises(StagingRefused):
                self._record(name)
        (self.testkeys / "db.crt").write_bytes(b"changed")
        with self.assertRaises(KeysRefused):
            self._record("normal-1")
        shutil.rmtree(self.testkeys)
        helpers.copy_testkeys(self.testkeys, helpers.template_store())
        (self.work / "template" / "vars-template.fd").write_bytes(helpers.make_store([("PK", b"x")]))
        with self.assertRaises(StagingRefused):
            self._record("normal-1")
        (self.work / "template" / "vars-template.fd").unlink()
        with self.assertRaises(StagingRefused):
            self._record("normal-1")
        self.assertEqual(self.machines, [])


class Preparation(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        self.enrolled = helpers.template_store()
        self.empty = self.temp / "empty.fd"
        self.empty.write_bytes(helpers.make_store([]))
        (self.temp / "firmware.fd").write_bytes(helpers.FIRMWARE_BYTES)
        self.testkeys = helpers.copy_testkeys(self.temp / "testkeys", self.enrolled)
        self.boots = 0

    def _run(self, command: list[str]) -> str:
        """Stands in for the assembler and linker: the build result is the committed loader."""
        if command[0] == "ld":
            shutil.copyfile(helpers.TESTKEYS / "loader-signed.efi", command[command.index("-o") + 1])
        return ""

    def _factory(self, console: bytes, store: bytes):
        def factory(run_directory: Path, firmware: Path) -> helpers.FakeMachine:
            self.boots += 1
            self.staged_program = (run_directory / "esp/EFI/BOOT/BOOTX64.EFI").read_bytes()
            self.staged_store = (run_directory / "vars.fd").read_bytes()
            (run_directory / "vars.fd").write_bytes(store)       # what the firmware would write
            return helpers.FakeMachine(self.clock, run_directory, {2.0: console}, exits_at=4.0)
        return factory

    def _env(self, console: bytes, store: bytes) -> preparation.PrepareEnvironment:
        self.clock = helpers.FakeClock()
        return preparation.PrepareEnvironment(
            testkeys_directory=self.testkeys, work_directory=self.temp / "work", run=self._run,
            machine_factory=self._factory(console, store), clock=self.clock, limits=LIMITS,
            empty_store=self.empty, firmware=self.temp / "firmware.fd")

    GOOD = (b"LUX-SETVAR db status=00\r\nLUX-SETVAR KEK status=00\r\n"
            b"LUX-SETVAR PK status=00\r\nLUX-SETVAR done\r\n")

    def test_template_is_made_by_one_enrolment_boot_and_reused(self) -> None:
        env = self._env(self.GOOD, self.enrolled)
        summary = preparation.prepare(env)
        self.assertEqual(summary["keys"], "verified")
        self.assertEqual(summary["vars_template_sha256"], hashlib.sha256(self.enrolled).hexdigest())
        self.assertEqual(self.staged_store, self.empty.read_bytes())
        self.assertIn("LUX-SETVAR PK status=??".encode("utf-16le"), self.staged_program)
        preparation.prepare(env)
        self.assertEqual(self.boots, 1)

    def test_a_failed_write_is_refused(self) -> None:
        bad = self.GOOD.replace(b"KEK status=00", b"KEK status=1A")
        with self.assertRaises(StagingRefused):
            preparation.prepare(self._env(bad, self.enrolled))
        self.assertFalse((self.temp / "work" / "template" / "vars-template.fd").exists())

    def test_a_store_without_the_keys_is_refused(self) -> None:
        with self.assertRaises(StagingRefused):
            preparation.prepare(self._env(self.GOOD, helpers.make_store([("PK", b"pk")])))

    def test_a_template_that_differs_from_the_manifest_is_discarded(self) -> None:
        other = helpers.make_store([("PK", b"1"), ("KEK", b"2"), ("db", b"3"), ("SecureBootEnable", b"\x01")])
        with self.assertRaises(StagingRefused):
            preparation.prepare(self._env(self.GOOD, other))
        self.assertFalse((self.temp / "work" / "template" / "vars-template.fd").exists())

    def test_a_firmware_file_that_differs_from_the_pinned_one_is_refused(self) -> None:
        (self.temp / "firmware.fd").write_bytes(b"a package update")
        with self.assertRaises(StagingRefused) as caught:
            preparation.prepare(self._env(self.GOOD, self.enrolled))
        self.assertIn("is pinned", str(caught.exception))
        self.assertEqual(self.boots, 0)

    def test_keys_are_never_regenerated_over_existing_ones(self) -> None:
        with self.assertRaises(KeysRefused):
            preparation.prepare(self._env(self.GOOD, self.enrolled), generate_keys=True)
        self.assertEqual(self.boots, 0)

    def test_missing_keys_are_not_generated_silently(self) -> None:
        shutil.rmtree(self.testkeys)
        with self.assertRaises(KeysRefused):
            preparation.prepare(self._env(self.GOOD, self.enrolled))
        self.assertFalse(self.testkeys.exists())

    def test_a_different_loader_build_is_refused(self) -> None:
        env = self._env(self.GOOD, self.enrolled)

        def other_build(command: list[str]) -> str:
            if command[0] == "ld":
                changed = bytearray((helpers.TESTKEYS / "loader-signed.efi").read_bytes())
                changed[0x400] ^= 1
                Path(command[command.index("-o") + 1]).write_bytes(changed)
            return ""

        env = preparation.PrepareEnvironment(**{**env.__dict__, "run": other_build})
        with self.assertRaises(StagingRefused):
            preparation.prepare(env)
        self.assertEqual(self.boots, 0)


class CommandLine(unittest.TestCase):
    def _main(self, arguments: list[str]) -> tuple[int, str, str]:
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(arguments)
        return code, out.getvalue(), err.getvalue()

    def test_counted_experiment_is_refused_with_exit_code_1_and_no_file(self) -> None:
        target = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, target, ignore_errors=True)
        with mock.patch.object(cli.provenance, "require_programs"), \
                mock.patch.object(cli, "QemuMachine", side_effect=AssertionError("no machine may be made")):
            code, _, err = self._main(["record", "blind", "--experiment", "signature-byte",
                                       "--out", str(target), "--work-dir", str(target / "work")])
        self.assertEqual(code, 1)
        self.assertIn("refused: experiment 'signature-byte' is counted and must not run", err)
        self.assertEqual(list(target.iterdir()), [])

    def test_gate_failure_gives_exit_code_1_and_writes_nothing(self) -> None:
        target = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, target, ignore_errors=True)
        with mock.patch.object(cli.provenance, "require_programs"), \
                mock.patch.object(cli.runner, "record_run", side_effect=GateFailure("readings disagree")):
            code, _, err = self._main(["record", "normal-1", "--experiment", "normal", "--out", str(target)])
        self.assertEqual(code, 1)
        self.assertIn("refused: readings disagree", err)
        self.assertEqual(list(target.iterdir()), [])

    # ---- record: existing recordings and the exit code

    def _result(self, result: str = "accepted") -> runner.RunResult:
        document = recording_from_fixture("normal", "x")
        document["outcome"]["result"] = result
        return runner.RunResult(document, b"raw event log")

    def _record_into(self, target: Path, name: str, experiment: str, *extra: str,
                     result: str = "accepted") -> tuple[int, str, str, mock.Mock]:
        with mock.patch.object(cli.provenance, "require_programs"), \
                mock.patch.object(cli.runner, "record_run", return_value=self._result(result)) as run:
            code, out, err = self._main(["record", name, "--experiment", experiment,
                                         "--out", str(target), *extra])
        return code, out, err, run

    def _temp(self) -> Path:
        target = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, target, ignore_errors=True)
        return target

    def test_an_existing_recording_is_not_overwritten_without_replace(self) -> None:
        target = self._temp()
        code, _, _, run = self._record_into(target, "normal-1", "normal")
        self.assertEqual((code, run.call_count), (0, 1))
        first = (target / "normal-1" / "recording.json").read_bytes()
        code, _, err, run = self._record_into(target, "normal-1", "normal")
        self.assertEqual((code, run.call_count), (1, 0))             # refused before any boot
        self.assertIn("pass --replace", err)
        self.assertEqual((target / "normal-1" / "recording.json").read_bytes(), first)
        code, _, _, run = self._record_into(target, "normal-1", "normal", "--replace")
        self.assertEqual((code, run.call_count), (0, 1))

    def test_a_counted_recording_is_never_replaced(self) -> None:
        target = self._temp()
        (target / "blind").mkdir()
        (target / "blind" / "recording.json").write_text("the first result")
        code, _, err, run = self._record_into(target, "blind", "boot-order", "--replace")
        self.assertEqual((code, run.call_count), (1, 0))
        self.assertIn("recorded once", err)
        self.assertEqual((target / "blind" / "recording.json").read_text(), "the first result")

    def test_a_recorded_timeout_gives_exit_code_3(self) -> None:
        target = self._temp()
        code, _, err, _ = self._record_into(target, "hung", "e2", result="timeout")
        self.assertEqual(code, 3)
        self.assertIn("recorded as 'timeout'", err)
        self.assertTrue((target / "hung" / "recording.json").is_file())

    # ---- compare

    def _two_normal_runs(self, target: Path) -> tuple[Path, Path]:
        first, second = target / "normal-1" / "recording.json", target / "normal-2" / "recording.json"
        recording.write_json(first, recording_from_fixture("normal", "normal-1"))
        recording.write_json(second, recording_from_fixture("normal", "normal-2", "2026-01-01T00:01:00Z"))
        return first, second

    def test_compare_refuses_a_recording_with_itself_a_copy_and_a_failed_gate(self) -> None:
        target = self._temp()
        first, second = self._two_normal_runs(target)
        out = target / "c.json"
        code, _, err = self._main(["compare", str(first), str(first), "--out", str(out)])
        self.assertEqual(code, 1)
        self.assertIn("the same recording", err)
        copy = recording_from_fixture("normal", "normal-9")                  # same boot, new name
        recording.write_json(target / "copy.json", copy)
        code, _, err = self._main(["compare", str(first), str(target / "copy.json"), "--out", str(out)])
        self.assertEqual(code, 1)
        self.assertIn("a copy of the other", err)
        failed = recording_from_fixture("normal", "normal-2", "2026-01-01T00:01:00Z")
        failed["gate"]["passed"] = False
        recording.write_json(target / "failed.json", failed)
        code, _, err = self._main(["compare", str(first), str(target / "failed.json"), "--out", str(out)])
        self.assertEqual(code, 1)
        self.assertIn("agreement gate", err)
        self.assertFalse(out.exists())
        code, text, _ = self._main(["compare", str(first), str(second), "--out", str(out)])
        self.assertEqual(code, 0)
        self.assertIn("identical: true", text)

    def test_a_document_with_a_missing_field_is_a_refusal_not_a_traceback(self) -> None:
        target = self._temp()
        first, second = self._two_normal_runs(target)
        broken = recording_from_fixture("normal", "normal-2", "2026-01-01T00:01:00Z")
        del broken["pcrs"]
        recording.write_json(second, broken)
        code, _, err = self._main(["compare", str(first), str(second), "--out", str(target / "c.json")])
        self.assertEqual(code, 1)
        self.assertIn("refused: a document lacks a field", err)

    def test_the_repeat_precondition_is_checked_against_the_files_on_disk(self) -> None:
        target = self._temp()
        first, second = self._two_normal_runs(target)
        repeat = target / cli.REPEAT_COMPARISON
        with self.assertRaises(ComparisonRefused):                           # no comparison yet
            cli._require_repeat_on_file(repeat, target)
        self.assertEqual(self._main(["compare", str(first), str(second), "--out", str(repeat)])[0], 0)
        cli._require_repeat_on_file(repeat, target)
        second.write_bytes(second.read_bytes() + b"\n")                      # changed afterwards
        with self.assertRaises(ComparisonRefused):
            cli._require_repeat_on_file(repeat, target)
        second.unlink()
        with self.assertRaises(ComparisonRefused):
            cli._require_repeat_on_file(repeat, target)

    # ---- check

    def _scored_setup(self) -> dict[str, Path]:
        """Two normal runs, one counted run under a prediction, and both comparisons."""
        import json
        target = self._temp()
        first, second = self._two_normal_runs(target)
        files = {"baseline": first, "prediction": target / "boot-order.json",
                 "changed": target / "blind" / "recording.json",
                 "repeat": target / cli.REPEAT_COMPARISON, "comparison": target / "c.json",
                 "score": target / "score.json"}
        files["prediction"].write_bytes(json.dumps(PREDICTION).encode())
        changed = recording_from_fixture("e2", "blind", "2026-01-01T00:02:00Z")
        counted = cli.experiments.get("boot-order")
        changed["run"].update(experiment="boot-order", kind="counted",
                              experiment_sha256=cli.experiments.fingerprint(counted))
        changed["provenance"]["prediction"] = {
            "path": "predictions/boot-order.json", "commit": "c", "parameters": {},
            "sha256": recording.sha256_of_file(files["prediction"])}
        recording.write_json(files["changed"], changed)
        for baseline, other, out in ((first, second, files["repeat"]),
                                     (first, files["changed"], files["comparison"])):
            code, _, err = self._main(["compare", str(baseline), str(other), "--out", str(out)])
            self.assertEqual(code, 0, err)
        return files

    def _check(self, files: dict[str, Path], *leave_out: str) -> tuple[int, str, str]:
        arguments = ["check", str(files["comparison"]), "--prediction", str(files["prediction"]),
                     "--recording", str(files["changed"]), "--baseline", str(files["baseline"])]
        if "repeat" not in leave_out:
            arguments += ["--repeat", str(files["repeat"])]
        if "out" not in leave_out:
            arguments += ["--out", str(files["score"])]
        return self._main(arguments)

    def test_check_scores_a_counted_run_and_writes_the_result_file(self) -> None:
        files = self._scored_setup()
        code, out, err = self._check(files)
        self.assertEqual(code, 0, err)                           # 0 means scored, rows may mismatch
        self.assertIn("specification-required rows met: 0 of 1", out)
        self.assertIn("open rows predicted correctly: 2 of 3", out)
        self.assertIn("mismatches: continues, pcr1", out)
        score = recording.load_json(files["score"], "lux-score/1")
        self.assertEqual((score["required_met"], score["required_total"]), (0, 1))
        self.assertEqual((score["open_correct"], score["open_total"]), (2, 3))
        self.assertEqual(score["mismatches"], ["continues", "pcr1"])
        self.assertEqual([row["id"] for row in score["rows"]], ["continues", "pcr1", "pcr0", "order-kept"])
        self.assertEqual(score["rows"][0], {"id": "continues", "basis": "uefi-required", "held": False})
        self.assertEqual((score["experiment"], score["run"]), ("boot-order", "blind"))
        self.assertEqual(score["comparison_sha256"], recording.sha256_of_file(files["comparison"]))
        self.assertEqual(score["repeat_comparison_sha256"], recording.sha256_of_file(files["repeat"]))
        self.assertEqual(score["changed_recording_sha256"], recording.sha256_of_file(files["changed"]))
        self.assertEqual(score["prediction"]["sha256"], recording.sha256_of_file(files["prediction"]))

    def test_check_refuses_an_edited_prediction(self) -> None:
        files = self._scored_setup()
        files["prediction"].write_bytes(files["prediction"].read_bytes() + b"\n")
        code, _, err = self._check(files)
        self.assertEqual(code, 1)
        self.assertIn("not the one this run was recorded under", err)
        self.assertFalse(files["score"].exists())

    def test_check_refuses_a_counted_run_without_the_repeat_comparison(self) -> None:
        files = self._scored_setup()
        code, _, err = self._check(files, "repeat")
        self.assertEqual(code, 1)
        self.assertIn("--repeat", err)
        files["repeat"].write_bytes(files["comparison"].read_bytes())        # not two normal runs
        code, _, err = self._check(files)
        self.assertEqual(code, 1)
        self.assertIn("not between two normal runs", err)

    def test_check_refuses_another_baseline_or_recording_than_the_comparison_used(self) -> None:
        files = self._scored_setup()
        other = dict(files, baseline=files["baseline"].parent.parent / "normal-2" / "recording.json")
        code, _, err = self._check(other)
        self.assertEqual(code, 1)
        self.assertIn("not made against this baseline", err)
        files["changed"].write_bytes(files["changed"].read_bytes() + b"\n")
        code, _, err = self._check(files)
        self.assertEqual(code, 1)
        self.assertIn("not made from this recording", err)

    def test_check_refuses_when_the_experiment_description_changed_after_the_run(self) -> None:
        files = self._scored_setup()
        edited = cli.experiments.Experiment("boot-order", "counted", "BootOrder lists its entries in reverse")
        with mock.patch.dict(cli.experiments.EXPERIMENTS, {"boot-order": edited}):
            code, _, err = self._check(files)
        self.assertEqual(code, 1)
        self.assertIn("description was changed after this run", err)

    def test_missing_file_is_a_plain_refusal(self) -> None:
        code, _, err = self._main(["compare", "nope-a.json", "nope-b.json", "--out", "nope-c.json"])
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("refused: cannot read"))


if __name__ == "__main__":
    unittest.main()
