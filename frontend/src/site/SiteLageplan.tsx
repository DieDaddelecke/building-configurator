/** Lageplan eines Grundstücks in lokalen Metern: Umgebung, Umriss, Kanten nach Art, Nordpfeil, Maßstab. */

import { useTranslation } from "react-i18next";

import type { SiteOut } from "../api/site";
import { Nordpfeil, strich, txt } from "../components/plan/Masskette";
import { PlanSvg, polygonPath, ringPath, toSvg, type LocalPoint } from "../components/plan/PlanSvg";
import { EDGE_COLORS, midpoint, siteBounds } from "./geo";

interface SiteLageplanProps {
  site: SiteOut;
  highlightedSeq?: number | null;
  onHighlight?: (seq: number | null) => void;
}

export function SiteLageplan({ site, highlightedSeq = null, onHighlight }: SiteLageplanProps) {
  const { t } = useTranslation();
  const bounds = siteBounds(site);
  const size = Math.max(bounds.maxE - bounds.minE, bounds.maxN - bounds.minN, 10);
  const rand = Math.max(6, size * 0.18);
  const label = size / 45;
  const bar = size > 60 ? 10 : 5;
  const outline = site.outline_local as unknown as LocalPoint[][];
  const [northX, northY] = toSvg([bounds.maxE + rand * 0.55, bounds.maxN + rand * 0.35]);
  const [barX, barY] = toSvg([bounds.minE - rand * 0.8, bounds.minN - rand * 0.55]);

  return (
    <PlanSvg bounds={bounds} rand={rand} label={t("site.plan.label", { idus: site.parcels.map((p) => p.idu).join(", ") })}>
      <g aria-hidden="true">
        {site.context.parcels.filter((ring) => ring.length >= 3).map((ring, i) => (
          <path key={`p${i}`} d={ringPath(ring as unknown as LocalPoint[])} style={strich("var(--line-strong)", size / 900)} />
        ))}
        {site.context.buildings.filter((ring) => ring.length >= 3).map((ring, i) => (
          <path key={`b${i}`} d={ringPath(ring as unknown as LocalPoint[])} style={{ fill: "var(--hatch)", opacity: 0.55 }} />
        ))}
        <path d={polygonPath(outline)} fillRule="evenodd" style={{ fill: "var(--sheet)", fillOpacity: 0.85 }} />
      </g>
      {site.edges.map((edge) => {
        const coords = edge.coords_local as unknown as LocalPoint[];
        const [mx, my] = toSvg(midpoint(coords));
        const active = highlightedSeq === edge.seq;
        const d = coords.map((p, i) => `${i ? "L" : "M"}${toSvg(p)[0].toFixed(3)} ${toSvg(p)[1].toFixed(3)}`).join("");
        return (
          <g
            key={edge.seq}
            onMouseEnter={() => onHighlight?.(edge.seq)}
            onMouseLeave={() => onHighlight?.(null)}
            data-testid={`plan-edge-${edge.seq}`}
          >
            <path
              d={d}
              style={strich(EDGE_COLORS[edge.kind], (active ? 2.2 : 1) * size / 140, {
                strokeDasharray: edge.classification_source === "customer" ? `${size / 60} ${size / 90}` : undefined,
                strokeLinecap: "round",
              })}
            />
            <circle cx={mx} cy={my} r={label * 1.05} style={{ fill: active ? EDGE_COLORS[edge.kind] : "var(--sheet)", stroke: EDGE_COLORS[edge.kind], strokeWidth: label / 7 }} />
            <text x={mx} y={my + label * 0.36} textAnchor="middle" style={txt(active ? "var(--sheet)" : "var(--ink)", label, { fontWeight: 500 })}>
              {edge.seq}
            </text>
          </g>
        );
      })}
      <g transform={`translate(${northX} ${northY}) scale(${size / 45})`}>
        <Nordpfeil x={0} y={0} />
      </g>
      <g transform={`translate(${barX} ${barY})`} aria-hidden="true">
        <rect x="0" y="0" width={bar} height={label * 0.45} style={{ fill: "var(--ink)" }} />
        <rect x={bar} y="0" width={bar} height={label * 0.45} style={{ fill: "var(--sheet)", stroke: "var(--ink)", strokeWidth: label / 12 }} />
        <text x="0" y={label * 1.6} style={txt("var(--mute)", label * 0.8)}>0</text>
        <text x={bar} y={label * 1.6} textAnchor="middle" style={txt("var(--mute)", label * 0.8)}>{bar}</text>
        <text x={2 * bar} y={label * 1.6} textAnchor="end" style={txt("var(--mute)", label * 0.8)}>{2 * bar} m</text>
      </g>
    </PlanSvg>
  );
}
