// The story's steps and the layers each one shows.
import { describe, expect, it } from "vitest";
import { OPENING, STOPS, headline, stop } from "../content/load";
import { PARTS } from "../content/types";
import { PART_BOXES, STEPS, STEP_COUNT, firstStepOf, focusAt, layersAt, pictureLabel, splitEmphasis } from "./scene";

const litParts = (n: number) => PARTS.filter((part) => layersAt(STEPS[n]).parts[part].on);
const strongParts = (n: number) => PARTS.filter((part) => layersAt(STEPS[n]).parts[part].strong);
const at = (id: string) => STEPS.findIndex((step) => step.id === id);
const storyScreens = STOPS.flatMap((s) => s.screens);

describe("the story's steps", () => {
  it("has the opening, the way inside, and one step per screen of the seven stops", () => {
    expect(STEP_COUNT).toBe(2 + storyScreens.length);
    expect(STEPS.slice(0, 3).map((s) => s.kind)).toEqual(["opening", "inside", "stop"]);
    expect(STEPS[0].screen).toBe(OPENING);
    expect(STEPS[1].screen).toBe(OPENING);
    expect(STEPS.slice(2).map((s) => s.screen)).toEqual(storyScreens);
  });

  it("keeps the first scene's three steps where they were", () => {
    expect(STEPS[2].screen).toBe(headline(stop(1)));
    expect(STEPS[2].stop?.number).toBe(1);
  });

  it("gives every step its own id, so every step has its own address and controls", () => {
    expect(new Set(STEPS.map((s) => s.id)).size).toBe(STEP_COUNT);
  });

  it("walks the stops in order, 1 to 7, and counts the screens inside each", () => {
    const numbers = STEPS.slice(2).map((s) => s.stop!.number);
    expect([...numbers].sort((a, b) => a - b)).toEqual(numbers);
    expect(new Set(numbers)).toEqual(new Set([1, 2, 3, 4, 5, 6, 7]));
    for (const step of STEPS.slice(2)) {
      expect(step.screenCount).toBe(step.stop!.screens.length);
      expect(step.stop!.screens[step.screenAt - 1]).toBe(step.screen);
    }
  });

  it("knows the first step of each stop, where a mark of the rail leads", () => {
    expect(firstStepOf(1)).toBe(2);
    for (const s of STOPS) expect(STEPS[firstStepOf(s.number)].screen).toBe(s.screens[0]);
  });

  it("takes each step's picture from the content, not from the scene", () => {
    for (const step of STEPS.slice(2)) {
      expect(step.lit).toEqual(step.screen.picture.lit);
      expect(step.newlyLit).toEqual(step.screen.picture.newly_lit);
      expect(step.view === "board").toBe(step.screen.picture.plate === "board");
    }
  });

  it("names the pilot and the closing screen as what they are", () => {
    expect(STEPS[at("s6-pilot-refusal")].kind).toBe("pilot");
    expect(STEPS[STEP_COUNT - 1].kind).toBe("closing");
    expect(STEPS.filter((s) => s.kind === "closing")).toHaveLength(1);
  });
});

describe("the layers a step shows", () => {
  it("shows the laptop alone at the opening", () => {
    const layers = layersAt(STEPS[0]);
    expect(layers.laptop).toBe(true);
    expect(layers.board).toBe(false);
    expect(layers.ending).toBe(false);
    expect(litParts(0)).toEqual([]);
  });

  it("shows the board, wholly dark, once the camera is inside", () => {
    const layers = layersAt(STEPS[1]);
    expect(layers.laptop).toBe(false);
    expect(layers.board).toBe(true);
    expect(litParts(1)).toEqual([]);
    expect(strongParts(1)).toEqual([]);
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

  it("lights each stop's parts as its screens say: one more area per stop, the display cable last", () => {
    const first = (n: number) => litParts(firstStepOf(n));
    expect(first(2)).toEqual(["power", "firmware", "processor"]);
    expect(first(3)).toEqual(["power", "firmware", "processor", "memory", "security"]);
    expect(first(4)).toContain("controllers");
    expect(first(5)).toContain("storage");
    expect(first(6)).not.toContain("ribbon");
    expect(litParts(at("s7-exit-call"))).toEqual([...PARTS]);
  });

  it("never puts light out along the story, and lights nothing while the laptop before power is in view", () => {
    for (let n = 1; n < STEP_COUNT; n++) for (const part of litParts(n - 1)) expect(litParts(n)).toContain(part);
    for (let n = 0; n < STEP_COUNT; n++) if (layersAt(STEPS[n]).laptop) expect(litParts(n)).toEqual([]);
  });

  it("declares every part at every step, so any step can follow any other", () => {
    for (const step of STEPS) expect(Object.keys(layersAt(step).parts).sort()).toEqual([...PARTS].sort());
  });

  it("shows exactly one of the three pictures at a time", () => {
    for (const step of STEPS) {
      const { laptop, board, ending } = layersAt(step);
      expect([laptop, board, ending].filter(Boolean)).toHaveLength(1);
    }
  });

  it("holds the picture inside a stop: the lit parts change only where a screen says a part is new", () => {
    for (let n = 3; n < STEP_COUNT; n++) {
      if (STEPS[n].newlyLit.length === 0) expect(litParts(n)).toEqual(litParts(n - 1));
    }
  });

  it("gives the parts a step is about a stronger light: the new ones, or the ones the screen names", () => {
    expect(strongParts(2)).toEqual(["power", "processor"]);
    expect(strongParts(at("s6-verify"))).toEqual(["security"]);
    expect(strongParts(at("s6-load"))).toEqual(["storage"]);
    for (let n = 0; n < STEP_COUNT; n++) for (const part of strongParts(n)) expect(litParts(n)).toContain(part);
  });

  it("lights the ground between the parts only once every part is lit", () => {
    for (let n = 0; n < STEP_COUNT; n++) expect(layersAt(STEPS[n]).whole.on).toBe(litParts(n).length === PARTS.length);
    expect(layersAt(STEPS[at("s7-exit-call")]).whole.on).toBe(true);
    expect(layersAt(STEPS[at("s7-tables")]).whole.on).toBe(false);
  });
});

describe("the ending", () => {
  const noReturn = at("s7-no-return");
  const last = STEP_COUNT - 1;

  it("pulls back from the board to the laptop with its inside awake, then lights the screen", () => {
    expect(layersAt(STEPS[noReturn - 1]).board).toBe(true);
    expect(layersAt(STEPS[noReturn])).toMatchObject({ board: false, laptop: false, ending: true, screenLit: false });
    expect(layersAt(STEPS[last])).toMatchObject({ board: false, laptop: false, ending: true, screenLit: true });
  });

  it("lights the screen at the last step only", () => {
    expect(STEPS.filter((step) => layersAt(step).screenLit)).toEqual([STEPS[last]]);
  });

  it("shows the refused pilot the same way: inside awake, screen dark", () => {
    expect(layersAt(STEPS[at("s6-pilot-refusal")])).toMatchObject({ ending: true, screenLit: false });
  });

  it("keeps the board lit behind the pulled-back laptop, so the camera can return to it", () => {
    const pilot = at("s6-pilot-refusal");
    expect(litParts(pilot)).toEqual(litParts(pilot - 1));
    expect(strongParts(pilot)).toEqual([]);
    expect(layersAt(STEPS[pilot + 1]).board).toBe(true);
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

describe("focusAt", () => {
  it("looks at the middle of the parts a step lights", () => {
    const { power, processor } = PART_BOXES;
    expect(focusAt(2)).toBeCloseTo((Math.min(power.left, processor.left) + Math.max(power.right, processor.right)) / 2);
  });
  it("looks, while the board is dark, where the next step will: the picture does not slide as light arrives", () => {
    expect(focusAt(1)).toBe(focusAt(2));
    expect(focusAt(0)).toBe(focusAt(2));
  });
  it("looks at the part a screen is about, where the screen names one", () => {
    const { security } = PART_BOXES;
    expect(focusAt(at("s6-verify"))).toBeCloseTo((security.left + security.right) / 2);
  });
  it("has somewhere to look at every step, the laptop's steps included", () => {
    for (let n = 0; n < STEP_COUNT; n++) {
      expect(focusAt(n)).toBeGreaterThan(0);
      expect(focusAt(n)).toBeLessThan(1);
    }
    expect(focusAt(STEP_COUNT - 1)).toBe(focusAt(at("s7-exit-events")));
  });
  it("keeps every part stop 1 lights inside a window two thirds of the board wide", () => {
    const { power, processor } = PART_BOXES;
    expect(Math.max(power.right, processor.right) - Math.min(power.left, processor.left)).toBeLessThanOrEqual(2 / 3);
  });
  it("knows where every part lies", () => {
    for (const part of PARTS) {
      expect(PART_BOXES[part].left).toBeLessThan(PART_BOXES[part].right);
      expect(PART_BOXES[part].right).toBeLessThanOrEqual(1);
    }
  });
});

describe("pictureLabel", () => {
  it("says which picture is shown and which parts are lit", () => {
    expect(pictureLabel(STEPS[0])).toMatch(/laptop/);
    expect(pictureLabel(STEPS[1])).toBe("Illustration: a circuit board, dark.");
    expect(pictureLabel(STEPS[2])).toBe("Illustration: a circuit board. Lit: power, processor.");
    expect(pictureLabel(STEPS[at("s7-exit-call")])).toBe("Illustration: a circuit board, every part lit.");
    expect(pictureLabel(STEPS[at("s7-no-return")])).toMatch(/inside awake, its screen dark/);
    expect(pictureLabel(STEPS[STEP_COUNT - 1])).toMatch(/screen lit/);
  });
});
