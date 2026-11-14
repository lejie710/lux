// The sources page: what was read or run and how it is cited, what was not read and what that costs the
// reader, the limits, the glossary with a filter, how one recording says it was made, and what the project
// is. Every word is the content's or the recording's; this file holds only the names of the fields.
import { useState } from "react";
import { provenanceOf } from "../content/files";
import {
  DISCLAIMER,
  FIRMWARE_SOURCES,
  GLOSSARY,
  LIMITS,
  NOT_READ,
  PICTURE_NOTE,
  READING_NOTES,
  SOURCES,
  SOURCE_SCREENS,
  STAGE_NAMES,
  TRADEMARK_NOTE,
  basisLabel,
  claimSource,
} from "../content/load";
import type { Claim, Source } from "../content/types";
import { filterGlossary } from "../model/glossary";
import { hrefOf, sectionId } from "../model/route";
import { Foot, Head } from "./Experiments";
import type { OpenEvidence } from "./Stage";
import { ClaimItem, Digest, NewTab } from "./sheetParts";

/** The run whose own account of how it was made is shown. */
export const PROVENANCE_RUN = "normal-1";

/** The parts of the page, in order, as the row of links under its head names them. */
export const SOURCE_SECTIONS = [
  ["read", "Read or run"],
  ["not-read", "Not read"],
  ["limits", "Limits"],
  ["glossary", "Glossary"],
  ["provenance", "Provenance"],
  ["about", "About"],
] as const;

export function Sources({ onOpen }: { onOpen: OpenEvidence }) {
  const [sources, about] = SOURCE_SCREENS;
  return (
    <div className="page page-sources">
      <section className="page-screen" id={sectionId(sources.id)} data-kind={sources.kind}>
        <Head screen={sources} onOpen={onOpen} first />
        <Foot screen={sources} onOpen={onOpen} />
        <nav className="page-parts" aria-label="On this page">
          {SOURCE_SECTIONS.map(([id, name]) => (
            <a key={id} href={hrefOf("sources", id)}>
              {name}
            </a>
          ))}
        </nav>
      </section>

      <section className="page-part" id={sectionId("read")} aria-labelledby="read-title">
        <h2 id="read-title" className="part-title">
          What was read or run
        </h2>
        <ul className="entries">
          {SOURCES.map((source) => (
            <SourceEntry key={source.id} source={source} />
          ))}
        </ul>
      </section>

      <section className="page-part" id={sectionId("not-read")} aria-labelledby="not-read-title">
        <h2 id="not-read-title" className="part-title">
          What was not read, and what that costs
        </h2>
        <ul className="entries">
          {NOT_READ.map((document) => (
            <li key={document.id} className="entry">
              <p className="entry-kind">{document.publisher}</p>
              <h3 className="entry-title">{document.title}</h3>
              <p className="entry-status">{document.status}</p>
              <dl className="entry-fields">
                <Field name="What it defines" value={document.what_it_defines} />
                <Field name="What that costs the reader" value={document.cost_to_reader} strong />
                <Field name="The rule on this site" value={document.site_rule} />
                <Field name="Its name" value={document.known_as} />
              </dl>
              <Claims claims={document.claims} />
            </li>
          ))}
        </ul>
      </section>

      <section className="page-part" id={sectionId("limits")} aria-labelledby="limits-title">
        <h2 id="limits-title" className="part-title">
          The limits of what is shown
        </h2>
        <ul className="entries entries-small">
          {LIMITS.map((limit) => (
            <li key={limit.id} className="entry">
              <h3 className="entry-title">{limit.title}</h3>
              <p className="entry-text">{limit.text}</p>
              <Claims claims={limit.claims} />
            </li>
          ))}
        </ul>
        <div className="notes">
          <h3 className="label">How to read this site</h3>
          <p>{STAGE_NAMES.text}</p>
          {Object.entries(READING_NOTES).map(([id, note]) => (
            <p key={id}>{note}</p>
          ))}
          <Claims claims={STAGE_NAMES.claims} />
        </div>
      </section>

      <Glossary />
      <Provenance />

      <section className="page-screen" id={sectionId(about.id)} data-kind={about.kind}>
        <Head screen={about} onOpen={onOpen} />
        <div className="about">
          {(about.paragraphs ?? []).map((text) => (
            <p key={text}>{text}</p>
          ))}
        </div>
        <Foot screen={about} onOpen={onOpen} />
        <div className="notes notes-last">
          <p>{PICTURE_NOTE}</p>
          <p>{TRADEMARK_NOTE}</p>
          <p>{DISCLAIMER}</p>
        </div>
      </section>
    </div>
  );
}

/** One named field of an entry. Nothing is drawn for a field the entry does not have. */
function Field({ name, value, strong = false }: { name: string; value?: string | null; strong?: boolean }) {
  if (!value) return null;
  return (
    <div data-strong={strong || undefined}>
      <dt>{name}</dt>
      <dd>{value}</dd>
    </div>
  );
}

/** The claims that rest on an entry, folded away, each with its basis label and its source. */
function Claims({ claims }: { claims: Claim[] }) {
  if (claims.length === 0) return null;
  return (
    <details className="entry-claims">
      <summary>
        {claims.length} {claims.length === 1 ? "claim" : "claims"}, with where each comes from
      </summary>
      <ul className="sheet-claims sheet-claims-plain">
        {claims.map((claim, n) => (
          <ClaimItem key={n} claim={claim} />
        ))}
      </ul>
    </details>
  );
}

/** Something that was read or run: its citation, how it was used, its licence, and the claims that rest on it. */
function SourceEntry({ source }: { source: Source }) {
  return (
    <li className="entry">
      <p className="entry-kind">{source.role ?? source.publisher ?? source.kind}</p>
      <h3 className="entry-title">{source.title}</h3>
      <p className="entry-cite">{source.citation_line ?? source.version}</p>
      {source.citation_line && <p className="entry-cite">Version {source.version}</p>}
      {source.url && (
        <p className="entry-link">
          <a href={source.url} target="_blank" rel="noreferrer">
            {source.url}
            <NewTab />
          </a>
        </p>
      )}
      <dl className="entry-fields">
        <Field name="What was read" value={source.read} />
        <Field name="How it was used" value={source.how_used} />
        <Field name="Used for" value={source.used_for} />
        <Field name="Not used for" value={source.not_used_for} />
        <Field name="Rights" value={source.rights} />
        <Field name="Licence" value={source.licence} />
      </dl>
      {source.licence_url && (
        <p className="entry-link">
          <a href={source.licence_url} target="_blank" rel="noreferrer">
            {source.licence_url}
            <NewTab />
          </a>
        </p>
      )}
      {source.sha256 && <Digest label="sha256" value={source.sha256} />}
      {source.caveats && (
        <ul className="entry-list">
          {source.caveats.map((text) => (
            <li key={text}>{text}</li>
          ))}
        </ul>
      )}
      {source.files && (
        <ul className="entry-list entry-files">
          {source.files.map((file) => (
            <li key={file}>{file}</li>
          ))}
        </ul>
      )}
      {source.source_files_note && (
        <>
          <p className="entry-text">{source.source_files_note}</p>
          <ul className="entry-list entry-files">
            {FIRMWARE_SOURCES.map((file) => (
              <li key={file.id}>
                <a href={file.url} target="_blank" rel="noreferrer">
                  {file.path}
                  <NewTab />
                </a>
                <span>
                  {file.project}. Read at: {file.read_at}. {file.licence}
                </span>
              </li>
            ))}
          </ul>
        </>
      )}
      <Claims claims={source.claims} />
    </li>
  );
}

/** The glossary, with a box that filters it as the reader types. */
function Glossary() {
  const [query, setQuery] = useState("");
  const found = filterGlossary(GLOSSARY, query);
  return (
    <section className="page-part" id={sectionId("glossary")} aria-labelledby="glossary-title">
      <h2 id="glossary-title" className="part-title">
        Glossary
      </h2>
      <div className="filter">
        <label htmlFor="glossary-filter">Filter the terms</label>
        <input
          id="glossary-filter"
          type="search"
          value={query}
          autoComplete="off"
          spellCheck={false}
          onChange={(e) => setQuery(e.target.value)}
        />
        <p role="status">
          {found.length === GLOSSARY.length
            ? `${GLOSSARY.length} terms`
            : `${found.length} of ${GLOSSARY.length} terms`}
        </p>
      </div>
      <dl className="glossary">
        {found.map((entry) => {
          const source = claimSource({ ...entry, text: entry.definition });
          return (
            <div key={entry.id} id={`term-${entry.id}`}>
              <dt>
                {entry.term}
                {entry.also.length > 0 && <span className="glossary-also"> also {entry.also.join(", ")}</span>}
              </dt>
              <dd>{entry.definition}</dd>
              <dd className="glossary-basis">
                <span className="claim-basis" data-basis={entry.basis}>
                  {basisLabel(entry.basis).label}
                </span>
                {source && <span className="claim-source">{source}</span>}
              </dd>
            </div>
          );
        })}
      </dl>
      {found.length === 0 && <p className="entry-text">No term matches.</p>}
    </section>
  );
}

/** How one recording says it was made: its own provenance block, field by field, as stored. */
function Provenance() {
  const found = provenanceOf(PROVENANCE_RUN);
  if (!found) return null;
  const { provenance: p, file, mayVary } = found;
  const rows: [string, string][] = [
    ["recorded_at", p.recorded_at],
    ["host_os", p.host_os],
    ...Object.entries(p.tools).map(([tool, version]): [string, string] => [`tools.${tool}`, version]),
    ["firmware.file", p.firmware.file],
  ];
  const digests: [string, string][] = [
    ["firmware.sha256", p.firmware.sha256],
    ...Object.entries(p.keys).map(([key, value]): [string, string] => [`keys.${key}`, value]),
    ...Object.entries(p.loader).map(([key, value]): [string, string] => [`loader.${key}`, value]),
    ["vars_template_sha256", p.vars_template_sha256],
  ];
  return (
    <section className="page-part" id={sectionId("provenance")} aria-labelledby="provenance-title">
      <h2 id="provenance-title" className="part-title">
        How the recording says it was made
      </h2>
      <p className="entry-text">
        The provenance block of run {PROVENANCE_RUN}, as the recording stores it. <span className="path">{file}</span>
      </p>
      <dl className="provenance">
        {rows.map(([field, value]) => (
          <div key={field}>
            <dt>{field}</dt>
            <dd>{value}</dd>
          </div>
        ))}
        {digests.map(([field, value]) => (
          <div key={field}>
            <dt>{field}</dt>
            <dd>
              <Digest label="" value={value} />
            </dd>
          </div>
        ))}
        <div>
          <dt>prediction</dt>
          <dd>{p.prediction === null ? "null" : JSON.stringify(p.prediction)}</dd>
        </div>
        <div>
          <dt>may_vary</dt>
          <dd>{mayVary.join(", ")}</dd>
        </div>
      </dl>
      {(["qemu_command_line", "swtpm_command_line"] as const).map((field) => (
        <div key={field} className="command">
          <p className="sheet-run">{field}</p>
          <pre tabIndex={0} role="group" aria-label={field}>
            {p[field]}
          </pre>
        </div>
      ))}
    </section>
  );
}
