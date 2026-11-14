// What "Open the evidence" shows for one screen: the evidence line or the label that says there is none, the
// records and fields behind it, the explanation, every claim with its basis and source, the terms, and what
// the recording does not show. A dialog: focus moves in, Tab stays in, Escape closes.
import { useEffect, useRef, type KeyboardEvent } from "react";
import {
  READING_NOTES,
  STOPS,
  basisLabel,
  claimNumbers,
  claimSource,
  define,
  firmwareSource,
  recordedEvent,
} from "../content/load";
import type { Claim, Screen } from "../content/types";
import { EvidencePill } from "./Stage";
import { panelKey } from "./panel";

interface EvidencePanelProps {
  screen: Screen;
  /** Open at the list of claims, not at the top. */
  atClaims: boolean;
  onClose: () => void;
}

export function EvidencePanel({ screen, atClaims, onClose }: EvidencePanelProps) {
  const sheet = useRef<HTMLDivElement>(null);
  const closeButton = useRef<HTMLButtonElement>(null);
  const claimsHeading = useRef<HTMLHeadingElement>(null);
  const stop = STOPS.find((s) => s.number === screen.stop) ?? null;
  const { detail, evidence } = screen;
  const first = claimNumbers(screen.id).first;
  const notShown = [...(stop?.not_shown ?? []), ...(detail.not_shown ?? [])];
  const cited = screen.claims.some((claim) => claim.citation ?? claim.uefi_pointer);

  // Focus moves into the panel when it opens: to the claims when a citation marker opened it.
  useEffect(() => {
    if (atClaims && claimsHeading.current) {
      claimsHeading.current.scrollIntoView({ block: "start" });
      claimsHeading.current.focus({ preventScroll: true });
    } else closeButton.current?.focus();
  }, [atClaims]);

  const onKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const controls = [...(sheet.current?.querySelectorAll<HTMLElement>("button, a[href]") ?? [])];
    const result = panelKey(e, controls.indexOf(document.activeElement as HTMLElement), controls.length);
    if (!result) return;
    e.preventDefault();
    if (result.action === "close") onClose();
    else controls[result.index]?.focus();
  };

  return (
    <>
      <div className="sheet-backdrop" onClick={onClose} />
      <div
        className="sheet"
        ref={sheet}
        role="dialog"
        aria-modal="true"
        aria-labelledby="sheet-title"
        onKeyDown={onKeyDown}
      >
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

        <section>
          <h3>{evidence.recorded ? "The line from the recording" : "Nothing was recorded here"}</h3>
          <EvidencePill evidence={evidence} />
          {evidence.caption && <p className="sheet-caption">{evidence.caption}</p>}
          {evidence.recorded && <p className="sheet-path">{evidence.field}</p>}
        </section>

        <section>
          <h3>What happens</h3>
          <p className="sheet-prose">{detail.explanation}</p>
        </section>

        {detail.events.length > 0 && (
          <section>
            <h3>Records of this boot</h3>
            <ul className="sheet-rows">
              {detail.events.flatMap((group) =>
                group.indexes.map((index) => {
                  const event = recordedEvent(group.run, index);
                  return (
                    <li key={`${group.run}-${index}`}>
                      <p className="row-line">
                        <span className="row-key">Record {event.index}</span> <span>PCR {event.pcr}</span>{" "}
                        <span className="row-type">{event.type}</span>
                      </p>
                      <p className="row-value">{event.summary}</p>
                      {group.note && <p className="row-why">{group.note}</p>}
                    </li>
                  );
                }),
              )}
            </ul>
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
