// The experiments page: the first screen with the state of the score, the two-run screen, the cards of the
// other experiments, and what the specification leaves open. The words come from the content. What has been
// run, compared and scored comes from the files on disk, so a card says "not yet run" until a recording
// exists. The question and the measure are behind the first screen's "Open the evidence".
import laptopAwake from "../assets/laptop-awake.webp";
import laptopInside from "../assets/laptop-inside.webp";
import { FILES } from "../content/files";
import { EXPERIMENT_SCREENS, PICTURE_NOTE, basisLabel, claimNumbers, claimSource, subjectId } from "../content/load";
import type { Card, PageScreen, Side } from "../content/types";
import {
  cardStates,
  furthest,
  onFile,
  registersDiffering,
  totals,
  type ExperimentState,
  type ExperimentStatus,
  type Files,
} from "../model/experiments";
import { sectionId } from "../model/route";
import { listed } from "./Comparison";
import { Emphasised, EvidencePill, type OpenEvidence } from "./Stage";
import { markerId, openerId } from "./panel";

interface PageProps {
  onOpen: OpenEvidence;
  /** The files that say what has been run. The ones on disk, unless a test hands in others. */
  files?: Files;
}

export function Experiments({ onOpen, files = FILES }: PageProps) {
  return (
    <div className="page page-experiments">
      {EXPERIMENT_SCREENS.map((screen) => (
        <section key={screen.id} className="page-screen" id={sectionId(screen.id)} data-kind={screen.kind}>
          <Head screen={screen} onOpen={onOpen} first={screen.kind === "intro"} />
          {screen.kind === "intro" && <Measure screen={screen} files={files} />}
          {screen.kind === "side-by-side" && <Sides screen={screen} />}
          {screen.kind === "cards" && (
            <ul className="cards">
              {(screen.cards ?? []).map((card) => (
                <ExperimentCard key={card.id} screen={screen} card={card} files={files} onOpen={onOpen} />
              ))}
            </ul>
          )}
          {screen.kind === "list" && <OpenItems screen={screen} />}
          <Foot screen={screen} onOpen={onOpen} files={files} />
          {screen.kind === "side-by-side" && <p className="page-note">{PICTURE_NOTE}</p>}
        </section>
      ))}
    </div>
  );
}

/** The top of a screen: its eyebrow, its statement with the citation marker, and its one supporting sentence. */
export function Head({ screen, onOpen, first = false }: { screen: PageScreen; onOpen: OpenEvidence; first?: boolean }) {
  const numbers = claimNumbers(screen.id);
  const Statement = first ? "h1" : "h2";
  return (
    <header className="page-head">
      {(screen.eyebrow ?? screen.title) && <p className="eyebrow">{screen.eyebrow ?? screen.title}</p>}
      {/* A page's first heading can take focus, so a change of page is read out from its top. */}
      <Statement className="statement" tabIndex={first ? -1 : undefined}>
        <Emphasised statement={screen.statement} />
        <button
          type="button"
          className="cite"
          id={markerId(screen.id)}
          aria-label={`Claims ${numbers.first} to ${numbers.last}: where this comes from`}
          onClick={() => onOpen(screen.id, markerId(screen.id), true)}
        >
          {numbers.first}
        </button>
      </Statement>
      {screen.status ? (
        <p className="aside aside-pilot">{screen.status.text}</p>
      ) : (
        screen.support && <p className="aside">{screen.support}</p>
      )}
    </header>
  );
}

/** What kind of run a line comes from, said after the run's name where it is not the normal run. */
const RUN_KINDS: Record<string, string> = { pilot: "a pilot, shown and not counted", counted: "a counted run" };

/**
 * The foot of a screen: its one evidence line, where it has one of its own, with the run it was recorded in
 * named over it, and the control behind it.
 */
export function Foot({ screen, onOpen, files = FILES }: { screen: PageScreen; onOpen: OpenEvidence; files?: Files }) {
  const { evidence } = screen;
  const run = evidence?.recorded ? evidence.run : null;
  const kind = RUN_KINDS[files.runs.find((r) => r.name === run)?.kind ?? ""];
  return (
    <div className="page-foot">
      {evidence && (
        <div className="page-line">
          {run && (
            <p className="page-run">
              Run {run}
              {kind && `, ${kind}`}
            </p>
          )}
          <EvidencePill evidence={evidence} mark />
        </div>
      )}
      <button
        type="button"
        className="open-evidence"
        id={openerId(screen.id)}
        aria-label={`Open the evidence: ${screen.statement.text}`}
        onClick={() => onOpen(screen.id, openerId(screen.id), false)}
      >
        Open the evidence
      </button>
    </div>
  );
}

/**
 * The score, the one thing the first screen shows beside its statement. It is read from the files: the two
 * numbers once a score is on file; a count of what is on file once a prediction or a counted run is; and
 * until then the content's own sentence, which says that there is nothing yet.
 */
function Measure({ screen, files }: { screen: PageScreen; files: Files }) {
  const sum = totals(files.scores);
  const counted = files.runs.filter((run) => run.kind === "counted").length;
  return (
    <div className="measure">
      <div>
        {sum ? (
          <dl className="score" data-claimed="true">
            <div>
              <dt>Specification-required behaviours met</dt>
              <dd>
                {sum.requiredMet} of {sum.requiredTotal}
              </dd>
            </div>
            <div>
              <dt>Open behaviours predicted correctly</dt>
              <dd>
                {sum.openCorrect} of {sum.openTotal}
              </dd>
            </div>
            <div>
              <dt>Counted experiments scored</dt>
              <dd>{sum.experiments}</dd>
            </div>
          </dl>
        ) : files.predictions.length + counted > 0 ? (
          <dl className="score" data-claimed="false">
            <div>
              <dt>Predictions on file</dt>
              <dd>{files.predictions.length}</dd>
            </div>
            <div>
              <dt>Counted runs recorded</dt>
              <dd>{counted}</dd>
            </div>
            <div>
              <dt>Scored</dt>
              <dd>0</dd>
            </div>
          </dl>
        ) : (
          screen.score && (
            <p className="score" data-claimed="false">
              {screen.score.text}
            </p>
          )
        )}
      </div>
    </div>
  );
}

/** The picture of a side: a run that was accepted ends with the screen lit, any other with the screen black. */
const pictureOf = (side: Side) =>
  side.outcome === "accepted"
    ? { src: laptopAwake, label: "Illustration: a laptop, its screen lit with a dawn sky." }
    : { src: laptopInside, label: "Illustration: a laptop, its inside awake, its screen dark." };

/** Two runs side by side: a picture, one statement and one line from the recording for each. */
function Sides({ screen }: { screen: PageScreen }) {
  return (
    <div className="sides">
      {(screen.sides ?? []).map((side) => {
        const picture = pictureOf(side);
        return (
          <div key={side.id} className="side" data-outcome={side.outcome}>
            <img src={picture.src} alt={picture.label} width={1280} height={960} />
            <h3 className="side-statement">
              <Emphasised statement={side.statement} />
            </h3>
            <EvidencePill evidence={side.evidence} mark />
          </div>
        );
      })}
    </div>
  );
}

/** What the page calls each state of an experiment. */
export const STATUS_NAMES: Record<ExperimentStatus, string> = {
  "not-run": "Not yet run",
  pilot: "Pilot",
  recorded: "Recorded, not yet scored",
  scored: "Scored",
};

/** A line of a file as a sentence of the page: its first letter a capital, a full stop at its end. */
const sentence = (text: string) => (text ? `${text[0].toUpperCase()}${text.slice(1).replace(/\.$/, "")}.` : "");

/** What the files hold for one form of an experiment, as rows of a card. */
function Result({ state, named }: { state: ExperimentState; named: boolean }) {
  const comparison = state.comparison?.file;
  const differing = comparison ? registersDiffering(comparison) : [];
  return (
    <>
      {named && (
        <p className="card-form">
          {/* The form in words, as its prediction or its recording says it; its name in the files beside it. */}
          {(state.prediction?.change ?? state.run?.change) && (
            <span className="card-form-change">{sentence(state.prediction?.change ?? state.run?.change ?? "")}</span>
          )}
          <span className="card-form-name">{state.experiment}</span>
        </p>
      )}
      <dl className="card-result">
        {state.prediction && (
          <div>
            <dt>Prediction on file</dt>
            <dd>
              {state.prediction.rows.length} {state.prediction.rows.length === 1 ? "row" : "rows"}
            </dd>
          </div>
        )}
        {state.run ? (
          <div>
            <dt>Run {state.run.name}</dt>
            <dd data-outcome={state.run.outcome}>{state.run.outcome}</dd>
          </div>
        ) : (
          <div>
            <dt>Run</dt>
            <dd>{STATUS_NAMES["not-run"].toLowerCase()}</dd>
          </div>
        )}
        {comparison && (
          <div>
            <dt>Registers that differ from run {comparison.baseline.run}</dt>
            <dd>{differing.length > 0 ? listed(differing) : "none"}</dd>
          </div>
        )}
        {comparison?.first_differing_event && (
          <div>
            <dt>First record that differs</dt>
            <dd>
              record {comparison.first_differing_event.index}, at stop {comparison.first_differing_event.stop}
            </dd>
          </div>
        )}
        {state.score && (
          <>
            <div>
              <dt>Specification-required rows met</dt>
              <dd>
                {state.score.required_met} of {state.score.required_total}
              </dd>
            </div>
            <div>
              <dt>Open rows predicted correctly</dt>
              <dd>
                {state.score.open_correct} of {state.score.open_total}
              </dd>
            </div>
          </>
        )}
      </dl>
    </>
  );
}

/** One experiment: what it changes, in the content's words, and what the files on disk hold for it. */
function ExperimentCard({
  screen,
  card,
  files,
  onOpen,
}: {
  screen: PageScreen;
  card: Card;
  files: Files;
  onOpen: OpenEvidence;
}) {
  const states = cardStates(card.id, files).filter(onFile);
  const status = furthest(states);
  const id = subjectId(screen.id, card.id);
  return (
    <li className="card" data-status={status} data-counted={card.counted}>
      <p className="card-top">
        <span className="card-label">{card.label}</span>
        <span className="card-status">{STATUS_NAMES[status]}</span>
      </p>
      <h3 className="card-title">{card.title}</h3>
      {card.change && <p className="card-change">{card.change}</p>}
      {states.length === 0 && <p className="card-absent">{card.status}</p>}
      {states.map((state) => (
        <Result key={state.experiment} state={state} named={states.length > 1 || state.experiment !== card.id} />
      ))}
      {(states.length > 0 || card.claims.length > 0) && (
        <button
          type="button"
          className="open-evidence"
          id={openerId(id)}
          onClick={() => onOpen(id, openerId(id), false)}
        >
          Open the evidence<span className="sr-only">: {card.title}</span>
        </button>
      )}
    </li>
  );
}

/** The behaviours the specification leaves open: each with the label of its basis and the place it is cited to. */
function OpenItems({ screen }: { screen: PageScreen }) {
  return (
    <ul className="open-items">
      {(screen.items ?? []).map((item) => (
        <li key={item.id}>
          {item.claims[0] && (
            <p className="claim-basis" data-basis={item.claims[0].basis}>
              {basisLabel(item.claims[0].basis).label}
            </p>
          )}
          <h3 className="card-title">{item.title}</h3>
          <p className="card-change">{item.text}</p>
          {item.note && <p className="card-note">{item.note}</p>}
          {item.claims[0] && <p className="claim-source">{claimSource(item.claims[0])}</p>}
        </li>
      ))}
    </ul>
  );
}
