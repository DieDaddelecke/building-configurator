/**
 * Ausstattung des Hausmodells (docs/PLAN_HAUSMODELL.md 3.10, P 8.2): je Slot die Werte des Katalogs mit
 * Verfügbarkeit, Status und Preisunterschied zur aktuellen Wahl, gerechnet vom Kern im Browser. HM4 wählt einen Wert
 * für alle Elemente; die Wahl je Raum oder Element folgt mit HM2. Beträge brutto, auf 100 € gerundet, mit „ca.“
 * (E-HM-2). Die Wirkung auf den PLU kennt erst der Server; sie steht im Ergebnis der Prüfung.
 *
 * HM5: Ausstattungslinien als Voreinstellung mehrerer Slots (Ergänzung 6), die Neigung des Dachs als Regler in der
 * Spanne der Form und die Drehung des Dachs als vier Lagen (E-HM-62). Eine Form, die der Kern auf dem Grundriss
 * nicht erzeugt, ist mit ihrem Grund gesperrt (Ergänzung 4).
 */

import type { HouseCandidate, HouseConfiguration, HouseEvaluation, HouseSlot } from "@emprise/domain";
import type { TFunction } from "i18next";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";

import { formatNumber } from "../site/geo";
import { gewaehlt, kandidaten, linie, mitLinie, mitWert, mitZahl, neigung, rechne, zahl, type Dokumente } from "./kern";
import { aufpreis, euroDelta } from "./preis";
import { grad, label } from "./texte";

type Status = HouseCandidate["status"];

const RANG: Record<Status, number> = { valid: 0, valid_with_warnings: 1, with_deviations: 2, blocked: 3 };
const TON: Record<Status, string> = { valid: "t-mute", valid_with_warnings: "t-warn", with_deviations: "t-alert", blocked: "t-alert" };

interface AusstattungProps {
  docs: Dokumente;
  configuration: HouseConfiguration;
  onChange: (next: HouseConfiguration) => void;
  disabled?: boolean;
}

/** Warum ein Wert sperrt: das Dach entsteht nicht (mit Grund des Kerns), eine Regel oder ein Fehler des Kerns. */
export function sperrgrund(candidate: HouseCandidate, t: TFunction, lng: string): string | null {
  const result = candidate.rule_results.find((r) => r.outcome === "block");
  if (!result) return null;
  if (result.code === "roof_not_constructible") {
    const reason = String(result.params.reason ?? "");
    return t("houseConfigurator.equipment.notBuildable", { reason: t(`houseConfigurator.roofRefusal.${reason}`, { defaultValue: reason }) });
  }
  if (result.message) return label(result.message, lng);
  return t(`houseConfigurator.rule.${result.code}`, { defaultValue: result.code });
}

interface WertProps {
  candidate: HouseCandidate | undefined;
  selected: boolean;
  base: Status;
  vatRate: number;
  testId: string;
}

/** Aufpreis, Status und Verfügbarkeit eines Werts gegenüber der aktuellen Wahl. */
function Wirkung({ candidate, selected, base, vatRate, testId }: WertProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  if (!candidate) return null;
  const none = candidate.target_count > 0 && candidate.available_count === 0;
  const partly = candidate.available_count > 0 && candidate.available_count < candidate.target_count;
  const amount = aufpreis(candidate.price_delta, vatRate);
  // Ein Status zählt nur, wenn er schlechter ist als mit der aktuellen Wahl
  const worse = RANG[candidate.status] > RANG[base] ? candidate.status : null;
  const grund = sperrgrund(candidate, t, lng);
  const reason = candidate.unavailable_reason ? label(candidate.unavailable_reason, lng) : grund;
  return (
    <>
      {!selected && !none && (
        <span className="num t-mute whitespace-nowrap" data-testid={`aufpreis-${testId}`}>
          {amount === 0 ? t("houseConfigurator.equipment.same") : t("houseConfigurator.equipment.delta", { amount: euroDelta(amount, lng) })}
        </span>
      )}
      {worse && !none && (
        <span className={`text-xs ${TON[worse]} basis-full`}>
          {t(`houseConfigurator.equipment.status.${worse}`)}
          {worse === "blocked" && grund ? ` – ${grund}` : ""}
        </span>
      )}
      {(none || partly) && (
        <span className="text-xs t-warn basis-full" data-testid={`gesperrt-${testId}`}>
          {none
            ? t("houseConfigurator.equipment.unavailable")
            : t("houseConfigurator.equipment.partly", { available: candidate.available_count, total: candidate.target_count })}
          {reason ? ` – ${reason}` : ""}
        </span>
      )}
    </>
  );
}

interface SlotProps {
  docs: Dokumente;
  configuration: HouseConfiguration;
  slot: HouseSlot;
  candidates: readonly HouseCandidate[];
  evaluation: HouseEvaluation | null;
  onChange: (next: HouseConfiguration) => void;
  disabled: boolean;
}

function Werte({ docs, configuration, slot, candidates, onChange, disabled }: SlotProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const options = docs.catalog.option_values.filter((o) => o.slot_id === slot.id).sort((a, b) => a.sort_order - b.sort_order);
  const current = gewaehlt(docs, configuration, slot.id);
  const base = candidates.find((c) => c.option_value_id === current)?.status ?? "valid";
  return (
    <>
      {options.map((option) => {
        const candidate = candidates.find((c) => c.option_value_id === option.id);
        const selected = option.id === current;
        const none = Boolean(candidate && candidate.target_count > 0 && candidate.available_count === 0);
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
                  {option.id === docs.template.defaults[slot.id] && <span className="t-faint"> · {t("houseConfigurator.equipment.standard")}</span>}
                </span>
                <Wirkung candidate={candidate} selected={selected} base={base} vatRate={docs.catalog.vat_rate} testId={option.id} />
              </span>
              {option.description && <span className="text-xs t-mute">{label(option.description, lng)}</span>}
            </span>
          </label>
        );
      })}
      {slot.granularity !== "global" && <p className="text-xs t-faint m-0 mt-auto">{t("houseConfigurator.equipment.allElements")}</p>}
    </>
  );
}

/** Neigung als Regler in der Spanne der Form; gespeichert wird beim Loslassen, nicht bei jedem Schritt. */
function Neigung({ docs, configuration, slot, evaluation, onChange, disabled }: SlotProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const range = neigung(docs, configuration);
  const wirksam = evaluation ? zahl(evaluation, slot.id) : null;
  const [entwurf, setEntwurf] = useState<number | null>(null);
  if (!range) return <p className="text-sm t-mute m-0">{t("houseConfigurator.equipment.pitchFlat")}</p>;
  const wert = entwurf ?? wirksam ?? range.default;
  const uebernehmen = () => {
    if (entwurf === null) return;
    setEntwurf(null);
    if (entwurf !== wirksam) onChange(mitZahl(docs, configuration, slot.id, entwurf));
  };
  const gewaehlt = configuration.selections[slot.id] !== undefined;
  return (
    <div className="flex flex-col gap-2 text-sm">
      <input
        type="range"
        min={range.min}
        max={range.max}
        step={1}
        value={wert}
        disabled={disabled}
        aria-label={label(slot.name, lng)}
        aria-valuetext={grad(wert, lng)}
        data-testid="neigung"
        onChange={(event) => setEntwurf(Number(event.target.value))}
        onPointerUp={uebernehmen}
        onKeyUp={uebernehmen}
        onBlur={uebernehmen}
      />
      <span className="flex flex-wrap justify-between gap-x-3 t-ink">
        <span className="num" data-testid="neigung-wert">
          {t("houseConfigurator.equipment.pitch", {
            value: formatNumber(wert, lng, 0),
            min: formatNumber(range.min, lng, 0),
            max: formatNumber(range.max, lng, 0),
          })}
        </span>
        {gewaehlt && (
          <button type="button" className="btn btn-ghost" disabled={disabled} onClick={() => onChange(mitZahl(docs, configuration, slot.id, null))}>
            {t("houseConfigurator.equipment.reset")}
          </button>
        )}
      </span>
    </div>
  );
}

/** Drehung des Dachs: die vier Lagen mit Status und Preisunterschied (P 8.2 `evaluateCandidates`). */
function Drehung({ docs, configuration, slot, candidates, evaluation, onChange, disabled }: SlotProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  if (candidates.length === 0) return <p className="text-sm t-mute m-0">{t("houseConfigurator.equipment.rotationNone")}</p>;
  const current = evaluation ? zahl(evaluation, slot.id) : null;
  const base = candidates.find((c) => c.number === current)?.status ?? "valid";
  return (
    <>
      {candidates.map((candidate) => {
        const value = candidate.number ?? 0;
        const selected = value === current;
        const none = candidate.target_count > 0 && candidate.available_count === 0;
        return (
          <label key={value} className={`flex gap-3 items-start text-sm ${none && !selected ? "opacity-60" : ""}`}>
            <input
              type="radio"
              className="mt-1"
              name={`slot-${slot.id}`}
              value={value}
              checked={selected}
              disabled={disabled || (none && !selected)}
              onChange={() => onChange(mitZahl(docs, configuration, slot.id, value))}
            />
            <span className="flex flex-wrap justify-between gap-x-3 flex-1 min-w-0 t-ink">
              <span className="num">{t("houseConfigurator.equipment.rotation", { value: formatNumber(value, lng, 0) })}</span>
              <Wirkung candidate={candidate} selected={selected} base={base} vatRate={docs.catalog.vat_rate} testId={`${slot.id}-${value}`} />
            </span>
          </label>
        );
      })}
    </>
  );
}

/** Ausstattungslinien: eine Wahl setzt mehrere Slots; aktiv ist eine Linie, solange alle ihre Werte gelten. */
function Linien({ docs, configuration, evaluation, onChange, disabled }: Omit<SlotProps, "slot" | "candidates">) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const lines = [...docs.catalog.lines].sort((a, b) => a.sort_order - b.sort_order || a.id.localeCompare(b.id));
  const aktiv = linie(docs, configuration);
  if (lines.length === 0) return null;
  const preis = (lineId: string) => {
    if (!evaluation) return null;
    try {
      return aufpreis(rechne(docs, mitLinie(docs, configuration, lineId)).price.net_amount - evaluation.price.net_amount, docs.catalog.vat_rate);
    } catch {
      return null;
    }
  };
  return (
    <fieldset className="border bd bg-sheet p-5 m-0 flex flex-col gap-3 min-w-0" data-testid="linien">
      <legend className="eyebrow px-1">{t("houseConfigurator.equipment.line")}</legend>
      <p className="text-sm t-mute m-0">{t("houseConfigurator.equipment.lineIntro")}</p>
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
        {lines.map((line) => {
          const selected = line.id === aktiv;
          const amount = selected ? null : preis(line.id);
          return (
            <label key={line.id} className="flex gap-3 items-start text-sm">
              <input
                type="radio"
                className="mt-1"
                name="linie"
                value={line.id}
                checked={selected}
                disabled={disabled}
                onChange={() => onChange(mitLinie(docs, configuration, line.id))}
              />
              <span className="flex flex-col gap-0.5 flex-1 min-w-0">
                <span className="flex flex-wrap justify-between gap-x-3 t-ink">
                  <span>
                    {label(line.name, lng)}
                    {selected && <span className="t-faint"> · {t("houseConfigurator.equipment.lineActive")}</span>}
                  </span>
                  {amount !== null && (
                    <span className="num t-mute whitespace-nowrap" data-testid={`aufpreis-${line.id}`}>
                      {amount === 0 ? t("houseConfigurator.equipment.same") : t("houseConfigurator.equipment.delta", { amount: euroDelta(amount, lng) })}
                    </span>
                  )}
                </span>
                {line.description && <span className="text-xs t-mute">{label(line.description, lng)}</span>}
              </span>
            </label>
          );
        })}
      </div>
      {aktiv === null && <p className="text-xs t-faint m-0">{t("houseConfigurator.equipment.lineNone")}</p>}
    </fieldset>
  );
}

export function Ausstattung({ docs, configuration, onChange, disabled = false }: AusstattungProps) {
  const { i18n } = useTranslation();
  const lng = i18n.language;
  const slots = useMemo(() => [...docs.catalog.slots].sort((a, b) => a.sort_order - b.sort_order), [docs]);
  const evaluation = useMemo(() => {
    try {
      return rechne(docs, configuration);
    } catch {
      return null;
    }
  }, [docs, configuration]);
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
    <div className="flex flex-col gap-6">
      <Linien docs={docs} configuration={configuration} evaluation={evaluation} onChange={onChange} disabled={disabled} />
      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6" data-testid="ausstattung">
        {slots.map((slot) => {
          const props: SlotProps = { docs, configuration, slot, candidates: werte.get(slot.id) ?? [], evaluation, onChange, disabled };
          return (
            <fieldset key={slot.id} className="border bd bg-sheet p-5 m-0 flex flex-col gap-3 min-w-0" data-testid={`slot-${slot.id}`}>
              <legend className="eyebrow px-1">{label(slot.name, lng)}</legend>
              {slot.description && <p className="text-sm t-mute m-0">{label(slot.description, lng)}</p>}
              {slot.parameter === "roof_pitch" ? (
                <Neigung key={JSON.stringify(configuration)} {...props} />
              ) : slot.parameter === "roof_rotation" ? (
                <Drehung {...props} />
              ) : (
                <Werte {...props} />
              )}
            </fieldset>
          );
        })}
      </div>
    </div>
  );
}
