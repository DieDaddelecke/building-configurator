/**
 * Der Bereich Analyse hängt die Verwaltung unter `/verwaltung/*` ein (Router mit Basis `/analyse`). Feste Pfade,
 * weil relative Links in einer Splat-Route von der vollen Adresse aus aufgelöst werden (`.` wäre auf jeder
 * Unterseite aktiv).
 */
export const VERWALTUNG_PFAD = "/verwaltung";
export const LISTEN_PFAD = `${VERWALTUNG_PFAD}/referenzlisten`;
