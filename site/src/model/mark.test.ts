// The mark's geometry, and the favicon drawn from it.
import { describe, expect, it } from "vitest";
import favicon from "../../public/favicon.svg?raw";
import { MARK, MARK_OPEN, lensPath } from "./mark";

describe("the mark", () => {
  it("is a closed line when the lens is shut", () => {
    expect(lensPath(0)).toBe("M4 12Q12 12 20 12Q12 12 4 12Z");
  });
  it("opens evenly above and below the disc's middle line", () => {
    const [, up, down] = lensPath(0.5)
      .match(/Q12 ([\d.]+) 20 12Q12 ([\d.]+)/)!
      .map(Number);
    expect(MARK.centre - up).toBeCloseTo(down - MARK.centre);
    expect(up).toBeLessThan(MARK.centre);
  });
  it("keeps the lens inside the disc", () => {
    expect(MARK.halfWidth).toBeLessThan(MARK.disc);
    // A quadratic curve reaches half way to its control point.
    expect((MARK_OPEN * 11) / 2).toBeLessThan(MARK.disc);
  });
  it("clamps how far the lens opens", () => {
    expect(lensPath(5)).toBe(lensPath(1));
    expect(lensPath(-1)).toBe(lensPath(0));
  });
  it("is the lens the favicon draws", () => {
    expect(favicon).toContain(`d="${lensPath(MARK_OPEN)}"`);
    expect(favicon).toContain(`fill="${MARK.light}"`);
    expect(favicon).toContain(`fill="${MARK.discFill}"`);
  });
});
