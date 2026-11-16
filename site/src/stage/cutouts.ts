// The pieces a frame of the board is drawn from: the dark picture, and for each part a cut-out of the awake
// picture through that part's soft mask, once as it is and once brighter and a little soft, for the added
// light. Each piece is only as large as its mask, and all of them are made once for a canvas size and
// shared by every stage on the page. The functions over pixels are plain and tested without a browser.
import { PARTS, type Part } from "../content/types";
import { GLOW_BRIGHTNESS, type Draw, type LightName } from "./light";
import { AWAKE, DARK, MASK_OF } from "./plates";

export interface Box {
  x: number;
  y: number;
  width: number;
  height: number;
}

/** The smallest box that holds every pixel of an RGBA picture that is not fully clear, or null if none is. */
export function alphaBounds(data: ArrayLike<number>, width: number, height: number): Box | null {
  let left = width;
  let right = -1;
  let top = height;
  let bottom = -1;
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      if (data[(y * width + x) * 4 + 3] === 0) continue;
      if (x < left) left = x;
      if (x > right) right = x;
      if (y < top) top = y;
      if (y > bottom) bottom = y;
    }
  }
  return right < 0 ? null : { x: left, y: top, width: right - left + 1, height: bottom - top + 1 };
}

/**
 * A box of a mask in the canvas's own pixels: grown by one pixel of the mask on every side, so the mask's
 * soft edge ends inside it, set on whole pixels and kept inside the canvas.
 */
export function boxOnCanvas(
  box: Box,
  mask: { width: number; height: number },
  canvas: { width: number; height: number },
): Box {
  const sx = canvas.width / mask.width;
  const sy = canvas.height / mask.height;
  const left = Math.max(0, Math.floor((box.x - 1) * sx));
  const top = Math.max(0, Math.floor((box.y - 1) * sy));
  const right = Math.min(canvas.width, Math.ceil((box.x + box.width + 1) * sx));
  const bottom = Math.min(canvas.height, Math.ceil((box.y + box.height + 1) * sy));
  return { x: left, y: top, width: right - left, height: bottom - top };
}

/** A box grown by a margin on every side and kept inside a canvas. */
export function grown(box: Box, by: number, canvas: { width: number; height: number }): Box {
  const left = Math.max(0, box.x - by);
  const top = Math.max(0, box.y - by);
  const right = Math.min(canvas.width, box.x + box.width + by);
  const bottom = Math.min(canvas.height, box.y + box.height + by);
  return { x: left, y: top, width: right - left, height: bottom - top };
}

/** Every colour of an RGBA picture made brighter by a factor, as a stylesheet's `brightness()` does. Alpha stays. */
export function brighten(data: Uint8ClampedArray, factor: number): void {
  for (let n = 0; n < data.length; n += 4) {
    data[n] = data[n] * factor;
    data[n + 1] = data[n + 1] * factor;
    data[n + 2] = data[n + 2] * factor;
  }
}

/** The weights of a Gaussian blur of a given deviation, out to three deviations on each side. */
export function blurWeights(sigma: number): Float32Array {
  const reach = Math.max(1, Math.ceil(sigma * 3));
  const weights = new Float32Array(reach * 2 + 1);
  let sum = 0;
  for (let n = -reach; n <= reach; n++) sum += weights[n + reach] = Math.exp(-(n * n) / (2 * sigma * sigma));
  for (let n = 0; n < weights.length; n++) weights[n] /= sum;
  return weights;
}

/** Work arrays that one blur after another can use, so that each does not leave its own behind. */
export interface BlurRoom {
  a?: Float32Array;
  b?: Float32Array;
}

/** A blur is worked in bands of this many rows, so it can be done a little at a time. */
const BAND = 64;

/**
 * An RGBA picture blurred in place, as a stylesheet's `blur()` does: a Gaussian of the given deviation over
 * colour weighted by alpha, with nothing but clear pixels beyond the picture's edges. The work is done in
 * bands of rows and hands back between them, so a caller with other things to do can spread it out.
 *
 * The picture is copied into a frame of clear pixels as wide as the blur reaches, so every pass is one
 * plain run over a stretch of the array: a neighbour beyond an edge is a clear pixel of the frame.
 */
export function* blurInSteps(
  data: Uint8ClampedArray,
  width: number,
  height: number,
  sigma: number,
  room: BlurRoom = {},
): Generator<void, void> {
  if (!(sigma > 0.05) || width === 0 || height === 0) return;
  const weights = blurWeights(sigma);
  const reach = (weights.length - 1) / 2;
  const wide = width + 2 * reach;
  const tall = height + 2 * reach;
  const row = wide * 4;
  // The two work arrays are the largest things a blur holds: one pair serves every blur that is given it.
  if (!room.a || !room.b || room.a.length < row * tall) {
    room.a = new Float32Array(row * tall);
    room.b = new Float32Array(row * tall);
  } else {
    room.a.fill(0, 0, row * tall);
    room.b.fill(0, 0, row * tall);
  }
  const a = room.a;
  const b = room.b;
  for (let y = 0; y < height; y++) {
    let from = y * width * 4;
    let to = (y + reach) * row + reach * 4;
    for (let x = 0; x < width; x++, from += 4, to += 4) {
      // Colour weighted by alpha. Most pictures are opaque, and then the weight is one.
      const alpha = data[from + 3] === 255 ? 1 : data[from + 3] / 255;
      a[to] = data[from] * alpha;
      a[to + 1] = data[from + 1] * alpha;
      a[to + 2] = data[from + 2] * alpha;
      a[to + 3] = data[from + 3];
    }
  }
  yield;
  // The weights are the same on both sides of the middle, so each pass adds a pair of neighbours at a time.
  const pass = (source: Float32Array, target: Float32Array, step: number, first: number, last: number) => {
    const middle = weights[reach];
    for (let n = first; n < last; n++) target[n] = source[n] * middle;
    for (let k = 1; k <= reach; k++) {
      const weight = weights[reach + k];
      const away = k * step;
      for (let n = first; n < last; n++) target[n] += (source[n - away] + source[n + away]) * weight;
    }
  };
  // Across the rows of the picture, from a to b; then down the columns, from b back to a.
  for (let y = reach; y < tall - reach; y += BAND) {
    pass(a, b, 4, y * row + reach * 4, Math.min(y + BAND, tall - reach) * row - reach * 4);
    yield;
  }
  for (let y = reach; y < tall - reach; y += BAND) {
    pass(b, a, row, y * row, Math.min(y + BAND, tall - reach) * row);
    yield;
  }
  for (let y = 0; y < height; y++) {
    let from = (y + reach) * row + reach * 4;
    let to = y * width * 4;
    for (let x = 0; x < width; x++, from += 4, to += 4) {
      const alpha = a[from + 3] / 255;
      const scale = alpha > 0.999 ? 1 : alpha > 0 ? 1 / alpha : 0;
      data[to] = a[from] * scale;
      data[to + 1] = a[from + 1] * scale;
      data[to + 2] = a[from + 2] * scale;
      data[to + 3] = a[from + 3];
    }
  }
}

/** The same blur, done in one go. */
export function blur(data: Uint8ClampedArray, width: number, height: number, sigma: number): void {
  const steps = blurInSteps(data, width, height, sigma);
  while (!steps.next().done);
}

/** One piece of a frame: a picture and where it goes on the canvas, in the canvas's own pixels. */
export interface Piece extends Box {
  source: CanvasImageSource;
}

/** The little of a canvas's context that drawing a frame needs. */
export interface Brush {
  globalAlpha: number;
  globalCompositeOperation: GlobalCompositeOperation;
  drawImage(source: CanvasImageSource, x: number, y: number, width: number, height: number): void;
}

/** Draws one frame: each piece of the list in order, at its strength, laid over or added as light. */
export function paint(brush: Brush, pieces: (name: Draw["image"]) => Piece | null, list: readonly Draw[]): void {
  for (const draw of list) {
    const piece = pieces(draw.image);
    if (!piece) continue;
    brush.globalAlpha = draw.alpha;
    brush.globalCompositeOperation = draw.blend;
    brush.drawImage(piece.source, piece.x, piece.y, piece.width, piece.height);
  }
  brush.globalAlpha = 1;
  brush.globalCompositeOperation = "source-over";
}

// From here on: the browser. Pictures are fetched and decoded once and shared by everything that asks.

const pictures = new Map<string, Promise<HTMLImageElement>>();

function picture(url: string): Promise<HTMLImageElement> {
  let loading = pictures.get(url);
  if (!loading) {
    loading = new Promise<HTMLImageElement>((resolve, reject) => {
      const image = new Image();
      const failed = () => reject(new Error(`picture not loaded: ${url}`));
      image.decoding = "async";
      image.src = url;
      // Decoded before it is first drawn, off the page's own thread where the browser can.
      if (typeof image.decode === "function") image.decode().then(() => resolve(image), failed);
      else {
        image.onload = () => resolve(image);
        image.onerror = failed;
      }
    });
    // A picture that failed is asked for again the next time.
    loading.catch(() => pictures.delete(url));
    pictures.set(url, loading);
  }
  return loading;
}

function scratch(width: number, height: number, read = false): [HTMLCanvasElement, CanvasRenderingContext2D] {
  const canvas = document.createElement("canvas");
  canvas.width = width;
  canvas.height = height;
  const context = canvas.getContext("2d", read ? { willReadFrequently: true } : undefined);
  if (!context) throw new Error("no canvas");
  context.imageSmoothingEnabled = true;
  context.imageSmoothingQuality = "high";
  return [canvas, context];
}

/** A canvas gives its memory back at once when it has no size. */
function empty(canvas: HTMLCanvasElement): void {
  canvas.width = 0;
  canvas.height = 0;
}

/** Where each mask has anything in it, in the mask's own pixels: read once per mask. */
const bounds = new Map<LightName, Promise<{ box: Box | null; width: number; height: number }>>();

function boundsOf(name: LightName) {
  let reading = bounds.get(name);
  if (!reading) {
    reading = picture(MASK_OF[name]).then((mask) => {
      const [canvas, context] = scratch(mask.naturalWidth, mask.naturalHeight, true);
      context.drawImage(mask, 0, 0);
      const box = alphaBounds(
        context.getImageData(0, 0, canvas.width, canvas.height).data,
        canvas.width,
        canvas.height,
      );
      const size = { box, width: canvas.width, height: canvas.height };
      empty(canvas);
      return size;
    });
    reading.catch(() => bounds.delete(name));
    bounds.set(name, reading);
  }
  return reading;
}

/**
 * An added light is never made in one go, so making it never holds the page up: a few milliseconds of work
 * at a time, with a pause after each slice and a longer one after each part. The lights no frame has asked
 * for yet are made ahead of their first use, after a wait. Milliseconds.
 */
const WARM_WAIT = 600;
const WORK_SLICE = 8;
const WORK_PAUSE = 24;
const WORK_GAP = 90;
/** A light that a frame is waiting for is made in longer slices with shorter pauses. */
const URGENT_SLICE = 12;
const URGENT_PAUSE = 4;

/**
 * The pieces for one canvas size. The dark picture and the plain cut-outs are ready when `ready` settles.
 * The cut-out of an added light is made when a frame first asks for it, or ahead of time after `warm`:
 * until it is made the frame is drawn without it, and those who listen are told when it is there.
 */
export class Cutouts {
  readonly ready: Promise<void>;
  users = 0;
  /** Whether a piece could not be made. A stage that finds this shows its layers instead of a canvas. */
  broken = false;
  private awake: HTMLImageElement | null = null;
  private masks = new Map<LightName, HTMLImageElement>();
  private boxes = new Map<LightName, Box>();
  private made = new Map<Draw["image"], Piece>();
  /** The added lights a frame has asked for and does not have yet, the latest first. */
  private wanted: Part[] = [];
  /** Whether the added lights nobody has asked for are made too. */
  private all = false;
  private timer = 0;
  /** The added light being made, part way through. */
  private ahead: { part: Part; steps: Generator<void, Piece | null> } | null = null;
  private gone = false;
  /** Work arrays for the blur of one added light after another. */
  private room: BlurRoom = {};
  private listeners = new Set<() => void>();

  constructor(
    readonly width: number,
    readonly height: number,
    /** The blur of the added light, in this canvas's pixels. */
    readonly sigma: number,
  ) {
    this.ready = this.prepare();
    // Whoever takes the pieces hears of a failure; nothing else needs to.
    this.ready.catch(() => {});
  }

  private async prepare(): Promise<void> {
    const names: LightName[] = [...PARTS, "whole"];
    const [dark, awake, masks, found] = await Promise.all([
      picture(DARK),
      picture(AWAKE),
      Promise.all(names.map((name) => picture(MASK_OF[name]))),
      Promise.all(names.map(boundsOf)),
    ]);
    if (this.gone) return;
    this.awake = awake;
    this.made.set("dark", { source: dark, x: 0, y: 0, width: this.width, height: this.height });
    names.forEach((name, n) => {
      const { box, width, height } = found[n];
      this.masks.set(name, masks[n]);
      if (!box) return;
      const place = boxOnCanvas(box, { width, height }, this);
      if (place.width <= 0 || place.height <= 0) return;
      this.boxes.set(name, place);
      const [canvas, context] = scratch(place.width, place.height);
      this.cut(context, awake, place, place);
      this.mask(context, masks[n], place);
      this.made.set(`lit:${name}`, { source: canvas, ...place });
    });
  }

  /** Draws the part of a picture that lies under `from` on the canvas into a context, at `into`'s size. */
  private cut(context: CanvasRenderingContext2D, source: HTMLImageElement, from: Box, into: Box): void {
    const sx = source.naturalWidth / this.width;
    const sy = source.naturalHeight / this.height;
    context.drawImage(
      source,
      from.x * sx,
      from.y * sy,
      from.width * sx,
      from.height * sy,
      0,
      0,
      into.width,
      into.height,
    );
  }

  /** Keeps of a context only what the mask lets through, the mask stretched over the whole picture. */
  private mask(context: CanvasRenderingContext2D, mask: HTMLImageElement, place: Box): void {
    context.globalCompositeOperation = "destination-in";
    this.cut(context, mask, place, place);
    context.globalCompositeOperation = "source-over";
  }

  /**
   * The cut-out of a part's added light: the awake picture made brighter, then soft, then cut by the mask.
   * It is made in steps, so the work can be spread out; run to its end, it gives the piece.
   */
  private *glow(part: Part): Generator<void, Piece | null> {
    const place = this.boxes.get(part);
    const mask = this.masks.get(part);
    if (!place || !mask || !this.awake) return null;
    // The blur takes in what lies around the cut-out, so a wider piece is blurred and its middle kept.
    const wide = grown(place, Math.ceil(this.sigma * 3) + 1, this);
    const [work, pixels] = scratch(wide.width, wide.height, true);
    try {
      this.cut(pixels, this.awake, wide, wide);
      const image = pixels.getImageData(0, 0, wide.width, wide.height);
      yield;
      brighten(image.data, GLOW_BRIGHTNESS);
      yield* blurInSteps(image.data, wide.width, wide.height, this.sigma, this.room);
      yield;
      pixels.putImageData(image, 0, 0);
      const [canvas, context] = scratch(place.width, place.height);
      context.drawImage(
        work,
        place.x - wide.x,
        place.y - wide.y,
        place.width,
        place.height,
        0,
        0,
        place.width,
        place.height,
      );
      this.mask(context, mask, place);
      return { source: canvas, ...place };
    } finally {
      empty(work);
    }
  }

  /**
   * A piece by name, or null when the picture has nothing there or the piece is not made yet. An added
   * light that is asked for and not yet made is made next.
   */
  piece = (name: Draw["image"]): Piece | null => {
    const have = this.made.get(name);
    if (have || this.gone || !name.startsWith("glow:")) return have ?? null;
    const part = name.slice(5) as Part;
    if (this.boxes.has(part) && this.wanted[0] !== part) {
      this.wanted = [part, ...this.wanted.filter((other) => other !== part)];
      // A frame is waiting: whatever wait was running is cut short.
      window.clearTimeout(this.timer);
      this.timer = 0;
      this.work(0);
    }
    return null;
  };

  /** Tells `heard` whenever a piece that was missing has been made. */
  listen(heard: () => void): void {
    this.listeners.add(heard);
  }

  unlisten(heard: () => void): void {
    this.listeners.delete(heard);
  }

  /** Makes the added light of every part ahead of its first use, after a wait. */
  warm(): void {
    if (this.all || this.gone) return;
    this.all = true;
    this.work(WARM_WAIT);
  }

  /** The next added light to make: one a frame waits for, or, ahead of time, the first not yet made. */
  private due(): Part | undefined {
    const missing = (part: Part) => this.boxes.has(part) && !this.made.has(`glow:${part}`);
    return this.wanted.find(missing) ?? (this.all ? PARTS.find(missing) : undefined);
  }

  /** Does a slice of the making after a wait, and again until nothing is left to make. */
  private work(wait: number): void {
    if (this.timer || this.gone) return;
    this.timer = window.setTimeout(() => {
      this.timer = 0;
      if (this.gone) return;
      if (!this.ahead) {
        const part = this.due();
        if (!part) {
          // Nothing left to make for now: the work arrays are not kept.
          this.room = {};
          return;
        }
        this.ahead = { part, steps: this.glow(part) };
      }
      const { part, steps } = this.ahead;
      const urgent = this.wanted.includes(part);
      let pause = urgent ? URGENT_PAUSE : WORK_PAUSE;
      try {
        const until = performance.now() + (urgent ? URGENT_SLICE : WORK_SLICE);
        let step = steps.next();
        while (!step.done && performance.now() < until) step = steps.next();
        if (step.done) {
          this.ahead = null;
          this.wanted = this.wanted.filter((other) => other !== part);
          if (step.value) this.made.set(`glow:${part}`, step.value);
          else this.boxes.delete(part);
          this.settle();
          for (const heard of this.listeners) heard();
          // A light a frame waits for is started at once; one made ahead of time, after a longer pause.
          pause = this.wanted.length > 0 ? URGENT_PAUSE : WORK_GAP;
        }
      } catch {
        // A light that cannot be made: the pieces are no good, and every stage that draws with them is told.
        this.ahead = null;
        this.broken = true;
        for (const heard of this.listeners) heard();
        return;
      }
      this.work(pause);
    }, wait);
  }

  /** Once every piece is made, the awake picture and the masks are not needed again. */
  private settle(): void {
    if (PARTS.some((name) => this.boxes.has(name) && !this.made.has(`glow:${name}`))) return;
    this.awake = null;
    this.masks.clear();
    this.room = {};
    // The pictures themselves are let go too; a canvas of another size fetches them again from the cache.
    pictures.delete(AWAKE);
    for (const name of [...PARTS, "whole"] as const) pictures.delete(MASK_OF[name]);
  }

  dispose(): void {
    this.gone = true;
    window.clearTimeout(this.timer);
    this.ahead?.steps.return(null);
    this.ahead = null;
    this.listeners.clear();
    this.wanted = [];
    for (const [name, piece] of this.made) if (name !== "dark") empty(piece.source as HTMLCanvasElement);
    this.made.clear();
    this.boxes.clear();
    this.masks.clear();
    this.awake = null;
    this.room = {};
  }
}

const shared = new Map<string, Cutouts>();
const keyOf = (width: number, height: number, sigma: number) => `${width}x${height}@${sigma.toFixed(2)}`;

/** The pieces for a canvas size, shared with every other stage that draws at that size. */
export function acquire(width: number, height: number, sigma: number): Cutouts {
  const key = keyOf(width, height, sigma);
  let set = shared.get(key);
  if (!set) {
    set = new Cutouts(width, height, Number(sigma.toFixed(2)));
    shared.set(key, set);
  }
  set.users++;
  return set;
}

/** Gives the pieces back. When no stage draws at that size any more, their memory is freed. */
export function release(set: Cutouts): void {
  set.users--;
  if (set.users > 0) return;
  const key = keyOf(set.width, set.height, set.sigma);
  if (shared.get(key) === set) shared.delete(key);
  set.dispose();
}
