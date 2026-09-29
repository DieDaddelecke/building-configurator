import "./styles/index.css";
import "./i18n";

import { lazy, StrictMode, Suspense } from "react";
import { createRoot } from "react-dom/client";

import { App } from "./App";

// Eine Anwendung, zwei Bereiche (REFACTORING_PLAN S2): Unter /analyse läuft „Emprise Analyse“ mit eigenem
// Router und Akzent, als eigener Chunk; alles andere ist der Konfigurator mit Büro. Zwischen den Bereichen
// wird per Link mit Neuladen gewechselt.
const AnalyseApp = lazy(() => import("./analyse/App").then((m) => ({ default: m.AnalyseApp })));
const pfad = window.location.pathname;
const analyse = pfad === "/analyse" || pfad.startsWith("/analyse/");

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    {analyse ? (
      <Suspense>
        <AnalyseApp />
      </Suspense>
    ) : (
      <App />
    )}
  </StrictMode>,
);
