// After the story: the seven stops in a row, each as a small picture of the board with the parts lit that
// the boot has reached by the end of that stop, and its name. Each leads back to its stop.
import boardDark from "../assets/board-dark.webp";
import { STOPS, headline } from "../content/load";
import { PARTS, type Part, type Stop } from "../content/types";
import { firstStepOf } from "../model/scene";
import { MASKS, WHOLE_MASK } from "./Stage";

/** The parts lit when a stop ends: its last screen's, since light never goes out along the story. */
export function litAtEndOf(stop: Stop): readonly Part[] {
  return stop.screens.at(-1)?.picture.lit ?? [];
}

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
          return (
            <li key={stop.id}>
              <a href={`#step-${firstStepOf(stop.number)}`} title={headline(stop).statement.text}>
                <span className="overview-board" aria-hidden="true">
                  <span className="overview-plate">
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
