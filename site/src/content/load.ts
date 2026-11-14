// The one door between the content files and the site. Components read words from here and write none of
// their own: a statement, a claim or a definition that is not in content/ is not on the page.
import storyA from "../../../content/story-a.json";
import storyB from "../../../content/story-b.json";
import storyC from "../../../content/story-c.json";
import shared from "../../../content/sources.json";
import experiments from "../../../content/experiments.json";
import {
  BASES,
  PARTS,
  type BaseScreen,
  type BasisLabel,
  type Card,
  type Claim,
  type Definition,
  type FirmwareSource,
  type GlossaryEntry,
  type Limit,
  type NotRead,
  type OpeningScreen,
  type PageScreen,
  type RecordedEvent,
  type Screen,
  type Source,
  type Stop,
  type StoryFile,
} from "./types";

export const FORMAT = "lux-content/2";

const stories = [storyA, storyB, storyC] as unknown as StoryFile[];
if ([...stories, shared, experiments].some((file) => file.format !== FORMAT))
  throw new Error(`content: expected format ${FORMAT}`);
if (!stories[0].opening) throw new Error("content: the first story file has no opening");

export const OPENING: OpeningScreen = stories[0].opening;
/** The seven stops, in order, from the three story files. */
export const STOPS: Stop[] = stories.flatMap((story) => story.stops);
export const BASIS_LABELS = shared.basis_labels as BasisLabel[];
export const GLOSSARY = shared.glossary as unknown as GlossaryEntry[];
export const FIRMWARE_SOURCES = shared.firmware_sources as FirmwareSource[];
/** The note under every picture. */
export const PICTURE_NOTE: string = shared.picture_note;
/** The line that says whose project this is. */
export const DISCLAIMER: string = shared.disclaimer;
/** How to read a page number, a type name or a register value. */
export const READING_NOTES: Record<string, string> = shared.reading_notes;
export const TRADEMARK_NOTE: string = shared.trademark_note;
/** Where the names of the four stages come from. */
export const STAGE_NAMES = shared.stage_names as { text: string; claims: Claim[] };
/** What was read or run, what was not read, and the limits of what is shown. */
export const SOURCES = shared.sources as unknown as Source[];
export const NOT_READ = shared.not_read as unknown as NotRead[];
export const LIMITS = shared.limits as unknown as Limit[];

/** The screens of the experiments page, in reading order, and the name the navigation gives the page. */
export const EXPERIMENT_SCREENS = experiments.screens as unknown as PageScreen[];
export const EXPERIMENTS_LABEL: string = experiments.section.nav_label;
/** The two screens of the sources page: the sources themselves, and what the project is. */
export const SOURCE_SCREENS = shared.screens as unknown as PageScreen[];

// The four fields of a committed recording that the story quotes, for every run on file. Only these fields
// are taken into the page; the rest of a recording stays in its file.
function byRun<T>(files: Record<string, T>): Record<string, T> {
  return Object.fromEntries(Object.entries(files).map(([path, value]) => [path.split("/").at(-2) ?? path, value]));
}
const EVENTS = byRun(
  import.meta.glob<RecordedEvent[]>("../../../recordings/*/recording.json", { eager: true, import: "events" }),
);
const CONSOLE = byRun(
  import.meta.glob<string[]>("../../../recordings/*/recording.json", { eager: true, import: "console" }),
);
const LOADER_REPORT = byRun(
  import.meta.glob<string[]>("../../../recordings/*/recording.json", { eager: true, import: "loader_report" }),
);
const PCRS = byRun(
  import.meta.glob<Record<string, Record<string, string>>>("../../../recordings/*/recording.json", {
    eager: true,
    import: "pcrs",
  }),
);

/** The runs that have a committed recording. */
export const RUNS: string[] = Object.keys(EVENTS).sort();

/** Every screen of the story, the opening first, in reading order. */
export function allScreens(): Screen[] {
  return [OPENING, ...STOPS.flatMap((stop) => stop.screens)];
}

export function stop(number: number): Stop {
  const found = STOPS.find((s) => s.number === number);
  if (!found) throw new Error(`content: no stop ${number}`);
  return found;
}

/** The screen whose statement stands for the stop. */
export function headline(of: Stop): Screen {
  const found = of.screens.find((screen) => screen.id === of.headline);
  if (!found) throw new Error(`content: stop ${of.number} has no screen ${of.headline}`);
  return found;
}

export function basisLabel(basis: string): BasisLabel {
  const found = BASIS_LABELS.find((b) => b.basis === basis);
  if (!found) throw new Error(`content: unknown basis ${basis}`);
  return found;
}

export function firmwareSource(id: string): FirmwareSource {
  const found = FIRMWARE_SOURCES.find((s) => s.id === id);
  if (!found) throw new Error(`content: unknown firmware source ${id}`);
  return found;
}

/** A definition as term and words, whether the screen defines it or points at the glossary. */
export function define(definition: Definition): { term: string; definition: string } {
  if ("term" in definition) return definition;
  const found = GLOSSARY.find((g) => g.id === definition.glossary);
  if (!found) throw new Error(`content: unknown glossary entry ${definition.glossary}`);
  return { term: found.term, definition: found.definition };
}

/** A record of a run's log by its own index, which counts from 1. */
export function recordedEvent(run: string, index: number): RecordedEvent {
  const found = EVENTS[run]?.find((e) => e.index === index);
  if (!found) throw new Error(`content: run ${run} has no event ${index}`);
  return found;
}

/** One line of a run's console or of its loader's report, by its place in that list, from 0. */
export function recordedLine(run: string, list: "console" | "loader_report", position: number): string {
  const found = (list === "console" ? CONSOLE : LOADER_REPORT)[run]?.[position];
  if (found === undefined) throw new Error(`content: run ${run} has no ${list} line ${position}`);
  return found;
}

/** A register's value in one hash bank, as read at the end of the run. */
export function recordedRegister(run: string, bank: string, register: number): string {
  const found = PCRS[run]?.[bank]?.[String(register)];
  if (!found) throw new Error(`content: run ${run} has no register ${register} in bank ${bank}`);
  return found;
}

/** The same three readings for a file that may name what a recording does not have: null, not an error. */
export const eventAt = (run: string, index: number) => EVENTS[run]?.find((e) => e.index === index) ?? null;
export const lineAt = (run: string, position: number) => CONSOLE[run]?.[position] ?? null;
export const registerAt = (run: string, bank: string, register: number) =>
  PCRS[run]?.[bank]?.[String(register)] ?? null;

/** A long hexadecimal value cut to its first and last digits, for a line that has no room for all of it. */
export function shortened(value: string, keep = 8): string {
  return value.length <= keep * 2 + 3 ? value : `${value.slice(0, keep)}...${value.slice(-keep)}`;
}

/** What an evidence panel can be opened on: a screen, or one card of a screen of cards. */
export interface Subject {
  /** The screen's id, or the screen's and the card's with a slash between. */
  id: string;
  screen: BaseScreen &
    Pick<PageScreen, "evidence" | "sides" | "cards" | "items" | "experiment" | "status" | "question" | "measure"> &
    Pick<Screen, "handover">;
  card: Card | null;
}

export const subjectId = (screenId: string, cardId?: string) => (cardId ? `${screenId}/${cardId}` : screenId);

/** The screen, or the card of a screen, that an id names, on any page. Null when nothing has that id. */
export function findSubject(id: string | null): Subject | null {
  if (!id) return null;
  const [screenId, cardId] = id.split("/");
  const screen = [...allScreens(), ...EXPERIMENT_SCREENS, ...SOURCE_SCREENS].find((s) => s.id === screenId);
  if (!screen) return null;
  const card = cardId ? (screen as PageScreen).cards?.find((c) => c.id === cardId) : undefined;
  if (cardId && !card) return null;
  return { id, screen, card: card ?? null };
}

/** The claims of a page's screens in reading order: a screen's own, then those of each of its cards and items. */
function claimGroups(screens: readonly (BaseScreen & Pick<PageScreen, "cards" | "items">)[]): [string, Claim[]][] {
  return screens.flatMap((screen) => [
    [screen.id, screen.claims] as [string, Claim[]],
    ...[...(screen.cards ?? []), ...(screen.items ?? [])].map(
      (part) => [subjectId(screen.id, part.id), part.claims] as [string, Claim[]],
    ),
  ]);
}

/**
 * The number printed on a claim: claims count from 1 through a page in reading order, so a marker beside a
 * statement and the list behind "Open the evidence" show the same numbers. The story, the experiments and
 * the sources each count from 1. The id is a screen's, or a screen's and a card's or item's.
 */
export function claimNumbers(id: string): { first: number; last: number } {
  for (const page of [allScreens(), EXPERIMENT_SCREENS, SOURCE_SCREENS]) {
    let before = 0;
    for (const [key, claims] of claimGroups(page)) {
      if (key === id) return { first: before + 1, last: before + claims.length };
      before += claims.length;
    }
  }
  throw new Error(`content: no screen ${id}`);
}

/** Where a claim comes from, in one line. Empty for general background, which names no source. */
export function claimSource(claim: Claim): string {
  const cite = claim.citation ?? claim.uefi_pointer;
  if (cite)
    return `${cite.document} ${cite.version}, section ${cite.section}, ${cite.title}. PDF page ${cite.pdf_page}`;
  // A claim read from more than one run names each run's own file.
  if (claim.basis === "recording") {
    const files = (claim.run ?? "").split(", ").map((run) => `recordings/${run}/recording.json`);
    return `${claim.file ?? files.join(", ")}: ${claim.field}`;
  }
  return claim.source ?? "";
}

/**
 * What a screen lacks that the scene needs in order to draw it. An empty list means the screen can be shown.
 * The content has its own, stricter check against the recordings; this one guards the site's reading of it.
 */
export function screenProblems(screen: Screen | PageScreen): string[] {
  const problems: string[] = [];
  const attempt = (what: string, read: () => unknown) => {
    try {
      read();
    } catch (e) {
      problems.push(`${what}: ${(e as Error).message}`);
    }
  };

  if (!screen.statement?.text) problems.push("no statement");
  else if (screen.statement.emphasis && !screen.statement.text.includes(screen.statement.emphasis))
    problems.push("the emphasis is not a phrase of the statement");

  // A two-run screen has no line of its own: each of its two sides carries one.
  const lines = screen.kind === "side-by-side" ? ((screen as PageScreen).sides ?? []).map((s) => s.evidence) : [];
  if (screen.kind === "side-by-side" && lines.length !== 2) problems.push("a two-run screen needs two sides");
  for (const evidence of screen.kind === "side-by-side" ? lines : [screen.evidence]) checkEvidence(evidence);

  function checkEvidence(evidence: Screen["evidence"] | null) {
    if (!evidence) problems.push("no evidence");
    else if (evidence.recorded) {
      if (!evidence.text) problems.push("recorded evidence has no line");
      if (evidence.kind === "event") {
        attempt("evidence", () => {
          const event = recordedEvent(evidence.run, evidence.event_index ?? -1);
          if (event.summary !== evidence.text) throw new Error("the line is not the event's summary");
        });
      } else {
        const list = evidence.kind;
        attempt("evidence", () => {
          if (recordedLine(evidence.run, list, evidence.position) !== evidence.text)
            throw new Error("the line is not the recorded one");
        });
      }
    } else if (!evidence.label) problems.push("missing evidence has no label");
  }

  if (!screen.claims?.length) problems.push("no claims");
  for (const claim of screen.claims ?? []) {
    if (!BASES.includes(claim.basis)) problems.push(`claim with unknown basis ${claim.basis}`);
    else if (claim.basis !== "general" && claim.basis !== "tcg-unread" && !claimSource(claim))
      problems.push(`claim ${claim.id} names no source`);
    if (claim.source_ref) attempt(`claim ${claim.id}`, () => firmwareSource(claim.source_ref!));
  }

  if (!screen.detail?.explanation) problems.push("no explanation");
  for (const definition of screen.detail?.definitions ?? []) attempt("definition", () => define(definition));
  for (const group of screen.detail?.events ?? [])
    for (const index of group.indexes) attempt("detail event", () => recordedEvent(group.run, index));
  for (const group of screen.detail?.console_lines ?? [])
    for (const at of group.positions) attempt("detail console line", () => recordedLine(group.run, "console", at));
  for (const group of screen.detail?.loader_report_lines ?? [])
    for (const at of group.positions) attempt("detail report line", () => recordedLine(group.run, "loader_report", at));
  for (const group of screen.detail?.pcrs ?? [])
    for (const n of group.registers) attempt("detail register", () => recordedRegister(group.run, group.bank, n));

  // Only the story is pictured from the content; the other pages have null there.
  const picture = (screen as Screen).picture;
  if (!picture) {
    if (screen.stop !== null || screen.kind === "opening") problems.push("no picture");
  } else {
    if (picture.plate !== "board" && picture.plate !== "laptop") problems.push(`unknown plate ${picture.plate}`);
    for (const part of [...picture.lit, ...picture.newly_lit])
      if (!PARTS.includes(part)) problems.push(`unknown part ${part}`);
    if (picture.newly_lit.some((part) => !picture.lit.includes(part))) problems.push("a newly lit part is not lit");
    if (picture.attention?.some((part) => !picture.lit.includes(part)))
      problems.push("attention is drawn to a part that is not lit");
  }
  return problems;
}
