// What a comparison file holds, laid out for the evidence panel: how each run ended, the first record that
// differs, the registers that differ with both values, the records only one run has, and the first console
// line that differs. Then the prediction and its score where they exist, and the note on a status.
import { comparisonView, type ComparedRecord } from "../content/files";
import { READING_NOTES, STOPS, basisLabel } from "../content/load";
import { BASES, type Basis, type Detail, type StatusMismatch } from "../content/types";
import { expectation, type ComparisonFile, type ExperimentState } from "../model/experiments";
import { Digest, RunName } from "./sheetParts";

/** A list of numbers in words: "4, 5 and 7". */
export function listed(values: readonly (number | string)[]): string {
  if (values.length < 2) return values.join("");
  return `${values.slice(0, -1).join(", ")} and ${values.at(-1)}`;
}

function Record({ record, plain }: { record: ComparedRecord; plain?: string }) {
  return (
    <li>
      <p className="row-line">
        <span className="row-key">Record {record.index}</span> <span>PCR {record.pcr}</span>{" "}
        <span className="row-type">{record.type}</span>
      </p>
      {record.summary && <p className="row-value">{record.summary}</p>}
      {plain && <p className="row-why">{plain}</p>}
      <Digest label="sha256" value={record.digest_sha256} />
    </li>
  );
}

interface ComparisonProps {
  comparison: { path: string; file: ComparisonFile };
  /** The words the screen adds to the file: a plain line per record, and what the stop of a record rests on. */
  detail: Detail | null;
}

export function Comparison({ comparison, detail }: ComparisonProps) {
  const view = comparisonView(comparison);
  const stop = view.first ? STOPS.find((s) => s.number === view.first?.stop) : null;
  const plain = (list: Detail["events_only_in_baseline"], index: number) => list?.find((e) => e.index === index)?.plain;
  return (
    <>
      <section>
        <h3>The two runs compared</h3>
        <p className="sheet-prose">
          Run {view.changed} against run {view.baseline}.
          {view.identical ? " The two are identical on every compared field." : ""}
        </p>
        <dl className="sheet-pairs">
          <div>
            <dt>Run {view.baseline}</dt>
            <dd>{view.outcome.baseline}</dd>
          </div>
          <div>
            <dt>Run {view.changed}</dt>
            <dd data-outcome={view.outcome.changed}>{view.outcome.changed}</dd>
          </div>
        </dl>
        <p className="sheet-path">{view.path}: outcome</p>
      </section>

      {view.first && (
        <section>
          <h3>The first record that differs</h3>
          <p className="sheet-prose">
            Record {view.first.index}
            {stop ? `, at stop ${stop.number}, ${stop.label}` : ""}. {detail?.first_differing_event?.before_it ?? ""}
          </p>
          {(["baseline", "changed"] as const).map((side) => {
            const record = view.first?.[side];
            return (
              <div key={side} className="sheet-lines-group">
                <RunName run={view[side]} />
                {record ? (
                  <ul className="sheet-rows">
                    <Record record={record} />
                  </ul>
                ) : (
                  <p className="row-why">This run has no record {view.first?.index}.</p>
                )}
              </div>
            );
          })}
          <p className="sheet-caption">{detail?.first_differing_event?.stop_basis ?? READING_NOTES.stops}</p>
          <p className="sheet-path">{view.path}: first_differing_event</p>
        </section>
      )}

      {!view.identical && (
        <section>
          <h3>Registers that differ</h3>
          {view.registers.length === 0 ? (
            <p className="sheet-prose">No register differs between the two runs.</p>
          ) : (
            <>
              <ul className="sheet-rows">
                {view.registers.map((register) => (
                  <li key={register.pcr}>
                    <p className="row-line">
                      <span className="row-key">PCR {register.pcr}</span>
                    </p>
                    <Digest label={`${view.baseline} ${view.bank}`} value={register.baseline} />
                    <Digest label={`${view.changed} ${view.bank}`} value={register.changed} />
                  </li>
                ))}
              </ul>
              <p className="sheet-caption">
                {view.banks.length > 1
                  ? `The same registers differ in the ${listed(view.banks)} banks. `
                  : `Shown for the ${view.bank} bank. `}
                {view.same.length > 0 ? `The same in both runs: registers ${listed(view.same)}.` : ""}
              </p>
            </>
          )}
          <p className="sheet-caption">{READING_NOTES.register_values}</p>
          <p className="sheet-path">{view.path}: pcrs_differing, pcrs_same</p>
        </section>
      )}

      {view.onlyBaseline.length + view.onlyChanged.length > 0 && (
        <section>
          <h3>Records only one run has</h3>
          {(
            [
              ["baseline", view.onlyBaseline, detail?.events_only_in_baseline],
              ["changed", view.onlyChanged, detail?.events_only_in_changed],
            ] as const
          ).map(([side, records, words]) => (
            <div key={side} className="sheet-lines-group">
              <RunName run={view[side]} />
              {records.length === 0 ? (
                <p className="row-why">None.</p>
              ) : (
                <ul className="sheet-rows">
                  {records.map((record) => (
                    <Record key={record.index} record={record} plain={plain(words, record.index)} />
                  ))}
                </ul>
              )}
            </div>
          ))}
          <p className="sheet-caption">{READING_NOTES.event_type_names}</p>
          <p className="sheet-path">{view.path}: events_only_in_baseline, events_only_in_changed</p>
        </section>
      )}

      {view.consoleFirst && (
        <section>
          <h3>The first console line that differs</h3>
          <p className="sheet-prose">Line {view.consoleFirst.line} of the console.</p>
          {(["baseline", "changed"] as const).map((side) => (
            <div key={side} className="sheet-lines-group">
              <RunName run={view[side]} />
              <ol className="sheet-lines">
                <li>
                  <span className="line-text">{view.consoleFirst?.[side] ?? "This run printed no such line."}</span>
                </li>
              </ol>
            </div>
          ))}
          <p className="sheet-path">{view.path}: console_first_differing_line</p>
        </section>
      )}
    </>
  );
}

const isBasis = (basis: string): basis is Basis => (BASES as readonly string[]).includes(basis);

/** The label of a basis, in the content's words where the content knows it. */
function BasisChip({ basis }: { basis: string }) {
  return (
    <p className="claim-basis" data-basis={basis}>
      {isBasis(basis) ? basisLabel(basis).label : basis}
    </p>
  );
}

/**
 * What was predicted before the run, and how it held: the rows of the prediction file, each with its basis
 * label, and the score file's verdict on each. A run with no prediction says so in the content's own words.
 */
export function Prediction({ state, status }: { state: ExperimentState; status: string | null }) {
  const { prediction, score } = state;
  const held = (id: string) => score?.rows.find((row) => row.id === id)?.held;
  // The rows to show: the prediction's, or failing that file the score's own, which name only basis and verdict.
  const rows = prediction?.rows ?? score?.rows.map((row) => ({ ...row, field: row.id })) ?? [];
  return (
    <section>
      <h3>The prediction</h3>
      {!prediction && !score && <p className="sheet-prose">{status ?? "No prediction is on file for this run."}</p>}
      {score && (
        <dl className="sheet-pairs">
          <div>
            <dt>Specification-required rows met</dt>
            <dd>
              {score.required_met} of {score.required_total}
            </dd>
          </div>
          <div>
            <dt>Open rows predicted correctly</dt>
            <dd>
              {score.open_correct} of {score.open_total}
            </dd>
          </div>
          <div>
            <dt>Mismatches</dt>
            <dd>{score.mismatches.length === 0 ? "none" : score.mismatches.join(", ")}</dd>
          </div>
        </dl>
      )}
      {prediction && (
        <p className="sheet-prose">
          {prediction.written ? `Written ${prediction.written}. ` : ""}
          {score ? "" : state.run ? "The run is recorded and not yet scored." : "On file. Not yet run."}
        </p>
      )}
      {prediction?.change && <p className="row-value">{prediction.change}</p>}
      {rows.length > 0 && (
        <ul className="sheet-rows">
          {rows.map((row) => {
            const verdict = held(row.id);
            const cite = "citation" in row ? row.citation : null;
            return (
              <li key={row.id}>
                <BasisChip basis={row.basis} />
                <p className="row-line">
                  <span className="row-key">{row.id}</span>
                  {verdict !== undefined && (
                    <span className="row-verdict" data-held={verdict}>
                      {verdict ? "held" : "did not hold"}
                    </span>
                  )}
                </p>
                {prediction && <p className="row-value">{expectation(row as never)}</p>}
                {cite && (
                  <p className="claim-source">
                    {cite.document} {cite.version}, {cite.section}. PDF page {cite.page}
                  </p>
                )}
                {"reason" in row && row.reason && <p className="row-why">{String(row.reason)}</p>}
                {"source" in row && row.source && <p className="claim-source">{String(row.source)}</p>}
              </li>
            );
          })}
        </ul>
      )}
      {prediction?.wrong_if && prediction.wrong_if.length > 0 && (
        <>
          <p className="sheet-group">What would prove it wrong, written before the run</p>
          {prediction.wrong_if.map((text) => (
            <p key={text} className="sheet-prose">
              {text}
            </p>
          ))}
        </>
      )}
      {prediction?.not_scored && prediction.not_scored.length > 0 && (
        <>
          <p className="sheet-group">Expected, and not scored</p>
          {prediction.not_scored.map((text) => (
            <p key={text} className="sheet-prose">
              {text}
            </p>
          ))}
        </>
      )}
      {score?.prediction?.path && <p className="sheet-path">{score.prediction.path}</p>}
    </section>
  );
}

/** The status the specification's text names, set against the words the firmware printed. */
export function StatusNote({ note }: { note: StatusMismatch }) {
  const { citation } = note;
  return (
    <section>
      <h3>{note.title}</h3>
      <dl className="sheet-terms">
        <div>
          <dt>The text</dt>
          <dd>{note.specification}</dd>
          <dd className="claim-source">
            {citation.document} {citation.version}, section {citation.section}, {citation.title}. PDF page{" "}
            {citation.pdf_page}
          </dd>
        </div>
        <div>
          <dt>The recording</dt>
          <dd>{note.recording}</dd>
          <dd className="claim-source">
            {note.evidence.file}: {note.evidence.field}[{note.evidence.array_index}]
          </dd>
        </div>
        <div>
          <dt>How the two stand</dt>
          <dd>{note.reading}</dd>
          <dd>{note.limit}</dd>
        </div>
      </dl>
    </section>
  );
}
