// The pages beside the story, rendered to HTML: the experiments, the sources, the strip of seven stops, the
// navigation, and the evidence of a two-run screen and of a card. No browser is needed, so nothing here
// proves layout; what is proved is that the page shows what the content and the files hold, and no more.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { App } from "./App";
import { EvidencePanel } from "./components/EvidencePanel";
import { Experiments } from "./components/Experiments";
import { Overview, litAtEndOf, partsOf } from "./components/Overview";
import { PROVENANCE_RUN, SOURCE_SECTIONS, Sources } from "./components/Sources";
import { FILES, comparisonAt, comparisonView, provenanceOf } from "./content/files";
import {
  DISCLAIMER,
  EXPERIMENT_SCREENS,
  FIRMWARE_SOURCES,
  GLOSSARY,
  LIMITS,
  NOT_READ,
  SOURCES,
  SOURCE_SCREENS,
  STOPS,
  TRADEMARK_NOTE,
  claimNumbers,
  findSubject,
  recordedRegister,
  screenProblems,
} from "./content/load";
import { PARTS } from "./content/types";
import { experimentState, type Files, type ScoreFile } from "./model/experiments";
import { readRoute } from "./model/route";
import { firstStepOf } from "./model/scene";
import index from "../index.html?raw";
import config from "../vite.config.ts?raw";
import pages from "./styles/pages.css?raw";

const count = (html: string, re: RegExp) => [...html.matchAll(re)].length;
const esc = (text: string) =>
  text
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/'/g, "&#x27;")
    .replace(/"/g, "&quot;");
const nothing = () => {};
const screenOf = (id: string) => EXPERIMENT_SCREENS.find((screen) => screen.id === id)!;
const cardHtml = (html: string, label: string) =>
  new RegExp(
    `<li class="card"[^>]*>(?:(?!<li class="card").)*?<span class="card-label">${label}</span>.*?</li>`,
    "s",
  ).exec(html)![0];

const NOTHING: Files = { runs: [], comparisons: [], scores: [], predictions: [] };
const SCORE: ScoreFile = {
  format: "lux-score/1",
  experiment: "signature-byte",
  run: "signature-byte-1",
  required_met: 1,
  required_total: 1,
  open_correct: 2,
  open_total: 3,
  mismatches: ["pcr1"],
  rows: [
    { id: "refused", basis: "uefi-required", held: true },
    { id: "pcr1", basis: "this-firmware", held: false },
  ],
};
const SCORED: Files = {
  ...NOTHING,
  runs: [{ name: "signature-byte-1", experiment: "signature-byte", kind: "counted", change: "", outcome: "refused" }],
  scores: [SCORE],
};

describe("the content of the two other pages", () => {
  it("has what a screen needs, on every screen", () => {
    for (const screen of [...EXPERIMENT_SCREENS, ...SOURCE_SCREENS])
      expect(screenProblems(screen), screen.id).toEqual([]);
  });

  it("numbers its claims from 1 on each page, a screen's own and then its cards' and items'", () => {
    expect(claimNumbers(EXPERIMENT_SCREENS[0].id).first).toBe(1);
    expect(claimNumbers(SOURCE_SCREENS[0].id).first).toBe(1);
    const pilots = screenOf("experiments-pilots");
    const own = claimNumbers(pilots.id);
    const first = claimNumbers(`${pilots.id}/${pilots.cards![0].id}`);
    expect(first.first).toBe(own.last + 1);
    expect(first.last - first.first + 1).toBe(pilots.cards![0].claims.length);
    expect(() => claimNumbers("no-such-screen")).toThrow();
  });

  it("finds a screen or one of its cards by id, and nothing for an id that names neither", () => {
    expect(findSubject("experiment-e2")?.card).toBeNull();
    expect(findSubject("experiments-pilots/e4")?.card?.label).toBe("E4");
    expect(findSubject("experiments-pilots/e9")).toBeNull();
    expect(findSubject("nowhere")).toBeNull();
    expect(findSubject(null)).toBeNull();
  });
});

describe("the files beside the content", () => {
  it("names each recording by the experiment it says it is", () => {
    const normal = FILES.runs.find((run) => run.name === "normal-1")!;
    expect(normal).toMatchObject({ experiment: "normal", kind: "normal", outcome: "accepted" });
    expect(FILES.runs.find((run) => run.name === "e2")).toMatchObject({ kind: "pilot", outcome: "refused" });
  });

  it("lays a comparison out with both runs' register values, read from the two recordings", () => {
    const view = comparisonView(comparisonAt("recordings/comparisons/normal-1_vs_e2.json")!);
    expect(view.registers.map((r) => r.pcr)).toEqual([4, 5, 7]);
    for (const register of view.registers) {
      expect(register.baseline).toBe(recordedRegister("normal-1", "sha256", register.pcr));
      expect(register.changed).toBe(recordedRegister("e2", "sha256", register.pcr));
      expect(register.baseline).not.toBe(register.changed);
    }
    expect(view.first).toMatchObject({ index: 25, stop: 6 });
    expect(view.first!.baseline!.summary).toBe("variable db, 851 data bytes");
    expect(view.onlyBaseline).toHaveLength(4);
    expect(view.onlyChanged).toHaveLength(2);
    expect(view.consoleFirst?.changed).toContain("Access Denied");
    expect(view.banks).toEqual(["sha1", "sha256", "sha384", "sha512"]);
  });

  it("finds the two normal runs identical, and no comparison at a path that is not on disk", () => {
    const view = comparisonView(comparisonAt("recordings/comparisons/normal-1_vs_normal-2.json")!);
    expect(view.identical).toBe(true);
    expect(view.registers).toEqual([]);
    expect(view.first).toBeNull();
    expect(comparisonAt("recordings/comparisons/none.json")).toBeNull();
  });

  it("reads a recording's own account of how it was made", () => {
    const found = provenanceOf(PROVENANCE_RUN)!;
    expect(found.file).toBe(`recordings/${PROVENANCE_RUN}/recording.json`);
    expect(found.provenance.firmware.sha256).toMatch(/^[0-9a-f]{64}$/);
    expect(found.mayVary).toContain("provenance.recorded_at");
    expect(provenanceOf("no-such-run")).toBeNull();
  });
});

describe("the experiments page", () => {
  const html = renderToStaticMarkup(<Experiments onOpen={nothing} />);

  it("has one section per screen of the content, each with its statement and the control for its evidence", () => {
    expect(count(html, /<section class="page-screen"/g)).toBe(EXPERIMENT_SCREENS.length);
    for (const screen of EXPERIMENT_SCREENS) {
      expect(html).toContain(`id="at-${screen.id}"`);
      expect(html).toContain(`id="evidence-open-${screen.id}"`);
      expect(html.replace(/<\/?em>/g, "")).toContain(esc(screen.statement.text));
    }
    expect(count(html, /<h1 /g)).toBe(1);
  });

  it("opens with one statement and the score, and keeps the question and the measure behind the control", () => {
    const intro = EXPERIMENT_SCREENS[0];
    expect(html).not.toContain(esc(intro.question!));
    for (const line of intro.measure!) expect(html).not.toContain(esc(line));
    const panel = renderToStaticMarkup(<EvidencePanel screen={intro} atClaims={false} onClose={nothing} />);
    expect(panel).toContain(`<h3>The question</h3><p class="sheet-prose">${esc(intro.question!)}</p>`);
    for (const line of intro.measure!) expect(panel).toContain(esc(line));
  });

  it("names the run over each evidence line, and says where it is a pilot or a counted run", () => {
    expect(html).toContain('<p class="page-run">Run normal-1</p>');
    expect(html).toContain('<p class="page-run">Run e1, a pilot, shown and not counted</p>');
    expect(html).toContain('<p class="page-run">Run e2, a pilot, shown and not counted</p>');
  });

  it("says which number is the record's and which the stop's", () => {
    expect(html).toMatch(/<dt>First record that differs<\/dt><dd>record \d+, at stop \d<\/dd>/);
  });

  it("names every control for the evidence apart", () => {
    const names = [...html.matchAll(/class="open-evidence" id="[^"]+" aria-label="([^"]+)"/g)].map((m) => m[1]);
    expect(names.length).toBe(EXPERIMENT_SCREENS.length);
    expect(new Set(names).size).toBe(names.length);
  });

  it("paints the two pictures of the two-run screen together: neither is put off", () => {
    const sides = /<div class="sides">[\s\S]*?<\/div><\/div>/.exec(html)![0];
    expect(count(sides, /<img /g)).toBe(2);
    expect(sides).not.toContain("decoding");
    expect(sides).not.toContain("loading=");
  });

  it("sets the two runs side by side: screen lit against screen dark, one statement and one line each", () => {
    const e2 = screenOf("experiment-e2");
    expect(count(html, /<div class="side" /g)).toBe(2);
    expect(html).toMatch(
      /data-outcome="accepted"><img [^>]*alt="Illustration: a laptop, its screen lit with a dawn sky\."/,
    );
    expect(html).toMatch(
      /data-outcome="refused"><img [^>]*alt="Illustration: a laptop, its inside awake, its screen dark\."/,
    );
    const plain = html.replace(/<wbr\/?>|<\/?span[^>]*>|<\/?em>/g, "");
    for (const side of e2.sides!) {
      expect(plain).toContain(esc(side.statement.text));
      expect(plain).toContain(esc(side.evidence.text));
    }
    expect(html).toContain("<em>Access Denied</em>");
    expect(html).toContain(esc(e2.status!.text));
  });

  it("shows each pilot on file as a pilot, with what its comparison file holds", () => {
    for (const card of screenOf("experiments-pilots").cards!) {
      const state = experimentState(card.id, FILES);
      const own = cardHtml(html, card.label);
      expect(own).toContain('data-status="pilot"');
      expect(own).toContain(`<dt>Run ${state.run!.name}</dt>`);
      expect(own).toContain(`>${state.run!.outcome}</dd>`);
      expect(own).toContain(`id="evidence-open-experiments-pilots/${card.id}"`);
    }
    expect(cardHtml(html, "E5")).toContain("<dd>4, 5 and 7</dd>");
    expect(cardHtml(html, "E4")).toContain("<dd>7</dd>");
  });

  it("lists what the specification leaves open, each with the label of its basis and its citation", () => {
    const items = screenOf("specification-leaves-open").items!;
    expect(count(html, /<ul class="open-items">.*?<\/ul>/gs)).toBe(1);
    for (const item of items) expect(html).toContain(esc(item.title));
    expect(count(html, /class="claim-basis" data-basis="uefi-platform"/g)).toBe(items.length);
  });
});

describe("the experiments page with nothing on file", () => {
  const html = renderToStaticMarkup(<Experiments onOpen={nothing} files={NOTHING} />);

  it("shows every card as not yet run, with the content's own status and no result", () => {
    const cards = EXPERIMENT_SCREENS.flatMap((screen) => screen.cards ?? []);
    expect(count(html, /<li class="card" data-status="not-run"/g)).toBe(cards.length);
    expect(count(html, /<span class="card-status">Not yet run<\/span>/g)).toBe(cards.length);
    expect(html).not.toContain('class="card-result"');
    for (const card of cards) expect(html).toContain(esc(card.status));
  });

  it("claims no score: the content's own sentence stands where the numbers would", () => {
    expect(html).toContain(esc(EXPERIMENT_SCREENS[0].score!.text));
    expect(html).toContain('class="score" data-claimed="false"');
    expect(html).not.toContain("Specification-required");
  });

  it("offers a card's evidence only where it has claims to show", () => {
    const blind = screenOf("experiments-blind").cards!;
    for (const card of blind.filter((c) => c.claims.length === 0))
      expect(html).not.toContain(`id="evidence-open-experiments-blind/${card.id}"`);
  });
});

describe("the experiments page with a score on file", () => {
  const html = renderToStaticMarkup(<Experiments onOpen={nothing} files={SCORED} />);

  it("shows the scored experiment as scored, with its two numbers, and the others as they are", () => {
    const own = cardHtml(html, "Signature byte");
    expect(own).toContain('data-status="scored"');
    expect(own).toContain("<dt>Specification-required rows met</dt><dd>1 of 1</dd>");
    expect(own).toContain("<dt>Open rows predicted correctly</dt><dd>2 of 3</dd>");
    expect(cardHtml(html, "E6")).toContain('data-status="not-run"');
  });

  it("puts the two headline numbers where the sentence that claimed nothing stood", () => {
    expect(html).toContain('class="score" data-claimed="true"');
    expect(html).toContain("<dt>Specification-required behaviours met</dt><dd>1 of 1</dd>");
    expect(html).toContain("<dt>Open behaviours predicted correctly</dt><dd>2 of 3</dd>");
    expect(html).not.toContain(esc(EXPERIMENT_SCREENS[0].score!.text));
  });

  it("counts what is on file while a prediction is and a score is not", () => {
    const waiting: Files = {
      ...NOTHING,
      predictions: [{ format: "lux-prediction/1", experiment: "signature-byte", rows: [] }],
    };
    const page = renderToStaticMarkup(<Experiments onOpen={nothing} files={waiting} />);
    expect(page).toContain("<dt>Predictions on file</dt><dd>1</dd>");
    expect(page).toContain("<dt>Scored</dt><dd>0</dd>");
    expect(cardHtml(page, "Signature byte")).toContain("<dt>Prediction on file</dt>");
    expect(cardHtml(page, "Signature byte")).toContain('data-status="not-run"');
  });
});

describe("the evidence of a two-run screen", () => {
  const e2 = findSubject("experiment-e2")!;
  const html = renderToStaticMarkup(<EvidencePanel screen={e2.screen} atClaims={false} onClose={nothing} />);

  it("shows the line from each recording, under the name of its run", () => {
    expect(html).toContain("The line from each recording");
    expect(html).toContain("recordings/normal-1/recording.json: console[2]");
    expect(html).toContain("recordings/e2/recording.json: console[1]");
  });

  it("shows the first record that differs, in both runs, and what its stop rests on", () => {
    expect(html).toContain("The first record that differs");
    expect(html).toContain("Record 25, at stop 6");
    expect(html).toContain("EV_EFI_VARIABLE_AUTHORITY");
    expect(html).toContain("action: Returning from EFI Application from Boot Option");
    expect(html).toContain(esc(e2.screen.detail.first_differing_event!.stop_basis));
  });

  it("shows the registers that differ with both values, whole behind a press", () => {
    for (const register of [4, 5, 7])
      for (const run of ["normal-1", "e2"])
        expect(html).toContain(`<p>${recordedRegister(run, "sha256", register)}</p>`);
    expect(html).toContain("The same registers differ in the sha1, sha256, sha384 and sha512 banks.");
  });

  it("shows the records only one run has, each with the content's plain line", () => {
    expect(html).toContain("Records only one run has");
    for (const event of [...e2.screen.detail.events_only_in_baseline!, ...e2.screen.detail.events_only_in_changed!])
      expect(html).toContain(esc(event.plain));
  });

  it("says in the content's words that there is no prediction, and labels every claim with its basis", () => {
    expect(html).toContain("The prediction");
    expect(count(html, new RegExp(esc(e2.screen.status!.text).replace(/[.]/g, "\\."), "g"))).toBe(2);
    expect(count(html, /<li value="\d+"><p class="claim-basis"/g)).toBe(e2.screen.claims.length);
    for (const basis of ["uefi-required", "tcg-unread", "this-firmware", "recording"])
      expect(html).toContain(`class="claim-basis" data-basis="${basis}"`);
  });

  it("sets the status the text names against the words the firmware printed", () => {
    const note = e2.screen.detail.status_mismatch!;
    for (const text of [note.title, note.specification, note.recording, note.reading, note.limit])
      expect(html).toContain(esc(text));
    expect(html).toContain(`section ${note.citation.section}`);
  });
});

describe("the evidence of a card", () => {
  const subject = findSubject("experiments-pilots/e1")!;
  const html = renderToStaticMarkup(
    <EvidencePanel screen={subject.screen} card={subject.card} atClaims={false} onClose={nothing} />,
  );

  it("is about that experiment alone: its title, its change, its comparison and its own claims", () => {
    expect(html).toContain(esc(subject.card!.title));
    expect(html).toContain("recordings/comparisons/normal-1_vs_e1.json");
    expect(html).toContain("Registers that differ");
    expect(count(html, /<li value="\d+"><p class="claim-basis"/g)).toBe(subject.card!.claims.length);
    expect(html).not.toContain("What happens");
  });

  it("opens from the address of the card", () => {
    const page = renderToStaticMarkup(
      <App mode={{ kind: "scroll" }} route={readRoute("#/experiments/experiments-pilots/e1/evidence")} />,
    );
    expect(page).toContain('role="dialog"');
    expect(page).toMatch(/<main id="top" inert="" data-page="experiments">/);
  });
});

describe("the sources page", () => {
  const html = renderToStaticMarkup(<Sources onOpen={nothing} />);

  it("lists every source with its citation or version, and every firmware source file as a link", () => {
    for (const source of SOURCES) {
      expect(html).toContain(esc(source.title));
      expect(html).toContain(esc(source.citation_line ?? source.version));
      expect(html).toContain(esc(source.how_used));
    }
    for (const file of FIRMWARE_SOURCES)
      expect(html).toContain(
        `<a href="${file.url}" target="_blank" rel="noreferrer">${file.path}<span class="sr-only"> (opens in a new tab)</span></a>`,
      );
  });

  it("says of every link that opens a new tab that it does", () => {
    const links = [...html.matchAll(/<a [^>]*target="_blank"[^>]*>[\s\S]*?<\/a>/g)].map((m) => m[0]);
    expect(links.length).toBeGreaterThan(0);
    for (const link of links) expect(link).toContain("(opens in a new tab)");
  });

  it("names the two scrolling boxes of the provenance block, so a screen reader can say what they are", () => {
    expect(html).toContain('<pre tabindex="0" role="group" aria-label="qemu_command_line">');
    expect(html).toContain('<pre tabindex="0" role="group" aria-label="swtpm_command_line">');
  });

  it("says what was not read and what that costs the reader", () => {
    for (const document of NOT_READ) {
      expect(html).toContain(esc(document.title));
      expect(html).toContain(esc(document.status));
      expect(html).toContain(esc(document.cost_to_reader));
    }
  });

  it("gives every limit, the whole glossary with each entry's basis, and a box to filter it", () => {
    for (const limit of LIMITS) expect(html).toContain(esc(limit.text));
    expect(count(html, /<div id="term-/g)).toBe(GLOSSARY.length);
    expect(html).toContain(`${GLOSSARY.length} terms`);
    expect(html).toMatch(/<label for="glossary-filter">[^<]+<\/label><input id="glossary-filter" type="search"/);
    for (const entry of GLOSSARY) expect(html).toContain(esc(entry.definition));
  });

  it("shows how the recording says it was made, field by field", () => {
    const { provenance } = provenanceOf(PROVENANCE_RUN)!;
    expect(html).toContain(`recordings/${PROVENANCE_RUN}/recording.json`);
    expect(html).toContain(`<dt>tools.qemu</dt><dd>${esc(provenance.tools.qemu)}</dd>`);
    expect(html).toContain(`<p>${provenance.firmware.sha256}</p>`);
    expect(html).toContain(esc(provenance.qemu_command_line));
  });

  it("ends with what the project is, the trademark note and the disclaimer", () => {
    for (const text of SOURCE_SCREENS[1].paragraphs!) expect(html).toContain(esc(text));
    expect(html).toContain(esc(TRADEMARK_NOTE));
    expect(html).toContain(esc(DISCLAIMER));
  });

  it("leads to each of its parts, and each part is there to be led to", () => {
    for (const [id] of SOURCE_SECTIONS) {
      expect(html).toContain(`href="#/sources/${id}"`);
      expect(html).toContain(`id="at-${id}"`);
    }
  });
});

describe("the strip of seven stops after the story", () => {
  const html = renderToStaticMarkup(<Overview />);

  it("has one small board per stop, with its name, leading to the first step of that stop", () => {
    expect(count(html, /<li>/g)).toBe(STOPS.length);
    for (const stop of STOPS) {
      expect(html).toContain(`href="#step-${firstStepOf(stop.number)}"`);
      expect(html).toContain(`<span class="overview-name">${esc(stop.label)}</span>`);
    }
  });

  it("draws each small board close on the parts its stop is about, and the last one whole", () => {
    const places = [
      ...html.matchAll(/class="overview-plate" style="width:([\d.]+)%;left:(-?[\d.]+)%;top:(-?[\d.]+)%"/g),
    ];
    expect(places.length).toBe(STOPS.length);
    expect(Number(places.at(-1)![1])).toBe(100);
    // No two neighbours are framed alike: the difference between stops can be seen at this size.
    for (let n = 1; n < places.length; n++) expect(places[n][0]).not.toBe(places[n - 1][0]);
    for (const stop of STOPS) expect(partsOf(stop).length).toBeGreaterThan(0);
    for (const [, width, left] of places) {
      expect(Number(left)).toBeLessThanOrEqual(0);
      expect(Number(left)).toBeGreaterThanOrEqual(100 - Number(width) - 1e-9);
    }
  });

  it("lights more of the board at each stop, and all of it at the last", () => {
    const lit = STOPS.map((stop) => litAtEndOf(stop).length);
    for (let n = 1; n < lit.length; n++) expect(lit[n]).toBeGreaterThanOrEqual(lit[n - 1]);
    expect(lit[0]).toBeGreaterThan(0);
    expect(lit.at(-1)).toBe(PARTS.length);
    expect(count(html, /class="overview-lit"/g)).toBe(lit.reduce((a, b) => a + b, 0) + 1);
  });

  it("follows the story on the scrolled and the still page, and not a frozen step", () => {
    expect(renderToStaticMarkup(<App mode={{ kind: "scroll" }} />)).toContain('id="overview"');
    expect(renderToStaticMarkup(<App mode={{ kind: "still" }} />)).toContain('id="overview"');
    expect(renderToStaticMarkup(<App mode={{ kind: "frozen", step: 3, evidence: false }} />)).not.toContain(
      'id="overview"',
    );
  });
});

describe("the navigation", () => {
  const nav = (hash: string) =>
    /<nav class="lnav"[\s\S]*?<\/nav>/.exec(
      renderToStaticMarkup(<App mode={{ kind: "scroll" }} route={readRoute(hash)} />),
    )![0];

  it("has three real links and marks the page in view", () => {
    for (const [hash, name] of [
      ["", "The boot"],
      ["#/experiments", "Experiments"],
      ["#/sources/glossary", "Sources"],
    ]) {
      const html = nav(hash);
      // The scrolled story has one link more: the way to the plain page.
      expect(count(html, /<a /g)).toBe(hash === "" ? 5 : 4);
      expect(count(html, /aria-current="page"/g)).toBe(1);
      expect(html).toMatch(new RegExp(`<a href="[^"]+" aria-current="page">${name}</a>`));
    }
    expect(nav("")).toContain('<a href="#/experiments">Experiments</a><a href="#/sources">Sources</a>');
  });

  it("shows one page at a time", () => {
    const experiments = renderToStaticMarkup(<App mode={{ kind: "scroll" }} route={readRoute("#/experiments")} />);
    expect(experiments).toContain('class="page page-experiments"');
    expect(experiments).not.toContain('class="stage"');
    expect(experiments).not.toContain('class="page page-sources"');
    const story = renderToStaticMarkup(<App mode={{ kind: "scroll" }} />);
    expect(story).toContain('class="stage"');
    expect(story).not.toContain('class="page ');
  });
});

describe("the pages' stylesheet and the files a host needs", () => {
  it("moves nothing at all", () => {
    expect(pages).not.toMatch(/transition|animation|@keyframes/);
  });

  it("previews a link with a picture, a title and a description", () => {
    for (const tag of ["og:title", "og:description", "og:image:width", "og:image:alt"])
      expect(index).toContain(`property="${tag}"`);
    expect(index).toContain('name="twitter:card" content="summary_large_image"');
    expect(config).toContain('property: "og:image"');
  });

  it("can be built for a folder of its own, and writes a page for an address that does not exist", () => {
    expect(config).toContain('env.LUX_BASE || "./"');
    expect(config).toContain('fileName: "404.html"');
  });
});
