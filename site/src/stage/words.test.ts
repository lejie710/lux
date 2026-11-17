// Which steps' words are in the scrolled story's stage: the step in view, and for a moment the steps just left.
import { describe, expect, it } from "vitest";
import css from "../styles/lux.css?raw";
import { WORDS_LINGER, wordsAt, wordsKept, wordsMoved, wordsPruned, wordsShown } from "./words";

describe("the words in the stage", () => {
  it("are those of the step in view alone while the story rests", () => {
    const state = wordsAt(7);
    expect(wordsKept(state)).toEqual([7]);
    expect(state.shown).toBe(true);
  });

  it("keep the step just left for the length of its fade, and put the new step in unseen first", () => {
    const moved = wordsMoved(wordsAt(7), 8, 1000);
    expect(wordsKept(moved)).toEqual([7, 8]);
    expect(moved.current).toBe(8);
    expect(moved.shown).toBe(false);
    const shown = wordsShown(moved);
    expect(shown.shown).toBe(true);
    expect(wordsKept(shown)).toEqual([7, 8]);
    expect(wordsPruned(shown, 1000 + WORDS_LINGER - 1)).toBe(shown);
    expect(wordsKept(wordsPruned(shown, 1000 + WORDS_LINGER))).toEqual([8]);
  });

  it("are in the story's order whichever way the reader scrolls", () => {
    expect(wordsKept(wordsMoved(wordsAt(8), 7, 0))).toEqual([7, 8]);
    expect(wordsKept(wordsMoved(wordsMoved(wordsAt(9), 8, 0), 7, 100))).toEqual([7, 8, 9]);
  });

  it("show a step again at once when the reader turns back to it before its words have gone", () => {
    const there = wordsShown(wordsMoved(wordsAt(7), 8, 1000));
    const back = wordsMoved(there, 7, 1200);
    expect(back.current).toBe(7);
    expect(back.shown).toBe(true);
    expect(wordsKept(back)).toEqual([7, 8]);
    // Each step is in the list once, however often the reader turns.
    const again = wordsMoved(back, 8, 1300);
    expect(wordsKept(again)).toEqual([7, 8]);
    expect(again.left).toHaveLength(1);
  });

  it("put a step in unseen again once its words have gone", () => {
    const there = wordsPruned(wordsShown(wordsMoved(wordsAt(7), 8, 1000)), 2000);
    expect(wordsMoved(there, 7, 2100).shown).toBe(false);
    // Also when the time is up but nothing has cleared the list yet.
    const late = wordsShown(wordsMoved(wordsAt(7), 8, 1000));
    expect(wordsMoved(late, 7, 1000 + WORDS_LINGER).shown).toBe(false);
  });

  it("hold no more than the steps of the last moment during a fast scroll, and one when it ends", () => {
    let state = wordsAt(0);
    let now = 0;
    for (let n = 1; n <= 21; n++) {
      state = wordsShown(wordsMoved(state, n, (now += 150)));
      // 150 ms a step: the steps left in the last 700 ms, and the one in view.
      expect(wordsKept(state).length).toBeLessThanOrEqual(Math.ceil(WORDS_LINGER / 150) + 1);
      expect(wordsKept(state)).toContain(n);
    }
    expect(wordsKept(wordsPruned(state, now + WORDS_LINGER))).toEqual([21]);
  });

  it("change nothing when the step does not change", () => {
    const state = wordsAt(3);
    expect(wordsMoved(state, 3, 50)).toBe(state);
    expect(wordsShown(state)).toBe(state);
    expect(wordsPruned(state, 99999)).toBe(state);
  });

  it("linger at least as long as the longest fade of words that are leaving", () => {
    const flat = css.replace(/\s+/g, " ");
    // Words that leave: the head fades at once; the evidence line and its control after a wait.
    const head =
      /\.words > \.head, \.words-opening > \* \{[^}]*transition: opacity ([\d.]+)s ease, transform ([\d.]+)s ease;/.exec(
        flat,
      )!;
    const foot =
      /\.foot > \.pill, \.foot > \.open-evidence \{ opacity: 0; transition: opacity ([\d.]+)s ease ([\d.]+)s;/.exec(
        flat,
      )!;
    const longest = Math.max(Number(head[1]), Number(head[2]), Number(foot[1]) + Number(foot[2])) * 1000;
    expect(longest).toBeCloseTo(600, 6);
    expect(WORDS_LINGER).toBeGreaterThanOrEqual(longest);
  });
});
