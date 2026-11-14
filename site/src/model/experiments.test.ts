// What the site says about an experiment when nothing is on file, when a pilot is, and when a score is.
import { describe, expect, it } from "vitest";
import {
  banksAgreeing,
  cardStates,
  expectation,
  experimentState,
  experimentsOf,
  furthest,
  onFile,
  registersDiffering,
  totals,
  type ComparisonFile,
  type Files,
  type PredictionFile,
  type RunInfo,
  type ScoreFile,
} from "./experiments";

const NOTHING: Files = { runs: [], comparisons: [], scores: [], predictions: [] };

const run = (name: string, experiment: string, kind: string, outcome = "accepted"): RunInfo => ({
  name,
  experiment,
  kind,
  change: "a change",
  outcome,
});

const comparison = (changed: RunInfo, differing: number[]): { path: string; file: ComparisonFile } => ({
  path: `recordings/comparisons/normal-1_vs_${changed.name}.json`,
  file: {
    format: "lux-comparison/1",
    baseline: { run: "normal-1", experiment: "normal", kind: "normal" },
    changed: { run: changed.name, experiment: changed.experiment, kind: changed.kind },
    identical: false,
    outcome: { baseline: "accepted", changed: changed.outcome },
    first_differing_event: null,
    pcrs_differing: { sha1: differing, sha256: differing },
    pcrs_same: { sha1: [0], sha256: [0] },
    events_only_in_baseline: [],
    events_only_in_changed: [],
    console_first_differing_line: null,
  },
});

const score = (experiment: string, met: number, required: number, correct: number, open: number): ScoreFile => ({
  format: "lux-score/1",
  experiment,
  run: `${experiment}-1`,
  required_met: met,
  required_total: required,
  open_correct: correct,
  open_total: open,
  mismatches: correct < open ? ["pcr1"] : [],
  rows: [
    { id: "refused", basis: "uefi-required", held: met === required },
    { id: "pcr1", basis: "this-firmware", held: correct === open },
  ],
});

const prediction = (experiment: string): PredictionFile => ({
  format: "lux-prediction/1",
  experiment,
  rows: [{ id: "refused", field: "outcome.changed", basis: "uefi-required", expect: "refused" }],
});

describe("an experiment with nothing on file", () => {
  it("is not run, and has no recording, comparison, score or prediction", () => {
    expect(experimentState("signature-byte", NOTHING)).toEqual({
      experiment: "signature-byte",
      status: "not-run",
      run: null,
      comparison: null,
      score: null,
      prediction: null,
    });
  });

  it("stays not run while only its prediction is on file, and names the prediction", () => {
    const state = experimentState("signature-byte", { ...NOTHING, predictions: [prediction("signature-byte")] });
    expect(state.status).toBe("not-run");
    expect(state.prediction?.rows).toHaveLength(1);
    expect(onFile(state)).toBe(true);
  });

  it("is not taken for another experiment's recording", () => {
    const files = { ...NOTHING, runs: [run("e1", "e1", "pilot")] };
    expect(experimentState("e4", files).status).toBe("not-run");
    expect(onFile(experimentState("e4", files))).toBe(false);
  });
});

describe("a pilot on file", () => {
  const e5 = run("e5", "e5", "pilot", "refused");
  const files: Files = {
    ...NOTHING,
    runs: [run("normal-1", "normal", "normal"), e5],
    comparisons: [comparison(e5, [4, 5, 7])],
  };
  const state = experimentState("e5", files);

  it("is a pilot, with its recording and its comparison with the normal run", () => {
    expect(state.status).toBe("pilot");
    expect(state.run?.outcome).toBe("refused");
    expect(state.comparison?.path).toBe("recordings/comparisons/normal-1_vs_e5.json");
    expect(state.score).toBeNull();
  });

  it("gives the registers that differ, and the banks in which the same ones do", () => {
    expect(registersDiffering(state.comparison!.file)).toEqual([4, 5, 7]);
    expect(banksAgreeing(state.comparison!.file)).toEqual(["sha1", "sha256"]);
  });

  it("belongs to an experiment by the name the recording gives itself, not by its folder", () => {
    const renamed = { ...NOTHING, runs: [run("my-run", "e5", "pilot", "refused")] };
    expect(experimentState("e5", renamed).run?.name).toBe("my-run");
  });

  it("is never scored into the headline numbers", () => {
    expect(totals(files.scores)).toBeNull();
  });
});

describe("a counted experiment", () => {
  const counted = run("signature-byte-1", "signature-byte", "counted", "refused");
  const recorded: Files = { ...NOTHING, runs: [counted], comparisons: [comparison(counted, [4, 5, 7])] };

  it("is recorded and not yet scored while no score file is on file", () => {
    expect(experimentState("signature-byte", recorded).status).toBe("recorded");
  });

  it("is scored once its score file is on file, and keeps the mismatch as a mismatch", () => {
    const files = { ...recorded, scores: [score("signature-byte", 1, 1, 2, 3)] };
    const state = experimentState("signature-byte", files);
    expect(state.status).toBe("scored");
    expect(state.score?.mismatches).toEqual(["pcr1"]);
  });

  it("sums the two headline numbers over every score on file", () => {
    expect(totals([score("signature-byte", 1, 1, 2, 3), score("boot-order-same", 0, 1, 4, 4)])).toEqual({
      requiredMet: 1,
      requiredTotal: 2,
      openCorrect: 6,
      openTotal: 7,
      experiments: 2,
    });
  });
});

describe("a card that stands for more than one form of its experiment", () => {
  const same = run("boot-order-same-1", "boot-order-same", "counted");
  const files: Files = {
    ...NOTHING,
    runs: [same],
    predictions: [prediction("boot-order-same"), prediction("boot-order-different")],
    scores: [score("boot-order-same", 1, 1, 1, 1)],
  };

  it("finds every form on file by the card's name and a suffix, and nothing else", () => {
    expect(experimentsOf("boot-order", files)).toEqual(["boot-order-different", "boot-order-same"]);
    expect(experimentsOf("order", files)).toEqual(["order"]);
    expect(experimentsOf("rebuilt-firmware", files)).toEqual(["rebuilt-firmware"]);
  });

  it("gives each form its own state, and the card the furthest of them", () => {
    const states = cardStates("boot-order", files);
    expect(states.map((state) => state.status)).toEqual(["not-run", "scored"]);
    expect(furthest(states)).toBe("scored");
    expect(furthest(cardStates("rebuilt-firmware", files))).toBe("not-run");
    expect(furthest([])).toBe("not-run");
  });
});

describe("a prediction row", () => {
  it("reads as the field, the relation and the value written before the run", () => {
    const row = { id: "r", field: "outcome.changed", basis: "uefi-required" };
    expect(expectation({ ...row, expect: "refused" })).toBe('outcome.changed equals "refused"');
    expect(expectation({ ...row, field: "pcrs_differing.sha256", expect_contains: [4] })).toBe(
      "pcrs_differing.sha256 holds all of [4]",
    );
    expect(expectation({ ...row, expect_excludes: [0, 1] })).toBe("outcome.changed holds none of [0,1]");
    expect(expectation({ ...row, expect_one_of: ["a", "b"] })).toBe('outcome.changed is one of ["a","b"]');
    expect(expectation(row)).toBe("outcome.changed");
  });
});
