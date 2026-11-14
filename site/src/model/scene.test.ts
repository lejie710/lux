// The scene's steps and the layers each one shows.
import { describe, expect, it } from "vitest";
import { OPENING, headline, stop } from "../content/load";
import { PARTS } from "../content/types";
import { STEPS, STEP_COUNT, layersAt, splitEmphasis } from "./scene";

const litParts = (n: number) => PARTS.filter((part) => layersAt(STEPS[n]).parts[part].on);

describe("the first scene's steps", () => {
  it("has three steps: the opening, the way inside, and stop 1", () => {
    expect(STEP_COUNT).toBe(3);
    expect(STEPS.map((s) => s.kind)).toEqual(["opening", "inside", "stop"]);
    expect(STEPS[0].screen).toBe(OPENING);
    expect(STEPS[1].screen).toBe(OPENING);
    expect(STEPS[2].screen).toBe(headline(stop(1)));
    expect(STEPS[2].stop?.number).toBe(1);
  });

  it("takes each step's picture from the content, not from the scene", () => {
    expect(STEPS[0].plate).toBe(OPENING.picture.plate);
    expect(STEPS[2].plate).toBe(headline(stop(1)).picture.plate);
    expect(STEPS[2].lit).toEqual(headline(stop(1)).picture.lit);
  });
});

describe("the layers a step shows", () => {
  it("shows the laptop alone at the opening", () => {
    const layers = layersAt(STEPS[0]);
    expect(layers.laptop).toBe(true);
    expect(layers.board).toBe(false);
    expect(litParts(0)).toEqual([]);
  });

  it("shows the board, wholly dark, once the camera is inside", () => {
    const layers = layersAt(STEPS[1]);
    expect(layers.laptop).toBe(false);
    expect(layers.board).toBe(true);
    expect(litParts(1)).toEqual([]);
  });

  it("lights power and the processor at stop 1, and nothing else", () => {
    const layers = layersAt(STEPS[2]);
    expect(layers.board).toBe(true);
    expect(layers.laptop).toBe(false);
    expect(litParts(2)).toEqual(["power", "processor"]);
  });

  it("lets light spread: power first, then the processor", () => {
    const { parts } = layersAt(STEPS[2]);
    expect(parts.power.order).toBe(0);
    expect(parts.processor.order).toBe(1);
  });

  it("never puts light out along the scene, and never lights a part while the laptop is in view", () => {
    for (let n = 1; n < STEP_COUNT; n++) for (const part of litParts(n - 1)) expect(litParts(n)).toContain(part);
    for (let n = 0; n < STEP_COUNT; n++) if (layersAt(STEPS[n]).laptop) expect(litParts(n)).toEqual([]);
  });

  it("declares every part at every step, so any step can follow any other", () => {
    for (const step of STEPS) expect(Object.keys(layersAt(step).parts).sort()).toEqual([...PARTS].sort());
  });

  it("shows exactly one plate at a time", () => {
    for (const step of STEPS) expect(layersAt(step).laptop).not.toBe(layersAt(step).board);
  });
});

describe("splitEmphasis", () => {
  it("cuts a statement around its emphasis", () => {
    expect(splitEmphasis("Before light.", "light.")).toEqual(["Before ", "light.", ""]);
    expect(splitEmphasis("a b c", "b")).toEqual(["a ", "b", " c"]);
  });
  it("leaves a statement whole when there is no emphasis, or it is not a phrase of it", () => {
    expect(splitEmphasis("a b c", null)).toEqual(["a b c", "", ""]);
    expect(splitEmphasis("a b c", "z")).toEqual(["a b c", "", ""]);
  });
});
