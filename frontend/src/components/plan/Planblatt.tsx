/** Planblatt mit Kopf und Schriftfeld aus dem Mockup; Inhalte kommen von außen statt aus festen Daten. */

import { useMemo, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

export interface SchriftfeldEintrag {
  label: string;
  wert: string;
}

interface PlanblattProps {
  inhalt: string;
  massstab?: string;
  schriftfeld: SchriftfeldEintrag[];
  children: ReactNode;
  overlay?: ReactNode;
  fuss?: ReactNode;
}

export function Planblatt({ inhalt, massstab, schriftfeld, children, overlay, fuss }: PlanblattProps) {
  const { t, i18n } = useTranslation();
  const stand = useMemo(() => new Date().toLocaleDateString(i18n.language), [i18n.language]);
  const felder = [...schriftfeld, { label: t("sheet.date"), wert: stand }];
  return (
    <figure className="border bd-strong bg-sheet relative m-0">
      <div className="flex items-center justify-between gap-4 px-4 py-2 border-b bd">
        <span className="eyebrow">{inhalt}</span>
        <span className="eyebrow">
          {t("sheet.scale")} {massstab ?? t("sheet.schematic")}
        </span>
      </div>
      <div className="relative px-3 py-3">
        {children}
        {overlay}
      </div>
      {fuss}
      <dl className="grid grid-cols-2 md:grid-cols-4 border-t bd-strong m-0">
        {felder.map(({ label, wert }, i) => (
          <div
            key={label}
            className={`px-3 py-2 bd ${i > 0 ? "md:border-l" : ""} ${i % 2 === 1 ? "border-l" : ""} ${i > 1 ? "border-t md:border-t-0" : ""}`}
          >
            <dt className="eyebrow">{label}</dt>
            <dd className="text-xs t-ink f-mono num m-0">{wert}</dd>
          </div>
        ))}
      </dl>
    </figure>
  );
}
