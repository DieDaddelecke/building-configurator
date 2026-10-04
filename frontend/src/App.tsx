import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useEffect } from "react";
import { createBrowserRouter, RouterProvider, type RouteObject } from "react-router";

import { NichtGefunden } from "./components/NichtGefunden";
import { AnfrageDetail } from "./pages/buero/AnfrageDetail";
import { Anfragen } from "./pages/buero/Anfragen";
import { BueroLayout } from "./pages/buero/BueroLayout";
import { BueroStart } from "./pages/buero/BueroStart";
import { GrundstueckBuero, Grundstuecke } from "./pages/buero/Grundstuecke";
import { Hausmodell } from "./pages/buero/katalog/Hausmodell";
import { HausmodellVersion } from "./pages/buero/katalog/HausmodellVersion";
import { KatalogLayout } from "./pages/buero/katalog/KatalogLayout";
import { KatalogLinienOptionen } from "./pages/buero/katalog/KatalogLinienOptionen";
import { KatalogPreise } from "./pages/buero/katalog/KatalogPreise";
import { KatalogTyp } from "./pages/buero/katalog/KatalogTyp";
import { KatalogTypen } from "./pages/buero/katalog/KatalogTypen";
import { KeinZugang } from "./pages/buero/KeinZugang";
import { Regeln, Regelwerk } from "./pages/buero/Regeln";
import { GrundstueckSeite } from "./pages/grundstueck/GrundstueckSeite";
import { KonfiguratorSeite } from "./pages/konfigurator/KonfiguratorSeite";
import { Start } from "./pages/Start";
import { VorgangSeite } from "./pages/vorgang/VorgangSeite";
import { ZugangSeite } from "./pages/vorgang/ZugangSeite";

const PlanVorschau = lazy(() => import("./pages/dev/PlanVorschau").then((m) => ({ default: m.PlanVorschau })));

/** Weiter nach `/analyse/verwaltung…`: anderer Router, also mit Neuladen. */
function ZurVerwaltung() {
  useEffect(() => {
    window.location.replace(`/analyse${window.location.pathname}${window.location.search}`);
  }, []);
  return null;
}

export const routes: RouteObject[] = [
  { path: "/", element: <Start /> },
  { path: "/grundstueck", element: <GrundstueckSeite /> },
  { path: "/konfigurator", element: <KonfiguratorSeite /> },
  { path: "/vorgang", element: <VorgangSeite /> },
  { path: "/zugang", element: <ZugangSeite /> },
  { path: "/buero/kein-zugang", element: <KeinZugang /> },
  // Frühere Adresse der Verwaltung; sie liegt nur noch im Bereich Analyse (REFACTORING_PLAN S21)
  { path: "/verwaltung/*", element: <ZurVerwaltung /> },
  {
    path: "/buero",
    element: <BueroLayout />,
    children: [
      { index: true, element: <BueroStart /> },
      { path: "grundstuecke", element: <Grundstuecke /> },
      { path: "grundstuecke/:projectId", element: <GrundstueckBuero /> },
      { path: "regeln", element: <Regeln /> },
      { path: "regeln/:ruleSetId", element: <Regelwerk /> },
      { path: "anfragen", element: <Anfragen /> },
      { path: "anfragen/:projectId", element: <AnfrageDetail /> },
      {
        path: "katalog",
        element: <KatalogLayout />,
        children: [
          { index: true, element: <KatalogTypen /> },
          { path: "typen/:slug/:version", element: <KatalogTyp /> },
          { path: "linien-optionen", element: <KatalogLinienOptionen /> },
          { path: "preise", element: <KatalogPreise /> },
          { path: "hausmodell", element: <Hausmodell /> },
          { path: "hausmodell/:slug/:version", element: <HausmodellVersion /> },
        ],
      },
    ],
  },
  ...(import.meta.env.DEV
    ? [{ path: "/dev/plan", element: <Suspense><PlanVorschau /></Suspense> }]
    : []),
  { path: "*", element: <NichtGefunden /> },
];

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={createBrowserRouter(routes)} />
    </QueryClientProvider>
  );
}
