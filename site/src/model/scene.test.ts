// The story's steps and the layers each one shows.
import { describe, expect, it } from "vitest";
import { OPENING, STOPS, headline, stop } from "../content/load";
import { PARTS } from "../content/types";
import {
  PART_BOXES,
  STEPS,
  STEP_COUNT,
  firstStepOf,
  focusAt,
  layersAt,
  pictureLabel,
  spanAt,
  splitEmphasis,
  stepKey,
  stepPassed,
  stepShown,
  tileFrame,
} from "./scene";

const litParts = (n: number) => PARTS.filter((part) => layersAt(STEPS[n]).parts[part].on);
const strongParts = (n: number) => PARTS.filter((part) => layersAt(STEPS[n]).parts[part].strong);
const restingParts = (n: number) => PARTS.filter((part) => layersAt(STEPS[n]).parts[part].rest);
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

  it("turns down the lit parts a step is not about, so the part it is about is the one warm point", () => {
    const verify = at("s6-verify");
    expect(restingParts(verify)).toEqual(litParts(verify).filter((part) => part !== "security"));
    expect(restingParts(verify).length).toBeGreaterThan(0);
    for (let n = 0; n < STEP_COUNT; n++) {
      // A part rests only while it is lit, never while the step is about it, and only on the board.
      for (const part of restingParts(n)) expect(litParts(n)).toContain(part);
      expect(restingParts(n).filter((part) => strongParts(n).includes(part))).toEqual([]);
      if (STEPS[n].view !== "board") expect(restingParts(n)).toEqual([]);
    }
  });

  it("rests nothing once the whole board is lit: the last board step is the brightest of the story", () => {
    const lastBoard = STEPS.map((step) => step.view).lastIndexOf("board");
    expect(litParts(lastBoard)).toEqual([...PARTS]);
    expect(restingParts(lastBoard)).toEqual([]);
    expect(layersAt(STEPS[lastBoard]).whole).toMatchObject({ on: true, rest: false });
    for (let n = 0; n < STEP_COUNT; n++) if (layersAt(STEPS[n]).whole.on) expect(restingParts(n)).toEqual([]);
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
  it("says how wide a stretch of the board a step looks at, and holds it while the board is dark", () => {
    const { power, processor, security } = PART_BOXES;
    expect(spanAt(2)).toBeCloseTo(Math.max(power.right, processor.right) - Math.min(power.left, processor.left));
    expect(spanAt(1)).toBe(spanAt(2));
    expect(spanAt(at("s6-verify"))).toBeCloseTo(security.right - security.left);
    for (let n = 0; n < STEP_COUNT; n++) {
      expect(spanAt(n)).toBeGreaterThan(0);
      expect(spanAt(n)).toBeLessThanOrEqual(1);
    }
  });
  it("knows where every part lies", () => {
    for (const part of PARTS) {
      expect(PART_BOXES[part].left).toBeLessThan(PART_BOXES[part].right);
      expect(PART_BOXES[part].right).toBeLessThanOrEqual(1);
    }
  });
});

describe("stepKey", () => {
  it("goes one step on for Space and Page Down, and one step back for Shift with Space and Page Up", () => {
    for (let n = 0; n < STEP_COUNT - 1; n++) {
      expect(stepKey({ key: " " }, n, STEP_COUNT)).toBe(n + 1);
      expect(stepKey({ key: "PageDown" }, n, STEP_COUNT)).toBe(n + 1);
    }
    for (let n = 1; n < STEP_COUNT; n++) {
      expect(stepKey({ key: " ", shiftKey: true }, n, STEP_COUNT)).toBe(n - 1);
      expect(stepKey({ key: "PageUp" }, n, STEP_COUNT)).toBe(n - 1);
    }
  });
  it("leaves the key to the browser at the two ends, so the page before and after the story can be reached", () => {
    expect(stepKey({ key: "PageUp" }, 0, STEP_COUNT)).toBeNull();
    expect(stepKey({ key: " " }, STEP_COUNT - 1, STEP_COUNT)).toBeNull();
  });
  it("leaves every other key alone", () => {
    for (const key of ["ArrowDown", "ArrowUp", "Enter", "Tab", "Home", "End", "a"])
      expect(stepKey({ key }, 3, STEP_COUNT)).toBeNull();
  });
});

describe("stepPassed", () => {
  it("gives the last step when the page is opened below the story, with every marker above the middle", () => {
    const tops = Array.from({ length: STEP_COUNT }, (_, n) => -20000 + n * 900);
    expect(stepPassed(tops, 450)).toBe(STEP_COUNT - 1);
  });
  it("gives the last marker that starts above the middle line, and none at the top of the page", () => {
    expect(stepPassed([-900, 0, 900, 1800], 450)).toBe(1);
    expect(stepPassed([600, 1500, 2400], 450)).toBeNull();
    expect(stepPassed([], 450)).toBeNull();
  });
});

describe("stepShown", () => {
  const never = () => {
    throw new Error("the markers were measured without need");
  };
  it("gives the marker that came onto the middle line, without measuring", () => {
    expect(stepShown([10], never, 450)).toBe(10);
    expect(stepShown([10, 11], never, 450)).toBe(11);
  });
  it("gives the last step when a jump to the foot of the page leaves a middle step's marker behind", () => {
    const tops = Array.from({ length: STEP_COUNT }, (_, n) => -20000 + n * 900);
    expect(stepShown([], () => tops, 450)).toBe(STEP_COUNT - 1);
  });
  it("gives the marker the line lies in when none was reported, and leaves the step alone above the story", () => {
    expect(stepShown([], () => [-900, 0, 900, 1800], 450)).toBe(1);
    expect(stepShown([], () => [600, 1500, 2400], 450)).toBeNull();
  });
});

describe("tileFrame", () => {
  it("draws the whole board once, at the foot of its frame, when every part is lit or none is named", () => {
    expect(tileFrame(PARTS, 2, true)).toEqual({ zoom: 1, left: 0, top: -25 });
    expect(tileFrame([], 2)).toEqual({ zoom: 1, left: 0, top: -25 });
  });
  it("draws a small part large, centred, and never past an edge of the board", () => {
    for (const part of PARTS) {
      const { zoom, left, top } = tileFrame([part], 2);
      expect(zoom).toBeGreaterThan(1);
      expect(zoom).toBeLessThanOrEqual(2.4);
      expect(left).toBeLessThanOrEqual(0);
      expect(left).toBeGreaterThanOrEqual(100 - zoom * 100 - 1e-9);
      expect(top).toBeLessThanOrEqual(0);
      expect(top).toBeGreaterThanOrEqual(100 - zoom * 125 - 1e-9);
    }
  });
  it("draws parts that lie far apart smaller, so both are in the frame", () => {
    expect(tileFrame(["power", "processor"], 2).zoom).toBeLessThan(tileFrame(["processor"], 2).zoom);
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
