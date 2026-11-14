// The site: the navigation bar, one of the three pages, and the evidence panel. The story is drawn in one
// of its three modes; the experiments and the sources are plain pages that scroll.
import { useEffect, useRef, useState } from "react";
import { EvidencePanel } from "./components/EvidencePanel";
import { Experiments } from "./components/Experiments";
import { Nav, PAGE_NAMES } from "./components/Nav";
import { Overview } from "./components/Overview";
import { Sources } from "./components/Sources";
import { Stage, type OpenEvidence } from "./components/Stage";
import { CLOSED, closePanel, openPanel, openerId } from "./components/panel";
import { DISCLAIMER, OPENING, findSubject, subjectId } from "./content/load";
import { STORY, readRoute, sectionId, type Route } from "./model/route";
import { STEPS, STEP_COUNT } from "./model/scene";
import type { Mode } from "./model/switches";
import { useStepScroll } from "./stage/useStepScroll";

export const SITE_TITLE = "Lux: what your laptop does before it wakes";

export function App({ mode, route: first = STORY }: { mode: Mode; route?: Route }) {
  const [route, setRoute] = useState(first);
  const { page } = route;
  // Evidence can be asked for from the start, for checks: by a frozen step of the story (?step=N&evidence),
  // or by the address of a section of another page (#/experiments/<section>/evidence).
  const [panel, setPanel] = useState(() => {
    if (page !== "story") {
      const id = route.evidence && route.section ? subjectId(route.section, route.card ?? undefined) : null;
      return id && findSubject(id) ? openPanel(id, openerId(id)) : CLOSED;
    }
    if (mode.kind !== "frozen" || !mode.evidence || STEPS[mode.step].kind === "opening") return CLOSED;
    return openPanel(STEPS[mode.step].screen.id, openerId(STEPS[mode.step].id));
  });
  const subject = findSubject(panel.screenId);

  const open: OpenEvidence = (screenId, opener, atClaims) => setPanel(openPanel(screenId, opener, atClaims));
  // The control that focus goes back to once the panel has closed.
  const returnTo = useRef<string | null>(null);
  const close = () => {
    const { state, focusId } = closePanel(panel);
    returnTo.current = focusId;
    setPanel(state);
  };

  // The address after the hash sign names the page. A panel does not outlive the page it was opened on.
  useEffect(() => {
    const onHashChange = () => {
      setRoute(readRoute(window.location.hash));
      setPanel(CLOSED);
    };
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  // A new page starts at its top, or at the section its address names. Within the story the browser and the
  // scroll hook place the step an address names; the still page and the strip after the story are placed here.
  const section = route.section;
  useEffect(() => {
    document.documentElement.dataset.mode = page === "story" ? mode.kind : "page";
    document.title = page === "story" ? SITE_TITLE : `${PAGE_NAMES[page]} · Lux`;
    if (page !== "story") {
      const target = section ? document.getElementById(sectionId(section)) : null;
      if (target) target.scrollIntoView({ block: "start", behavior: "instant" });
      else window.scrollTo({ top: 0, behavior: "instant" });
      return;
    }
    const id = window.location.hash.slice(1);
    const placedByScroll = mode.kind === "scroll" && id.startsWith("step-");
    if (id && id !== "top" && !placedByScroll)
      document.getElementById(id)?.scrollIntoView({ block: "start", behavior: "instant" });
    else if (!placedByScroll) window.scrollTo({ top: 0, behavior: "instant" });
  }, [page, section, mode.kind]);

  // The page behind an open panel does not scroll, so the step under it cannot change. When the panel has
  // closed and the page is in reach again, focus goes back to the control that opened it, without moving
  // the page. It cannot go back sooner: an inert page refuses focus.
  useEffect(() => {
    document.documentElement.classList.toggle("panel-open", Boolean(subject));
    if (subject || !returnTo.current) return;
    document.getElementById(returnTo.current)?.focus({ preventScroll: true });
    returnTo.current = null;
  }, [subject]);

  // After a change of page (not on the first one) focus goes to the new page's heading, so the change is
  // read out and the next Tab starts at the top of the new page.
  const shownPage = useRef(page);
  useEffect(() => {
    if (shownPage.current === page) return;
    shownPage.current = page;
    document.querySelector<HTMLElement>("main h1")?.focus({ preventScroll: true });
  }, [page]);

  const behind = Boolean(subject);
  const frozen = page === "story" && mode.kind === "frozen";
  return (
    <>
      {/* Behind an open panel the page is out of reach: no focus, no clicks, not read out. */}
      <Nav page={page} inert={behind} plain={page === "story" && mode.kind === "scroll"} />
      <main id="top" inert={behind} data-page={page}>
        {page === "experiments" && <Experiments onOpen={open} />}
        {page === "sources" && <Sources onOpen={open} />}
        {page === "story" && mode.kind === "scroll" && <ScrollScene onOpen={open} />}
        {page === "story" &&
          mode.kind === "still" &&
          STEPS.map((step, n) => (
            <section key={step.id} className="still-step" id={`step-${n}`}>
              <Stage current={n} solo anchors={false} onOpen={open} />
            </section>
          ))}
        {page === "story" && mode.kind === "frozen" && (
          <section className="frozen-step">
            <Stage current={mode.step} solo anchors={false} onOpen={open} />
          </section>
        )}
        {page === "story" && !frozen && <Overview />}
      </main>
      {!frozen && (
        <footer className="closing" inert={behind}>
          <p>{OPENING.scope_note}</p>
          <p>{DISCLAIMER}</p>
        </footer>
      )}
      {subject && (
        <EvidencePanel screen={subject.screen} card={subject.card} atClaims={panel.atClaims} onClose={close} />
      )}
    </>
  );
}

/**
 * The story as the reader scrolls it: a tall section whose stage stays pinned while a track of invisible
 * markers, one per step, passes the middle of the window.
 */
function ScrollScene({ onOpen }: { onOpen: OpenEvidence }) {
  const { i, markers, go } = useStepScroll();
  // The step is spoken only after it has changed once: a page that has just loaded says nothing.
  const moved = useRef(false);
  if (i !== 0) moved.current = true;
  const step = STEPS[i];
  const spoken = step.stop ? step.screen.statement.text : step.kind === "inside" ? step.screen.support : null;

  return (
    <section className="scene">
      <div className="pin">
        <Stage current={i} onOpen={onOpen} onStep={go} />
      </div>
      <div className="track" aria-hidden="true">
        {STEPS.map((s, n) => (
          <div
            key={s.id}
            className="marker"
            // A further screen of the same stop is a shorter stretch of scrolling than a new stop.
            data-length={n === 0 ? "long" : s.screenAt > 1 ? "short" : "full"}
            id={`step-${n}`}
            data-index={n}
            ref={(el) => {
              markers.current[n] = el;
            }}
          />
        ))}
      </div>
      <p className="sr-only" role="status">
        {moved.current ? `Step ${i + 1} of ${STEP_COUNT}. ${spoken ?? (step.screen as typeof OPENING).title.text}` : ""}
      </p>
    </section>
  );
}
