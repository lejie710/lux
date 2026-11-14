// What "Open the evidence" shows for one screen: the evidence line or the label that says there is none, the
// explanation, the console lines, records and registers behind it, every claim with its basis and source,
// the terms, and what the recording does not show. A two-run screen and a card of an experiment also show
// what their comparison file holds. A dialog: focus moves in, Tab stays in, Escape closes.
import { useEffect, useRef } from "react";
import { FILES, comparisonAt } from "../content/files";
import {
  READING_NOTES,
  STOPS,
  basisLabel,
  claimNumbers,
  define,
  recordedEvent,
  recordedLine,
  recordedRegister,
  subjectId,
  type Subject,
} from "../content/load";
import { BASES, type Card, type Claim, type Detail } from "../content/types";
import { cardStates, experimentState, onFile } from "../model/experiments";
import { Comparison, Prediction, StatusNote } from "./Comparison";
import { EvidencePill } from "./Stage";
import { panelKey } from "./panel";
import { ClaimItem, Digest, RunName } from "./sheetParts";

interface EvidencePanelProps {
  screen: Subject["screen"];
  /** One card of the screen: the panel is then about that experiment alone. */
  card?: Card | null;
  /** Open at the list of claims, not at the top. */
  atClaims: boolean;
  onClose: () => void;
}

/** What the panel's Tab loop goes through: its controls, its fold-outs and its scrolling lists. */
const CONTROLS = "button, a[href], summary, [tabindex='0']";

export function EvidencePanel({ screen, card = null, atClaims, onClose }: EvidencePanelProps) {
  const sheet = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const claimsHeading = useRef<HTMLHeadingElement>(null);
  const stop = STOPS.find((s) => s.number === screen.stop) ?? null;
  const { detail, evidence } = screen;
  const notShown = [...(stop?.not_shown ?? []), ...(detail.not_shown ?? [])];
  // The claims shown: a card's own, or the screen's followed by those of each of its cards and items.
  const groups: { id: string; title: string | null; claims: Claim[] }[] = card
    ? [{ id: subjectId(screen.id, card.id), title: null, claims: card.claims }]
    : [
        { id: screen.id, title: null, claims: screen.claims },
        ...[...(screen.cards ?? []), ...(screen.items ?? [])].map((part) => ({
          id: subjectId(screen.id, part.id),
          title: part.title,
          claims: part.claims,
        })),
      ].filter((group) => group.title === null || group.claims.length > 0);
  const claims = groups.flatMap((group) => group.claims);
  const cited = claims.some((claim) => claim.citation ?? claim.uefi_pointer);
  // The labels to explain: the ones these claims carry and the ones the screen asks for, in the content's order.
  const labels = BASES.filter(
    (basis) => claims.some((claim) => claim.basis === basis) || detail.basis_labels?.includes(basis),
  ).map(basisLabel);
  const stageName = stop?.stage_name;
  // What the files on disk hold for this experiment: its comparison with the normal run, prediction and score.
  // A card may stand for more than one form of its experiment; a two-run screen names one.
  const states = card
    ? cardStates(card.id, FILES).filter(onFile)
    : screen.experiment
      ? [experimentState(screen.experiment, FILES)]
      : [];
  const comparison = !card && detail.comparison ? comparisonAt(detail.comparison.file) : null;
  const status = card ? card.status : (screen.status?.text ?? null);

  // Focus moves into the panel when it opens: to the claims when a citation marker opened it.
  useEffect(() => {
    if (atClaims && claimsHeading.current) {
      claimsHeading.current.scrollIntoView({ block: "start" });
      claimsHeading.current.focus({ preventScroll: true });
    } else closeButton.current?.focus();
  }, [atClaims]);

  // Keys are heard on the whole document while the panel is open, so Escape and the Tab loop still work
  // after a click on plain text has taken focus off every control.
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const controls = [...(sheet.current?.querySelectorAll<HTMLElement>(CONTROLS) ?? [])];
      const active = document.activeElement as HTMLElement | null;
      // Focus on something in the panel that is not a control (the heading a citation marker lands on):
      // Tab then goes on from there, to the first control that follows it.
      const loose = active && active !== sheet.current && sheet.current?.contains(active) ? active : null;
      const following = (control: HTMLElement) =>
        Boolean(loose!.compareDocumentPosition(control) & Node.DOCUMENT_POSITION_FOLLOWING);
      const next = loose ? controls.findIndex(following) : -1;
      const after = loose ? (next < 0 ? controls.length : next) : null;
      const result = panelKey(e, controls.indexOf(active as HTMLElement), controls.length, after);
      if (!result) return;
      e.preventDefault();
      if (result.action === "close") close.current();
      else controls[result.index]?.focus();
    };
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <>
      <div className="sheet-backdrop" onClick={onClose} />
      <div className="sheet" ref={sheet} role="dialog" aria-modal="true" aria-labelledby="sheet-title" tabIndex={-1}>
        <header className="sheet-head">
          <p className="sheet-eyebrow">
            The evidence
            {stop && (
              <>
                {" "}
                <span aria-hidden="true">·</span> {stop.number} of {stop.of} <span aria-hidden="true">·</span>{" "}
                {stop.label}
              </>
            )}
            {card && (
              <>
                {" "}
                <span aria-hidden="true">·</span> {card.label}
              </>
            )}
          </p>
          <button type="button" className="sheet-close" ref={closeButton} onClick={onClose}>
            Close
          </button>
        </header>
        <h2 id="sheet-title" className="sheet-title">
          {card ? card.title : screen.statement.text}
        </h2>
        {card
          ? card.change && <p className="sheet-support">{card.change}</p>
          : screen.support && <p className="sheet-support">{screen.support}</p>}
        {screen.pilot_label && <p className="sheet-pilot">{screen.pilot_label}</p>}
        {status && <p className="sheet-pilot">{status}</p>}

        {screen.handover && <p className="sheet-caption">{screen.handover.note}</p>}

        {!card && screen.question && (
          <section>
            <h3>The question</h3>
            <p className="sheet-prose">{screen.question}</p>
          </section>
        )}
        {!card && screen.measure && screen.measure.length > 0 && (
          <section>
            <h3>The measure</h3>
            {screen.measure.map((text) => (
              <p key={text} className="sheet-prose">
                {text}
              </p>
            ))}
          </section>
        )}

        {!card && screen.sides && (
          <section>
            <h3>The line from each recording</h3>
            {screen.sides.map((side) => (
              <div key={side.id} className="sheet-lines-group">
                <RunName run={side.run} />
                <EvidencePill evidence={side.evidence} />
                <p className="sheet-path">
                  {side.evidence.file}: {side.evidence.field}
                </p>
              </div>
            ))}
          </section>
        )}
        {!card && evidence && (
          <section>
            <h3>{evidence.recorded ? "The line from the recording" : "Nothing was recorded here"}</h3>
            <EvidencePill evidence={evidence} />
            {evidence.caption && <p className="sheet-caption">{evidence.caption}</p>}
            {evidence.recorded && (
              <p className="sheet-path">
                {evidence.file}: {evidence.field}
              </p>
            )}
          </section>
        )}

        {!card && (
          <section>
            <h3>What happens</h3>
            <p className="sheet-prose">{detail.explanation}</p>
          </section>
        )}
        {card && !states.some((state) => state.run) && (
          <section>
            <h3>Not yet run</h3>
            <p className="sheet-prose">{card.result_note ?? "No recording of this experiment is on file."}</p>
          </section>
        )}

        {comparison ? (
          <Comparison comparison={comparison} detail={card ? null : detail} />
        ) : (
          !card &&
          detail.comparison && (
            <section>
              <h3>The two runs compared</h3>
              <p className="sheet-prose">
                Run {detail.comparison.changed} against run {detail.comparison.baseline}.
              </p>
              <p className="sheet-path">{detail.comparison.file}</p>
            </section>
          )
        )}
        {states.map((state) => (
          <div key={state.experiment} className="sheet-form">
            {card && (states.length > 1 || state.experiment !== card.id) && (
              <p className="sheet-form-name">{state.experiment}</p>
            )}
            {card && state.comparison && <Comparison comparison={state.comparison} detail={null} />}
            <Prediction state={state} status={status} />
          </div>
        ))}
        {!card && detail.status_mismatch && <StatusNote note={detail.status_mismatch} />}

        {!card && (
          <>
            <Lines detail={detail} />
            <Records detail={detail} />
            <Registers detail={detail} />
          </>
        )}

        {!card && detail.other_fields && detail.other_fields.length > 0 && (
          <section>
            <h3>
              {!detail.other_fields.every((field) => field.file.startsWith("recordings/"))
                ? "Also on file"
                : evidence?.recorded
                  ? "Other fields of the recording"
                  : "The nearest the recording has"}
            </h3>
            <ul className="sheet-rows">
              {detail.other_fields.map((field) => (
                <li key={`${field.file}-${field.field}`}>
                  <p className="row-line">
                    <span className="row-key">{field.field}</span>
                    {field.value !== undefined && <span className="row-type"> {String(field.value)}</span>}
                  </p>
                  <p className="row-why">{field.why}</p>
                  <p className="row-file">{field.file}</p>
                </li>
              ))}
            </ul>
          </section>
        )}

        {claims.length > 0 && (
          <section>
            <h3 ref={claimsHeading} tabIndex={-1}>
              Where each claim comes from
            </h3>
            {card?.specification_note && <p className="sheet-caption sheet-caption-first">{card.specification_note}</p>}
            {/* The legend: what each label on these claims means. */}
            <dl className="sheet-legend" aria-label="What the labels mean">
              {labels.map((label) => (
                <div key={label.basis}>
                  <dt className="claim-basis" data-basis={label.basis}>
                    {label.label}
                  </dt>
                  <dd>{label.meaning}</dd>
                </div>
              ))}
            </dl>
            {groups.map((group) => {
              const first = claimNumbers(group.id).first;
              return (
                <div key={group.id}>
                  {group.title && <p className="sheet-group">{group.title}</p>}
                  <ol className="sheet-claims" start={first}>
                    {group.claims.map((claim, n) => (
                      <ClaimItem key={claim.id ?? n} claim={claim} number={first + n} />
                    ))}
                  </ol>
                </div>
              );
            })}
            {cited && <p className="sheet-caption">{READING_NOTES.pdf_page}</p>}
          </section>
        )}

        {(stageName || detail.definitions.length > 0) && (
          <section>
            <h3>Terms</h3>
            <dl className="sheet-terms">
              {stageName && (
                <div>
                  <dt>
                    {stageName.name} ({stageName.expansion})
                  </dt>
                  <dd>{stageName.attribution}</dd>
                </div>
              )}
              {detail.definitions.map(define).map((entry) => (
                <div key={entry.term}>
                  <dt>{entry.term}</dt>
                  <dd>{entry.definition}</dd>
                </div>
              ))}
            </dl>
          </section>
        )}

        {!card && notShown.length > 0 && (
          <section>
            <h3>What the recording does not show</h3>
            {notShown.map((text) => (
              <p key={text} className="sheet-prose">
                {text}
              </p>
            ))}
          </section>
        )}
      </div>
    </>
  );
}

/** The console lines and the lines of the loader's report that a screen names, as they were printed. */
function Lines({ detail }: { detail: Detail }) {
  const consoleLines = detail.console_lines ?? [];
  const reportLines = detail.loader_report_lines ?? [];
  if (consoleLines.length + reportLines.length === 0 && !detail.console_note) return null;
  return (
    <section>
      <h3>What was printed</h3>
      {consoleLines.map((group, n) => (
        <div key={`console-${n}`} className="sheet-lines-group">
          <RunName run={group.run} />
          <ol className="sheet-lines">
            {group.positions.map((at) => (
              <li key={at}>
                <span className="line-at">console[{at}]</span>
                <span className="line-text">{recordedLine(group.run, "console", at)}</span>
              </li>
            ))}
          </ol>
          {group.note && <p className="row-why">{group.note}</p>}
        </div>
      ))}
      {detail.console_note && <p className="sheet-caption">{detail.console_note}</p>}
      {reportLines.map((group, n) => (
        <div key={`report-${n}`} className="sheet-lines-group">
          <RunName run={group.run} />
          <p className="sheet-caption">
            The loader&apos;s report, {group.positions.length} {group.positions.length === 1 ? "line" : "lines"}
            {group.prefix ? `, each beginning ${group.prefix.trim()}` : ""}.
          </p>
          {/* A long list scrolls in its own box, which the keyboard can reach. */}
          <ol
            className="sheet-lines sheet-lines-long"
            tabIndex={group.positions.length > 8 ? 0 : undefined}
            aria-label={`Loader report of run ${group.run}`}
          >
            {group.positions.map((at) => (
              <li key={at} data-marked={group.highlight?.includes(at) || undefined}>
                <span className="line-at">loader_report[{at}]</span>
                <span className="line-text">{recordedLine(group.run, "loader_report", at)}</span>
              </li>
            ))}
          </ol>
          {group.note && <p className="row-why">{group.note}</p>}
        </div>
      ))}
    </section>
  );
}

/** The records of the log that a screen names: number, register, type, what it says, and its fingerprint. */
function Records({ detail }: { detail: Detail }) {
  if (detail.events.length === 0) return null;
  return (
    <section>
      <h3>Records of the log</h3>
      {detail.events.map((group, n) => (
        <div key={n} className="sheet-lines-group">
          <RunName run={group.run} />
          {group.note && <p className="row-why row-why-first">{group.note}</p>}
          <ul className="sheet-rows">
            {group.indexes.map((index) => {
              const event = recordedEvent(group.run, index);
              return (
                <li key={index}>
                  <p className="row-line">
                    <span className="row-key">Record {event.index}</span> <span>PCR {event.pcr}</span>{" "}
                    <span className="row-type">{event.type}</span>
                  </p>
                  <p className="row-value">{event.summary}</p>
                  <Digest label="sha256" value={event.digest_sha256} />
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {detail.pilot_note && <p className="sheet-caption">{detail.pilot_note}</p>}
      <p className="sheet-caption">{READING_NOTES.event_type_names}</p>
    </section>
  );
}

/** The registers a screen names, with the value each held when the run ended. */
function Registers({ detail }: { detail: Detail }) {
  if (detail.pcrs.length === 0) return null;
  return (
    <section>
      <h3>Registers at the end of the run</h3>
      {detail.pcrs.map((group, n) => (
        <div key={n} className="sheet-lines-group">
          <RunName run={group.run} />
          <ul className="sheet-rows">
            {group.registers.map((register) => (
              <li key={register}>
                <p className="row-line">
                  <span className="row-key">PCR {register}</span>
                </p>
                <Digest label={group.bank} value={recordedRegister(group.run, group.bank, register)} />
              </li>
            ))}
          </ul>
          {group.note && <p className="row-why">{group.note}</p>}
        </div>
      ))}
      <p className="sheet-caption">{READING_NOTES.register_values}</p>
    </section>
  );
}
