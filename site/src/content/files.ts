// The files beside the content that the experiments and sources pages read: which run each recording is,
// the comparison files, the score files, the predictions, and a recording's own account of how it was made.
// Whatever is on disk when the site is built is shown; what is absent is shown as absent.
import {
  COMPARISON_FORMAT,
  PREDICTION_FORMAT,
  SCORE_FORMAT,
  banksAgreeing,
  registersDiffering,
  type ComparedEvent,
  type ComparisonFile,
  type Files,
  type PredictionFile,
  type RunInfo,
  type ScoreFile,
} from "../model/experiments";
import { RUNS, eventAt, lineAt, registerAt } from "./load";

interface RunBlock {
  experiment: string;
  kind: string;
  change: string;
}

/** A recording's own account of how it was made. */
export interface Provenance {
  recorded_at: string;
  host_os: string;
  tools: Record<string, string>;
  firmware: { file: string; sha256: string };
  keys: Record<string, string>;
  loader: Record<string, string>;
  vars_template_sha256: string;
  qemu_command_line: string;
  swtpm_command_line: string;
  prediction: unknown;
}

const folderOf = (path: string) => path.split("/").at(-2) ?? path;
const recordings = "../../../recordings/*/recording.json";
const RUN_BLOCKS = import.meta.glob<RunBlock>("../../../recordings/*/recording.json", { eager: true, import: "run" });
const OUTCOMES = import.meta.glob<{ result: string }>("../../../recordings/*/recording.json", {
  eager: true,
  import: "outcome",
});
const PROVENANCES = import.meta.glob<Provenance>("../../../recordings/*/recording.json", {
  eager: true,
  import: "provenance",
});
const MAY_VARY = import.meta.glob<string[]>("../../../recordings/*/recording.json", {
  eager: true,
  import: "may_vary",
});
const pathOf = (run: string) => recordings.replace("*", run);

const COMPARISONS = import.meta.glob<ComparisonFile>("../../../recordings/comparisons/*.json", {
  eager: true,
  import: "default",
});
// A score has no fixed home yet: it is written wherever the check command is told to. These are the places
// looked in, and a file counts only if it says it is a score.
const SCORES = import.meta.glob<ScoreFile>(
  ["../../../results/*.json", "../../../recordings/scores/*.json", "../../../recordings/*/score.json"],
  { eager: true, import: "default" },
);
const PREDICTIONS = import.meta.glob<PredictionFile>("../../../predictions/*.json", {
  eager: true,
  import: "default",
});

/** A path as the repository names it, from its root. */
const fromRoot = (path: string) => path.replace(/^(\.\.\/)+/, "");

/** Everything on disk that says what has been run, compared, predicted and scored. */
export const FILES: Files = {
  runs: Object.entries(RUN_BLOCKS)
    .map(([path, run]): RunInfo => ({
      name: folderOf(path),
      experiment: run.experiment,
      kind: run.kind,
      change: run.change,
      outcome: OUTCOMES[path]?.result ?? "",
    }))
    .sort((a, b) => a.name.localeCompare(b.name)),
  comparisons: Object.entries(COMPARISONS)
    .filter(([, file]) => file.format === COMPARISON_FORMAT)
    .map(([path, file]) => ({ path: fromRoot(path), file }))
    .sort((a, b) => a.path.localeCompare(b.path)),
  scores: Object.values(SCORES).filter((file) => file.format === SCORE_FORMAT),
  predictions: Object.values(PREDICTIONS).filter((file) => file.format === PREDICTION_FORMAT),
};

/** The comparison file at a path counted from the repository's root, or null when it is not on disk. */
export function comparisonAt(path: string): { path: string; file: ComparisonFile } | null {
  return FILES.comparisons.find((c) => c.path === path) ?? null;
}

/** How a run says it was made, and the fields a comparison is told to ignore. Null when the run is not on disk. */
export function provenanceOf(run: string): { file: string; provenance: Provenance; mayVary: string[] } | null {
  const provenance = PROVENANCES[pathOf(run)];
  if (!provenance || !RUNS.includes(run)) return null;
  return { file: fromRoot(pathOf(run)), provenance, mayVary: MAY_VARY[pathOf(run)] ?? [] };
}

/** One record as a comparison names it, with the line the recording holds for it. */
export interface ComparedRecord extends ComparedEvent {
  /** The record's line in its own run, or empty when the recording has no record of that number. */
  summary: string;
}

/** A comparison file laid out for a page: both runs' values side by side, read from the two recordings. */
export interface ComparisonView {
  path: string;
  baseline: string;
  changed: string;
  identical: boolean;
  outcome: { baseline: string; changed: string };
  first: { index: number; stop: number; baseline: ComparedRecord | null; changed: ComparedRecord | null } | null;
  /** The registers that differ, each with its value in both runs, in one hash bank. */
  bank: string;
  registers: { pcr: number; baseline: string; changed: string }[];
  /** The banks in which exactly those registers differ, and the registers that are the same. */
  banks: string[];
  same: number[];
  onlyBaseline: ComparedRecord[];
  onlyChanged: ComparedRecord[];
  /** The first console line that differs, counted from 1, with both runs' lines. */
  consoleFirst: { line: number; baseline: string | null; changed: string | null } | null;
}

/** A comparison's records, registers and lines with the words and values the two recordings hold for them. */
export function comparisonView({ path, file }: { path: string; file: ComparisonFile }): ComparisonView {
  const withLine = (run: string, event: ComparedEvent): ComparedRecord => ({
    ...event,
    summary: eventAt(run, event.index)?.summary ?? "",
  });
  const base = file.baseline.run;
  const changed = file.changed.run;
  const first = file.first_differing_event;
  const bank = file.pcrs_differing.sha256 ? "sha256" : (Object.keys(file.pcrs_differing)[0] ?? "sha256");
  const line = file.console_first_differing_line;
  return {
    path,
    baseline: base,
    changed,
    identical: file.identical,
    outcome: file.outcome,
    first: first && {
      index: first.index,
      stop: first.stop,
      baseline: first.baseline && withLine(base, { ...first.baseline, index: first.index }),
      changed: first.changed && withLine(changed, { ...first.changed, index: first.index }),
    },
    bank,
    registers: registersDiffering(file).map((pcr) => ({
      pcr,
      baseline: registerAt(base, bank, pcr) ?? "",
      changed: registerAt(changed, bank, pcr) ?? "",
    })),
    banks: banksAgreeing(file),
    same: file.pcrs_same[bank] ?? [],
    onlyBaseline: file.events_only_in_baseline.map((event) => withLine(base, event)),
    onlyChanged: file.events_only_in_changed.map((event) => withLine(changed, event)),
    consoleFirst:
      line === null
        ? null
        : {
            line,
            baseline: file.console_first_differing_text?.baseline ?? lineAt(base, line - 1),
            changed: file.console_first_differing_text?.changed ?? lineAt(changed, line - 1),
          },
  };
}
