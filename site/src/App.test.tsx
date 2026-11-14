// The page in its three modes and the evidence panel, rendered to HTML. No browser is needed, so nothing
// here proves motion or focus in a real window; the panel's key and focus rules are tested in panel.test.ts.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { App } from "./App";
import { EvidencePanel } from "./components/EvidencePanel";
import { EvidencePill, Stage } from "./components/Stage";
import { PICTURE_NOTE, OPENING, basisLabel, claimNumbers, define, headline, stop } from "./content/load";
import { PARTS } from "./content/types";
import { STEPS } from "./model/scene";
import css from "./styles/lux.css?raw";

const count = (html: string, re: RegExp) => [...html.matchAll(re)].length;
/** Text as React writes it into HTML. */
const esc = (text: string) => text.replace(/&/g, "&amp;").replace(/'/g, "&#x27;").replace(/"/g, "&quot;");
const stopOne = headline(stop(1));
const nothing = () => {};

describe("the scrolled page", () => {
  const html = renderToStaticMarkup(<App mode={{ kind: "scroll" }} />);

  it("pins one stage and lays one marker per step under it", () => {
    expect(count(html, /class="stage"/g)).toBe(1);
    expect(count(html, /class="marker"/g)).toBe(STEPS.length);
    expect(html).toContain('<div class="pin">');
  });

  it("keeps every step's words in the page and puts all but the current one out of reach", () => {
    expect(count(html, /class="words /g)).toBe(STEPS.length);
    expect(count(html, /class="words [a-z-]+" data-on="false" inert=""/g)).toBe(STEPS.length - 1);
    expect(html).toContain(esc(OPENING.title.text.split(" ")[0]));
    expect(html).toContain(esc(stopOne.statement.text.split(" its ")[0]));
  });

  it("starts at the opening: the laptop in view, the board and every part dark", () => {
    expect(html).toMatch(/class="laptop"[^>]*data-on="true"/);
    expect(html).toMatch(/class="board" data-on="false"/);
    expect(count(html, /class="lit"/g)).toBe(PARTS.length);
    expect(count(html, /class="lit" data-part="[a-z]+" data-on="true"/g)).toBe(0);
  });

  it("says nothing aloud until the step has changed", () => {
    expect(html).toContain('<p class="sr-only" role="status"></p>');
  });

  it("has the navigation, with the two unbuilt places as text that says so", () => {
    expect(html).toContain('aria-current="location"');
    expect(count(html, /<span class="soon">/g)).toBe(2);
    expect(count(html, /<small>coming<\/small>/g)).toBe(2);
    expect(count(html, /<a /g)).toBe(2);
  });
});

describe("?static: every step as a still section", () => {
  const html = renderToStaticMarkup(<App mode={{ kind: "still" }} />);

  it("stacks one section per step, with nothing pinned and no track", () => {
    expect(count(html, /class="still-step"/g)).toBe(STEPS.length);
    expect(count(html, /class="stage"/g)).toBe(STEPS.length);
    expect(html).not.toContain('class="pin"');
    expect(html).not.toContain('class="track"');
  });

  it("gives each section its own step's words only, all in reach", () => {
    expect(count(html, /class="words /g)).toBe(STEPS.length);
    expect(html).not.toContain("inert");
    expect(count(html, /<h1/g)).toBe(1);
  });

  it("shows each step's end state: the last section has power and the processor lit", () => {
    const last = html.slice(html.lastIndexOf('class="still-step"'));
    expect(last).toMatch(/data-part="power" data-on="true"/);
    expect(last).toMatch(/data-part="processor" data-on="true"/);
    expect(count(last, /class="lit" data-part="[a-z]+" data-on="true"/g)).toBe(2);
  });

  it("is unpinned and unmoving in the stylesheet", () => {
    const flat = css.replace(/\s+/g, " ");
    expect(flat).toContain(
      'html[data-mode="still"] *, html[data-mode="frozen"] * { transition: none !important; animation: none !important; }',
    );
    expect(flat).toMatch(/@media \(prefers-reduced-motion: reduce\) \{ \* \{ transition: none !important;/);
  });
});

describe("?step=N: the scene frozen at one step", () => {
  it.each([0, 1, 2])("renders step %i alone, with nothing to scroll", (step) => {
    const html = renderToStaticMarkup(<App mode={{ kind: "frozen", step, evidence: false }} />);
    expect(count(html, /class="stage"/g)).toBe(1);
    expect(html).toContain(`data-step="${STEPS[step].id}"`);
    expect(html).not.toContain('class="track"');
    expect(html).not.toContain('class="closing"');
    expect(html).not.toContain('role="dialog"');
  });

  it("puts the page behind an open panel out of reach, and lets the panel itself take focus", () => {
    const open = renderToStaticMarkup(<App mode={{ kind: "frozen", step: 2, evidence: true }} />);
    expect(open).toMatch(/<nav class="lnav" aria-label="Site" inert="">/);
    expect(open).toMatch(/<main id="top" inert="">/);
    expect(open).toMatch(/role="dialog" aria-modal="true" aria-labelledby="sheet-title" tabindex="-1"/);
    const still = renderToStaticMarkup(<App mode={{ kind: "still" }} />);
    expect(still).not.toContain("inert");
  });

  it("opens the evidence from the start when asked, but not at the opening, which has no control for it", () => {
    expect(renderToStaticMarkup(<App mode={{ kind: "frozen", step: 2, evidence: true }} />)).toContain('role="dialog"');
    expect(renderToStaticMarkup(<App mode={{ kind: "frozen", step: 0, evidence: true }} />)).not.toContain("dialog");
  });
});

describe("a stage", () => {
  const html = renderToStaticMarkup(<Stage current={2} solo onOpen={nothing} />);

  it("shows stop 1's count, label and statement, with the emphasis marked", () => {
    expect(html).toContain("1 of 7");
    expect(html).toContain(stop(1).label);
    expect(html).toContain(`<em>${stopOne.statement.emphasis}</em>`);
  });

  it("shows the label that says nothing was recorded, in place of an evidence line", () => {
    const label = !stopOne.evidence.recorded ? stopOne.evidence.label : "";
    expect(html).toContain(`<p class="pill pill-missing">${esc(label)}</p>`);
    expect(html).not.toContain("pill-type");
  });

  it("has the citation marker, the evidence control and the rail at 1 of 7", () => {
    const { first, last } = claimNumbers(stopOne.id);
    expect(html).toContain(`aria-label="Claims ${first} to ${last}: where this comes from"`);
    expect(html).toMatch(/<button type="button" class="open-evidence" id="evidence-open-s1-power-reset">/);
    expect(html).toContain('aria-label="Stop 1 of 7"');
    expect(count(html, /<span data-on="true"><\/span>/g)).toBe(1);
    expect(count(html, /<span data-on="false"><\/span>/g)).toBe(6);
  });

  it("carries the note under the picture, from the content", () => {
    expect(html).toContain(`<p class="picture-note">${esc(PICTURE_NOTE)}</p>`);
  });

  it("shows a recorded line with its register and type, read from the recording", () => {
    const pill = renderToStaticMarkup(<EvidencePill evidence={OPENING.evidence} />);
    expect(pill).toMatch(/<span class="pill-register">PCR \d+<\/span>/);
    expect(pill).toMatch(/<span class="pill-type">EV_[A-Z_]+<\/span>/);
    expect(pill).toContain(esc(OPENING.evidence.recorded ? OPENING.evidence.text : ""));
  });

  it("gives the step before stop 1 the opening's supporting sentence, small, and no evidence line", () => {
    const inside = renderToStaticMarkup(<Stage current={1} solo onOpen={nothing} />);
    expect(inside).toContain(`<h2 class="statement statement-support">${esc(OPENING.support ?? "")}`);
    expect(inside).not.toContain('class="pill');
    expect(inside).toContain('id="evidence-open-inside"');
  });

  it("names the picture by what it shows, not by the note on why it was drawn so", () => {
    expect(html).toContain('role="img" aria-label="Illustration: a circuit board. Lit: power, processor."');
    expect(html).not.toContain(esc(stopOne.picture.note));
  });

  it("tells the board where to look, for windows too narrow to show all of it", () => {
    expect(html).toMatch(/class="board" data-on="true" style="--focus:0\.\d+"/);
  });
});

describe("the evidence panel for stop 1", () => {
  const html = renderToStaticMarkup(<EvidencePanel screen={stopOne} atClaims={false} onClose={nothing} />);

  it("is a labelled dialog with a way out", () => {
    expect(html).toContain('role="dialog" aria-modal="true" aria-labelledby="sheet-title" tabindex="-1"');
    expect(html).toMatch(/<button type="button" class="sheet-close">Close<\/button>/);
    expect(html).toContain(`<h2 id="sheet-title" class="sheet-title">${esc(stopOne.statement.text)}</h2>`);
  });

  it("lists every claim with its number, its basis label and its words", () => {
    const { first } = claimNumbers(stopOne.id);
    expect(count(html, /<li value="\d+">/g)).toBe(stopOne.claims.length);
    stopOne.claims.forEach((claim, n) => {
      expect(html).toContain(`<li value="${first + n}">`);
      expect(html).toContain(esc(claim.text));
      expect(html).toContain(`data-basis="${claim.basis}"`);
      expect(html).toContain(esc(basisLabel(claim.basis).label));
    });
  });

  it("gives the specification's section and page, and links the firmware source file", () => {
    const cited = stopOne.claims.find((claim) => claim.citation)!.citation!;
    expect(html).toContain(esc(`section ${cited.section}, ${cited.title}. PDF page ${cited.pdf_page}`));
    expect(html).toMatch(/<a href="https:\/\/[^"]+ResetVectorVtf0\.asm" target="_blank" rel="noreferrer">/);
  });

  it("defines every term, from the glossary or from the screen", () => {
    for (const entry of stopOne.detail.definitions.map(define)) {
      expect(html).toContain(`<dt>${esc(entry.term)}</dt>`);
      expect(html).toContain(esc(entry.definition));
    }
  });

  it("says what the recording does not show, and explains the step", () => {
    expect(html).toContain(esc(stop(1).not_shown[0]));
    expect(html).toContain(esc(stopOne.detail.explanation));
    expect(html).toContain("Nothing was recorded here");
  });

  it("shows the records of the boot for a screen that names some", () => {
    const opening = renderToStaticMarkup(<EvidencePanel screen={OPENING} atClaims={false} onClose={nothing} />);
    expect(opening).toContain("Record 1</span>");
    expect(opening).toContain("Record 28</span>");
    expect(opening).toContain("The line from the recording");
  });
});

describe("the stylesheet", () => {
  it("moves nothing but transform and opacity", () => {
    const moved = [...css.matchAll(/transition:([^;]+);/g)].flatMap((m) =>
      m[1]
        .split(",")
        .map((part) => part.trim().split(/\s+/)[0])
        .filter((property) => property !== "none"),
    );
    expect(moved.length).toBeGreaterThan(0);
    expect(new Set(moved)).toEqual(new Set(["transform", "opacity"]));
    for (const frames of css.matchAll(/@keyframes [a-z-]+ \{([\s\S]*?)\n\}/g))
      for (const property of frames[1].matchAll(/^\s+([a-z-]+):/gm))
        expect(["opacity", "transform"]).toContain(property[1]);
  });

  it("lets the opening rest for a full window: the first marker is a window and a half", () => {
    const flat = css.replace(/\s+/g, " ");
    expect(flat).toContain(".marker:first-child { flex-basis: 150svh; }");
    expect(flat).toContain("height: calc(100svh + 150svh + (var(--steps) - 1) * 90svh);");
  });

  it("sizes the opening's title from the stage's height too, and gives the laptop only the room it leaves", () => {
    const flat = css.replace(/\s+/g, " ");
    expect(flat).toMatch(/--title-size: clamp\(\d+px, min\([\d.]+cqw, [\d.]+cqh\), \d+px\);/);
    expect(flat).toMatch(/\.laptop \{[^}]*height: min\([^;]*var\(--title-block\)\);/);
  });

  it("slides the board on a tall stage with a transform only, towards the step's focus", () => {
    const flat = css.replace(/\s+/g, " ");
    expect(flat).toMatch(/@container \(max-aspect-ratio: 4 \/ 5\) \{ \.board \{[^}]*--pan: clamp\([^;]*var\(--focus\)/);
    expect(flat).toContain("transform: translateX(var(--pan));");
  });

  it("keeps the faintest text readable on black: at least 4.5 to 1", () => {
    const hex = /--faint: #([0-9a-f]{6});/.exec(css)![1];
    const channel = (n: number) => {
      const c = parseInt(hex.slice(n, n + 2), 16) / 255;
      return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
    };
    const luminance = 0.2126 * channel(0) + 0.7152 * channel(2) + 0.0722 * channel(4);
    expect((luminance + 0.05) / 0.05).toBeGreaterThan(4.5);
  });

  it("keeps the page black", () => {
    expect(css).toMatch(/--black: #000;/);
    expect(css).toMatch(/html \{\s+background: var\(--black\);/);
  });
});

describe("the site's own files", () => {
  const files = import.meta.glob<string>(["./**/*.{ts,tsx,css}", "../index.html", "../ASSETS.md"], {
    eager: true,
    query: "?raw",
    import: "default",
  });

  // The en dash, the em dash and the horizontal bar, by number so that this file holds none.
  const LONG_DASH = new RegExp("[\u2013\u2014\u2015]");

  it("use no long dash", () => {
    expect(Object.keys(files).length).toBeGreaterThan(10);
    for (const [name, text] of Object.entries(files)) expect(LONG_DASH.test(text), name).toBe(false);
  });
});
