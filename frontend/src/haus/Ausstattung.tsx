/**
 * Ausstattung des Hausmodells (docs/PLAN_HAUSMODELL.md 3.10, P 8.2): je Slot die Werte des Katalogs mit
 * Verfügbarkeit, Status und Preisunterschied zur aktuellen Wahl, gerechnet vom Kern im Browser. HM4 wählt einen Wert
 * für alle Elemente; die Wahl je Raum oder Element folgt mit HM2. Beträge brutto, auf 100 € gerundet, mit „ca.“
 * (E-HM-2). Die Wirkung auf den PLU kennt erst der Server; sie steht im Ergebnis der Prüfung.
 */

import type { HouseCandidate, HouseConfiguration } from "@emprise/domain";
import { useMemo } from "react";
import { useTranslation } from "react-i18next";

import { gewaehlt, kandidaten, mitWert, type Dokumente } from "./kern";
import { aufpreis, euroDelta } from "./preis";
import { label } from "./texte";

type Status = HouseCandidate["status"];

const RANG: Record<Status, number> = { valid: 0, valid_with_warnings: 1, with_deviations: 2, blocked: 3 };
const TON: Record<Status, string> = { valid: "t-mute", valid_with_warnings: "t-warn", with_deviations: "t-alert", blocked: "t-alert" };

interface AusstattungProps {
  docs: Dokumente;
  configuration: HouseConfiguration;
  onChange: (next: HouseConfiguration) => void;
  disabled?: boolean;
}

export function Ausstattung({ docs, configuration, onChange, disabled = false }: AusstattungProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const slots = useMemo(() => [...docs.catalog.slots].sort((a, b) => a.sort_order - b.sort_order), [docs]);
  const werte = useMemo(() => {
    const result = new Map<string, readonly HouseCandidate[]>();
    for (const slot of slots) {
      try {
        result.set(slot.id, kandidaten(docs, configuration, slot.id));
      } catch {
        // Ohne Kandidaten bleibt der Slot wählbar; der Server prüft beim Speichern
        result.set(slot.id, []);
      }
    }
    return result;
  }, [docs, configuration, slots]);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6" data-testid="ausstattung">
      {slots.map((slot) => {
        const options = docs.catalog.option_values.filter((o) => o.slot_id === slot.id).sort((a, b) => a.sort_order - b.sort_order);
        const current = gewaehlt(docs, configuration, slot.id);
        const candidates = werte.get(slot.id) ?? [];
        const base = candidates.find((c) => c.option_value_id === current)?.status ?? "valid";
        return (
          <fieldset key={slot.id} className="border bd bg-sheet p-5 m-0 flex flex-col gap-3 min-w-0" data-testid={`slot-${slot.id}`}>
            <legend className="eyebrow px-1">{label(slot.name, lng)}</legend>
            {slot.description && <p className="text-sm t-mute m-0">{label(slot.description, lng)}</p>}
            {options.map((option) => {
              const candidate = candidates.find((c) => c.option_value_id === option.id);
              const selected = option.id === current;
              const none = Boolean(candidate && candidate.target_count > 0 && candidate.available_count === 0);
              const partly = Boolean(candidate && candidate.available_count > 0 && candidate.available_count < candidate.target_count);
              const amount = candidate ? aufpreis(candidate.price_delta, docs.catalog.vat_rate) : null;
              // Ein Status zählt nur, wenn er schlechter ist als mit der aktuellen Wahl
              const worse = candidate && RANG[candidate.status] > RANG[base] ? candidate.status : null;
              return (
                <label key={option.id} className={`flex gap-3 items-start text-sm ${none && !selected ? "opacity-60" : ""}`}>
                  <input
                    type="radio"
                    className="mt-1"
                    name={`slot-${slot.id}`}
                    value={option.id}
                    checked={selected}
                    disabled={disabled || (none && !selected)}
                    onChange={() => onChange(mitWert(docs, configuration, slot.id, option.id))}
                  />
                  <span className="flex flex-col gap-0.5 flex-1 min-w-0">
                    <span className="flex flex-wrap justify-between gap-x-3 t-ink">
                      <span>
                        {label(option.name, lng)}
                        {option.id === docs.template.defaults[slot.id] && (
                          <span className="t-faint"> · {t("houseConfigurator.equipment.standard")}</span>
                        )}
                      </span>
                      {!selected && amount !== null && (
                        <span className="num t-mute whitespace-nowrap" data-testid={`aufpreis-${option.id}`}>
                          {amount === 0
                            ? t("houseConfigurator.equipment.same")
                            : t("houseConfigurator.equipment.delta", { amount: euroDelta(amount, lng) })}
                        </span>
                      )}
                    </span>
                    {option.description && <span className="text-xs t-mute">{label(option.description, lng)}</span>}
                    {worse && <span className={`text-xs ${TON[worse]}`}>{t(`houseConfigurator.equipment.status.${worse}`)}</span>}
                    {(none || partly) && (
                      <span className="text-xs t-warn">
                        {none
                          ? t("houseConfigurator.equipment.unavailable")
                          : t("houseConfigurator.equipment.partly", { available: candidate!.available_count, total: candidate!.target_count })}
                        {candidate?.unavailable_reason ? ` – ${label(candidate.unavailable_reason, lng)}` : ""}
                      </span>
                    )}
                  </span>
                </label>
              );
            })}
            {slot.granularity !== "global" && <p className="text-xs t-faint m-0 mt-auto">{t("houseConfigurator.equipment.allElements")}</p>}
          </fieldset>
        );
      })}
    </div>
  );
}
