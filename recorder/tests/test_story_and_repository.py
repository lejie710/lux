"""Story stops and repository rules."""
import unittest

from recorder import eventlog, storymap
from recorder.tests import helpers


class StoryStops(unittest.TestCase):
    def test_real_normal_boot_maps_to_the_declared_stops(self) -> None:
        events = eventlog.parse_event_log(helpers.fixture_bytes("normal-eventlog.bin")).events
        stops = [storymap.assign_stop(event) for event in events]
        self.assertEqual([stop for stop, _ in stops],
                         [3] * 3 + [4] * 6 + [5] * 15 + [6] * 2 + [7] * 2)
        self.assertEqual(stops[8], (4, "pcr7-policy"))            # the register 7 separator
        self.assertEqual(stops[16], (5, "boot-attempt"))
        self.assertEqual(stops[24], (6, "authorise"))
        self.assertEqual(stops[27], (7, "exit-boot-services"))

    def test_real_refused_boot_ends_at_stop_6_and_tries_again(self) -> None:
        events = eventlog.parse_event_log(helpers.fixture_bytes("e2-eventlog.bin")).events
        stops = [storymap.assign_stop(event) for event in events]
        self.assertEqual(stops[24], (6, "authorise"))             # "Returning from EFI Application"
        self.assertEqual(stops[25], (5, "boot-attempt"))          # the next boot option is called
        self.assertNotIn(7, [stop for stop, _ in stops])

    def test_every_real_event_matches_exactly_one_rule(self) -> None:
        for tag in ("normal", "e2"):
            for event in eventlog.parse_event_log(helpers.fixture_bytes(f"{tag}-eventlog.bin")).events:
                matching = [rule.name for rule in storymap.RULES if rule.matches(event)]
                self.assertEqual(len(matching), 1, (event.index, matching))

    def test_an_event_no_rule_claims_gets_no_stop(self) -> None:
        stray = helpers.make_event(9, 0x0000000D, b"unexpected")
        self.assertEqual(storymap.assign_stop(stray), (None, None))
        wrong_register = helpers.make_event(2, eventlog.EV_EFI_VARIABLE_AUTHORITY, bytes(40))
        self.assertEqual(storymap.assign_stop(wrong_register), (None, None))

    def test_rules_name_a_basis_and_no_stop_before_3(self) -> None:
        for rule in storymap.RULES:
            self.assertTrue(rule.basis)
            self.assertIn(rule.stop, (3, 4, 5, 6, 7))


class RepositoryRules(unittest.TestCase):
    TEXT_SUFFIXES = (".py", ".md", ".json", ".sh", ".s", ".txt", ".gitignore", ".gitattributes")

    def _text_files(self):
        for path in helpers.REPOSITORY.rglob("*"):
            relative = path.relative_to(helpers.REPOSITORY).parts
            if path.is_file() and relative[0] not in (".git", "work", "scratch", "site") \
                    and "__pycache__" not in relative and path.name.endswith(self.TEXT_SUFFIXES):
                yield path

    def test_no_long_dashes_and_no_carriage_returns(self) -> None:
        long_dashes = (chr(0x2014), chr(0x2013))
        for path in self._text_files():
            data = path.read_bytes()
            self.assertNotIn(b"\r", data, path)
            text = data.decode("utf-8")
            for dash in long_dashes:
                self.assertNotIn(dash, text, path)

    def test_no_host_path_or_user_folder_in_any_text_file(self) -> None:
        for path in self._text_files():
            text = path.read_text(encoding="utf-8")
            for marker in ("/mnt/c/", "C:\\Users", "/root/lux", "/home/"):
                if path.name in ("test_capture.py", "test_story_and_repository.py", "normalise.py"):
                    continue                    # these files name the markers they search for
                self.assertNotIn(marker, text, path)


if __name__ == "__main__":
    unittest.main()
