// The page: the navigation bar, the first scene in one of its three modes, and the evidence panel.
import { useEffect, useRef, useState, type CSSProperties } from "react";
import { EvidencePanel } from "./components/EvidencePanel";
import { Nav } from "./components/Nav";
import { Stage, type OpenEvidence } from "./components/Stage";
import { CLOSED, closePanel, openPanel, openerId } from "./components/panel";
import { DISCLAIMER, OPENING, allScreens } from "./content/load";
import { STEPS, STEP_COUNT } from "./model/scene";
import type { Mode } from "./model/switches";
import { useStepScroll } from "./stage/useStepScroll";

export function App({ mode }: { mode: Mode }) {
  // A frozen step can ask for its evidence to be open from the start (?step=N&evidence), for checks.
  const [panel, setPanel] = useState(() => {
    if (mode.kind !== "frozen" || !mode.evidence || STEPS[mode.step].kind === "opening") return CLOSED;
    return openPanel(STEPS[mode.step].screen.id, openerId(STEPS[mode.step].id));
  });
  const screen = allScreens().find((s) => s.id === panel.screenId);

  const open: OpenEvidence = (screenId, opener, atClaims) => setPanel(openPanel(screenId, opener, atClaims));
  // The control that focus goes back to once the panel has closed.
  const returnTo = useRef<string | null>(null);
  const close = () => {
    const { state, focusId } = closePanel(panel);
    returnTo.current = focusId;
    setPanel(state);
  };

  // The page behind an open panel does not scroll, so the step under it cannot change. When the panel has
  // closed and the page is in reach again, focus goes back to the control that opened it, without moving
  // the page. It cannot go back sooner: an inert page refuses focus.
  useEffect(() => {
    document.documentElement.classList.toggle("panel-open", Boolean(screen));
    if (screen || !returnTo.current) return;
    document.getElementById(returnTo.current)?.focus({ preventScroll: true });
    returnTo.current = null;
  }, [screen]);

  return (
    <>
      {/* Behind an open panel the page is out of reach: no focus, no clicks, not read out. */}
      <Nav inert={Boolean(screen)} />
      <main id="top" inert={Boolean(screen)}>
        {mode.kind === "scroll" && <ScrollScene onOpen={open} />}
        {mode.kind === "still" &&
          STEPS.map((step, n) => (
            <section key={step.id} className="still-step">
              <Stage current={n} solo onOpen={open} />
            </section>
          ))}
        {mode.kind === "frozen" && (
          <section className="frozen-step">
            <Stage current={mode.step} solo onOpen={open} />
          </section>
        )}
      </main>
      {mode.kind !== "frozen" && (
        <footer className="closing" inert={Boolean(screen)}>
          <p>{OPENING.scope_note}</p>
          <p>{DISCLAIMER}</p>
        </footer>
      )}
      {screen && <EvidencePanel screen={screen} atClaims={panel.atClaims} onClose={close} />}
    </>
  );
}

/**
 * The scene as the reader scrolls it: a tall section whose stage stays pinned while a track of invisible
 * markers, one per step, passes the middle of the window.
 */
function ScrollScene({ onOpen }: { onOpen: OpenEvidence }) {
  const { i, markers } = useStepScroll();
  // The step is spoken only after it has changed once: a page that has just loaded says nothing.
  const moved = useRef(false);
  if (i !== 0) moved.current = true;
  const step = STEPS[i];
  const spoken = step.stop ? step.screen.statement.text : step.kind === "inside" ? step.screen.support : null;

  return (
    <section className="scene" style={{ "--steps": STEP_COUNT } as CSSProperties}>
      <div className="pin">
        <Stage current={i} onOpen={onOpen} />
      </div>
      <div className="track" aria-hidden="true">
        {STEPS.map((s, n) => (
          <div
            key={s.id}
            className="marker"
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
