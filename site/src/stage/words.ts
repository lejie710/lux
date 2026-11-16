// Which steps' words are in the stage of the scrolled story. Only the step in view, and for a moment the
// steps just left, so that their words can fade out: a step at rest has one block of words over the
// picture, as a still section has, however many steps the story holds.
import { useLayoutEffect, useEffect, useRef, useState, type RefObject } from "react";

/** A step that was left keeps its words this long: the longest of their fades, and a little more. Milliseconds. */
export const WORDS_LINGER = 700;

export interface WordsState {
  /** The step in view. */
  current: number;
  /** Whether its words are shown. Words new to the page are put in unseen first, so that they fade in. */
  shown: boolean;
  /** The steps just left, and the time until which each keeps its words. */
  left: readonly { step: number; until: number }[];
}

export function wordsAt(step: number): WordsState {
  return { current: step, shown: true, left: [] };
}

/** The step changes at `now`. Words still in the page from an earlier visit are shown at once. */
export function wordsMoved(state: WordsState, to: number, now: number): WordsState {
  if (to === state.current) return state;
  const kept = state.left.filter((entry) => entry.step !== to && entry.step !== state.current && entry.until > now);
  return {
    current: to,
    shown: state.left.some((entry) => entry.step === to && entry.until > now),
    left: [...kept, { step: state.current, until: now + WORDS_LINGER }],
  };
}

/** The words of the step in view have been put in the page: now they are shown. */
export function wordsShown(state: WordsState): WordsState {
  return state.shown ? state : { ...state, shown: true };
}

/** Steps whose time is up lose their words. */
export function wordsPruned(state: WordsState, now: number): WordsState {
  const left = state.left.filter((entry) => entry.until > now);
  return left.length === state.left.length ? state : { ...state, left };
}

/** The steps whose words are in the page, in the story's order. */
export function wordsKept(state: WordsState): number[] {
  return [...new Set([state.current, ...state.left.map((entry) => entry.step)])].sort((a, b) => a - b);
}

/**
 * The words of the scrolled story for a step: which steps' words to draw, and which of them is shown.
 * `stage` is the element they are drawn in.
 */
export function useWords(current: number, stage: RefObject<HTMLElement | null>): { kept: number[]; on: number | null } {
  const [state, setState] = useState(() => wordsAt(current));
  let now = state;
  if (state.current !== current) {
    now = wordsMoved(state, current, performance.now());
    setState(now);
  }

  // Words new to the page are laid out unseen once, then shown, so the stylesheet fades them in.
  useLayoutEffect(() => {
    if (now.shown) return;
    void stage.current?.offsetWidth;
    setState(wordsShown);
  }, [now.shown, now.current, stage]);

  // One timer for the step whose words go next.
  const timer = useRef(0);
  const next = now.left.length > 0 ? Math.min(...now.left.map((entry) => entry.until)) : null;
  useEffect(() => {
    if (next === null) return;
    timer.current = window.setTimeout(
      () => setState((s) => wordsPruned(s, performance.now())),
      Math.max(0, next - performance.now()) + 20,
    );
    return () => window.clearTimeout(timer.current);
  }, [next]);

  return { kept: wordsKept(now), on: now.shown ? now.current : null };
}
