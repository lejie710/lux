"""Event log parsing, PCR replay and the agreement gate."""
import hashlib
import unittest

from recorder import banks, capture, eventlog, gate
from recorder.errors import FormatError, GateFailure
from recorder.tests import helpers


class ExtendRule(unittest.TestCase):
    def test_extend_hashes_old_value_then_digest(self) -> None:
        old, digest = bytes(32), hashlib.sha256(b"x").digest()
        self.assertEqual(banks.extend("sha256", old, digest), hashlib.sha256(old + digest).digest())
        self.assertNotEqual(banks.extend("sha256", old, digest), hashlib.sha256(digest + old).digest())

    def test_start_values(self) -> None:
        start = banks.start_banks()
        self.assertEqual(set(start), {"sha1", "sha256", "sha384", "sha512"})
        self.assertEqual(start["sha256"][0], bytes(32))
        self.assertEqual(start["sha256"][17], b"\xff" * 32)
        self.assertEqual(start["sha256"][22], b"\xff" * 32)
        self.assertEqual(start["sha256"][23], bytes(32))
        self.assertEqual(len(start["sha512"]), 24)

    def test_hex_round_trip(self) -> None:
        start = banks.start_banks()
        self.assertEqual(banks.banks_from_hex(banks.banks_to_hex(start)), start)


class ParseRealLogs(unittest.TestCase):
    def test_normal_log_is_consumed_to_its_last_byte(self) -> None:
        log = eventlog.parse_event_log(helpers.fixture_bytes("normal-eventlog.bin"))
        self.assertEqual(len(log.events), 28)
        self.assertEqual(log.byte_length, 9657)
        self.assertEqual(log.digest_sizes, {"sha1": 20, "sha256": 32, "sha384": 48, "sha512": 64})

    def test_refused_log_has_26_events(self) -> None:
        log = eventlog.parse_event_log(helpers.fixture_bytes("e2-eventlog.bin"))
        self.assertEqual(len(log.events), 26)

    def test_type_names_and_digests_equal_the_tool_output(self) -> None:
        for tag in ("normal", "e2"):
            log = eventlog.parse_event_log(helpers.fixture_bytes(f"{tag}-eventlog.bin"))
            expected = [line.split() for line in helpers.fixture_text(f"{tag}-event-types.txt").splitlines()]
            self.assertEqual(len(expected), len(log.events))
            for event, (index, pcr, code, name, digest) in zip(log.events, expected):
                self.assertEqual(event.index, int(index))
                self.assertEqual(event.pcr, int(pcr))
                self.assertEqual(event.type_code, int(code, 16))
                self.assertEqual(eventlog.type_name(event.type_code), name)
                self.assertEqual(event.digests["sha256"].hex(), digest)

    def test_summaries_come_from_the_event_data(self) -> None:
        log = eventlog.parse_event_log(helpers.fixture_bytes("normal-eventlog.bin"))
        summaries = [eventlog.summarise(event) for event in log.events]
        self.assertEqual(summaries[0], "firmware version string 2024.02-2ubuntu0.10")
        self.assertEqual(summaries[1], "firmware blob at 0x820000, length 0xe0000")
        self.assertEqual(summaries[3], "variable SecureBoot, 1 data bytes")
        self.assertEqual(summaries[13], "variable BootOrder, 4 data bytes")
        self.assertEqual(summaries[16], "action: Calling EFI Application from Boot Option")
        self.assertEqual(summaries[17], "separator, data 00000000")
        self.assertEqual(summaries[24], "variable db, 817 data bytes")
        self.assertEqual(summaries[25], "image loaded at 0x1cde4018, length 0x9d38")

    def test_unknown_type_is_marked_not_guessed(self) -> None:
        self.assertEqual(eventlog.type_name(0x12345678), "UNKNOWN_0x12345678")

    def test_content_digests_recompute_for_21_events(self) -> None:
        log = eventlog.parse_event_log(helpers.fixture_bytes("normal-eventlog.bin"))
        results = [eventlog.content_digests_match(event) for event in log.events]
        self.assertEqual(results.count(True), 21)
        self.assertEqual(results.count(False), 0)
        self.assertIsNone(results[1])          # a firmware blob lies outside the log

    def test_boot_variable_digest_covers_the_value_only(self) -> None:
        log = eventlog.parse_event_log(helpers.fixture_bytes("normal-eventlog.bin"))
        boot_order = log.events[13]
        name, value = eventlog.variable_parts(boot_order)
        self.assertEqual(name, "BootOrder")
        self.assertEqual(hashlib.sha256(value).digest(), boot_order.digests["sha256"])
        self.assertNotEqual(hashlib.sha256(boot_order.data).digest(), boot_order.digests["sha256"])


class ParseBrokenLogs(unittest.TestCase):
    def test_trailing_bytes_are_refused(self) -> None:
        with self.assertRaises(FormatError):
            eventlog.parse_event_log(helpers.fixture_bytes("normal-eventlog.bin") + b"\x00" * 8)

    def test_missing_signature_is_refused(self) -> None:
        data = bytearray(helpers.fixture_bytes("normal-eventlog.bin"))
        data[32:36] = b"XXXX"
        with self.assertRaises(FormatError):
            eventlog.parse_event_log(bytes(data))

    def test_too_short_is_refused(self) -> None:
        with self.assertRaises(FormatError):
            eventlog.read_event_log(b"\x00" * 20)

    def test_reading_stops_at_empty_flash(self) -> None:
        event = helpers.make_event(0, eventlog.EV_SEPARATOR, bytes(4))
        log = eventlog.read_event_log(helpers.encode_log([event]) + b"\xff" * 64)
        self.assertEqual(len(log.events), 1)

    def test_wrong_content_digest_is_detected(self) -> None:
        wrong = helpers.make_event(7, eventlog.EV_SEPARATOR, bytes(4),
                                   digests=helpers.all_digests(b"something else"))
        self.assertIs(eventlog.content_digests_match(wrong), False)


class Replay(unittest.TestCase):
    def test_real_log_replay_equals_real_live_read(self) -> None:
        for tag in ("normal", "e2"):
            log = eventlog.parse_event_log(helpers.fixture_bytes(f"{tag}-eventlog.bin"))
            self.assertEqual(gate.replay_events(log.events), helpers.live_banks(tag))

    def test_real_extend_list_replay_equals_real_live_read(self) -> None:
        for tag in ("normal", "e2"):
            extends = capture.extends_from_messages(
                capture.parse_tpm_log(helpers.fixture_text(f"{tag}-tpm.log")))
            self.assertEqual(gate.replay_extends(extends), helpers.live_banks(tag))

    def test_replay_follows_the_extend_rule_in_order(self) -> None:
        first = helpers.make_event(0, eventlog.EV_SEPARATOR, b"one", 1)
        second = helpers.make_event(0, eventlog.EV_SEPARATOR, b"two", 2)
        expected = hashlib.sha256(
            hashlib.sha256(bytes(32) + first.digests["sha256"]).digest() + second.digests["sha256"]).digest()
        self.assertEqual(gate.replay_events([first, second])["sha256"][0], expected)
        self.assertNotEqual(gate.replay_events([second, first])["sha256"][0], expected)

    def test_no_action_events_are_not_extended(self) -> None:
        note = helpers.make_event(0, eventlog.EV_NO_ACTION, b"note")
        self.assertEqual(gate.replay_events([note]), banks.start_banks())

    def test_refused_extend_is_not_replayed(self) -> None:
        refused = capture.Extend(0, helpers.all_digests(b"x"), 0x101)
        self.assertEqual(gate.replay_extends([refused]), banks.start_banks())


class Gate(unittest.TestCase):
    def _real(self, tag: str):
        log = eventlog.parse_event_log(helpers.fixture_bytes(f"{tag}-eventlog.bin"))
        extends = capture.extends_from_messages(capture.parse_tpm_log(helpers.fixture_text(f"{tag}-tpm.log")))
        return log.events, extends, helpers.live_banks(tag)

    def test_real_boots_pass(self) -> None:
        for tag, recomputed in (("normal", 21), ("e2", 20)):
            events, extends, live = self._real(tag)
            report = gate.evaluate(events, extends, live, 1)
            self.assertTrue(report.passed, report.failures)
            self.assertEqual(report.checks["content_digests_recomputed"], recomputed)
            gate.require(report)

    def test_one_flipped_bit_in_one_digest_fails(self) -> None:
        events, extends, live = self._real("normal")
        digests = dict(events[0].digests)
        digests["sha512"] = bytes([digests["sha512"][0] ^ 1]) + digests["sha512"][1:]
        tampered = (eventlog.Event(1, events[0].pcr, events[0].type_code, digests, events[0].data),) + events[1:]
        report = gate.evaluate(tampered, extends, live, 1)
        self.assertFalse(report.checks["event_log_replay_equals_live"])
        self.assertFalse(report.checks["event_sequence_equals_extend_sequence"])
        with self.assertRaises(GateFailure):
            gate.require(report)

    def test_one_flipped_bit_in_the_live_read_fails(self) -> None:
        events, extends, live = self._real("normal")
        live["sha1"][23] = b"\x01" + live["sha1"][23][1:]
        report = gate.evaluate(events, extends, live, 1)
        self.assertFalse(report.checks["event_log_replay_equals_live"])
        self.assertFalse(report.checks["extend_list_replay_equals_live"])
        self.assertFalse(report.passed)

    def test_missing_bank_in_live_read_fails(self) -> None:
        events, extends, live = self._real("normal")
        del live["sha384"]
        self.assertFalse(gate.evaluate(events, extends, live, 1).passed)

    def test_a_lost_extend_fails(self) -> None:
        events, extends, live = self._real("normal")
        report = gate.evaluate(events, extends[:-1], live, 1)
        self.assertFalse(report.checks["extend_list_replay_equals_live"])
        self.assertFalse(report.checks["event_sequence_equals_extend_sequence"])

    def test_an_extend_the_tpm_refused_fails(self) -> None:
        events, extends, live = self._real("normal")
        extends[3] = capture.Extend(extends[3].pcr, extends[3].digests, 0x101)
        self.assertFalse(gate.evaluate(events, extends, live, 1).checks["all_extends_answered_ok"])

    def test_two_or_zero_log_candidates_fail(self) -> None:
        events, extends, live = self._real("normal")
        for count in (0, 2):
            report = gate.evaluate(events, extends, live, count)
            self.assertFalse(report.passed)
            with self.assertRaises(GateFailure):
                gate.require(report)

    def test_log_that_does_not_describe_its_data_fails(self) -> None:
        wrong = helpers.make_event(7, eventlog.EV_SEPARATOR, bytes(4),
                                   digests=helpers.all_digests(b"other"))
        live = gate.replay_events([wrong])
        report = gate.evaluate((wrong,), helpers.extends_for([wrong]), live, 1)
        self.assertTrue(report.checks["event_log_replay_equals_live"])
        self.assertFalse(report.checks["content_digests_match"])
        self.assertFalse(report.passed)


if __name__ == "__main__":
    unittest.main()
