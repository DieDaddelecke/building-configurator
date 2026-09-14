/**
 * Maßketten, Schraffur, Nordpfeil und Maßstabsleiste aus dem Mockup (Hauskonfigurator.jsx).
 * Einheit: Meter im SVG-Koordinatensystem des Planblatts (y nach unten; siehe PlanSvg).
 */

import type { CSSProperties } from "react";

const MONO = "IBM Plex Mono, ui-monospace, Consolas, monospace";

export const txt = (farbe: string, groesse: number, extra: CSSProperties = {}): CSSProperties => ({
  fill: farbe,
  fontFamily: MONO,
  fontSize: groesse,
  ...extra,
});

export const strich = (farbe: string, breite: number, extra: CSSProperties = {}): CSSProperties => ({
  stroke: farbe,
  strokeWidth: breite,
  fill: "none",
  ...extra,
});

const freistellen: CSSProperties = {
  paintOrder: "stroke",
  stroke: "var(--sheet)",
  strokeWidth: 0.28,
  strokeLinejoin: "round",
};

interface MassHProps {
  x1: number;
  x2: number;
  y: number;
  label: string;
  /** y der Bezugskante für Hilfslinien */
  von?: number;
  farbe?: string;
  gr?: number;
}

export function MassH({ x1, x2, y, label, von, farbe = "var(--mute)", gr = 0.72 }: MassHProps) {
  const t = 0.32;
  return (
    <g>
      {von != null && (
        <>
          <line x1={x1} y1={von} x2={x1} y2={y + (y > von ? 0.4 : -0.4)} style={strich(farbe, 0.035)} />
          <line x1={x2} y1={von} x2={x2} y2={y + (y > von ? 0.4 : -0.4)} style={strich(farbe, 0.035)} />
        </>
      )}
      <line x1={x1} y1={y} x2={x2} y2={y} style={strich(farbe, 0.045)} />
      <line x1={x1 - t} y1={y + t} x2={x1 + t} y2={y - t} style={strich(farbe, 0.08)} />
      <line x1={x2 - t} y1={y + t} x2={x2 + t} y2={y - t} style={strich(farbe, 0.08)} />
      <text x={(x1 + x2) / 2} y={y - 0.3} textAnchor="middle" style={txt(farbe, gr, freistellen)}>
        {label}
      </text>
    </g>
  );
}

interface MassVProps {
  y1: number;
  y2: number;
  x: number;
  label: string;
  von?: number;
  farbe?: string;
  gr?: number;
}

export function MassV({ y1, y2, x, label, von, farbe = "var(--mute)", gr = 0.72 }: MassVProps) {
  const t = 0.32;
  const my = (y1 + y2) / 2;
  return (
    <g>
      {von != null && (
        <>
          <line x1={von} y1={y1} x2={x + (x > von ? 0.4 : -0.4)} y2={y1} style={strich(farbe, 0.035)} />
          <line x1={von} y1={y2} x2={x + (x > von ? 0.4 : -0.4)} y2={y2} style={strich(farbe, 0.035)} />
        </>
      )}
      <line x1={x} y1={y1} x2={x} y2={y2} style={strich(farbe, 0.045)} />
      <line x1={x - t} y1={y1 + t} x2={x + t} y2={y1 - t} style={strich(farbe, 0.08)} />
      <line x1={x - t} y1={y2 + t} x2={x + t} y2={y2 - t} style={strich(farbe, 0.08)} />
      <text
        x={x - 0.3}
        y={my}
        textAnchor="middle"
        transform={`rotate(-90 ${x - 0.3} ${my})`}
        style={txt(farbe, gr, freistellen)}
      >
        {label}
      </text>
    </g>
  );
}

export function Schraffur({ id, farbe, abstand = 0.7, breite = 0.05 }: { id: string; farbe: string; abstand?: number; breite?: number }) {
  return (
    <pattern id={id} patternUnits="userSpaceOnUse" width={abstand} height={abstand} patternTransform="rotate(45)">
      <line x1="0" y1="0" x2="0" y2={abstand} style={strich(farbe, breite)} />
    </pattern>
  );
}

/** Nordpfeil; `drehung` in Grad im Uhrzeigersinn, falls Planoben nicht Norden ist. */
export function Nordpfeil({ x, y, drehung = 0 }: { x: number; y: number; drehung?: number }) {
  return (
    <g transform={`translate(${x} ${y}) rotate(${drehung})`} aria-label="N">
      <circle r="1.5" style={strich("var(--ink)", 0.06)} />
      <path d="M0 -1.5 L0.55 0.9 L0 0.45 L-0.55 0.9 Z" style={{ fill: "var(--ink)" }} />
      <text y="-2" textAnchor="middle" style={txt("var(--ink)", 0.8, { fontWeight: 500 })}>
        N
      </text>
    </g>
  );
}

/** Maßstabsleiste mit zwei Feldern gleicher Länge (Meter). */
export function Massstab({ x, y, feld = 5 }: { x: number; y: number; feld?: number }) {
  return (
    <g transform={`translate(${x} ${y})`}>
      <rect x="0" y="0" width={feld} height="0.45" style={{ fill: "var(--ink)" }} />
      <rect x={feld} y="0" width={feld} height="0.45" style={{ fill: "var(--sheet)", stroke: "var(--ink)", strokeWidth: 0.05 }} />
      <text x="0" y="1.5" style={txt("var(--mute)", 0.6)}>0</text>
      <text x={feld} y="1.5" textAnchor="middle" style={txt("var(--mute)", 0.6)}>{feld}</text>
      <text x={2 * feld} y="1.5" textAnchor="end" style={txt("var(--mute)", 0.6)}>{2 * feld} m</text>
    </g>
  );
}
