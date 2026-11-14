// What is known about an experiment, worked out from the files on disk and from nothing else: whether a
// recording of it exists, what its comparison with the normal run holds, and whether it has been scored.
// These are plain functions over plain data, so the absent, pilot and scored cases can each be tested.

/** The part of a recording that says which run it is and how it ended. */
export interface RunInfo {
  /** The folder the recording lies in. */
  name: string;
  experiment: string;
  /** "normal", "pilot" or "counted". */
  kind: string;
  change: string;
  /** "accepted", "refused" or "timeout". */
  outcome: string;
}

export interface ComparedEvent {
  index: number;
  pcr: number;
  type: string;
  digest_sha256: string;
}

/** A comparison file, format lux-comparison/1, as far as the site reads it. */
export interface ComparisonFile {
  format: string;
  baseline: { run: string; experiment: string; kind: string };
  changed: { run: string; experiment: string; kind: string };
  identical: boolean;
  outcome: { baseline: string; changed: string };
  first_differing_event: {
    index: number;
    stop: number;
    baseline: Omit<ComparedEvent, "index"> | null;
    changed: Omit<ComparedEvent, "index"> | null;
  } | null;
  /** Register numbers by hash bank. */
  pcrs_differing: Record<string, number[]>;
  pcrs_same: Record<string, number[]>;
  events_only_in_baseline: ComparedEvent[];
  events_only_in_changed: ComparedEvent[];
  /** Counted from 1. */
  console_first_differing_line: number | null;
  console_first_differing_text?: { baseline: string | null; changed: string | null };
  refusal_lines?: { baseline: string[]; changed: string[] };
}

/** A score file, format lux-score/1. */
export interface ScoreFile {
  format: string;
  experiment: string;
  run: string;
  required_met: number;
  required_total: number;
  open_correct: number;
  open_total: number;
  mismatches: string[];
  rows: { id: string; basis: string; held: boolean }[];
  prediction?: { path?: string; sha256?: string; commit?: string };
}

/** One row of a prediction: a field of the comparison, one expectation about it, and where that comes from. */
export interface PredictionRow {
  id: string;
  field: string;
  basis: string;
  citation?: { document: string; version: string; section: string; page: number } | null;
  reason?: string;
  source?: string;
  [expectation: string]: unknown;
}

/** A prediction file, format lux-prediction/1. */
export interface PredictionFile {
  format: string;
  experiment: string;
  written?: string;
  change?: string;
  rows: PredictionRow[];
  wrong_if?: string[];
  not_scored?: string[];
}

export interface Files {
  runs: RunInfo[];
  comparisons: { path: string; file: ComparisonFile }[];
  scores: ScoreFile[];
  predictions: PredictionFile[];
}

export const COMPARISON_FORMAT = "lux-comparison/1";
export const SCORE_FORMAT = "lux-score/1";
export const PREDICTION_FORMAT = "lux-prediction/1";

export type ExperimentStatus = "not-run" | "pilot" | "recorded" | "scored";

export interface ExperimentState {
  /** The experiment as the recorder names it. */
  experiment: string;
  /**
   * not-run: no recording of it is on file. pilot: recorded, and never to be counted. recorded: a counted
   * run is on file and no score is. scored: a score file is on file.
   */
  status: ExperimentStatus;
  run: RunInfo | null;
  comparison: { path: string; file: ComparisonFile } | null;
  score: ScoreFile | null;
  prediction: PredictionFile | null;
}

/**
 * What the files say about one experiment. A recording belongs to an experiment by the experiment it names
 * itself, never by its folder name; a comparison belongs to it when its changed side is that experiment.
 */
export function experimentState(experiment: string, files: Files): ExperimentState {
  const run = files.runs.find((r) => r.experiment === experiment) ?? null;
  const prediction = files.predictions.find((p) => p.experiment === experiment) ?? null;
  if (!run) return { experiment, status: "not-run", run: null, comparison: null, score: null, prediction };
  const comparison =
    files.comparisons.find((c) => c.file.changed.experiment === experiment && c.file.changed.run === run.name) ?? null;
  const score = files.scores.find((s) => s.experiment === experiment) ?? null;
  const status: ExperimentStatus = score ? "scored" : run.kind === "pilot" ? "pilot" : "recorded";
  return { experiment, status, run, comparison, score, prediction };
}

/**
 * The experiments on file that belong to one card of the content. A card names an experiment, and the
 * recorder may run it in more than one form, each named with the card's name and a suffix (`boot-order-same`
 * for the card `boot-order`). With nothing on file the card's own name stands, and its state is "not run".
 */
export function experimentsOf(card: string, files: Files): string[] {
  const named = [...files.runs, ...files.predictions, ...files.scores]
    .map((file) => file.experiment)
    .filter((experiment) => experiment === card || experiment.startsWith(`${card}-`));
  return named.length > 0 ? [...new Set(named)].sort() : [card];
}

/** What the files say about each form of a card's experiment. */
export function cardStates(card: string, files: Files): ExperimentState[] {
  return experimentsOf(card, files).map((experiment) => experimentState(experiment, files));
}

const FURTHEST: ExperimentStatus[] = ["not-run", "pilot", "recorded", "scored"];

/** The state of a card as a whole: the furthest any form of its experiment has got. */
export function furthest(states: readonly ExperimentState[]): ExperimentStatus {
  return FURTHEST[Math.max(0, ...states.map((state) => FURTHEST.indexOf(state.status)))];
}

/** Whether anything at all is on file for an experiment: a recording, a prediction or a score. */
export const onFile = (state: ExperimentState) => Boolean(state.run || state.prediction || state.score);

/** The registers that differ between the two runs of a comparison, in the SHA-256 bank or else the first bank. */
export function registersDiffering(file: ComparisonFile): number[] {
  return file.pcrs_differing.sha256 ?? Object.values(file.pcrs_differing)[0] ?? [];
}

/** The hash banks in which exactly those registers differ. */
export function banksAgreeing(file: ComparisonFile): string[] {
  const wanted = registersDiffering(file).join();
  return Object.keys(file.pcrs_differing).filter((bank) => file.pcrs_differing[bank].join() === wanted);
}

export interface Totals {
  requiredMet: number;
  requiredTotal: number;
  openCorrect: number;
  openTotal: number;
  /** How many experiments the numbers are summed over. */
  experiments: number;
}

/** The two headline numbers over every score on file. Null while there is none: nothing is claimed. */
export function totals(scores: readonly ScoreFile[]): Totals | null {
  if (scores.length === 0) return null;
  return scores.reduce<Totals>(
    (sum, score) => ({
      requiredMet: sum.requiredMet + score.required_met,
      requiredTotal: sum.requiredTotal + score.required_total,
      openCorrect: sum.openCorrect + score.open_correct,
      openTotal: sum.openTotal + score.open_total,
      experiments: sum.experiments + 1,
    }),
    { requiredMet: 0, requiredTotal: 0, openCorrect: 0, openTotal: 0, experiments: 0 },
  );
}

/** How each kind of expectation reads between the field and its value. */
const EXPECTATIONS: Record<string, string> = {
  expect: "equals",
  expect_one_of: "is one of",
  expect_contains: "holds all of",
  expect_excludes: "holds none of",
  expect_text_contains: "contains the text",
};

/** A prediction row's one expectation, as the field, the relation and the value written before the run. */
export function expectation(row: PredictionRow): string {
  const key = Object.keys(EXPECTATIONS).find((k) => k in row);
  if (!key) return row.field;
  return `${row.field} ${EXPECTATIONS[key]} ${JSON.stringify(row[key])}`;
}
