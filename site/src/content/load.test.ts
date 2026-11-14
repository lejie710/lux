// The content, as the site reads it: every screen of the story file has what the scene needs.
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
  recordedEvent,
  screenProblems,
  stop,
} from "./load";
import { BASES, type Screen } from "./types";

describe("the story file", () => {
  it("holds the opening and stops 1 to 3", () => {
    expect(OPENING.kind).toBe("opening");
    expect(STOPS.map((s) => s.number)).toEqual([1, 2, 3]);
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
