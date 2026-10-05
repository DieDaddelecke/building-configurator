/**
 * Rechenkern im Browser (docs/PLAN_HAUSMODELL.md 3.1, L5): Vorschau von Preis, Regeln und Kandidaten ohne Server.
 * Maßgeblich bleibt der Server; beim Speichern schickt die Seite den Preis mit, der Server vergleicht ihn.
 * HM4 rechnet im Hauptthread (Demohaus: unter 5 ms für alle Kandidaten); der Web Worker kommt mit HM2.
 */

import {
  DOMAIN_VERSION,
  evaluate,
  type HouseCandidate,
  type HouseCatalog,
  type HouseConfiguration,
  type HouseEvaluation,
  type HouseSlotSelection,
  type HouseTemplate,
} from "@emprise/domain";

import type { HouseDocumentsOut } from "../api/hausKonfiguration";

export { DOMAIN_VERSION };

export interface Dokumente {
  template: HouseTemplate;
  catalog: HouseCatalog;
}

/** Festgehaltene Dokumente aus der API; der Server hat sie gegen den Vertrag geprüft. Die Typen der Antwort
 * weichen nur bei Tupeln ab (README, openapi-fetch), deshalb die Umwandlung. */
export function dokumente(documents: HouseDocumentsOut): Dokumente {
  return { template: documents.template as unknown as HouseTemplate, catalog: documents.catalog as unknown as HouseCatalog };
}

export function rechne(docs: Dokumente, configuration: HouseConfiguration): HouseEvaluation {
  return evaluate({ ...docs, configuration });
}

/** Alle Werte eines Slots mit Status und Preisdifferenz zur aktuellen Auswahl (P 8.2). */
export function kandidaten(docs: Dokumente, configuration: HouseConfiguration, slotId: string): readonly HouseCandidate[] {
  return evaluate({ ...docs, configuration, candidates: { slot_id: slotId, element_id: null } }).candidates ?? [];
}

/** Globaler Wert eines Slots in der Auswahl, sonst der Standard des Templates. */
export function gewaehlt(docs: Dokumente, configuration: HouseConfiguration, slotId: string): string | null {
  return configuration.selections[slotId]?.value?.option_value_id ?? docs.template.defaults[slotId] ?? null;
}

/** Auswahl mit neuem globalem Wert; der Standard des Templates entfernt die Wahl (nichts bleibt still gesetzt). */
export function mitWert(docs: Dokumente, configuration: HouseConfiguration, slotId: string, optionId: string): HouseConfiguration {
  const selections = { ...configuration.selections };
  const current = selections[slotId];
  const overrides = current && (Object.keys(current.room_overrides).length > 0 || Object.keys(current.element_overrides).length > 0);
  if (optionId === docs.template.defaults[slotId] && !overrides) {
    delete selections[slotId];
  } else {
    const next: HouseSlotSelection = {
      value: { type: "option", option_value_id: optionId },
      room_overrides: current?.room_overrides ?? {},
      element_overrides: current?.element_overrides ?? {},
    };
    selections[slotId] = next;
  }
  return { selections };
}

function kanonisch(value: unknown): unknown {
  if (Array.isArray(value)) return value.map(kanonisch);
  if (value && typeof value === "object") {
    return Object.fromEntries(Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([k, v]) => [k, kanonisch(v)]));
  }
  return value;
}

/** Zwei Auswahlen gleich, unabhängig von der Reihenfolge der Schlüssel. */
export function gleich(a: HouseConfiguration, b: HouseConfiguration): boolean {
  return JSON.stringify(kanonisch(a)) === JSON.stringify(kanonisch(b));
}
