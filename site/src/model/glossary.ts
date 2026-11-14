// The glossary's filter: the entries whose term, other names or definition hold what was typed.

export interface Filterable {
  term: string;
  also: string[];
  definition: string;
}

/**
 * The entries that match a query, in their own order. Every word typed must be found, in any of the three
 * places, without regard to case. An empty query matches everything.
 */
export function filterGlossary<T extends Filterable>(entries: readonly T[], query: string): T[] {
  const wanted = query.toLowerCase().split(/\s+/).filter(Boolean);
  if (wanted.length === 0) return [...entries];
  return entries.filter((entry) => {
    const text = [entry.term, ...entry.also, entry.definition].join(" ").toLowerCase();
    return wanted.every((word) => text.includes(word));
  });
}
