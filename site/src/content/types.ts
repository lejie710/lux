// The shape of the content files in ../../../content, as far as the site reads them. content/README.md is the
// authority; this file names only the fields a component draws.

export const BASES = ["uefi-required", "uefi-platform", "tcg-unread", "this-firmware", "recording", "general"] as const;
export type Basis = (typeof BASES)[number];

/** The parts of the board a picture can light. */
export const PARTS = [
  "power",
  "firmware",
  "processor",
  "memory",
  "controllers",
  "storage",
  "security",
  "ribbon",
] as const;
export type Part = (typeof PARTS)[number];

export interface Statement {
  text: string;
  /** Null, or one phrase of `text`, set in the warm colour. */
  emphasis: string | null;
}

export interface Citation {
  document: string;
  version: string;
  section: string;
  title: string;
  pdf_page: number;
  pdf_pages?: number[];
  says?: string;
}

export interface Claim {
  id?: string;
  text: string;
  basis: Basis;
  citation?: Citation;
  uefi_pointer?: Citation;
  source?: string;
  source_ref?: string;
  run?: string;
  file?: string;
  field?: string;
  note?: string;
  reason?: string;
}

/** One line copied from a committed recording. */
export interface RecordedEvidence {
  recorded: true;
  kind: "event" | "console" | "loader_report";
  run: string;
  file: string;
  field: string;
  position: number;
  text: string;
  event_index?: number;
  highlight?: string;
  caption?: string;
}

/** Evidence that does not exist, and says so. */
export interface MissingEvidence {
  recorded: false;
  kind: "not-recorded";
  label: string;
  caption?: string;
}

export type Evidence = RecordedEvidence | MissingEvidence;

export type Definition = { glossary: string } | { term: string; definition: string };

export interface Detail {
  events: { run: string; indexes: number[]; note?: string }[];
  other_fields?: { file: string; field: string; value?: string | number | boolean; why: string }[];
  explanation: string;
  definitions: Definition[];
  not_shown?: string[];
}

export interface Picture {
  plate: "board" | "laptop";
  lit: Part[];
  newly_lit: Part[];
  screen: "none" | "dark" | "dawn";
  note: string;
}

export interface Screen {
  id: string;
  kind: string;
  stop: number | null;
  statement: Statement;
  support: string | null;
  evidence: Evidence;
  detail: Detail;
  claims: Claim[];
  picture: Picture;
}

export interface OpeningScreen extends Screen {
  kind: "opening";
  eyebrow: string;
  title: Statement;
  invitation: { label: string; line: string };
  scope_note: string;
}

export interface Stop {
  number: number;
  of: number;
  id: string;
  label: string;
  not_shown: string[];
  /** The id of the one screen whose statement stands for the stop. */
  headline: string;
  screens: Screen[];
}

export interface StoryFile {
  format: string;
  opening: OpeningScreen;
  stops: Stop[];
}

export interface BasisLabel {
  basis: Basis;
  label: string;
  meaning: string;
}

export interface GlossaryEntry {
  id: string;
  term: string;
  definition: string;
}

export interface FirmwareSource {
  id: string;
  project: string;
  path: string;
  url: string;
  read_at: string;
  licence: string;
}

/** One record of the boot's log, as a recording stores it. */
export interface RecordedEvent {
  index: number;
  pcr: number;
  type: string;
  summary: string;
}
