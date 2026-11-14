// The small pieces the evidence panel and the pages share: the name of a run, a long value shown short,
// and one claim with its basis and source.
import { basisLabel, claimSource, firmwareSource, shortened } from "../content/load";
import type { Claim } from "../content/types";

/** A run is named wherever its lines or records are shown, so two runs on one screen cannot be confused. */
export function RunName({ run }: { run: string }) {
  return <p className="sheet-run">Run {run}</p>;
}

/** A long value, shown short, with the whole of it one press away. */
export function Digest({ label, value }: { label: string; value: string }) {
  return (
    <details className="digest">
      <summary>
        <span className="digest-label">{label}</span> {shortened(value)}
      </summary>
      <p>{value}</p>
    </details>
  );
}

/**
 * One claim: its number where the list is numbered, the label of its basis, its words, and the line that
 * says where it comes from.
 */
export function ClaimItem({ claim, number }: { claim: Claim; number?: number }) {
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
