"""The recordings committed in the repository must keep what the site relies on."""
import hashlib
import json
import unittest

from recorder import compare, eventlog, gate, keys, recording
from recorder.banks import banks_from_hex
from recorder.tests import helpers

RECORDINGS = helpers.REPOSITORY / "recordings"


class CommittedRecordings(unittest.TestCase):
    """The recordings in the repository must keep the properties the site relies on."""

    def _load(self, run: str) -> dict:
        return recording.load_json(RECORDINGS / run / "recording.json", recording.RECORDING_FORMAT)

    def _compare(self, baseline: str, changed: str) -> dict:
        return compare.compare_recordings(
            self._load(baseline), self._load(changed),
            recording.sha256_of_file(RECORDINGS / baseline / "recording.json"),
            recording.sha256_of_file(RECORDINGS / changed / "recording.json"))

    def test_the_two_normal_runs_are_identical(self) -> None:
        result = self._compare("normal-1", "normal-2")
        self.assertTrue(result["identical"], result["other_fields_differing"])

    def test_the_pilot_differs_in_registers_4_5_and_7_only(self) -> None:
        result = self._compare("normal-1", "e2")
        self.assertEqual(result["outcome"], {"baseline": "accepted", "changed": "refused"})
        for bank, differing in result["pcrs_differing"].items():
            self.assertEqual(differing, [4, 5, 7], bank)
        self.assertEqual(result["first_differing_event"]["index"], 25)

    def test_committed_comparisons_equal_a_fresh_comparison(self) -> None:
        for baseline, changed in (("normal-1", "normal-2"), ("normal-1", "e2")):
            stored = recording.load_json(
                RECORDINGS / "comparisons" / f"{baseline}_vs_{changed}.json", compare.COMPARISON_FORMAT)
            self.assertEqual(stored, self._compare(baseline, changed))

    def test_each_recording_follows_from_its_own_event_log(self) -> None:
        for run, events in (("normal-1", 28), ("normal-2", 28), ("e2", 26)):
            document = self._load(run)
            raw = (RECORDINGS / run / "eventlog.bin").read_bytes()
            log = eventlog.parse_event_log(raw)
            self.assertEqual(len(log.events), events)
            self.assertEqual(document["event_log"]["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(gate.replay_events(log.events), banks_from_hex(document["pcrs"]))
            self.assertEqual(document["events"], [recording.event_row(event) for event in log.events])
            self.assertTrue(document["gate"]["passed"])
            self.assertEqual(document["may_vary"], list(recording.MAY_VARY))

    def test_every_event_has_a_stop(self) -> None:
        for run in ("normal-1", "normal-2", "e2"):
            for row in self._load(run)["events"]:
                self.assertIsNotNone(row["stop"], (run, row["index"]))

    def test_recordings_were_made_with_the_committed_keys_and_loader(self) -> None:
        manifest = keys.verify(helpers.TESTKEYS)
        fingerprints = keys.fingerprints(helpers.TESTKEYS)
        for run in ("normal-1", "normal-2", "e2"):
            provenance = self._load(run)["provenance"]
            self.assertEqual(provenance["keys"], fingerprints)
            self.assertEqual(provenance["vars_template_sha256"], manifest["vars_template_sha256"])
            self.assertIsNone(provenance["prediction"])
        self.assertEqual(self._load("normal-1")["provenance"]["loader"]["authenticode_sha256"],
                         manifest["loader_authenticode_sha256"])
        self.assertEqual(self._load("e2")["provenance"]["loader"]["authenticode_sha256"],
                         helpers.CHANGED_LOADER_AUTHENTICODE)

    def test_only_normal_and_pilot_runs_are_committed_without_a_prediction(self) -> None:
        for path in sorted(RECORDINGS.glob("*/recording.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            if document["run"]["kind"] == "counted":
                self.assertIsNotNone(document["provenance"]["prediction"], path.parent.name)

    def test_image_digest_is_measured_only_when_the_loader_is_accepted(self) -> None:
        normal = [row["digest_sha256"] for row in self._load("normal-1")["events"]]
        refused = [row["digest_sha256"] for row in self._load("e2")["events"]]
        self.assertEqual(normal.count(helpers.LOADER_AUTHENTICODE), 1)
        self.assertNotIn(helpers.LOADER_AUTHENTICODE, refused)
        self.assertNotIn(helpers.CHANGED_LOADER_AUTHENTICODE, refused)


if __name__ == "__main__":
    unittest.main()
