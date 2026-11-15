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

/** `plain`: the page in view is the scrolled story, which has a plain page beside it for those who want one. */
export function Nav({
  page = "story",
  inert = false,
  plain = false,
}: {
  page?: Page;
  inert?: boolean;
  plain?: boolean;
}) {
  return (
    <nav className="lnav" aria-label="Site" inert={inert}>
      {/* The first thing a keyboard reaches: the whole story as a page that is read from top to bottom. */}
      {plain && (
        <a className="skip" href="?static">
          Read the boot as a plain page
        </a>
      )}
      <a className="name" href={hrefOf("story")}>
        <Mark />
        {/* In a very narrow window the word gives its room to the three links; the link keeps its name. */}
        <span className="name-word">Lux</span>
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
