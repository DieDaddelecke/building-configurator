// Ausstattungslinien (Ergänzung 6, E-HM-14): eine Voreinstellung mehrerer Slots auf ausdrückliche Wahl des Kunden.
// Eine Linie wird nicht gespeichert und hat keinen eigenen Preis; aktiv ist sie, solange jeder ihrer Werte global
// gewählt ist oder als Standard des Templates gilt.
import type { HouseCatalog, HouseConfiguration, HouseLine, HouseSlotValue, HouseTemplate } from "./contract.gen.ts";

/** Setzt die globalen Werte der Linie; Überschreibungen je Raum oder Element bleiben. */
export function applyLine(configuration: HouseConfiguration, line: HouseLine): HouseConfiguration {
  const selections = { ...configuration.selections };
  for (const [slotId, value] of Object.entries(line.presets)) {
    const current = selections[slotId] ?? { value: null, room_overrides: {}, element_overrides: {} };
    selections[slotId] = { ...current, value };
  }
  return { selections };
}

function holdsPreset(template: HouseTemplate, configuration: HouseConfiguration, slotId: string, preset: HouseSlotValue): boolean {
  const chosen = configuration.selections[slotId]?.value ?? null;
  if (preset.type === "number") return chosen?.type === "number" && chosen.value === preset.value;
  const effective = chosen?.type === "option" ? chosen.option_value_id : (template.defaults[slotId] ?? null);
  return effective === preset.option_value_id;
}

/** Erste Linie (nach `sort_order`), deren Werte alle gelten, sonst `null`. */
export function activeLine(input: { readonly template: HouseTemplate; readonly catalog: HouseCatalog; readonly configuration: HouseConfiguration }): string | null {
  const lines = [...input.catalog.lines].sort((a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id));
  const found = lines.find((line) =>
    Object.entries(line.presets).every(([slotId, preset]) => holdsPreset(input.template, input.configuration, slotId, preset)),
  );
  return found?.id ?? null;
}
