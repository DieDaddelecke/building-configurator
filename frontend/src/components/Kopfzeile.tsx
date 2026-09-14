import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { LANGUAGES } from "../i18n";

export function Sprachwahl() {
  const { t, i18n } = useTranslation();
  return (
    <div role="group" aria-label={t("language.label")} className="flex gap-1">
      {LANGUAGES.map((lng) => (
        <button
          key={lng}
          type="button"
          className="chip f-mono"
          aria-pressed={i18n.resolvedLanguage === lng}
          onClick={() => void i18n.changeLanguage(lng)}
          lang={lng}
          title={t(`language.${lng}`)}
        >
          {lng.toUpperCase()}
        </button>
      ))}
    </div>
  );
}

export function Kopfzeile({ untertitel, home = "/", children }: { untertitel: string; home?: string; children?: ReactNode }) {
  const { t } = useTranslation();
  return (
    <header className="border-b bd bg-paper">
      <div className="max-w-7xl mx-auto px-6 lg:px-10 py-3 flex flex-wrap items-center gap-x-10 gap-y-2">
        <Link to={home} className="flex items-baseline gap-3 no-underline">
          <span className="f-display text-2xl font-semibold t-ink" style={{ fontStretch: "125%", letterSpacing: "-0.02em" }}>
            {t("brand")}
          </span>
          <span className="eyebrow hidden sm:inline">{untertitel}</span>
        </Link>
        <div className="flex-1 flex items-center justify-end gap-4">
          {children}
          <Sprachwahl />
        </div>
      </div>
    </header>
  );
}
