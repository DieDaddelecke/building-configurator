/**
 * Typkarten mit Zulässigkeit (Plan H2 4.4, Spez. 5.4.6): jede Karte zeigt, ob der Typ auf dem Grundstück
 * möglich ist; ein gesperrter Typ nennt alle Gründe und einen Vorschlag. Gründe und Hinweise kommen als
 * stabile Codes vom Server und werden hier übersetzt.
 */

import { useTranslation } from "react-i18next";

import type { CheckOut, TypeFactsOut, TypeFitOut } from "../api/configuration";
import { formatNumber } from "../site/geo";
import { checkText, STATUS_TONE } from "./format";

interface TypKartenProps {
  types: readonly TypeFitOut[];
  selectedSlug: string | null;
  onSelect: (slug: string) => void;
  pending?: boolean;
  /** Fehlermeldung zum zuletzt versuchten Typ, z. B. wenn er inzwischen gesperrt ist. */
  error?: { slug: string; reasons: readonly CheckOut[] } | null;
}

const ring = (value: unknown) => (value ?? []) as unknown as readonly (readonly [number, number])[];

/** Grundriss als Silhouette; Straßenfassade in Akzentfarbe. Modellnorden liegt oben. */
function Silhouette({ facts }: { facts: TypeFactsOut }) {
  const outline = ring(facts.projection_local);
  const facade = ring(facts.facade_local);
  const xs = outline.map((p) => p[0]);
  const ys = outline.map((p) => p[1]);
  const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
  const pad = Math.max(maxX - minX, maxY - minY) * 0.08;
  const path = (points: readonly (readonly [number, number])[]) =>
    points.map(([x, y], i) => `${i ? "L" : "M"}${x.toFixed(2)} ${(-y).toFixed(2)}`).join("") + "Z";
  const points = facade.length > 1 && facade[0]![0] === facade.at(-1)![0] && facade[0]![1] === facade.at(-1)![1] ? facade.slice(0, -1) : facade;
  const streetEdges = Object.entries(facts.facade_roles)
    .filter(([, role]) => role === "street")
    .map(([index]) => Number(index))
    .filter((i) => i < points.length);
  return (
    <svg
      viewBox={`${minX - pad} ${-maxY - pad} ${maxX - minX + 2 * pad} ${maxY - minY + 2 * pad}`}
      className="w-24 h-16 shrink-0"
      aria-hidden="true"
    >
      <path d={path(outline)} style={{ fill: "none", stroke: "var(--faint)", strokeWidth: 0.12, strokeDasharray: "0.5 0.4" }} />
      <path d={path(points)} style={{ fill: "var(--accent-tint)", stroke: "var(--ink)", strokeWidth: 0.18 }} />
      {streetEdges.map((i) => {
        const a = points[i]!;
        const b = points[(i + 1) % points.length]!;
        return <line key={i} x1={a[0]} y1={-a[1]} x2={b[0]} y2={-b[1]} style={{ stroke: "var(--accent)", strokeWidth: 0.5 }} />;
      })}
    </svg>
  );
}

function Fakten({ facts }: { facts: TypeFactsOut }) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const rows: [string, string][] = [
    [t("configurator.types.fact.footprint"), `${formatNumber(facts.footprint_m2, lng, 0)} m²`],
    [t("configurator.types.fact.living"), `${formatNumber(facts.living_area_m2, lng, 0)} m²`],
    [t("configurator.types.fact.size"), `${formatNumber(facts.width_m, lng, 1)} × ${formatNumber(facts.depth_m, lng, 1)} m`],
    [t("configurator.types.fact.roof"), t(`configurator.types.roof.${facts.roof_form}`, { defaultValue: facts.roof_form })],
    [t("configurator.types.fact.ridge"), `${formatNumber(facts.ridge_height_m, lng, 1)} m`],
    [t("configurator.types.fact.storeys"), facts.storeys],
  ];
  return (
    <dl className="grid grid-cols-2 gap-x-4 gap-y-1 m-0 text-sm">
      {rows.map(([label, value]) => (
        <div key={label} className="flex justify-between gap-2 border-t bd py-1">
          <dt className="t-mute">{label}</dt>
          <dd className="m-0 num t-ink text-right">{value}</dd>
        </div>
      ))}
    </dl>
  );
}

function Pruefungen({ title, checks, tone }: { title: string; checks: readonly CheckOut[]; tone: string }) {
  const { t, i18n } = useTranslation();
  if (checks.length === 0) return null;
  return (
    <div className="flex flex-col gap-1">
      <div className={`eyebrow ${tone}`}>{title}</div>
      <ul className="m-0 pl-5 text-sm flex flex-col gap-1">
        {checks.map((check, index) => (
          <li key={`${check.code}-${check.edge_seq ?? ""}-${index}`} className={STATUS_TONE[check.status]}>
            {checkText(check, t, i18n.language)}
          </li>
        ))}
      </ul>
    </div>
  );
}

const hintKey = (check: CheckOut) => `${check.code}|${check.reason ?? ""}`;

export function TypKarten({ types, selectedSlug, onSelect, pending = false, error = null }: TypKartenProps) {
  const { t } = useTranslation();
  const bySlug = new Map(types.map((type) => [type.slug, type]));
  // Zulässige zuerst: Wer wählen will, findet sie oben; gesperrte bleiben mit Gründen sichtbar
  const ordered = [...types].sort((a, b) => Number(b.allowed) - Number(a.allowed));
  if (types.length === 0) return <p className="t-mute">{t("configurator.types.empty")}</p>;
  // Was für jeden Typ gleich lautet, betrifft das Grundstück und steht einmal oben statt auf jeder Karte
  const common =
    types.length > 1 ? types[0]!.hints.filter((h) => types.every((type) => type.hints.some((x) => hintKey(x) === hintKey(h)))) : [];
  const commonKeys = new Set(common.map(hintKey));

  return (
    <div className="flex flex-col gap-6">
      <Pruefungen title={t("configurator.types.commonHints")} checks={common} tone="t-mute" />
    <ul className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6 m-0 p-0 list-none" data-testid="typkarten">
      {ordered.map((type) => {
        const selected = type.slug === selectedSlug;
        const suggestions = type.suggestions.map((slug) => bySlug.get(slug)).filter((s): s is TypeFitOut => Boolean(s));
        return (
          <li
            key={type.slug}
            id={`typ-${type.slug}`}
            data-testid={`typ-${type.slug}`}
            className={`flex flex-col gap-4 p-5 border ${selected ? "bd-accent bg-tint" : "bd bg-sheet"}`}
            style={selected ? { borderColor: "var(--accent)" } : undefined}
          >
            <div className="flex items-start gap-4">
              <Silhouette facts={type.facts} />
              <div className="flex flex-col gap-1 min-w-0">
                <h3 className="f-display text-xl font-semibold t-ink m-0">{type.name}</h3>
                <span className={`eyebrow ${type.allowed ? "t-accent" : "t-alert"}`}>
                  {type.allowed ? t("configurator.types.allowed") : t("configurator.types.blocked")}
                </span>
              </div>
            </div>
            <Fakten facts={type.facts} />
            {!type.allowed && <Pruefungen title={t("configurator.types.reasons")} checks={type.reasons} tone="t-alert" />}
            <Pruefungen title={t("configurator.types.hints")} checks={type.hints.filter((h) => !commonKeys.has(hintKey(h)))} tone="t-mute" />
            {error && error.slug === type.slug && (
              <p role="alert" className="text-sm t-alert m-0">
                {t("configurator.types.selectError")}
              </p>
            )}
            {!type.allowed &&
              suggestions.map((suggestion) => (
                <p key={suggestion.slug} className="text-sm m-0 t-ink">
                  {t("configurator.types.suggestion", { name: suggestion.name })}{" "}
                  <a className="link" href={`#typ-${suggestion.slug}`}>
                    {t("configurator.types.showSuggestion", { name: suggestion.name })}
                  </a>
                </p>
              ))}
            <div className="mt-auto pt-2">
              {selected ? (
                <span className="eyebrow t-accent">{t("configurator.types.selected")}</span>
              ) : (
                <button
                  type="button"
                  className="btn btn-primary"
                  disabled={!type.allowed || pending}
                  onClick={() => onSelect(type.slug)}
                >
                  {t("configurator.types.select")}
                </button>
              )}
            </div>
          </li>
        );
      })}
    </ul>
    </div>
  );
}
