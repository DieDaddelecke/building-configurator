/**
 * Geometrie des Typumrisses für die Katalogpflege (Plan H1 3.3). Der Umriss kommt aus der API in lokalen
 * Metern (Ost, Nord), gegen den Uhrzeigersinn, ohne wiederholten Startpunkt; Kante `i` läuft von Punkt `i`
 * zu Punkt `i + 1`. Alles hier ist Vorschlag und Darstellung: maßgeblich bleibt, was das Büro speichert (L6).
 */

import type { components } from "../api/schema";

export type FacadeRole = components["schemas"]["FacadeRolesIn"]["roles"][string];
export type Ring = readonly (readonly number[])[];
export type Roles = Record<string, FacadeRole>;

export const FACADE_ROLES: readonly FacadeRole[] = ["street", "garden", "side_left", "side_right"];

export interface Edge {
  index: number;
  from: readonly [number, number];
  to: readonly [number, number];
  length: number;
  /** Nach außen zeigende Einheitsnormale (Umriss gegen den Uhrzeigersinn) */
  normal: readonly [number, number];
}

export function edgesOf(ring: Ring): Edge[] {
  return ring.map((point, index) => {
    const next = ring[(index + 1) % ring.length]!;
    const dx = next[0]! - point[0]!;
    const dy = next[1]! - point[1]!;
    const length = Math.hypot(dx, dy) || 1;
    return {
      index,
      from: [point[0]!, point[1]!],
      to: [next[0]!, next[1]!],
      length: Math.hypot(dx, dy),
      normal: [dy / length, -dx / length],
    };
  });
}

/** Punkt auf einer Kante bei Anteil `position` (0 = Anfang, 1 = Ende). */
export function pointOnEdge(edge: Edge, position: number): [number, number] {
  return [edge.from[0] + (edge.to[0] - edge.from[0]) * position, edge.from[1] + (edge.to[1] - edge.from[1]) * position];
}

/**
 * Vorschlag der Fassadenrollen (Plan H1 3.3, analog zur Kantenklassifikation in G1): Die längste Kante ist die
 * Straßenseite, jede Kante, die in die Gegenrichtung zeigt, ist Gartenseite. Kanten quer dazu heißen von der
 * Straße aus gesehen links oder rechts; schräge und kurze Versätze bleiben ohne Rolle. Die Zuordnung von links
 * und rechts ist eine Festlegung der Oberfläche (ANNAHMEN H10), keine Vorgabe der Spezifikation.
 */
export function suggestRoles(ring: Ring): Roles {
  const edges = edgesOf(ring);
  if (edges.length < 3) return {};
  const street = edges.reduce((best, edge) => (edge.length > best.length ? edge : best));
  const roles: Roles = { [street.index]: "street" };
  for (const edge of edges) {
    const alignment = -(edge.normal[0] * street.normal[0] + edge.normal[1] * street.normal[1]);
    if (edge.index !== street.index && alignment > 0.9) roles[edge.index] = "garden";
  }
  // Blick von der Straße ins Haus: links ist die Blickrichtung um 90° gegen den Uhrzeigersinn gedreht
  const view: [number, number] = [-street.normal[0], -street.normal[1]];
  const left: [number, number] = [-view[1], view[0]];
  for (const edge of edges) {
    if (roles[edge.index]) continue;
    const across = edge.normal[0] * left[0] + edge.normal[1] * left[1];
    if (across > 0.9) roles[edge.index] = "side_left";
    else if (across < -0.9) roles[edge.index] = "side_right";
  }
  return roles;
}

export interface Placement {
  edge: number;
  position: number;
}

/** Eingang und Garagentor liegen als `{edge, position}` am Umriss (ANNAHMEN H10); alles andere gilt als leer. */
export function readPlacement(value: Record<string, unknown> | null | undefined): Placement | null {
  if (!value) return null;
  const { edge, position } = value;
  if (typeof edge !== "number" || typeof position !== "number") return null;
  return { edge, position };
}

/** Umrissfläche nach Gauß, zur Kontrolle der Anzeige gegen den Serverwert. */
export function ringArea(ring: Ring): number {
  let sum = 0;
  ring.forEach((point, i) => {
    const next = ring[(i + 1) % ring.length]!;
    sum += point[0]! * next[1]! - next[0]! * point[1]!;
  });
  return Math.abs(sum) / 2;
}
