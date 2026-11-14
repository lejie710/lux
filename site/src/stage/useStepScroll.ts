// The pinned scene's scroll steps: one invisible marker per step crosses the viewport, and the step whose
// marker is at the viewport's middle is the current one. Each step holds a complete state, so fast or
// reverse scrolling lands correctly.
import { useEffect, useRef, useState } from "react";

export function useStepScroll() {
  const [i, setI] = useState(0);
  const markers = useRef<(HTMLDivElement | null)[]>([]);

  useEffect(() => {
    let io: IntersectionObserver | undefined;
    const observe = () => {
      io?.disconnect();
      // IntersectionObserver percentage margins use the root's width, even
      // vertically. Pixels keep the activation band at the viewport midpoint.
      const middle = Math.floor(window.innerHeight / 2);
      io = new IntersectionObserver(
        (entries) => {
          for (const entry of entries) {
            if (entry.isIntersecting) setI(Number((entry.target as HTMLElement).dataset.index));
          }
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

  return { i, markers };
}
