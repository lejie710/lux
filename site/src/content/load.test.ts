// The content, as the site reads it: every screen of the story has what the scene needs.
import { describe, expect, it } from "vitest";
import {
  BASIS_LABELS,
  OPENING,
  PICTURE_NOTE,
  STOPS,
  allScreens,
  basisLabel,
  claimNumbers,
  claimSource,
  define,
  headline,
  RUNS,
  recordedEvent,
  recordedLine,
  recordedRegister,
  screenProblems,
  shortened,
  stop,
} from "./load";
import { BASES, type Screen } from "./types";

describe("the story", () => {
  it("holds the opening and stops 1 to 7, in order, from the three story files", () => {
    expect(OPENING.kind).toBe("opening");
    expect(STOPS.map((s) => s.number)).toEqual([1, 2, 3, 4, 5, 6, 7]);
    expect(allScreens()).toHaveLength(1 + STOPS.reduce((sum, s) => sum + s.screens.length, 0));
    expect(new Set(allScreens().map((screen) => screen.id)).size).toBe(allScreens().length);
  });

  it("ends on the one closing screen, which carries the way on to the earlier site", () => {
    const last = allScreens().at(-1)!;
    expect(last.kind).toBe("closing");
    expect(last.handover?.text).toBeTruthy();
    expect(last.handover?.link_label).toBeTruthy();
    expect(allScreens().filter((screen) => screen.handover)).toHaveLength(1);
  });

  it("marks every pilot screen with the sentence that says it is not counted", () => {
    const pilots = allScreens().filter((screen) => screen.kind === "pilot");
    expect(pilots.length).toBeGreaterThan(0);
    for (const pilot of pilots) expect(pilot.pilot_label).toMatch(/not counted/);
  });

  it.each(allScreens().map((screen) => [screen.id, screen] as const))("%s has what the scene needs", (_, screen) => {
    expect(screenProblems(screen)).toEqual([]);
  });

  it("gives every stop a headline screen, a label and a note on what is not shown", () => {
    for (const s of STOPS) {
      expect(headline(s).stop).toBe(s.number);
      expect(s.label).not.toBe("");
      expect(s.not_shown.length).toBeGreaterThan(0);
    }
  });

  it("gives the opening its title, invitation and scope note", () => {
    expect(OPENING.title.text).not.toBe("");
    expect(OPENING.invitation.label).not.toBe("");
    expect(OPENING.invitation.line).not.toBe("");
    expect(OPENING.scope_note).not.toBe("");
    expect(OPENING.support).not.toBeNull();
  });

  it("marks stop 1 as described, not recorded", () => {
    const evidence = headline(stop(1)).evidence;
    expect(evidence.recorded).toBe(false);
    expect(!evidence.recorded && evidence.label).toMatch(/not recorded/);
  });
});

describe("the recordings the story quotes", () => {
  it("has the two runs the story names", () => {
    expect(RUNS).toContain("normal-1");
    expect(RUNS).toContain("e2");
  });

  it("reads a console line and a line of the loader's report by their place, from 0", () => {
    expect(recordedLine("normal-1", "console", 0)).toMatch(/^BdsDxe: loading /);
    expect(recordedLine("normal-1", "loader_report", 0)).toMatch(/^LUX CFG /);
    expect(() => recordedLine("normal-1", "console", 999)).toThrow(/no console line 999/);
    expect(() => recordedLine("no-such-run", "console", 0)).toThrow(/no-such-run/);
  });

  it("quotes every evidence line of the console letter for letter", () => {
    for (const screen of allScreens()) {
      const evidence = screen.evidence;
      if (evidence.recorded && evidence.kind !== "event")
        expect(recordedLine(evidence.run, evidence.kind, evidence.position)).toBe(evidence.text);
    }
  });

  it("reads a register's value at the end of the run, in the bank that is asked for", () => {
    expect(recordedRegister("normal-1", "sha256", 7)).toMatch(/^[0-9a-f]{64}$/i);
    expect(recordedRegister("normal-1", "sha256", 7)).not.toBe(recordedRegister("e2", "sha256", 7));
    expect(() => recordedRegister("normal-1", "sha256", 24)).toThrow(/no register 24/);
  });

  it("gives every record its fingerprint, whole", () => {
    expect(recordedEvent("normal-1", 1).digest_sha256).toMatch(/^[0-9a-f]{64}$/);
  });

  it("shortens a long value to its two ends and leaves a short one alone", () => {
    expect(shortened("0123456789abcdef0123456789abcdef")).toBe("01234567...89abcdef");
    expect(shortened("abc")).toBe("abc");
  });
});

describe("screenProblems", () => {
  const good = headline(stop(1));
  const broken = (change: Partial<Screen>) => screenProblems({ ...good, ...change });

  it("names a missing statement, claim list and picture", () => {
    expect(broken({ statement: { text: "", emphasis: null } })).toContain("no statement");
    expect(broken({ claims: [] })).toContain("no claims");
    expect(broken({ picture: undefined as never })).toContain("no picture");
  });
  it("refuses an emphasis that is not in the statement", () => {
    expect(broken({ statement: { text: "One thing.", emphasis: "another" } })).not.toEqual([]);
  });
  it("refuses a definition that points at no glossary entry", () => {
    const detail = { ...good.detail, definitions: [{ glossary: "no-such-term" }] };
    expect(broken({ detail }).join()).toMatch(/unknown glossary entry no-such-term/);
  });
  it("refuses a part the board does not have, and a claim with an unknown basis", () => {
    const picture = { ...good.picture, lit: ["power", "fan"] as never };
    expect(broken({ picture })).toContain("unknown part fan");
    expect(broken({ claims: [{ text: "x", basis: "rumour" as never }] })).toContain("claim with unknown basis rumour");
  });
  it("refuses an evidence line that is not the recorded event's own", () => {
    const evidence = { ...OPENING.evidence, text: "something else" } as Screen["evidence"];
    expect(screenProblems({ ...OPENING, evidence }).join()).toMatch(/not the event's summary/);
  });
});

describe("the shared lists", () => {
  it("labels every basis", () => {
    for (const basis of BASES) expect(basisLabel(basis).label).not.toBe("");
    expect(BASIS_LABELS).toHaveLength(BASES.length);
    expect(() => basisLabel("rumour")).toThrow();
  });
  it("resolves a glossary pointer and passes a local definition through", () => {
    expect(define({ glossary: "reset" }).term).toBe("Reset");
    expect(define({ term: "t", definition: "d" })).toEqual({ term: "t", definition: "d" });
  });
  it("has the note that goes under every picture", () => {
    expect(PICTURE_NOTE).toMatch(/illustration/i);
    expect(PICTURE_NOTE).toMatch(/recording/);
  });
  it("reads an event's register and type from the recording", () => {
    const last = recordedEvent("normal-1", 28);
    expect(last.summary).toBe(OPENING.evidence.recorded && OPENING.evidence.text);
    expect(typeof last.pcr).toBe("number");
    expect(last.type).toMatch(/^EV_/);
    expect(() => recordedEvent("normal-1", 99)).toThrow();
    expect(() => recordedEvent("no-such-run", 1)).toThrow();
  });
});

describe("claim numbers and sources", () => {
  it("counts claims through the story in reading order, without gaps", () => {
    let next = 1;
    for (const screen of allScreens()) {
      expect(claimNumbers(screen.id)).toEqual({ first: next, last: next + screen.claims.length - 1 });
      next += screen.claims.length;
    }
  });
  it("says where every claim comes from, except general background and unread documents", () => {
    for (const screen of allScreens())
      for (const claim of screen.claims) {
        if (claim.basis === "general") expect(claimSource(claim)).toBe("");
        else if (claim.basis !== "tcg-unread") expect(claimSource(claim)).not.toBe("");
      }
  });
  it("cites a specification by section, title and PDF page", () => {
    const cited = headline(stop(1)).claims.find((claim) => claim.citation)!;
    expect(claimSource(cited)).toBe(
      `UEFI Specification 2.11, section ${cited.citation!.section}, ${cited.citation!.title}. PDF page ${cited.citation!.pdf_page}`,
    );
  });
});
