/**
 * Gabarit und Schnitt (AN3, docs/PLAN_AN3_GABARIT.md 3.6): Lageplan mit den Konturen der Höhenstufen und den
 * Schnittlinien, Tabelle der Stufen, Schnitt A–A' oder B–B' mit Grenzen, Stufen, Abstandslinien und Trauf- und
 * Firsthöhe. Eine Stufe gilt bis zu ihrer Oberkante. Mit bekanntem Gelände zeigt der Schnitt das Profil über der
 * Bezugshöhe (AN5, docs/PLAN_AN5_AUSGABE.md 3.3), sonst ist das Gelände eben dargestellt (E-AN3G-4).
 */

import type { TFunction } from "i18next";
import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useAnalysis, type GabaritLevelOut, type GabaritOut, type SectionOut } from "../api/analysis";
import type { EnvelopeOut } from "../api/envelope";
import { Nordpfeil, Schraffur, strich, txt } from "../components/plan/Masskette";
import { PlanSvg, boundsOf, polygonPath, toSvg, type LocalPoint } from "../components/plan/PlanSvg";
import { formatNumber } from "../site/geo";

type Reading = SectionOut["prospects"][number]["reading"];
type Key = SectionOut["key"];

const rings = (value: unknown) => (value ?? []) as unknown as LocalPoint[][];

/** Ab dieser Neigung ist der Messpunkt der Höhe nach PLU zu prüfen (wie im Bericht, `report.STEEP_PERCENT`). */
const STEIL_PROZENT = 5;

/** Deckkraft einer Stufe: höhere Stufen kräftiger, damit die Höhenlinien lesbar gestaffelt sind. */
function staerke(index: number, count: number): number {
  return count <= 1 ? 1 : 0.35 + (0.65 * index) / (count - 1);
}

function meter(value: number, language: string): string {
  return formatNumber(value, language, 2);
}

function unterscheiden(gabarit: GabaritOut): boolean {
  return gabarit.levels.some(
    (level) =>
      Math.abs((level.contours.lenient?.area_m2 ?? 0) - (level.contours.strict?.area_m2 ?? 0)) > 0.005 ||
      JSON.stringify(level.contours.lenient?.rings_local) !== JSON.stringify(level.contours.strict?.rings_local),
  );
}

// ---------------------------------------------------------------------------
// Lageplan
// ---------------------------------------------------------------------------

function GabaritPlan({
  envelope,
  gabarit,
  sections,
  reading,
  section,
  highlighted,
}: {
  envelope: EnvelopeOut;
  gabarit: GabaritOut;
  sections: SectionOut[];
  reading: Reading;
  section: Key;
  highlighted: number | null;
}) {
  const { t } = useTranslation();
  const outline = rings(envelope.outline_local);
  const bounds = boundsOf(outline.flat());
  const size = Math.max(bounds.maxE - bounds.minE, bounds.maxN - bounds.minN, 10);
  const rand = Math.max(6, size * 0.18);
  const [northX, northY] = toSvg([bounds.maxE + rand * 0.55, bounds.maxN + rand * 0.35]);
  const count = gabarit.levels.length;
  return (
    <PlanSvg bounds={bounds} rand={rand} label={t("analyse.gabarit.plan.label")}>
      <path d={polygonPath(outline)} fillRule="evenodd" style={strich("var(--ink)", size / 180, { fill: "var(--sheet)" })} />
      {gabarit.levels.map((level, index) => {
        const contour = level.contours[reading];
        const aktiv = highlighted === index;
        return (
          <path
            key={index}
            d={polygonPath(rings(contour?.rings_local))}
            fillRule="evenodd"
            data-testid={`gabarit-kontur-${index}`}
            style={strich("var(--accent)", (aktiv ? 2.4 : 1) * (size / 260), {
              fill: "var(--accent)",
              fillOpacity: 0.07,
              strokeOpacity: aktiv ? 1 : staerke(index, count),
              strokeDasharray: level.roof ? `${size / 90} ${size / 140}` : undefined,
            })}
          />
        );
      })}
      {sections.map((item) => {
        const [x1, y1] = toSvg(item.start_local as unknown as LocalPoint);
        const [x2, y2] = toSvg(item.end_local as unknown as LocalPoint);
        const dx = x2 - x1;
        const dy = y2 - y1;
        const laenge = Math.hypot(dx, dy) || 1;
        const [ux, uy] = [dx / laenge, dy / laenge];
        const ueber = rand * 0.35;
        const aktiv = item.key === section;
        const farbe = aktiv ? "var(--ink)" : "var(--mute)";
        return (
          <g key={item.key} data-testid={`schnittlinie-${item.key}`}>
            <line
              x1={x1 - ux * ueber}
              y1={y1 - uy * ueber}
              x2={x2 + ux * ueber}
              y2={y2 + uy * ueber}
              style={strich(farbe, (aktiv ? 1.4 : 0.8) * (size / 300), { strokeDasharray: `${size / 40} ${size / 120} ${size / 300} ${size / 120}` })}
            />
            <text x={x1 - ux * ueber * 1.6} y={y1 - uy * ueber * 1.6 + size / 90} textAnchor="middle" style={txt(farbe, size / 38, { fontWeight: 600 })}>
              {item.key}
            </text>
            <text x={x2 + ux * ueber * 1.6} y={y2 + uy * ueber * 1.6 + size / 90} textAnchor="middle" style={txt(farbe, size / 38, { fontWeight: 600 })}>
              {`${item.key}'`}
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

function Stufen({
  gabarit,
  highlighted,
  onHighlight,
}: {
  gabarit: GabaritOut;
  highlighted: number | null;
  onHighlight: (index: number | null) => void;
}) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const count = gabarit.levels.length;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm border-collapse">
        <caption className="sr-only">{t("analyse.gabarit.levels.caption")}</caption>
        <thead>
          <tr className="text-left border-b bd-strong">
            <th scope="col" className="py-2 pr-3 font-medium">{t("analyse.gabarit.levels.level")}</th>
            <th scope="col" className="py-2 pr-3 font-medium text-right">{t("analyse.analysis.reading.lenient")}</th>
            <th scope="col" className="py-2 font-medium text-right">{t("analyse.analysis.reading.strict")}</th>
          </tr>
        </thead>
        <tbody>
          {gabarit.levels.map((level, index) => (
            <tr
              key={index}
              className={`border-b bd align-top ${highlighted === index ? "bg-tint" : ""}`}
              onMouseEnter={() => onHighlight(index)}
              onMouseLeave={() => onHighlight(null)}
              data-testid={`gabarit-stufe-${index}`}
            >
              <th scope="row" className="py-2 pr-3 font-normal text-left">
                <span className="inline-flex items-center gap-2">
                  <svg width="18" height="8" aria-hidden="true">
                    <line
                      x1="0"
                      y1="4"
                      x2="18"
                      y2="4"
                      style={strich("var(--accent)", 2, {
                        strokeOpacity: staerke(index, count),
                        strokeDasharray: level.roof ? "4 3" : undefined,
                      })}
                    />
                  </svg>
                  <span className="f-mono num whitespace-nowrap">
                    {t("analyse.gabarit.levels.range", { from: meter(level.from_m, lng), to: meter(level.to_m, lng) })}
                  </span>
                </span>
                {level.roof && <span className="block text-xs t-mute">{t("analyse.gabarit.levels.roof")}</span>}
              </th>
              <td className="py-2 pr-3 num t-ink text-right">{flaeche(level, "lenient", lng)}</td>
              <td className="py-2 num t-ink text-right">
                {flaeche(level, "strict", lng)}
                {level.contours.strict && !level.contours.strict.complete && <span className="t-warn"> *</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function flaeche(level: GabaritLevelOut, reading: Reading, language: string): string {
  const contour = level.contours[reading];
  return contour ? `${formatNumber(contour.area_m2, language, 0)} m²` : "–";
}

// ---------------------------------------------------------------------------
// Schnitt
// ---------------------------------------------------------------------------

function kante(kind: string | null | undefined, t: TFunction): string {
  return t(`analyse.gabarit.section.kind.${kind ?? "other"}`);
}

function Schnitt({ section, gabarit, highlighted }: { section: SectionOut; gabarit: GabaritOut; highlighted: number | null }) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const top = gabarit.top_m ?? Math.max(0, ...section.levels.map((level) => level.to_m));
  const profil = section.terrain;
  const hoch = Math.max(0, ...profil.map(([, dz = 0]) => dz));
  const tief = Math.min(0, ...profil.map(([, dz = 0]) => dz));
  const size = Math.max(section.length_m, top, 10);
  const schrift = size / 42;
  const links = -Math.max(3, size * 0.1);
  const rechts = section.length_m + Math.max(3, size * 0.14);
  const oben = Math.max(top, hoch) + schrift * 3;
  const unten = -tief + schrift * 3.2;
  const beschriftung = -tief + schrift * 2.2;
  const pfad = (points: number[][]) => points.map(([s = 0, z = 0], i) => `${i ? "L" : "M"}${s.toFixed(3)} ${(-z).toFixed(3)}`).join("");
  const koten = Array.from(new Set(section.levels.map((level) => level.to_m))).sort((a, b) => a - b);

  return (
    <svg
      viewBox={`${links} ${-oben} ${rechts - links} ${oben + unten}`}
      className="w-full h-auto block select-none"
      role="img"
      aria-label={t("analyse.gabarit.section.label", { key: section.key })}
    >
      <defs>
        <Schraffur id={`boden-${section.key}`} farbe="var(--faint)" abstand={schrift * 0.7} breite={schrift * 0.06} />
      </defs>
      {profil.length > 1 ? (
        <g data-testid={`schnitt-gelaende-${section.key}`}>
          <path
            d={`${pfad(profil)}L${(profil.at(-1)?.[0] ?? 0).toFixed(3)} ${(-tief + schrift * 0.8).toFixed(3)}L${(profil[0]?.[0] ?? 0).toFixed(3)} ${(-tief + schrift * 0.8).toFixed(3)}Z`}
            style={{ fill: `url(#boden-${section.key})`, stroke: "none" }}
          />
          <path
            d={pfad(profil)}
            style={strich("var(--ink)", schrift * 0.08, { fill: "none", strokeDasharray: `${schrift * 0.5} ${schrift * 0.25}` })}
          />
          {/* ±0,00 = mittlere Geländehöhe der Stichproben (E-AN5-4) */}
          <line
            x1={links}
            y1={0}
            x2={rechts}
            y2={0}
            style={strich("var(--mute)", schrift * 0.04, { strokeDasharray: `${schrift * 0.2} ${schrift * 0.3}` })}
          />
        </g>
      ) : (
        <>
          {section.parcel.map(([a = 0, b = 0], i) => (
            <rect key={`boden${i}`} x={a} y={0} width={b - a} height={schrift * 0.8} style={{ fill: `url(#boden-${section.key})` }} />
          ))}
          <line x1={links} y1={0} x2={rechts} y2={0} style={strich("var(--ink)", schrift * 0.08)} />
        </>
      )}
      {(["lenient", "strict"] as const).map((reading) =>
        section.levels.flatMap((level, index) =>
          (level.intervals[reading] ?? []).map(([a = 0, b = 0], j) => (
            <rect
              key={`${reading}${index}-${j}`}
              x={a}
              y={-level.to_m}
              width={b - a}
              height={level.to_m - level.from_m}
              data-testid={`schnitt-stufe-${reading}-${index}-${j}`}
              style={{
                fill: "var(--accent)",
                fillOpacity: reading === "strict" ? 0.3 : 0.1,
                stroke: highlighted === index ? "var(--accent)" : "none",
                strokeWidth: schrift * 0.08,
              }}
            />
          )),
        ),
      )}
      {section.height_lines.map((line, i) => (
        <g key={`h${i}`}>
          <line
            x1={line.start}
            y1={-line.height_m}
            x2={line.end}
            y2={-line.height_m}
            style={strich("var(--mute)", schrift * 0.05, { strokeDasharray: `${schrift * 0.6} ${schrift * 0.4}` })}
          />
          <text x={line.end - schrift * 0.3} y={-line.height_m - schrift * 0.3} textAnchor="end" style={txt("var(--mute)", schrift * 0.9)}>
            {`${t(`analyse.gabarit.section.${line.kind}`)} ${meter(line.height_m, lng)}${line.derived ? " *" : ""}`}
          </text>
        </g>
      ))}
      {section.prospects.map((prospect, i) => (
        <path
          key={`p${i}`}
          d={pfad(prospect.points)}
          data-testid={`schnitt-abstand-${prospect.edge_seq}-${prospect.reading}`}
          style={strich("var(--warn)", schrift * (prospect.reading === "strict" ? 0.09 : 0.06), {
            strokeDasharray: prospect.reading === "strict" ? undefined : `${schrift * 0.3} ${schrift * 0.3}`,
          })}
        />
      ))}
      {section.crossings.map((crossing, i) => (
        <g key={`c${i}`} data-testid={`schnitt-grenze-${crossing.edge_seq ?? "x"}`}>
          <line
            x1={crossing.s}
            y1={beschriftung - schrift * 1.4}
            x2={crossing.s}
            y2={-(top + schrift)}
            style={strich("var(--ink)", schrift * 0.06, { strokeDasharray: `${schrift * 0.25} ${schrift * 0.25}` })}
          />
          <text
            x={crossing.s}
            y={beschriftung}
            textAnchor={crossing.inward > 0 ? "start" : "end"}
            style={txt("var(--ink)", schrift * 0.9)}
          >
            {`${kante(crossing.kind, t)}${crossing.edge_seq != null ? ` ${crossing.edge_seq}` : ""}`}
          </text>
        </g>
      ))}
      {koten.map((height) => (
        <g key={`k${height}`}>
          <line x1={links + schrift * 0.4} y1={-height} x2={links + schrift * 1.1} y2={-height} style={strich("var(--mute)", schrift * 0.06)} />
          <text x={links + schrift * 1.3} y={-height + schrift * 0.35} style={txt("var(--mute)", schrift * 0.85)}>
            {`+${meter(height, lng)}`}
          </text>
        </g>
      ))}
      <text x={links + schrift * 0.4} y={-oben + schrift * 1.4} style={txt("var(--ink)", schrift * 1.2, { fontWeight: 600 })}>
        {section.key}
      </text>
      <text x={rechts - schrift * 0.4} y={-oben + schrift * 1.4} textAnchor="end" style={txt("var(--ink)", schrift * 1.2, { fontWeight: 600 })}>
        {`${section.key}'`}
      </text>
    </svg>
  );
}

function Hinweise({ gabarit }: { gabarit: GabaritOut }) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const slope = gabarit.terrain_slope_percent;
  const reference = gabarit.reference_altitude_ngf;
  const werte = { slope: formatNumber(slope ?? 0, lng, 1), reference: meter(reference ?? 0, lng) };
  // Profil über der mittleren Geländehöhe; ab 5 % entscheidet das PLU, wo die Höhe gemessen wird (E-AN5-4)
  const gelaende =
    gabarit.terrain_status !== "ok" || slope == null || reference == null
      ? t("analyse.gabarit.notes.terrain")
      : slope > STEIL_PROZENT
        ? t("analyse.gabarit.notes.terrainSteep", werte)
        : t("analyse.gabarit.notes.terrainProfile", werte);
  return (
    <ul className="m-0 pl-5 text-sm t-mute flex flex-col gap-1">
      <li>{t("analyse.gabarit.notes.reading")}</li>
      <li>{gelaende}</li>
      {gabarit.levels.some((level) => level.roof) && <li>{t("analyse.gabarit.notes.roof")}</li>}
      {gabarit.storey_height_m != null && (
        <li>{t("analyse.gabarit.notes.storeys", { height: meter(gabarit.storey_height_m, lng) })}</li>
      )}
      {gabarit.reasons
        .filter((reason) => reason.startsWith("height_unknown:"))
        .map((reason) => (
          <li key={reason} className="t-warn">
            {t("analyse.gabarit.notes.heightUnknown", { zone: reason.split(":")[1] })}
          </li>
        ))}
      {gabarit.levels.some((level) => level.contours.strict && !level.contours.strict.complete) && (
        <li className="t-warn">{t("analyse.gabarit.notes.incomplete")}</li>
      )}
    </ul>
  );
}

export function GabaritSchnitt({ projectId, envelope }: { projectId: string; envelope: EnvelopeOut }) {
  const { t } = useTranslation();
  const analysis = useAnalysis(projectId);
  const [reading, setReading] = useState<Reading>("lenient");
  const [key, setKey] = useState<Key>("A");
  const [highlighted, setHighlighted] = useState<number | null>(null);
  const gabarit = analysis.data?.gabarit;
  // Ohne Baurahmen erklärt die Analyse darüber, warum es keine Werte gibt
  if (!analysis.data || !gabarit) return null;
  const sections = analysis.data.sections;
  const section = sections.find((item) => item.key === key) ?? sections[0];
  const beide = unterscheiden(gabarit);
  const gezeigt: Reading = beide ? reading : "lenient";

  return (
    <section aria-labelledby="gabarit" className="flex flex-col gap-5">
      <h2 id="gabarit" className="eyebrow m-0">{t("analyse.gabarit.title")}</h2>
      {gabarit.status === "unavailable" ? (
        <p className="t-mute m-0">{t(`analyse.gabarit.unavailable.${gabarit.reason ?? "height_unknown"}`)}</p>
      ) : (
        <>
          <p className="t-mute m-0 text-sm">{t("analyse.gabarit.intro")}</p>
          {beide && (
            <div className="flex flex-wrap gap-2" role="group" aria-label={t("analyse.gabarit.readingLabel")}>
              {(["lenient", "strict"] as const).map((item) => (
                <button key={item} type="button" className="chip" aria-pressed={gezeigt === item} onClick={() => setReading(item)}>
                  {t(`analyse.analysis.reading.${item}`)}
                </button>
              ))}
            </div>
          )}
          <div className="grid gap-6 lg:grid-cols-[3fr_2fr] items-start [&>*]:min-w-0">
            <div className="karte p-4">
              <GabaritPlan
                envelope={envelope}
                gabarit={gabarit}
                sections={sections}
                reading={gezeigt}
                section={section?.key ?? "A"}
                highlighted={highlighted}
              />
            </div>
            <Stufen gabarit={gabarit} highlighted={highlighted} onHighlight={setHighlighted} />
          </div>
          {section && (
            <div className="flex flex-col gap-3">
              <div className="flex flex-wrap gap-2" role="group" aria-label={t("analyse.gabarit.section.choose")}>
                {sections.map((item) => (
                  <button key={item.key} type="button" className="chip" aria-pressed={item.key === section.key} onClick={() => setKey(item.key)}>
                    {t(`analyse.gabarit.section.${item.key}`)}
                  </button>
                ))}
              </div>
              <div className="karte p-4">
                <Schnitt section={section} gabarit={gabarit} highlighted={highlighted} />
              </div>
              <p className="text-xs t-mute m-0">{t("analyse.gabarit.section.legend")}</p>
            </div>
          )}
          <Hinweise gabarit={gabarit} />
        </>
      )}
    </section>
  );
}
