// After the story: the seven stops in a row, each as a small picture of the board with the parts lit that
// the boot has reached by the end of that stop, and its name. Each leads back to its stop. A small picture
// of the whole board looks the same at every stop, so each one is drawn close on the parts its stop is
// about; the last, where every part is lit, shows the whole board.
import { STOPS, headline } from "../content/load";
import { PARTS, type Part, type Stop } from "../content/types";
import { firstStepOf, tileFrame } from "../model/scene";
import { DARK as boardDark, MASKS, WHOLE_MASK } from "../stage/plates";

/** The parts lit when a stop ends: its last screen's, since light never goes out along the story. */
export function litAtEndOf(stop: Stop): readonly Part[] {
  return stop.screens.at(-1)?.picture.lit ?? [];
}

/**
 * The parts a stop is about: the ones that light during it, or, where none does, the ones its headline
 * screen draws attention to.
 */
export function partsOf(stop: Stop): readonly Part[] {
  const before = STOPS.find((s) => s.number === stop.number - 1);
  const already = before ? litAtEndOf(before) : [];
  const fresh = litAtEndOf(stop).filter((part) => !already.includes(part));
  return fresh.length > 0 ? fresh : (headline(stop).picture.attention ?? []);
}

/** The frame of a small board: twice as wide as it is tall. */
const TILE_SHAPE = 2;

const mask = (name: string) => ({ maskImage: `url("${name}")`, WebkitMaskImage: `url("${name}")` });

export function Overview() {
  return (
    <section className="overview" id="overview" aria-labelledby="overview-title">
      <h2 id="overview-title" className="overview-title">
        The boot in seven stops
      </h2>
      <ol className="overview-strip">
        {STOPS.map((stop) => {
          const lit = litAtEndOf(stop);
          const all = PARTS.every((part) => lit.includes(part));
          const frame = tileFrame(partsOf(stop), TILE_SHAPE, all);
          const place = { width: `${frame.zoom * 100}%`, left: `${frame.left}%`, top: `${frame.top}%` };
          return (
            <li key={stop.id}>
              <a href={`#step-${firstStepOf(stop.number)}`} title={headline(stop).statement.text}>
                <span className="overview-board" aria-hidden="true">
                  <span className="overview-plate" style={place}>
                    <img src={boardDark} alt="" width={1920} height={1200} loading="lazy" decoding="async" />
                    {lit.map((part) => (
                      <span key={part} className="overview-lit" style={mask(MASKS[part])} />
                    ))}
                    {all && <span className="overview-lit" style={mask(WHOLE_MASK)} />}
                  </span>
                </span>
                <span className="overview-count">
                  {stop.number} of {stop.of}
                </span>
                <span className="overview-name">{stop.label}</span>
              </a>
            </li>
          );
        })}
      </ol>
    </section>
  );
}
