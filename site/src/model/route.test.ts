// The address after the hash sign, and the page it names.
import { describe, expect, it } from "vitest";
import { filterGlossary } from "./glossary";
import { STORY, hrefOf, readRoute, sectionId } from "./route";

describe("the page an address names", () => {
  it("is the story for no hash, for a step of the story and for anything unknown", () => {
    for (const hash of ["", "#", "#top", "#step-4", "#overview", "#/", "#/nowhere", "#/experiments/Bad Name"])
      expect(readRoute(hash), hash).toEqual(STORY);
  });

  it("is the experiments or the sources page, at its top or at a section", () => {
    expect(readRoute("#/experiments")).toEqual({ page: "experiments", section: null, card: null, evidence: false });
    expect(readRoute("#/sources/")).toEqual({ page: "sources", section: null, card: null, evidence: false });
    expect(readRoute("#/sources/glossary")).toMatchObject({ page: "sources", section: "glossary", evidence: false });
  });

  it("opens the evidence of a section, or of one card of it, when the address ends so", () => {
    expect(readRoute("#/experiments/experiment-e2/evidence")).toEqual({
      page: "experiments",
      section: "experiment-e2",
      card: null,
      evidence: true,
    });
    expect(readRoute("#/experiments/experiments-pilots/e1/evidence")).toMatchObject({
      section: "experiments-pilots",
      card: "e1",
      evidence: true,
    });
    expect(readRoute("#/experiments/evidence").evidence).toBe(false);
  });

  it("writes the address it reads", () => {
    expect(hrefOf("story")).toBe("#top");
    expect(hrefOf("story", "step-3")).toBe("#step-3");
    expect(readRoute(hrefOf("experiments")).page).toBe("experiments");
    expect(readRoute(hrefOf("sources", "limits"))).toMatchObject({ page: "sources", section: "limits" });
    expect(sectionId("limits")).toBe("at-limits");
  });
});

describe("the glossary's filter", () => {
  const entries = [
    { term: "Register (PCR)", also: ["TPM register"], definition: "One of the registers." },
    { term: "Loader", also: [], definition: "The program firmware starts." },
  ];

  it("matches everything while nothing is typed", () => {
    expect(filterGlossary(entries, "  ")).toHaveLength(2);
  });

  it("looks in the term, its other names and its definition, without regard to case", () => {
    expect(filterGlossary(entries, "pcr").map((e) => e.term)).toEqual(["Register (PCR)"]);
    expect(filterGlossary(entries, "tpm REGISTER")).toHaveLength(1);
    expect(filterGlossary(entries, "firmware starts").map((e) => e.term)).toEqual(["Loader"]);
  });

  it("needs every word typed, and finds nothing for a word that is nowhere", () => {
    expect(filterGlossary(entries, "loader pcr")).toEqual([]);
    expect(filterGlossary(entries, "zebra")).toEqual([]);
  });
});
