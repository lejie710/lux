// Draws the board of one stage on its canvas and keeps it up to date: one frame when a step is shown as a
// still, and a run of frames after a step change in the scrolled story, which ends when every light has
// arrived. Nothing is drawn while nothing changes, while the page is hidden, or for a stage far from the
// window. If the canvas cannot be made or drawn, it says so once and stops, and the stage shows its layers.
import { PARTS } from "../content/types";
import type { Layers } from "../model/scene";
import { acquire, paint, release, type Cutouts } from "./cutouts";
import {
  allSettled,
  backingSize,
  drawList,
  glowBlur,
  levelsAt,
  retargetAll,
  sameLevels,
  tracksAt,
  type Levels,
} from "./light";

export type LightStatus = "pending" | "drawn" | "failed";

/** A board that has left view is still drawn for this long: the time it takes to fade out. Milliseconds. */
const OUT_OF_SIGHT = 800;
/** A change of size is acted on once it has stood for this long. */
const RESIZE_WAIT = 150;

export interface BoardLight {
  /** A new step: its lights are the new end of every level. */
  step(layers: Layers): void;
  stop(): void;
}

export function runBoardLight(
  canvas: HTMLCanvasElement,
  first: Layers,
  animate: boolean,
  report: (status: LightStatus) => void,
): BoardLight {
  const stage = canvas.closest<HTMLElement>(".stage") ?? canvas;
  let tracks = tracksAt(first);
  let boardOn = first.board;
  let changedAt = 0;
  let set: Cutouts | null = null;
  let context: CanvasRenderingContext2D | null = null;
  let drawn: Levels | null = null;
  let sized = "";
  let taking = 0;
  let frame = 0;
  let timer = 0;
  let stopped = false;
  // The pinned stage of the scrolled story is always held; a still section only while it is near the window.
  let near = animate;

  const still = () => !animate || window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  /** Gives the canvas's memory and the shared pieces back. */
  const drop = () => {
    taking++;
    window.cancelAnimationFrame(frame);
    frame = 0;
    if (set) {
      set.unlisten(redraw);
      release(set);
    }
    set = null;
    context = null;
    drawn = null;
    sized = "";
    canvas.width = 0;
    canvas.height = 0;
  };

  const fail = () => {
    if (stopped) return;
    stopped = true;
    drop();
    unlisten();
    report("failed");
  };

  /** Asks ahead for the added light of the parts a step is about, so it is made before its fade begins. */
  const ask = (layers: Layers) => {
    for (const part of PARTS) if (layers.parts[part].strong) set?.piece(`glow:${part}`);
  };

  const draw = (now: number) => {
    if (!context || !set) return;
    if (set.broken) throw new Error("a piece of the picture could not be made");
    const levels = levelsAt(tracks, now);
    if (drawn && sameLevels(drawn, levels)) return;
    paint(context, set.piece, drawList(levels));
    drawn = levels;
  };

  /** Whether another frame is due: a light is still on its way, on a page and a board that can be seen. */
  const moving = (now: number) =>
    animate &&
    context !== null &&
    !document.hidden &&
    !allSettled(tracks, now) &&
    (boardOn || now - changedAt < OUT_OF_SIGHT);

  const tick = () => {
    frame = 0;
    if (stopped) return;
    const now = performance.now();
    try {
      draw(now);
    } catch {
      fail();
      return;
    }
    if (moving(now)) frame = window.requestAnimationFrame(tick);
  };

  const run = () => {
    if (!frame && !stopped && moving(performance.now())) frame = window.requestAnimationFrame(tick);
  };

  /** Draws now, whatever was drawn before, and goes on if a light is on its way. */
  const redraw = () => {
    if (stopped || !context) return;
    drawn = null;
    try {
      draw(performance.now());
    } catch {
      fail();
      return;
    }
    run();
  };

  /** Sizes the canvas for the board as it is laid out now, takes the pieces for that size, and draws. */
  const take = async () => {
    if (stopped || !near) return;
    const cssWidth = canvas.clientWidth;
    if (!cssWidth) return;
    // A board wider than its stage is slid sideways to the step's parts.
    const stageWidth = stage.clientWidth;
    const size = backingSize(cssWidth, window.devicePixelRatio, cssWidth > stageWidth);
    const sigma = glowBlur(stageWidth, cssWidth, size.width);
    const key = `${size.width}x${size.height}@${sigma.toFixed(2)}`;
    if (key === sized) return;
    const mine = ++taking;
    const next = acquire(size.width, size.height, sigma);
    try {
      await next.ready;
    } catch {
      release(next);
      if (mine === taking) fail();
      return;
    }
    if (stopped || mine !== taking) {
      release(next);
      return;
    }
    try {
      if (set) {
        set.unlisten(redraw);
        release(set);
      }
      set = next;
      // An added light that a frame had to do without is drawn as soon as it is made.
      set.listen(redraw);
      sized = key;
      canvas.width = size.width;
      canvas.height = size.height;
      context = canvas.getContext("2d");
      if (!context) throw new Error("no canvas");
      // The dark plate is drawn from the picture itself at the canvas's size: scaled with care, as a page scales it.
      context.imageSmoothingEnabled = true;
      context.imageSmoothingQuality = "high";
      drawn = null;
      draw(performance.now());
    } catch {
      fail();
      return;
    }
    report("drawn");
    if (animate) set.warm();
    run();
  };

  const resized = () => {
    window.clearTimeout(timer);
    timer = window.setTimeout(take, RESIZE_WAIT);
  };

  const shown = () => {
    if (document.hidden) {
      window.cancelAnimationFrame(frame);
      frame = 0;
    } else redraw();
  };

  const sizes = "ResizeObserver" in window ? new ResizeObserver(resized) : null;
  sizes?.observe(canvas);
  // A still section keeps its canvas while it is within half a window of the window, and no longer.
  const reach = Math.max(300, Math.round(window.innerHeight / 2));
  const places =
    !animate && "IntersectionObserver" in window
      ? new IntersectionObserver(
          (entries) => {
            const now = entries[entries.length - 1].isIntersecting;
            if (now === near) return;
            near = now;
            if (near) void take();
            else if (set) {
              drop();
              report("pending");
            }
          },
          { rootMargin: `${reach}px 0px` },
        )
      : null;
  if (places) places.observe(stage);
  else near = true;
  window.addEventListener("resize", resized);
  window.addEventListener("pageshow", shown);
  document.addEventListener("visibilitychange", shown);
  canvas.addEventListener("contextrestored", redraw);

  function unlisten() {
    window.clearTimeout(timer);
    sizes?.disconnect();
    places?.disconnect();
    window.removeEventListener("resize", resized);
    window.removeEventListener("pageshow", shown);
    document.removeEventListener("visibilitychange", shown);
    canvas.removeEventListener("contextrestored", redraw);
  }

  void take();

  return {
    step(layers) {
      if (stopped) return;
      const now = performance.now();
      boardOn = layers.board;
      changedAt = now;
      tracks = still() ? tracksAt(layers) : retargetAll(tracks, layers, now);
      if (!context) return;
      ask(layers);
      try {
        draw(now);
      } catch {
        fail();
        return;
      }
      run();
    },
    stop() {
      if (stopped) return;
      stopped = true;
      drop();
      unlisten();
    },
  };
}
