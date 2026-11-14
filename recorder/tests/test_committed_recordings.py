"""The recordings committed in the repository must keep what the site relies on."""
import hashlib
import json
import unittest

from recorder import compare, eventlog, gate, keys, recording
from recorder.banks import banks_from_hex
from recorder.tests import helpers

RECORDINGS = helpers.REPOSITORY / "recordings"
NORMAL_RUNS = ("normal-1", "normal-2")
PILOTS = ("e1", "e2", "e4", "e5")
ALL_RUNS = NORMAL_RUNS + PILOTS
# Every committed comparison: the repeat of the normal run, and each pilot against normal-1.
PAIRS = (("normal-1", "normal-2"),) + tuple(("normal-1", pilot) for pilot in PILOTS)
# Number of events each committed event log holds.
EVENT_COUNTS = {"normal-1": 28, "normal-2": 28, "e1": 27, "e2": 26, "e4": 27, "e5": 27}
AUTHORITY = "EV_EFI_VARIABLE_AUTHORITY"


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
        for baseline, changed in PAIRS:
            stored = recording.load_json(
                RECORDINGS / "comparisons" / f"{baseline}_vs_{changed}.json", compare.COMPARISON_FORMAT)
            self.assertEqual(stored, self._compare(baseline, changed))

    def test_each_recording_follows_from_its_own_event_log(self) -> None:
        for run, events in EVENT_COUNTS.items():
            document = self._load(run)
            raw = (RECORDINGS / run / "eventlog.bin").read_bytes()
            log = eventlog.parse_event_log(raw)
            self.assertEqual(len(log.events), events)
            self.assertEqual(document["event_log"]["sha256"], hashlib.sha256(raw).hexdigest())
            self.assertEqual(gate.replay_events(log.events), banks_from_hex(document["pcrs"]))
            self.assertEqual(document["events"], [recording.event_row(event) for event in log.events])
            self.assertTrue(document["gate"]["passed"])
            self.assertEqual(set(document["gate"]["checks"].values()), {True})
            self.assertIs(document["outcome"]["settled"], True)
            self.assertEqual(document["may_vary"], list(recording.MAY_VARY))

    def test_the_committed_pairs_may_be_compared_and_the_normal_run_repeats(self) -> None:
        for baseline, changed in PAIRS:
            compare.require_comparable(
                self._load(baseline), self._load(changed),
                recording.sha256_of_file(RECORDINGS / baseline / "recording.json"),
                recording.sha256_of_file(RECORDINGS / changed / "recording.json"))
        repeat = recording.load_json(
            RECORDINGS / "comparisons" / "normal-1_vs_normal-2.json", compare.COMPARISON_FORMAT)
        compare.require_repeat(repeat, recording.sha256_of_file(RECORDINGS / "normal-1" / "recording.json"))

    def test_the_pilot_recording_proves_which_byte_was_changed(self) -> None:
        self.assertIsNone(self._load("normal-1")["run"]["change_detail"])
        detail = self._load("e2")["run"]["change_detail"]
        self.assertEqual(detail["loader_byte"], {"file_offset": 0x85E, "old_value": 0x41,
                                                 "new_value": 0x42, "area": "section .data"})
        self.assertEqual((detail["store_edits"], detail["firmware_replaced"]), ([], False))

    def test_outcomes_and_story_lines(self) -> None:
        normal, refused = self._load("normal-1"), self._load("e2")
        self.assertEqual((normal["outcome"]["result"], normal["outcome"]["refusal_lines"]), ("accepted", []))
        self.assertEqual(refused["outcome"]["result"], "refused")
        self.assertEqual(len(refused["outcome"]["refusal_lines"]), 1)
        self.assertEqual((len(normal["console"]), len(normal["loader_report"])), (10, 148))
        self.assertEqual((len(refused["console"]), refused["loader_report"]), (4, []))
        self.assertEqual([row["stop"] for row in refused["events"]][-3:], [5, 6, 5])

    def test_recordings_name_only_the_tools_a_run_uses_and_the_pinned_firmware(self) -> None:
        pins = keys.pins_of(keys.verify(helpers.TESTKEYS))
        for run in ALL_RUNS:
            provenance = self._load(run)["provenance"]
            self.assertEqual(set(provenance["tools"]), {"qemu", "ovmf", "swtpm", "binutils", "python"})
            self.assertEqual(provenance["host_os"], "Ubuntu 24.04")
            self.assertEqual(provenance["firmware"], {"file": pins.firmware_file,
                                                      "sha256": pins.firmware_sha256})

    def test_every_event_has_a_stop(self) -> None:
        for run in ALL_RUNS:
            for row in self._load(run)["events"]:
                self.assertIsNotNone(row["stop"], (run, row["index"]))

    def test_recordings_were_made_with_the_committed_keys_and_loader(self) -> None:
        manifest = keys.verify(helpers.TESTKEYS)
        fingerprints = keys.fingerprints(helpers.TESTKEYS)
        for run in ALL_RUNS:
            provenance = self._load(run)["provenance"]
            self.assertEqual(provenance["keys"], fingerprints)
            self.assertEqual(provenance["vars_template_sha256"], manifest["vars_template_sha256"])
            self.assertIsNone(provenance["prediction"])
        self.assertEqual(self._load("normal-1")["provenance"]["loader"]["authenticode_sha256"],
                         manifest["loader_authenticode_sha256"])
        for run, loader in (("e1", helpers.CHANGED_LOADER_AUTHENTICODE),
                            ("e2", helpers.CHANGED_LOADER_AUTHENTICODE),
                            ("e4", helpers.LOADER_AUTHENTICODE), ("e5", helpers.LOADER_AUTHENTICODE)):
            self.assertEqual(self._load(run)["provenance"]["loader"]["authenticode_sha256"], loader, run)

    def test_every_committed_recording_is_listed_here(self) -> None:
        on_disk = {path.parent.name for path in RECORDINGS.glob("*/recording.json")}
        self.assertEqual(on_disk, set(ALL_RUNS))
        for run in PILOTS:
            self.assertEqual((self._load(run)["run"]["experiment"], self._load(run)["run"]["kind"]),
                             (run, "pilot"))

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


class OtherPilots(unittest.TestCase):
    """What the pilots e1, e4 and e5 were observed to do, pinned to the committed files.

    These are observations of one firmware build, not predictions and not scores.
    """

    def _load(self, run: str) -> dict:
        return recording.load_json(RECORDINGS / run / "recording.json", recording.RECORDING_FORMAT)

    def _comparison(self, run: str) -> dict:
        return recording.load_json(
            RECORDINGS / "comparisons" / f"normal-1_vs_{run}.json", compare.COMPARISON_FORMAT)

    def _types(self, run: str) -> list[str]:
        return [row["type"] for row in self._load(run)["events"]]

    def _digests(self, run: str) -> list[str]:
        return [row["digest_sha256"] for row in self._load(run)["events"]]

    def _assert_registers(self, run: str, expected: list[int]) -> None:
        for bank, differing in self._comparison(run)["pcrs_differing"].items():
            self.assertEqual(differing, expected, (run, bank))

    def test_e1_changed_loader_runs_with_secure_boot_off(self) -> None:
        result = self._comparison("e1")
        self.assertEqual(result["outcome"], {"baseline": "accepted", "changed": "accepted"})
        self._assert_registers("e1", [4, 7])
        self.assertEqual(result["first_differing_event"]["index"], 4)
        self.assertIn("LUX-LOADER B: started, boot services active", self._load("e1")["console"])
        # The changed loader's own digest is measured, the signed loader's is not.
        self.assertEqual(self._digests("e1").count(helpers.CHANGED_LOADER_AUTHENTICODE), 1)
        self.assertNotIn(helpers.LOADER_AUTHENTICODE, self._digests("e1"))
        self.assertNotIn(AUTHORITY, self._types("e1"))

    def test_e4_signed_loader_runs_and_only_register_7_differs(self) -> None:
        result = self._comparison("e4")
        self.assertEqual(result["outcome"], {"baseline": "accepted", "changed": "accepted"})
        self._assert_registers("e4", [7])
        self.assertEqual(result["first_differing_event"]["index"], 4)
        self.assertIn("LUX-LOADER A: started, boot services active", self._load("e4")["console"])
        self.assertEqual(self._digests("e4").count(helpers.LOADER_AUTHENTICODE), 1)
        # With the switch off this firmware logs no record of which key allowed the loader.
        self.assertNotIn(AUTHORITY, self._types("e4"))
        self.assertEqual(self._types("normal-1").count(AUTHORITY), 1)

    def test_e1_and_e4_differ_from_the_normal_run_in_the_same_first_event(self) -> None:
        first = [self._comparison(run)["first_differing_event"] for run in ("e1", "e4")]
        self.assertEqual(first[0], first[1])
        row = self._load("e4")["events"][3]
        self.assertEqual((row["index"], row["pcr"]), (4, 7))
        self.assertIn("SecureBoot", row["summary"])

    def test_e5_signed_loader_on_the_forbidden_list_is_refused(self) -> None:
        result = self._comparison("e5")
        self.assertEqual(result["outcome"], {"baseline": "accepted", "changed": "refused"})
        self._assert_registers("e5", [4, 5, 7])
        self.assertEqual(result["first_differing_event"]["index"], 8)
        refusal = self._load("e5")["outcome"]["refusal_lines"]
        self.assertEqual(len(refusal), 1)
        self.assertTrue(refusal[0].endswith("Access Denied"))
        self.assertEqual(self._load("e5")["loader_report"], [])
        self.assertNotIn(helpers.LOADER_AUTHENTICODE, self._digests("e5"))

    def test_e5_firmware_read_the_forbidden_list_written_into_the_store_file(self) -> None:
        normal, revoked = self._load("normal-1")["events"][7], self._load("e5")["events"][7]
        self.assertEqual(normal["summary"], "variable dbx, 0 data bytes")
        self.assertEqual(revoked["summary"], "variable dbx, 76 data bytes")
        # The measured list holds the signed loader's hash. No event of this run has that
        # hash as its digest, so the one place it appears in the raw log is the list.
        raw = (RECORDINGS / "e5" / "eventlog.bin").read_bytes()
        self.assertEqual(raw.count(bytes.fromhex(helpers.LOADER_AUTHENTICODE)), 1)

    def test_e5_logs_the_authority_record_although_the_loader_is_refused(self) -> None:
        # Unlike e2, where the changed loader matches no key and no such record is logged.
        authority = [row for row in self._load("normal-1")["events"] if row["type"] == AUTHORITY]
        in_e5 = [row for row in self._load("e5")["events"] if row["type"] == AUTHORITY]
        self.assertEqual([row["digest_sha256"] for row in in_e5],
                         [row["digest_sha256"] for row in authority])
        self.assertNotIn(AUTHORITY, self._types("e2"))
        self.assertEqual([row["stop"] for row in self._load("e5")["events"]][-3:], [6, 6, 5])

    def test_store_edits_are_named_in_each_recording(self) -> None:
        expected = {"e1": ["secure-boot-off"], "e4": ["secure-boot-off"], "e5": ["revoke-loader-hash"]}
        for run, edits in expected.items():
            detail = self._load(run)["run"]["change_detail"]
            self.assertEqual((detail["store_edits"], detail["firmware_replaced"]), (edits, False), run)
        self.assertIsNotNone(self._load("e1")["run"]["change_detail"]["loader_byte"])
        self.assertIsNone(self._load("e4")["run"]["change_detail"]["loader_byte"])
        self.assertIsNone(self._load("e5")["run"]["change_detail"]["loader_byte"])


if __name__ == "__main__":
    unittest.main()
