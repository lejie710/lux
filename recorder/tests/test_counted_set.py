"""The counted experiments: two boot entries, the signature byte, and their predictions.

Nothing here boots anything. The changed boot order in particular is staged
and driven with fakes only: a counted experiment is booted once, for the
record, after its prediction is committed.
"""
import copy
import hashlib
import io
import json
import re
import shutil
import struct
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest import mock

from recorder import (bootentries, cli, compare, eventlog, experiments, loader, pe, prediction,
                      recording, runner, session, staging, varstore)
from recorder.errors import ComparisonRefused, FormatError, StagingRefused
from recorder.provenance import certificate_fingerprint
from recorder.tests import helpers
from recorder.tests.helpers import FakeGit
from recorder.tests.test_compare_prediction import PREDICTION, recording_from_fixture

SIGNED_LOADER = helpers.TESTKEYS / "loader-signed.efi"
PREDICTIONS = helpers.REPOSITORY / "predictions"
RECORDINGS = helpers.REPOSITORY / "recordings"
A_FIRST = ["Boot0002", "Boot0003", "Boot0000", "Boot0001"]
B_FIRST = ["Boot0003", "Boot0002", "Boot0000", "Boot0001"]
# The counted experiments that have a committed prediction. `rebuilt-firmware` has none yet.
PREDICTED = ("boot-order-same", "boot-order-different", "signature-byte", "signature-byte-off")


class BootEntries(unittest.TestCase):
    def test_option_names_are_four_upper_case_hexadecimal_digits(self) -> None:
        self.assertEqual([varstore.option_name(n) for n in (0, 3, 0x1A, 0xFFFF)],
                         ["Boot0000", "Boot0003", "Boot001A", "BootFFFF"])
        for number in (-1, 0x10000):
            with self.assertRaises(ValueError):
                varstore.option_name(number)

    def test_a_load_option_names_one_file_by_path_and_no_disk(self) -> None:
        option = varstore.load_option("Lux entry A", "\\EFI\\LUX\\A.EFI")
        attributes, path_list_length = struct.unpack_from("<IH", option, 0)
        self.assertEqual(attributes, 1)                              # active, part of a normal boot
        description = "Lux entry A\0".encode("utf-16le")
        self.assertEqual(option[6:6 + len(description)], description)
        paths = option[6 + len(description):]
        self.assertEqual(len(paths), path_list_length)               # nothing follows the path list
        node_type, sub_type, node_length = struct.unpack_from("<BBH", paths, 0)
        self.assertEqual((node_type, sub_type), (4, 4))              # media device path, file path
        self.assertEqual(paths[4:node_length], "\\EFI\\LUX\\A.EFI\0".encode("utf-16le"))
        self.assertEqual(paths[node_length:], bytes([0x7F, 0xFF, 4, 0]))     # end of the whole path

    def test_both_entries_differ_in_one_letter_so_their_variables_have_one_size(self) -> None:
        a, b = bootentries.ENTRY_A, bootentries.ENTRY_B
        self.assertEqual((a.variable, b.variable), ("Boot0002", "Boot0003"))
        self.assertEqual((a.firmware_path, b.firmware_path), ("\\EFI\\LUX\\A.EFI", "\\EFI\\LUX\\B.EFI"))
        self.assertEqual(len(varstore.load_option(a.description, a.firmware_path)),
                         len(varstore.load_option(b.description, b.firmware_path)))
        self.assertEqual(bootentries.option_names(bootentries.ORDER_A_FIRST), A_FIRST)
        self.assertEqual(bootentries.option_names(bootentries.ORDER_B_FIRST), B_FIRST)

    def test_the_entries_are_written_before_the_order_that_names_them(self) -> None:
        for order in (bootentries.ORDER_A_FIRST, bootentries.ORDER_B_FIRST):
            writes = bootentries.variable_writes(order)
            self.assertEqual([write.name for write in writes], ["Boot0002", "Boot0003", "BootOrder"])
            self.assertEqual(writes[2].payload, varstore.boot_order_data(order))
            self.assertEqual({write.attributes for write in writes}, {0x07})
            self.assertEqual({write.vendor_guid for write in writes}, {varstore.GLOBAL_VARIABLE_GUID})

    def test_an_order_that_drops_or_repeats_an_option_is_refused(self) -> None:
        for order in ((3, 2), (3, 3, 0, 1), (3, 2, 0, 1, 4), ()):
            with self.assertRaises(ValueError):
                bootentries.variable_writes(order)

    def test_two_stores_differ_in_one_variable_only(self) -> None:
        original = helpers.two_entry_store()
        changed = helpers.two_entry_store(bootentries.ORDER_B_FIRST)
        self.assertTrue(varstore.only_this_variable_differs(original, changed, "BootOrder"))
        self.assertFalse(varstore.only_this_variable_differs(original, original, "BootOrder"))
        self.assertFalse(varstore.only_this_variable_differs(original, changed, "Boot0002"))
        self.assertFalse(varstore.only_this_variable_differs(original, changed, "NoSuchVariable"))
        self.assertFalse(varstore.only_this_variable_differs(original, changed + b"\xff", "BootOrder"))
        elsewhere = bytearray(changed)
        elsewhere[varstore.live_variable(changed, "Boot0001").data_offset] ^= 1
        self.assertFalse(varstore.only_this_variable_differs(original, bytes(elsewhere), "BootOrder"))
        longer = helpers.make_store([("BootOrder", b"\x03\x00\x02\x00\x00\x00\x01\x00\x04\x00")])
        self.assertFalse(varstore.only_this_variable_differs(original, longer, "BootOrder"))


class SignatureArea(unittest.TestCase):
    def setUp(self) -> None:
        self.signed = SIGNED_LOADER.read_bytes()
        self.parts = pe.signature_parts(self.signed)
        self.area = pe.parse_pe(self.signed).signature_offset

    def test_the_parts_cover_the_whole_area_without_gaps(self) -> None:
        position = 0
        for part in self.parts:
            self.assertEqual(part.offset_in_area, position)
            self.assertGreater(part.size, 0)
            position += part.size
        self.assertEqual(position, pe.parse_pe(self.signed).signature_size)
        named = [part.name for part in self.parts if part.name != pe.PART_STRUCTURE]
        self.assertEqual(named, ["entry header", "signed image digest", "signer certificate",
                                 "signed attributes", "signature value", "padding"])

    def test_the_signed_image_digest_is_the_loaders_authenticode_digest(self) -> None:
        part = next(part for part in self.parts if part.name == pe.PART_IMAGE_DIGEST)
        start = self.area + part.offset_in_area
        self.assertEqual(self.signed[start:start + part.size].hex(), helpers.LOADER_AUTHENTICODE)

    def test_the_signature_value_is_as_long_as_a_2048_bit_key(self) -> None:
        part = next(part for part in self.parts if part.name == pe.PART_SIGNATURE_VALUE)
        self.assertEqual((part.offset_in_area, part.size), (1362, 256))
        self.assertEqual(pe.signature_part_at(self.signed, 1362).name, "signature value")
        self.assertEqual(pe.signature_part_at(self.signed, 1617).name, "signature value")
        self.assertEqual(pe.signature_part_at(self.signed, 1618).name, "padding")
        self.assertEqual(pe.signature_part_at(self.signed, 1361).name, "structure")

    def test_the_certificate_part_is_the_committed_db_certificate(self) -> None:
        part = next(part for part in self.parts if part.name == pe.PART_CERTIFICATE)
        start = self.area + part.offset_in_area
        embedded = hashlib.sha256(self.signed[start:start + part.size]).hexdigest()
        fingerprint = certificate_fingerprint((helpers.TESTKEYS / "db.crt").read_text(encoding="ascii"))
        self.assertEqual(embedded, fingerprint)

    def test_a_changed_byte_is_named_by_its_part(self) -> None:
        for offset, part in ((0, "entry header"), (150, "signed image digest"), (500, "signer certificate"),
                             (1200, "signed attributes"), (1490, "signature value"), (1620, "padding")):
            _, change = loader.change_signature_byte(self.signed, offset)
            self.assertEqual(change.area, f"signature area, {part}")
            self.assertEqual(change.file_offset, self.area + offset)

    def test_an_offset_outside_the_area_or_an_unsigned_image_has_no_part(self) -> None:
        for offset in (-1, 1624, 5000):
            with self.assertRaises(FormatError):
                pe.signature_part_at(self.signed, offset)
        image = pe.parse_pe(self.signed)
        unsigned = bytearray(self.signed[:image.signature_offset])
        struct.pack_into("<II", unsigned, image.certificate_entry_offset, 0, 0)
        with self.assertRaises(FormatError):
            pe.signature_parts(bytes(unsigned))

    def test_an_area_that_is_not_laid_out_as_expected_is_refused(self) -> None:
        broken = []
        wrong_type = bytearray(self.signed)
        struct.pack_into("<H", wrong_type, self.area + 6, 1)                 # not a signed-data entry
        broken.append(wrong_type)
        wrong_tag = bytearray(self.signed)
        wrong_tag[self.area + 8] = 0x31                                      # the outer item is no sequence
        broken.append(wrong_tag)
        too_long = bytearray(self.signed)
        struct.pack_into(">H", too_long, self.area + 10, 0xFFFF)             # item runs past the entry
        broken.append(too_long)
        short_entry = bytearray(self.signed)
        struct.pack_into("<I", short_entry, self.area, 4)                    # entry shorter than its header
        broken.append(short_entry)
        for data in broken:
            with self.assertRaises(FormatError):
                pe.signature_parts(bytes(data))
            with self.assertRaises(StagingRefused):
                loader.change_signature_byte(bytes(data), 1490)


class SecondLoader(unittest.TestCase):
    def setUp(self) -> None:
        self.signed = SIGNED_LOADER.read_bytes()
        self.second = loader.SECOND_LOADER_PATH.read_bytes()

    def test_the_committed_second_loader_is_the_first_with_one_letter_changed_and_signed(self) -> None:
        loader.verify_second_loader(self.second, self.signed)
        self.assertEqual(pe.authenticode_sha256(self.second), helpers.CHANGED_LOADER_AUTHENTICODE)
        self.assertIn("LUX-LOADER B".encode("utf-16le"), self.second)
        self.assertNotIn("LUX-LOADER A".encode("utf-16le"), self.second)
        image = pe.parse_pe(self.second)
        outside = [i for i in range(image.signature_offset) if self.second[i] != self.signed[i]]
        checksum = range(image.checksum_offset, image.checksum_offset + 4)
        self.assertEqual([i for i in outside if i not in checksum], [0x85E])     # the one letter

    def test_its_signature_names_its_own_digest_and_the_same_certificate(self) -> None:
        parts = {part.name: part for part in pe.signature_parts(self.second)}
        area = pe.parse_pe(self.second).signature_offset
        digest = parts[pe.PART_IMAGE_DIGEST]
        start = area + digest.offset_in_area
        self.assertEqual(self.second[start:start + digest.size].hex(), helpers.CHANGED_LOADER_AUTHENTICODE)

        def certificate(data: bytes) -> bytes:
            part = next(p for p in pe.signature_parts(data) if p.name == pe.PART_CERTIFICATE)
            offset = pe.parse_pe(data).signature_offset + part.offset_in_area
            return data[offset:offset + part.size]

        self.assertEqual(certificate(self.second), certificate(self.signed))

    def test_another_file_is_refused(self) -> None:
        tampered = bytearray(self.second)
        tampered[0x900] ^= 1
        for other in (bytes(tampered), self.signed, loader.change_content_byte(self.signed)[0]):
            with self.assertRaises(StagingRefused):
                loader.verify_second_loader(other, self.signed)

    def test_a_right_hash_is_not_enough(self) -> None:
        # Even a file with the pinned hash must carry a signature and the one-letter content.
        with mock.patch.object(loader, "SECOND_LOADER_SHA256", hashlib.sha256(self.signed).hexdigest()):
            with self.assertRaises(StagingRefused):
                loader.verify_second_loader(self.signed, self.signed)


class TwoEntryStaging(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        self.signed = SIGNED_LOADER.read_bytes()
        packaged = self.temp / "packaged.fd"
        packaged.write_bytes(helpers.FIRMWARE_BYTES)
        patcher = mock.patch.object(staging, "PACKAGED_FIRMWARE", packaged)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.one = self.temp / "one.fd"
        self.one.write_bytes(helpers.template_store())
        self.two = self.temp / "two.fd"
        self.two.write_bytes(helpers.two_entry_store())
        self.b_first = self.temp / "b-first.fd"
        self.b_first.write_bytes(helpers.two_entry_store(bootentries.ORDER_B_FIRST))
        self.assets = staging.Assets(
            SIGNED_LOADER, self.one, hashlib.sha256(helpers.FIRMWARE_BYTES).hexdigest(),
            second_loader=loader.SECOND_LOADER_PATH, two_entry_template=self.two,
            b_first_template=self.b_first)

    def _stage(self, identifier: str, assets: staging.Assets | None = None) -> tuple[staging.StagedRun, Path]:
        run = self.temp / "runs" / identifier
        return staging.stage_run(experiments.get(identifier), run, assets or self.assets, {}), run

    def test_the_two_entry_normal_run_puts_one_loader_behind_each_entry(self) -> None:
        staged, run = self._stage("normal-two-same")
        self.assertEqual((run / "esp/EFI/LUX/A.EFI").read_bytes(), self.signed)
        self.assertEqual((run / "esp/EFI/LUX/B.EFI").read_bytes(), self.signed)
        self.assertFalse((run / "esp/EFI/BOOT").exists())            # nothing behind the default path
        self.assertEqual((run / "vars.fd").read_bytes(), self.two.read_bytes())
        self.assertIsNone(staged.change_detail())
        self.assertEqual(list(staged.boot_order), A_FIRST)
        self.assertEqual([entry.as_document() for entry in staged.boot_entries], [
            {"entry": "A", "option": "Boot0002", "path": "\\EFI\\LUX\\A.EFI",
             "file_sha256": hashlib.sha256(self.signed).hexdigest(),
             "authenticode_sha256": helpers.LOADER_AUTHENTICODE},
            {"entry": "B", "option": "Boot0003", "path": "\\EFI\\LUX\\B.EFI",
             "file_sha256": hashlib.sha256(self.signed).hexdigest(),
             "authenticode_sha256": helpers.LOADER_AUTHENTICODE}])
        self.assertEqual(staged.vars_template_sha256, hashlib.sha256(self.two.read_bytes()).hexdigest())

    def test_the_different_form_puts_the_second_loader_behind_entry_b_only(self) -> None:
        staged, run = self._stage("normal-two-different")
        self.assertEqual((run / "esp/EFI/LUX/A.EFI").read_bytes(), self.signed)
        self.assertEqual((run / "esp/EFI/LUX/B.EFI").read_bytes(), loader.SECOND_LOADER_PATH.read_bytes())
        self.assertEqual([entry.authenticode_sha256 for entry in staged.boot_entries],
                         [helpers.LOADER_AUTHENTICODE, helpers.CHANGED_LOADER_AUTHENTICODE])
        self.assertEqual(staged.loader_authenticode_sha256, helpers.LOADER_AUTHENTICODE)
        self.assertIsNone(staged.change_detail())

    def test_the_changed_order_is_staged_from_its_own_store_and_proven_in_the_recording(self) -> None:
        for identifier, behind_b in (("boot-order-same", self.signed),
                                     ("boot-order-different", loader.SECOND_LOADER_PATH.read_bytes())):
            staged, run = self._stage(identifier)
            store = (run / "vars.fd").read_bytes()
            self.assertEqual(store, self.b_first.read_bytes())
            self.assertEqual(varstore.read_boot_order(store), [3, 2, 0, 1])
            self.assertEqual((run / "esp/EFI/LUX/A.EFI").read_bytes(), self.signed)
            self.assertEqual((run / "esp/EFI/LUX/B.EFI").read_bytes(), behind_b)
            self.assertEqual(staged.change_detail(), {
                "loader_byte": None, "store_edits": [], "firmware_replaced": False,
                "boot_order": B_FIRST})
            self.assertEqual(staged.vars_template_sha256,
                             hashlib.sha256(self.b_first.read_bytes()).hexdigest())

    def test_a_changed_run_and_its_normal_run_have_the_same_disk(self) -> None:
        for changed, normal in (("boot-order-same", "normal-two-same"),
                                ("boot-order-different", "normal-two-different")):
            self.assertEqual(experiments.get(changed).baseline, normal)
            self.assertEqual(experiments.baseline_of(experiments.get(changed)).kind, "normal")
            _, changed_run = self._stage(changed)
            _, normal_run = self._stage(normal)
            for name in ("A.EFI", "B.EFI"):
                self.assertEqual((changed_run / "esp/EFI/LUX" / name).read_bytes(),
                                 (normal_run / "esp/EFI/LUX" / name).read_bytes())
            stores = (normal_run / "vars.fd").read_bytes(), (changed_run / "vars.fd").read_bytes()
            self.assertTrue(varstore.only_this_variable_differs(*stores, "BootOrder"))

    def test_a_changed_order_store_that_differs_in_anything_else_is_refused(self) -> None:
        elsewhere = bytearray(self.b_first.read_bytes())
        elsewhere[-1] ^= 1
        stores = (bytes(elsewhere), helpers.two_entry_store((3, 2, 1, 0)), self.two.read_bytes(),
                  helpers.template_store())
        for store in stores:
            self.b_first.write_bytes(store)
            with self.assertRaises(StagingRefused):
                self._stage("boot-order-same")
            self.assertFalse((self.temp / "runs" / "boot-order-same").exists())

    def test_missing_templates_and_a_missing_second_loader_are_refused(self) -> None:
        self.b_first.unlink()
        with self.assertRaises(StagingRefused) as caught:
            self._stage("boot-order-same")
        self.assertIn("--changed-boot-order", str(caught.exception))
        self._stage("normal-two-same")                               # needs only the two-entry template
        without_second = staging.Assets(SIGNED_LOADER, self.one, self.assets.firmware_sha256,
                                        two_entry_template=self.two)
        with self.assertRaises(StagingRefused):
            self._stage("normal-two-different", without_second)
        self.two.unlink()
        with self.assertRaises(StagingRefused):
            self._stage("normal-two-same")

    def test_a_two_entry_template_must_hold_both_entries_as_written(self) -> None:
        store = self.two.read_bytes()
        wrong_entry = varstore.replace_data(
            store, "Boot0003", varstore.load_option("Lux entry B", "\\EFI\\LUX\\X.EFI"))
        for broken in (wrong_entry, helpers.template_store(), helpers.two_entry_store((2, 3, 1, 0))):
            with self.assertRaises(StagingRefused):
                staging.require_two_entries(broken, bootentries.ORDER_A_FIRST)
        staging.require_two_entries(store, bootentries.ORDER_A_FIRST)

    def test_one_entry_runs_are_staged_as_before(self) -> None:
        staged, run = self._stage("normal")
        self.assertEqual((run / "esp/EFI/BOOT/BOOTX64.EFI").read_bytes(), self.signed)
        self.assertFalse((run / "esp/EFI/LUX").exists())
        self.assertEqual((staged.boot_entries, staged.boot_order), ((), ()))

    def test_signature_byte_off_changes_the_byte_and_the_switch(self) -> None:
        run = self.temp / "runs" / "signature-byte-off"
        staged = staging.stage_run(experiments.get("signature-byte-off"), run, self.assets,
                                   {"signature_area_offset": 1490})
        self.assertEqual(varstore.read_data((run / "vars.fd").read_bytes(), "SecureBootEnable"), b"\x00")
        self.assertEqual(staged.change_detail(), {
            "loader_byte": {"file_offset": 40170, "old_value": 0xDA, "new_value": 0xDB,
                            "area": "signature area, signature value"},
            "store_edits": ["secure-boot-off"], "firmware_replaced": False})
        self.assertEqual(staged.loader_authenticode_sha256, helpers.LOADER_AUTHENTICODE)


class Fingerprints(unittest.TestCase):
    def test_fields_added_later_do_not_change_the_fingerprint_of_older_experiments(self) -> None:
        # The values stored in the recordings that were committed before the fields existed.
        for run in ("normal-1", "e1", "e2", "e4", "e5"):
            document = recording.load_json(RECORDINGS / run / "recording.json", recording.RECORDING_FORMAT)
            experiment = experiments.get(document["run"]["experiment"])
            self.assertEqual(experiments.fingerprint(experiment), document["run"]["experiment_sha256"], run)

    def test_every_committed_recording_carries_the_fingerprint_of_its_experiment(self) -> None:
        for path in sorted(RECORDINGS.glob("*/recording.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            experiment = experiments.get(document["run"]["experiment"])
            self.assertEqual(experiments.fingerprint(experiment), document["run"]["experiment_sha256"],
                             path.parent.name)

    def test_a_used_later_field_is_part_of_the_fingerprint(self) -> None:
        same, different = experiments.get("normal-two-same"), experiments.get("normal-two-different")
        self.assertNotEqual(experiments.fingerprint(same), experiments.fingerprint(different))
        self.assertNotEqual(experiments.fingerprint(same), experiments.fingerprint(experiments.get("normal")))


class MoreExpectations(unittest.TestCase):
    def _row(self, **expectation: object) -> dict:
        return {"id": "r", "field": "value", "basis": "this-firmware", "citation": None,
                "source": "recordings/normal-1/recording.json", **expectation}

    def test_either_or_holds_for_each_named_value_and_for_no_other(self) -> None:
        row = self._row(expect_one_of=["a", ["b"]])
        self.assertTrue(prediction.row_holds(row, {"value": "a"}))
        self.assertTrue(prediction.row_holds(row, {"value": ["b"]}))
        self.assertFalse(prediction.row_holds(row, {"value": "c"}))
        self.assertFalse(prediction.row_holds(row, {"value": None}))

    def test_text_contains(self) -> None:
        row = self._row(expect_text_contains="Boot0003")
        self.assertTrue(prediction.row_holds(row, {"value": 'BdsDxe: loading Boot0003 "Lux entry B"'}))
        self.assertFalse(prediction.row_holds(row, {"value": 'BdsDxe: loading Boot0002 "Lux entry A"'}))
        self.assertFalse(prediction.row_holds(row, {"value": None}))          # no line differs at all
        self.assertFalse(prediction.row_holds(row, {"value": ["Boot0003"]}))  # a list is not a text

    def test_a_null_block_gives_null_and_a_missing_field_is_still_an_error(self) -> None:
        comparison = {"first_differing_event": None, "outcome": {"changed": "accepted"}}
        self.assertIsNone(prediction.lookup(comparison, "first_differing_event.index"))
        row = {**self._row(expect=14), "field": "first_differing_event.index"}
        self.assertFalse(prediction.row_holds(row, comparison))
        with self.assertRaises(FormatError):
            prediction.lookup(comparison, "outcome.missing")
        with self.assertRaises(FormatError):
            prediction.lookup(comparison, "no_such_block.index")

    def _document(self, change) -> dict:
        document = copy.deepcopy(PREDICTION)
        change(document)
        return document

    def test_validation_of_the_new_expectations(self) -> None:
        good = [
            lambda d: d["rows"][2].update(expect_one_of=["x", "y"]) or d["rows"][2].pop("expect_excludes"),
            lambda d: d["rows"][2].update(expect_text_contains="x") or d["rows"][2].pop("expect_excludes"),
        ]
        for change in good:
            prediction.validate(self._document(change))
        broken = [
            lambda d: d["rows"][2].update(expect_one_of=["x"]) or d["rows"][2].pop("expect_excludes"),
            lambda d: d["rows"][2].update(expect_one_of="xy") or d["rows"][2].pop("expect_excludes"),
            lambda d: d["rows"][2].update(expect_text_contains="") or d["rows"][2].pop("expect_excludes"),
            lambda d: d["rows"][2].update(expect_text_contains=["x"]) or d["rows"][2].pop("expect_excludes"),
            lambda d: d["rows"][2].update(expect_excludes=[]),
            lambda d: d["rows"][2].update(expect_one_of=["x", "y"]),              # two expectations
        ]
        for change in broken:
            with self.assertRaises(FormatError):
                prediction.validate(self._document(change))

    def test_validation_of_the_parts_that_are_not_rows(self) -> None:
        sha = "ab" * 32
        prediction.validate(self._document(lambda d: d.update(
            wrong_if=["The boot is refused."], not_scored=["BootCurrent."],
            baseline={"run": "normal-1", "recording_sha256": sha})))
        broken = [
            lambda d: d.update(wrong_if="The boot is refused."),
            lambda d: d.update(wrong_if=[]),
            lambda d: d.update(wrong_if=["ok", " "]),
            lambda d: d.update(not_scored=[3]),
            lambda d: d.update(baseline="normal-1"),
            lambda d: d.update(baseline={"run": "normal-1", "recording_sha256": "ABCD"}),
            lambda d: d.update(baseline={"run": "", "recording_sha256": sha}),
        ]
        for change in broken:
            with self.assertRaises(FormatError):
                prediction.validate(self._document(change))

    def test_a_prediction_fits_only_the_baseline_it_names(self) -> None:
        document = {"baseline": {"run": "normal-1", "recording_sha256": "aa"}}
        self.assertTrue(prediction.fits_baseline(document, {"baseline": {"recording_sha256": "aa"}}))
        self.assertFalse(prediction.fits_baseline(document, {"baseline": {"recording_sha256": "bb"}}))
        self.assertTrue(prediction.fits_baseline({}, {"baseline": {"recording_sha256": "bb"}}))


class BaselineRules(unittest.TestCase):
    """A changed run is compared with the normal run it changes, and with no other."""

    def setUp(self) -> None:
        self.normal = recording_from_fixture("normal", "normal-1")
        self.two = self._as(recording_from_fixture("normal", "normal-two-same-1", "2026-01-01T00:01:00Z"),
                            "normal-two-same")
        self.two_again = self._as(
            recording_from_fixture("normal", "normal-two-same-2", "2026-01-01T00:02:00Z"), "normal-two-same")
        self.changed = self._as(recording_from_fixture("normal", "blind", "2026-01-01T00:03:00Z"),
                                "boot-order-same")
        self.pilot = recording_from_fixture("e2", "e2", "2026-01-01T00:04:00Z")

    @staticmethod
    def _as(document: dict, identifier: str) -> dict:
        experiment = experiments.get(identifier)
        document["run"].update(experiment=identifier, kind=experiment.kind, change=experiment.change,
                               experiment_sha256=experiments.fingerprint(experiment))
        return document

    def test_a_boot_order_run_is_compared_with_its_two_entry_normal_run_only(self) -> None:
        compare.require_comparable(self.two, self.changed, "a", "b")
        with self.assertRaises(ComparisonRefused) as caught:
            compare.require_comparable(self.normal, self.changed, "a", "b")
        self.assertIn("normal-two-same", str(caught.exception))
        other = self._as(copy.deepcopy(self.two), "normal-two-different")
        with self.assertRaises(ComparisonRefused):
            compare.require_comparable(other, self.changed, "a", "b")

    def test_a_pilot_is_compared_with_the_plain_normal_run_only(self) -> None:
        compare.require_comparable(self.normal, self.pilot, "a", "b")
        with self.assertRaises(ComparisonRefused):
            compare.require_comparable(self.two, self.pilot, "a", "b")

    def test_two_normal_runs_of_any_kind_may_be_compared(self) -> None:
        compare.require_comparable(self.normal, self.two, "a", "b")
        compare.require_comparable(self.two, self.two_again, "a", "b")

    def test_an_unknown_experiment_has_no_baseline(self) -> None:
        self.changed["run"]["experiment"] = "boot-order"             # the name before the two forms
        with self.assertRaises(ComparisonRefused):
            compare.require_comparable(self.two, self.changed, "a", "b")

    def test_the_repeat_must_be_two_recordings_of_that_normal_run(self) -> None:
        repeat = compare.compare_recordings(self.two, self.two_again, "a", "b")
        compare.require_repeat(repeat, "a", "normal-two-same")
        for baseline in ("normal", "normal-two-different"):
            with self.assertRaises(ComparisonRefused):
                compare.require_repeat(repeat, "a", baseline)
        mixed = compare.compare_recordings(self.normal, self.two, "a", "b")
        self.assertTrue(mixed["identical"])                          # the fixtures are one boot
        for baseline in ("normal", "normal-two-same"):
            with self.assertRaises(ComparisonRefused):
                compare.require_repeat(mixed, "a", baseline)

    def test_the_comparison_gives_the_text_of_the_first_console_line_that_differs(self) -> None:
        result = compare.compare_recordings(self.normal, self.pilot, "a", "b")
        number = result["console_first_differing_line"]
        self.assertEqual(result["console_first_differing_text"],
                         {"baseline": self.normal["console"][number - 1],
                          "changed": self.pilot["console"][number - 1]})
        self.assertEqual(compare.differing_line_text(["a", "b"], ["a"]), {"baseline": "b", "changed": None})
        self.assertEqual(compare.differing_line_text(["a"], ["a", "c"]), {"baseline": None, "changed": "c"})
        self.assertEqual(compare.differing_line_text(["a"], ["a"]), {"baseline": None, "changed": None})

    def test_the_reference_to_a_prediction_is_not_listed_as_a_difference(self) -> None:
        self.changed["provenance"]["prediction"] = {"path": "predictions/boot-order-same.json",
                                                    "sha256": "aa", "commit": "c", "parameters": {}}
        result = compare.compare_recordings(self.two, self.changed, "a", "b")
        self.assertEqual(result["other_fields_differing"], [])
        self.changed["provenance"]["tools"]["qemu"] = "2"
        result = compare.compare_recordings(self.two, self.changed, "a", "b")
        self.assertEqual(result["other_fields_differing"], ["provenance.tools.qemu"])


class CommittedPredictions(unittest.TestCase):
    """The prediction files in the repository, checked against what they are about."""

    def _load(self, name: str) -> dict:
        return prediction.load(PREDICTIONS / f"{name}.json")

    def test_there_is_one_file_per_counted_experiment_that_can_be_run(self) -> None:
        on_disk = {path.stem for path in PREDICTIONS.glob("*.json")}
        self.assertEqual(on_disk, set(PREDICTED))
        counted = {e.identifier for e in experiments.EXPERIMENTS.values() if e.kind == "counted"}
        self.assertEqual(counted - on_disk, {"rebuilt-firmware"})

    def test_each_fits_its_experiment_word_for_word(self) -> None:
        for name in PREDICTED:
            document, experiment = self._load(name), experiments.get(name)
            self.assertEqual(document["experiment"], name)
            self.assertEqual(document["change"], experiment.change)
            self.assertEqual(set(document["parameters"]), set(experiment.parameters))
            self.assertEqual(prediction._require_fits_experiment(document, experiment, ""),
                             document["parameters"])

    def test_each_says_what_would_prove_it_wrong_and_names_its_baseline(self) -> None:
        for name in PREDICTED:
            document, experiment = self._load(name), experiments.get(name)
            self.assertGreaterEqual(len(document["wrong_if"]), 2, name)
            self.assertIn("wrong", document["wrong_if"][0])
            baseline = document["baseline"]
            file = RECORDINGS / baseline["run"] / "recording.json"
            self.assertEqual(baseline["recording_sha256"], recording.sha256_of_file(file), name)
            run = json.loads(file.read_text(encoding="utf-8"))["run"]
            self.assertEqual((run["experiment"], run["kind"]), (experiment.baseline, "normal"), name)
            repeat = RECORDINGS / cli.repeat_comparison(experiment.baseline)
            compare.require_repeat(recording.load_json(repeat, compare.COMPARISON_FORMAT),
                                   baseline["recording_sha256"], experiment.baseline)

    def test_each_covers_what_a_prediction_must_cover(self) -> None:
        needed = {"outcome.changed", "refusal_lines.changed", "first_differing_event.index",
                  "first_differing_event.stop", "first_differing_event.changed",
                  "events_only_in_baseline", "events_only_in_changed", "console_first_differing_line"}
        for name in PREDICTED:
            rows = self._load(name)["rows"]
            self.assertLessEqual(needed, {row["field"] for row in rows}, name)
            registers = []
            for row in rows:
                reason = row.get("reason", "")
                self.assertTrue(reason.endswith("."), (name, row["id"]))
                self.assertNotIn(". ", reason[:-1], (name, row["id"]))       # one sentence
                if row["field"] == "pcrs_differing.sha256":
                    registers += row.get("expect_contains", []) + row.get("expect_excludes", [])
            self.assertEqual(sorted(registers), list(range(8)), name)        # each of 0 to 7, once

    def test_every_specification_row_cites_a_page_of_the_verified_reading(self) -> None:
        verified = {("3 Boot Manager (opening text)", 152),
                    ("3.3 Globally Defined Variables (Table 3.3 Global Variables)", 165),
                    ("3.3 Globally Defined Variables", 166),
                    ("7.4.1 EFI_BOOT_SERVICES.LoadImage()", 283),
                    ("32.5.1 Overview (under 32.5 UEFI Image Validation)", 1633)}
        required = 0
        for name in PREDICTED:
            for row in self._load(name)["rows"]:
                if row["basis"] in ("uefi-required", "uefi-platform"):
                    citation = row["citation"]
                    self.assertEqual((citation["document"], citation["version"]),
                                     ("UEFI Specification", "2.11"))
                    self.assertIn((citation["section"], citation["page"]), verified, (name, row["id"]))
                    required += row["basis"] == "uefi-required"
                else:
                    self.assertIsNone(row["citation"])
        self.assertEqual(required, 6)

    def test_a_row_about_an_unread_document_claims_nothing_about_it(self) -> None:
        for name in PREDICTED:
            for row in self._load(name)["rows"]:
                if row["basis"] == "tcg-unread":
                    self.assertIn("not been read", row["reason"], (name, row["id"]))
                    self.assertIn("nothing is claimed here about what", row["reason"], (name, row["id"]))
                    self.assertNotIn("source", row)

    def test_every_observation_names_a_committed_file(self) -> None:
        for name in PREDICTED:
            for row in self._load(name)["rows"]:
                files = re.findall(r"recordings/[A-Za-z0-9_./-]+\.json", row.get("source", ""))
                if row["basis"] == "this-firmware":
                    self.assertTrue(files, (name, row["id"]))
                for file in files:
                    self.assertTrue((helpers.REPOSITORY / file).is_file(), (name, row["id"], file))

    def test_the_signature_byte_lies_in_the_middle_of_the_signature_value(self) -> None:
        signed = SIGNED_LOADER.read_bytes()
        part = next(p for p in pe.signature_parts(signed) if p.name == pe.PART_SIGNATURE_VALUE)
        for name in ("signature-byte", "signature-byte-off"):
            document = self._load(name)
            offset = document["parameters"]["signature_area_offset"]
            self.assertEqual(offset, part.offset_in_area + part.size // 2)
            changed, change = loader.change_signature_byte(signed, offset)
            self.assertEqual(change.area, "signature area, signature value")
            byte = document["byte"]
            self.assertEqual((byte["file_offset"], byte["old_value"], byte["new_value"]),
                             (change.file_offset, change.old_value, change.new_value))
            self.assertEqual((byte["part"], byte["position_in_part"], byte["part_size"]),
                             ("signature value", 128, 256))
            self.assertEqual(pe.authenticode_sha256(changed), helpers.LOADER_AUTHENTICODE)
            self.assertEqual(sum(a != b for a, b in zip(signed, changed)), 1)

    def test_the_predicted_boot_order_digest_follows_from_the_bytes_that_will_be_written(self) -> None:
        original = hashlib.sha256(varstore.boot_order_data(bootentries.ORDER_A_FIRST)).hexdigest()
        changed = hashlib.sha256(varstore.boot_order_data(bootentries.ORDER_B_FIRST)).hexdigest()
        for name in ("boot-order-same", "boot-order-different"):
            document = self._load(name)
            rows = {row["id"]: row for row in document["rows"]}
            baseline = json.loads((RECORDINGS / document["baseline"]["run"] / "recording.json")
                                  .read_text(encoding="utf-8"))
            event = baseline["events"][13]
            self.assertEqual((event["index"], event["digest_sha256"], event["summary"]),
                             (14, original, "variable BootOrder, 8 data bytes"))
            self.assertEqual(rows["order-measured-as-written"]["expect"]["digest_sha256"], changed)
            self.assertEqual(rows["events-only-in-normal-run"]["expect"][0]["digest_sha256"], original)
            self.assertEqual(rows["events-only-in-changed-run"]["expect"][0]["digest_sha256"], changed)
            self.assertEqual(rows["first-console-line"]["expect"],
                             baseline["console"][0].replace("Boot0002", "Boot0003")
                             .replace("entry A", "entry B").replace("A.EFI", "B.EFI"))
            self.assertEqual(document["boot_order"]["changed_run"], B_FIRST)
        different = {row["id"]: row for row in self._load("boot-order-different")["rows"]}
        self.assertEqual(different["second-loader-measured"]["expect_contains"][0]["digest_sha256"],
                         pe.authenticode_sha256(loader.SECOND_LOADER_PATH.read_bytes()))

    def test_the_signature_rows_repeat_what_the_pilots_showed(self) -> None:
        def comparison(pilot: str) -> dict:
            return recording.load_json(RECORDINGS / "comparisons" / f"normal-1_vs_{pilot}.json",
                                       compare.COMPARISON_FORMAT)

        for name, pilot in (("signature-byte", "e2"), ("signature-byte-off", "e4")):
            seen = comparison(pilot)
            score = prediction.score(self._load(name), seen)
            # Against its pilot, every row holds except the ones that tell the two apart.
            self.assertEqual(score["mismatches"], [], name)

    def test_the_files_are_plain_text_without_long_dashes(self) -> None:
        for path in sorted(PREDICTIONS.glob("*.json")):
            text = path.read_bytes().decode("utf-8")
            for long_dash in (chr(0x2014), chr(0x2013)):
                self.assertNotIn(long_dash, text)
            self.assertNotIn("\r", text)
            self.assertTrue(text.endswith("}\n"))


class TwoEntryNormalRuns(unittest.TestCase):
    """What the committed normal runs with two boot entries show."""

    def _load(self, run: str) -> dict:
        return recording.load_json(RECORDINGS / run / "recording.json", recording.RECORDING_FORMAT)

    def test_entry_a_is_started_first_and_the_loader_runs(self) -> None:
        for run in ("normal-two-same-1", "normal-two-different-1"):
            document = self._load(run)
            self.assertEqual(document["console"][:3], [
                'BdsDxe: loading Boot0002 "Lux entry A" from \\EFI\\LUX\\A.EFI',
                'BdsDxe: starting Boot0002 "Lux entry A" from \\EFI\\LUX\\A.EFI',
                "LUX-LOADER A: started, boot services active"])
            self.assertEqual(document["outcome"]["result"], "accepted")
            self.assertEqual(document["outcome"]["refusal_lines"], [])
            self.assertEqual(document["provenance"]["boot_order"], A_FIRST)
            self.assertIsNone(document["run"]["change_detail"])

    def test_the_order_and_the_options_are_measured_in_the_order_the_list_gives(self) -> None:
        events = self._load("normal-two-same-1")["events"]
        self.assertEqual([(row["pcr"], row["summary"]) for row in events[13:18]], [
            (1, "variable BootOrder, 8 data bytes"), (1, "variable Boot0002, 68 data bytes"),
            (1, "variable Boot0003, 68 data bytes"), (1, "variable Boot0000, 62 data bytes"),
            (1, "variable Boot0001, 110 data bytes")])
        raw = (RECORDINGS / "normal-two-same-1" / "eventlog.bin").read_bytes()
        measured = eventlog.variable_parts(eventlog.parse_event_log(raw).events[13])
        self.assertEqual(measured, ("BootOrder", varstore.boot_order_data(bootentries.ORDER_A_FIRST)))

    def test_only_register_1_differs_from_the_plain_normal_run(self) -> None:
        plain, two = self._load("normal-1"), self._load("normal-two-same-1")
        differing, _ = compare.compare_pcrs(plain["pcrs"], two["pcrs"])
        self.assertEqual(set(map(tuple, differing.values())), {(1,)})

    def test_the_two_forms_differ_only_in_the_file_behind_entry_b(self) -> None:
        same, different = self._load("normal-two-same-1"), self._load("normal-two-different-1")
        for field in ("console", "loader_report", "events", "pcrs", "event_log", "vars_after_sha256"):
            self.assertEqual(same[field], different[field], field)
        behind_b = [document["provenance"]["boot_entries"][1]["authenticode_sha256"]
                    for document in (same, different)]
        self.assertEqual(behind_b, [helpers.LOADER_AUTHENTICODE, helpers.CHANGED_LOADER_AUTHENTICODE])
        self.assertEqual(same["provenance"]["boot_entries"][0], different["provenance"]["boot_entries"][0])


class CountedPipeline(unittest.TestCase):
    """Every committed prediction, driven through record, compare and score with fakes.

    The fake machine replays one real normal boot whatever is staged, so the
    scores mean nothing. What is under test is that each counted experiment
    can be staged from its committed prediction, recorded, compared with a
    recording of its own normal run and scored without an error. That is all
    that may be learned about a counted experiment before its one real boot.
    """

    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        template = helpers.template_store()
        self.two_entries = helpers.two_entry_store()
        self.work = self.temp / "work"
        (self.work / "template").mkdir(parents=True)
        (self.work / staging.TEMPLATE_PATH).write_bytes(template)
        (self.work / staging.TWO_ENTRY_TEMPLATE_PATH).write_bytes(self.two_entries)
        (self.work / staging.B_FIRST_TEMPLATE_PATH).write_bytes(
            helpers.two_entry_store(bootentries.ORDER_B_FIRST))
        self.testkeys = helpers.copy_testkeys(self.temp / "testkeys", template)
        self.predictions = self.temp / "predictions"
        shutil.copytree(PREDICTIONS, self.predictions)
        firmware = self.temp / "firmware.fd"
        firmware.write_bytes(helpers.FIRMWARE_BYTES)
        patcher = mock.patch.object(staging, "PACKAGED_FIRMWARE", firmware)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.memory = (bytes(512) + eventlog.HEADER_SIGNATURE + b"\x90" * 64
                       + helpers.fixture_bytes("normal-eventlog.bin") + b"\xff" * 128)
        self.staged: dict[str, dict[str, bytes]] = {}

    def _env(self) -> runner.Environment:
        clock = helpers.FakeClock()

        def factory(run_directory: Path, firmware: Path) -> helpers.FakeMachine:
            self.staged[run_directory.name] = {
                str(path.relative_to(run_directory).as_posix()): path.read_bytes()
                for path in sorted(run_directory.rglob("*")) if path.is_file()}
            return helpers.FakeMachine(
                clock, run_directory, {5.0: helpers.fixture_bytes("normal-serial.log")},
                tpm_log=helpers.fixture_text("normal-tpm.log"), memory=self.memory,
                live=helpers.live_banks("normal"))

        return runner.Environment(
            testkeys_directory=self.testkeys, predictions_directory=self.predictions,
            work_directory=self.work, machine_factory=factory, clock=clock, limits=session.Limits(),
            tool_versions=lambda: {"qemu": "test"}, host_os="test os", git=FakeGit(),
            require_repeat=lambda: None,
            two_entry_template_sha256=hashlib.sha256(self.two_entries).hexdigest())

    def _record(self, name: str, experiment: str, moment: str) -> dict:
        return runner.record_run(runner.RunRequest(name, experiment, moment), self._env()).document

    def test_each_predicted_experiment_goes_from_staging_to_a_score(self) -> None:
        for name in PREDICTED:
            experiment = experiments.get(name)
            normal = self._record("normal-run", experiment.baseline, "2026-01-01T00:00:00Z")
            changed = self._record("counted-run", name, "2026-01-01T00:01:00Z")
            self.assertEqual(changed["run"]["kind"], "counted")
            committed = prediction.load(PREDICTIONS / f"{name}.json")
            self.assertEqual(changed["provenance"]["prediction"]["parameters"], committed["parameters"])
            self.assertEqual(changed["provenance"]["prediction"]["sha256"],
                             recording.sha256_of_file(PREDICTIONS / f"{name}.json"))
            compare.require_comparable(normal, changed, "a", "b")
            result = compare.compare_recordings(normal, changed, "a", "b")
            score = prediction.score(committed, result)
            self.assertEqual(len(score["rows"]), len(committed["rows"]), name)
            self.assertEqual(score["required_total"] + score["open_total"], len(committed["rows"]))

    def test_the_boot_order_runs_differ_from_their_normal_runs_in_the_store_alone(self) -> None:
        for name in ("boot-order-same", "boot-order-different"):
            self._record("normal-run", experiments.get(name).baseline, "2026-01-01T00:00:00Z")
            normal_files = self.staged["normal-run"]
            changed = self._record("counted-run", name, "2026-01-01T00:01:00Z")
            changed_files = self.staged["counted-run"]
            self.assertEqual(sorted(changed_files), ["esp/EFI/LUX/A.EFI", "esp/EFI/LUX/B.EFI", "vars.fd"])
            differing = [file for file in changed_files if changed_files[file] != normal_files[file]]
            self.assertEqual(differing, ["vars.fd"])
            self.assertTrue(varstore.only_this_variable_differs(
                normal_files["vars.fd"], changed_files["vars.fd"], "BootOrder"))
            self.assertEqual(changed["run"]["change_detail"]["boot_order"], B_FIRST)
            self.assertEqual(changed["provenance"]["boot_order"], B_FIRST)

    def test_the_signature_runs_change_the_one_byte_the_prediction_names(self) -> None:
        signed = SIGNED_LOADER.read_bytes()
        for name, store_edits in (("signature-byte", []), ("signature-byte-off", ["secure-boot-off"])):
            changed = self._record("counted-run", name, "2026-01-01T00:01:00Z")
            staged = self.staged["counted-run"]["esp/EFI/BOOT/BOOTX64.EFI"]
            self.assertEqual([i for i in range(len(signed)) if signed[i] != staged[i]], [40170])
            detail = changed["run"]["change_detail"]
            self.assertEqual(detail["loader_byte"]["area"], "signature area, signature value")
            self.assertEqual(detail["store_edits"], store_edits)
            self.assertEqual(changed["provenance"]["loader"]["authenticode_sha256"],
                             helpers.LOADER_AUTHENTICODE)


class ChangedBootOrderCommand(unittest.TestCase):
    """`prepare --changed-boot-order` makes nothing before a prediction is committed."""

    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)
        (self.temp / "predictions").mkdir()

    def _copy(self, name: str) -> None:
        shutil.copyfile(PREDICTIONS / f"{name}.json", self.temp / "predictions" / f"{name}.json")

    def _main(self, git: FakeGit) -> tuple[int, str, str, mock.Mock]:
        out, err = io.StringIO(), io.StringIO()
        with mock.patch.object(cli.provenance, "require_programs"), \
                mock.patch.object(cli, "REPOSITORY", self.temp), \
                mock.patch.object(cli.prediction, "run_git", git), \
                mock.patch.object(cli, "QemuMachine", side_effect=AssertionError("no machine may be made")), \
                mock.patch.object(cli.preparation, "prepare_changed_boot_order",
                                  return_value={"boot_order": "Boot0003 Boot0002"}) as prepare, \
                redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["prepare", "--changed-boot-order", "--work-dir", str(self.temp / "work")])
        return code, out.getvalue(), err.getvalue(), prepare

    def test_it_is_refused_without_a_prediction(self) -> None:
        code, _, err, prepare = self._main(FakeGit())
        self.assertEqual((code, prepare.call_count), (1, 0))
        self.assertIn("refused: the changed boot order is not prepared", err)

    def test_it_is_refused_while_the_prediction_is_not_committed(self) -> None:
        self._copy("boot-order-same")
        for git in (FakeGit(tracked=False), FakeGit(status=" M boot-order-same.json\n"),
                    FakeGit(blob=b"another text was committed")):
            code, _, _, prepare = self._main(git)
            self.assertEqual((code, prepare.call_count), (1, 0))

    def test_a_prediction_for_another_experiment_does_not_open_it(self) -> None:
        self._copy("signature-byte")
        code, _, _, prepare = self._main(FakeGit())
        self.assertEqual((code, prepare.call_count), (1, 0))

    def test_it_runs_once_either_boot_order_prediction_is_committed(self) -> None:
        for name in ("boot-order-same", "boot-order-different"):
            shutil.rmtree(self.temp / "predictions")
            (self.temp / "predictions").mkdir()
            self._copy(name)
            code, out, _, prepare = self._main(FakeGit())
            self.assertEqual((code, prepare.call_count), (0, 1), name)
            self.assertIn("boot_order: Boot0003 Boot0002", out)

    def test_each_experiment_looks_for_the_repeat_of_its_own_normal_run(self) -> None:
        self.assertEqual(cli.repeat_comparison("normal"), cli.REPEAT_COMPARISON)
        self.assertEqual(cli.repeat_comparison("normal-two-same").as_posix(),
                         "comparisons/normal-two-same-1_vs_normal-two-same-2.json")
        for path in (cli.repeat_comparison(e.baseline) for e in experiments.EXPERIMENTS.values()):
            self.assertTrue((RECORDINGS / path).is_file(), path)


if __name__ == "__main__":
    unittest.main()
