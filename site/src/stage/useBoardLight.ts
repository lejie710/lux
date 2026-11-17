// The board's canvas as a hook: it starts the drawing when the canvas is on the page, passes each step
// change on, and reports whether the picture is drawn, still on its way, or cannot be drawn at all.
import { useEffect, useRef, useState, type RefObject } from "react";
import type { Layers } from "../model/scene";
import { runBoardLight, type BoardLight, type LightStatus } from "./boardLight";
import { lightKey } from "./light";

export function useBoardLight(canvas: RefObject<HTMLCanvasElement | null>, layers: Layers): LightStatus {
  const [status, setStatus] = useState<LightStatus>("pending");
  const latest = useRef(layers);
  latest.current = layers;
  const light = useRef<BoardLight | null>(null);

  useEffect(() => {
    if (!canvas.current) return;
    const running = runBoardLight(canvas.current, latest.current, setStatus);
    light.current = running;
    return () => {
      running.stop();
      light.current = null;
    };
  }, [canvas]);

  // A render that changes no light changes nothing here: only a new state of the lights is a step change.
  const key = lightKey(layers);
  useEffect(() => {
    light.current?.step(latest.current);
  }, [key]);

  return status;
}
