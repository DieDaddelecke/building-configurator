/**
 * Terrasse, Carport und Zufahrt als Ebenen im Lageplan (Plan H3 4.4). Nur Darstellung: Die Nebenbauten setzt der
 * Server automatisch, der Kunde platziert sie nicht selbst. `size` ist die größere Kantenlänge des Grundstücks
 * in Metern und bestimmt die Strichstärken wie beim Haus.
 */

import type { OutbuildingsOut } from "../api/configuration";
import { ringPath, type LocalPoint } from "../components/plan/PlanSvg";

const ring = (value: unknown) => (value ?? null) as unknown as LocalPoint[] | null;

export function Nebenbauten({ outbuildings, size }: { outbuildings: OutbuildingsOut | null | undefined; size: number }) {
  if (!outbuildings) return null;
  const terrace = ring(outbuildings.terrace?.polygon_local);
  const carport = ring(outbuildings.carport?.polygon_local);
  return (
    <g data-testid="nebenbauten" aria-hidden="true">
      {outbuildings.driveways.map((drive, index) => {
        const points = ring(drive.polygon_local);
        return points ? (
          <path
            key={`${drive.source}-${index}`}
            data-testid="zufahrt"
            d={ringPath(points)}
            style={{ fill: "var(--line)", fillOpacity: 0.7, stroke: "var(--line-strong)", strokeWidth: size / 500 }}
          />
        ) : null;
      })}
      {terrace && (
        <path
          data-testid="terrasse"
          d={ringPath(terrace)}
          style={{ fill: "var(--warn-tint)", stroke: "var(--warn)", strokeWidth: size / 400 }}
        />
      )}
      {carport && (
        <path
          data-testid="carport"
          d={ringPath(carport)}
          style={{
            fill: "var(--sheet)",
            stroke: "var(--ink)",
            strokeWidth: size / 400,
            strokeDasharray: `${size / 90} ${size / 140}`,
          }}
        />
      )}
    </g>
  );
}
