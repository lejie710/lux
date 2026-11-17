// One stage: the picture, and the words of its step over it. In the scrolled story the laptops and the board
// are always in the stage and the current step sets which is seen; the board's lights are drawn on one
// canvas, and the words in the page are those of the step in view and, while they fade, of the step just
// left. A stage shown alone (a still section, or a frozen step) carries only its own step's words and only
// the pictures its step shows: nothing fades there, so nothing unseen needs to be drawn.
import { Fragment, useRef, type CSSProperties } from "react";
import laptopAwake from "../assets/laptop-awake.webp";
import laptopDark from "../assets/laptop-dark.webp";
import laptopInside from "../assets/laptop-inside.webp";
import { PICTURE_NOTE, claimNumbers, define, recordedEvent } from "../content/load";
import type { Evidence, OpeningScreen, Statement } from "../content/types";
import {
  STEPS,
  firstStepOf,
  focusAt,
  layersAt,
  pictureLabel,
  spanAt,
  splitEmphasis,
  type SceneStep,
} from "../model/scene";
import { useWords } from "../stage/words";
import { Board } from "./Board";
import { Mark } from "./Mark";
import { markerId, openerId } from "./panel";

/** Opens the evidence of a screen. `atClaims` asks for its list of claims, as a citation marker does. */
export type OpenEvidence = (screenId: string, openerId: string, atClaims: boolean) => void;

interface StageProps {
  /** The step the stage shows. */
  current: number;
  /** Alone on the page: a still. Only this step's words and pictures are rendered, and nothing fades. */
  solo?: boolean;
  /** Whether the page has a place for each step that a mark of the rail can lead to. */
  anchors?: boolean;
  onOpen: OpenEvidence;
  /** Where the reader can step through the story: called with the step to go to. */
  onStep?: (to: number) => void;
}

export function Stage({ current, solo = false, anchors = true, onOpen, onStep }: StageProps) {
  const step = STEPS[current];
  const layers = layersAt(step);
  // A stage that cross-fades keeps both laptops and the board; one shown alone draws only what its step shows.
  const drawn = (shown: boolean) => shown || !solo;
  // The words in the page: this step's alone on a still, and in the scrolled story also those just left.
  const stage = useRef<HTMLDivElement>(null);
  const words = useWords(current, stage);
  const kept = solo ? [current] : words.kept;
  const on = solo ? current : words.on;
  // A screen with a supporting line under its statement leaves the laptop of the ending less room.
  const low = Boolean(step.screen.pilot_label || step.screen.handover);
  const frame = { "--focus": focusAt(current), "--span": Math.max(spanAt(current), 0.01) } as CSSProperties;
  return (
    <div className="stage" data-step={step.id} ref={stage}>
      <div className="picture" role="img" aria-label={pictureLabel(step)}>
        {drawn(layers.laptop) && (
          <img className="laptop" src={laptopDark} alt="" width={1280} height={960} data-on={layers.laptop} />
        )}
        {drawn(layers.board) && <Board layers={layers} frame={frame} animate={!solo} />}
        {/* The laptop of the ending: its inside awake, and over that the same laptop with its screen lit. As
            the screen lights, the stylesheet turns down the light under the keys. */}
        {drawn(layers.ending) && (
          <div className="ending" data-on={layers.ending} data-low={low} data-dawn={layers.screenLit}>
            <img src={laptopInside} alt="" width={1280} height={960} />
            {drawn(layers.screenLit) && (
              <img className="dawn" src={laptopAwake} alt="" width={1280} height={960} data-on={layers.screenLit} />
            )}
          </div>
        )}
      </div>
      {kept.map((n) => (
        <Words key={STEPS[n].id} step={STEPS[n]} on={n === on} anchors={anchors} onOpen={onOpen} />
      ))}
      {onStep && (
        <p className="step-nav">
          <button type="button" disabled={current === 0} onClick={() => onStep(current - 1)}>
            Previous step
          </button>
          <button type="button" disabled={current === STEPS.length - 1} onClick={() => onStep(current + 1)}>
            Next step
          </button>
        </p>
      )}
      <p className="picture-note">{step.screen.picture_caption ?? PICTURE_NOTE}</p>
    </div>
  );
}

/** The words of one step. While another step is current they are faded out and out of reach. */
function Words({
  step,
  on,
  anchors,
  onOpen,
}: {
  step: SceneStep;
  on: boolean;
  anchors: boolean;
  onOpen: OpenEvidence;
}) {
  const { screen, stop } = step;
  if (step.kind === "opening") {
    const opening = screen as OpeningScreen;
    return (
      <div className="words words-opening" data-on={on} inert={!on}>
        <div className="title-block">
          <p className="title-eyebrow">{opening.eyebrow}</p>
          <h1 className="title" tabIndex={-1}>
            <Emphasised statement={opening.title} />
          </h1>
          <p className="subtitle">{opening.statement.text}</p>
        </div>
        <p className="invite">
          <Mark size={30} />
          <span>
            <strong>{opening.invitation.label}</strong>
            <span>{opening.invitation.line}</span>
          </span>
        </p>
      </div>
    );
  }

  // The step between the opening and stop 1 has no statement of its own: it carries the opening's supporting
  // sentence, at supporting size, and no evidence line. The first evidence line belongs to a stop.
  const statement: Statement = stop ? screen.statement : { text: screen.support ?? "", emphasis: null };
  const numbers = claimNumbers(screen.id);
  return (
    <div className="words words-stop" data-kind={step.kind} data-view={step.view} data-on={on} inert={!on}>
      <div className="head">
        {stop && (
          <p className="eyebrow">
            {stop.number} of {stop.of} <span aria-hidden="true">·</span> {stop.label}
            {screen.thread && (
              <>
                {" "}
                <span aria-hidden="true">·</span>{" "}
                <span className="thread">{define({ glossary: screen.thread }).term}</span>
              </>
            )}
          </p>
        )}
        <h2 className={stop ? "statement" : "statement statement-support"}>
          <Emphasised statement={statement} />
          <button
            type="button"
            className="cite"
            id={markerId(step.id)}
            aria-label={`Claims ${numbers.first} to ${numbers.last}: where this comes from`}
            onClick={() => onOpen(screen.id, markerId(step.id), true)}
          >
            {numbers.first}
          </button>
        </h2>
        {/* The one supporting line a screen may carry: a pilot's label, or the way on from the last screen. */}
        {screen.pilot_label && <p className="aside aside-pilot">{screen.pilot_label}</p>}
        {/* The way on is a link once the content holds its address. Until then it is words, not a link. */}
        {screen.handover && (
          <p className="aside aside-handover">
            {screen.handover.text}{" "}
            {screen.handover.url ? (
              <a href={screen.handover.url}>{screen.handover.link_label}</a>
            ) : (
              <span className="handover-pending">{screen.handover.link_label}</span>
            )}
          </p>
        )}
      </div>
      {/* The step before stop 1 has no evidence line of its own, so no foot: its marker leads to the claims. */}
      {stop && (
        <div className="foot">
          <EvidencePill evidence={screen.evidence} />
          <button
            type="button"
            className="open-evidence"
            id={openerId(step.id)}
            aria-label={`Open the evidence: ${stop.label}, screen ${step.screenAt} of ${step.screenCount}`}
            onClick={() => onOpen(screen.id, openerId(step.id), false)}
          >
            Open the evidence
          </button>
          <Rail step={step} anchors={anchors} />
        </div>
      )}
    </div>
  );
}

export function Emphasised({ statement }: { statement: Statement }) {
  const [before, emphasis, after] = splitEmphasis(statement.text, statement.emphasis);
  return (
    <>
      {before}
      {emphasis && <em>{emphasis}</em>}
      {after}
    </>
  );
}

/** Where a recorded line comes from, said in one word before it. */
const LINE_KINDS = { console: "Console", loader_report: "Loader report" } as const;

/**
 * The one line of evidence on a screen. A recorded event shows its register and type, read from the
 * recording, then the line itself; a line of the console or of the loader's report says which it is;
 * evidence that does not exist shows the label that says so. The line is never reworded. With `mark`, the
 * part of the line the content asks to have set in colour is.
 */
export function EvidencePill({ evidence, mark = false }: { evidence: Evidence; mark?: boolean }) {
  if (!evidence.recorded) return <p className="pill pill-missing">{evidence.label}</p>;
  const event =
    evidence.kind === "event" && evidence.event_index ? recordedEvent(evidence.run, evidence.event_index) : null;
  const [before, emphasis, after] = splitEmphasis(evidence.text, mark ? (evidence.highlight ?? null) : null);
  return (
    <p className="pill">
      {event ? (
        <>
          <span className="pill-register">PCR {event.pcr}</span> <span className="pill-type">{event.type}</span>{" "}
        </>
      ) : (
        evidence.kind !== "event" && (
          <>
            <span className="pill-type">{LINE_KINDS[evidence.kind]}</span>{" "}
          </>
        )
      )}
      <span className="pill-line">
        <Breakable line={before} />
        {emphasis && <em>{emphasis}</em>}
        <Breakable line={after} />
      </span>
    </p>
  );
}

/**
 * A recorded line with the places a long one may break: before the word "from", where a console line goes on
 * to name a device, and after each slash of the device's path. Not one character of the line is changed.
 */
export function Breakable({ line }: { line: string }) {
  // Spaces at the ends of a part stay outside its box, where a line can break and no space is lost.
  const parts = line.split(/ (?=from )/).map((part) => /^(\s*)(.*?)(\s*)$/s.exec(part)!);
  return (
    <>
      {parts.map(([, lead, words, trail], n) => (
        <Fragment key={n}>
          {n > 0 && " "}
          {lead}
          {words && (
            // A line of one part is plain text: only a line of two parts has parts to keep whole.
            <span className={parts.length > 1 ? "pill-part" : undefined}>
              {words.split("/").map((piece, m) => (
                <Fragment key={m}>
                  {m > 0 && "/"}
                  {m > 0 && <wbr />}
                  {piece}
                </Fragment>
              ))}
            </span>
          )}
          {trail}
        </Fragment>
      ))}
    </>
  );
}

/**
 * Where the reader is among the seven stops: one mark per stop, lit up to this one. The mark of the current
 * stop fills screen by screen. Where the page has a place for each step, a mark leads to its stop.
 */
function Rail({ step, anchors }: { step: SceneStep; anchors: boolean }) {
  const { number: at, of } = step.stop!;
  return (
    <p className="rail" role="group" aria-label={`Stop ${at} of ${of}, screen ${step.screenAt} of ${step.screenCount}`}>
      {Array.from({ length: of }, (_, n) => {
        const fill = n + 1 < at ? 1 : n + 1 > at ? 0 : step.screenAt / step.screenCount;
        const mark = <i style={{ "--fill": fill } as CSSProperties} />;
        return anchors ? (
          <a key={n} href={`#step-${firstStepOf(n + 1)}`} aria-label={`Go to stop ${n + 1}`} data-on={fill > 0}>
            {mark}
          </a>
        ) : (
          <span key={n} data-on={fill > 0}>
            {mark}
          </span>
        );
      })}
    </p>
  );
}
