// The pages of the site and the address of each. A page lives after the hash sign, so the site is one file
// and no server has to know its addresses: it can be hosted as plain files under any folder.

export const PAGES = ["story", "experiments", "sources"] as const;
export type Page = (typeof PAGES)[number];

export interface Route {
  page: Page;
  /** A place on the page: the id of one of its sections. Null for the top. */
  section: string | null;
  /** One card of that section, where the address names one. */
  card: string | null;
  /** Whether the evidence of that section, or of that card, is open from the start. */
  evidence: boolean;
}

export const STORY: Route = { page: "story", section: null, card: null, evidence: false };

const NAME = /^[a-z0-9-]+$/;

/**
 * The page an address's hash names. `#/experiments` and `#/sources` are the two other pages. A further part
 * names a section (`#/sources/glossary`) and one more a card of it; `/evidence` at the end opens the
 * evidence of the section or card. Every other hash, such as `#step-4` or none, belongs to the story.
 */
export function readRoute(hash: string): Route {
  if (!hash.startsWith("#/")) return STORY;
  const parts = hash.slice(2).split("/").filter(Boolean);
  const [page, ...rest] = parts;
  if ((page !== "experiments" && page !== "sources") || !rest.every((part) => NAME.test(part))) return STORY;
  const evidence = rest.at(-1) === "evidence";
  const [section, card] = evidence ? rest.slice(0, -1) : rest;
  return { page, section: section ?? null, card: card ?? null, evidence: evidence && Boolean(section) };
}

/** The address of a page, or of a section of it. The story's is the top of the page. */
export function hrefOf(page: Page, section?: string): string {
  if (page === "story") return section ? `#${section}` : "#top";
  return section ? `#/${page}/${section}` : `#/${page}`;
}

/** The id a section of a page carries in the document. */
export const sectionId = (section: string) => `at-${section}`;
