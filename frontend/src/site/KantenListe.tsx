/**
 * Kanten eines Grundstücks mit Art, Richtung, Länge und Korrektur (Spez. 5.1.4 Punkt 6, Plan 3.3).
 * Kunde: nur „Straße“ oder „Nachbar“; Architekt: jede Art. Kundenkorrekturen sind bis zur Bestätigung
 * nicht bindend.
 */

import { useTranslation } from "react-i18next";

import type { EdgeOut } from "../api/site";
import { compass, EDGE_COLORS, formatNumber } from "./geo";

type Rolle = "customer" | "architect";

interface KantenListeProps {
  edges: readonly EdgeOut[];
  rolle: Rolle;
  onChange: (seq: number, value: string | null) => void;
  pending?: boolean;
  highlightedSeq?: number | null;
  onHighlight?: (seq: number | null) => void;
}

function customerValue(edge: EdgeOut): string {
  if (edge.override_kind === "street") return "street";
  if (edge.override_kind === "not_street") return "neighbour";
  return "auto";
}

function architectValue(edge: EdgeOut): string {
  return edge.classification_source === "architect" ? (edge.kind as string) : "auto";
}

function nachbarn(edge: EdgeOut): string {
  if (edge.street_name && edge.kind === "street") return edge.street_name;
  return edge.adjacent
    .slice(0, 2)
    .map((idu) => `${idu.slice(8, 10).replace(/^0/, "")} ${Number(idu.slice(10))}`)
    .join(", ");
}

export function KantenListe({ edges, rolle, onChange, pending = false, highlightedSeq = null, onHighlight }: KantenListeProps) {
  const { t, i18n } = useTranslation();
  const options: string[] = rolle === "customer" ? ["auto", "street", "neighbour"] : ["auto", "street", "side", "rear", "other"];

  return (
    <div className="overflow-x-auto relative">
      <table className="w-full text-sm border-collapse">
        <caption className="eyebrow text-left pb-2">{t("site.edges.caption")}</caption>
        <thead>
          <tr className="text-left border-b bd-strong">
            <th scope="col" className="py-2 pr-2 font-medium">{t("site.edges.seq")}</th>
            <th scope="col" className="py-2 pr-2 font-medium">{t("site.edges.kind")}</th>
            <th scope="col" className="py-2 pr-2 font-medium">{t("site.edges.facing")}</th>
            <th scope="col" className="py-2 pr-2 font-medium text-right">{t("site.edges.length")}</th>
            <th scope="col" className="py-2 pr-2 font-medium">{t("site.edges.adjacent")}</th>
            <th scope="col" className="py-2 font-medium">{t("site.edges.correction")}</th>
          </tr>
        </thead>
        <tbody>
          {edges.map((edge) => {
            const locked = rolle === "customer" && (edge.ring > 0 || edge.classification_source === "architect");
            const value = rolle === "customer" ? customerValue(edge) : architectValue(edge);
            const uncertain = edge.classification_source === "auto" && edge.confidence < 0.65;
            return (
              <tr
                key={edge.seq}
                className={`border-b bd ${highlightedSeq === edge.seq ? "bg-tint" : ""}`}
                onMouseEnter={() => onHighlight?.(edge.seq)}
                onMouseLeave={() => onHighlight?.(null)}
              >
                <td className="py-2 pr-2 f-mono num">
                  <span className="inline-block w-6 text-center border" style={{ borderColor: EDGE_COLORS[edge.kind] }}>
                    {edge.seq}
                  </span>
                </td>
                <td className="py-2 pr-2">
                  <span className="font-medium" style={{ color: EDGE_COLORS[edge.kind] }}>
                    {t(`site.kind.${edge.kind}`)}
                  </span>
                  <span className="block text-xs t-mute">
                    {t(`site.source.${edge.classification_source}`)}
                    {uncertain && <> · <span className="t-warn">{t("site.edges.uncertain")}</span></>}
                  </span>
                </td>
                <td className="py-2 pr-2">{t(`site.compass.${compass(edge.normal_azimuth_deg)}`)}</td>
                <td className="py-2 pr-2 text-right f-mono num">{formatNumber(edge.length_m, i18n.language)} m</td>
                <td className="py-2 pr-2 t-mute">{nachbarn(edge)}</td>
                <td className="py-2">
                  <label className="sr-only" htmlFor={`kante-${edge.seq}`}>
                    {t("site.edges.correctionFor", { seq: edge.seq })}
                  </label>
                  <select
                    id={`kante-${edge.seq}`}
                    className="field text-sm py-1"
                    value={value}
                    disabled={locked || pending}
                    onChange={(event) => onChange(edge.seq, event.target.value === "auto" ? null : event.target.value)}
                  >
                    {options.map((option) => (
                      <option key={option} value={option}>
                        {t(`site.correction.${option}`)}
                      </option>
                    ))}
                  </select>
                  {locked && edge.classification_source === "architect" && (
                    <span className="block text-xs t-mute">{t("site.edges.confirmed")}</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

