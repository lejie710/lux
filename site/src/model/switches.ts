// The two switches a page address can carry. index.html reads them before first paint and sets a class on
// the page; the app reads them again here to choose what to render.

export interface Switches {
  /** `?static`: every step as a still section, one under the other, nothing pinned. */
  still: boolean;
  /** `?step=N`: the scene frozen at step N, with nothing to scroll. Null when absent or not a step. */
  step: number | null;
  /** `?evidence`, with `?step=N`: the frozen step's evidence panel is open from the start. */
  evidence: boolean;
}

export function readSwitches(search: string, stepCount: number): Switches {
  const params = new URLSearchParams(search);
  const raw = params.get("step");
  const n = raw !== null && /^\d+$/.test(raw) ? Number(raw) : NaN;
  const step = n < stepCount ? n : null;
  return { still: params.has("static"), step, evidence: step !== null && params.has("evidence") };
}

/** How the scene is drawn: pinned and scrolled, as still sections, or frozen at one step. */
export type Mode = { kind: "scroll" } | { kind: "still" } | { kind: "frozen"; step: number; evidence: boolean };

/** A frozen step wins over the still page; reduced motion makes the page still, as `?static` does. */
export function modeFor(switches: Switches, reducedMotion: boolean): Mode {
  if (switches.step !== null) return { kind: "frozen", step: switches.step, evidence: switches.evidence };
  return switches.still || reducedMotion ? { kind: "still" } : { kind: "scroll" };
}
