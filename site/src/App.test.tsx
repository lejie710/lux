// The page in its three modes and the evidence panel, rendered to HTML. No browser is needed, so nothing
// here proves motion or focus in a real window; the panel's key and focus rules are tested in panel.test.ts.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { App } from "./App";
import { EvidencePanel } from "./components/EvidencePanel";
import { EvidencePill, Stage } from "./components/Stage";
import {
  PICTURE_NOTE,
  OPENING,
  STOPS,
  allScreens,
  basisLabel,
  claimNumbers,
  claimSource,
  define,
  headline,
  recordedEvent,
  recordedLine,
  recordedRegister,
  stop,
} from "./content/load";
import { PARTS } from "./content/types";
import { STEPS, firstStepOf } from "./model/scene";
import css from "./styles/lux.css?raw";

const count = (html: string, re: RegExp) => [...html.matchAll(re)].length;
/** Text as React writes it into HTML. */
const esc = (text: string) => text.replace(/&/g, "&amp;").replace(/'/g, "&#x27;").replace(/"/g, "&quot;");
/** A recorded line as it reads, without the marks that say where a long one may break. */
const plain = (html: string) => html.replace(/<wbr\/?>|<\/?span[^>]*>|<\/?em>/g, "");
const stopOne = headline(stop(1));
const nothing = () => {};
const at = (id: string) => STEPS.findIndex((step) => step.id === id);
const screenOf = (id: string) => allScreens().find((screen) => screen.id === id)!;
const panelOf = (id: string) =>
  renderToStaticMarkup(<EvidencePanel screen={screenOf(id)} atClaims={false} onClose={nothing} />);

describe("the scrolled page", () => {
  const html = renderToStaticMarkup(<App mode={{ kind: "scroll" }} />);

  it("pins one stage and lays one marker per step under it", () => {
    expect(count(html, /class="stage"/g)).toBe(1);
    expect(count(html, /class="marker"/g)).toBe(STEPS.length);
    expect(html).toContain('<div class="pin">');
  });

  it("keeps every step's words in the page and puts all but the current one out of reach", () => {
    expect(count(html, /class="words /g)).toBe(STEPS.length);
    expect(count(html, /class="words [a-z-]+"[^>]* data-on="false" inert=""/g)).toBe(STEPS.length - 1);
    expect(html).toContain(esc(OPENING.title.text.split(" ")[0]));
    expect(html).toContain(esc(stopOne.statement.text.split(" its ")[0]));
  });

  it("starts at the opening: the laptop in view, the board and every part dark", () => {
    expect(html).toMatch(/class="laptop"[^>]*data-on="true"/);
    expect(html).toMatch(/class="board" data-on="false"/);
    expect(html).toMatch(/class="ending" data-on="false"/);
    expect(count(html, /class="lit"/g)).toBe(PARTS.length + 1);
    expect(count(html, /class="lit" data-part="[a-z]+" data-on="true"/g)).toBe(0);
    expect(count(html, /class="glow" data-part="[a-z]+" data-on="true"/g)).toBe(0);
  });

  it("makes a further screen of a stop a shorter stretch of scrolling than a new stop", () => {
    expect(count(html, /class="marker" data-length="long"/g)).toBe(1);
    expect(count(html, /class="marker" data-length="full"/g)).toBe(1 + STOPS.length);
    expect(count(html, /class="marker" data-length="short"/g)).toBe(STEPS.length - 2 - STOPS.length);
  });

  it("gives every step a place in the page, which the rail's marks lead to", () => {
    STEPS.forEach((_, n) => expect(html).toContain(`id="step-${n}"`));
    for (const s of STOPS) expect(html).toContain(`href="#step-${firstStepOf(s.number)}"`);
  });

  it("says nothing aloud until the step has changed", () => {
    expect(html).toContain('<p class="sr-only" role="status"></p>');
  });

  it("has the navigation, with the story marked as the page in view", () => {
    expect(html).toContain('<a href="#top" aria-current="page">The boot</a>');
    expect(count(/<nav[\s\S]*?<\/nav>/.exec(html)![0], /<a /g)).toBe(5);
  });

  it("leads to the plain page first, before anything else can take focus", () => {
    const nav = /<nav[\s\S]*?<\/nav>/.exec(html)![0];
    expect(nav).toMatch(/^<nav[^>]*><a class="skip" href="\?static">Read the boot as a plain page<\/a>/);
    const still = renderToStaticMarkup(<App mode={{ kind: "still" }} />);
    expect(still).not.toContain('class="skip"');
  });

  it("offers a step back and a step on, the first of which has nowhere to go at the opening", () => {
    expect(html).toContain('<button type="button" disabled="">Previous step</button>');
    expect(html).toContain('<button type="button">Next step</button>');
  });

  it("keeps every layer of the picture in the page, lit or not, so one step can fade into the next", () => {
    expect(count(html, /class="lit" data-part="[a-z]+"/g)).toBe(PARTS.length + 1);
    expect(count(html, /class="glow" data-part="[a-z]+"/g)).toBe(PARTS.length);
    expect(html).toMatch(/class="ending" data-on="false"/);
    expect(html).toMatch(/class="dawn"[^>]*data-on="false"/);
  });

  it("has no link that leads nowhere", () => {
    expect(html).not.toContain('href="#"');
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

  it("draws in each section only the layers its step shows", () => {
    const lit = STEPS.reduce((sum, step) => sum + (step.view === "board" ? step.lit.length : 0), 0);
    const whole = STEPS.filter((step) => step.view === "board" && step.lit.length === PARTS.length).length;
    expect(count(html, /class="lit" data-part="[a-z]+" data-on="true"/g)).toBe(lit + whole);
    expect(html).not.toMatch(/class="(lit|glow)" data-part="[a-z]+" data-on="false"/);
    expect(html).not.toMatch(/class="(laptop|board|ending)" data-on="false"/);
    expect(count(html, /class="dawn"/g)).toBe(1);
  });

  it("names every control for the evidence apart, and has marks where the scrolled page has links to stops", () => {
    const names = [...html.matchAll(/class="open-evidence" id="[^"]+" aria-label="([^"]+)"/g)].map((m) => m[1]);
    expect(names.length).toBe(STEPS.length - 2);
    expect(new Set(names).size).toBe(names.length);
    for (const name of names) expect(name.startsWith("Open the evidence: ")).toBe(true);
    expect(html).not.toContain("Go to stop");
  });

  it("shows each step's end state: stop 1's section has power and the processor lit", () => {
    const from = html.indexOf('id="step-2"');
    const section = html.slice(from, html.indexOf('id="step-3"'));
    expect(section).toMatch(/data-part="power" data-on="true"/);
    expect(section).toMatch(/data-part="processor" data-on="true"/);
    expect(count(section, /class="lit" data-part="[a-z]+" data-on="true"/g)).toBe(2);
  });

  it("ends on the laptop with its screen lit and the way on to the earlier site", () => {
    const last = html.slice(html.lastIndexOf('class="still-step"'));
    expect(last).toMatch(/class="ending" data-on="true"/);
    expect(last).toMatch(/class="dawn"[^>]*data-on="true"/);
    expect(last).toContain(esc(screenOf(STEPS.at(-1)!.id).handover!.text));
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
  it.each(STEPS.map((_, n) => n))("renders step %i alone, with nothing to scroll", (step) => {
    const html = renderToStaticMarkup(<App mode={{ kind: "frozen", step, evidence: false }} />);
    expect(count(html, /class="stage"/g)).toBe(1);
    expect(html).toContain(`data-step="${STEPS[step].id}"`);
    expect(html).not.toContain('class="track"');
    expect(html).not.toContain('class="closing"');
    expect(html).not.toContain('role="dialog"');
    expect(count(html, /class="words /g)).toBe(1);
    // Nothing to jump to on a frozen page: the rail's marks are not links.
    expect(html).not.toContain('href="#step-');
  });

  it.each(STEPS.map((_, n) => n).slice(1))("opens the evidence of step %i from the start when asked", (step) => {
    const html = renderToStaticMarkup(<App mode={{ kind: "frozen", step, evidence: true }} />);
    expect(html).toContain('role="dialog"');
    expect(html).toContain(`<h2 id="sheet-title" class="sheet-title">${esc(STEPS[step].screen.statement.text)}</h2>`);
  });

  it("puts the page behind an open panel out of reach, and lets the panel itself take focus", () => {
    const open = renderToStaticMarkup(<App mode={{ kind: "frozen", step: 2, evidence: true }} />);
    expect(open).toMatch(/<nav class="lnav" aria-label="Site" inert="">/);
    expect(open).toMatch(/<main id="top" inert="" data-page="story">/);
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
    expect(html).toContain(
      '<button type="button" class="open-evidence" id="evidence-open-s1-power-reset" aria-label="Open the evidence: Power and reset, screen 1 of 1">',
    );
    expect(html).toContain('aria-label="Stop 1 of 7, screen 1 of 1"');
    expect(count(html, /<a href="#step-\d+" aria-label="Go to stop \d" data-on="true">/g)).toBe(1);
    expect(count(html, /<a href="#step-\d+" aria-label="Go to stop \d" data-on="false">/g)).toBe(6);
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
    // It has no evidence line of its own, so no control for one: its marker leads to the opening's claims.
    expect(inside).not.toContain('id="evidence-open-inside"');
    expect(inside).toContain('id="evidence-marker-inside"');
  });

  it("names the picture by what it shows, not by the note on why it was drawn so", () => {
    expect(html).toContain('role="img" aria-label="Illustration: a circuit board. Lit: power, processor."');
    expect(html).not.toContain(esc(stopOne.picture.note));
  });

  it("tells the board where to look, for windows too narrow to show all of it", () => {
    expect(html).toMatch(/class="board" data-on="true" style="--focus:0\.\d+;--span:0\.\d+"/);
  });
});

describe("stops 2 to 7 on the stage", () => {
  const stage = (id: string) => renderToStaticMarkup(<Stage current={at(id)} solo onOpen={nothing} />);

  it.each(STEPS.slice(2).map((step) => [step.id, step] as const))(
    "%s shows one statement, one evidence line and one way to the rest",
    (id, step) => {
      const html = stage(id);
      expect(count(html, /<h2 class="statement">/g)).toBe(1);
      expect(count(html, /<p class="pill[ "]/g)).toBe(1);
      expect(count(html, /class="open-evidence"/g)).toBe(1);
      expect(html).toContain(`${step.stop!.number} of 7`);
      expect(html).toContain(esc(step.stop!.label));
      // The supporting sentence and the explanation stay behind the evidence control.
      if (step.screen.support) expect(html).not.toContain(esc(step.screen.support));
      expect(html).not.toContain(esc(step.screen.detail.explanation));
    },
  );

  it("fills the rail up to the stop in view, and the stop's own mark screen by screen", () => {
    const html = stage("s4-policy");
    expect(html).toContain('aria-label="Stop 4 of 7, screen 2 of 3"');
    expect(count(html, /style="--fill:1"/g)).toBe(3);
    expect(count(html, /style="--fill:0"/g)).toBe(3);
    expect(html).toMatch(/style="--fill:0\.66+7?"/);
  });

  it("quotes a console line as it was recorded, product name and all, and says it is the console", () => {
    const html = stage("s5-choice");
    expect(html).toContain('<span class="pill-type">Console</span>');
    expect(plain(html)).toContain(esc(recordedLine("normal-1", "console", 0)));
    expect(recordedLine("normal-1", "console", 0)).toContain("QEMU HARDDISK");
  });

  it("lets a long line break before the word from and after a slash, and changes no character of it", () => {
    const line = recordedLine("normal-1", "console", 0);
    const pill = renderToStaticMarkup(
      <EvidencePill
        evidence={{
          recorded: true,
          kind: "console",
          run: "normal-1",
          file: "recordings/normal-1/recording.json",
          field: "console[0]",
          position: 0,
          text: line,
        }}
      />,
    );
    expect(count(pill, /class="pill-part"/g)).toBe(2);
    expect(pill).toContain('</span> <span class="pill-part">from ');
    expect(pill).toContain("/<wbr/>");
    expect(plain(pill)).toContain(esc(line));
    // A line with nothing to break at is plain text.
    const short = renderToStaticMarkup(<EvidencePill evidence={screenOf("s6-start").evidence} />);
    expect(short).not.toContain("pill-part");
  });

  it("names the protection a screen follows, in the content's own term", () => {
    expect(stage("s4-policy")).toContain(`<span class="thread">${define({ glossary: "secure-boot" }).term}</span>`);
    expect(stage("s4-services")).not.toContain('class="thread"');
  });

  it("gives the part a screen is about a stronger light, and no other", () => {
    const html = stage("s6-verify");
    expect(html).toMatch(/class="glow" data-part="security" data-on="true"/);
    expect(count(html, /class="glow" data-part="[a-z]+" data-on="true"/g)).toBe(1);
  });

  it("marks the pilot as a pilot, over the laptop with its inside awake and its screen dark", () => {
    const html = stage("s6-pilot-refusal");
    expect(html).toContain(`<p class="aside aside-pilot">${esc(screenOf("s6-pilot-refusal").pilot_label!)}</p>`);
    expect(html).toMatch(/class="ending" data-on="true" data-low="true"/);
    // A stage shown alone draws only what its step shows: no lit screen, and no board behind the laptop.
    expect(html).not.toContain('class="dawn"');
    expect(html).not.toContain('class="board"');
  });

  it("ends with the screen lit, its own note under the picture, and the way on as words until it has an address", () => {
    const last = STEPS.at(-1)!;
    const html = stage(last.id);
    const handover = last.screen.handover!;
    expect(html).toMatch(/class="dawn"[^>]*data-on="true"/);
    expect(html).toContain(`<p class="picture-note">${esc(last.screen.picture_caption!)}</p>`);
    expect(html).toContain(esc(handover.text));
    // The content decides: a link where it holds an address, plain words where it holds none. Never a dead link.
    if (handover.url) expect(html).toContain(`<a href="${handover.url}">${handover.link_label}</a>`);
    else {
      expect(html).toContain(`<span class="handover-pending">${handover.link_label}</span>`);
      expect(html).not.toMatch(/<a [^>]*>Continue/);
    }
    expect(html).not.toContain('href="#"');
    // What the way on is stands in the panel, where a keyboard and a touch screen can reach it.
    expect(panelOf(last.id)).toContain(esc(handover.note));
  });

  it("links the way on to the earlier site's public address", () => {
    const last = STEPS.at(-1)!;
    expect(last.screen.handover!.url).toBe("https://lejie710.github.io/nox/");
    expect(stage(last.id)).toContain('<a href="https://lejie710.github.io/nox/">Continue in Nox</a>');
    expect(stage(last.id)).not.toContain("handover-pending");
  });

  it("lights the whole board once the display cable is lit", () => {
    expect(stage("s7-exit-call")).toMatch(/class="lit" data-part="whole" data-on="true"/);
    expect(stage("s7-tables")).not.toContain('data-part="whole"');
  });
});

describe("the evidence panel for every screen", () => {
  it.each(allScreens().map((screen) => [screen.id, screen] as const))(
    "%s: every claim, term and line",
    (id, screen) => {
      const html = panelOf(id);
      expect(count(html, /<li value="\d+">/g)).toBe(screen.claims.length);
      for (const claim of screen.claims) expect(html).toContain(esc(claim.text));
      for (const entry of screen.detail.definitions.map(define)) expect(html).toContain(esc(entry.definition));
      expect(html).toContain(esc(screen.detail.explanation));
      if (screen.support) expect(html).toContain(esc(screen.support));
      for (const group of screen.detail.console_lines)
        for (const place of group.positions) expect(html).toContain(esc(recordedLine(group.run, "console", place)));
      for (const group of screen.detail.loader_report_lines)
        for (const place of group.positions)
          expect(html).toContain(esc(recordedLine(group.run, "loader_report", place)));
      for (const group of screen.detail.events)
        for (const index of group.indexes) expect(html).toContain(recordedEvent(group.run, index).digest_sha256);
      for (const group of screen.detail.pcrs)
        for (const n of group.registers) expect(html).toContain(recordedRegister(group.run, group.bank, n));
    },
  );

  it("shows a record's number, register, type and line, and its fingerprint short with the whole value behind it", () => {
    const html = panelOf("s6-verify");
    const event = recordedEvent("normal-1", 25);
    expect(html).toContain("Record 25</span>");
    expect(html).toContain(`PCR ${event.pcr}</span>`);
    expect(html).toContain(`<span class="row-type">${event.type}</span>`);
    expect(html).toContain(esc(event.summary));
    const digest = event.digest_sha256;
    expect(html).toContain(
      `<summary><span class="digest-label">sha256</span> ${digest.slice(0, 8)}...${digest.slice(-8)}</summary><p>${digest}</p>`,
    );
  });

  it("explains, as a legend, exactly the basis labels the screen's claims carry", () => {
    for (const screen of allScreens()) {
      const html = panelOf(screen.id);
      const legend = /<dl class="sheet-legend"[\s\S]*?<\/dl>/.exec(html)![0];
      const bases = new Set(screen.claims.map((claim) => claim.basis));
      expect(count(legend, /<dt /g)).toBe(bases.size);
      for (const basis of bases) {
        expect(legend).toContain(`data-basis="${basis}">${esc(basisLabel(basis).label)}</dt>`);
        expect(legend).toContain(esc(basisLabel(basis).meaning));
      }
    }
  });

  it("names the run beside its lines, so the pilot's lines are not taken for the normal run's", () => {
    const html = panelOf("s6-pilot-refusal");
    expect(html).toContain('<p class="sheet-run">Run e2</p>');
    // The normal run is named only where the two runs are compared, never over the pilot's printed lines.
    const printed = /<h3>What was printed<\/h3>.*?<\/section>/s.exec(html)![0];
    expect(printed).not.toContain('<p class="sheet-run">Run normal-1</p>');
    expect(html).toContain("The first record that differs");
    expect(html).toContain(esc(screenOf("s6-pilot-refusal").pilot_label!));
    expect(html).toContain("recordings/comparisons/normal-1_vs_e2.json");
  });

  it("keeps the identifier lines of the table list behind the control, the two it is about marked", () => {
    const html = panelOf("s7-tables");
    expect(count(html, /<li data-marked="true">/g)).toBe(2);
    expect(html).toContain(recordedLine("normal-1", "loader_report", 10));
    const stage = renderToStaticMarkup(<Stage current={at("s7-tables")} solo onOpen={nothing} />);
    expect(stage).not.toContain(recordedLine("normal-1", "loader_report", 10));
  });

  it("puts a long list of lines in a box of its own that the keyboard can reach", () => {
    expect(panelOf("s7-memory-map")).toMatch(/<ol class="sheet-lines sheet-lines-long" tabindex="0"/);
    expect(panelOf("s7-tables")).toMatch(/<ol class="sheet-lines sheet-lines-long" tabindex="0"/);
  });

  it("heads a file that is not a recording as such, and says where nothing was recorded", () => {
    const html = panelOf("s2-earliest-code");
    expect(html).toContain("<h3>Nothing was recorded here</h3>");
    expect(html).toContain("<h3>Also on file</h3>");
    expect(html).not.toContain("Other fields of the recording");
    expect(panelOf("s1-power-reset")).toContain("<h3>The nearest the recording has</h3>");
  });

  it("marks the place where the specification points elsewhere as a pointer, not as the source of a claim", () => {
    expect(panelOf("s6-verify")).toContain(
      '<p class="claim-source">Where UEFI 2.11 points away: UEFI Specification 2.11, section 2.6.4,',
    );
  });

  it("names each run's own file for a claim read from more than one run", () => {
    expect(claimSource({ text: "", basis: "recording", run: "normal-1, e2", field: "run.kind" })).toBe(
      "recordings/normal-1/recording.json, recordings/e2/recording.json: run.kind",
    );
    expect(claimSource({ text: "", basis: "recording", run: "e2", field: "run.kind" })).toBe(
      "recordings/e2/recording.json: run.kind",
    );
  });

  it("says where the stage name comes from, at the stops that have one", () => {
    const html = panelOf("s3-first-records");
    expect(html).toContain(esc(stop(3).stage_name!.attribution));
    expect(panelOf("s6-verify")).not.toContain("<dt>SEC");
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

  it("lets the opening rest for a full window, and the last step hold until the section ends", () => {
    const flat = css.replace(/\s+/g, " ");
    expect(flat).toContain('.marker[data-length="long"] { height: 150svh; }');
    expect(flat).toContain('.marker[data-length="short"] { height: 90svh; }');
    expect(flat).toContain(".marker:last-child { height: 190svh; }");
    expect(flat).toContain(".track { margin-top: -100svh;");
  });

  it("makes no stretch of scrolling shorter than a window's own paging, so no screen can be passed over", () => {
    // Space and Page Down move a window by about seven eighths of its height.
    const heights = [...css.matchAll(/\.marker[^{]*\{\s*height:\s*(\d+)svh/g)].map((m) => Number(m[1]));
    expect(heights.length).toBe(4);
    for (const height of heights) expect(height).toBeGreaterThanOrEqual(88);
  });

  it("gives an unlit mark of the rail an edge that can be seen: three to one on black", () => {
    const alpha = Number(
      /\.rail i \{[^}]*background: rgba\(255, 255, 255, ([\d.]+)\)/.exec(css.replace(/\s+/g, " "))![1],
    );
    const level = (255 * alpha) / 255;
    const luminance = level <= 0.03928 ? level / 12.92 : ((level + 0.055) / 1.055) ** 2.4;
    expect((luminance + 0.05) / 0.05).toBeGreaterThanOrEqual(3);
  });

  it("draws the board large on a tall stage, and smaller only as far as a step's parts need", () => {
    const flat = css.replace(/\s+/g, " ");
    expect(flat).toMatch(/@container \(max-aspect-ratio: 4 \/ 5\) \{ \.board \{[^}]*--wide: 250cqw;/);
    expect(flat).toMatch(/--zoom: min\(1, [\d.]+ \/ var\(--span\)\);/);
    expect(flat).toContain("transform: translateX(var(--pan)) scale(var(--zoom));");
  });

  it("adds the stronger light and lights the screen by opacity alone", () => {
    const flat = css.replace(/\s+/g, " ");
    expect(flat).toMatch(/\.glow\[data-on="true"\] \{ opacity: 0\.\d+; transition: opacity /);
    expect(flat).toMatch(/\.ending \.dawn\[data-on="true"\] \{ opacity: 1; transition: opacity /);
    expect(flat).toMatch(/\.ending\[data-on="false"\] \{ opacity: 0; transform: scale\([\d.]+\);/);
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

  it("keeps the navigation on one line, with a 44 px reach for each link in a narrow window", () => {
    const flat = css.replace(/\s+/g, " ");
    expect(flat).toContain(".lnav .name, .lnav .links { flex: none; white-space: nowrap; }");
    const narrow = flat.slice(flat.indexOf("@media (max-width: 760px)"));
    expect(narrow).toMatch(/\.lnav \.links a \{[^}]*min-height: 44px;[^}]*padding: 0 8px;/);
    // Under 360 px the word beside the mark is hidden from the eye only: the link keeps its name.
    const tiny = flat.slice(flat.indexOf("@media (max-width: 359px)"));
    expect(tiny).toMatch(/\.lnav \.name-word \{[^}]*clip-path: inset\(50%\);/);
    expect(tiny.slice(0, tiny.indexOf("@container"))).not.toContain("display: none");
    expect(renderToStaticMarkup(<App mode={{ kind: "scroll" }} />)).toContain('<span class="name-word">Lux</span>');
  });

  it("makes the board and the laptop smaller on a stage that is narrow and short, never the words", () => {
    const flat = css.replace(/\s+/g, " ");
    expect(flat).toMatch(/--plate: min\(var\(--wide\), max\(\d+cqw, \d+cqh - \d+px\)\);/);
    expect(flat).toContain("width: var(--plate);");
    expect(flat).toMatch(/\.ending \{ --tall: min\(\d+cqh, \d+cqw, 100cqh - \d+px\);/);
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
