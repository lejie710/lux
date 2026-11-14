// The navigation bar: the mark and name on the left, the three pages on the right. The page in view is
// marked as the current one. The names of the two other pages come from the content.
import { EXPERIMENTS_LABEL, SOURCE_SCREENS } from "../content/load";
import { PAGES, hrefOf, type Page } from "../model/route";
import { Mark } from "./Mark";

/** What the navigation calls each page. The story's name is the site's own; the others are the content's. */
export const PAGE_NAMES: Record<Page, string> = {
  story: "The boot",
  experiments: EXPERIMENTS_LABEL,
  sources: SOURCE_SCREENS[0].title ?? "Sources",
};

export function Nav({ page = "story", inert = false }: { page?: Page; inert?: boolean }) {
  return (
    <nav className="lnav" aria-label="Site" inert={inert}>
      <a className="name" href={hrefOf("story")}>
        <Mark />
        Lux
      </a>
      <span className="links">
        {PAGES.map((p) => (
          <a key={p} href={hrefOf(p)} aria-current={p === page ? "page" : undefined}>
            {PAGE_NAMES[p]}
          </a>
        ))}
      </span>
    </nav>
  );
}
