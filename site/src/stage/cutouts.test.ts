// The functions over pixels that make the board's pieces, on small pictures, and the drawing of a frame
// against a brush that only writes down what it is asked to do. No browser is needed for any of it.
import { describe, expect, it } from "vitest";
import { STEPS, layersAt } from "../model/scene";
import {
  alphaBounds,
  blur,
  blurInSteps,
  blurWeights,
  boxOnCanvas,
  brighten,
  grown,
  paint,
  type Brush,
  type Piece,
} from "./cutouts";
import { drawList, levelsAt, tracksAt, type Draw } from "./light";

/** An RGBA picture of one colour, with some pixels set. */
function picture(width: number, height: number, set: Record<string, [number, number, number, number]> = {}) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (const [at, colour] of Object.entries(set)) {
    const [x, y] = at.split(",").map(Number);
    data.set(colour, (y * width + x) * 4);
  }
  return data;
}
const pixel = (data: Uint8ClampedArray, width: number, x: number, y: number) => [
  ...data.slice((y * width + x) * 4, (y * width + x) * 4 + 4),
];

describe("where a mask has anything in it", () => {
  it("is the smallest box around every pixel that is not clear", () => {
    const data = picture(8, 6, { "2,1": [0, 0, 0, 9], "5,4": [0, 0, 0, 255], "3,3": [255, 255, 255, 1] });
    expect(alphaBounds(data, 8, 6)).toEqual({ x: 2, y: 1, width: 4, height: 4 });
  });

  it("ignores colour without alpha, and is nothing for a clear mask", () => {
    expect(alphaBounds(picture(4, 4, { "1,1": [255, 255, 255, 0] }), 4, 4)).toBeNull();
    expect(alphaBounds(picture(4, 4), 4, 4)).toBeNull();
  });

  it("is the whole picture for a mask that reaches every edge", () => {
    const data = picture(3, 2, { "0,0": [0, 0, 0, 1], "2,1": [0, 0, 0, 1] });
    expect(alphaBounds(data, 3, 2)).toEqual({ x: 0, y: 0, width: 3, height: 2 });
  });
});

describe("a mask's box on the canvas", () => {
  const mask = { width: 600, height: 375 };

  it("is grown by one pixel of the mask and set on whole canvas pixels", () => {
    // A canvas 3.2 times the mask: 99 -> 316.8, 201 -> 643.2 across; 49 -> 156.8, 101 -> 323.2 down.
    expect(boxOnCanvas({ x: 100, y: 50, width: 100, height: 50 }, mask, { width: 1920, height: 1200 })).toEqual({
      x: 316,
      y: 156,
      width: 644 - 316,
      height: 324 - 156,
    });
  });

  it("stays inside the canvas for a mask that reaches the picture's edges", () => {
    const canvas = { width: 1425, height: 891 };
    expect(boxOnCanvas({ x: 0, y: 63, width: 600, height: 312 }, mask, canvas)).toEqual({
      x: 0,
      y: Math.floor((62 * 891) / 375),
      width: 1425,
      height: 891 - Math.floor((62 * 891) / 375),
    });
  });

  it("covers every canvas pixel the mask's box touches, at any canvas size", () => {
    for (const width of [320, 975, 1425, 1872, 1920]) {
      const canvas = { width, height: Math.round(width * 0.625) };
      const box = boxOnCanvas({ x: 153, y: 240, width: 151, height: 120 }, mask, canvas);
      expect(box.x).toBeLessThanOrEqual((153 * width) / 600);
      expect(box.x + box.width).toBeGreaterThanOrEqual(Math.min(width, (304 * width) / 600));
      expect(Number.isInteger(box.x) && Number.isInteger(box.width)).toBe(true);
    }
  });

  it("grows a box by a margin, inside the canvas", () => {
    const canvas = { width: 100, height: 60 };
    expect(grown({ x: 10, y: 10, width: 20, height: 20 }, 5, canvas)).toEqual({ x: 5, y: 5, width: 30, height: 30 });
    expect(grown({ x: 2, y: 50, width: 97, height: 10 }, 5, canvas)).toEqual({ x: 0, y: 45, width: 100, height: 15 });
  });
});

describe("the added light's brightness", () => {
  it("multiplies every colour, stops at white, and leaves alpha as it is", () => {
    const data = picture(2, 1, { "0,0": [100, 200, 0, 128], "1,0": [10, 190, 255, 255] });
    brighten(data, 1.35);
    expect(pixel(data, 2, 0, 0)).toEqual([135, 255, 0, 128]);
    expect(pixel(data, 2, 1, 0)).toEqual([14, 255, 255, 255]);
  });
});

describe("the added light's blur", () => {
  it("weighs its neighbours by a bell curve that sums to one", () => {
    const weights = blurWeights(1.38);
    expect(weights.length).toBe(2 * Math.ceil(1.38 * 3) + 1);
    expect([...weights].reduce((a, b) => a + b, 0)).toBeCloseTo(1, 5);
    const middle = (weights.length - 1) / 2;
    expect(weights[middle]).toBeGreaterThan(weights[middle + 1]);
    expect(weights[middle - 2]).toBeCloseTo(weights[middle + 2], 7);
    // One deviation out is e to the minus one half of the middle.
    expect(blurWeights(1)[4] / blurWeights(1)[3]).toBeCloseTo(Math.exp(-0.5), 5);
  });

  it("spreads one bright pixel evenly to every side and keeps its light", () => {
    const size = 21;
    const data = picture(size, size);
    for (let n = 3; n < data.length; n += 4) data[n] = 255;
    data.set([255, 255, 255, 255], (10 * size + 10) * 4);
    blur(data, size, size, 1.5);
    const red = (x: number, y: number) => pixel(data, size, x, y)[0];
    expect(red(10, 10)).toBeLessThan(255);
    expect(red(10, 10)).toBeGreaterThan(red(11, 10));
    expect(red(11, 10)).toBeGreaterThan(red(12, 10));
    expect(red(9, 10)).toBe(red(11, 10));
    expect(red(10, 9)).toBe(red(10, 11));
    expect(red(10, 9)).toBe(red(11, 10));
    expect(red(12, 12)).toBe(red(8, 8));
    // Each written value is rounded to a whole level, so the sum is kept to within that rounding.
    let sum = 0;
    for (let n = 0; n < data.length; n += 4) sum += data[n];
    expect(Math.abs(sum - 255)).toBeLessThan(12);
    // The picture stays opaque away from its edges.
    expect(pixel(data, size, 10, 10)[3]).toBe(255);
  });

  it("leaves a flat picture flat, and fades it only at its own edges, where nothing lies beyond", () => {
    const size = 15;
    const data = picture(size, size);
    for (let n = 0; n < data.length; n += 4) data.set([200, 100, 50, 255], n);
    blur(data, size, size, 1);
    expect(pixel(data, size, 7, 7)).toEqual([200, 100, 50, 255]);
    const corner = pixel(data, size, 0, 0);
    expect(corner[3]).toBeLessThan(255);
    expect(corner[3]).toBeGreaterThan(40);
    // The colour of a faded pixel is still the picture's colour: it is the alpha that falls.
    expect(Math.abs(corner[0] - 200)).toBeLessThanOrEqual(2);
    expect(Math.abs(corner[1] - 100)).toBeLessThanOrEqual(2);
  });

  it("does not let a clear pixel's colour leak into its neighbours", () => {
    const data = picture(5, 1, { "1,0": [255, 0, 0, 0], "2,0": [0, 0, 255, 255], "3,0": [255, 0, 0, 0] });
    blur(data, 5, 1, 1);
    expect(pixel(data, 5, 2, 0)[0]).toBe(0);
    expect(pixel(data, 5, 1, 0).slice(0, 3)).toEqual([0, 0, 255]);
  });

  it("gives the same picture done a little at a time as done in one go, and hands back between bands", () => {
    const width = 37;
    const height = 150;
    const make = () => {
      const data = picture(width, height);
      for (let n = 0; n < data.length; n++) data[n] = n % 4 === 3 ? (n % 11 === 3 ? 90 : 255) : (n * 7919) % 256;
      return data;
    };
    const whole = make();
    blur(whole, width, height, 1.38);
    const stepped = make();
    let steps = 0;
    for (const _ of blurInSteps(stepped, width, height, 1.38)) steps++;
    expect([...stepped]).toEqual([...whole]);
    // 150 rows in bands of 64: three bands across, three down, and the copy in.
    expect(steps).toBe(7);
    expect([...make()]).not.toEqual([...whole]);
  });

  it("does nothing for a blur too small to see", () => {
    const data = picture(3, 3, { "1,1": [9, 8, 7, 255] });
    const before = [...data];
    blur(data, 3, 3, 0);
    blur(data, 3, 3, 0.04);
    expect([...data]).toEqual(before);
  });
});

describe("the drawing of one frame", () => {
  /** A brush that writes down each drawing with the strength and the blend it had at that moment. */
  function recorder() {
    const drawn: { source: unknown; alpha: number; blend: string; box: number[] }[] = [];
    const brush: Brush = {
      globalAlpha: 1,
      globalCompositeOperation: "source-over",
      drawImage(source, x, y, width, height) {
        drawn.push({
          source,
          alpha: this.globalAlpha,
          blend: this.globalCompositeOperation,
          box: [x, y, width, height],
        });
      },
    };
    return { brush, drawn };
  }
  const pieces = (name: Draw["image"]): Piece => ({
    source: name as unknown as CanvasImageSource,
    x: name === "dark" ? 0 : 10,
    y: name === "dark" ? 0 : 20,
    width: name === "dark" ? 1920 : 300,
    height: name === "dark" ? 1200 : 200,
  });
  const at = (id: string) => STEPS.findIndex((step) => step.id === id);

  it("draws every piece of the list in order, each where it belongs, at its strength and with its blend", () => {
    const list = drawList(levelsAt(tracksAt(layersAt(STEPS[at("s5-attempt")])), 0));
    const { brush, drawn } = recorder();
    paint(brush, pieces, list);
    expect(drawn.map((d) => d.source)).toEqual(list.map((d) => d.image));
    expect(drawn.map((d) => d.alpha)).toEqual(list.map((d) => d.alpha));
    expect(drawn.map((d) => d.blend)).toEqual(list.map((d) => d.blend));
    expect(drawn[0].box).toEqual([0, 0, 1920, 1200]);
    expect(drawn[1].box).toEqual([10, 20, 300, 200]);
    expect(drawn.filter((d) => d.blend === "screen").map((d) => d.source)).toEqual(["glow:security"]);
  });

  it("leaves the brush as it found it, so nothing drawn later is faint or added as light by mistake", () => {
    const { brush } = recorder();
    paint(brush, pieces, drawList(levelsAt(tracksAt(layersAt(STEPS[at("s5-attempt")])), 0)));
    expect(brush.globalAlpha).toBe(1);
    expect(brush.globalCompositeOperation).toBe("source-over");
  });

  it("draws a dark board with one drawing, and skips a piece the picture does not have", () => {
    const dark = recorder();
    paint(dark.brush, pieces, drawList(levelsAt(tracksAt(layersAt(STEPS[1])), 0)));
    expect(dark.drawn).toHaveLength(1);
    const partial = recorder();
    const list = drawList(levelsAt(tracksAt(layersAt(STEPS[at("s1-power-reset")])), 0));
    paint(partial.brush, (name) => (name.startsWith("glow:") ? null : pieces(name)), list);
    expect(partial.drawn.map((d) => d.source)).toEqual(["dark", "lit:power", "lit:processor"]);
  });

  it("draws the same frame twice the same way: a frame holds no memory of the one before", () => {
    const list = drawList(levelsAt(tracksAt(layersAt(STEPS[at("s7-exit-call")])), 0));
    const first = recorder();
    paint(first.brush, pieces, list);
    paint(first.brush, pieces, list);
    expect(first.drawn.slice(0, list.length)).toEqual(first.drawn.slice(list.length));
  });
});
