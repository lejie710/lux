// The story as data: the opening, the way inside, and one step per screen of the seven stops. Each step
// declares the complete state of the picture and names the screen whose words it shows. Because a step is a
// whole state and not a change, scrolling fast, backwards or jumping lands on the right picture.
import boxes from "../assets/parts.json";
import { OPENING, STOPS } from "../content/load";
import { PARTS, type Part, type Screen, type Stop } from "../content/types";

export type StepKind = "opening" | "inside" | "stop" | "pilot" | "closing";

/** What is in view: the laptop before power, the board, the laptop with its inside awake, or with its screen lit. */
export type View = "laptop-dark" | "board" | "laptop-inside" | "laptop-awake";

export interface SceneStep {
  id: string;
  kind: StepKind;
  /** The screen of the content whose words this step shows. */
  screen: Screen;
  /** The stop the step belongs to, or null before the first stop. */
  stop: Stop | null;
  /** The step's place among the screens of its stop, from 1, and how many screens the stop has. */
  screenAt: number;
  screenCount: number;
  view: View;
  /** The parts of the board that glow, and the ones that light at this step, in the order they light. */
  lit: readonly Part[];
  newlyLit: readonly Part[];
  /** The lit parts this step is about: they are given a slightly stronger light. */
  attention: readonly Part[];
}

/** The view a screen's picture asks for. A laptop with nothing lit is the machine before power. */
function viewOf(screen: Screen): View {
  const { plate, lit, screen: display } = screen.picture;
  if (plate === "board") return "board";
  if (display === "dawn") return "laptop-awake";
  return lit.length === 0 ? "laptop-dark" : "laptop-inside";
}

function stepOf(screen: Screen, stop: Stop | null, screenAt: number, screenCount: number): SceneStep {
  const kind: StepKind =
    screen.kind === "opening" || screen.kind === "pilot" || screen.kind === "closing" ? screen.kind : "stop";
  const { lit, newly_lit: newlyLit, attention } = screen.picture;
  return {
    id: screen.id,
    kind,
    screen,
    stop,
    screenAt,
    screenCount,
    view: viewOf(screen),
    lit,
    newlyLit,
    attention: attention ?? newlyLit,
  };
}

export const STEPS: readonly SceneStep[] = [
  // The dark laptop, the title, the invitation to scroll.
  stepOf(OPENING, null, 1, 1),
  // The camera goes inside: the board, as dark as the laptop was. Still the opening's words.
  { ...stepOf(OPENING, null, 1, 1), id: "inside", kind: "inside", view: "board", newlyLit: [], attention: [] },
  // Every screen of every stop, in reading order, pictured as its screen says.
  ...STOPS.flatMap((stop) => stop.screens.map((screen, n) => stepOf(screen, stop, n + 1, stop.screens.length))),
];

export const STEP_COUNT = STEPS.length;

/** The first step of a stop: where a mark of the rail leads. */
export function firstStepOf(stopNumber: number): number {
  return STEPS.findIndex((step) => step.stop?.number === stopNumber);
}

export interface PartLayer {
  /** Whether the awake picture shows through this part's mask. */
  on: boolean;
  /** Its place among the parts that light at this step, from 0: light spreads in this order. */
  order: number;
  /** Whether this step is about the part: it is lit a little more strongly. */
  strong: boolean;
}

export interface Layers {
  /** The laptop before power, as the opening shows it. */
  laptop: boolean;
  board: boolean;
  /** The pulled-back laptop of the ending, its inside awake; and whether its screen is lit. */
  ending: boolean;
  screenLit: boolean;
  /** The ground between the parts: lit once every part is. */
  whole: PartLayer;
  parts: Record<Part, PartLayer>;
}

/**
 * Which layers of the picture a step shows. Every layer is always in the page; a step only sets what is seen.
 * The parts stay lit behind the pulled-back laptop, so the board is as it was when the camera returns to it.
 */
export function layersAt(step: SceneStep): Layers {
  const parts = {} as Record<Part, PartLayer>;
  for (const part of PARTS) {
    const on = step.lit.includes(part);
    parts[part] = {
      on,
      order: on ? Math.max(0, step.newlyLit.indexOf(part)) : 0,
      strong: on && step.view === "board" && step.attention.includes(part),
    };
  }
  const all = PARTS.every((part) => parts[part].on);
  return {
    laptop: step.view === "laptop-dark",
    board: step.view === "board",
    ending: step.view === "laptop-inside" || step.view === "laptop-awake",
    screenLit: step.view === "laptop-awake",
    whole: { on: all, order: all ? step.newlyLit.length : 0, strong: false },
    parts,
  };
}

/** Where each part lies on the board picture, as fractions of its width and height. Written by tools/make_assets.py. */
export const PART_BOXES: Record<Part, { left: number; right: number; top: number; bottom: number }> = boxes;

/** The parts of the board a step looks at: the ones it is about, or all its lit ones. None off the board. */
function lookedAt(step: SceneStep): readonly Part[] {
  if (step.view !== "board") return [];
  return step.attention.length > 0 ? step.attention : step.lit;
}

/**
 * The point of the board a step looks at, as a fraction of the picture's width: the middle of the parts the
 * step is about. A step with nothing to look at (a dark board, or the laptop) looks where the next step
 * will, or failing that where the last one did, so the picture does not slide as the light arrives. A narrow
 * window frames the board around this point.
 */
export function focusAt(index: number): number {
  const after = STEPS.slice(index).find((step) => lookedAt(step).length > 0);
  const before = STEPS.slice(0, index)
    .reverse()
    .find((step) => lookedAt(step).length > 0);
  const step = after ?? before;
  if (!step) return 0.5;
  const parts = lookedAt(step);
  const left = Math.min(...parts.map((part) => PART_BOXES[part].left));
  const right = Math.max(...parts.map((part) => PART_BOXES[part].right));
  return (left + right) / 2;
}

/** The picture of a step in words, for a reader who cannot see it: what is in view, and which parts are lit. */
export function pictureLabel(step: SceneStep): string {
  if (step.view === "laptop-dark") return "Illustration: a laptop, closed down and dark.";
  if (step.view === "laptop-inside") return "Illustration: a laptop, its inside awake, its screen dark.";
  if (step.view === "laptop-awake") return "Illustration: a laptop, its screen lit with a dawn sky.";
  if (step.lit.length === 0) return "Illustration: a circuit board, dark.";
  if (PARTS.every((part) => step.lit.includes(part))) return "Illustration: a circuit board, every part lit.";
  return `Illustration: a circuit board. Lit: ${step.lit.join(", ")}.`;
}

/** A statement cut at its emphasis: the words before, the emphasised phrase, the words after. */
export function splitEmphasis(text: string, emphasis: string | null): [string, string, string] {
  const at = emphasis ? text.indexOf(emphasis) : -1;
  if (!emphasis || at < 0) return [text, "", ""];
  return [text.slice(0, at), emphasis, text.slice(at + emphasis.length)];
}
