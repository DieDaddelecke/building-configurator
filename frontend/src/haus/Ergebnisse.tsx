/**
 * Ergebnis der Prüfung (docs/PLAN_HAUSMODELL.md 3.7): Status der Konfiguration und alle Ergebnisse nach Art –
 * sperrende Katalogregeln, Abweichungen vom PLU, offene Prüfpunkte, Hinweise. Eine Abweichung verhindert nichts;
 * die Konfiguration bleibt gespeichert (E-HM-6). Dazu die Werte, die der Kern für einzelne Elemente nicht anwenden
 * konnte (`ResolutionNote`). Es gilt der gespeicherte Stand; eine laufende Änderung kennzeichnet `veraltet`.
 */

import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import type { HouseConfigurationOut } from "../api/hausKonfiguration";
import { checkText } from "../configuration/format";
import type { Dokumente } from "./kern";
import { grad, label } from "./texte";

type Gruppe = "block" | "deviation" | "warning" | "info";
const GRUPPEN: readonly Gruppe[] = ["block", "deviation", "warning", "info"];
const GRUPPEN_TON: Record<Gruppe, string> = { block: "t-alert", deviation: "t-alert", warning: "t-warn", info: "t-mute" };
const STATUS_TON = { valid: "bg-sheet border bd", valid_with_warnings: "bg-warn", with_deviations: "bg-alert", blocked: "bg-alert" };

type Regel = HouseConfigurationOut["rule_results"][number];
type Notiz = HouseConfigurationOut["notes"][number];

function regelText(result: Regel, t: TFunction, lng: string): string {
  return result.message ? label(result.message, lng) : t(`houseConfigurator.rule.${result.code}`, { defaultValue: result.code });
}

/** Notizen je Slot, Wert und angewandtem Wert zusammengefasst: „Fenster: … gilt für 3 Elemente nicht“. Bei
 * Neigung und Drehung des Dachs stehen Zahlen statt Werten (E-HM-62). */
function notizen(notes: readonly Notiz[], docs: Dokumente | null, t: TFunction, lng: string): string[] {
  const name = (id: string) => {
    const option = docs?.catalog.option_values.find((o) => o.id === id);
    return option ? label(option.name, lng) : id;
  };
  const zahl = (value: number | null) => (value === null ? "–" : grad(value, lng));
  const slotName = (id: string) => {
    const slot = docs?.catalog.slots.find((s) => s.id === id);
    return slot ? label(slot.name, lng) : id;
  };
  const groups = new Map<string, { note: Notiz; count: number }>();
  for (const note of notes) {
    const key = [note.code, note.slot_id, note.skipped_value_ids.join(","), note.skipped_number, note.applied_value_id, note.applied_number].join("|");
    const group = groups.get(key);
    if (group) group.count += 1;
    else groups.set(key, { note, count: 1 });
  }
  return [...groups.values()].map(({ note, count }) => {
    const text = t(`houseConfigurator.results.note.${note.code}`, {
      slot: slotName(note.slot_id),
      value: note.skipped_value_ids.length > 0 ? note.skipped_value_ids.map(name).join(", ") : zahl(note.skipped_number),
      applied: note.applied_value_id !== null ? name(note.applied_value_id) : zahl(note.applied_number),
      count,
    });
    return note.reason ? `${text} ${label(note.reason, lng)}` : text;
  });
}

interface ErgebnisseProps {
  current: HouseConfigurationOut;
  docs: Dokumente | null;
  /** Bezeichnungen für `params.subject` der Prüfungen (Haustyp). */
  names: Record<string, string>;
  veraltet: boolean;
}

export function Ergebnisse({ current, docs, names, veraltet }: ErgebnisseProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const texte: Record<Gruppe, string[]> = { block: [], deviation: [], warning: [], info: [] };
  for (const result of current.rule_results) texte[result.outcome].push(regelText(result, t, lng));
  for (const result of current.site_results) texte[result.outcome].push(checkText(result.check, t, lng, names));
  texte.info.push(...notizen(current.notes, docs, t, lng));
  const status = current.status;

  return (
    <section aria-labelledby="haus-ergebnis" className="flex flex-col gap-4" data-testid="ergebnis">
      <h2 id="haus-ergebnis" className="eyebrow m-0">
        {t("houseConfigurator.results.title")}
      </h2>
      {status && (
        <div className={`${STATUS_TON[status]} t-ink px-4 py-3 text-sm max-w-prose`} data-testid="haus-status">
          <strong>{t(`houseConfigurator.results.status.${status}`)}</strong> · {t(`houseConfigurator.results.statusText.${status}`)}
        </div>
      )}
      {veraltet && (
        <p className="text-sm t-mute m-0" role="status">
          {t("houseConfigurator.results.stale")}
        </p>
      )}
      {current.site_changed && <p className="text-sm t-warn m-0">{t("houseConfigurator.results.siteChanged")}</p>}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {GRUPPEN.filter((gruppe) => texte[gruppe].length > 0).map((gruppe) => (
          <div key={gruppe} className="flex flex-col gap-1" data-testid={`ergebnis-${gruppe}`}>
            <div className={`eyebrow ${GRUPPEN_TON[gruppe]}`}>{t(`houseConfigurator.results.group.${gruppe}`)}</div>
            <ul className="m-0 pl-5 text-sm flex flex-col gap-1">
              {texte[gruppe].map((text, index) => (
                <li key={`${gruppe}-${index}`} className={gruppe === "info" ? "t-mute" : "t-ink"}>
                  {text}
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </section>
  );
}
