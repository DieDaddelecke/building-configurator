/**
 * Rechenkern im Browser (docs/PLAN_HAUSMODELL.md 3.1, L5): Vorschau von Preis, Regeln und Kandidaten ohne Server.
 * Maßgeblich bleibt der Server; beim Speichern schickt die Seite den Preis mit, der Server vergleicht ihn.
 * HM4 rechnet im Hauptthread (Demohaus: unter 5 ms für alle Kandidaten); der Web Worker kommt mit HM2.
 */

import {
  activeLine,
  DOMAIN_VERSION,
  evaluate,
  roofPitchRange,
  type HouseCandidate,
  type HouseCatalog,
  type HouseConfiguration,
  type HouseEvaluation,
  type HouseSlotSelection,
  type HouseTemplate,
  type PitchRange,
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
  const value = configuration.selections[slotId]?.value;
  return value?.type === "option" ? value.option_value_id : (docs.template.defaults[slotId] ?? null);
}

/** Wirksame Zahl eines Zahl-Slots (Neigung, Drehung des Dachs) nach der Auflösung; `null`, wenn er für die
 * Dachform nicht gilt (E-HM-62). */
export function zahl(evaluation: HouseEvaluation, slotId: string): number | null {
  return evaluation.resolved.find((value) => value.slot_id === slotId)?.number ?? null;
}

/** Spanne der Neigung für den Regler; `null` beim Flachdach oder wenn sich die Auswahl nicht rechnen lässt. */
export function neigung(docs: Dokumente, configuration: HouseConfiguration): PitchRange | null {
  try {
    return roofPitchRange({ ...docs, configuration });
  } catch {
    return null;
  }
}

function ohne(configuration: HouseConfiguration, slotId: string): HouseConfiguration {
  const selections = { ...configuration.selections };
  delete selections[slotId];
  return { selections };
}

/** Auswahl mit einer Zahl; `null` oder der Standard der Dachform entfernen die Wahl (wie bei `mitWert`). */
export function mitZahl(docs: Dokumente, configuration: HouseConfiguration, slotId: string, value: number | null): HouseConfiguration {
  const rest = ohne(configuration, slotId);
  if (value === null) return rest;
  let standard: number | null = null;
  try {
    standard = zahl(rechne(docs, rest), slotId);
  } catch {
    // Lässt sich die Auswahl ohne die Zahl nicht rechnen, bleibt die Zahl gewählt
  }
  if (standard !== null && Math.abs(standard - value) < 1e-9) return rest;
  return { selections: { ...rest.selections, [slotId]: { value: { type: "number", value }, room_overrides: {}, element_overrides: {} } } };
}

/** Aktive Ausstattungslinie (Ergänzung 6, E-HM-14) oder `null`. */
export function linie(docs: Dokumente, configuration: HouseConfiguration): string | null {
  return activeLine({ ...docs, configuration });
}

/** Auswahl mit den Werten einer Linie; die Linie selbst wird nicht gespeichert. Werte gleich dem Standard des
 * Templates entfallen wie bei `mitWert`; Zahlen bleiben gesetzt, weil die Linie sie ausdrücklich verlangt. */
export function mitLinie(docs: Dokumente, configuration: HouseConfiguration, lineId: string): HouseConfiguration {
  const line = docs.catalog.lines.find((l) => l.id === lineId);
  if (!line) return configuration;
  let next = configuration;
  for (const [slotId, value] of Object.entries(line.presets)) {
    if (value.type === "option") {
      next = mitWert(docs, next, slotId, value.option_value_id);
    } else {
      const current = next.selections[slotId];
      next = {
        selections: {
          ...next.selections,
          [slotId]: { value, room_overrides: current?.room_overrides ?? {}, element_overrides: current?.element_overrides ?? {} },
        },
      };
    }
  }
  return next;
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
