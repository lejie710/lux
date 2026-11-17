// The light of the board as numbers: how lit each part is at a moment after a step change, and what one
// frame of the picture draws. Plain functions over plain data, so the timeline is tested without a browser.
// The picture is drawn on one canvas whose size is capped by the picture itself, never by the screen's
// density, so its memory is the same on every screen.
import { PARTS, type Part } from "../content/types";
import type { Layers, PartLayer } from "../model/scene";

/** The light a lit part has at rest, the light of a lit part the step is not about, and the added light. */
export const LIT_FULL = 1;
export const LIT_REST = 0.5;
export const GLOW_STRONG = 0.75;

/** The added light is brighter than the picture and a little soft: its blur is this share of the stage's width. */
export const GLOW_BRIGHTNESS = 1.35;
export const GLOW_BLUR_OF_STAGE = 0.0018;

/** Light spreads: each part that lights at a step waits this long after the one before it. Milliseconds. */
export const STAGGER = 900;

/** Where a level is going, and how: after `delay`, over `duration`. Milliseconds. */
export interface Rule {
  to: number;
  delay: number;
  duration: number;
}

/** The light of a part's cut-out. It comes on slowly and in turn, settles to half quickly, goes out quickly. */
export function litRule(layer: PartLayer): Rule {
  if (!layer.on) return { to: 0, delay: 0, duration: 500 };
  if (layer.rest) return { to: LIT_REST, delay: 0, duration: 1200 };
  return { to: LIT_FULL, delay: 500 + layer.order * STAGGER, duration: 1900 };
}

/** The added light of the part a step is about. It follows the part's own light, and goes out quickly. */
export function glowRule(layer: PartLayer): Rule {
  if (!layer.strong) return { to: 0, delay: 0, duration: 600 };
  return { to: GLOW_STRONG, delay: 700 + layer.order * STAGGER, duration: 1400 };
}

/** The curve named `ease` in a stylesheet: a cubic Bezier through (0.25, 0.1) and (0.25, 1). */
export function ease(x: number): number {
  if (x <= 0) return 0;
  if (x >= 1) return 1;
  const bezier = (t: number, a: number, b: number) =>
    3 * (1 - t) * (1 - t) * t * a + 3 * (1 - t) * t * t * b + t * t * t;
  // The curve's x grows with its parameter, so the parameter for an x is found by halving.
  let low = 0;
  let high = 1;
  for (let n = 0; n < 40; n++) {
    const mid = (low + high) / 2;
    if (bezier(mid, 0.25, 0.25) < x) low = mid;
    else high = mid;
  }
  return bezier((low + high) / 2, 0.1, 1);
}

/**
 * One level on its way: from `from` to `to`, changed at `start`, moving after `delay` for `duration`.
 * `back` is the level it would return to if it were turned round, and `share` how much of a full change it
 * is: a change turned round before it has ended takes only as long as the way it has gone.
 */
export interface Track {
  from: number;
  to: number;
  start: number;
  delay: number;
  duration: number;
  back: number;
  share: number;
}

/** A level that is where its rule ends and is going nowhere: a frozen picture, and the first frame. */
export function resting(to: number): Track {
  return { from: to, to, start: 0, delay: 0, duration: 0, back: to, share: 1 };
}

/** How far along its curve a track is at a time, from 0 to 1. Nothing moves until the delay has passed. */
function progress(track: Track, now: number): number {
  const t = now - track.start - track.delay;
  if (t <= 0) return track.duration > 0 || t < 0 ? 0 : 1;
  if (t >= track.duration) return 1;
  return ease(t / track.duration);
}

export function valueAt(track: Track, now: number): number {
  if (track.from === track.to) return track.to;
  const p = progress(track, now);
  return p >= 1 ? track.to : track.from + (track.to - track.from) * p;
}

export function settled(track: Track, now: number): boolean {
  return track.from === track.to || now - track.start - track.delay >= track.duration;
}

/**
 * A track given a new rule, as a stylesheet's transition takes a new value. The same end leaves the track
 * as it is: a change of order alone starts nothing. A new end starts from the level reached, so a step
 * change in the middle of a fade never jumps. Turning back to the level the track came from takes only as
 * long as the way already gone; the wait before it is the new rule's own.
 */
export function retarget(track: Track, rule: Rule, now: number): Track {
  if (track.to === rule.to) return track;
  const at = valueAt(track, now);
  if (at === rule.to) return resting(rule.to);
  if (!settled(track, now) && track.back === rule.to) {
    const share = Math.min(1, Math.max(0, progress(track, now) * track.share + (1 - track.share)));
    return {
      from: at,
      to: rule.to,
      start: now,
      delay: rule.delay,
      duration: rule.duration * share,
      back: track.to,
      share,
    };
  }
  return { from: at, to: rule.to, start: now, delay: rule.delay, duration: rule.duration, back: at, share: 1 };
}

/** A name on the picture: one of the eight parts, or the ground between them. */
export type LightName = Part | "whole";
export const LIGHT_NAMES: readonly LightName[] = [...PARTS, "whole"];

export type Tracks = Record<LightName, { lit: Track; glow: Track }>;
export type Levels = Record<LightName, { lit: number; glow: number }>;

const layerOf = (layers: Layers, name: LightName): PartLayer => (name === "whole" ? layers.whole : layers.parts[name]);
const each = <T>(make: (name: LightName) => T) =>
  Object.fromEntries(LIGHT_NAMES.map((name) => [name, make(name)])) as Record<LightName, T>;

/** Every level at the end of its rule: the picture of a step as a still. */
export function tracksAt(layers: Layers): Tracks {
  return each((name) => ({
    lit: resting(litRule(layerOf(layers, name)).to),
    glow: resting(glowRule(layerOf(layers, name)).to),
  }));
}

/** The tracks after a step change at `now`: each level takes the rule of the new step. */
export function retargetAll(tracks: Tracks, layers: Layers, now: number): Tracks {
  return each((name) => ({
    lit: retarget(tracks[name].lit, litRule(layerOf(layers, name)), now),
    glow: retarget(tracks[name].glow, glowRule(layerOf(layers, name)), now),
  }));
}

export function levelsAt(tracks: Tracks, now: number): Levels {
  return each((name) => ({ lit: valueAt(tracks[name].lit, now), glow: valueAt(tracks[name].glow, now) }));
}

export function allSettled(tracks: Tracks, now: number): boolean {
  return LIGHT_NAMES.every((name) => settled(tracks[name].lit, now) && settled(tracks[name].glow, now));
}

export function sameLevels(a: Levels, b: Levels): boolean {
  return LIGHT_NAMES.every((name) => a[name].lit === b[name].lit && a[name].glow === b[name].glow);
}

/** A level too faint to see is not drawn. */
const FAINT = 0.002;

/** One thing a frame draws: a picture, how strongly, and whether it is laid over or added as light. */
export interface Draw {
  image: "dark" | `lit:${LightName}` | `glow:${Part}`;
  alpha: number;
  blend: "source-over" | "screen";
}

/**
 * What one frame draws, in order: the dark board, then for each part its cut-out of the awake board and
 * over that its added light, then the ground between the parts. The order matters: added light depends on
 * what lies under it.
 */
export function drawList(levels: Levels): Draw[] {
  const list: Draw[] = [{ image: "dark", alpha: 1, blend: "source-over" }];
  for (const part of PARTS) {
    const { lit, glow } = levels[part];
    if (lit > FAINT) list.push({ image: `lit:${part}`, alpha: lit, blend: "source-over" });
    if (glow > FAINT) list.push({ image: `glow:${part}`, alpha: glow, blend: "screen" });
  }
  if (levels.whole.lit > FAINT) list.push({ image: "lit:whole", alpha: levels.whole.lit, blend: "source-over" });
  return list;
}

/** The two pictures of the board are this large. A canvas with more pixels would hold no more detail. */
export const PLATE = { width: 1920, height: 1200 } as const;

/**
 * The canvas's own pixels for a board laid out `cssWidth` wide on a screen of a given density. One canvas
 * pixel per screen pixel, up to the picture's own size and no further: a denser screen or a larger board
 * gets the same canvas, so the picture's memory has a fixed ceiling (1920 x 1200 pixels, 9.2 MB). A board
 * that is slid sideways does not sit on whole screen pixels, so on a screen of low density it is given two
 * canvas pixels per screen pixel, under the same ceiling, and stays sharp. The canvas has the picture's
 * shape, as the board's box has.
 */
export function backingSize(cssWidth: number, ratio: number, slid = false): { width: number; height: number } {
  const density = ratio > 0 ? ratio : 1;
  const wanted = Math.round(cssWidth * (slid ? Math.max(density, 2) : density));
  const width = Math.max(1, Math.min(PLATE.width, wanted));
  return { width, height: Math.max(1, Math.round((width * PLATE.height) / PLATE.width)) };
}

/** The added light's blur in canvas pixels: a share of the stage's width, scaled as the board is. */
export function glowBlur(stageWidth: number, cssWidth: number, canvasWidth: number): number {
  return cssWidth > 0 ? (GLOW_BLUR_OF_STAGE * stageWidth * canvasWidth) / cssWidth : 0;
}

/** The light of a step in a few words, so a change of step is told from a render that changes nothing. */
export function lightKey(layers: Layers): string {
  return LIGHT_NAMES.map((name) => {
    const { on, order, strong, rest } = layerOf(layers, name);
    return `${on ? 1 : 0}${rest ? 1 : 0}${strong ? 1 : 0}${order}`;
  }).join(" ");
}

/** The parts a step shows lit, resting and with added light, by name: what the picture's element says of itself. */
export function lightSummary(layers: Layers): { lit: string; rest: string; strong: string; whole: boolean } {
  const names = (pick: (layer: PartLayer) => boolean) => PARTS.filter((part) => pick(layers.parts[part])).join(" ");
  return {
    lit: names((layer) => layer.on),
    rest: names((layer) => layer.rest),
    strong: names((layer) => layer.strong),
    whole: layers.whole.on,
  };
}
