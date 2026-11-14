"""The content check must pass the committed content and refuse each kind of broken content."""
import copy
import importlib.util
import io
import json
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from recorder.tests import helpers

SCRIPT = helpers.REPOSITORY / "scripts" / "check_content.py"
_spec = importlib.util.spec_from_file_location("check_content", SCRIPT)
check_content = importlib.util.module_from_spec(_spec)
sys.modules["check_content"] = check_content
_spec.loader.exec_module(check_content)

NORMAL = "recordings/normal-1/recording.json"
PILOT = "recordings/e2/recording.json"
RULES = {1: [], 2: [], 3: ["pcr0-firmware"], 4: ["pcr7-policy"], 5: ["pcr1-config", "boot-attempt"],
         6: ["load-verify"], 7: ["exit-boot-services"]}
PARTS = ["power", "firmware", "processor", "memory", "controllers", "storage", "security"]
CITATION = {"document": "UEFI Specification", "version": "2.11", "section": "3.1",
            "title": "Firmware Boot Manager", "pdf_page": 152}


def _recordings() -> dict:
    return check_content.load_repository(helpers.REPOSITORY)[1]


def _screen(number: int) -> dict:
    """One small valid screen. Stop 1 has no recording; the others quote event number `number`."""
    if number == 1:
        evidence = {"recorded": False, "kind": "not-recorded", "label": "Described, not recorded."}
    else:
        events = RECORDINGS[NORMAL]["events"]
        evidence = {"recorded": True, "kind": "event", "run": "normal-1", "file": NORMAL,
                    "field": "events[%d].summary" % number, "position": number,
                    "text": events[number]["summary"], "event_index": events[number]["index"]}
    return {
        "id": "s%d" % number, "kind": "stop", "stop": number,
        "statement": {"text": "Firmware does step number %d." % number, "emphasis": "step"},
        "support": "One sentence of support.",
        "evidence": evidence,
        "detail": {"console_lines": [{"run": "normal-1", "positions": [0]}], "loader_report_lines": [],
                   "events": [{"run": "normal-1", "indexes": [1, 28]}],
                   "pcrs": [{"run": "normal-1", "bank": "sha256", "registers": [0, 7]}],
                   "explanation": "First sentence. Second sentence.",
                   "definitions": [{"glossary": "hash"}, {"term": "Local term", "definition": "Only here."}]},
        "claims": [{"text": "The log holds 28 events.", "basis": "recording", "run": "normal-1", "field": "events"}],
        "picture": {"plate": "board", "lit": PARTS[:number], "newly_lit": [PARTS[number - 1]],
                    "screen": "none", "note": "Illustration only."},
    }


def _stop(number: int) -> dict:
    return {"number": number, "of": 7, "id": "stop-%d" % number, "label": "Stop %d" % number, "stage_name": None,
            "threads": [], "mapping": {"rules": list(RULES[number]), "events": "Some.", "rests_on": "Log order."},
            "not_shown": ["Something."], "headline": "s%d" % number, "screens": [_screen(number)]}


def _content() -> dict:
    """The smallest content that passes: seven stops in three files, and a sources file."""
    def story(name: str, numbers: range) -> dict:
        return {"format": "lux-content/2", "file": name, "language": "en", "stops": [_stop(n) for n in numbers]}
    return {
        "story-a.json": story("story-a.json", range(1, 4)),
        "story-b.json": story("story-b.json", range(4, 6)),
        "story-c.json": story("story-c.json", range(6, 8)),
        "sources.json": {
            "format": "lux-content/2", "file": "sources.json", "language": "en",
            "names_kept_out_of_statements": ["QEMU"],
            "firmware_sources": [{"id": "fw-sec", "path": "OvmfPkg/Sec/SecMain.c",
                                  "url": "https://example.org/OvmfPkg/Sec/SecMain.c"}],
            "glossary": [{"id": "hash", "term": "Hash", "also": ["digest"],
                          "definition": "A short value computed from data.", "basis": "recording",
                          "run": "normal-1", "field": "events"}],
        },
    }


RECORDINGS = _recordings()


def _rules(content: dict, readme: str = None) -> list:
    return sorted({problem.rule for problem in check_content.Checker(content, RECORDINGS, readme).run()})


def _first(content: dict, number: int = 4) -> dict:
    """The screen of stop `number` in the small content."""
    for name in check_content.STORY_FILES:
        for stop in content[name]["stops"]:
            if stop["number"] == number:
                return stop["screens"][0]
    raise AssertionError(number)


class CommittedContent(unittest.TestCase):
    def test_the_committed_content_passes(self) -> None:
        problems, summary = check_content.check_repository(helpers.REPOSITORY)
        self.assertEqual([], [str(problem) for problem in problems])
        self.assertEqual(7, sum(len(doc.get("stops", [])) for doc in check_content.load_repository(helpers.REPOSITORY)[0].values()))
        self.assertGreater(summary["claims"], 100)

    def test_the_seven_headlines_exist_and_fit(self) -> None:
        content = check_content.load_repository(helpers.REPOSITORY)[0]
        headlines = []
        for name in check_content.STORY_FILES:
            for stop in content[name]["stops"]:
                screen = next(s for s in stop["screens"] if s["id"] == stop["headline"])
                headlines.append(screen["statement"]["text"])
        self.assertEqual(7, len(headlines))
        self.assertTrue(all(len(text.split()) <= 14 for text in headlines), headlines)

    def test_stops_one_and_two_claim_no_event(self) -> None:
        content = check_content.load_repository(helpers.REPOSITORY)[0]["story-a.json"]
        self.assertFalse(content["stops"][0]["screens"][0]["evidence"]["recorded"])
        self.assertEqual([], content["stops"][0]["mapping"]["rules"])
        self.assertEqual([], content["stops"][1]["mapping"]["rules"])

    def test_main_returns_zero_for_the_repository(self) -> None:
        with redirect_stdout(io.StringIO()) as out:
            code = check_content.main(["check_content.py", str(helpers.REPOSITORY)])
        self.assertEqual(0, code)
        self.assertIn("passed, no problems", out.getvalue())

    def test_main_returns_one_for_a_broken_copy(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            shutil.copytree(helpers.REPOSITORY / "content", root / "content")
            shutil.copytree(helpers.REPOSITORY / "recordings", root / "recordings")
            path = root / "content" / "story-a.json"
            doc = json.loads(path.read_text(encoding="utf-8"))
            doc["stops"][2]["screens"][0]["evidence"]["text"] += " "
            path.write_text(json.dumps(doc), encoding="utf-8")
            with redirect_stdout(io.StringIO()) as out:
                code = check_content.main(["check_content.py", str(root)])
        self.assertEqual(1, code)
        self.assertIn("[evidence]", out.getvalue())
        self.assertIn("FAILED, 1 problem(s)", out.getvalue())


class SmallContent(unittest.TestCase):
    def setUp(self) -> None:
        self.content = _content()

    def test_the_small_content_passes(self) -> None:
        self.assertEqual([], [str(p) for p in check_content.Checker(self.content, RECORDINGS).run()])

    # ---- claims and citations

    def test_a_claim_without_a_basis_fails(self) -> None:
        del _first(self.content)["claims"][0]["basis"]
        self.assertEqual(["claim"], _rules(self.content))

    def test_an_unknown_basis_fails(self) -> None:
        _first(self.content)["claims"][0]["basis"] = "the-specification"
        self.assertEqual(["claim"], _rules(self.content))

    def test_a_screen_without_claims_fails(self) -> None:
        _first(self.content)["claims"] = []
        self.assertEqual(["claim"], _rules(self.content))

    def test_a_uefi_basis_with_a_full_citation_passes(self) -> None:
        for basis in ("uefi-required", "uefi-platform"):
            _first(self.content)["claims"].append({"text": "Control passes to the boot manager.", "basis": basis,
                                                   "citation": dict(CITATION, pdf_pages=[152, 153])})
        self.assertEqual([], _rules(self.content))

    def test_a_uefi_basis_without_a_citation_fails(self) -> None:
        for basis in ("uefi-required", "uefi-platform"):
            content = _content()
            _first(content)["claims"].append({"text": "Control passes to the boot manager.", "basis": basis})
            self.assertEqual(["citation"], _rules(content), basis)

    def test_each_missing_part_of_a_citation_fails(self) -> None:
        for key in check_content.CITATION_KEYS:
            content = _content()
            citation = dict(CITATION)
            del citation[key]
            _first(content)["claims"].append({"text": "A requirement.", "basis": "uefi-required", "citation": citation})
            self.assertEqual(["citation"], _rules(content), key)

    def test_a_wrong_version_or_a_page_as_text_fails(self) -> None:
        for change in ({"version": "2.10"}, {"document": "PI Specification"}, {"pdf_page": "152"},
                       {"pdf_page": 0}, {"pdf_page": 2302}, {"pdf_pages": [150, 151]}, {"section": ""}):
            content = _content()
            _first(content)["claims"].append({"text": "A requirement.", "basis": "uefi-required",
                                              "citation": dict(CITATION, **change)})
            self.assertEqual(["citation"], _rules(content), change)

    def test_a_citation_on_an_unread_document_fails(self) -> None:
        for basis in ("tcg-unread", "this-firmware", "recording", "general"):
            content = _content()
            claim = {"text": "Register 7 holds the policy.", "basis": basis, "citation": dict(CITATION),
                     "source": "observed in recording normal-1 event 4", "run": "normal-1", "field": "events"}
            _first(content)["claims"].append(claim)
            self.assertIn("citation", _rules(content), basis)

    def test_a_pointer_away_from_uefi_is_allowed_and_checked(self) -> None:
        claim = {"text": "Which register is used is not stated in UEFI 2.11.", "basis": "tcg-unread",
                 "uefi_pointer": dict(CITATION)}
        _first(self.content)["claims"].append(claim)
        self.assertEqual([], _rules(self.content))
        del claim["uefi_pointer"]["title"]
        self.assertEqual(["citation"], _rules(self.content))

    def test_this_firmware_needs_an_observation_or_a_confirmed_file(self) -> None:
        good = [{"source": "observed in recording normal-1 event 25"},
                {"source": "observed in recordings normal-1 and e2"},
                {"source": "OvmfPkg/Sec/SecMain.c", "source_ref": "fw-sec"}]
        bad = [{}, {"source": "OvmfPkg/Sec/SecMain.c"}, {"source": "observed in recording normal-9 event 1"},
               {"source": "OvmfPkg/Other.c", "source_ref": "fw-sec"}, {"source": "OvmfPkg/Sec/SecMain.c", "source_ref": "fw-none"},
               {"source": "common knowledge"}]
        for extra in good:
            content = _content()
            _first(content)["claims"].append(dict({"text": "This firmware did it.", "basis": "this-firmware"}, **extra))
            self.assertEqual([], _rules(content), extra)
        for extra in bad:
            content = _content()
            _first(content)["claims"].append(dict({"text": "This firmware did it.", "basis": "this-firmware"}, **extra))
            self.assertEqual(["claim"], _rules(content), extra)

    def test_a_recording_claim_needs_a_real_run_and_field(self) -> None:
        for change in ({"run": "normal-9"}, {"run": "normal-1, e9"}, {"field": "no_such_field"}, {"field": ""},
                       {"file": "recordings/none.json"}):
            content = _content()
            _first(content)["claims"][0].update(change)
            self.assertEqual(["claim"], _rules(content), change)
        _first(self.content)["claims"][0].update({"run": "normal-1, e2", "field": "events[3].pcr and console[0]"})
        self.assertEqual([], _rules(self.content))

    def test_too_many_general_claims_fail(self) -> None:
        _first(self.content)["claims"] += [{"text": "Background.", "basis": "general"}] * 3
        self.assertEqual(["general"], _rules(self.content))

    # ---- wording

    def test_the_specification_says_on_an_unread_or_firmware_claim_fails(self) -> None:
        phrases = ["The specification says register 7 holds the policy.",
                   "UEFI 2.11 requires the loader to be measured into register 4.",
                   "The spec states that a separator follows.",
                   "Register 4 is required by the specification for the loader.",
                   "As the specification defines, the event goes to register 5.",
                   "The firmware measures the loader as specified.",
                   "According to UEFI 2.11 the boot attempt is logged."]
        for basis, extra in (("tcg-unread", {}), ("this-firmware", {"source": "observed in recording normal-1 event 26"})):
            for phrase in phrases:
                content = _content()
                _first(content)["claims"].append(dict({"text": phrase, "basis": basis}, **extra))
                self.assertEqual(["phrase"], _rules(content), (basis, phrase))

    def test_the_phrase_is_also_caught_in_a_note_and_a_definition(self) -> None:
        _first(self.content)["claims"].append({"text": "Register 7 holds the policy.", "basis": "tcg-unread",
                                               "note": "The specification says so."})
        self.assertEqual(["phrase"], _rules(self.content))
        content = _content()
        _first(content)["detail"]["definitions"].append(
            {"term": "Separator", "definition": "An event the specification requires.", "basis": "tcg-unread"})
        self.assertEqual(["phrase"], _rules(content))

    def test_saying_that_the_specification_is_silent_is_allowed(self) -> None:
        for text in ("UEFI 2.11 states no rule for measuring boot events.",
                     "The specification does not say which register is used.",
                     "Which register is used is not stated in UEFI 2.11.",
                     "UEFI 2.11 defines nothing here and points to another document."):
            content = _content()
            _first(content)["claims"].append({"text": text, "basis": "tcg-unread"})
            self.assertEqual([], _rules(content), text)

    def test_the_phrase_is_allowed_where_the_specification_was_read(self) -> None:
        _first(self.content)["claims"].append({"text": "The specification says control passes to the boot manager.",
                                               "basis": "uefi-required", "citation": dict(CITATION)})
        self.assertEqual([], _rules(self.content))

    def test_a_stage_name_on_a_uefi_requirement_fails(self) -> None:
        for name in ("SEC", "PEI", "DXE", "BDS"):
            content = _content()
            _first(content)["claims"].append({"text": "The %s phase must load drivers." % name,
                                              "basis": "uefi-required", "citation": dict(CITATION)})
            self.assertEqual(["stage"], _rules(content), name)

    def test_a_stage_name_must_be_attributed_as_unread(self) -> None:
        stage = {"name": "DXE", "expansion": "Driver Execution Environment",
                 "attribution": "A name from the firmware's source and from the Platform Initialization "
                                "specification, which was not read for this project.", "claims": []}
        self.content["story-b.json"]["stops"][0]["stage_name"] = stage
        self.assertEqual([], _rules(self.content))
        stage["attribution"] = "Defined by the Platform Initialization specification."
        self.assertEqual(["stage"], _rules(self.content))

    def test_a_forbidden_character_fails_anywhere(self) -> None:
        for character in (chr(0x2014), chr(0x2013), chr(0x2015), chr(0xFFFD), chr(0x07), chr(0x85)):
            content = _content()
            _first(content)["detail"]["explanation"] = "First sentence %s still first. Second sentence." % character
            self.assertEqual(["character"], _rules(content), hex(ord(character)))
        content = _content()
        content["sources.json"]["a%skey" % chr(0x2014)] = 1
        self.assertEqual(["character"], _rules(content))
        self.assertEqual(["character"], _rules(_content(), readme="A rule %s with an em-dash." % chr(0x2014)))
        self.assertEqual([], _rules(_content(), readme="A rule, with a comma.\n\tAnd a tab."))

    def test_a_product_name_in_a_statement_or_support_fails(self) -> None:
        _first(self.content)["statement"] = {"text": "QEMU starts the firmware.", "emphasis": None}
        self.assertEqual(["names"], _rules(self.content))
        content = _content()
        _first(content)["support"] = "The machine is emulated by qemu."
        self.assertEqual(["names"], _rules(content))

    # ---- statement and support

    def test_a_statement_of_fourteen_words_passes_and_fifteen_fails(self) -> None:
        fourteen = "one two three four five six seven eight nine ten eleven twelve thirteen fourteen."
        _first(self.content)["statement"] = {"text": fourteen, "emphasis": None}
        self.assertEqual([], _rules(self.content))
        _first(self.content)["statement"]["text"] = "zero " + fourteen
        self.assertEqual(["statement"], _rules(self.content))

    def test_a_missing_statement_or_a_foreign_emphasis_fails(self) -> None:
        for statement in (None, "A bare string.", {"text": ""}, {"text": "Firmware runs.", "emphasis": "loader"},
                          {"text": "Firmware runs.", "emphasis": ""}):
            content = _content()
            _first(content)["statement"] = statement
            self.assertEqual(["statement"], _rules(content), statement)

    def test_support_is_one_sentence_of_at_most_thirty_words(self) -> None:
        thirty = " ".join(["word"] * 29) + " end."
        _first(self.content)["support"] = thirty
        self.assertEqual([], _rules(self.content))
        for support in ("more " + thirty, "One sentence. Two sentences.", "No full stop", ""):
            content = _content()
            _first(content)["support"] = support
            self.assertEqual(["support"], _rules(content), support)
        content = _content()
        _first(content)["support"] = None
        self.assertEqual([], _rules(content))

    # ---- evidence

    def test_an_evidence_line_that_differs_by_one_character_fails(self) -> None:
        for change in (lambda text: text + ".", lambda text: text.upper(), lambda text: text.replace(",", ""),
                       lambda text: " " + text):
            content = _content()
            evidence = _first(content)["evidence"]
            evidence["text"] = change(evidence["text"])
            self.assertEqual(["evidence"], _rules(content), evidence["text"])

    def test_an_evidence_line_from_the_wrong_place_fails(self) -> None:
        for change in ({"position": 5}, {"field": "events[5].summary"}, {"field": "events[4].type"},
                       {"event_index": 4}, {"run": "e9"}, {"file": PILOT}, {"kind": "console"},
                       {"field": "events[99].summary", "position": 99}, {"recorded": "yes"}):
            content = _content()
            _first(content)["evidence"].update(change)
            self.assertEqual(["evidence"], _rules(content), change)

    def test_a_console_line_and_a_loader_report_line_are_checked_too(self) -> None:
        line = RECORDINGS[PILOT]["console"][1]
        _first(self.content)["evidence"] = {"recorded": True, "kind": "console", "run": "e2", "file": PILOT,
                                            "field": "console[1]", "position": 1, "text": line,
                                            "highlight": "Access Denied"}
        self.assertEqual([], _rules(self.content))
        _first(self.content)["evidence"]["highlight"] = "Access Granted"
        self.assertEqual(["evidence"], _rules(self.content))
        report = RECORDINGS[NORMAL]["loader_report"][10]
        content = _content()
        _first(content)["evidence"] = {"recorded": True, "kind": "loader_report", "run": "normal-1", "file": NORMAL,
                                       "field": "loader_report[10]", "position": 10, "text": report}
        self.assertEqual([], _rules(content))
        _first(content)["evidence"]["text"] = report.lower()
        self.assertEqual(["evidence"], _rules(content))

    def test_missing_evidence_fails_and_unrecorded_evidence_must_say_so(self) -> None:
        for evidence in (None, {"recorded": False, "kind": "not-recorded"},
                         {"recorded": False, "kind": "not-recorded", "label": "Not recorded.", "text": "made up"}):
            content = _content()
            _first(content)["evidence"] = evidence
            self.assertEqual(["evidence"], _rules(content), evidence)

    def test_both_sides_of_a_comparison_need_recorded_evidence(self) -> None:
        screen = _first(self.content)
        side = {"id": "baseline", "statement": {"text": "Untouched, it starts.", "emphasis": None},
                "evidence": screen["evidence"]}
        screen.update({"kind": "side-by-side", "evidence": None, "sides": [side, dict(side, id="changed")]})
        self.assertEqual([], _rules(self.content))
        screen["sides"][1] = dict(side, id="changed", evidence={"recorded": False, "kind": "not-recorded", "label": "None."})
        self.assertEqual(["evidence"], _rules(self.content))
        screen["sides"] = [side]
        self.assertEqual(["evidence"], _rules(self.content))

    # ---- detail and definitions

    def test_detail_must_name_lines_events_and_registers_that_exist(self) -> None:
        for key, group in (("console_lines", {"run": "normal-1", "positions": [10]}),
                           ("console_lines", {"run": "e2", "positions": [4]}),
                           ("loader_report_lines", {"run": "e2", "positions": [0]}),
                           ("events", {"run": "normal-1", "indexes": [0]}),
                           ("events", {"run": "e2", "indexes": [27]}),
                           ("events", {"run": "normal-9", "indexes": [1]}),
                           ("pcrs", {"run": "normal-1", "bank": "sha256", "registers": [24]}),
                           ("pcrs", {"run": "normal-1", "bank": "md5", "registers": [0]}),
                           ("pcrs", {"run": "normal-1", "bank": "sha256", "registers": []})):
            content = _content()
            _first(content)["detail"][key] = [group]
            self.assertEqual(["detail"], _rules(content), (key, group))

    def test_the_explanation_has_two_to_four_sentences(self) -> None:
        for count, expected in ((1, ["detail"]), (2, []), (4, []), (5, ["detail"])):
            content = _content()
            _first(content)["detail"]["explanation"] = " ".join(["A sentence about UEFI 2.11 here."] * count)
            self.assertEqual(expected, _rules(content), count)

    def test_definitions_point_at_the_glossary_or_define_a_new_term(self) -> None:
        for definition in ({"glossary": "no-such-entry"}, {"term": "Hash", "definition": "Defined again."},
                           {"term": "digest", "definition": "A glossary name defined again."},
                           {"term": "No text"}, {"glossary": "hash"}, "hash"):
            content = _content()
            _first(content)["detail"]["definitions"].append(definition)
            self.assertEqual(["definition"], _rules(content), definition)

    def test_one_term_has_one_definition_across_screens(self) -> None:
        _first(self.content, 6)["detail"]["definitions"][1]["definition"] = "Other words."
        self.assertEqual(["definition"], _rules(self.content))

    def test_a_glossary_entry_needs_a_basis_and_unique_names(self) -> None:
        glossary = self.content["sources.json"]["glossary"]
        del glossary[0]["basis"]
        self.assertEqual(["claim"], _rules(self.content))
        content = _content()
        content["sources.json"]["glossary"].append({"id": "digest", "term": "Digest", "definition": "Again.", "basis": "general"})
        self.assertIn("definition", _rules(content))

    # ---- stops and pictures

    def test_each_missing_stop_number_fails(self) -> None:
        for number in range(1, 8):
            content = _content()
            for name in check_content.STORY_FILES:
                content[name]["stops"] = [stop for stop in content[name]["stops"] if stop["number"] != number]
            problems = check_content.Checker(content, RECORDINGS).run()
            self.assertIn("stop %d is missing" % number, [p.message for p in problems if p.rule == "stop"], number)

    def test_a_repeated_or_misplaced_stop_fails(self) -> None:
        self.content["story-b.json"]["stops"].append(copy.deepcopy(self.content["story-b.json"]["stops"][0]))
        self.assertIn("stop", _rules(self.content))
        content = _content()
        content["story-a.json"]["stops"].reverse()
        self.assertIn("stop", _rules(content))
        content = _content()
        content["story-a.json"]["stops"][0]["number"] = 8
        self.assertIn("stop", _rules(content))

    def test_a_missing_story_file_fails(self) -> None:
        del self.content["story-c.json"]
        rules = _rules(self.content)
        self.assertIn("format", rules)
        self.assertIn("stop", rules)

    def test_a_malformed_stop_fails(self) -> None:
        for change in ({"of": 6}, {"id": "stop-x"}, {"label": ""}, {"headline": "s9"}, {"not_shown": []},
                       {"threads": ["third-thread"]}, {"screens": []}, {"mapping": {"rules": []}},
                       {"mapping": {"rules": ["pcr0-firmware"], "rests_on": "Log order."}}):
            content = _content()
            content["story-b.json"]["stops"][0].update(change)
            self.assertIn("stop", _rules(content), change)
        content = _content()
        del content["story-b.json"]["stops"][0]["stage_name"]
        self.assertEqual(["stop"], _rules(content))
        content = _content()
        _first(content)["stop"] = 5
        self.assertEqual(["stop"], _rules(content))

    def test_light_never_goes_out_along_the_story(self) -> None:
        picture = _first(self.content, 5)["picture"]
        picture["lit"] = ["power", "firmware"]
        picture["newly_lit"] = []
        self.assertEqual(["picture"], _rules(self.content))

    def test_a_malformed_picture_fails(self) -> None:
        for change in ({"plate": "poster"}, {"screen": "noon"}, {"screen": "dawn"}, {"note": ""}, {"newly_lit": []},
                       {"lit": PARTS[:4] + ["speaker"], "newly_lit": ["controllers", "speaker"]}, {"lit": None}):
            content = _content()
            _first(content)["picture"].update(change)
            self.assertIn("picture", _rules(content), change)
        content = _content()
        _first(content)["picture"] = None
        self.assertIn("picture", _rules(content))

    def test_a_wrong_header_kind_or_repeated_id_fails(self) -> None:
        for key, value in (("format", "lux-content/1"), ("language", "de"), ("file", "other.json")):
            content = _content()
            content["story-a.json"][key] = value
            self.assertEqual(["format"], _rules(content), key)
        content = _content()
        _first(content)["kind"] = "poster"
        self.assertEqual(["format"], _rules(content))
        content = _content()
        _first(content, 5)["id"] = "s4"
        content["story-b.json"]["stops"][1]["headline"] = "s4"
        self.assertEqual(["format"], _rules(content))


if __name__ == "__main__":
    unittest.main()
