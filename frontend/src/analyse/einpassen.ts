/**
 * Lage einpassen (AN5, docs/PLAN_AN5_AUSGABE.md 3.2), ohne Karte und ohne React: Umriss um den Drehpunkt drehen
 * und auf Länge/Breite setzen, verschieben, Tastenschritte.
 *
 * Die Karte zeichnet jeden Punkt `p` des lokalen Umrisses als Versatz `R(map_rotation_deg + Δ) · (p − pivot)` in
 * Metern Ost/Nord um den Drehpunkt; `R` dreht im Uhrzeigersinn. Der Server rechnet dieselbe Drehung im Gitter von
 * Lambert-93 und nimmt die Gitterkonvergenz dazu; Karte und Ergebnis stimmen deshalb überein.
 */

export interface LonLat {
  lon: number;
  lat: number;
}

export type Punkt = readonly [number, number];
/** Punkt wie in der API (`outline_local`, `pivot_local`): `[x, y]` in lokalen Metern. */
type ApiPunkt = readonly number[];

// Ellipsoid GRS80 / WGS84
const A = 6_378_137;
const E2 = 0.00669438;

/** Meter je Grad Länge und Breite an einer Breite (Krümmungsradien des Ellipsoids). */
export function meterJeGrad(lat: number): { ost: number; nord: number } {
  const phi = (lat * Math.PI) / 180;
  const w = 1 - E2 * Math.sin(phi) ** 2;
  const n = A / Math.sqrt(w);
  const m = (A * (1 - E2)) / w ** 1.5;
  return { ost: (Math.PI / 180) * n * Math.cos(phi), nord: (Math.PI / 180) * m };
}

/** Vektor in Metern Ost/Nord im Uhrzeigersinn drehen. */
export function drehen([x, y]: Punkt, grad: number): [number, number] {
  const a = (grad * Math.PI) / 180;
  const cos = Math.cos(a);
  const sin = Math.sin(a);
  return [x * cos + y * sin, -x * sin + y * cos];
}

/** Um Meter Ost/Nord verschieben. */
export function verschieben(punkt: LonLat, ost: number, nord: number): LonLat {
  const m = meterJeGrad(punkt.lat);
  return { lon: punkt.lon + ost / m.ost, lat: punkt.lat + nord / m.nord };
}

/** Lokale Ringe in Länge/Breite: gedreht um `grad` (Karte plus eingestellte Drehung), Drehpunkt auf `zentrum`. */
export function umrissAufKarte(
  ringe: readonly (readonly ApiPunkt[])[],
  pivot: ApiPunkt,
  zentrum: LonLat,
  grad: number,
): [number, number][][] {
  const m = meterJeGrad(zentrum.lat);
  const [px = 0, py = 0] = pivot;
  return ringe.map((ring) => {
    const punkte = ring.map(([x = 0, y = 0]): [number, number] => {
      const [ost, nord] = drehen([x - px, y - py], grad);
      return [zentrum.lon + ost / m.ost, zentrum.lat + nord / m.nord];
    });
    // GeoJSON schließt Ringe; die API liefert offene
    const [first] = punkte;
    const last = punkte.at(-1);
    if (first && last && (first[0] !== last[0] || first[1] !== last[1])) punkte.push([first[0], first[1]]);
    return punkte;
  });
}

/** Winkel auf (−180°, 180°], auf 0,1° gerundet (Schritt der Feinknöpfe). */
export function winkel(grad: number): number {
  let value = ((grad % 360) + 360) % 360;
  if (value > 180) value -= 360;
  return Math.round(value * 10) / 10 || 0;
}

export const SCHRITT_M = 0.1;
export const SCHRITT_GROSS_M = 1;

/** Pfeiltaste in Meter Ost/Nord: 0,1 m, mit Umschalttaste 1 m. Andere Tasten: `null`. */
export function tastenSchritt(taste: string, gross: boolean): [number, number] | null {
  const schritt = gross ? SCHRITT_GROSS_M : SCHRITT_M;
  switch (taste) {
    case "ArrowUp":
      return [0, schritt];
    case "ArrowDown":
      return [0, -schritt];
    case "ArrowLeft":
      return [-schritt, 0];
    case "ArrowRight":
      return [schritt, 0];
    default:
      return null;
  }
}

/** Abstand zweier Punkte in Metern (kurze Strecken), für die Anzeige „um … m verschoben“. */
export function abstandM(a: LonLat, b: LonLat): number {
  const m = meterJeGrad((a.lat + b.lat) / 2);
  return Math.hypot((b.lon - a.lon) * m.ost, (b.lat - a.lat) * m.nord);
}
