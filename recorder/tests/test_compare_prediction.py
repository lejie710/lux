"""Comparing recordings, and checking a comparison against a prediction."""
import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from recorder import capture, compare, eventlog, gate, prediction, recording
from recorder.errors import FormatError, PredictionMissing
from recorder.tests import helpers


def recording_from_fixture(tag: str, name: str) -> dict:
    """A recording document built from one of the real fixture boots."""
    raw = helpers.fixture_bytes(f"{tag}-eventlog.bin")
    events = eventlog.parse_event_log(raw).events
    console = capture.clean_console(helpers.fixture_bytes(f"{tag}-serial.log"))
    facts = recording.RunFacts(
        name=name, experiment=tag, kind="normal" if tag == "normal" else "pilot", change="none",
        provenance={"recorded_at": "2026-01-01T00:00:00Z", "tools": {"qemu": "1"}, "prediction": None},
        outcome={"result": capture.classify_outcome(console), "trigger": "x", "ending": "y"},
        timing={"seconds_to_trigger": 5.0, "seconds_to_pause": 8.0},
        console=console, events=events, pcrs=helpers.live_banks(tag), event_log_bytes=raw,
        vars_after_sha256="aa", gate={"passed": True},
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
        self.assertEqual(result["baseline"], {"run": "normal-1", "recording_sha256": "hash-a"})

    def test_any_other_single_field_change_is_reported(self) -> None:
        changes = {
            "vars_after_sha256": lambda d: d.__setitem__("vars_after_sha256", "bb"),
            "provenance.tools.qemu": lambda d: d["provenance"]["tools"].__setitem__("qemu", "2"),
            "event_log.sha256": lambda d: d["event_log"].__setitem__("sha256", "00"),
            "gate.passed": lambda d: d["gate"].__setitem__("passed", False),
            "outcome.trigger": lambda d: d["outcome"].__setitem__("trigger", "z"),
            "run.experiment": lambda d: d["run"].__setitem__("experiment", "e9"),
            "format": lambda d: d.__setitem__("format", "other"),
        }
        for path, change in changes.items():
            other = copy.deepcopy(self.normal)
            change(other)
            result = self._compare(self.normal, other)
            self.assertFalse(result["identical"], path)
            self.assertEqual(result["other_fields_differing"], [path])

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
        ]
        for change in broken:
            with self.assertRaises(FormatError):
                prediction.validate(self._broken(change))


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


class FakeGit:
    """Answers the three git questions from a small table."""

    def __init__(self, tracked: bool = True, status: str = "", commit: str = "abc123\n",
                 code: int = 0) -> None:
        self.tracked, self.status, self.commit, self.code = tracked, status, commit, code
        self.asked: list[str] = []

    def __call__(self, arguments: list[str], directory: Path) -> tuple[int, str]:
        self.asked.append(arguments[0])
        if self.code:
            return self.code, ""
        if arguments[0] == "ls-files":
            return (0 if self.tracked else 1), ""
        if arguments[0] == "status":
            return 0, self.status
        return 0, self.commit


class PredictionGate(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, self.directory, ignore_errors=True)
        self.file = self.directory / "boot-order.json"
        self.file.write_bytes(json.dumps(PREDICTION).encode())

    def test_committed_prediction_is_accepted_with_its_hash_and_commit(self) -> None:
        reference = prediction.require_committed("boot-order", self.directory, FakeGit())
        self.assertEqual(reference.path, "predictions/boot-order.json")
        self.assertEqual(reference.sha256, recording.sha256_of_file(self.file))
        self.assertEqual(reference.commit, "abc123")

    def test_missing_file_refuses_without_asking_git(self) -> None:
        git = FakeGit()
        with self.assertRaises(PredictionMissing):
            prediction.require_committed("signature-byte", self.directory, git)
        self.assertEqual(git.asked, [])

    def test_untracked_modified_or_unknown_commit_refuses(self) -> None:
        for git in (FakeGit(tracked=False), FakeGit(status=" M boot-order.json\n"),
                    FakeGit(commit=""), FakeGit(code=128)):
            with self.assertRaises(PredictionMissing):
                prediction.require_committed("boot-order", self.directory, git)

    def test_git_that_cannot_run_means_no(self) -> None:
        def broken_git(arguments: list[str], directory: Path) -> tuple[int, str]:
            return prediction.run_git(arguments, directory / "does-not-exist")
        with self.assertRaises(PredictionMissing):
            prediction.require_committed("boot-order", self.directory, broken_git)

    def test_invalid_or_misnamed_prediction_refuses(self) -> None:
        self.file.write_text("{not json")
        with self.assertRaises(PredictionMissing):
            prediction.require_committed("boot-order", self.directory, FakeGit())
        other = self.directory / "signature-byte.json"
        other.write_bytes(json.dumps(PREDICTION).encode())       # names boot-order inside
        with self.assertRaises(PredictionMissing):
            prediction.require_committed("signature-byte", self.directory, FakeGit())

    def test_edit_after_the_run_is_detected(self) -> None:
        reference = prediction.require_committed("boot-order", self.directory, FakeGit())
        made = {"provenance": {"prediction": reference.as_document()}}
        self.assertTrue(prediction.unchanged_since_run(made, self.file))
        self.file.write_bytes(self.file.read_bytes() + b" ")
        self.assertFalse(prediction.unchanged_since_run(made, self.file))
        self.assertFalse(prediction.unchanged_since_run({"provenance": {"prediction": None}}, self.file))


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
