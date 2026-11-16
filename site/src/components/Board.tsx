// The board of one stage. In the scrolled story its picture is drawn on one canvas: the dark plate, each lit
// part's cut-out of the awake plate, the added light of the part the step is about. The canvas says in its
// attributes what the step lights, so the state is in the page as well as in the pixels. A step shown as a
// still (a still section, a frozen step) is drawn as layers instead, only the ones the step shows; so is
// the scrolled story where its canvas cannot be made or drawn, and there a step changes at once, not faded.
import { useRef, type CSSProperties } from "react";
import { PARTS } from "../content/types";
import type { Layers, PartLayer } from "../model/scene";
import { lightSummary, type LightName } from "../stage/light";
import { DARK, MASK_OF } from "../stage/plates";
import { useBoardLight } from "../stage/useBoardLight";

interface BoardProps {
  layers: Layers;
  /** Where the board looks on a narrow stage: its focus and its span, as custom properties. */
  frame: CSSProperties;
  /** Whether light spreads from one step to the next (the scrolled story), or the step is a still. */
  animate: boolean;
}

export function Board({ layers, frame, animate }: BoardProps) {
  return animate ? <CanvasBoard layers={layers} frame={frame} /> : <StillBoard layers={layers} frame={frame} />;
}

/** A still: nothing fades, so the few layers the step shows are the whole picture and no canvas is made. */
function StillBoard({ layers, frame }: Omit<BoardProps, "animate">) {
  return (
    <div className="board" data-on={layers.board} style={frame} data-light="layers">
      <img src={DARK} alt="" width={1920} height={1200} />
      <BoardLayers layers={layers} />
    </div>
  );
}

function CanvasBoard({ layers, frame }: Omit<BoardProps, "animate">) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const light = useBoardLight(canvas, layers);
  const { lit, rest, strong, whole } = lightSummary(layers);
  return (
    <div className="board" data-on={layers.board} style={frame} data-light={light}>
      <img src={DARK} alt="" width={1920} height={1200} />
      {light === "failed" ? (
        <BoardLayers layers={layers} />
      ) : (
        <canvas
          ref={canvas}
          aria-hidden="true"
          data-lit={lit}
          data-rest={rest}
          data-strong={strong}
          data-whole={whole}
        />
      )}
    </div>
  );
}

/**
 * The board's lights as layers: over the dark plate, one copy of the awake plate per lit part, cut out by
 * the part's mask, and a second copy over the part the step is about. Only what the step shows is in the
 * page.
 */
export function BoardLayers({ layers }: { layers: Layers }) {
  return (
    <>
      {PARTS.map((part) => (
        <Light key={part} name={part} layer={layers.parts[part]} />
      ))}
      <Light name="whole" layer={layers.whole} />
    </>
  );
}

function Light({ name, layer }: { name: LightName; layer: PartLayer }) {
  const style = {
    maskImage: `url("${MASK_OF[name]}")`,
    WebkitMaskImage: `url("${MASK_OF[name]}")`,
  } as CSSProperties;
  return (
    <>
      {layer.on && <div className="lit" data-part={name} data-rest={layer.rest} style={style} />}
      {layer.strong && <div className="glow" data-part={name} style={style} />}
    </>
  );
}
