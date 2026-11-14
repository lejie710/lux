// The entry point: the fonts, the stylesheet, and the app mounted on the page.
import "@fontsource-variable/inter";
import "@fontsource/ibm-plex-mono/500.css";
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { readRoute } from "./model/route";
import { STEP_COUNT } from "./model/scene";
import { modeFor, readSwitches } from "./model/switches";
import "./styles/lux.css";
import "./styles/pages.css";

// How the scene is drawn is decided once, before anything is on the page: pinned and scrolled, as still
// sections (?static, or the reader prefers reduced motion), or frozen at one step (?step=N).
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const mode = modeFor(readSwitches(location.search, STEP_COUNT), reducedMotion);
// Which page is shown is read from the address after the hash sign: the story, the experiments or the sources.
const route = readRoute(location.hash);
document.documentElement.dataset.mode = route.page === "story" ? mode.kind : "page";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App mode={mode} route={route} />
  </StrictMode>,
);
