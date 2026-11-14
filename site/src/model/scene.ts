// The first scene as data: three steps, each declaring the complete state of the picture and naming the
// screen whose words it shows. Because a step is a whole state and not a change, scrolling fast, backwards
// or jumping lands on the right picture.
import { OPENING, headline, stop } from "../content/load";
import { PARTS, type Part, type Screen, type Stop } from "../content/types";

export type StepKind = "opening" | "inside" | "stop";

export interface SceneStep {
  id: string;
  kind: StepKind;
  /** The screen of the content whose words this step shows. */
  screen: Screen;
  /** The stop the step belongs to, or null before the first stop. */
  stop: Stop | null;
  /** Which plate is in view. */
  plate: "laptop" | "board";
  /** The parts of the board that glow, and the ones that light at this step, in the order they light. */
  lit: readonly Part[];
  newlyLit: readonly Part[];
}

const first = stop(1);
const firstScreen = headline(first);

export const STEPS: readonly SceneStep[] = [
  // The dark laptop, the title, the invitation to scroll.
  {
    id: "opening",
    kind: "opening",
    screen: OPENING,
    stop: null,
    plate: OPENING.picture.plate,
    lit: OPENING.picture.lit,
    newlyLit: OPENING.picture.newly_lit,
  },
  // The camera goes inside: the board, as dark as the laptop was. Still the opening's words.
  { id: "inside", kind: "inside", screen: OPENING, stop: null, plate: "board", lit: OPENING.picture.lit, newlyLit: [] },
  // Stop 1, lit as its screen says.
  {
    id: firstScreen.id,
    kind: "stop",
    screen: firstScreen,
    stop: first,
    plate: firstScreen.picture.plate,
    lit: firstScreen.picture.lit,
    newlyLit: firstScreen.picture.newly_lit,
  },
];

export const STEP_COUNT = STEPS.length;

export interface PartLayer {
  /** Whether the awake plate shows through this part's mask. */
  on: boolean;
  /** Its place among the parts that light at this step, from 0: light spreads in this order. */
  order: number;
}

export interface Layers {
  laptop: boolean;
  board: boolean;
  parts: Record<Part, PartLayer>;
}

/** Which layers of the picture a step shows. Every layer is always in the page; a step only sets what is seen. */
export function layersAt(step: SceneStep): Layers {
  const parts = {} as Record<Part, PartLayer>;
  for (const part of PARTS) {
    const on = step.plate === "board" && step.lit.includes(part);
    parts[part] = { on, order: on ? Math.max(0, step.newlyLit.indexOf(part)) : 0 };
  }
  return { laptop: step.plate === "laptop", board: step.plate === "board", parts };
}

/** A statement cut at its emphasis: the words before, the emphasised phrase, the words after. */
export function splitEmphasis(text: string, emphasis: string | null): [string, string, string] {
  const at = emphasis ? text.indexOf(emphasis) : -1;
  if (!emphasis || at < 0) return [text, "", ""];
  return [text.slice(0, at), emphasis, text.slice(at + emphasis.length)];
}
