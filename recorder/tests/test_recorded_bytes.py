"""The byte-level statements of the story must be the bytes of the committed event log.

`recording.json` keeps a summary of each event: its register, type, size and
digest. The value itself is in the raw log stored beside it. Where the story
states such a value, this test reads it from `recordings/normal-1/eventlog.bin`
with the recorder's own parser and requires the story to carry the same bytes.
"""
import json
import struct
import unittest

from recorder import eventlog
from recorder.tests import helpers

RUN = helpers.REPOSITORY / "recordings" / "normal-1"
CONTENT = helpers.REPOSITORY / "content"
CALLING = "Calling EFI Application from Boot Option"


def spaced(data: bytes) -> str:
    """Bytes as the story prints them: two hexadecimal digits each, a space between."""
    return " ".join(f"{byte:02x}" for byte in data)


def leading_number(value: bytes) -> int:
    """The first four bytes of a value, read as one number with the low byte first."""
    return struct.unpack_from("<I", value, 0)[0]


def carried_text(value: bytes) -> str:
    """The 16-bit text a boot option's value carries after its first six bytes, up to the first zero."""
    text = value[6:].decode("utf-16le", errors="replace")
    return text[:text.index("\0")]


class RecordedBytes(unittest.TestCase):
    """What the raw event log of the normal run holds, byte for byte."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.log = eventlog.parse_event_log((RUN / "eventlog.bin").read_bytes())
        cls.recording = json.loads((RUN / "recording.json").read_text(encoding="utf-8"))

    def _variable(self, index: int, name: str) -> bytes:
        """The value of the variable event at `index` (counted from 1), which must be named `name`."""
        event = self.log.events[index - 1]
        self.assertEqual(event.index, index)
        parts = eventlog.variable_parts(event)
        self.assertIsNotNone(parts)
        self.assertEqual(parts[0], name)
        self.assertEqual(self.recording["events"][index - 1]["summary"],
                         f"variable {name}, {len(parts[1])} data bytes")
        return parts[1]

    def _screen(self, file: str, screen_id: str) -> dict:
        document = json.loads((CONTENT / file).read_text(encoding="utf-8"))
        for stop in document["stops"]:
            for screen in stop["screens"]:
                if screen["id"] == screen_id:
                    return screen
        self.fail(f"{file} has no screen {screen_id}")

    def _recording_claims(self, file: str, screen_id: str) -> str:
        """Every claim of the screen whose basis is the recording, as one text."""
        claims = self._screen(file, screen_id)["claims"]
        return "\n".join(claim["text"] for claim in claims if claim["basis"] == "recording")

    def test_the_secure_boot_switch_is_one_byte_01(self) -> None:
        value = self._variable(4, "SecureBoot")
        self.assertEqual(value, b"\x01")
        self.assertEqual(self.log.events[3].pcr, 7)
        self.assertIn(f"one byte, {spaced(value)}.", self._recording_claims("story-b.json", "s4-policy"))

    def test_the_stored_order_is_0000_then_0001(self) -> None:
        value = self._variable(14, "BootOrder")
        self.assertEqual(value, bytes.fromhex("00000100"))
        self.assertEqual(struct.unpack("<2H", value), (0, 1))
        claims = self._recording_claims("story-b.json", "s5-boot-order")
        self.assertIn(f"The four bytes are {spaced(value)} ", claims)
        self.assertIn("they are 0000 and then 0001", claims)
        # The two options recorded after the order carry those two numbers in their names.
        self._variable(15, "Boot0000")
        self._variable(16, "Boot0001")

    def test_the_two_boot_options_begin_differently_and_carry_their_names(self) -> None:
        first, second = self._variable(15, "Boot0000"), self._variable(16, "Boot0001")
        self.assertEqual((len(first), len(second)), (62, 110))
        self.assertEqual((first[:4], second[:4]), (bytes.fromhex("09010000"), bytes.fromhex("01000000")))
        self.assertEqual((leading_number(first), leading_number(second)), (0x00000109, 0x00000001))
        self.assertEqual(carried_text(first), "UiApp")
        self.assertEqual(carried_text(second), "UEFI QEMU HARDDISK QM00001 ")
        # The text of option 0001 is the name in quotation marks on the first console line.
        self.assertIn(f'Boot0001 "{carried_text(second)}"', self.recording["console"][0])
        self.assertFalse(any("Boot0000" in line or "UiApp" in line for line in self.recording["console"]))
        claims = self._recording_claims("story-b.json", "s5-choice")
        self.assertIn(f"Boot0000 begins with the bytes {spaced(first[:4])} and carries the text UiApp.", claims)
        self.assertIn(f"Boot0001 begins with {spaced(second[:4])} and carries the text "
                      f"{carried_text(second).strip()},", claims)
        self.assertIn(f"0x{leading_number(first):08x} for Boot0000 and 0x{leading_number(second):08x} for Boot0001",
                      claims)
        explanation = self._screen("story-b.json", "s5-choice")["detail"]["explanation"]
        self.assertIn(f"begin {spaced(first[:4])},", explanation)
        self.assertIn(f"begins {spaced(second[:4])},", explanation)

    def test_one_record_says_a_boot_option_is_called_and_it_names_none(self) -> None:
        calls = [event for event in self.log.events if eventlog.action_text(event) == CALLING]
        self.assertEqual([event.index for event in calls], [17])
        self.assertEqual(calls[0].data, CALLING.encode("ascii"))

    def test_the_key_record_is_the_end_of_the_allowed_list(self) -> None:
        whole = self._variable(7, "db")
        record = self._variable(25, "db")
        self.assertEqual(eventlog.type_name(self.log.events[24].type_code), "EV_EFI_VARIABLE_AUTHORITY")
        self.assertEqual((len(whole), len(record)), (879, 851))
        self.assertEqual(len(whole) - len(record), 28)
        self.assertEqual(whole[28:], record)
        claims = self._recording_claims("story-c.json", "s6-verify")
        self.assertIn("the 879 bytes are 28 bytes followed by the 851 bytes of this record, byte for byte", claims)
        self.assertIn("28 + 851 = 879", claims)


if __name__ == "__main__":
    unittest.main()
