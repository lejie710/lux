"""PE parsing, loader copies, the variable store, keys, and staging every experiment."""
import hashlib
import json
import shutil
import struct
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from recorder import enrol, experiments, keys, loader, pe, provenance, staging, varstore
from recorder.errors import FormatError, KeysRefused, StagingRefused, ToolMissing
from recorder.tests import helpers

SIGNED_LOADER = helpers.TESTKEYS / keys.SIGNED_LOADER_NAME


class TempDirCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, self.temp, ignore_errors=True)


class PeImage(unittest.TestCase):
    def setUp(self) -> None:
        self.signed = SIGNED_LOADER.read_bytes()
        self.image = pe.parse_pe(self.signed)

    def test_authenticode_of_the_signed_loader_equals_the_published_value(self) -> None:
        self.assertEqual(pe.authenticode_sha256(self.signed), helpers.LOADER_AUTHENTICODE)

    def test_authenticode_ignores_the_signature_area(self) -> None:
        unsigned = bytearray(self.signed[:self.image.signature_offset])
        struct.pack_into("<II", unsigned, self.image.certificate_entry_offset, 0, 0)
        self.assertFalse(pe.parse_pe(bytes(unsigned)).is_signed)
        self.assertEqual(pe.authenticode_sha256(bytes(unsigned)), helpers.LOADER_AUTHENTICODE)

    def test_authenticode_ignores_the_checksum_field(self) -> None:
        changed = bytearray(self.signed)
        changed[self.image.checksum_offset] ^= 0xFF
        self.assertEqual(pe.authenticode_sha256(bytes(changed)), helpers.LOADER_AUTHENTICODE)

    def test_authenticode_changes_with_one_content_byte(self) -> None:
        changed, _ = loader.change_content_byte(self.signed)
        self.assertEqual(pe.authenticode_sha256(changed), helpers.CHANGED_LOADER_AUTHENTICODE)

    def test_trailing_bytes_after_the_last_section_are_hashed(self) -> None:
        last_section_end = max(s.file_offset + s.file_size for s in self.image.sections)
        self.assertLess(last_section_end, self.image.signature_offset)
        changed = bytearray(self.signed)
        changed[last_section_end] ^= 0x01
        self.assertNotEqual(pe.authenticode_sha256(bytes(changed)), helpers.LOADER_AUTHENTICODE)

    def test_layout_of_the_signed_loader(self) -> None:
        self.assertTrue(self.image.is_signed)
        self.assertEqual(self.image.signature_offset + self.image.signature_size, len(self.signed))
        self.assertIn(".data", [section.name for section in self.image.sections])
        self.assertTrue(pe.in_signature_area(self.image, self.image.signature_offset))
        self.assertFalse(pe.in_signature_area(self.image, self.image.signature_offset - 1))
        self.assertIsNone(pe.section_at(self.image, self.image.signature_offset))

    def test_not_a_pe_file_is_refused(self) -> None:
        for data in (b"", b"MZ" + bytes(100), b"XX" + self.signed[2:]):
            with self.assertRaises(FormatError):
                pe.parse_pe(data)

    def test_enrol_program_is_a_valid_unsigned_image(self) -> None:
        writes = [enrol.VariableWrite("db", varstore.IMAGE_SECURITY_DATABASE_GUID, 0x27, b"payload")]
        program = enrol.build_enrol_program(writes)
        image = pe.parse_pe(program)
        self.assertEqual([s.name for s in image.sections], [".text", ".data", ".reloc"])
        self.assertFalse(image.is_signed)
        self.assertEqual(program, enrol.build_enrol_program(writes))        # repeatable
        self.assertIn("LUX-SETVAR db status=??".encode("utf-16le"), program)
        self.assertIn(b"payload", program)

    def test_enrol_program_for_the_committed_keys_is_byte_for_byte_pinned(self) -> None:
        """The variable store template is made by this program, so its bytes must not drift."""
        program = enrol.build_enrol_program(keys.enrolment_writes(helpers.TESTKEYS))
        self.assertEqual(len(program), 8704)
        self.assertEqual(hashlib.sha256(program).hexdigest(),
                         "3a6693a52aa132740ff115bbb49e59078ce69df2304422c08fdc671006340806")


class LoaderCopies(unittest.TestCase):
    def setUp(self) -> None:
        self.signed = SIGNED_LOADER.read_bytes()

    def test_content_change_is_one_byte_in_the_data_section(self) -> None:
        changed, change = loader.change_content_byte(self.signed)
        differing = [i for i in range(len(self.signed)) if self.signed[i] != changed[i]]
        self.assertEqual(differing, [change.file_offset])
        self.assertEqual((change.file_offset, change.old_value, change.new_value), (0x85E, 0x41, 0x42))
        self.assertEqual(change.area, "section .data")

    def test_signature_change_is_one_byte_in_the_signature_area_only(self) -> None:
        changed, change = loader.change_signature_byte(self.signed, 100)
        differing = [i for i in range(len(self.signed)) if self.signed[i] != changed[i]]
        self.assertEqual(differing, [change.file_offset])
        self.assertTrue(pe.in_signature_area(pe.parse_pe(self.signed), change.file_offset))
        self.assertEqual(change.area, "signature area, structure")
        self.assertEqual(pe.authenticode_sha256(changed), helpers.LOADER_AUTHENTICODE)

    def test_signature_offset_outside_the_area_is_refused(self) -> None:
        size = pe.parse_pe(self.signed).signature_size
        for offset in (-1, size, size + 1000):
            with self.assertRaises(StagingRefused):
                loader.change_signature_byte(self.signed, offset)

    def test_unsigned_image_is_refused(self) -> None:
        image = pe.parse_pe(self.signed)
        unsigned = bytearray(self.signed[:image.signature_offset])
        struct.pack_into("<II", unsigned, image.certificate_entry_offset, 0, 0)
        with self.assertRaises(StagingRefused):
            loader.change_signature_byte(bytes(unsigned), 0)
        with self.assertRaises(StagingRefused):
            loader.change_content_byte(bytes(unsigned))

    def test_missing_or_repeated_start_message_is_refused(self) -> None:
        needle = loader.START_MESSAGE.encode("utf-16le")
        with self.assertRaises(StagingRefused):
            loader.change_content_byte(self.signed.replace(needle, b"\x00" * len(needle)))

    def test_build_commands_leave_the_timestamp_out(self) -> None:
        commands = loader.build_commands(Path("guest/loader.s"), Path("build"))
        self.assertEqual(commands[0][0], "as")
        self.assertIn("--no-insert-timestamp", commands[1])


class VariableStore(unittest.TestCase):
    def test_records_are_read_in_file_order(self) -> None:
        store = helpers.template_store()
        self.assertEqual([v.name for v in varstore.parse_store(store)],
                         ["PK", "KEK", "db", "SecureBootEnable", "BootOrder"])
        self.assertEqual(varstore.read_data(store, "BootOrder"), b"\x00\x00\x01\x00")
        self.assertIsNone(varstore.read_data(store, "dbx"))

    def test_hand_built_record_is_parsed(self) -> None:
        name = "Lang\0".encode("utf-16le")
        record = struct.pack("<HBBIQ", 0x55AA, 0x3F, 0, 7, 0) + bytes(16)
        record += struct.pack("<III", 0, len(name), 3) + bytes(16) + name + b"eng"
        store = bytearray(b"\xff" * 512)
        store[0:100] = bytes(100)
        struct.pack_into("<H", store, 48, 72)
        store[100:100 + len(record)] = record
        (variable,) = varstore.parse_store(bytes(store))
        self.assertEqual((variable.name, variable.attributes, variable.data_size), ("Lang", 7, 3))
        self.assertEqual(varstore.read_data(bytes(store), "Lang"), b"eng")

    def test_deleted_records_are_not_live(self) -> None:
        store = bytearray(helpers.template_store())
        store[varstore.live_variable(bytes(store), "db").record_offset + 2] = 0x3C
        self.assertIsNone(varstore.live_variable(bytes(store), "db"))
        self.assertEqual(len(varstore.parse_store(bytes(store))), 5)

    def test_secure_boot_switch(self) -> None:
        store = helpers.template_store()
        switched = varstore.switch_secure_boot_off(store)
        self.assertEqual(varstore.read_data(switched, "SecureBootEnable"), b"\x00")
        self.assertEqual(sum(a != b for a, b in zip(store, switched)), 1)
        with self.assertRaises(StagingRefused):
            varstore.switch_secure_boot_off(switched)

    def test_boot_order_is_read_back_as_option_numbers(self) -> None:
        store = helpers.make_store([("BootOrder", varstore.boot_order_data([3, 2, 0, 1]))])
        self.assertEqual(varstore.read_boot_order(store), [3, 2, 0, 1])
        self.assertEqual(varstore.read_data(store, "BootOrder"), bytes.fromhex("0300020000000100"))
        for broken in (helpers.make_store([]), helpers.make_store([("BootOrder", b"\x01\x00\x02")])):
            with self.assertRaises(FormatError):
                varstore.read_boot_order(broken)

    def test_in_place_edit_refuses_another_size_or_a_missing_variable(self) -> None:
        with self.assertRaises(StagingRefused):
            varstore.replace_data(helpers.template_store(), "BootOrder", b"\x00\x00")
        with self.assertRaises(StagingRefused):
            varstore.replace_data(helpers.template_store(), "Nothing", b"\x00")

    def test_appended_revocation_entry(self) -> None:
        digest = hashlib.sha256(b"image").digest()
        entry = varstore.sha256_signature_list(keys.OWNER_GUID, digest)
        self.assertEqual(len(entry), 76)
        self.assertEqual(struct.unpack_from("<III", entry, 16), (76, 0, 48))
        self.assertEqual(entry[-32:], digest)
        store = varstore.append_variable(helpers.template_store(), "dbx",
                                         varstore.IMAGE_SECURITY_DATABASE_GUID, 0x27, entry)
        self.assertEqual(varstore.read_data(store, "dbx"), entry)
        with self.assertRaises(StagingRefused):
            varstore.append_variable(store, "dbx", varstore.IMAGE_SECURITY_DATABASE_GUID, 0x27, entry)

    def test_append_refuses_a_full_store(self) -> None:
        with self.assertRaises(StagingRefused):
            varstore.append_variable(helpers.make_store([], size=160), "Big",
                                     varstore.GLOBAL_VARIABLE_GUID, 7, bytes(200))


class Keys(TempDirCase):
    def test_committed_keys_match_their_manifest(self) -> None:
        manifest = keys.verify(helpers.TESTKEYS)
        self.assertEqual(manifest["loader_authenticode_sha256"], helpers.LOADER_AUTHENTICODE)
        self.assertEqual(len(manifest["vars_template_sha256"]), 64)
        pins = keys.pins_of(manifest)
        self.assertEqual(pins.firmware_file, "OVMF_CODE_4M.secboot.fd")
        self.assertEqual(len(pins.firmware_sha256), 64)
        self.assertEqual(set(pins.created_with), {"openssl", "sbsigntool", "efitools"})

    def test_a_manifest_that_does_not_pin_the_firmware_fails_verification(self) -> None:
        copy = helpers.copy_testkeys(self.temp / "keys", helpers.template_store())
        manifest = json.loads((copy / keys.MANIFEST_NAME).read_text(encoding="utf-8"))
        del manifest["firmware"]
        (copy / keys.MANIFEST_NAME).write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaises(KeysRefused):
            keys.verify(copy)

    def test_readme_states_that_the_certificates_are_not_yet_valid_at_the_guest_clock(self) -> None:
        text = (helpers.TESTKEYS / "README.md").read_text(encoding="utf-8")
        self.assertIn("not yet valid", text)
        self.assertEqual(set(keys.fingerprints(helpers.TESTKEYS)), {"PK", "KEK", "db"})

    def test_readme_says_the_keys_are_public_test_keys(self) -> None:
        text = (helpers.TESTKEYS / "README.md").read_text(encoding="utf-8")
        self.assertIn("public test material", text)
        self.assertIn("Never enrol", text)

    def test_generation_refuses_a_directory_that_holds_keys(self) -> None:
        commands: list[list[str]] = []
        with self.assertRaises(KeysRefused):
            keys.generate(helpers.TESTKEYS, self.temp / "scratch", commands.append)
        self.assertEqual(commands, [])
        self.assertFalse((self.temp / "scratch").exists())

    def test_generation_refuses_even_a_single_leftover_file(self) -> None:
        target = self.temp / "keys"
        target.mkdir()
        (target / "db.key").write_text("old")
        with self.assertRaises(KeysRefused):
            keys.generate(target, self.temp / "scratch", lambda command: "")

    def test_generation_into_an_empty_directory_runs_the_commands(self) -> None:
        target = self.temp / "keys"
        target.mkdir()
        (target / "README.md").write_text("readme")
        scratch = self.temp / "scratch"

        def fake_run(command: list[str]) -> str:
            Path(command[-1]).write_text(command[0])          # the last argument is the output
            if command[0] == "openssl":
                Path(command[command.index("-keyout") + 1]).write_text("key")
            return ""

        keys.generate(target, scratch, fake_run)
        self.assertEqual(len(keys.key_material_present(target)), 12)
        self.assertFalse(scratch.exists())

    def test_failed_generation_leaves_the_directory_empty(self) -> None:
        target = self.temp / "keys"

        def failing_run(command: list[str]) -> str:
            raise ToolMissing("openssl is not installed")

        with self.assertRaises(ToolMissing):
            keys.generate(target, self.temp / "scratch", failing_run)
        self.assertEqual(keys.key_material_present(target), [])

    def test_changed_missing_or_extra_file_fails_verification(self) -> None:
        copy = helpers.copy_testkeys(self.temp / "keys", helpers.template_store())
        keys.verify(copy)
        (copy / "extra.key").write_text("x")
        with self.assertRaises(KeysRefused):
            keys.verify(copy)
        (copy / "extra.key").unlink()
        original = (copy / "db.crt").read_bytes()
        (copy / "db.crt").write_bytes(original + b"\n")
        with self.assertRaises(KeysRefused):
            keys.verify(copy)
        (copy / "db.crt").unlink()
        with self.assertRaises(KeysRefused):
            keys.verify(copy)

    def test_missing_manifest_fails_verification(self) -> None:
        with self.assertRaises(KeysRefused):
            keys.verify(self.temp)

    def test_enrolment_order_is_db_kek_pk(self) -> None:
        writes = keys.enrolment_writes(helpers.TESTKEYS)
        self.assertEqual([w.name for w in writes], ["db", "KEK", "PK"])
        self.assertEqual({w.attributes for w in writes}, {0x27})

    def test_certificate_fingerprint_is_the_hash_of_the_der_bytes(self) -> None:
        pem = "-----BEGIN CERTIFICATE-----\nQUJD\nREVG\n-----END CERTIFICATE-----\n"
        self.assertEqual(provenance.certificate_fingerprint(pem), hashlib.sha256(b"ABCDEF").hexdigest())
        with self.assertRaises(ValueError):
            provenance.certificate_fingerprint("no certificate here")


class Provenance(unittest.TestCase):
    def test_versions_come_from_the_package_manager(self) -> None:
        versions = provenance.tool_versions(lambda command: f" {command[-1]}-1.0\n")
        self.assertEqual(versions["qemu"], "qemu-system-x86-1.0")
        self.assertEqual(set(versions), set(provenance.PACKAGES) | {"python"})

    def test_only_what_a_run_uses_is_a_compared_tool_version(self) -> None:
        self.assertEqual(set(provenance.PACKAGES), {"qemu", "ovmf", "swtpm", "binutils"})
        self.assertEqual(set(provenance.PACKAGES) & set(provenance.KEY_TOOL_PACKAGES), set())
        created = provenance.package_versions(provenance.KEY_TOOL_PACKAGES, lambda command: "9\n")
        self.assertEqual(created, {"openssl": "9", "sbsigntool": "9", "efitools": "9"})

    def test_host_name_leaves_the_point_release_out(self) -> None:
        directory = Path(tempfile.mkdtemp(prefix="lux-test-"))
        self.addCleanup(shutil.rmtree, directory, ignore_errors=True)
        release = directory / "os-release"
        release.write_text('PRETTY_NAME="Ubuntu 24.04.5 LTS"\nNAME="Ubuntu"\nVERSION_ID="24.04"\n')
        self.assertEqual(provenance.host_os(release), "Ubuntu 24.04")
        release.write_text('PRETTY_NAME="Ubuntu 24.04.6 LTS"\nNAME="Ubuntu"\nVERSION_ID="24.04"\n')
        self.assertEqual(provenance.host_os(release), "Ubuntu 24.04")
        release.write_text('NAME="Other"\n')
        self.assertEqual(provenance.host_os(release), "Other")
        self.assertTrue(provenance.host_os(directory / "missing"))

    def test_missing_package_manager_is_reported_not_hidden(self) -> None:
        def failing(command: list[str]) -> str:
            raise ToolMissing("no dpkg-query")
        self.assertEqual(provenance.tool_versions(failing)["ovmf"], "not reported by the package manager")

    def test_missing_programs_are_named(self) -> None:
        with self.assertRaises(ToolMissing) as caught:
            provenance.require_programs(find=lambda name: None if name == "swtpm" else "/usr/bin/x")
        self.assertIn("swtpm", str(caught.exception))
        self.assertNotIn("qemu", str(caught.exception))
        provenance.require_programs(find=lambda name: "/usr/bin/x")
        with self.assertRaises(ToolMissing):
            provenance.require_programs(provenance.KEY_GENERATION_PROGRAMS, find=lambda name: None)
        self.assertNotIn("openssl", provenance.REQUIRED_PROGRAMS)


class Staging(TempDirCase):
    def setUp(self) -> None:
        super().setUp()
        self.template = self.temp / "vars-template.fd"
        self.template.write_bytes(helpers.template_store())
        self.packaged = self.temp / "packaged.fd"
        self.packaged.write_bytes(helpers.FIRMWARE_BYTES)
        patcher = mock.patch.object(staging, "PACKAGED_FIRMWARE", self.packaged)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.assets = staging.Assets(SIGNED_LOADER, self.template,
                                     hashlib.sha256(helpers.FIRMWARE_BYTES).hexdigest())
        self.signed = SIGNED_LOADER.read_bytes()
        self.rebuilt = self.temp / "rebuilt.fd"
        self.rebuilt.write_bytes(b"rebuilt firmware")
        self.rebuilt_sha256 = hashlib.sha256(b"rebuilt firmware").hexdigest()

    def _stage(self, identifier: str, **parameters: object) -> tuple[staging.StagedRun, Path]:
        experiment = experiments.get(identifier)
        run = self.temp / "runs" / identifier
        firmware = self.rebuilt if experiment.firmware == experiments.FIRMWARE_REBUILT else None
        return staging.stage_run(experiment, run, self.assets, parameters, firmware), run

    def test_every_experiment_has_one_sentence_and_a_known_kind(self) -> None:
        self.assertEqual(set(experiments.EXPERIMENTS),
                         {"normal", "normal-two-same", "normal-two-different", "e1", "e2", "e4", "e5",
                          "boot-order-same", "boot-order-different", "signature-byte",
                          "signature-byte-off", "rebuilt-firmware"})
        for experiment in experiments.EXPERIMENTS.values():
            self.assertIn(experiment.kind, ("normal", "pilot", "counted"))
            self.assertTrue(experiment.change)
        counted = {e.identifier for e in experiments.EXPERIMENTS.values() if e.kind == "counted"}
        self.assertEqual(counted, {"boot-order-same", "boot-order-different", "signature-byte",
                                   "signature-byte-off", "rebuilt-firmware"})
        with self.assertRaises(StagingRefused):
            experiments.get("unknown")

    def test_normal_run_gets_the_signed_loader_and_an_untouched_template(self) -> None:
        staged, run = self._stage("normal")
        self.assertEqual((run / "esp/EFI/BOOT/BOOTX64.EFI").read_bytes(), self.signed)
        self.assertEqual((run / "vars.fd").read_bytes(), self.template.read_bytes())
        self.assertTrue((run / "tpm").is_dir())
        self.assertEqual(staged.loader_authenticode_sha256, helpers.LOADER_AUTHENTICODE)
        self.assertEqual(staged.firmware, staging.PACKAGED_FIRMWARE)
        self.assertEqual(staged.firmware_sha256, self.assets.firmware_sha256)
        self.assertIsNone(staged.loader_change)
        self.assertIsNone(staged.change_detail())

    def test_a_missing_or_different_packaged_firmware_is_refused_before_anything_is_written(self) -> None:
        self.packaged.write_bytes(b"a package update")
        with self.assertRaises(StagingRefused) as caught:
            self._stage("normal")
        self.assertIn("is pinned", str(caught.exception))
        self.packaged.unlink()
        with self.assertRaises(StagingRefused):
            self._stage("normal")
        self.assertFalse((self.temp / "runs").exists())

    def test_e2_changes_one_loader_byte_and_nothing_else(self) -> None:
        staged, run = self._stage("e2")
        self.assertEqual(staged.loader_authenticode_sha256, helpers.CHANGED_LOADER_AUTHENTICODE)
        self.assertEqual(staged.loader_change.area, "section .data")
        self.assertEqual((run / "vars.fd").read_bytes(), self.template.read_bytes())
        self.assertEqual(staged.change_detail(), {
            "loader_byte": {"file_offset": 0x85E, "old_value": 0x41, "new_value": 0x42,
                            "area": "section .data"},
            "store_edits": [], "firmware_replaced": False})

    def test_e1_and_e4_switch_secure_boot_off(self) -> None:
        for identifier, loader_digest in (("e1", helpers.CHANGED_LOADER_AUTHENTICODE),
                                          ("e4", helpers.LOADER_AUTHENTICODE)):
            staged, run = self._stage(identifier)
            self.assertEqual(varstore.read_data((run / "vars.fd").read_bytes(), "SecureBootEnable"), b"\x00")
            self.assertEqual(staged.loader_authenticode_sha256, loader_digest)
            self.assertEqual(staged.change_detail()["store_edits"], ["secure-boot-off"])
        self.assertIsNone(self._stage("e4")[0].change_detail()["loader_byte"])

    def test_e5_adds_the_loader_hash_to_the_revocation_list(self) -> None:
        _, run = self._stage("e5")
        dbx = varstore.read_data((run / "vars.fd").read_bytes(), "dbx")
        self.assertEqual(dbx[-32:].hex(), helpers.LOADER_AUTHENTICODE)
        self.assertEqual((run / "esp/EFI/BOOT/BOOTX64.EFI").read_bytes(), self.signed)

    def test_signature_byte_takes_its_offset_from_the_prediction_parameters_only(self) -> None:
        self.assertFalse(hasattr(experiments.get("signature-byte"), "signature_area_offset"))
        for parameters in ({}, {"signature_area_offset": "64"}, {"signature_area_offset": True}):
            with self.assertRaises(StagingRefused):
                self._stage("signature-byte", **parameters)
        self.assertFalse((self.temp / "runs" / "signature-byte").exists())
        staged, _ = self._stage("signature-byte", signature_area_offset=64)
        self.assertEqual(staged.loader_change.area, "signature area, structure")
        self.assertEqual(staged.loader_authenticode_sha256, helpers.LOADER_AUTHENTICODE)
        self.assertNotEqual(staged.loader_sha256, hashlib.sha256(self.signed).hexdigest())
        detail = staged.change_detail()["loader_byte"]
        self.assertEqual(detail["file_offset"], pe.parse_pe(self.signed).signature_offset + 64)
        self.assertEqual(detail["old_value"] ^ detail["new_value"], 1)

    def test_rebuilt_firmware_must_have_the_hash_the_prediction_pins(self) -> None:
        staged, _ = self._stage("rebuilt-firmware", firmware_sha256=self.rebuilt_sha256)
        self.assertEqual(staged.firmware.name, "rebuilt.fd")
        self.assertEqual(staged.firmware_sha256, self.rebuilt_sha256)
        self.assertTrue(staged.change_detail()["firmware_replaced"])
        with self.assertRaises(StagingRefused):                       # no pin in the prediction
            self._stage("rebuilt-firmware")
        with self.assertRaises(StagingRefused):                       # another file than pinned
            self._stage("rebuilt-firmware", firmware_sha256="00" * 32)
        experiment = experiments.get("rebuilt-firmware")
        pinned = {"firmware_sha256": self.rebuilt_sha256}
        with self.assertRaises(StagingRefused):                       # no file given
            staging.stage_run(experiment, self.temp / "r", self.assets, pinned, None)
        with self.assertRaises(StagingRefused):                       # file does not exist
            staging.stage_run(experiment, self.temp / "r", self.assets, pinned, self.temp / "none.fd")
        with self.assertRaises(StagingRefused):                       # the normal run takes no file
            staging.stage_run(experiments.get("normal"), self.temp / "r", self.assets, {}, self.rebuilt)

    def test_leftovers_of_an_earlier_run_are_removed(self) -> None:
        _, run = self._stage("normal")
        (run / "swtpm.log").write_text("old")
        self._stage("normal")
        self.assertFalse((run / "swtpm.log").exists())

    def test_manifest_is_deterministic_json(self) -> None:
        copy = helpers.copy_testkeys(self.temp / "keys", helpers.template_store())
        first = (copy / keys.MANIFEST_NAME).read_bytes()
        keys.write_manifest(copy, helpers.test_pins(helpers.template_store()))
        self.assertEqual((copy / keys.MANIFEST_NAME).read_bytes(), first)
        self.assertEqual(json.loads(first)["owner_guid"], keys.OWNER_GUID)
        self.assertEqual(keys.pins_of(keys.verify(copy)), helpers.test_pins(helpers.template_store()))
        self.assertNotIn(b"\r", first)


if __name__ == "__main__":
    unittest.main()
