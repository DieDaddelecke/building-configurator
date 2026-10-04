/**
 * Vorschau des Template-Entwurfs im Importbericht (docs/PLAN_HAUSMODELL.md 3.6, HM3): Räume mit Raumtyp,
 * Bezugskontur mit Segmenten und Fassadenrollen, Innenwände, Öffnungen, Eingang. Hervorgehoben werden die
 * Elemente des gewählten Befunds. Lokale Meter des Templates, y-Achse oben (keine Himmelsrichtung); Maße der Öffnungen aus dem IFC.
 */

import { useTranslation } from "react-i18next";

import type { FacadeRole, HouseImportReport, HouseTemplate } from "../../api/haus";
import { strich, txt } from "../../components/plan/Masskette";
import { boundsOf, PlanSvg, ringPath, toSvg, type LocalPoint } from "../../components/plan/PlanSvg";
import { number } from "../../katalog/bausteine";

export const ROLE_COLORS: Record<FacadeRole, string> = {
  street: "var(--accent)",
  garden: "var(--warn)",
  side_left: "var(--ink)",
  side_right: "var(--mute)",
};

interface Point {
  x: number;
  y: number;
}

interface Host {
  from: Point;
  to: Point;
}

const local = (p: Point): LocalPoint => [p.x, p.y];

/** Wirtsachsen der Öffnungen: Kanten der Bezugskontur und Achsen der Innenwände. */
export function hostsOf(template: HouseTemplate): Map<string, Host> {
  const hosts = new Map<string, Host>();
  for (const loop of template.envelope) {
    const ring = loop.inner_polygon;
    loop.segments.forEach((segment, i) => hosts.set(segment.id, { from: ring[i]!, to: ring[(i + 1) % ring.length]! }));
  }
  for (const wall of template.interior_walls) hosts.set(wall.id, { from: wall.axis[0]!, to: wall.axis[1]! });
  return hosts;
}

const pointAlong = (host: Host, distance: number): Point => {
  const dx = host.to.x - host.from.x;
  const dy = host.to.y - host.from.y;
  const length = Math.hypot(dx, dy) || 1;
  return { x: host.from.x + (dx / length) * distance, y: host.from.y + (dy / length) * distance };
};

export function areaOf(ring: readonly Point[]): number {
  let sum = 0;
  ring.forEach((p, i) => {
    const q = ring[(i + 1) % ring.length]!;
    sum += p.x * q.y - q.x * p.y;
  });
  return Math.abs(sum) / 2;
}

function centroid(ring: readonly Point[]): Point {
  let a = 0;
  let cx = 0;
  let cy = 0;
  ring.forEach((p, i) => {
    const q = ring[(i + 1) % ring.length]!;
    const cross = p.x * q.y - q.x * p.y;
    a += cross;
    cx += (p.x + q.x) * cross;
    cy += (p.y + q.y) * cross;
  });
  if (Math.abs(a) < 1e-9) return ring[0]!;
  return { x: cx / (3 * a), y: cy / (3 * a) };
}

interface VorschauProps {
  template: HouseTemplate;
  report: HouseImportReport | null;
  /** Raumtyp → Anzeigename. */
  roomNames: Record<string, string>;
  /** Fassadenrollen des Entwurfs, auch ungespeicherte. */
  roles: Record<string, FacadeRole | undefined>;
  highlighted: ReadonlySet<string>;
}

export function Vorschau({ template, report, roomNames, roles, highlighted }: VorschauProps) {
  const { t, i18n } = useTranslation();
  const outline = template.envelope.flatMap((loop) => loop.inner_polygon.map(local));
  const bounds = boundsOf(outline);
  const size = Math.max(bounds.maxE - bounds.minE, bounds.maxN - bounds.minN, 4);
  const label = size / 34;
  const hosts = hostsOf(template);
  const widths = new Map((report?.openings ?? []).map((o) => [o.element_id, o.width ?? 0.9]));
  const exterior = new Set(template.envelope.flatMap((loop) => loop.segments.map((s) => s.id)));
  const lit = (id: string) => highlighted.has(id);

  return (
    <PlanSvg bounds={bounds} rand={size * 0.12} label={t("house.preview.label")}>
      {template.rooms.map((room) => {
        const [x, y] = toSvg(local(centroid(room.polygon)));
        const unassigned = room.room_type_id === "unassigned";
        return (
          <g key={room.id} data-testid={`raum-${room.id}`} data-lit={lit(room.id) || undefined}>
            <path
              d={ringPath(room.polygon.map(local))}
              style={{
                fill: lit(room.id) ? "var(--alert-tint)" : unassigned ? "var(--warn-tint)" : "var(--accent-tint)",
                stroke: lit(room.id) ? "var(--alert)" : "none",
                strokeWidth: size / 150,
              }}
            />
            <text x={x} y={y} textAnchor="middle" dominantBaseline="central" style={txt("var(--ink)", label)}>
              {unassigned ? t("house.preview.unassigned") : (roomNames[room.room_type_id] ?? room.room_type_id)}
            </text>
            <text x={x} y={y + label * 1.3} textAnchor="middle" dominantBaseline="central" style={txt("var(--mute)", label * 0.85)}>
              {number(areaOf(room.polygon), i18n.language, 2)} m²
            </text>
          </g>
        );
      })}
      {template.interior_walls.map((wall) => {
        const [x1, y1] = toSvg(local(wall.axis[0]!));
        const [x2, y2] = toSvg(local(wall.axis[1]!));
        return (
          <line
            key={wall.id}
            x1={x1}
            y1={y1}
            x2={x2}
            y2={y2}
            data-testid={`wand-${wall.id}`}
            style={strich(lit(wall.id) ? "var(--alert)" : "var(--house)", wall.thickness, { strokeLinecap: "square" })}
          />
        );
      })}
      {template.envelope.flatMap((loop) =>
        loop.segments.map((segment, i) => {
          const from = loop.inner_polygon[i]!;
          const to = loop.inner_polygon[(i + 1) % loop.inner_polygon.length]!;
          const role = roles[segment.id];
          // Bezugskontur gegen den Uhrzeigersinn: außen liegt rechts der Kante
          const dx = to.x - from.x;
          const dy = to.y - from.y;
          const length = Math.hypot(dx, dy) || 1;
          const [lx, ly] = toSvg([(from.x + to.x) / 2 + (dy / length) * label * 2, (from.y + to.y) / 2 - (dx / length) * label * 2]);
          const [x1, y1] = toSvg(local(from));
          const [x2, y2] = toSvg(local(to));
          const color = lit(segment.id) ? "var(--alert)" : role ? ROLE_COLORS[role] : "var(--line-strong)";
          return (
            <g key={segment.id}>
              <line
                x1={x1}
                y1={y1}
                x2={x2}
                y2={y2}
                data-testid={`segment-${i}`}
                data-role={role ?? ""}
                style={strich(color, size / (lit(segment.id) ? 70 : 110), { strokeLinecap: "round" })}
              />
              <text x={lx} y={ly} textAnchor="middle" dominantBaseline="central" style={txt(color, label)}>
                {i}
              </text>
            </g>
          );
        }),
      )}
      {template.openings.map((opening) => {
        const host = hosts.get(opening.host_id);
        if (!host) return null;
        const half = (widths.get(opening.id) ?? 0.9) / 2;
        const [x1, y1] = toSvg(local(pointAlong(host, opening.offset_along_host - half)));
        const [x2, y2] = toSvg(local(pointAlong(host, opening.offset_along_host + half)));
        // Öffnung als Lücke in der Wand; Fenster durchgezogen, Tür gestrichelt (Farben gehören den Rollen)
        const color = lit(opening.id) ? "var(--alert)" : "var(--ink)";
        const dash = opening.kind === "door" ? { strokeDasharray: `${size / 90} ${size / 150}` } : {};
        const entrance = opening.id === template.entrance_opening_id;
        const [mx, my] = toSvg(local(pointAlong(host, opening.offset_along_host)));
        return (
          <g key={opening.id} data-testid={`oeffnung-${opening.id}`} data-kind={opening.kind}>
            <line
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              style={strich("var(--sheet)", exterior.has(opening.host_id) ? size / 45 : size / 65, { strokeLinecap: "butt" })}
            />
            <line
              x1={x1}
              y1={y1}
              x2={x2}
              y2={y2}
              style={strich(color, lit(opening.id) ? size / 120 : size / 220, { strokeLinecap: "butt", ...dash })}
            />
            {entrance && (
              <circle cx={mx} cy={my} r={size / 70} style={{ fill: "var(--ink)" }} data-testid="marke-eingang">
                <title>{t("house.draft.entrance")}</title>
              </circle>
            )}
          </g>
        );
      })}
    </PlanSvg>
  );
}
