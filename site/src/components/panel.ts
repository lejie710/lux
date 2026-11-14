// The evidence panel's behaviour as plain functions: what is open, where focus goes when it closes, and what
// a key does inside it. The component only carries these out.

export interface PanelState {
  /** The screen whose evidence is shown, or null when the panel is closed. */
  screenId: string | null;
  /** The id of the control that opened it: focus returns there. */
  openerId: string | null;
  /** Whether the panel opens at its list of claims, as a citation marker asks, or at its top. */
  atClaims: boolean;
}

export const CLOSED: PanelState = { screenId: null, openerId: null, atClaims: false };

export function openPanel(screenId: string, openerId: string, atClaims = false): PanelState {
  return { screenId, openerId, atClaims };
}

/** Closing empties the panel and names the control that focus goes back to. */
export function closePanel(state: PanelState): { state: PanelState; focusId: string | null } {
  return { state: CLOSED, focusId: state.openerId };
}

export type PanelKeyAction = { action: "close" } | { action: "focus"; index: number } | null;

/**
 * What a key does while the panel is open. Escape closes it. Tab stays inside: from the last control it
 * goes to the first, and Shift and Tab from the first (or from the panel itself, at -1) goes to the last.
 * `at` is the focused control's place among the panel's `count` controls. Null leaves the key to the browser.
 * `after` is given when focus is inside the panel on something that is not a control, such as the heading a
 * citation marker lands on: it is the place of the first control that follows it, or `count` when none does.
 * Tab then goes to that control and Shift and Tab to the one before it, round the ends, so focus moves on
 * from where the reader is and never leaves the panel.
 */
export function panelKey(
  key: { key: string; shiftKey?: boolean },
  at: number,
  count: number,
  after: number | null = null,
): PanelKeyAction {
  if (key.key === "Escape") return { action: "close" };
  if (key.key !== "Tab" || count === 0) return null;
  if (at < 0 && after !== null) return { action: "focus", index: (key.shiftKey ? after - 1 + count : after) % count };
  if (key.shiftKey && at <= 0) return { action: "focus", index: count - 1 };
  if (!key.shiftKey && (at < 0 || at === count - 1)) return { action: "focus", index: 0 };
  return null;
}

/** The ids of the two controls that open a screen's evidence. */
export const openerId = (stepId: string) => `evidence-open-${stepId}`;
export const markerId = (stepId: string) => `evidence-marker-${stepId}`;
