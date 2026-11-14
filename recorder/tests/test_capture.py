"""Console cleaning, the TPM log, the register read, and finding the log in memory."""
import struct
import unittest

from recorder import capture, eventlog, normalise
from recorder.errors import FormatError
from recorder.tests import helpers


class Console(unittest.TestCase):
    def test_real_console_cleans_to_158_lines(self) -> None:
        lines = capture.clean_console(helpers.fixture_bytes("normal-serial.log"))
        self.assertEqual(len(lines), 158)
        self.assertTrue(lines[0].startswith("BdsDxe: loading Boot0001"))
        self.assertEqual(lines[2], "LUX-LOADER A: started, boot services active")
        self.assertEqual(lines[-1], "LUX-FINAL-MARKER loader idle after ExitBootServices")
        self.assertFalse(any("\x1b" in line or "\r" in line for line in lines))

    def test_control_codes_nul_bytes_and_blank_lines_are_removed(self) -> None:
        raw = b"\x1b[2J\x1b[01;01H\x1b[=3hfirst\x00\r\n\r\n  \r\nsecond\r\n"
        self.assertEqual(capture.clean_console(raw), ["first", "second"])

    def test_outcomes(self) -> None:
        normal = capture.clean_console(helpers.fixture_bytes("normal-serial.log"))
        refused = capture.clean_console(helpers.fixture_bytes("e2-serial.log"))
        self.assertEqual(capture.classify_outcome(normal), "accepted")
        self.assertEqual(capture.classify_outcome(refused), "refused")
        self.assertEqual(capture.classify_outcome(["BdsDxe: loading Boot0001"]), "timeout")
        self.assertEqual(len(refused), 4)
        self.assertEqual(capture.classify_outcome(['BdsDxe: failed to start Boot0001 "x": Aborted']),
                         "start-failed")

    def test_a_refusal_followed_by_an_accepted_loader_keeps_both_facts(self) -> None:
        """One boot option refused, the next one accepted: the marker wins, the refusal stays."""
        lines = ['BdsDxe: failed to load Boot0002 "a": Access Denied',
                 'BdsDxe: starting Boot0001 "b"', "LUX-FINAL-MARKER loader idle"]
        self.assertEqual(capture.classify_outcome(lines), "accepted")
        self.assertEqual(capture.refusal_lines(lines), [lines[0]])
        normal = capture.clean_console(helpers.fixture_bytes("normal-serial.log"))
        self.assertEqual(capture.refusal_lines(normal), [])
        refused = capture.clean_console(helpers.fixture_bytes("e2-serial.log"))
        self.assertEqual(capture.refusal_lines(refused), [refused[1]])

    def test_the_end_of_a_refused_boot_is_a_firmware_line(self) -> None:
        refused = capture.clean_console(helpers.fixture_bytes("e2-serial.log"))
        self.assertIsNone(capture.REFUSAL_END_PATTERN.search("\n".join(refused[:2])))
        self.assertIsNotNone(capture.REFUSAL_END_PATTERN.search(refused[2]))
        self.assertIsNotNone(capture.REFUSAL_END_PATTERN.search(refused[3]))

    def test_the_loader_dump_is_split_from_the_story_lines_without_loss(self) -> None:
        lines = capture.clean_console(helpers.fixture_bytes("normal-serial.log"))
        console, report = capture.split_console(lines)
        self.assertEqual((len(console), len(report)), (10, 148))
        self.assertEqual(sorted(console + report), sorted(lines))
        self.assertEqual(console[0], lines[0])
        self.assertEqual(console[-1], lines[-1])
        self.assertTrue(all(line.startswith(("LUX MM ", "LUX CFG ")) for line in report))
        self.assertEqual(capture.split_console(["a", "LUX MM 1", "b"]), (["a", "b"], ["LUX MM 1"]))


class TpmLog(unittest.TestCase):
    def test_real_log_holds_28_extends_all_answered(self) -> None:
        messages = capture.parse_tpm_log(helpers.fixture_text("normal-tpm.log"))
        extends = capture.extends_from_messages(messages)
        self.assertEqual(len(extends), 28)
        self.assertTrue(all(item.response_code == 0 for item in extends))
        per_pcr = {pcr: sum(1 for item in extends if item.pcr == pcr) for pcr in range(8)}
        self.assertEqual(per_pcr, {0: 4, 1: 8, 2: 1, 3: 1, 4: 3, 5: 3, 6: 1, 7: 7})
        self.assertEqual(set(extends[0].digests), {"sha1", "sha256", "sha384", "sha512"})

    def test_extend_sequence_equals_event_sequence(self) -> None:
        for tag in ("normal", "e2"):
            extends = capture.extends_from_messages(
                capture.parse_tpm_log(helpers.fixture_text(f"{tag}-tpm.log")))
            events = eventlog.parse_event_log(helpers.fixture_bytes(f"{tag}-eventlog.bin")).events
            self.assertEqual([(e.pcr, e.digests) for e in events],
                             [(x.pcr, x.digests) for x in extends])

    def test_round_trip_of_a_built_log(self) -> None:
        wanted = [capture.Extend(7, helpers.all_digests(b"a"), 0),
                  capture.Extend(4, helpers.all_digests(b"b"), 0x101)]
        found = capture.extends_from_messages(capture.parse_tpm_log(helpers.encode_tpm_log(wanted)))
        self.assertEqual(found, wanted)

    def test_truncated_message_is_refused(self) -> None:
        text = helpers.encode_tpm_log([capture.Extend(0, helpers.all_digests(b"a"), 0)])
        lines = text.split("\n")
        del lines[3]                       # lose 16 bytes of the command
        with self.assertRaises(FormatError):
            capture.extends_from_messages(capture.parse_tpm_log("\n".join(lines)))

    def test_other_commands_are_ignored(self) -> None:
        text = " SWTPM_IO_Read: length 10\n 80 01 00 00 00 0A 00 00 01 81 \n" \
               " SWTPM_IO_Write: length 10\n 80 01 00 00 00 0A 00 00 01 01 \n noise\n"
        messages = capture.parse_tpm_log(text)
        self.assertEqual([m.direction for m in messages], ["command", "response"])
        self.assertEqual(capture.extends_from_messages(messages), [])

    def _extend_command(self, body: bytes) -> list[capture.TpmMessage]:
        command = struct.pack(">HII", 0x8002, 10 + len(body), capture.TPM_CC_PCR_EXTEND) + body
        return [capture.TpmMessage("command", command, len(command))]

    def test_a_cut_off_extend_command_is_a_format_error_not_a_crash(self) -> None:
        whole = struct.pack(">II", 7, 0) + struct.pack(">I", 1) + struct.pack(">H", 0x000B) + bytes(32)
        self.assertEqual(capture.extends_from_messages(self._extend_command(whole))[0].pcr, 7)
        for length in (0, 4, 8, 10, 13):
            with self.assertRaises(FormatError):
                capture.extends_from_messages(self._extend_command(whole[:length]))

    def test_a_short_digest_in_an_extend_command_is_refused(self) -> None:
        short = struct.pack(">II", 7, 0) + struct.pack(">I", 1) + struct.pack(">H", 0x000B) + bytes(5)
        with self.assertRaises(FormatError) as caught:
            capture.extends_from_messages(self._extend_command(short))
        self.assertIn("5-byte sha256 digest", str(caught.exception))


class RegisterRead(unittest.TestCase):
    def test_command_bytes(self) -> None:
        command = capture.build_pcr_read_command(0x000B, 8)
        self.assertEqual(command.hex(), "8001" "00000014" "0000017e" "00000001" "000b" "03" "00ff00")
        self.assertEqual(struct.unpack(">HII", command[:10]), (0x8001, len(command), 0x17E))
        with self.assertRaises(ValueError):
            capture.build_pcr_read_command(0x000B, 4)

    def _response(self, code: int, values: dict[int, bytes]) -> bytes:
        bitmap = bytearray(3)
        for index in values:
            bitmap[index // 8] |= 1 << (index % 8)
        body = struct.pack(">I", 99) + struct.pack(">IHB", 1, 0x000B, 3) + bytes(bitmap)
        body += struct.pack(">I", len(values))
        for index in sorted(values):
            body += struct.pack(">H", len(values[index])) + values[index]
        return struct.pack(">HII", 0x8001, 10 + len(body), code) + body

    def test_response_is_decoded_by_register_index(self) -> None:
        values = {8: b"\x08" * 32, 10: b"\x0a" * 32, 15: b"\x0f" * 32}
        self.assertEqual(capture.parse_pcr_read_response(self._response(0, values)), values)

    def test_failure_code_is_refused(self) -> None:
        with self.assertRaises(FormatError):
            capture.parse_pcr_read_response(self._response(0x101, {0: bytes(32)}))
        with self.assertRaises(FormatError):
            capture.parse_pcr_read_response(b"\x80\x01")

    def test_a_cut_off_response_is_a_format_error_at_every_length(self) -> None:
        whole = self._response(0, {8: b"\x08" * 32, 9: b"\x09" * 32})
        for length in range(len(whole)):
            with self.assertRaises(FormatError, msg=length):
                capture.parse_pcr_read_response(whole[:length])

    def test_response_size_comes_from_the_header(self) -> None:
        whole = self._response(0, {8: b"\x08" * 32})
        self.assertEqual(capture.response_size(whole[:10]), len(whole))
        with self.assertRaises(FormatError):
            capture.response_size(whole[:5])
        with self.assertRaises(FormatError):
            capture.response_size(struct.pack(">HII", 0x8001, 3, 0))


class LogInMemory(unittest.TestCase):
    def setUp(self) -> None:
        self.log = helpers.fixture_bytes("normal-eventlog.bin")

    def _decoy(self) -> bytes:
        """The header text with nothing valid around it, as found in firmware code."""
        return b"\x90" * 40 + eventlog.HEADER_SIGNATURE + b"\x90" * 80

    def test_the_log_is_found_between_decoys(self) -> None:
        memory = bytes(4096) + self._decoy() + bytes(100) + self.log + b"\xff" * 64 + self._decoy()
        candidates = capture.find_event_logs(memory)
        self.assertEqual(len(candidates), 1)
        found = candidates[0]
        self.assertEqual(memory[found.offset:found.offset + found.log.byte_length], self.log)
        self.assertEqual(len(found.log.events), 28)

    def test_header_without_events_is_not_a_candidate(self) -> None:
        header_only = helpers.encode_log([])
        self.assertEqual(capture.find_event_logs(bytes(64) + header_only + b"\xff" * 64), [])

    def test_signature_near_the_start_of_memory_does_not_crash(self) -> None:
        self.assertEqual(capture.find_event_logs(b"\x00" * 4 + eventlog.HEADER_SIGNATURE), [])

    def test_two_logs_give_two_candidates(self) -> None:
        memory = self.log + b"\xff" * 64 + self.log + b"\xff" * 64
        self.assertEqual(len(capture.find_event_logs(memory)), 2)


class Normalise(unittest.TestCase):
    def test_run_directory_is_masked_everywhere(self) -> None:
        text = "-serial file:/home/someone/work/runs/a/serial.log -pidfile /home/someone/work/runs/a/qemu.pid"
        masked = normalise.mask_run_directory(text, "/home/someone/work/runs/a/")
        self.assertEqual(masked, "-serial file:<run-dir>/serial.log -pidfile <run-dir>/qemu.pid")

    def test_host_paths_are_found_anywhere_in_a_document(self) -> None:
        document = {"a": {"b": ["fine", "/home/someone/x"]}, "c": "/usr/share/OVMF/file.fd",
                    "d": "PciRoot(0x0)/Pci(0x1F,0x2)", "e": "C:\\Users\\someone"}
        self.assertEqual(normalise.find_host_paths(document), ["a.b[1]", "e"])

    def test_seconds_are_rounded_to_one_decimal(self) -> None:
        self.assertEqual(normalise.round_seconds(5.849), 5.8)


if __name__ == "__main__":
    unittest.main()
