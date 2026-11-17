// The board's light as numbers: the level of every part at a time after a step change, forward, backward
// and interrupted; what a frame draws; and the size of the canvas it is drawn on.
import { describe, expect, it } from "vitest";
import { PARTS, type Part } from "../content/types";
import { STEPS, layersAt, type PartLayer } from "../model/scene";
import {
  GLOW_STRONG,
  LIGHT_NAMES,
  LIT_FULL,
  LIT_REST,
  PLATE,
  STAGGER,
  allSettled,
  backingSize,
  drawList,
  ease,
  glowBlur,
  glowRule,
  levelsAt,
  lightKey,
  lightSummary,
  litRule,
  resting,
  retarget,
  retargetAll,
  sameLevels,
  settled,
  tracksAt,
  valueAt,
  type Levels,
  type Tracks,
} from "./light";

const at = (id: string) => STEPS.findIndex((step) => step.id === id);
const layer = (over: Partial<PartLayer>): PartLayer => ({ on: false, order: 0, strong: false, rest: false, ...over });
/** Long enough for any change to have ended: the longest wait is two turns, the longest fade 1.9 s. */
const LONG = 500 + 9 * STAGGER + 1900 + 1;

/** The story walked from one step to another with a rest after each step, as a slow reader scrolls it. */
function walk(from: number, to: number, start = tracksAt(layersAt(STEPS[from]))): { tracks: Tracks; now: number } {
  let tracks = start;
  let now = 0;
  const way = to >= from ? 1 : -1;
  for (let n = from + way; n !== to + way; n += way) {
    tracks = retargetAll(tracks, layersAt(STEPS[n]), now);
    now += LONG;
  }
  return { tracks, now };
}

describe("the rules of one light", () => {
  it("lights a part in its turn, settles a resting part to half, and puts a part out quickly", () => {
    expect(litRule(layer({}))).toEqual({ to: 0, delay: 0, duration: 500 });
    expect(litRule(layer({ on: true }))).toEqual({ to: LIT_FULL, delay: 500, duration: 1900 });
    expect(litRule(layer({ on: true, order: 2 }))).toEqual({ to: LIT_FULL, delay: 500 + 2 * STAGGER, duration: 1900 });
    expect(litRule(layer({ on: true, rest: true, order: 2 }))).toEqual({ to: LIT_REST, delay: 0, duration: 1200 });
  });

  it("adds the stronger light a little after the part's own, and takes it away quickly", () => {
    expect(glowRule(layer({ on: true }))).toEqual({ to: 0, delay: 0, duration: 600 });
    expect(glowRule(layer({ on: true, strong: true }))).toEqual({ to: GLOW_STRONG, delay: 700, duration: 1400 });
    expect(glowRule(layer({ on: true, strong: true, order: 1 })).delay).toBe(700 + STAGGER);
  });

  it("holds the levels the picture was approved with", () => {
    expect([LIT_FULL, LIT_REST, GLOW_STRONG, STAGGER]).toEqual([1, 0.5, 0.75, 900]);
  });
});

describe("the curve of a fade", () => {
  it("is the stylesheet's ease: it starts and ends flat, and is past the middle at half time", () => {
    expect(ease(0)).toBe(0);
    expect(ease(1)).toBe(1);
    expect(ease(-1)).toBe(0);
    expect(ease(2)).toBe(1);
    // Values of cubic-bezier(0.25, 0.1, 0.25, 1), worked out apart from this code.
    expect(ease(0.25)).toBeCloseTo(0.4085, 3);
    expect(ease(0.5)).toBeCloseTo(0.8024, 3);
    expect(ease(0.75)).toBeCloseTo(0.9604, 3);
  });

  it("never goes back", () => {
    let last = 0;
    for (let x = 0; x <= 1.0001; x += 0.01) {
      expect(ease(x)).toBeGreaterThanOrEqual(last);
      last = ease(x);
    }
  });
});

describe("one level on its way", () => {
  const rule = { to: 1, delay: 500, duration: 1900 };
  const track = retarget(resting(0), rule, 1000);

  it("waits out its delay, then moves, then stays", () => {
    expect(valueAt(track, 1000)).toBe(0);
    expect(valueAt(track, 1499)).toBe(0);
    expect(valueAt(track, 1500)).toBe(0);
    expect(valueAt(track, 1500 + 950)).toBeCloseTo(ease(0.5), 10);
    expect(valueAt(track, 3399)).toBeLessThan(1);
    expect(valueAt(track, 3400)).toBe(1);
    expect(valueAt(track, 99999)).toBe(1);
    expect(settled(track, 3399)).toBe(false);
    expect(settled(track, 3400)).toBe(true);
  });

  it("only rises on the way up", () => {
    let last = 0;
    for (let t = 1000; t <= 3500; t += 25) {
      expect(valueAt(track, t)).toBeGreaterThanOrEqual(last);
      last = valueAt(track, t);
    }
  });

  it("is left alone by a rule with the same end: a change of turn alone starts nothing", () => {
    expect(retarget(track, { to: 1, delay: 2300, duration: 1900 }, 1200)).toBe(track);
    expect(retarget(resting(0.5), { to: 0.5, delay: 0, duration: 1200 }, 5)).toEqual(resting(0.5));
  });

  it("starts a new change from the level it has reached, so an interrupted fade never jumps", () => {
    const now = 1500 + 700;
    const reached = valueAt(track, now);
    expect(reached).toBeGreaterThan(0);
    expect(reached).toBeLessThan(1);
    const next = retarget(track, { to: 0.5, delay: 0, duration: 1200 }, now);
    expect(valueAt(next, now)).toBe(reached);
    expect(valueAt(next, now + 1200)).toBe(0.5);
    // A level that is neither end of the first change: the new change takes its rule's whole time.
    expect(next.duration).toBe(1200);
  });

  it("turned round before it has ended, takes only as long as the way it has gone", () => {
    const now = 1500 + 400;
    const reached = valueAt(track, now);
    const back = retarget(track, { to: 0, delay: 0, duration: 500 }, now);
    expect(valueAt(back, now)).toBe(reached);
    expect(back.duration).toBeCloseTo(500 * reached, 10);
    expect(valueAt(back, now + back.duration)).toBe(0);
    // Turned round once more: the second turn is again shortened by what is left of the first.
    const half = now + back.duration / 2;
    const again = retarget(back, rule, half);
    expect(valueAt(again, half)).toBeCloseTo(valueAt(back, half), 12);
    expect(again.duration).toBeLessThan(1900);
    expect(again.delay).toBe(500);
    expect(valueAt(again, half + again.delay + again.duration)).toBe(1);
  });

  it("turned round while it still waits, is simply back where it was", () => {
    const back = retarget(track, { to: 0, delay: 0, duration: 500 }, 1300);
    expect(back).toEqual(resting(0));
    expect(settled(back, 1300)).toBe(true);
  });

  it("at rest is at its end at every time", () => {
    expect(valueAt(resting(0.75), 0)).toBe(0.75);
    expect(valueAt(resting(0.75), -5)).toBe(0.75);
    expect(settled(resting(0.75), 0)).toBe(true);
  });
});

describe("the board's light along the story", () => {
  it("shows a step as a still with every level at its end: lit, half at rest, and the added light", () => {
    STEPS.forEach((step) => {
      const layers = layersAt(step);
      const tracks = tracksAt(layers);
      expect(allSettled(tracks, 0)).toBe(true);
      const levels = levelsAt(tracks, 0);
      for (const part of PARTS) {
        const { on, rest, strong } = layers.parts[part];
        expect(levels[part].lit, `${step.id} ${part}`).toBe(on ? (rest ? LIT_REST : LIT_FULL) : 0);
        expect(levels[part].glow, `${step.id} ${part}`).toBe(strong ? GLOW_STRONG : 0);
      }
      expect(levels.whole).toEqual({ lit: layers.whole.on ? LIT_FULL : 0, glow: 0 });
    });
  });

  it("spreads light part by part: at stop 1 the processor is still dark when power has begun to rise", () => {
    const stop1 = at("s1-power-reset");
    const tracks = retargetAll(tracksAt(layersAt(STEPS[stop1 - 1])), layersAt(STEPS[stop1]), 0);
    const early = levelsAt(tracks, 500 + 600);
    expect(early.power.lit).toBeGreaterThan(0.3);
    expect(early.processor.lit).toBe(0);
    expect(early.power.glow).toBeGreaterThan(0);
    expect(early.processor.glow).toBe(0);
    const later = levelsAt(tracks, 500 + STAGGER + 600);
    expect(later.processor.lit).toBeGreaterThan(0.3);
    expect(later.power.lit).toBeGreaterThan(later.processor.lit);
    // The whole change: the second part's wait, then its fade.
    expect(allSettled(tracks, 500 + STAGGER + 1900 - 1)).toBe(false);
    expect(allSettled(tracks, 500 + STAGGER + 1900)).toBe(true);
    expect(levelsAt(tracks, 500 + STAGGER + 1900)).toEqual(levelsAt(tracksAt(layersAt(STEPS[stop1])), 0));
  });

  it("lights the ground between the parts last, after the last part of its step", () => {
    const exit = at("s7-exit-call");
    const tracks = retargetAll(tracksAt(layersAt(STEPS[exit - 1])), layersAt(STEPS[exit]), 0);
    const newly = STEPS[exit].newlyLit.length;
    expect(tracks.whole.lit.delay).toBe(500 + newly * STAGGER);
    expect(levelsAt(tracks, 500 + newly * STAGGER).whole.lit).toBe(0);
    expect(levelsAt(tracks, 500 + newly * STAGGER + 1900).whole.lit).toBe(1);
  });

  it("ends every step change, forward or backward, on the step's still picture", () => {
    for (let n = 1; n < STEPS.length; n++) {
      const still = levelsAt(tracksAt(layersAt(STEPS[n])), 0);
      const forward = retargetAll(tracksAt(layersAt(STEPS[n - 1])), layersAt(STEPS[n]), 0);
      expect(levelsAt(forward, LONG), `to ${STEPS[n].id}`).toEqual(still);
      const before = levelsAt(tracksAt(layersAt(STEPS[n - 1])), 0);
      const backward = retargetAll(tracksAt(layersAt(STEPS[n])), layersAt(STEPS[n - 1]), 0);
      expect(levelsAt(backward, LONG), `back from ${STEPS[n].id}`).toEqual(before);
    }
  });

  it("lands on the right picture after a jump from any step to any other", () => {
    for (const from of [0, 2, 9, 15, 19, 21])
      for (let to = 0; to < STEPS.length; to++) {
        const tracks = retargetAll(tracksAt(layersAt(STEPS[from])), layersAt(STEPS[to]), 0);
        expect(levelsAt(tracks, LONG), `${from} to ${to}`).toEqual(levelsAt(tracksAt(layersAt(STEPS[to])), 0));
      }
  });

  it("lands on the right picture after a fast scroll through every step, there and back", () => {
    let tracks = tracksAt(layersAt(STEPS[0]));
    let now = 0;
    // A step every 120 ms: no fade has time to end before the next begins.
    for (let n = 1; n < STEPS.length; n++) tracks = retargetAll(tracks, layersAt(STEPS[n]), (now += 120));
    expect(allSettled(tracks, now)).toBe(false);
    expect(levelsAt(tracks, now + LONG)).toEqual(levelsAt(tracksAt(layersAt(STEPS.at(-1)!)), 0));
    for (let n = STEPS.length - 2; n >= 0; n--) tracks = retargetAll(tracks, layersAt(STEPS[n]), (now += 120));
    expect(levelsAt(tracks, now + LONG)).toEqual(levelsAt(tracksAt(layersAt(STEPS[0])), 0));
  });

  it("never jumps when a step change interrupts another: each level goes on from where it was", () => {
    let tracks = tracksAt(layersAt(STEPS[0]));
    let now = 0;
    for (const n of [2, 4, 3, 18, 5, 19, 1, 12]) {
      now += 730;
      const before = levelsAt(tracks, now);
      tracks = retargetAll(tracks, layersAt(STEPS[n]), now);
      const after = levelsAt(tracks, now);
      for (const name of LIGHT_NAMES) {
        expect(after[name].lit).toBeCloseTo(before[name].lit, 12);
        expect(after[name].glow).toBeCloseTo(before[name].glow, 12);
      }
    }
  });

  it("keeps every level between dark and its brightest at every moment of a slow walk and a fast one", () => {
    for (const gap of [LONG, 300]) {
      let tracks = tracksAt(layersAt(STEPS[0]));
      let now = 0;
      for (let n = 1; n < STEPS.length; n++) {
        tracks = retargetAll(tracks, layersAt(STEPS[n]), now);
        for (let t = now; t < now + gap; t += gap / 7) {
          const levels = levelsAt(tracks, t);
          for (const name of LIGHT_NAMES) {
            expect(levels[name].lit).toBeGreaterThanOrEqual(0);
            expect(levels[name].lit).toBeLessThanOrEqual(LIT_FULL);
            expect(levels[name].glow).toBeGreaterThanOrEqual(0);
            expect(levels[name].glow).toBeLessThanOrEqual(GLOW_STRONG);
          }
        }
        now += gap;
      }
    }
  });

  it("never lets a lit part fall below half its light along the story, at rest or on the way", () => {
    let tracks = tracksAt(layersAt(STEPS[0]));
    let now = 0;
    const litBefore = new Set<Part>();
    for (let n = 1; n < STEPS.length; n++) {
      tracks = retargetAll(tracks, layersAt(STEPS[n]), now);
      for (let t = now; t <= now + LONG; t += LONG / 40)
        for (const part of litBefore)
          expect(levelsAt(tracks, t)[part].lit, `${STEPS[n].id} ${part}`).toBeGreaterThanOrEqual(LIT_REST);
      now += LONG;
      for (const part of STEPS[n].lit) litBefore.add(part);
    }
  });

  it("is the same picture however the story was reached: walked forward, walked back, or opened there", () => {
    const there = walk(0, 12);
    expect(levelsAt(there.tracks, there.now)).toEqual(levelsAt(tracksAt(layersAt(STEPS[12])), 0));
    const back = walk(21, 12);
    expect(levelsAt(back.tracks, back.now)).toEqual(levelsAt(tracksAt(layersAt(STEPS[12])), 0));
  });

  it("tells two sets of levels apart, and two steps' lights apart", () => {
    const a = levelsAt(tracksAt(layersAt(STEPS[12])), 0);
    expect(sameLevels(a, levelsAt(tracksAt(layersAt(STEPS[13])), 0))).toBe(true);
    expect(sameLevels(a, levelsAt(tracksAt(layersAt(STEPS[11])), 0))).toBe(false);
    expect(lightKey(layersAt(STEPS[12]))).toBe(lightKey(layersAt(STEPS[13])));
    expect(lightKey(layersAt(STEPS[12]))).not.toBe(lightKey(layersAt(STEPS[11])));
    // The laptop in front of the board changes the lights behind it: nothing rests there.
    expect(lightKey(layersAt(STEPS[14]))).not.toBe(lightKey(layersAt(STEPS[15])));
  });

  it("says in words what a step lights", () => {
    expect(lightSummary(layersAt(STEPS[at("s1-power-reset")]))).toEqual({
      lit: "power processor",
      rest: "",
      strong: "power processor",
      whole: false,
    });
    const verify = lightSummary(layersAt(STEPS[at("s6-verify")]));
    expect(verify.strong).toBe("security");
    expect(verify.rest.split(" ")).not.toContain("security");
    expect(lightSummary(layersAt(STEPS[at("s7-exit-events")])).whole).toBe(true);
    expect(lightSummary(layersAt(STEPS[0]))).toEqual({ lit: "", rest: "", strong: "", whole: false });
  });
});

describe("what one frame draws", () => {
  const frame = (id: string) => drawList(levelsAt(tracksAt(layersAt(STEPS[at(id)])), 0));

  it("draws the dark board first and whole, whatever is lit", () => {
    for (const step of STEPS)
      expect(drawList(levelsAt(tracksAt(layersAt(step)), 0))[0]).toEqual({
        image: "dark",
        alpha: 1,
        blend: "source-over",
      });
    expect(frame("inside")).toHaveLength(1);
  });

  it("draws each part's cut-out and its added light over it, in the board's own order", () => {
    expect(frame("s1-power-reset")).toEqual([
      { image: "dark", alpha: 1, blend: "source-over" },
      { image: "lit:power", alpha: 1, blend: "source-over" },
      { image: "glow:power", alpha: 0.75, blend: "screen" },
      { image: "lit:processor", alpha: 1, blend: "source-over" },
      { image: "glow:processor", alpha: 0.75, blend: "screen" },
    ]);
  });

  it("draws resting parts at half, and adds light to the one part the step is about", () => {
    const list = frame("s5-attempt");
    const lit = STEPS[at("s5-attempt")].lit;
    expect(list.filter((d) => d.blend === "screen")).toEqual([
      { image: "glow:security", alpha: 0.75, blend: "screen" },
    ]);
    expect(list.filter((d) => d.image.startsWith("lit:")).map((d) => d.image)).toEqual(
      PARTS.filter((part) => lit.includes(part)).map((part) => `lit:${part}`),
    );
    for (const d of list.filter((d) => d.image.startsWith("lit:")))
      expect(d.alpha).toBe(d.image === "lit:security" ? 1 : 0.5);
    // The added light comes straight after its own part's cut-out.
    expect(list[list.findIndex((d) => d.image === "glow:security") - 1].image).toBe("lit:security");
  });

  it("draws the ground between the parts last, once every part is lit, and rests nothing then", () => {
    const list = frame("s7-exit-call");
    expect(list.at(-1)).toEqual({ image: "lit:whole", alpha: 1, blend: "source-over" });
    expect(list.filter((d) => d.image.startsWith("lit:")).every((d) => d.alpha === 1)).toBe(true);
    expect(list).toHaveLength(1 + PARTS.length + 1 + 1);
  });

  it("leaves out what is too faint to see", () => {
    const levels = levelsAt(tracksAt(layersAt(STEPS[1])), 0) as Levels;
    levels.power = { lit: 0.001, glow: 0.0015 };
    levels.storage = { lit: 0.01, glow: 0 };
    expect(drawList(levels).map((d) => d.image)).toEqual(["dark", "lit:storage"]);
  });
});

describe("the canvas the board is drawn on", () => {
  it("has one pixel per screen pixel while the picture has that many", () => {
    expect(backingSize(1425, 1)).toEqual({ width: 1425, height: 891 });
    expect(backingSize(1024, 1)).toEqual({ width: 1024, height: 640 });
    expect(backingSize(624, 3)).toEqual({ width: 1872, height: 1170 });
  });

  it("is never larger than the picture, on any screen and for any board", () => {
    // The phone of the report: a board 975 px wide on a screen of three pixels to one.
    expect(backingSize(975, 3)).toEqual({ width: PLATE.width, height: PLATE.height });
    expect(backingSize(1075, 3)).toEqual({ width: 1920, height: 1200 });
    expect(backingSize(975, 2)).toEqual({ width: 1920, height: 1200 });
    expect(backingSize(2560, 2)).toEqual({ width: 1920, height: 1200 });
    for (const width of [1, 320, 975, 1440, 2050, 5000])
      for (const ratio of [0.5, 1, 1.5, 2, 3, 4, 8]) {
        const size = backingSize(width, ratio, width % 2 === 1);
        expect(size.width * size.height).toBeLessThanOrEqual(1920 * 1200);
        expect(size.width).toBeGreaterThanOrEqual(1);
        expect(size.height).toBeGreaterThanOrEqual(1);
      }
  });

  it("costs the same on a screen of three pixels to one as on one of two", () => {
    expect(backingSize(975, 3, true)).toEqual(backingSize(975, 2, true));
    expect(backingSize(975, 4, true)).toEqual(backingSize(975, 2, true));
  });

  it("gives a board that is slid sideways two pixels per screen pixel on a screen of low density", () => {
    expect(backingSize(700, 1, true)).toEqual({ width: 1400, height: 875 });
    expect(backingSize(975, 1, true)).toEqual({ width: 1920, height: 1200 });
    expect(backingSize(700, 3, true)).toEqual(backingSize(700, 3));
  });

  it("has the picture's shape, and a size even where the screen's density is not known", () => {
    expect(backingSize(1600, 1)).toEqual({ width: 1600, height: 1000 });
    expect(backingSize(800, 0)).toEqual({ width: 800, height: 500 });
    expect(backingSize(0, 2)).toEqual({ width: 1, height: 1 });
  });

  it("blurs the added light by a share of the stage's width, in the canvas's own pixels", () => {
    // A phone: the stage 390 wide, the board 975, the canvas 1920.
    expect(glowBlur(390, 975, 1920)).toBeCloseTo(0.702 * (1920 / 975), 10);
    // A wide window: the board as wide as the stage, the canvas one to one.
    expect(glowBlur(1425, 1425, 1425)).toBeCloseTo(2.565, 10);
    expect(glowBlur(390, 0, 1920)).toBe(0);
  });
});
