import { useId, useMemo } from "react";
import { useTranslation } from "react-i18next";

import type { UploadCandidateOut } from "../../api/site";
import { txt } from "../../components/plan/Masskette";
import { boundsOf, PlanSvg, polygonPath, toSvg, type LocalPoint } from "../../components/plan/PlanSvg";
import { formatNumber } from "../../site/geo";

/** Höchstens so viele Konturen werden zu einem Grundstück vereinigt (`MAX_SELECTED` im Backend, UP17). */
export const MAX_AUSWAHL = 20;
/** Ein Punkt so nah am Rand gilt als auf dem Rand: Teilflächen teilen sich ihre Kanten. */
const RAND_M = 0.05;

/** Flächenschwerpunkt eines Rings, damit die Nummer in der Parzelle steht (Gauß'sche Formel). */
function schwerpunkt(ring: readonly LocalPoint[]): LocalPoint {
  let flaeche = 0;
  let x = 0;
  let y = 0;
  ring.slice(1).forEach(([x1, y1], i) => {
    const [x0, y0] = ring[i] ?? [x1, y1];
    const kreuz = x0 * y1 - x1 * y0;
    flaeche += kreuz;
    x += (x0 + x1) * kreuz;
    y += (y0 + y1) * kreuz;
  });
  if (Math.abs(flaeche) < 1e-9) return ring[0] ?? [0, 0];
  return [x / (3 * flaeche), y / (3 * flaeche)];
}

/** Liegt der Punkt im Ring oder auf seinem Rand? */
function imRing([px, py]: LocalPoint, ring: readonly LocalPoint[]): boolean {
  let innen = false;
  for (let i = 0; i < ring.length; i++) {
    const [xi, yi] = ring[i] ?? [0, 0];
    const [xj, yj] = ring[i === 0 ? ring.length - 1 : i - 1] ?? [0, 0];
    const dx = xj - xi;
    const dy = yj - yi;
    const laenge2 = dx * dx + dy * dy;
    const t = laenge2 > 0 ? Math.max(0, Math.min(1, ((px - xi) * dx + (py - yi) * dy) / laenge2)) : 0;
    if (Math.hypot(px - (xi + t * dx), py - (yi + t * dy)) <= RAND_M) return true;
    if (yi > py !== yj > py && px < (dx * (py - yi)) / dy + xi) innen = !innen;
  }
  return innen;
}

const aussenring = (candidate: UploadCandidateOut) =>
  (candidate.outline_overview as unknown as LocalPoint[][])[0] ?? [];

/**
 * Konturen, die innerhalb einer gewählten liegen – etwa das Gebäude in der Parzelle. Sie gehören schon zum
 * Grundstück, weil jeder Kandidat sein Außenring ist (UP13, UP17). Bei gleich großen Konturen enthält die mit
 * dem kleineren Index die andere, sonst enthielten sich zwei Kopien gegenseitig.
 */
export function enthalteneKonturen(
  candidates: readonly UploadCandidateOut[],
  selected: readonly number[],
): Set<number> {
  const gewaehlt = candidates.filter((c) => selected.includes(c.index));
  const rahmen = new Map(candidates.map((c) => [c.index, boundsOf(aussenring(c))]));
  const enthalten = new Set<number>();
  for (const innen of candidates) {
    const b = rahmen.get(innen.index);
    const ring = aussenring(innen);
    const drin = gewaehlt.some((aussen) => {
      if (aussen.index === innen.index) return false;
      if (aussen.area_m2 < innen.area_m2 || (aussen.area_m2 === innen.area_m2 && aussen.index > innen.index)) return false;
      const a = rahmen.get(aussen.index);
      if (!a || !b || b.minE < a.minE - RAND_M || b.maxE > a.maxE + RAND_M || b.minN < a.minN - RAND_M || b.maxN > a.maxN + RAND_M)
        return false;
      const aussenRing = aussenring(aussen);
      return ring.every((p) => imRing(p, aussenRing));
    });
    if (drin) enthalten.add(innen.index);
  }
  return enthalten;
}

/** Fläche der Auswahl vor der Übernahme: gewählte Konturen ohne die enthaltenen. Die genaue Fläche rechnet der
 * Server beim Vereinigen (Spalten geschlossen, vereinfacht). */
export function auswahlFlaeche(candidates: readonly UploadCandidateOut[], selected: readonly number[]): number {
  const enthalten = enthalteneKonturen(candidates, selected);
  return candidates
    .filter((c) => selected.includes(c.index) && !enthalten.has(c.index))
    .reduce((summe, c) => summe + c.area_m2, 0);
}

export function bezeichnung(candidate: UploadCandidateOut): string {
  return candidate.name ?? candidate.layer ?? `#${candidate.index + 1}`;
}

interface KonturWahlProps {
  candidates: readonly UploadCandidateOut[];
  selected: readonly number[];
  onToggle: (index: number) => void;
}

/**
 * Übersicht aller Konturen einer Datei auf einem gemeinsamen Ursprung (`outline_overview`, UP14): Die Parzelle
 * wird zwischen ihren Nachbarn angeklickt, wie auf dem Katasterauszug. Große Flächen liegen unten, kleine
 * darüber – ein Klick ins Haus trifft das Haus, daneben die Parzelle. Ein Klick nimmt eine Fläche in die Auswahl,
 * ein zweiter heraus; mehrere gewählte Flächen werden zu einem Grundstück vereinigt (UP17). Die Liste darunter
 * ist der Weg ohne Maus.
 */
export function KonturWahl({ candidates, selected, onToggle }: KonturWahlProps) {
  const { t, i18n } = useTranslation();
  const listId = useId();
  const alle = candidates.flatMap((c) => (c.outline_overview as unknown as LocalPoint[][]).flat());
  const bounds = boundsOf(alle);
  const groesse = Math.max(bounds.maxE - bounds.minE, bounds.maxN - bounds.minN, 10);
  const schrift = groesse / 50;
  const reihenfolge = candidates
    .map((candidate) => ({ candidate, ringe: candidate.outline_overview as unknown as LocalPoint[][] }))
    .sort((a, b) => b.candidate.area_m2 - a.candidate.area_m2);
  const enthalten = useMemo(() => enthalteneKonturen(candidates, selected), [candidates, selected]);
  const voll = selected.length >= MAX_AUSWAHL;
  const umschalten = (index: number) => {
    if (selected.includes(index) || !voll) onToggle(index);
  };
  const text = (candidate: UploadCandidateOut) =>
    `${bezeichnung(candidate)} · ${formatNumber(candidate.area_m2, i18n.language)} m²`;

  return (
    <div className="flex flex-col gap-3">
      <div className="karte p-2">
        <PlanSvg bounds={bounds} rand={groesse * 0.03} label={t("analyse.upload.overview")}>
          {reihenfolge.map(({ candidate, ringe: r }) => {
            const gewaehlt = selected.includes(candidate.index);
            const teil = gewaehlt || enthalten.has(candidate.index);
            const betont = gewaehlt && !enthalten.has(candidate.index);
            return (
              <path
                key={candidate.index}
                d={polygonPath(r)}
                fillRule="evenodd"
                data-testid={`kontur-${candidate.index}`}
                data-auswahl={betont ? "gewaehlt" : teil ? "enthalten" : undefined}
                onClick={() => umschalten(candidate.index)}
                style={{
                  cursor: "pointer",
                  fill: teil ? "var(--accent-tint)" : "var(--sheet)",
                  fillOpacity: teil ? 1 : 0.6,
                  stroke: teil ? "var(--accent)" : "var(--line-strong)",
                  strokeWidth: ((betont ? 3 : 1) * groesse) / 700,
                }}
              >
                <title>{text(candidate)}</title>
              </path>
            );
          })}
          <g aria-hidden="true" style={{ pointerEvents: "none" }}>
            {reihenfolge
              .filter(({ candidate }) => candidate.name)
              .map(({ candidate, ringe: r }) => {
                const aussen = r[0];
                if (!aussen) return null;
                const [x, y] = toSvg(schwerpunkt(aussen));
                return (
                  <text
                    key={candidate.index}
                    x={x}
                    y={y + schrift * 0.35}
                    textAnchor="middle"
                    style={txt(selected.includes(candidate.index) ? "var(--accent)" : "var(--ink)", schrift, { fontWeight: 500 })}
                  >
                    {candidate.name}
                  </text>
                );
              })}
          </g>
        </PlanSvg>
      </div>
      <p className="t-mute text-xs m-0">{t("analyse.upload.selectionHint")}</p>
      <div className="flex flex-col gap-1">
        <label htmlFor={listId} className="text-sm">
          {t("analyse.upload.list")}
        </label>
        <select
          id={listId}
          className="field"
          value=""
          disabled={voll}
          onChange={(event) => {
            if (event.target.value !== "") umschalten(Number(event.target.value));
          }}
        >
          <option value="" disabled>
            {t("analyse.upload.pick")}
          </option>
          {candidates
            .filter((candidate) => !selected.includes(candidate.index))
            .map((candidate) => (
              <option key={candidate.index} value={candidate.index}>
                {text(candidate)}
              </option>
            ))}
        </select>
        {voll && <p className="t-mute text-xs m-0">{t("analyse.upload.maxSelected", { count: MAX_AUSWAHL })}</p>}
      </div>
      {selected.length > 0 && (
        <ul className="flex flex-wrap gap-2 m-0 p-0 list-none" aria-label={t("analyse.upload.selection")}>
          {selected.map((index) => {
            const candidate = candidates.find((c) => c.index === index);
            if (!candidate) return null;
            return (
              <li key={index}>
                <button
                  type="button"
                  className="chip inline-flex items-center gap-2"
                  aria-pressed="true"
                  aria-label={t("analyse.upload.remove", { name: text(candidate) })}
                  onClick={() => onToggle(index)}
                >
                  <span>{text(candidate)}</span>
                  <span aria-hidden="true">×</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
