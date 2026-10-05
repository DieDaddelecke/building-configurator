/**
 * Befunde des Importberichts (P 12.4): nach Schwere geordnet, Text aus dem Code (E-HM-33). `error` behebt nur
 * eine neue Datei, `open` klärt das Büro im Entwurf; beide verhindern die Veröffentlichung.
 */

import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import type { HouseImportFinding, HouseTemplate } from "../../api/haus";

export const SEVERITIES = ["error", "open", "warning", "info"] as const;
export type Severity = (typeof SEVERITIES)[number];

const SEVERITY_CLASS: Record<Severity, string> = {
  error: "bd-alert bg-alert",
  open: "bd-warn bg-warn",
  warning: "bd",
  info: "bd",
};

const PERCENT = new Set(["share", "deviation"]);

const locale = (language: string) => (language === "de" ? "de-DE" : "fr-FR");

/** Zahlen für den Text: Anteile in Prozent, sonst höchstens zwei Nachkommastellen; ohne Wert ein Strich. Die
 * Neigungen eines Dachs (`slopes`) kommen als Text und bekommen das Dezimalkomma. */
export function formatParams(params: HouseImportFinding["params"], language: string): Record<string, string> {
  const format = new Intl.NumberFormat(locale(language), { maximumFractionDigits: 2 });
  const percent = new Intl.NumberFormat(locale(language), { style: "percent", maximumFractionDigits: 1 });
  return Object.fromEntries(
    Object.entries(params).map(([key, value]) => [
      key,
      typeof value === "number"
        ? PERCENT.has(key)
          ? percent.format(value)
          : format.format(value)
        : value === null || value === ""
          ? "–"
          : key === "slopes"
            ? value.replace(/(\d)\.(\d)/g, "$1,$2")
            : value,
    ]),
  );
}

/** Dach (E-HM-65): Grund der Erkennung, Ablehnung durch den Kern und gesetzte Form als Text. */
function roofTexts(t: TFunction, raw: HouseImportFinding["params"], params: Record<string, string>): Record<string, string> {
  const texts: Record<string, string> = {};
  if (typeof raw.refusal === "string") {
    texts.refusalText = t(`houseConfigurator.roofRefusal.${raw.refusal}`, { defaultValue: raw.refusal });
  }
  if (typeof raw.reason === "string") {
    texts.reasonText = t(`house.roofReason.${raw.reason}`, { ...params, ...texts, defaultValue: raw.reason });
  }
  if (typeof raw.form === "string") {
    texts.formText = t(`configurator.types.roof.${raw.form}`, { defaultValue: raw.form });
  }
  return texts;
}

export function findingText(t: TFunction, finding: HouseImportFinding, language: string): string {
  const params = formatParams(finding.params, language);
  // Nicht gelesene Bauteile: je IFC-Klasse eine Zahl
  const list = Object.entries(params)
    .map(([key, value]) => `${key} ${value}`)
    .join(", ");
  // Ein fehlender Wert bliebe sonst als Platzhalter im Text stehen
  return t(`house.finding.${finding.code}`, {
    detail: "–",
    ...params,
    ...roofTexts(t, finding.params, params),
    list,
    defaultValue: finding.code,
  });
}

/** Elemente des Entwurfs zu einem Befund: das genannte Element, sonst alle aus derselben IFC-Kennung. */
export function elementIds(template: HouseTemplate | null, finding: HouseImportFinding): string[] {
  if (finding.element_id) return [finding.element_id];
  if (!finding.ifc_guid || !template) return [];
  const elements = [
    ...template.rooms,
    ...template.openings,
    ...template.interior_walls,
    ...template.envelope.flatMap((loop) => loop.segments),
  ];
  return elements.filter((element) => element.source_ifc_guid === finding.ifc_guid).map((element) => element.id);
}

interface BefundeProps {
  findings: HouseImportFinding[];
  template: HouseTemplate | null;
  onHighlight: (ids: string[]) => void;
}

export function Befunde({ findings, template, onHighlight }: BefundeProps) {
  const { t, i18n } = useTranslation();
  if (findings.length === 0) return <p className="m-0 text-sm t-mute">{t("house.report.none")}</p>;
  const sorted = [...findings].sort((a, b) => SEVERITIES.indexOf(a.severity) - SEVERITIES.indexOf(b.severity));
  return (
    <ul className="m-0 p-0 list-none flex flex-col gap-2" aria-label={t("house.report.findings")}>
      {sorted.map((finding, i) => {
        const ids = elementIds(template, finding);
        return (
          <li key={`${finding.code}-${i}`} className={`border text-sm ${SEVERITY_CLASS[finding.severity]}`} data-severity={finding.severity}>
            <button
              type="button"
              className="w-full text-left p-3 flex flex-col gap-1 bg-transparent border-0 cursor-default"
              onMouseEnter={() => onHighlight(ids)}
              onMouseLeave={() => onHighlight([])}
              onFocus={() => onHighlight(ids)}
              onBlur={() => onHighlight([])}
            >
              <span>
                <strong className={finding.severity === "error" ? "t-alert" : finding.severity === "open" ? "t-warn" : "t-mute"}>
                  {t(`house.severity.${finding.severity}`)}
                </strong>{" "}
                {findingText(t, finding, i18n.language)}
              </span>
              {(finding.element_id || finding.ifc_guid) && (
                <span className="f-mono text-xs t-mute">
                  {[finding.element_id, finding.ifc_guid && `IFC ${finding.ifc_guid}`].filter(Boolean).join(" · ")}
                </span>
              )}
            </button>
          </li>
        );
      })}
    </ul>
  );
}
