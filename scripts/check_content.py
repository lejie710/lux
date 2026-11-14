#!/usr/bin/env python3
"""Check the site's content files against the rules in content/README.md.

Usage:  python3 scripts/check_content.py [repository root]

Loads every JSON file in content/ and every committed recording, prints one
line per problem and exits 1 if there is any. Standard library only.

The rules, by the code printed in front of each problem:

  format      a file has the wrong format string, language or file name
  character   a forbidden character (em-dash and relatives, control characters)
  statement   a statement is missing, longer than 14 words, or its emphasis
              is not a phrase of the statement
  support     a supporting sentence is longer than 30 words or is not one sentence
  names       a statement or supporting sentence names a product or project
  evidence    an evidence line is missing, or is not found letter for letter
              in the recording, field and position it names
  detail      "Open the evidence" names a line, event or register that does
              not exist, or its explanation is not two to four sentences
  definition  a definition points at no glossary entry, repeats one, or the
              same term is defined in two ways
  claim       a claim has no basis, an unknown basis, or lacks what its basis needs
  citation    a UEFI basis without a full citation, or a citation where none belongs
  phrase      wording such as "the specification says" on a claim whose basis
              is tcg-unread or this-firmware
  stage       a claim cites UEFI 2.11 as the basis for SEC, PEI, DXE or BDS
  stop        a stop number is missing, repeated, or a stop is malformed
  picture     a picture names an unknown part, light goes out along the story,
              or attention is drawn to a part that is not lit
  general     too many claims lean on the basis "general"
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any, Iterator, NamedTuple

FORMAT = "lux-content/2"
STORY_FILES = ("story-a.json", "story-b.json", "story-c.json")
SOURCES_FILE = "sources.json"
STOPS = 7
MAX_STATEMENT_WORDS = 14
MAX_SUPPORT_WORDS = 30
MIN_EXPLANATION_SENTENCES = 2
MAX_EXPLANATION_SENTENCES = 4
MAX_GENERAL_SHARE = 0.10
UEFI_DOCUMENT = "UEFI Specification"
UEFI_VERSION = "2.11"
UEFI_PDF_PAGES = 2301
REGISTERS_PER_BANK = 24

BASES = ("uefi-required", "uefi-platform", "tcg-unread", "this-firmware", "recording", "general")
UEFI_BASES = ("uefi-required", "uefi-platform")
CITATION_KEYS = ("document", "version", "section", "title", "pdf_page")
SCREEN_KINDS = ("opening", "stop", "pilot", "closing", "intro", "side-by-side", "cards", "list",
                "sources-page", "about")
EVIDENCE_KINDS = {"event": "events", "console": "console", "loader_report": "loader_report"}
BOARD_PARTS = ("power", "firmware", "processor", "memory", "controllers", "storage", "security", "ribbon")
PLATES = ("board", "laptop")
SCREEN_STATES = ("none", "dark", "dawn")
THREADS = ("secure-boot", "measured-boot")
STAGE_NAMES = ("SEC", "PEI", "DXE", "BDS")

# Written as escapes so that this file does not contain the characters it forbids.
FORBIDDEN_CHARACTERS = {
    "\u2013": "en dash", "\u2014": "em-dash", "\u2015": "horizontal bar", "\u2212": "minus sign",
    "\ufffd": "replacement character",
}
SENTENCE_END = re.compile(r"[.!?][\"')\]]?(?=\s|$)")
# "the specification says", "UEFI 2.11 requires", "required by the specification", and relatives.
# A denial ("states no rule", "defines nothing") is not an appeal to the specification and is let through.
SPEC_NOUN = r"(?:(?:the\s+)?(?:uefi\s+)?(?:specification|spec|standard)(?:\s+2\.11)?|uefi(?:\s+2\.11)?)"
SPEC_VERB = r"(?:says|states|requires|mandates|demands|specifies|defines|prescribes)"
SPEC_PHRASES = (
    re.compile(SPEC_NOUN + r"\s+" + SPEC_VERB + r"\b(?!\s+(?:no|nothing|neither|none)\b)", re.IGNORECASE),
    re.compile(r"\b(?:required|mandated|specified|defined|prescribed)\s+by\s+" + SPEC_NOUN + r"\b", re.IGNORECASE),
    re.compile(r"\b(?:as|per|according\s+to)\s+" + SPEC_NOUN + r"\b", re.IGNORECASE),
    re.compile(r"\bas\s+specified\b", re.IGNORECASE),
)
OBSERVED = "observed in recording"
RUN_IN_SOURCE = re.compile(r"recordings?\s+([a-z0-9]+(?:-[a-z0-9]+)*)(?:\s+and\s+([a-z0-9]+(?:-[a-z0-9]+)*))?")
FIELD_PATH = re.compile(r"(events|console|loader_report)\[(\d+)\](?:\.(\w+))?$")


class Problem(NamedTuple):
    rule: str
    where: str
    message: str

    def __str__(self) -> str:
        return "[%s] %s: %s" % (self.rule, self.where, self.message)


def words(text: str) -> int:
    return len(text.split())


def sentences(text: str) -> int:
    return len(SENTENCE_END.findall(text.strip()))


def walk(node: Any, where: str) -> Iterator[tuple[str, Any]]:
    """Yield every node of a JSON tree with a readable path."""
    yield where, node
    if isinstance(node, dict):
        for key, value in node.items():
            label = value.get("id") if isinstance(value, dict) else None
            yield from walk(value, "%s.%s%s" % (where, key, "(%s)" % label if label else ""))
    elif isinstance(node, list):
        for position, value in enumerate(node):
            label = value.get("id") if isinstance(value, dict) else None
            yield from walk(value, "%s[%s]" % (where, label if label else position))


def is_claim(node: Any) -> bool:
    return isinstance(node, dict) and "basis" in node and ("text" in node or "definition" in node)


class Checker:
    """Collects problems. `content` maps a file name to its parsed JSON; `recordings`
    maps a repository-relative path (forward slashes) to a parsed recording or comparison."""

    def __init__(self, content: dict[str, Any], recordings: dict[str, Any], readme: str | None = None) -> None:
        self.content = content
        self.recordings = recordings
        self.readme = readme
        self.problems: list[Problem] = []
        self.runs = {path.split("/")[1]: data for path, data in recordings.items()
                     if path.endswith("/recording.json")}
        self.known_fields = {key for data in recordings.values() if isinstance(data, dict) for key in data}
        sources = content.get(SOURCES_FILE) or {}
        self.glossary = {entry.get("id"): entry for entry in sources.get("glossary", []) if isinstance(entry, dict)}
        self.firmware_sources = {entry.get("id"): entry for entry in sources.get("firmware_sources", [])
                                 if isinstance(entry, dict)}
        self.kept_out = [name for name in sources.get("names_kept_out_of_statements", []) if isinstance(name, str)]

    def fail(self, rule: str, where: str, message: str) -> None:
        self.problems.append(Problem(rule, where, message))

    # ------------------------------------------------------------ whole run

    def run(self) -> list[Problem]:
        for name in sorted(self.content):
            self.check_file_header(name, self.content[name])
            self.check_characters(name, self.content[name])
        if self.readme is not None:
            self.check_text_characters("README.md", self.readme)
        for name in (*STORY_FILES, SOURCES_FILE):
            if name not in self.content:
                self.fail("format", name, "the file is missing")
        self.check_stops()
        ids: dict[str, str] = {}
        for name, where, screen in self.screens():
            self.check_screen(name, where, screen)
            if screen.get("id") in ids:
                self.fail("format", where, "the id is also used in %s" % ids[screen["id"]])
            ids.setdefault(screen.get("id"), name)
        self.check_claims()
        self.check_glossary()
        self.check_local_definitions()
        return self.problems

    def screens(self) -> Iterator[tuple[str, str, dict]]:
        """Every screen of every file, in reading order."""
        for name in sorted(self.content):
            doc = self.content[name]
            if not isinstance(doc, dict):
                continue
            found = []
            if isinstance(doc.get("opening"), dict):
                found.append(doc["opening"])
            for stop in doc.get("stops", []) if isinstance(doc.get("stops"), list) else []:
                if isinstance(stop, dict):
                    found.extend(s for s in stop.get("screens", []) if isinstance(s, dict))
            if isinstance(doc.get("screens"), list):
                found.extend(s for s in doc["screens"] if isinstance(s, dict))
            for screen in found:
                yield name, "%s: screen %s" % (name, screen.get("id", "(no id)")), screen

    # ------------------------------------------------------------ files

    def check_file_header(self, name: str, doc: Any) -> None:
        if not isinstance(doc, dict):
            self.fail("format", name, "the file is not a JSON object")
            return
        if doc.get("format") != FORMAT:
            self.fail("format", name, "format is %r, expected %r" % (doc.get("format"), FORMAT))
        if doc.get("language") != "en":
            self.fail("format", name, "language is %r, expected 'en'" % doc.get("language"))
        if doc.get("file") != name:
            self.fail("format", name, "file is %r, expected %r" % (doc.get("file"), name))

    def check_characters(self, name: str, doc: Any) -> None:
        for where, node in walk(doc, name):
            if isinstance(node, str):
                self.check_text_characters(where, node)
            elif isinstance(node, dict):
                for key in node:
                    self.check_text_characters(where, key)

    def check_text_characters(self, where: str, text: str) -> None:
        for character in sorted(set(text)):
            code = ord(character)
            if character in FORBIDDEN_CHARACTERS:
                self.fail("character", where, "contains %s (U+%04X)" % (FORBIDDEN_CHARACTERS[character], code))
            elif (code < 0x20 and character not in "\n\t") or 0x7F <= code <= 0x9F:
                self.fail("character", where, "contains a control character (U+%04X)" % code)

    # ------------------------------------------------------------ stops

    def check_stops(self) -> None:
        seen: dict[int, str] = {}
        lit: set[str] = set()
        for name in STORY_FILES:
            doc = self.content.get(name)
            if not isinstance(doc, dict):
                continue
            if isinstance(doc.get("opening"), dict):
                lit = self.check_picture("%s: screen opening" % name, doc["opening"].get("picture"), lit, True)
            for stop in doc.get("stops", []):
                where = "%s: stop %s" % (name, stop.get("number") if isinstance(stop, dict) else "?")
                if not isinstance(stop, dict) or not isinstance(stop.get("number"), int):
                    self.fail("stop", where, "a stop needs an integer 'number'")
                    continue
                number = stop["number"]
                if number in seen:
                    self.fail("stop", where, "stop %d is also in %s" % (number, seen[number]))
                seen[number] = name
                lit = self.check_stop(where, stop, lit)
        for number in range(1, STOPS + 1):
            if number not in seen:
                self.fail("stop", "story", "stop %d is missing" % number)
        for number in sorted(seen):
            if not 1 <= number <= STOPS:
                self.fail("stop", "story", "stop %d is outside 1 to %d" % (number, STOPS))
        if sorted(seen) != list(seen):
            self.fail("stop", "story", "the stops are not in rising order: %s" % list(seen))

    def check_stop(self, where: str, stop: dict, lit: set[str]) -> set[str]:
        number = stop["number"]
        if stop.get("of") != STOPS:
            self.fail("stop", where, "'of' is %r, expected %d" % (stop.get("of"), STOPS))
        if stop.get("id") != "stop-%d" % number:
            self.fail("stop", where, "id is %r, expected 'stop-%d'" % (stop.get("id"), number))
        if not isinstance(stop.get("label"), str) or not stop["label"].strip():
            self.fail("stop", where, "a stop needs a label")
        stage = stop.get("stage_name", "absent")
        if stage == "absent":
            self.fail("stop", where, "'stage_name' must be present (null when the stop has no stage name)")
        elif stage is not None:
            for key in ("name", "expansion", "attribution"):
                if not isinstance(stage.get(key) if isinstance(stage, dict) else None, str):
                    self.fail("stop", where, "stage_name needs the text field %r" % key)
            if isinstance(stage, dict) and "not read" not in stage.get("attribution", "") \
                    and "was not read" not in stage.get("attribution", ""):
                self.fail("stage", where, "the attribution of a stage name must say that the Platform "
                                          "Initialization specification was not read")
        for thread in stop.get("threads", []):
            if thread not in THREADS:
                self.fail("stop", where, "unknown thread %r" % thread)
        if not isinstance(stop.get("not_shown"), list) or not stop["not_shown"]:
            self.fail("stop", where, "'not_shown' must list at least one thing the recording does not show")
        screens = [s for s in stop.get("screens", []) if isinstance(s, dict)] if isinstance(stop.get("screens"), list) else []
        if not screens:
            self.fail("stop", where, "a stop needs at least one screen")
        if stop.get("headline") not in [s.get("id") for s in screens]:
            self.fail("stop", where, "headline %r is not the id of one of its screens" % stop.get("headline"))
        for screen in screens:
            if screen.get("stop") != number:
                self.fail("stop", "%s, screen %s" % (where, screen.get("id")),
                          "the screen says stop %r" % screen.get("stop"))
            lit = self.check_picture("%s, screen %s" % (where, screen.get("id")), screen.get("picture"), lit, True)
        self.check_mapping(where, stop)
        return lit

    def check_mapping(self, where: str, stop: dict) -> None:
        mapping = stop.get("mapping")
        if not isinstance(mapping, dict) or not isinstance(mapping.get("rules"), list) \
                or not isinstance(mapping.get("rests_on"), str) or not mapping["rests_on"].strip():
            self.fail("stop", where, "'mapping' needs 'rules' (a list) and 'rests_on' (what the mapping rests on)")
            return
        normal = self.runs.get("normal-1")
        if not normal:
            return
        recorded = {event.get("stop_rule") for event in normal.get("events", []) if event.get("stop") == stop["number"]}
        if recorded != set(mapping["rules"]):
            self.fail("stop", where, "mapping rules %s differ from the rules the recording normal-1 stores "
                                     "for this stop, %s" % (sorted(mapping["rules"]), sorted(recorded)))

    def check_picture(self, where: str, picture: Any, lit: set[str], in_story: bool) -> set[str]:
        if picture is None and not in_story:
            return lit
        if not isinstance(picture, dict):
            self.fail("picture", where, "a story screen needs a 'picture' object")
            return lit
        if picture.get("plate") not in PLATES:
            self.fail("picture", where, "plate is %r, expected one of %s" % (picture.get("plate"), list(PLATES)))
        if picture.get("screen") not in SCREEN_STATES:
            self.fail("picture", where, "screen is %r, expected one of %s" % (picture.get("screen"), list(SCREEN_STATES)))
        if (picture.get("plate") == "board") != (picture.get("screen") == "none"):
            self.fail("picture", where, "the board plate shows no screen ('none'); the laptop plate shows one ('dark' or 'dawn')")
        if not isinstance(picture.get("note"), str) or not picture["note"].strip():
            self.fail("picture", where, "a picture needs a note")
        now = picture.get("lit") if isinstance(picture.get("lit"), list) else None
        new = picture.get("newly_lit") if isinstance(picture.get("newly_lit"), list) else None
        if now is None or new is None:
            self.fail("picture", where, "'lit' and 'newly_lit' must be lists")
            return lit
        for part in [*now, *new]:
            if part not in BOARD_PARTS:
                self.fail("picture", where, "unknown part %r" % part)
        if not lit <= set(now):
            self.fail("picture", where, "light goes out: %s lit before, dark here" % sorted(lit - set(now)))
        if set(new) != set(now) - lit:
            self.fail("picture", where, "newly_lit is %s, but the parts new on this screen are %s"
                      % (sorted(new), sorted(set(now) - lit)))
        attention = picture.get("attention", [])
        if not isinstance(attention, list) or not set(attention) <= set(now):
            self.fail("picture", where, "'attention' must be a list of parts that are lit on this screen")
        return set(now)

    # ------------------------------------------------------------ screens

    def check_screen(self, name: str, where: str, screen: dict) -> None:
        if not isinstance(screen.get("id"), str):
            self.fail("format", where, "a screen needs an id")
        if screen.get("kind") not in SCREEN_KINDS:
            self.fail("format", where, "kind is %r, expected one of %s" % (screen.get("kind"), list(SCREEN_KINDS)))
        self.check_statement(where, screen.get("statement"))
        self.check_support(where, screen.get("support"))
        if screen.get("kind") == "side-by-side":
            sides = screen.get("sides")
            if not isinstance(sides, list) or len(sides) != 2:
                self.fail("evidence", where, "a side-by-side screen needs exactly two sides")
                sides = []
            for side in sides:
                side_where = "%s, side %s" % (where, side.get("id") if isinstance(side, dict) else "?")
                if not isinstance(side, dict):
                    self.fail("evidence", side_where, "a side must be an object")
                    continue
                self.check_statement(side_where, side.get("statement"))
                self.check_evidence(side_where, side.get("evidence"), must_be_recorded=True)
        else:
            self.check_evidence(where, screen.get("evidence"), must_be_recorded=False)
        self.check_detail(where, screen.get("detail"))
        claims = screen.get("claims")
        if not isinstance(claims, list) or not claims:
            self.fail("claim", where, "a screen needs at least one claim")
        if name not in STORY_FILES and screen.get("picture") is not None:
            self.check_picture(where, screen["picture"], set(), False)

    def check_statement(self, where: str, statement: Any) -> None:
        if not isinstance(statement, dict) or not isinstance(statement.get("text"), str) or not statement["text"].strip():
            self.fail("statement", where, "the statement must be an object with a non-empty 'text'")
            return
        text = statement["text"]
        if words(text) > MAX_STATEMENT_WORDS:
            self.fail("statement", where, "%d words, the limit is %d: %r" % (words(text), MAX_STATEMENT_WORDS, text))
        emphasis = statement.get("emphasis")
        if emphasis is not None and (not isinstance(emphasis, str) or not emphasis or emphasis not in text):
            self.fail("statement", where, "emphasis %r is not a phrase of the statement" % (emphasis,))
        self.check_names(where, text)

    def check_support(self, where: str, support: Any) -> None:
        if support is None:
            return
        if not isinstance(support, str) or not support.strip():
            self.fail("support", where, "support must be one sentence or null")
            return
        if words(support) > MAX_SUPPORT_WORDS:
            self.fail("support", where, "%d words, the limit is %d" % (words(support), MAX_SUPPORT_WORDS))
        if sentences(support) != 1:
            self.fail("support", where, "must be exactly one sentence, found %d" % sentences(support))
        self.check_names(where, support)

    def check_names(self, where: str, text: str) -> None:
        for name in self.kept_out:
            if re.search(r"(?<![A-Za-z0-9])%s(?![A-Za-z0-9])" % re.escape(name), text, re.IGNORECASE):
                self.fail("names", where, "names %r; product and project names belong in evidence and sources" % name)

    def check_evidence(self, where: str, evidence: Any, must_be_recorded: bool) -> None:
        if not isinstance(evidence, dict):
            self.fail("evidence", where, "the evidence line is missing")
            return
        if evidence.get("recorded") is False:
            if must_be_recorded:
                self.fail("evidence", where, "this evidence line must come from a recording")
            if evidence.get("kind") != "not-recorded" or not isinstance(evidence.get("label"), str) \
                    or not evidence["label"].strip():
                self.fail("evidence", where, "evidence that is not recorded needs kind 'not-recorded' and a label saying so")
            if "text" in evidence or "file" in evidence:
                self.fail("evidence", where, "evidence that is not recorded must not carry a text or a file")
            return
        if evidence.get("recorded") is not True:
            self.fail("evidence", where, "'recorded' must be true or false")
            return
        kind, run, file = evidence.get("kind"), evidence.get("run"), evidence.get("file")
        text, field, position = evidence.get("text"), evidence.get("field"), evidence.get("position")
        if kind not in EVIDENCE_KINDS:
            self.fail("evidence", where, "kind is %r, expected one of %s" % (kind, sorted(EVIDENCE_KINDS)))
            return
        if not isinstance(text, str) or not text:
            self.fail("evidence", where, "the evidence line has no text")
            return
        if file != "recordings/%s/recording.json" % run or file not in self.recordings:
            self.fail("evidence", where, "file %r is not the committed recording of run %r" % (file, run))
            return
        match = FIELD_PATH.match(field) if isinstance(field, str) else None
        if not match or match.group(1) != EVIDENCE_KINDS[kind] or int(match.group(2)) != position \
                or (match.group(3) or None) != ("summary" if kind == "event" else None):
            self.fail("evidence", where, "field %r does not name position %r of %r" % (field, position, EVIDENCE_KINDS[kind]))
            return
        lines = self.recordings[file].get(EVIDENCE_KINDS[kind])
        if not isinstance(lines, list) or not 0 <= position < len(lines):
            self.fail("evidence", where, "%s has no %s" % (file, field))
            return
        found = lines[position]
        if kind == "event":
            if evidence.get("event_index") != found.get("index"):
                self.fail("evidence", where, "event_index is %r, the event at position %d has index %r"
                          % (evidence.get("event_index"), position, found.get("index")))
            found = found.get("summary")
        if found != text:
            self.fail("evidence", where, "the text is not found letter for letter in %s %s: content has %r, "
                                         "the recording has %r" % (file, field, text, found))
        highlight = evidence.get("highlight")
        if highlight is not None and (not isinstance(highlight, str) or highlight not in text):
            self.fail("evidence", where, "highlight %r is not part of the evidence line" % (highlight,))

    def check_detail(self, where: str, detail: Any) -> None:
        if not isinstance(detail, dict):
            self.fail("detail", where, "the detail block for 'Open the evidence' is missing")
            return
        for key, item, size in (("console_lines", "positions", "console"),
                                ("loader_report_lines", "positions", "loader_report"),
                                ("events", "indexes", "events"), ("pcrs", "registers", None)):
            groups = detail.get(key)
            if not isinstance(groups, list):
                self.fail("detail", where, "'%s' must be a list (empty when there is nothing to show)" % key)
                continue
            for group in groups:
                run = group.get("run") if isinstance(group, dict) else None
                values = group.get(item) if isinstance(group, dict) else None
                if run not in self.runs or not isinstance(values, list) or not values \
                        or not all(isinstance(v, int) and not isinstance(v, bool) for v in values):
                    self.fail("detail", where, "%s: each group needs a committed 'run' and a non-empty list '%s'" % (key, item))
                    continue
                recording = self.runs[run]
                if size is None:
                    bank = recording.get("pcrs", {}).get(group.get("bank"))
                    bad = [v for v in values if bank is None or str(v) not in bank]
                elif key == "events":
                    known = {event.get("index") for event in recording.get(size, [])}
                    bad = [v for v in values if v not in known]
                else:
                    bad = [v for v in values if not 0 <= v < len(recording.get(size) or [])]
                if bad:
                    self.fail("detail", where, "%s: run %s has no %s %s" % (key, run, item, bad))
        comparison = detail.get("comparison")
        if comparison is not None and (not isinstance(comparison, dict) or comparison.get("file") not in self.recordings):
            self.fail("detail", where, "comparison names a file that is not committed")
        explanation = detail.get("explanation")
        if not isinstance(explanation, str) or not explanation.strip():
            self.fail("detail", where, "the explanation is missing")
        elif not MIN_EXPLANATION_SENTENCES <= sentences(explanation) <= MAX_EXPLANATION_SENTENCES:
            self.fail("detail", where, "the explanation has %d sentences, expected %d to %d"
                      % (sentences(explanation), MIN_EXPLANATION_SENTENCES, MAX_EXPLANATION_SENTENCES))
        definitions = detail.get("definitions")
        if not isinstance(definitions, list):
            self.fail("definition", where, "'definitions' must be a list")
            return
        used = set()
        for definition in definitions:
            if isinstance(definition, dict) and set(definition) == {"glossary"}:
                key = ("glossary", definition["glossary"])
                if definition["glossary"] not in self.glossary:
                    self.fail("definition", where, "glossary entry %r does not exist" % (definition["glossary"],))
            elif isinstance(definition, dict) and isinstance(definition.get("term"), str) \
                    and isinstance(definition.get("definition"), str) and "glossary" not in definition:
                key = ("local", definition["term"].lower())
            else:
                self.fail("definition", where, "a definition is either {\"glossary\": id} or has 'term' and 'definition'")
                continue
            if key in used:
                self.fail("definition", where, "%s is defined twice on this screen" % (key[1],))
            used.add(key)

    # ------------------------------------------------------------ claims

    def check_claims(self) -> None:
        counts = dict.fromkeys(BASES, 0)
        for name in sorted(self.content):
            for where, node in walk(self.content[name], name):
                if isinstance(node, dict) and isinstance(node.get("claims"), list):
                    for position, claim in enumerate(node["claims"]):
                        if not is_claim(claim) or "text" not in claim:
                            self.fail("claim", "%s.claims[%d]" % (where, position), "a claim needs 'text' and 'basis'")
                if is_claim(node):
                    self.check_claim(where, node)
                    if node.get("basis") in counts:
                        counts[node["basis"]] += 1
        total = sum(counts.values())
        if total and counts["general"] > MAX_GENERAL_SHARE * total:
            self.fail("general", "all files", "%d of %d claims have the basis 'general'; it must stay rare (at most %d%%)"
                      % (counts["general"], total, round(MAX_GENERAL_SHARE * 100)))
        self.claim_counts = counts

    def check_claim(self, where: str, claim: dict) -> None:
        basis = claim.get("basis")
        text = claim.get("text", claim.get("definition"))
        if not isinstance(text, str) or not text.strip():
            self.fail("claim", where, "the claim has no text")
            text = ""
        if basis not in BASES:
            self.fail("claim", where, "basis is %r, expected one of %s" % (basis, list(BASES)))
            return
        if basis in UEFI_BASES:
            self.check_citation(where, claim.get("citation"), "citation")
            if basis == "uefi-required":
                named = [stage for stage in STAGE_NAMES if re.search(r"\b%s\b" % stage, text)]
                if named:
                    self.fail("stage", where, "names %s on a claim that cites UEFI 2.11 as a requirement; these are "
                                              "not UEFI 2.11 terms" % ", ".join(named))
        elif "citation" in claim:
            self.fail("citation", where, "basis %r must not carry a citation" % basis)
        if "uefi_pointer" in claim:
            self.check_citation(where, claim["uefi_pointer"], "uefi_pointer")
        if basis in ("tcg-unread", "this-firmware"):
            for key in ("text", "definition", "note", "reason"):
                value = claim.get(key)
                if not isinstance(value, str):
                    continue
                for pattern in SPEC_PHRASES:
                    match = pattern.search(value)
                    if match:
                        self.fail("phrase", where, "%r in '%s' of a claim whose basis is %s"
                                  % (match.group(0), key, basis))
                        break
        if basis == "this-firmware":
            self.check_firmware_source(where, claim)
        if basis == "recording":
            self.check_recording_claim(where, claim)

    def check_citation(self, where: str, citation: Any, key: str) -> None:
        if not isinstance(citation, dict):
            self.fail("citation", where, "'%s' is missing; it needs %s" % (key, ", ".join(CITATION_KEYS)))
            return
        for field in CITATION_KEYS:
            if field not in citation or citation[field] in ("", None):
                self.fail("citation", where, "%s lacks '%s'" % (key, field))
        if citation.get("document") != UEFI_DOCUMENT or citation.get("version") != UEFI_VERSION:
            self.fail("citation", where, "%s must cite %s, version %s; found %r, %r"
                      % (key, UEFI_DOCUMENT, UEFI_VERSION, citation.get("document"), citation.get("version")))
        for field in ("section", "title"):
            if field in citation and not isinstance(citation[field], str):
                self.fail("citation", where, "%s.%s must be text" % (key, field))
        page = citation.get("pdf_page")
        if "pdf_page" in citation and (isinstance(page, bool) or not isinstance(page, int) or not 1 <= page <= UEFI_PDF_PAGES):
            self.fail("citation", where, "%s.pdf_page must be a whole number from 1 to %d, found %r"
                      % (key, UEFI_PDF_PAGES, page))
        many = citation.get("pdf_pages")
        if many is not None and (not isinstance(many, list) or page not in many or sorted(many) != many
                                 or not all(isinstance(p, int) and 1 <= p <= UEFI_PDF_PAGES for p in many)):
            self.fail("citation", where, "%s.pdf_pages must be a rising list of pages that includes pdf_page" % key)

    def check_firmware_source(self, where: str, claim: dict) -> None:
        source = claim.get("source")
        if not isinstance(source, str) or not source.strip():
            self.fail("claim", where, "basis this-firmware needs a 'source'")
            return
        reference = claim.get("source_ref")
        if reference is not None:
            entry = self.firmware_sources.get(reference)
            if not entry or not str(entry.get("url", "")).startswith("https://"):
                self.fail("claim", where, "source_ref %r is not a firmware source with a URL in %s" % (reference, SOURCES_FILE))
                return
        if source.startswith(OBSERVED):
            named = [run for match in RUN_IN_SOURCE.finditer(source) for run in match.groups() if run]
            missing = [run for run in named if run not in self.runs]
            if not named or missing:
                self.fail("claim", where, "source %r names no committed recording%s"
                          % (source, " (unknown: %s)" % ", ".join(missing) if missing else ""))
        elif reference is None:
            self.fail("claim", where, "source %r is neither '%s <run> ...' nor a file with a source_ref" % (source, OBSERVED))
        elif self.firmware_sources[reference].get("path") != source:
            self.fail("claim", where, "source %r is not the path of source_ref %r" % (source, reference))

    def check_recording_claim(self, where: str, claim: dict) -> None:
        run, field = claim.get("run"), claim.get("field")
        if not isinstance(run, str) or not isinstance(field, str) or not run.strip() or not field.strip():
            self.fail("claim", where, "basis recording needs 'run' and 'field'")
            return
        missing = [name for name in (part.strip() for part in run.split(",")) if name not in self.runs]
        if missing:
            self.fail("claim", where, "run %r names no committed recording (unknown: %s)" % (run, ", ".join(missing)))
        if not any(re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(key), field) for key in self.known_fields):
            self.fail("claim", where, "field %r names no field of a recording or comparison" % field)
        if "file" in claim and claim["file"] not in self.recordings:
            self.fail("claim", where, "file %r is not committed" % (claim["file"],))

    # ------------------------------------------------------------ glossary

    def check_glossary(self) -> None:
        sources = self.content.get(SOURCES_FILE)
        if not isinstance(sources, dict):
            return
        where = "%s: glossary" % SOURCES_FILE
        names: dict[str, str] = {}
        ids = set()
        for entry in sources.get("glossary", []):
            if not isinstance(entry, dict) or not all(isinstance(entry.get(k), str) and entry[k] for k in ("id", "term", "definition")):
                self.fail("definition", where, "an entry needs 'id', 'term' and 'definition'")
                continue
            if entry["id"] in ids:
                self.fail("definition", where, "id %r is used twice" % entry["id"])
            ids.add(entry["id"])
            if "basis" not in entry:
                self.fail("claim", "%s[%s]" % (where, entry["id"]), "a glossary entry needs a basis")
            for name in [entry["term"], *entry.get("also", [])]:
                if name.lower() in names:
                    self.fail("definition", where, "%r is a name of both %r and %r" % (name, names[name.lower()], entry["id"]))
                names[name.lower()] = entry["id"]
        self.glossary_names = names

    def check_local_definitions(self) -> None:
        names = getattr(self, "glossary_names", {})
        texts: dict[str, tuple[str, str]] = {}
        for name, where, screen in self.screens():
            detail = screen.get("detail")
            for definition in detail.get("definitions", []) if isinstance(detail, dict) and isinstance(detail.get("definitions"), list) else []:
                if not isinstance(definition, dict) or not isinstance(definition.get("term"), str) \
                        or not isinstance(definition.get("definition"), str):
                    continue
                term = definition["term"].lower()
                if term in names:
                    self.fail("definition", where, "%r is in the glossary (%s); point to it instead of defining it again"
                              % (definition["term"], names[term]))
                if term in texts and texts[term][0] != definition["definition"]:
                    self.fail("definition", where, "%r is defined differently in %s" % (definition["term"], texts[term][1]))
                texts.setdefault(term, (definition["definition"], where))


def load_repository(root: Path) -> tuple[dict[str, Any], dict[str, Any], str | None]:
    """Read content/*.json, every committed recording and comparison, and content/README.md."""
    content = {path.name: json.loads(path.read_text(encoding="utf-8")) for path in sorted((root / "content").glob("*.json"))}
    recordings = {}
    for path in sorted((root / "recordings").glob("*/*.json")):
        recordings[path.relative_to(root).as_posix()] = json.loads(path.read_text(encoding="utf-8"))
    readme = root / "content" / "README.md"
    return content, recordings, readme.read_text(encoding="utf-8") if readme.exists() else None


def check_repository(root: Path) -> tuple[list[Problem], dict[str, int]]:
    content, recordings, readme = load_repository(root)
    checker = Checker(content, recordings, readme)
    problems = checker.run()
    screens = list(checker.screens())
    summary = {"files": len(content), "screens": len(screens), "claims": sum(checker.claim_counts.values()),
               **{"claims " + basis: count for basis, count in checker.claim_counts.items()},
               "recordings": len(checker.runs), "glossary entries": len(checker.glossary)}
    return problems, summary


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    problems, summary = check_repository(root)
    for problem in problems:
        print(problem)
    print("content check: %s" % ", ".join("%d %s" % (count, label) for label, count in summary.items()))
    print("content check: %s" % ("FAILED, %d problem(s)" % len(problems) if problems else "passed, no problems"))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
