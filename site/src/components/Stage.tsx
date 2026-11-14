// One stage: the picture in all its layers, and the words of each step over it. Every layer and every step's
// words are always in the stage; the current step only sets which are seen, and the stylesheet fades between
// them. A stage shown alone (a still section, or a frozen step) carries only its own step's words.
import type { CSSProperties } from "react";
import boardDark from "../assets/board-dark.webp";
import laptopAwake from "../assets/laptop-awake.webp";
import laptopDark from "../assets/laptop-dark.webp";
import laptopInside from "../assets/laptop-inside.webp";
import { PICTURE_NOTE, claimNumbers, define, recordedEvent } from "../content/load";
import { PARTS, type Evidence, type OpeningScreen, type Part, type Statement } from "../content/types";
import {
  STEPS,
  firstStepOf,
  focusAt,
  layersAt,
  pictureLabel,
  splitEmphasis,
  type PartLayer,
  type SceneStep,
} from "../model/scene";
import { Mark } from "./Mark";
import { markerId, openerId } from "./panel";

const maskFiles = import.meta.glob<string>("../assets/masks/*.webp", { eager: true, import: "default" });
const maskOf = (name: string) => maskFiles[`../assets/masks/${name}.webp`];
/** The mask picture of each part, by part name. */
export const MASKS = Object.fromEntries(PARTS.map((part) => [part, maskOf(part)])) as Record<Part, string>;
/** The mask of the whole board: the ground between the parts. */
export const WHOLE_MASK = maskOf("whole");

/** Opens the evidence of a screen. `atClaims` asks for its list of claims, as a citation marker does. */
export type OpenEvidence = (screenId: string, openerId: string, atClaims: boolean) => void;

interface StageProps {
  /** The step the stage shows. */
  current: number;
  /** Alone on the page: only this step's words are rendered. */
  solo?: boolean;
  /** Whether the page has a place for each step that a mark of the rail can lead to. */
  anchors?: boolean;
  onOpen: OpenEvidence;
}

export function Stage({ current, solo = false, anchors = true, onOpen }: StageProps) {
  const step = STEPS[current];
  const layers = layersAt(step);
  return (
    <div className="stage" data-step={step.id}>
      <div className="picture" role="img" aria-label={pictureLabel(step)}>
        <img className="laptop" src={laptopDark} alt="" width={1280} height={960} data-on={layers.laptop} />
        <div className="board" data-on={layers.board} style={{ "--focus": focusAt(current) } as CSSProperties}>
          <img src={boardDark} alt="" width={1920} height={1200} />
          {PARTS.map((part) => (
            <Light key={part} name={part} layer={layers.parts[part]} />
          ))}
          <Light name="whole" layer={layers.whole} />
        </div>
        {/* The laptop of the ending: its inside awake, and over that the same laptop with its screen lit. */}
        <div className="ending" data-on={layers.ending}>
          <img src={laptopInside} alt="" width={1280} height={960} decoding="async" fetchPriority="low" />
          <img
            className="dawn"
            src={laptopAwake}
            alt=""
            width={1280}
            height={960}
            decoding="async"
            fetchPriority="low"
            data-on={layers.screenLit}
          />
        </div>
      </div>
      {STEPS.map((s, n) =>
        solo && n !== current ? null : (
          <Words key={s.id} step={s} on={n === current} anchors={anchors} onOpen={onOpen} />
        ),
      )}
      <p className="picture-note">{step.screen.picture_caption ?? PICTURE_NOTE}</p>
    </div>
  );
}

/**
 * The light of one part: a copy of the awake picture cut out by the part's mask, and over it a second copy
 * that adds a little more light while the step is about that part.
 */
function Light({ name, layer }: { name: string; layer: PartLayer }) {
  const style = {
    "--order": layer.order,
    maskImage: `url("${maskOf(name)}")`,
    WebkitMaskImage: `url("${maskOf(name)}")`,
  } as CSSProperties;
  return (
    <>
      <div className="lit" data-part={name} data-on={layer.on} style={style} />
      {name !== "whole" && <div className="glow" data-part={name} data-on={layer.strong} style={style} />}
    </>
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
        {screen.handover && (
          <p className="aside aside-handover">
            {screen.handover.text}{" "}
            <a href="#" title={screen.handover.note}>
              {screen.handover.link_label}
            </a>
          </p>
        )}
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
        {stop && <Rail step={step} anchors={anchors} />}
      </div>
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
        {mark ? (
          <Emphasised statement={{ text: evidence.text, emphasis: evidence.highlight ?? null }} />
        ) : (
          evidence.text
        )}
      </span>
    </p>
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
