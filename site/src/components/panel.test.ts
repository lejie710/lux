// The evidence panel's behaviour: opening, closing, where focus returns, and the keys.
import { describe, expect, it } from "vitest";
import { CLOSED, closePanel, markerId, openPanel, openerId, panelKey } from "./panel";

describe("opening and closing", () => {
  it("starts closed", () => {
    expect(CLOSED.screenId).toBeNull();
  });
  it("opens on a screen and remembers the control that opened it", () => {
    expect(openPanel("s1-power-reset", "evidence-open-s1-power-reset")).toEqual({
      screenId: "s1-power-reset",
      openerId: "evidence-open-s1-power-reset",
      atClaims: false,
    });
  });
  it("opens at the claims when a citation marker asks", () => {
    expect(openPanel("s1-power-reset", markerId("s1-power-reset"), true).atClaims).toBe(true);
  });
  it("closes, and returns focus to the control that opened it", () => {
    const { state, focusId } = closePanel(openPanel("s1-power-reset", openerId("s1-power-reset")));
    expect(state).toEqual(CLOSED);
    expect(focusId).toBe("evidence-open-s1-power-reset");
  });
  it("gives the two controls of a step different ids", () => {
    expect(openerId("a")).not.toBe(markerId("a"));
  });
});

describe("keys inside the panel", () => {
  it("closes on Escape, wherever focus is", () => {
    expect(panelKey({ key: "Escape" }, 0, 4)).toEqual({ action: "close" });
    expect(panelKey({ key: "Escape" }, -1, 0)).toEqual({ action: "close" });
  });
  it("wraps Tab from the last control to the first", () => {
    expect(panelKey({ key: "Tab" }, 3, 4)).toEqual({ action: "focus", index: 0 });
  });
  it("wraps Shift and Tab from the first control to the last", () => {
    expect(panelKey({ key: "Tab", shiftKey: true }, 0, 4)).toEqual({ action: "focus", index: 3 });
  });
  it("brings focus in when it sits on the panel itself", () => {
    expect(panelKey({ key: "Tab" }, -1, 4)).toEqual({ action: "focus", index: 0 });
    expect(panelKey({ key: "Tab", shiftKey: true }, -1, 4)).toEqual({ action: "focus", index: 3 });
  });
  it("lets Tab go on from a heading inside the panel, to the control that follows it", () => {
    // A citation marker opens the panel at its list of claims and puts focus on that list's heading.
    expect(panelKey({ key: "Tab" }, -1, 4, true)).toBeNull();
    expect(panelKey({ key: "Tab", shiftKey: true }, -1, 4, true)).toBeNull();
    expect(panelKey({ key: "Escape" }, -1, 4, true)).toEqual({ action: "close" });
  });
  it("leaves Tab to the browser between controls", () => {
    expect(panelKey({ key: "Tab" }, 1, 4)).toBeNull();
    expect(panelKey({ key: "Tab", shiftKey: true }, 2, 4)).toBeNull();
  });
  it("leaves every other key alone", () => {
    expect(panelKey({ key: "Enter" }, 0, 4)).toBeNull();
    expect(panelKey({ key: "ArrowDown" }, 0, 4)).toBeNull();
  });
});
