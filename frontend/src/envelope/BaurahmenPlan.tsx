/**
 * Lageplan des Baurahmens in lokalen Metern: Grundstück, Teilflächen, bebaubare Konturen in beiden
 * Auslegungen, Bauband, Bauverbots- und Einschränkungsflächen, Kanten mit ihrem Abstand (Plan 3.5).
 * Norden liegt oben (`toSvg` kehrt die y-Achse um).
 */

import { useTranslation } from "react-i18next";

import type { EnvelopeOut } from "../api/envelope";
import { Nordpfeil, strich, txt } from "../components/plan/Masskette";
import { PlanSvg, boundsOf, polygonPath, ringPath, toSvg, type LocalPoint } from "../components/plan/PlanSvg";
import { EDGE_COLORS, midpoint } from "../site/geo";
import { setbackValue } from "./format";

interface BaurahmenPlanProps {
  envelope: EnvelopeOut;
  highlightedSeq?: number | null;
  onHighlight?: (seq: number | null) => void;
}

const rings = (value: unknown) => (value ?? []) as unknown as LocalPoint[][];

export function BaurahmenPlan({ envelope, highlightedSeq = null, onHighlight }: BaurahmenPlanProps) {
  const { t, i18n } = useTranslation();
  const outline = rings(envelope.outline_local);
  const bounds = boundsOf(outline.flat());
  const size = Math.max(bounds.maxE - bounds.minE, bounds.maxN - bounds.minN, 10);
  const rand = Math.max(6, size * 0.18);
  const label = size / 45;
  const lenient = rings(envelope.contours.lenient?.rings_local);
  const strict = rings(envelope.contours.strict?.rings_local);
  const [northX, northY] = toSvg([bounds.maxE + rand * 0.55, bounds.maxN + rand * 0.35]);

  return (
    <PlanSvg bounds={bounds} rand={rand} label={t("envelope.plan.label")}>
      <defs>
        <pattern id="baurahmen-verbot" width="2" height="2" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="2" style={{ stroke: "var(--alert)", strokeWidth: 0.6 }} />
        </pattern>
        <pattern id="baurahmen-offen" width="2.4" height="2.4" patternUnits="userSpaceOnUse" patternTransform="rotate(-45)">
          <line x1="0" y1="0" x2="0" y2="2.4" style={{ stroke: "var(--faint)", strokeWidth: 0.5 }} />
        </pattern>
      </defs>
      <g aria-hidden="true">
        <path d={polygonPath(outline)} fillRule="evenodd" style={{ fill: "var(--sheet)", fillOpacity: 0.9 }} />
        {envelope.parts
          .filter((part) => part.excluded)
          .flatMap((part) => rings(part.rings_local).map((ring, i) => (
            <path key={`x${part.zone_code}${i}`} d={ringPath(ring)} style={{ fill: "url(#baurahmen-offen)" }} />
          )))}
        {envelope.bands.flatMap((band, index) =>
          rings(band.rings_local).map((ring, i) => (
            <path
              key={`band${index}-${i}`}
              d={ringPath(ring)}
              style={strich("var(--accent)", size / 500, { fill: "var(--accent)", fillOpacity: 0.05, strokeDasharray: `${size / 90} ${size / 90}` })}
            />
          )),
        )}
        {envelope.constraints
          .filter((item) => item.effect !== "info" && item.rings_local.length > 0)
          .flatMap((item, index) =>
            rings(item.rings_local).map((ring, i) => (
              <path
                key={`c${index}-${i}`}
                d={ringPath(ring)}
                style={{ fill: item.effect === "no_build" ? "url(#baurahmen-verbot)" : "var(--warn)", fillOpacity: item.effect === "no_build" ? 1 : 0.14 }}
              />
            )),
          )}
        <path
          d={polygonPath(lenient)}
          fillRule="evenodd"
          style={strich("var(--accent)", size / 260, { fill: "var(--accent)", fillOpacity: 0.1, strokeDasharray: `${size / 70} ${size / 110}` })}
          data-testid="kontur-lenient"
        />
        <path
          d={polygonPath(strict)}
          fillRule="evenodd"
          style={strich("var(--accent)", size / 200, { fill: "var(--accent)", fillOpacity: 0.28 })}
          data-testid="kontur-strict"
        />
      </g>
      {envelope.edges.map((edge) => {
        const coords = edge.coords_local as unknown as LocalPoint[];
        if (coords.length < 2) return null;
        const [mx, my] = toSvg(midpoint(coords));
        const active = highlightedSeq === edge.seq;
        const unknown = edge.markers.includes("setback_unknown") || edge.markers.includes("alignment");
        const d = coords.map((p, i) => `${i ? "L" : "M"}${toSvg(p)[0].toFixed(3)} ${toSvg(p)[1].toFixed(3)}`).join("");
        return (
          <g
            key={edge.seq}
            onMouseEnter={() => onHighlight?.(edge.seq)}
            onMouseLeave={() => onHighlight?.(null)}
            data-testid={`baurahmen-kante-${edge.seq}`}
          >
            <path
              d={d}
              style={strich(unknown ? "var(--alert)" : EDGE_COLORS[edge.kind], ((active ? 2.2 : 1) * size) / 140, {
                strokeDasharray: edge.classification_source === "customer" ? `${size / 60} ${size / 90}` : undefined,
                strokeLinecap: "round",
              })}
            />
            <text
              x={mx}
              y={my - label * 0.4}
              textAnchor="middle"
              style={txt(active ? "var(--accent)" : "var(--mute)", label * 0.95, { fontWeight: active ? 600 : 400 })}
            >
              {setbackValue(edge, t, i18n.language)}
            </text>
          </g>
        );
      })}
      <g transform={`translate(${northX} ${northY}) scale(${size / 45})`}>
        <Nordpfeil x={0} y={0} />
      </g>
    </PlanSvg>
  );
}
