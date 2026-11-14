// The one door between the content files and the site. Components read words from here and write none of
// their own: a statement, a claim or a definition that is not in content/ is not on the page.
import storyA from "../../../content/story-a.json";
import shared from "../../../content/sources.json";
import { events as normal1Events } from "../../../recordings/normal-1/recording.json";
import {
  BASES,
  PARTS,
  type BasisLabel,
  type Claim,
  type Definition,
  type FirmwareSource,
  type GlossaryEntry,
  type OpeningScreen,
  type RecordedEvent,
  type Screen,
  type Stop,
  type StoryFile,
} from "./types";

export const FORMAT = "lux-content/2";

const story = storyA as unknown as StoryFile;
if (story.format !== FORMAT || shared.format !== FORMAT) throw new Error(`content: expected format ${FORMAT}`);

export const OPENING: OpeningScreen = story.opening;
export const STOPS: Stop[] = story.stops;
export const BASIS_LABELS = shared.basis_labels as BasisLabel[];
export const GLOSSARY = shared.glossary as unknown as GlossaryEntry[];
export const FIRMWARE_SOURCES = shared.firmware_sources as FirmwareSource[];
/** The note under every picture. */
export const PICTURE_NOTE: string = shared.picture_note;
/** The line that says whose project this is. */
export const DISCLAIMER: string = shared.disclaimer;
/** How to read a page number, a type name or a register value. */
export const READING_NOTES: Record<string, string> = shared.reading_notes;

/** The events of each committed run the story quotes, by run name. */
const EVENTS: Record<string, RecordedEvent[]> = { "normal-1": normal1Events };

/** Every screen of the story file, the opening first, in reading order. */
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

/**
 * The number printed on a claim: claims count from 1 through the story file in reading order, so a marker
 * beside a statement and the list behind "Open the evidence" show the same numbers.
 */
export function claimNumbers(screenId: string): { first: number; last: number } {
  let before = 0;
  for (const screen of allScreens()) {
    if (screen.id === screenId) return { first: before + 1, last: before + screen.claims.length };
    before += screen.claims.length;
  }
  throw new Error(`content: no screen ${screenId}`);
}

/** Where a claim comes from, in one line. Empty for general background, which names no source. */
export function claimSource(claim: Claim): string {
  const cite = claim.citation ?? claim.uefi_pointer;
  if (cite)
    return `${cite.document} ${cite.version}, section ${cite.section}, ${cite.title}. PDF page ${cite.pdf_page}`;
  if (claim.basis === "recording") return `${claim.file ?? `recordings/${claim.run}/recording.json`}: ${claim.field}`;
  return claim.source ?? "";
}

/**
 * What a screen lacks that the scene needs in order to draw it. An empty list means the screen can be shown.
 * The content has its own, stricter check against the recordings; this one guards the site's reading of it.
 */
export function screenProblems(screen: Screen): string[] {
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

  const evidence = screen.evidence;
  if (!evidence) problems.push("no evidence");
  else if (evidence.recorded) {
    if (!evidence.text) problems.push("recorded evidence has no line");
    if (evidence.kind === "event") {
      attempt("evidence", () => {
        const event = recordedEvent(evidence.run, evidence.event_index ?? -1);
        if (event.summary !== evidence.text) throw new Error("the line is not the event's summary");
      });
    }
  } else if (!evidence.label) problems.push("missing evidence has no label");

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

  const picture = screen.picture;
  if (!picture) problems.push("no picture");
  else {
    if (picture.plate !== "board" && picture.plate !== "laptop") problems.push(`unknown plate ${picture.plate}`);
    for (const part of [...picture.lit, ...picture.newly_lit])
      if (!PARTS.includes(part)) problems.push(`unknown part ${part}`);
    if (picture.newly_lit.some((part) => !picture.lit.includes(part))) problems.push("a newly lit part is not lit");
  }
  return problems;
}
