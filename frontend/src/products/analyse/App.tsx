import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { createBrowserRouter, RouterProvider, type RouteObject } from "react-router";

import { NichtGefunden } from "../../components/NichtGefunden";
import { AnalyseLayout } from "./AnalyseLayout";
import { Projekte } from "./Projekte";
import { ProjektSeite } from "./ProjektSeite";

/** Eigener Router des Analyse-Produkts (AN0, erweitert in AN1). Er lädt bewusst nichts aus
 *  `src/App.tsx`, damit die Seiten des Hauskonfigurators nicht in dieses Bündel geraten.
 *  PLU hochladen (AN2) und Baurahmen (AN3) kommen als weitere Schritte im Projekt dazu. */
export const routes: RouteObject[] = [
  {
    path: "/",
    element: <AnalyseLayout />,
    children: [
      { index: true, element: <Projekte /> },
      { path: "projekt/:projectId", element: <ProjektSeite /> },
    ],
  },
  { path: "*", element: <NichtGefunden /> },
];

const queryClient = new QueryClient({
  defaultOptions: { queries: { retry: 1, refetchOnWindowFocus: false } },
});

export function AnalyseApp() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={createBrowserRouter(routes)} />
    </QueryClientProvider>
  );
}
