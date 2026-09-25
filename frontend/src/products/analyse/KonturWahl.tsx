import { useId } from "react";
import { useTranslation } from "react-i18next";

import type { UploadCandidateOut } from "../../api/site";
import { txt } from "../../components/plan/Masskette";
import { boundsOf, PlanSvg, polygonPath, toSvg, type LocalPoint } from "../../components/plan/PlanSvg";
import { formatNumber } from "../../site/geo";

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

export function bezeichnung(candidate: UploadCandidateOut): string {
  return candidate.name ?? candidate.layer ?? `#${candidate.index + 1}`;
}

interface KonturWahlProps {
  candidates: readonly UploadCandidateOut[];
  selected: number | null;
  onSelect: (index: number) => void;
}

/**
 * Übersicht aller Konturen einer Datei auf einem gemeinsamen Ursprung (`outline_overview`, UP14): Die Parzelle
 * wird zwischen ihren Nachbarn angeklickt, wie auf dem Katasterauszug. Große Flächen liegen unten, kleine
 * darüber – ein Klick ins Haus trifft das Haus, daneben die Parzelle. Die Auswahlliste darunter ist der Weg
 * ohne Maus.
 */
export function KonturWahl({ candidates, selected, onSelect }: KonturWahlProps) {
  const { t, i18n } = useTranslation();
  const listId = useId();
  const alle = candidates.flatMap((c) => (c.outline_overview as unknown as LocalPoint[][]).flat());
  const bounds = boundsOf(alle);
  const groesse = Math.max(bounds.maxE - bounds.minE, bounds.maxN - bounds.minN, 10);
  const schrift = groesse / 50;
  const reihenfolge = candidates
    .map((candidate) => ({ candidate, ringe: candidate.outline_overview as unknown as LocalPoint[][] }))
    .sort((a, b) => b.candidate.area_m2 - a.candidate.area_m2);

  return (
    <div className="flex flex-col gap-3">
      <div className="karte p-2">
        <PlanSvg bounds={bounds} rand={groesse * 0.03} label={t("analyse.upload.overview")}>
          {reihenfolge.map(({ candidate, ringe: r }) => {
            const aktiv = candidate.index === selected;
            return (
              <path
                key={candidate.index}
                d={polygonPath(r)}
                fillRule="evenodd"
                data-testid={`kontur-${candidate.index}`}
                onClick={() => onSelect(candidate.index)}
                style={{
                  cursor: "pointer",
                  fill: aktiv ? "var(--accent-tint)" : "var(--sheet)",
                  fillOpacity: aktiv ? 1 : 0.6,
                  stroke: aktiv ? "var(--accent)" : "var(--line-strong)",
                  strokeWidth: ((aktiv ? 3 : 1) * groesse) / 700,
                }}
              >
                <title>{`${bezeichnung(candidate)} · ${formatNumber(candidate.area_m2, i18n.language)} m²`}</title>
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
                    style={txt(candidate.index === selected ? "var(--accent)" : "var(--ink)", schrift, { fontWeight: 500 })}
                  >
                    {candidate.name}
                  </text>
                );
              })}
          </g>
        </PlanSvg>
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor={listId} className="text-sm">
          {t("analyse.upload.list")}
        </label>
        <select
          id={listId}
          className="field"
          value={selected ?? ""}
          onChange={(event) => onSelect(Number(event.target.value))}
        >
          <option value="" disabled>
            {t("analyse.upload.pick")}
          </option>
          {candidates.map((candidate) => (
            <option key={candidate.index} value={candidate.index}>
              {`${bezeichnung(candidate)} · ${formatNumber(candidate.area_m2, i18n.language)} m²`}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
