// One stage: the picture in all its layers, and the words of each step over it. Every layer and every step's
// words are always in the stage; the current step only sets which are seen, and the stylesheet fades between
// them. A stage shown alone (a still section, or a frozen step) carries only its own step's words.
import type { CSSProperties } from "react";
import boardDark from "../assets/board-dark.webp";
import laptopDark from "../assets/laptop-dark.webp";
import { PICTURE_NOTE, claimNumbers, recordedEvent } from "../content/load";
import { PARTS, type Evidence, type OpeningScreen, type Part, type Statement } from "../content/types";
import { STEPS, focusAt, layersAt, pictureLabel, splitEmphasis, type SceneStep } from "../model/scene";
import { Mark } from "./Mark";
import { markerId, openerId } from "./panel";

const maskFiles = import.meta.glob<string>("../assets/masks/*.webp", { eager: true, import: "default" });
/** The mask picture of each part, by part name. */
export const MASKS = Object.fromEntries(
  PARTS.map((part) => [part, maskFiles[`../assets/masks/${part}.webp`]]),
) as Record<Part, string>;

/** Opens the evidence of a screen. `atClaims` asks for its list of claims, as a citation marker does. */
export type OpenEvidence = (screenId: string, openerId: string, atClaims: boolean) => void;

interface StageProps {
  /** The step the stage shows. */
  current: number;
  /** Alone on the page: only this step's words are rendered. */
  solo?: boolean;
  onOpen: OpenEvidence;
}

export function Stage({ current, solo = false, onOpen }: StageProps) {
  const step = STEPS[current];
  const layers = layersAt(step);
  return (
    <div className="stage" data-step={step.id}>
      <div className="picture" role="img" aria-label={pictureLabel(step)}>
        <img className="laptop" src={laptopDark} alt="" width={1280} height={960} data-on={layers.laptop} />
        <div className="board" data-on={layers.board} style={{ "--focus": focusAt(current) } as CSSProperties}>
          <img src={boardDark} alt="" width={1920} height={1200} />
          {PARTS.map((part) => (
            <div
              key={part}
              className="lit"
              data-part={part}
              data-on={layers.parts[part].on}
              style={
                {
                  "--order": layers.parts[part].order,
                  maskImage: `url("${MASKS[part]}")`,
                  WebkitMaskImage: `url("${MASKS[part]}")`,
                } as CSSProperties
              }
            />
          ))}
        </div>
      </div>
      {STEPS.map((s, n) =>
        solo && n !== current ? null : <Words key={s.id} step={s} on={n === current} onOpen={onOpen} />,
      )}
      <p className="picture-note">{PICTURE_NOTE}</p>
    </div>
  );
}

/** The words of one step. While another step is current they are faded out and out of reach. */
function Words({ step, on, onOpen }: { step: SceneStep; on: boolean; onOpen: OpenEvidence }) {
  const { screen, stop } = step;
  if (step.kind === "opening") {
    const opening = screen as OpeningScreen;
    return (
      <div className="words words-opening" data-on={on} inert={!on}>
        <div className="title-block">
          <p className="title-eyebrow">{opening.eyebrow}</p>
          <h1 className="title">
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
    <div className="words words-stop" data-on={on} inert={!on}>
      <div className="head">
        {stop && (
          <p className="eyebrow">
            {stop.number} of {stop.of} <span aria-hidden="true">·</span> {stop.label}
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
      </div>
      <div className="foot">
        {stop && <EvidencePill evidence={screen.evidence} />}
        <button
          type="button"
          className="open-evidence"
          id={openerId(step.id)}
          onClick={() => onOpen(screen.id, openerId(step.id), false)}
        >
          Open the evidence
        </button>
        {stop && <Rail at={stop.number} of={stop.of} />}
      </div>
    </div>
  );
}

function Emphasised({ statement }: { statement: Statement }) {
  const [before, emphasis, after] = splitEmphasis(statement.text, statement.emphasis);
  return (
    <>
      {before}
      {emphasis && <em>{emphasis}</em>}
      {after}
    </>
  );
}

/**
 * The one line of evidence on a screen. A recorded event shows its register and type, read from the
 * recording, then the line itself; evidence that does not exist shows the label that says so.
 */
export function EvidencePill({ evidence }: { evidence: Evidence }) {
  if (!evidence.recorded) return <p className="pill pill-missing">{evidence.label}</p>;
  const event =
    evidence.kind === "event" && evidence.event_index ? recordedEvent(evidence.run, evidence.event_index) : null;
  return (
    <p className="pill">
      {event && (
        <>
          <span className="pill-register">PCR {event.pcr}</span> <span className="pill-type">{event.type}</span>{" "}
        </>
      )}
      <span className="pill-line">{evidence.text}</span>
    </p>
  );
}

/** Where the reader is among the stops: one mark per stop, lit up to this one. */
function Rail({ at, of }: { at: number; of: number }) {
  return (
    <p className="rail" role="img" aria-label={`Stop ${at} of ${of}`}>
      {Array.from({ length: of }, (_, n) => (
        <span key={n} data-on={n < at} />
      ))}
    </p>
  );
}
