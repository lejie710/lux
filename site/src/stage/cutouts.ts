// The pieces a frame of the board is drawn from: the dark picture, and for each part a cut-out of the awake
// picture through that part's soft mask, once as it is and once brighter and a little soft, for the added
// light. Each piece is only as large as its mask, and all of them are made once for a canvas size. A picture
// the pieces are cut from is held only until its pieces are made. The functions over pixels are plain and
// tested without a browser.
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
    // The first pixel of the row that is not clear, then the last: what lies between needs no look.
    const row = y * width * 4 + 3;
    let first = 0;
    while (first < width && data[row + first * 4] === 0) first++;
    if (first === width) continue;
    let last = width - 1;
    while (last > first && data[row + last * 4] === 0) last--;
    if (first < left) left = first;
    if (last > right) right = last;
    if (y < top) top = y;
    bottom = y;
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

// From here on: the browser.

/** A picture fetched for one set of pieces. It is not decoded until it is first needed. */
function load(url: string): Promise<HTMLImageElement> {
  return new Promise<HTMLImageElement>((resolve, reject) => {
    const image = new Image();
    image.decoding = "async";
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error(`picture not loaded: ${url}`));
    image.src = url;
  });
}

/** Decodes a picture before it is drawn, off the page's own thread where the browser can. */
async function decode(image: HTMLImageElement): Promise<void> {
  if (typeof image.decode === "function") await image.decode();
}

/** A picture that is not needed again gives its decoded pixels back at once, without waiting to be collected. */
function forget(image: HTMLImageElement): void {
  image.onload = null;
  image.onerror = null;
  image.removeAttribute("src");
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
const bounds = new Map<LightName, { box: Box | null; width: number; height: number }>();

function boundsOf(name: LightName, mask: HTMLImageElement) {
  let size = bounds.get(name);
  if (!size) {
    const [canvas, context] = scratch(mask.naturalWidth, mask.naturalHeight, true);
    try {
      context.drawImage(mask, 0, 0);
      const box = alphaBounds(
        context.getImageData(0, 0, canvas.width, canvas.height).data,
        canvas.width,
        canvas.height,
      );
      size = { box, width: canvas.width, height: canvas.height };
    } finally {
      empty(canvas);
    }
    bounds.set(name, size);
  }
  return size;
}

/** The colour the check below draws and expects to read back. */
const PROBE = [10, 200, 90, 255] as const;

/** Whether pixels read back from a canvas are the pixels that were drawn. */
export function readsBack(data: ArrayLike<number>): boolean {
  if (data.length < PROBE.length || data.length % PROBE.length !== 0) return false;
  for (let n = 0; n < data.length; n++) if (Math.abs(data[n] - PROBE[n % PROBE.length]) > 2) return false;
  return true;
}

/**
 * The cut-outs are placed and the added light is made from pixels read back from a canvas. A browser may
 * hand back clear or altered pixels instead (a privacy setting does); then no piece can be trusted, and
 * this throws, so the stage shows its layers.
 */
function checkReadback(): void {
  const [canvas, context] = scratch(4, 4, true);
  try {
    context.fillStyle = `rgb(${PROBE[0]}, ${PROBE[1]}, ${PROBE[2]})`;
    context.fillRect(0, 0, 4, 4);
    if (!readsBack(context.getImageData(0, 0, 4, 4).data)) throw new Error("pixels cannot be read back");
  } finally {
    empty(canvas);
  }
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
  /** The pictures this set has fetched and not yet let go. */
  private pictures = new Set<HTMLImageElement>();
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

  /** Keeps a fetched picture until it is let go; one that arrives after the set is gone is let go at once. */
  private hold(image: HTMLImageElement): HTMLImageElement {
    if (this.gone) forget(image);
    else this.pictures.add(image);
    return image;
  }

  private letGo(image: HTMLImageElement): void {
    this.pictures.delete(image);
    forget(image);
  }

  private async prepare(): Promise<void> {
    checkReadback();
    const names: LightName[] = [...PARTS, "whole"];
    // Everything is fetched at once. The masks are then decoded and used one at a time, each let go as soon
    // as its cut-out is made, with a pause after each: making them never holds the page up for long, and
    // no more than one decoded mask is held at a time.
    const masks = names.map((name) => load(MASK_OF[name]).then((image) => this.hold(image)));
    // A mask that fails is heard of where it is awaited below, and nowhere else.
    for (const mask of masks) mask.catch(() => {});
    const [dark, awake] = await Promise.all(
      [DARK, AWAKE].map(async (url) => {
        const image = this.hold(await load(url));
        await decode(image);
        return image;
      }),
    );
    for (const [n, name] of names.entries()) {
      const mask = await masks[n];
      if (this.gone) return;
      await decode(mask);
      if (this.gone) return;
      const { box, width, height } = boundsOf(name, mask);
      const place = box && boxOnCanvas(box, { width, height }, this);
      // Every mask of the picture has something in it. One that seems empty was not read: no piece is made.
      if (!place || place.width <= 0 || place.height <= 0) throw new Error(`nothing in the mask: ${name}`);
      this.boxes.set(name, place);
      const [canvas, context] = scratch(place.width, place.height);
      this.made.set(`lit:${name}`, { source: canvas, ...place });
      this.cut(context, awake, place, place);
      this.mask(context, mask, place);
      this.letGo(mask);
      await new Promise<void>((resolve) => window.setTimeout(resolve));
    }
    if (this.gone) return;
    this.awake = awake;
    this.made.set("dark", { source: dark, x: 0, y: 0, width: this.width, height: this.height });
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
    // The part's own cut-out has the mask's soft edge in its alpha, so it serves as the mask here.
    const lit = this.made.get(`lit:${part}`);
    if (!place || !lit || !this.awake) return null;
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
      context.globalCompositeOperation = "destination-in";
      context.drawImage(lit.source, 0, 0, place.width, place.height);
      context.globalCompositeOperation = "source-over";
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

  /**
   * Once every piece is made, the awake picture is not needed again and is let go. A canvas of another size
   * fetches it again, from the browser's cache, and decodes it again.
   */
  private settle(): void {
    if (PARTS.some((name) => this.boxes.has(name) && !this.made.has(`glow:${name}`))) return;
    if (this.awake) this.letGo(this.awake);
    this.awake = null;
    this.room = {};
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
    for (const image of this.pictures) forget(image);
    this.pictures.clear();
    this.awake = null;
    this.room = {};
  }
}

const shared = new Map<string, Cutouts>();
const keyOf = (width: number, height: number, sigma: number) => `${width}x${height}@${sigma.toFixed(2)}`;

/** The pieces for a canvas size, shared with any other stage that draws at that size. */
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
