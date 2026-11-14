// What "Open the evidence" shows for one screen: the evidence line or the label that says there is none, the
// explanation, the console lines, records and registers behind it, every claim with its basis and source,
// the terms, and what the recording does not show. A dialog: focus moves in, Tab stays in, Escape closes.
import { useEffect, useRef } from "react";
import {
  READING_NOTES,
  STOPS,
  basisLabel,
  claimNumbers,
  claimSource,
  define,
  firmwareSource,
  recordedEvent,
  recordedLine,
  recordedRegister,
  shortened,
} from "../content/load";
import { BASES, type Claim, type Detail, type Screen } from "../content/types";
import { EvidencePill } from "./Stage";
import { panelKey } from "./panel";

interface EvidencePanelProps {
  screen: Screen;
  /** Open at the list of claims, not at the top. */
  atClaims: boolean;
  onClose: () => void;
}

/** What the panel's Tab loop goes through: its controls, its fold-outs and its scrolling lists. */
const CONTROLS = "button, a[href], summary, [tabindex='0']";

export function EvidencePanel({ screen, atClaims, onClose }: EvidencePanelProps) {
  const sheet = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const claimsHeading = useRef<HTMLHeadingElement>(null);
  const stop = STOPS.find((s) => s.number === screen.stop) ?? null;
  const { detail, evidence } = screen;
  const first = claimNumbers(screen.id).first;
  const notShown = [...(stop?.not_shown ?? []), ...(detail.not_shown ?? [])];
  const cited = screen.claims.some((claim) => claim.citation ?? claim.uefi_pointer);
  // The labels to explain: the ones this screen's claims carry and the ones it asks for, in the content's order.
  const labels = BASES.filter(
    (basis) => screen.claims.some((claim) => claim.basis === basis) || detail.basis_labels?.includes(basis),
  ).map(basisLabel);
  const stageName = stop?.stage_name;

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
      const result = panelKey(e, controls.indexOf(document.activeElement as HTMLElement), controls.length);
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
          </p>
          <button type="button" className="sheet-close" ref={closeButton} onClick={onClose}>
            Close
          </button>
        </header>
        <h2 id="sheet-title" className="sheet-title">
          {screen.statement.text}
        </h2>
        {screen.support && <p className="sheet-support">{screen.support}</p>}
        {screen.pilot_label && <p className="sheet-pilot">{screen.pilot_label}</p>}

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

        <section>
          <h3>What happens</h3>
          <p className="sheet-prose">{detail.explanation}</p>
        </section>

        <Lines detail={detail} />
        <Records detail={detail} />
        <Registers detail={detail} />

        {detail.comparison && (
          <section>
            <h3>The two runs compared</h3>
            <p className="sheet-prose">
              Run {detail.comparison.changed} against run {detail.comparison.baseline}.
            </p>
            <p className="sheet-path">{detail.comparison.file}</p>
          </section>
        )}

        {detail.other_fields && detail.other_fields.length > 0 && (
          <section>
            <h3>{evidence.recorded ? "Other fields of the recording" : "The nearest the recording has"}</h3>
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

        <section>
          <h3 ref={claimsHeading} tabIndex={-1}>
            Where each claim comes from
          </h3>
          {/* The legend: what each label on this screen's claims means. */}
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
          <ol className="sheet-claims" start={first}>
            {screen.claims.map((claim, n) => (
              <ClaimItem key={claim.id ?? n} claim={claim} number={first + n} />
            ))}
          </ol>
          {cited && <p className="sheet-caption">{READING_NOTES.pdf_page}</p>}
        </section>

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

        {notShown.length > 0 && (
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

/** A run is named wherever its lines or records are shown, so two runs on one screen cannot be confused. */
function RunName({ run }: { run: string }) {
  return <p className="sheet-run">Run {run}</p>;
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

/** A long value, shown short, with the whole of it one press away. */
function Digest({ label, value }: { label: string; value: string }) {
  return (
    <details className="digest">
      <summary>
        <span className="digest-label">{label}</span> {shortened(value)}
      </summary>
      <p>{value}</p>
    </details>
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

/** One claim: its number, the label of its basis, its words, and the line that says where it comes from. */
function ClaimItem({ claim, number }: { claim: Claim; number: number }) {
  const basis = basisLabel(claim.basis);
  const source = claimSource(claim);
  const file = claim.source_ref ? firmwareSource(claim.source_ref) : null;
  return (
    <li value={number}>
      <p className="claim-basis" data-basis={claim.basis} title={basis.meaning}>
        {basis.label}
      </p>
      <p className="claim-text">{claim.text}</p>
      {source &&
        (file ? (
          <p className="claim-source">
            <a href={file.url} target="_blank" rel="noreferrer">
              {source}
            </a>
          </p>
        ) : (
          <p className="claim-source">{source}</p>
        ))}
      {claim.note && <p className="claim-note">{claim.note}</p>}
    </li>
  );
}
