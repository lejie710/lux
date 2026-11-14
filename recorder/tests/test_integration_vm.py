"""Integration test: boot the real virtual machine. Skipped unless asked for.

Run it with `LUX_VM_TESTS=1` on a machine where `python3 -m recorder prepare`
has succeeded. It boots the normal run twice and the normal run with two
boot entries once (about ten seconds each); it never runs a changed boot.
"""
import os
import shutil
import subprocess
import unittest
from pathlib import Path

from recorder import cli, compare, prediction, provenance, recording, runner
from recorder.session import Limits, QemuMachine, SystemClock
from recorder.tests import helpers

VM_TESTS_WANTED = os.environ.get("LUX_VM_TESTS") == "1"
VM_AVAILABLE = shutil.which("qemu-system-x86_64") is not None and shutil.which("swtpm") is not None


def _environment() -> runner.Environment:
    """The real machine, in the prepared work directory."""
    return runner.Environment(
        testkeys_directory=helpers.TESTKEYS,
        predictions_directory=helpers.REPOSITORY / "predictions",
        work_directory=cli.default_work_directory(), machine_factory=QemuMachine,
        clock=SystemClock(), limits=Limits(),
        tool_versions=provenance.tool_versions, host_os=provenance.host_os(), git=prediction.run_git,
        require_repeat=lambda: None)              # only counted runs ask, and none is run here


@unittest.skipUnless(VM_TESTS_WANTED, "set LUX_VM_TESTS=1 to boot the virtual machine")
@unittest.skipUnless(VM_AVAILABLE, "QEMU and swtpm are not installed")
class TwoEntryNormalRunRepeats(unittest.TestCase):
    """The normal run with two boot entries, in the original order. Not a changed boot."""

    def test_a_fresh_run_equals_the_committed_two_entry_normal_recording(self) -> None:
        fresh = runner.record_run(
            runner.RunRequest("it-normal-two", "normal-two-same", "fresh"), _environment()).document
        committed = recording.load_json(
            helpers.REPOSITORY / "recordings" / "normal-two-same-1" / "recording.json",
            recording.RECORDING_FORMAT)
        result = compare.compare_recordings(committed, fresh, "committed", "fresh")
        self.assertTrue(result["identical"], result)
        self.assertIsNone(fresh["run"]["change_detail"])
        self.assertEqual(fresh["provenance"]["boot_order"][:2], ["Boot0002", "Boot0003"])


@unittest.skipUnless(VM_TESTS_WANTED, "set LUX_VM_TESTS=1 to boot the virtual machine")
@unittest.skipUnless(VM_AVAILABLE, "QEMU and swtpm are not installed")
class NormalRunRepeats(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        env = _environment()
        work = env.work_directory
        cls.work = work
        cls.first = runner.record_run(runner.RunRequest("it-normal-1", "normal", "first"), env).document
        cls.second = runner.record_run(runner.RunRequest("it-normal-2", "normal", "second"), env).document

    def test_three_way_gate_passes_in_both_runs(self) -> None:
        for document in (self.first, self.second):
            self.assertTrue(document["gate"]["passed"])
            self.assertEqual(set(document["gate"]["checks"].values()), {True})
            self.assertEqual(document["gate"]["counts"]["log_candidates_parsed"], 1)
            self.assertEqual(document["outcome"]["result"], "accepted")
            self.assertIs(document["outcome"]["settled"], True)

    def test_two_normal_runs_are_equal_on_every_compared_field(self) -> None:
        result = compare.compare_recordings(self.first, self.second, "first", "second")
        self.assertTrue(result["identical"], result)
        self.assertEqual(result["other_fields_differing"], [])

    def test_a_fresh_run_equals_the_committed_normal_recording(self) -> None:
        committed = recording.load_json(
            helpers.REPOSITORY / "recordings" / "normal-1" / "recording.json", recording.RECORDING_FORMAT)
        result = compare.compare_recordings(committed, self.first, "committed", "fresh")
        self.assertTrue(result["identical"], result)

    def test_nothing_is_left_behind(self) -> None:
        self.assertEqual(list(Path(self.work).rglob("mem.bin")), [])
        self.assertEqual(list(Path(self.work).rglob("*.sock")), [])

    def test_no_process_of_either_run_survives(self) -> None:
        for name in ("qemu-system-x86_64", "swtpm"):
            found = subprocess.run(["pgrep", "-x", name], capture_output=True, text=True, check=False)
            self.assertEqual(found.stdout.strip(), "", name)


if __name__ == "__main__":
    unittest.main()
