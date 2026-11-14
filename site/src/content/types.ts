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
  /** Lines of a run's console, by place in its `console` list, from 0. */
  console_lines: { run: string; positions: number[]; note?: string }[];
  /** Lines of the loader's report, by place in `loader_report`, from 0. `highlight` names places to mark. */
  loader_report_lines: { run: string; positions: number[]; prefix?: string; highlight?: number[]; note?: string }[];
  /** Records of a run's log, by their own index, from 1. */
  events: { run: string; indexes: number[]; note?: string }[];
  /** Registers of one hash bank, as read at the end of the run. */
  pcrs: { run: string; bank: string; registers: number[]; note?: string }[];
  /** The comparison file a two-run screen rests on. */
  comparison?: { file: string; baseline: string; changed: string };
  console_note?: string;
  pilot_note?: string;
  /** Basis labels to explain on this screen, beside the ones its claims carry. */
  basis_labels?: Basis[];
  other_fields?: { file: string; field: string; value?: string | number | boolean; why: string }[];
  explanation: string;
  definitions: Definition[];
  not_shown?: string[];
}

export interface Picture {
  plate: "board" | "laptop";
  lit: Part[];
  newly_lit: Part[];
  /** The lit parts the screen is about. Absent: the newly lit ones. */
  attention?: Part[];
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
  /** Which of the two protections the screen follows, where it follows one. */
  thread?: "secure-boot" | "measured-boot";
  /** A pilot screen: the sentence that says the run is shown and not counted. */
  pilot_label?: string;
  /** The closing screen: the note under its picture, and the link to the earlier site. */
  picture_caption?: string;
  handover?: { to: string; text: string; link_label: string; note: string };
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
  /** The name the firmware's source uses for this stage, where it has one. */
  stage_name: { name: string; expansion: string; attribution: string } | null;
  /** Where the label comes from, when the stop has no stage name. */
  label_basis?: string;
  not_shown: string[];
  /** The id of the one screen whose statement stands for the stop. */
  headline: string;
  screens: Screen[];
}

export interface StoryFile {
  format: string;
  /** Only the first story file has the opening. */
  opening?: OpeningScreen;
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
  /** The record's fingerprint in the SHA-256 bank, 64 hexadecimal digits. */
  digest_sha256: string;
}
