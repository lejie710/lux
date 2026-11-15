// The pinned scene's scroll steps: one invisible marker per step crosses the viewport, and the step whose
// marker is at the viewport's middle is the current one. Each step holds a complete state, so fast or
// reverse scrolling lands correctly.
import { useCallback, useEffect, useRef, useState } from "react";
import { stepKey, stepShown } from "../model/scene";

/** Controls that use Space themselves: a press on one of them is theirs, not a step. */
const CONTROLS = "a[href], button, input, select, textarea, summary, [tabindex='0']";

export function useStepScroll() {
  const [i, setI] = useState(0);
  const markers = useRef<(HTMLDivElement | null)[]>([]);
  const at = useRef(0);
  at.current = i;

  /** Go to a step: its marker is put at the middle of the window, at once. The first step is the top. */
  const go = useCallback((to: number) => {
    if (to <= 0) window.scrollTo({ top: 0, behavior: "instant" });
    else markers.current[to]?.scrollIntoView({ block: "center", behavior: "instant" });
  }, []);

  // One press of Space or Page Down is one step, and Shift with Space or Page Up one step back, while the
  // stage is pinned. A window's own paging is longer than a short stretch of the track and would skip a screen.
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.defaultPrevented || e.altKey || e.ctrlKey || e.metaKey) return;
      if (document.documentElement.classList.contains("panel-open")) return;
      const target = e.target as HTMLElement | null;
      if (e.key === " " && target?.closest?.(CONTROLS)) return;
      const scene = markers.current[0]?.closest(".scene")?.getBoundingClientRect();
      if (!scene || scene.top > 1 || scene.bottom < window.innerHeight - 1) return;
      const to = stepKey(e, at.current, markers.current.length);
      if (to === null) return;
      e.preventDefault();
      go(to);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [go]);

  useEffect(() => {
    let io: IntersectionObserver | undefined;
    const observe = () => {
      io?.disconnect();
      // IntersectionObserver percentage margins use the root's width, even
      // vertically. Pixels keep the activation band at the viewport midpoint.
      const middle = Math.floor(window.innerHeight / 2);
      io = new IntersectionObserver(
        (entries) => {
          const onLine = entries
            .filter((entry) => entry.isIntersecting)
            .map((entry) => Number((entry.target as HTMLElement).dataset.index));
          // With no marker on the middle line the page is below the story: opened at the strip of stops,
          // or carried to its foot in one jump by the End key, which can pass the last markers between two
          // observations. The stage's last visible rows then belong to the last step, not to the step the
          // jump left behind.
          const tops = () => markers.current.map((marker) => marker?.getBoundingClientRect().top ?? Infinity);
          const shown = stepShown(onLine, tops, middle);
          if (shown !== null) setI(shown);
        },
        { rootMargin: `-${middle}px 0px -${Math.max(0, window.innerHeight - middle - 1)}px 0px` },
      );
      markers.current.forEach((marker) => marker && io?.observe(marker));
    };
    observe();
    // An address that ends in #step-N lands on that step: its marker is put at the middle of the window.
    const linked = /^#step-(\d+)$/.exec(window.location.hash);
    markers.current[Number(linked?.[1] ?? -1)]?.scrollIntoView({ block: "center", behavior: "instant" });
    window.addEventListener("resize", observe);
    return () => {
      io?.disconnect();
      window.removeEventListener("resize", observe);
    };
  }, []);

  return { i, markers, go };
}
