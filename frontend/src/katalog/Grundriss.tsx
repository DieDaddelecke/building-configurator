/**
 * Umriss eines Haustyps in lokalen Metern: Fassadenhülle, Projektion (Dachüberstand), Kanten je nach
 * Fassadenrolle eingefärbt, Eingang und Garagentor (Plan H1 3.3). Norden liegt oben.
 */

import { useTranslation } from "react-i18next";

import { strich, txt } from "../components/plan/Masskette";
import { PlanSvg, boundsOf, ringPath, toSvg, type LocalPoint } from "../components/plan/PlanSvg";
import { edgesOf, pointOnEdge, type FacadeRole, type Placement, type Ring, type Roles } from "./geometrie";

export const ROLE_COLORS: Record<FacadeRole, string> = {
  street: "var(--accent)",
  garden: "var(--warn)",
  side_left: "var(--ink)",
  side_right: "var(--mute)",
};

interface GrundrissProps {
  facade: Ring;
  projection: Ring;
  roles: Roles;
  entrance?: Placement | null;
  garageDoor?: Placement | null;
  highlighted?: number | null;
}

export function Grundriss({ facade, projection, roles, entrance, garageDoor, highlighted = null }: GrundrissProps) {
  const { t } = useTranslation();
  const rings = (ring: Ring) => ring as unknown as LocalPoint[];
  const bounds = boundsOf([...rings(facade), ...rings(projection)]);
  const size = Math.max(bounds.maxE - bounds.minE, bounds.maxN - bounds.minN, 4);
  const label = size / 22;
  const edges = edgesOf(facade);
  const marker = (placement: Placement | null | undefined) => {
    const edge = placement ? edges[placement.edge] : undefined;
    return edge && placement ? toSvg(pointOnEdge(edge, placement.position)) : null;
  };
  const entrancePoint = marker(entrance);
  const garagePoint = marker(garageDoor);

  return (
    <PlanSvg bounds={bounds} rand={size * 0.22} label={t("catalog.type.planLabel")}>
      <path d={ringPath(rings(projection))} style={strich("var(--faint)", size / 300, { strokeDasharray: `${size / 60} ${size / 90}` })} />
      <path d={ringPath(rings(facade))} style={{ fill: "var(--accent-tint)", stroke: "none" }} />
      {edges.map((edge) => {
        const role = roles[edge.index];
        const [x1, y1] = toSvg(edge.from);
        const [x2, y2] = toSvg(edge.to);
        const [lx, ly] = toSvg([
          (edge.from[0] + edge.to[0]) / 2 + edge.normal[0] * label * 1.5,
          (edge.from[1] + edge.to[1]) / 2 + edge.normal[1] * label * 1.5,
        ]);
        const active = highlighted === edge.index;
        return (
          <g key={edge.index}>
            <line
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              style={strich(role ? ROLE_COLORS[role] : "var(--line-strong)", size / (active ? 60 : 110), { strokeLinecap: "round" })}
              data-testid={`kante-${edge.index}`}
              data-role={role ?? ""}
            />
            <text x={lx} y={ly} textAnchor="middle" dominantBaseline="central" style={txt(role ? ROLE_COLORS[role] : "var(--mute)", label)}>
              {edge.index}
            </text>
          </g>
        );
      })}
      {entrancePoint && (
        <circle cx={entrancePoint[0]} cy={entrancePoint[1]} r={size / 60} style={{ fill: "var(--ink)" }} data-testid="marke-eingang">
          <title>{t("catalog.type.entrance")}</title>
        </circle>
      )}
      {garagePoint && (
        <rect
          x={garagePoint[0] - size / 40}
          y={garagePoint[1] - size / 40}
          width={size / 20}
          height={size / 20}
          style={{ fill: "var(--sheet)", stroke: "var(--ink)", strokeWidth: size / 300 }}
          data-testid="marke-garage"
        >
          <title>{t("catalog.type.garageDoor")}</title>
        </rect>
      )}
    </PlanSvg>
  );
}
