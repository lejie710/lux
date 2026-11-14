"""Comparing recordings, and checking a comparison against a prediction."""
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from recorder import capture, compare, eventlog, experiments, gate, prediction, recording
from recorder.errors import ComparisonRefused, FormatError, PredictionMissing
from recorder.tests import helpers
from recorder.tests.helpers import FakeGit

BOOT_ORDER = experiments.get("boot-order")
SIGNATURE_BYTE = experiments.get("signature-byte")


def recording_from_fixture(tag: str, name: str, recorded_at: str = "2026-01-01T00:00:00Z") -> dict:
    """A recording document built from one of the real fixture boots."""
    raw = helpers.fixture_bytes(f"{tag}-eventlog.bin")
    events = eventlog.parse_event_log(raw).events
    lines = capture.clean_console(helpers.fixture_bytes(f"{tag}-serial.log"))
    console, loader_report = capture.split_console(lines)
    experiment = experiments.get(tag)
    facts = recording.RunFacts(
        name=name, experiment=tag, experiment_sha256=experiments.fingerprint(experiment),
        kind=experiment.kind, change=experiment.change, change_detail=None,
        provenance={"recorded_at": recorded_at, "tools": {"qemu": "1"}, "prediction": None},
        outcome={"result": capture.classify_outcome(lines),
                 "refusal_lines": capture.refusal_lines(lines), "trigger": "x", "ending": "y"},
        timing={"seconds_to_trigger": 5.0, "seconds_to_pause": 8.0},
        console=console, loader_report=loader_report, events=events, pcrs=helpers.live_banks(tag),
        event_log_bytes=raw, vars_after_sha256="aa", gate={"passed": True},
    )
    return recording.build_recording(facts)


class CompareRecordings(unittest.TestCase):
    def setUp(self) -> None:
        self.normal = recording_from_fixture("normal", "normal-1")
        self.refused = recording_from_fixture("e2", "e2")

    def _compare(self, baseline: dict, changed: dict) -> dict:
        return compare.compare_recordings(baseline, changed, "hash-a", "hash-b")

    def test_recordings_differing_only_in_may_vary_fields_are_identical(self) -> None:
        other = copy.deepcopy(self.normal)
        other["run"]["name"] = "normal-2"
        other["provenance"]["recorded_at"] = "2027-05-05T05:05:05Z"
        other["timing"] = {"seconds_to_trigger": 9.9, "seconds_to_pause": 19.9}
        result = self._compare(self.normal, other)
        self.assertTrue(result["identical"])
        self.assertIsNone(result["first_differing_event"])
        self.assertIsNone(result["console_first_differing_line"])
        self.assertEqual(result["other_fields_differing"], [])
        self.assertEqual(result["events_only_in_baseline"], [])
        self.assertEqual(result["pcrs_differing"]["sha256"], [])
        self.assertEqual(result["pcrs_same"]["sha512"], list(range(24)))
        self.assertEqual(result["baseline"], {"run": "normal-1", "experiment": "normal",
                                              "kind": "normal", "recording_sha256": "hash-a"})
        self.assertIsNone(result["loader_report_first_differing_line"])

    def test_any_other_single_field_change_is_reported(self) -> None:
        changes = {
            "vars_after_sha256": lambda d: d.__setitem__("vars_after_sha256", "bb"),
            "provenance.tools.qemu": lambda d: d["provenance"]["tools"].__setitem__("qemu", "2"),
            "event_log.sha256": lambda d: d["event_log"].__setitem__("sha256", "00"),
            "gate.passed": lambda d: d["gate"].__setitem__("passed", False),
            "outcome.trigger": lambda d: d["outcome"].__setitem__("trigger", "z"),
            "format": lambda d: d.__setitem__("format", "other"),
        }
        for path, change in changes.items():
            other = copy.deepcopy(self.normal)
            change(other)
            result = self._compare(self.normal, other)
            self.assertFalse(result["identical"], path)
            self.assertEqual(result["other_fields_differing"], [path])

    def test_which_experiment_a_run_is_goes_into_the_header_not_the_differences(self) -> None:
        other = copy.deepcopy(self.normal)
        other["run"].update(experiment="e4", kind="pilot", change="x", experiment_sha256="ff",
                            change_detail={"store_edits": ["secure-boot-off"]})
        result = self._compare(self.normal, other)
        self.assertEqual(result["other_fields_differing"], [])
        self.assertEqual((result["changed"]["experiment"], result["changed"]["kind"]), ("e4", "pilot"))

    def test_a_changed_loader_report_line_is_reported(self) -> None:
        other = copy.deepcopy(self.normal)
        other["loader_report"][3] = "LUX MM moved"
        result = self._compare(self.normal, other)
        self.assertFalse(result["identical"])
        self.assertEqual(result["loader_report_first_differing_line"], 4)
        self.assertIsNone(result["console_first_differing_line"])

    def test_a_refusal_before_an_accepted_boot_is_not_identical_to_a_clean_boot(self) -> None:
        other = copy.deepcopy(self.normal)
        other["outcome"]["refusal_lines"] = ["BdsDxe: failed to load Boot0002: Access Denied"]
        result = self._compare(self.normal, other)
        self.assertEqual(result["outcome"], {"baseline": "accepted", "changed": "accepted"})
        self.assertEqual(result["refusal_lines"]["baseline"], [])
        self.assertEqual(len(result["refusal_lines"]["changed"]), 1)
        self.assertFalse(result["identical"])

    def test_one_changed_register_value_is_reported_in_its_bank_only(self) -> None:
        other = copy.deepcopy(self.normal)
        other["pcrs"]["sha384"]["9"] = "11" * 48
        result = self._compare(self.normal, other)
        self.assertFalse(result["identical"])
        self.assertEqual(result["pcrs_differing"],
                         {"sha1": [], "sha256": [], "sha384": [9], "sha512": []})
        self.assertNotIn(9, result["pcrs_same"]["sha384"])

    def test_a_missing_register_counts_as_differing(self) -> None:
        other = copy.deepcopy(self.normal)
        del other["pcrs"]["sha256"]["3"]
        self.assertEqual(self._compare(self.normal, other)["pcrs_differing"]["sha256"], [3])
        self.assertEqual(self._compare(other, self.normal)["pcrs_differing"]["sha256"], [3])

    def test_changed_console_line_and_outcome_are_reported(self) -> None:
        other = copy.deepcopy(self.normal)
        other["console"][4] = "different"
        other["outcome"]["result"] = "timeout"
        result = self._compare(self.normal, other)
        self.assertEqual(result["console_first_differing_line"], 5)
        self.assertEqual(result["outcome"], {"baseline": "accepted", "changed": "timeout"})
        self.assertFalse(result["identical"])

    def test_a_field_hidden_in_may_vary_is_reported(self) -> None:
        for document in (copy.deepcopy(self.normal), copy.deepcopy(self.normal)):
            document["may_vary"] = list(recording.MAY_VARY) + ["pcrs"]
            result = self._compare(document, copy.deepcopy(document))
            self.assertFalse(result["identical"])
            self.assertEqual(result["other_fields_differing"], ["may_vary"])

    def test_refused_boot_against_normal_boot(self) -> None:
        result = self._compare(self.normal, self.refused)
        self.assertFalse(result["identical"])
        self.assertEqual(result["outcome"], {"baseline": "accepted", "changed": "refused"})
        for bank in ("sha1", "sha256", "sha384", "sha512"):
            self.assertEqual(result["pcrs_differing"][bank], [4, 5, 7])
        first = result["first_differing_event"]
        self.assertEqual((first["index"], first["stop"]), (25, 6))
        self.assertEqual(first["baseline"]["type"], "EV_EFI_VARIABLE_AUTHORITY")
        self.assertEqual(first["changed"]["type"], "EV_EFI_ACTION")
        self.assertEqual([e["index"] for e in result["events_only_in_baseline"]], [25, 26, 27, 28])
        self.assertEqual([(e["index"], e["pcr"]) for e in result["events_only_in_changed"]], [(25, 4), (26, 4)])
        self.assertEqual(result["console_first_differing_line"], 2)
        self.assertEqual(result["loader_report_first_differing_line"], 1)
        self.assertEqual(len(result["refusal_lines"]["changed"]), 1)

    def test_repeated_events_are_paired_one_by_one(self) -> None:
        row = {"index": 1, "pcr": 4, "type": "T", "digest_sha256": "aa", "stop": 5}
        twice = [row, {**row, "index": 2}]
        self.assertEqual(compare.events_only_in(twice, [row]),
                         [{"index": 2, "pcr": 4, "type": "T", "digest_sha256": "aa"}])
        self.assertEqual(compare.events_only_in([row], twice), [])

    def test_a_shorter_event_list_differs_at_its_end(self) -> None:
        shorter = copy.deepcopy(self.normal)
        shorter["events"] = shorter["events"][:-1]
        first = self._compare(self.normal, shorter)["first_differing_event"]
        self.assertEqual(first["index"], 28)
        self.assertIsNone(first["changed"])
        self.assertEqual(first["stop"], 7)


class ComparableAndRepeat(unittest.TestCase):
    """Pairs that must not be compared, and what counts as the repeat precondition."""

    def setUp(self) -> None:
        self.first = recording_from_fixture("normal", "normal-1")
        self.second = recording_from_fixture("normal", "normal-2", "2026-01-01T00:01:00Z")
        self.refused = recording_from_fixture("e2", "e2", "2026-01-01T00:02:00Z")

    def test_two_boots_of_the_normal_run_are_comparable(self) -> None:
        compare.require_comparable(self.first, self.second, "a", "b")
        compare.require_comparable(self.first, self.refused, "a", "c")

    def test_a_recording_is_not_compared_with_itself(self) -> None:
        with self.assertRaises(ComparisonRefused):
            compare.require_comparable(self.first, self.first, "a", "a")

    def test_a_renamed_copy_is_not_a_second_boot(self) -> None:
        renamed = copy.deepcopy(self.first)
        renamed["run"]["name"] = "normal-2"
        self.assertTrue(compare.compare_recordings(self.first, renamed, "a", "b")["identical"])
        with self.assertRaises(ComparisonRefused):
            compare.require_comparable(self.first, renamed, "a", "b")

    def test_a_recording_that_failed_its_gate_is_not_compared(self) -> None:
        for broken in (self.first, self.second):
            original = broken["gate"]["passed"]
            for value in (False, None, "yes"):
                broken["gate"]["passed"] = value
                with self.assertRaises(ComparisonRefused):
                    compare.require_comparable(self.first, self.second, "a", "b")
            broken["gate"]["passed"] = original

    def test_the_baseline_must_be_a_normal_run(self) -> None:
        with self.assertRaises(ComparisonRefused):
            compare.require_comparable(self.refused, self.second, "c", "b")

    def test_repeat_precondition_holds_for_two_identical_normal_runs(self) -> None:
        repeat = compare.compare_recordings(self.first, self.second, "a", "b")
        compare.require_repeat(repeat, "a")

    def test_repeat_precondition_refusals(self) -> None:
        good = compare.compare_recordings(self.first, self.second, "a", "b")
        not_identical = {**good, "identical": False}
        with_itself = compare.compare_recordings(self.first, self.second, "a", "a")
        against_pilot = compare.compare_recordings(self.first, self.refused, "a", "c")
        for repeat, baseline in ((not_identical, "a"), (with_itself, "a"), (against_pilot, "a"),
                                 (good, "another-baseline")):
            with self.assertRaises(ComparisonRefused):
                compare.require_repeat(repeat, baseline)


PREDICTION = {
    "format": "lux-prediction/1", "experiment": "boot-order", "written": "2026-11-20",
    "change": "BootOrder lists its entries in reverse",
    "rows": [
        {"id": "continues", "field": "outcome.changed", "expect": "accepted", "basis": "uefi-required",
         "citation": {"document": "UEFI Specification", "version": "2.11",
                      "section": "3 Boot Manager", "page": 152}},
        {"id": "pcr1", "field": "pcrs_differing.sha256", "expect_contains": [1],
         "basis": "tcg-unread", "citation": None, "reason": "seen in the normal run on this firmware"},
        {"id": "pcr0", "field": "pcrs_differing.sha256", "expect_excludes": [0],
         "basis": "this-firmware", "citation": None, "source": "recordings/normal-1/recording.json"},
        {"id": "order-kept", "field": "identical", "expect": False, "basis": "uefi-platform",
         "citation": {"document": "UEFI Specification", "version": "2.11",
                      "section": "3 Boot Manager", "page": 152}},
    ],
}


class ValidatePrediction(unittest.TestCase):
    def test_the_example_is_valid(self) -> None:
        self.assertEqual(prediction.validate(copy.deepcopy(PREDICTION)), PREDICTION)

    def _broken(self, change) -> dict:
        document = copy.deepcopy(PREDICTION)
        change(document)
        return document

    def test_label_and_citation_must_fit(self) -> None:
        broken = [
            lambda d: d["rows"][0].__setitem__("citation", None),                # required, no citation
            lambda d: d["rows"][0]["citation"].pop("page"),                      # citation without page
            lambda d: d["rows"][0]["citation"].__setitem__("page", "152"),       # page not a number
            lambda d: d["rows"][0]["citation"].__setitem__("section", " "),      # empty section title
            lambda d: d["rows"][3].pop("citation"),                              # platform, no citation
            lambda d: d["rows"][1].__setitem__("citation", {"document": "x"}),   # unread, yet cited
            lambda d: d["rows"][1].pop("reason"),                                # unread, no reason
            lambda d: d["rows"][2].pop("source"),                                # firmware, no source
            lambda d: d["rows"][2].__setitem__("basis", "my-guess"),             # unknown label
        ]
        for change in broken:
            with self.assertRaises(FormatError):
                prediction.validate(self._broken(change))

    def test_structure_is_checked(self) -> None:
        broken = [
            lambda d: d.__setitem__("format", "lux-prediction/0"),
            lambda d: d.__setitem__("rows", []),
            lambda d: d.pop("written"),
            lambda d: d["rows"][0].pop("field"),
            lambda d: d["rows"][0].pop("expect"),
            lambda d: d["rows"][0].__setitem__("expect_contains", [1]),          # two expectations
            lambda d: d["rows"][1].__setitem__("id", "continues"),               # duplicate id
            lambda d: d.__setitem__("parameters", [64]),                         # not an object
            lambda d: d.__setitem__("parameters", {"signature_area_offset": "64"}),
            lambda d: d.__setitem__("parameters", {"signature_area_offset": -1}),
            lambda d: d.__setitem__("parameters", {"signature_area_offset": True}),
            lambda d: d.__setitem__("parameters", {"firmware_sha256": "ABC"}),
        ]
        for change in broken:
            with self.assertRaises(FormatError):
                prediction.validate(self._broken(change))

    def test_parameters_are_accepted_when_well_formed(self) -> None:
        document = self._broken(lambda d: d.__setitem__(
            "parameters", {"signature_area_offset": 64, "firmware_sha256": "ab" * 32}))
        self.assertEqual(prediction.validate(document)["parameters"]["signature_area_offset"], 64)


class ScorePrediction(unittest.TestCase):
    COMPARISON = {"identical": False, "outcome": {"baseline": "accepted", "changed": "accepted"},
                  "pcrs_differing": {"sha256": [1]}}

    def test_all_rows_hold(self) -> None:
        result = prediction.score(PREDICTION, self.COMPARISON)
        self.assertEqual((result["required_met"], result["required_total"]), (1, 1))
        self.assertEqual((result["open_correct"], result["open_total"]), (3, 3))
        self.assertEqual(result["mismatches"], [])

    def test_mismatches_are_counted_and_named_per_kind(self) -> None:
        comparison = {"identical": False, "outcome": {"changed": "refused"},
                      "pcrs_differing": {"sha256": [0, 4]}}
        result = prediction.score(PREDICTION, comparison)
        self.assertEqual((result["required_met"], result["required_total"]), (0, 1))
        self.assertEqual((result["open_correct"], result["open_total"]), (1, 3))
        self.assertEqual(result["mismatches"], ["continues", "pcr1", "pcr0"])

    def test_a_field_the_comparison_lacks_is_an_error_not_a_pass(self) -> None:
        with self.assertRaises(FormatError):
            prediction.score(PREDICTION, {"identical": False})
        row = {"id": "x", "field": "identical", "expect_contains": [1]}
        with self.assertRaises(FormatError):
            prediction.row_holds(row, {"identical": False})


def signature_prediction(**parameters: object) -> dict:
    """A valid prediction for the signature-byte experiment with the given parameters."""
    document = copy.deepcopy(PREDICTION)
    document.update(experiment="signature-byte", change=SIGNATURE_BYTE.change, parameters=parameters)
    return document


class PredictionGate(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.file = self.directory / "boot-order.json"
        self.file.write_bytes(json.dumps(PREDICTION).encode())

    def test_committed_prediction_is_accepted_with_its_hash_and_commit(self) -> None:
        reference = prediction.require_committed(BOOT_ORDER, self.directory, FakeGit())
        self.assertEqual(reference.path, "predictions/boot-order.json")
        self.assertEqual(reference.sha256, recording.sha256_of_file(self.file))
        self.assertEqual(reference.commit, "abc123")
        self.assertEqual(reference.parameters, {})

    def test_missing_file_refuses_without_asking_git(self) -> None:
        git = FakeGit()
        with self.assertRaises(PredictionMissing):
            prediction.require_committed(SIGNATURE_BYTE, self.directory, git)
        self.assertEqual(git.asked, [])

    def test_untracked_modified_or_unknown_commit_refuses(self) -> None:
        for git in (FakeGit(tracked=False), FakeGit(status=" M boot-order.json\n"),
                    FakeGit(commit=""), FakeGit(code=128), FakeGit(ancestor=False)):
            with self.assertRaises(PredictionMissing):
                prediction.require_committed(BOOT_ORDER, self.directory, git)

    def test_a_file_that_differs_from_the_committed_bytes_refuses(self) -> None:
        """Git says "unchanged", but the committed content is another: the edit is caught."""
        git = FakeGit(blob=json.dumps({**PREDICTION, "written": "2026-11-19"}).encode())
        with self.assertRaises(PredictionMissing) as caught:
            prediction.require_committed(BOOT_ORDER, self.directory, git)
        self.assertIn("differs from the committed one", str(caught.exception))

    def test_git_that_cannot_run_means_no(self) -> None:
        def broken_git(arguments: list[str], directory: Path) -> tuple[int, bytes]:
            return prediction.run_git(arguments, directory / "does-not-exist")
        with self.assertRaises(PredictionMissing):
            prediction.require_committed(BOOT_ORDER, self.directory, broken_git)

    def test_invalid_or_misnamed_prediction_refuses(self) -> None:
        self.file.write_text("{not json")
        with self.assertRaises(PredictionMissing):
            prediction.require_committed(BOOT_ORDER, self.directory, FakeGit())
        other = self.directory / "signature-byte.json"
        other.write_bytes(json.dumps(PREDICTION).encode())       # names boot-order inside
        with self.assertRaises(PredictionMissing):
            prediction.require_committed(SIGNATURE_BYTE, self.directory, FakeGit())

    def test_a_prediction_of_another_change_refuses(self) -> None:
        self.file.write_bytes(json.dumps({**PREDICTION, "change": "BootOrder is emptied"}).encode())
        with self.assertRaises(PredictionMissing) as caught:
            prediction.require_committed(BOOT_ORDER, self.directory, FakeGit())
        self.assertIn("another change", str(caught.exception))

    def test_parameters_must_be_exactly_the_ones_the_experiment_needs(self) -> None:
        file = self.directory / "signature-byte.json"
        for parameters in ({}, {"firmware_sha256": "ab" * 32},
                           {"signature_area_offset": 64, "firmware_sha256": "ab" * 32}):
            file.write_bytes(json.dumps(signature_prediction(**parameters)).encode())
            with self.assertRaises(PredictionMissing):
                prediction.require_committed(SIGNATURE_BYTE, self.directory, FakeGit())
        file.write_bytes(json.dumps(signature_prediction(signature_area_offset=64)).encode())
        reference = prediction.require_committed(SIGNATURE_BYTE, self.directory, FakeGit())
        self.assertEqual(reference.parameters, {"signature_area_offset": 64})
        self.assertEqual(reference.as_document()["parameters"], {"signature_area_offset": 64})
        self.file.write_bytes(json.dumps({**PREDICTION, "parameters": {"signature_area_offset": 1}}).encode())
        with self.assertRaises(PredictionMissing):
            prediction.require_committed(BOOT_ORDER, self.directory, FakeGit())

    def test_edit_after_the_run_is_detected(self) -> None:
        reference = prediction.require_committed(BOOT_ORDER, self.directory, FakeGit())
        made = {"provenance": {"prediction": reference.as_document()}}
        self.assertTrue(prediction.unchanged_since_run(made, self.file))
        self.file.write_bytes(self.file.read_bytes() + b" ")
        self.assertFalse(prediction.unchanged_since_run(made, self.file))
        self.assertFalse(prediction.unchanged_since_run({"provenance": {"prediction": None}}, self.file))


@unittest.skipUnless(shutil.which("git"), "git is not installed")
class PredictionGateWithRealGit(unittest.TestCase):
    """The gate against a real, temporary git repository. No fake answers here."""

    def setUp(self) -> None:
        self.repository = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, self.repository, ignore_errors=True)
        self.predictions = self.repository / "predictions"
        self.predictions.mkdir()
        self.file = self.predictions / "boot-order.json"
        self._git("init", "--quiet")
        (self.repository / "README").write_text("test repository\n")
        self._git("add", "README")
        self._commit("first")

    def _git(self, *arguments: str) -> str:
        done = subprocess.run(
            ["git", "-c", "user.name=Test", "-c", "user.email=test@example.invalid",
             "-c", "core.autocrlf=false", "-c", "commit.gpgsign=false", *arguments],
            cwd=self.repository, capture_output=True, text=True, check=True)
        return done.stdout

    def _commit(self, message: str) -> None:
        self._git("commit", "--quiet", "--no-verify", "-m", message)

    def _write(self, **changes: object) -> None:
        self.file.write_bytes(json.dumps({**PREDICTION, **changes}).encode())

    def _refused(self) -> str:
        with self.assertRaises(PredictionMissing) as caught:
            prediction.require_committed(BOOT_ORDER, self.predictions)
        return str(caught.exception)

    def test_untracked_then_staged_then_committed_then_modified(self) -> None:
        self._write()
        self.assertIn("not committed", self._refused())                 # untracked
        self._git("add", "predictions/boot-order.json")
        self.assertIn("not committed", self._refused())                 # staged only
        self._commit("add the prediction")
        reference = prediction.require_committed(BOOT_ORDER, self.predictions)
        self.assertEqual(reference.path, "predictions/boot-order.json")
        self.assertEqual(reference.sha256, recording.sha256_of_file(self.file))
        self.assertEqual(reference.commit, self._git("rev-parse", "HEAD").strip())
        self._write(written="2026-11-21")
        self.assertIn("not committed", self._refused())                 # modified

    def test_an_edit_hidden_from_git_status_is_still_refused(self) -> None:
        """`assume-unchanged` makes git report a clean file; the committed bytes do not lie."""
        self._write()
        self._git("add", "predictions/boot-order.json")
        self._commit("add the prediction")
        self._git("update-index", "--assume-unchanged", "predictions/boot-order.json")
        self._write(written="2026-11-21")
        self.assertEqual(self._git("status", "--porcelain").strip(), "")
        self.assertIn("differs from the committed one", self._refused())

    def test_a_later_commit_of_the_file_is_the_one_named(self) -> None:
        self._write()
        self._git("add", "predictions/boot-order.json")
        self._commit("add the prediction")
        first = self._git("rev-parse", "HEAD").strip()
        self._write(written="2026-11-22")
        self._git("add", "predictions/boot-order.json")
        self._commit("revise the prediction before the run")
        reference = prediction.require_committed(BOOT_ORDER, self.predictions)
        self.assertNotEqual(reference.commit, first)
        self.assertEqual(reference.sha256, recording.sha256_of_file(self.file))


class DeterministicWriting(unittest.TestCase):
    def test_same_document_gives_the_same_bytes_with_lf_and_sorted_keys(self) -> None:
        text = recording.dumps({"b": 1, "a": {"d": "x", "c": [2, 1]}})
        self.assertEqual(text, '{\n  "a": {\n    "c": [\n      2,\n      1\n    ],\n    "d": "x"\n  },\n  "b": 1\n}\n')

    def test_file_round_trip_and_format_check(self) -> None:
        directory = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
        document = recording_from_fixture("normal", "normal-1")
        path = directory / "deep" / "recording.json"
        recording.write_json(path, document)
        self.assertNotIn(b"\r", path.read_bytes())
        self.assertEqual(recording.load_json(path, recording.RECORDING_FORMAT), document)
        with self.assertRaises(FormatError):
            recording.load_json(path, compare.COMPARISON_FORMAT)
        with self.assertRaises(FormatError):
            recording.load_json(directory / "missing.json", recording.RECORDING_FORMAT)

    def test_recording_shape(self) -> None:
        document = recording_from_fixture("normal", "normal-1")
        self.assertEqual(document["format"], "lux-recording/1")
        self.assertEqual(len(document["console"]), 10)
        self.assertEqual(len(document["loader_report"]), 148)
        self.assertTrue(all(line.startswith(("LUX MM ", "LUX CFG ")) for line in document["loader_report"]))
        self.assertEqual(document["console"][-1], "LUX-FINAL-MARKER loader idle after ExitBootServices")
        self.assertEqual(set(document["run"]), {"name", "experiment", "experiment_sha256", "kind",
                                                "change", "change_detail"})
        self.assertEqual(document["event_log"], {
            "sha256": "d5bb1bd8dd779d329039b12d3d09885fa5ad901f53f037d6d25efa4082205536",
            "bytes": 9657, "events": 28})
        self.assertEqual(document["may_vary"], sorted(document["may_vary"]))
        first = document["events"][0]
        self.assertEqual(first, {
            "index": 1, "pcr": 0, "type": "EV_S_CRTM_VERSION", "type_code": "0x00000008",
            "digest_sha256": "d60c3bd4dfdf42a8f4f54c44a8d9f2ddb835990b97a836d8e9b77f317d2f40ea",
            "summary": "firmware version string 2024.02-2ubuntu0.10",
            "stop": 3, "stop_rule": "pcr0-firmware"})
        self.assertEqual(document["pcrs"]["sha256"]["7"],
                         "abff6d6bc78d92bac155169c929608f59e424c7739690a722b7d243da0b1613d")
        self.assertEqual(gate.replay_events(eventlog.parse_event_log(
            helpers.fixture_bytes("normal-eventlog.bin")).events)["sha256"][7].hex(),
            document["pcrs"]["sha256"]["7"])


if __name__ == "__main__":
    unittest.main()
