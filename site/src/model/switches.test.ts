// The ?static and ?step switches, and the mode they choose.
import { describe, expect, it } from "vitest";
import { modeFor, readSwitches } from "./switches";

describe("readSwitches", () => {
  it("reads nothing from a plain address", () => {
    expect(readSwitches("", 3)).toEqual({ still: false, step: null, evidence: false });
  });
  it("reads ?static, with or without a value", () => {
    expect(readSwitches("?static", 3).still).toBe(true);
    expect(readSwitches("?static=1&x=2", 3).still).toBe(true);
  });
  it("reads ?step=N for every step of the scene", () => {
    expect([0, 1, 2].map((n) => readSwitches(`?step=${n}`, 3).step)).toEqual([0, 1, 2]);
  });
  it.each(["?step=3", "?step=-1", "?step=1.5", "?step=", "?step=two", "?step"])("refuses %s", (search) => {
    expect(readSwitches(search, 3).step).toBeNull();
  });
  it("opens the evidence only on a frozen step", () => {
    expect(readSwitches("?step=2&evidence", 3).evidence).toBe(true);
    expect(readSwitches("?evidence", 3).evidence).toBe(false);
    expect(readSwitches("?step=9&evidence", 3).evidence).toBe(false);
  });
});

describe("modeFor", () => {
  const plain = readSwitches("", 3);
  it("scrolls by default", () => {
    expect(modeFor(plain, false)).toEqual({ kind: "scroll" });
  });
  it("is still for ?static and for reduced motion", () => {
    expect(modeFor(readSwitches("?static", 3), false)).toEqual({ kind: "still" });
    expect(modeFor(plain, true)).toEqual({ kind: "still" });
  });
  it("freezes at a step, whatever else is asked", () => {
    expect(modeFor(readSwitches("?step=1", 3), false)).toEqual({ kind: "frozen", step: 1, evidence: false });
    expect(modeFor(readSwitches("?step=2&static", 3), true)).toEqual({ kind: "frozen", step: 2, evidence: false });
  });
  it("ignores a step the scene does not have", () => {
    expect(modeFor(readSwitches("?step=7", 3), false)).toEqual({ kind: "scroll" });
  });
});
