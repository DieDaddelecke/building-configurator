import "./styles.css";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { createBrowserRouter, RouterProvider, type RouteObject } from "react-router";

import { NichtGefunden } from "../components/NichtGefunden";
import { AnalyseLayout } from "./AnalyseLayout";
import { OrganisationSeite } from "./OrganisationSeite";
import { Projekte } from "./Projekte";
import { ProjektSeite } from "./ProjektSeite";
import { VerwaltungSeite } from "./VerwaltungSeite";

/** Router des Bereichs „Emprise Analyse“ unter `/analyse` (AN0, AN1; eine Anwendung seit REFACTORING_PLAN S2).
 *  `src/main.tsx` lädt ihn als eigenen Chunk; er importiert nichts aus `src/App.tsx`, damit die Seiten des
 *  Konfigurators nicht mitgeladen werden. Pfade hier sind relativ zu `ANALYSE_BASE`. */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AnalyseLayout />,
    children: [
      { index: true, element: <Projekte /> },
      { path: "projekt/:projectId", element: <ProjektSeite /> },
      // Mitglieder, Erscheinungsbild, Verbrauch und API-Schlüssel (AN6)
      { path: "organisation", element: <OrganisationSeite /> },
      // Gemeinsame Verwaltung beider Produkte (PLAN_G2_VOLLSTAENDIGKEIT 3.9)
      { path: "verwaltung/*", element: <VerwaltungSeite /> },
    ],
  },
  { path: "*", element: <NichtGefunden /> },
];

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export const ANALYSE_BASE = "/analyse";

export function AnalyseApp() {
  const [router] = useState(() => createBrowserRouter(routes, { basename: ANALYSE_BASE }));
  useEffect(() => {
    document.title = "Emprise Analyse";
  }, []);
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
