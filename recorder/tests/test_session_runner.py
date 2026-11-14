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
from recorder.errors import GateFailure, KeysRefused, PredictionMissing, StagingRefused
from recorder.tests import helpers
from recorder.tests.test_compare_prediction import PREDICTION, FakeGit

MARKER = b"BdsDxe: starting Boot0001\r\nLUX-FINAL-MARKER loader idle after ExitBootServices\r\n"
REFUSAL = b"BdsDxe: failed to load Boot0001 \"disk\": Access Denied\r\n"
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

    def test_refused_boot_takes_the_same_path(self) -> None:
        machine = self._machine(console_at={6.0: REFUSAL})
        observation = session.run_boot(machine, self.clock, LIMITS)
        self.assertEqual(machine.calls, ["start", "pause_and_save_memory", "kill_vm", "read_pcrs", "stop"])
        self.assertEqual(observation.trigger, session.TRIGGER_REFUSAL)

    def test_pause_waits_until_the_tpm_log_stops_growing(self) -> None:
        machine = self._machine(console_at={6.0: REFUSAL}, activity_until=10.0)
        session.run_boot(machine, self.clock, LIMITS)
        self.assertGreaterEqual(machine.paused_at, 13.0)             # last growth plus 3 s
        self.assertLess(machine.paused_at, 13.6)

    def test_console_growth_after_the_trigger_also_delays_the_pause(self) -> None:
        machine = self._machine(console_at={6.0: REFUSAL, 8.0: REFUSAL + b"BdsDxe: No bootable option\r\n"})
        session.run_boot(machine, self.clock, LIMITS)
        self.assertGreaterEqual(machine.paused_at, 11.0)

    def test_settling_gives_up_after_its_maximum(self) -> None:
        machine = self._machine(console_at={1.0: MARKER}, activity_until=10_000.0)
        observation = session.run_boot(machine, self.clock, LIMITS)
        self.assertAlmostEqual(observation.seconds_to_pause, 1.0 + LIMITS.settle_max, delta=0.5)

    def test_no_trigger_ends_after_the_time_limit_and_is_still_captured(self) -> None:
        machine = self._machine(console_at={0.0: b"BdsDxe: loading Boot0001\r\n"})
        observation = session.run_boot(machine, self.clock, LIMITS)
        self.assertEqual(observation.trigger, session.TRIGGER_NONE)
        self.assertAlmostEqual(observation.seconds_to_trigger, LIMITS.trigger, delta=0.5)
        self.assertIn("pause_and_save_memory", machine.calls)

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

    def test_trigger_is_read_from_guest_output_only(self) -> None:
        self.assertEqual(session.find_trigger(b"BdsDxe: loading Boot0001"), session.TRIGGER_NONE)
        self.assertEqual(session.find_trigger(MARKER), session.TRIGGER_MARKER)
        self.assertEqual(session.find_trigger(REFUSAL), session.TRIGGER_REFUSAL)

    def test_command_lines_are_explicit_and_differ_only_in_the_run_directory(self) -> None:
        firmware = PurePosixPath("/usr/share/OVMF/OVMF_CODE_4M.secboot.fd")
        first = session.qemu_arguments(PurePosixPath("/work/runs/a"), firmware)
        second = session.qemu_arguments(PurePosixPath("/work/runs/b"), firmware)
        self.assertEqual(first[:4], ["timeout", "-s", "KILL", "300"])
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
        firmware.write_bytes(b"firmware image")
        patcher = mock.patch.object(staging, "PACKAGED_FIRMWARE", firmware)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.machines: list[helpers.FakeMachine] = []
        self.memory = (bytes(512) + b"\x90" * 40 + eventlog_module.HEADER_SIGNATURE + b"\x90" * 64
                       + helpers.fixture_bytes("normal-eventlog.bin") + b"\xff" * 128)
        self.live = helpers.live_banks("normal")
        self.tpm_log = helpers.fixture_text("normal-tpm.log")

    def _factory(self, run_directory: Path, firmware: Path) -> helpers.FakeMachine:
        machine = helpers.FakeMachine(
            helpers.FakeClock(), run_directory, {5.0: helpers.fixture_bytes("normal-serial.log")},
            tpm_log=self.tpm_log, memory=self.memory, live=self.live)
        self.machines.append(machine)
        return machine

    def _env(self, git=None) -> runner.Environment:
        clock = helpers.FakeClock()

        def factory(run_directory: Path, firmware: Path) -> helpers.FakeMachine:
            machine = self._factory(run_directory, firmware)
            machine.clock = clock
            return machine

        return runner.Environment(
            testkeys_directory=self.testkeys, predictions_directory=self.predictions,
            work_directory=self.work, machine_factory=factory, clock=clock, limits=LIMITS,
            tool_versions=lambda: {"qemu": "test"}, host_os="test os", git=git or FakeGit())

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
        self.assertEqual(len(document["console"]), 158)
        self.assertTrue(document["gate"]["passed"])
        self.assertEqual(document["gate"]["checks"]["log_candidates_parsed"], 1)
        self.assertEqual(document["gate"]["checks"]["content_digests_recomputed"], 21)
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
        self.assertEqual({rule.name for rule in storymap.RULES},
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
            machine.exits_at = 2.0
            return machine

        env = runner.Environment(**{**env.__dict__, "machine_factory": exiting})
        with self.assertRaises(GateFailure):
            runner.record_run(runner.RunRequest("normal-1", "normal", "now"), env)

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
            "path": "predictions/boot-order.json",
            "sha256": recording.sha256_of_file(path), "commit": "feedbeef"})
        self.assertEqual(document["run"]["kind"], "counted")

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
        with mock.patch.object(cli.provenance, "require_programs"):
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

    def test_compare_and_check_commands(self) -> None:
        from recorder.tests.test_compare_prediction import recording_from_fixture
        import json
        target = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, target, ignore_errors=True)
        prediction_file = target / "boot-order.json"
        prediction_file.write_bytes(json.dumps(PREDICTION).encode())
        baseline = recording_from_fixture("normal", "normal-1")
        changed = recording_from_fixture("e2", "blind")
        changed["provenance"]["prediction"] = {
            "path": "predictions/boot-order.json", "commit": "c",
            "sha256": recording.sha256_of_file(prediction_file)}
        recording.write_json(target / "a.json", baseline)
        recording.write_json(target / "b.json", changed)
        code, out, _ = self._main(["compare", str(target / "a.json"), str(target / "b.json"),
                                   "--out", str(target / "c.json")])
        self.assertEqual(code, 0)
        self.assertIn("identical: false", out)
        self.assertIn("[4, 5, 7]", out)
        check = ["check", str(target / "c.json"), "--prediction", str(prediction_file),
                 "--recording", str(target / "b.json")]
        code, out, _ = self._main(check)
        self.assertEqual(code, 0)
        self.assertIn("specification-required rows met: 0 of 1", out)
        self.assertIn("open rows predicted correctly: 2 of 3", out)
        self.assertIn("mismatches: continues, pcr1", out)
        prediction_file.write_bytes(prediction_file.read_bytes() + b"\n")     # edited after the run
        code, _, err = self._main(check)
        self.assertEqual(code, 1)
        self.assertIn("not the one this run was recorded under", err)

    def test_missing_file_is_a_plain_refusal(self) -> None:
        code, _, err = self._main(["compare", "nope-a.json", "nope-b.json", "--out", "nope-c.json"])
        self.assertEqual(code, 1)
        self.assertTrue(err.startswith("refused: cannot read"))


if __name__ == "__main__":
    unittest.main()
