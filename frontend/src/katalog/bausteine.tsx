/** Gemeinsame Bausteine der Katalogpflege: Beträge, Statusmarke, Fehleranzeige, Rechte. */

import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";
import type { VersionStatus } from "../api/catalog";
import type { components } from "../api/schema";

type Staff = components["schemas"]["StaffInfo"];

/** Bearbeiten dürfen `architect` und `catalog_admin` (ANNAHMEN H01); `ops` liest nur. Durchsetzung: Server. */
export const canEditCatalog = (staff: Staff) => staff.roles.some((r) => r === "architect" || r === "catalog_admin");

const locale = (language: string) => (language === "de" ? "de-DE" : "fr-FR");

/** Beträge liegen als Cent vor; Katalogpreise sind Bestandteile von Spannen, nie ein Gesamtpreis (L1). */
export function eur(cents: number, language: string): string {
  return new Intl.NumberFormat(locale(language), { style: "currency", currency: "EUR", maximumFractionDigits: 0 }).format(
    cents / 100,
  );
}

export const spanne = (minCents: number, maxCents: number, language: string) =>
  `${eur(minCents, language)} – ${eur(maxCents, language)}`;

export const number = (value: number, language: string, digits = 1) =>
  new Intl.NumberFormat(locale(language), { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);

const STATUS_CLASS: Record<VersionStatus, string> = {
  draft: "t-warn bd-warn",
  review: "t-warn bd-warn",
  published: "t-accent bd-accent",
  retired: "t-mute bd",
};

export function Statusmarke({ status }: { status: VersionStatus }) {
  const { t } = useTranslation();
  return <span className={`border px-2 py-0.5 text-xs f-mono ${STATUS_CLASS[status]}`}>{t(`catalog.status.${status}`)}</span>;
}

export function KatalogFehler({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (error instanceof ApiError && error.problem.status === 403) {
    return <p role="alert" className="t-alert">{t("catalog.forbidden")}</p>;
  }
  if (error instanceof ApiError) {
    return (
      <p role="alert" className="t-alert">
        {error.problem.detail ?? error.problem.title}
      </p>
    );
  }
  return <p role="alert" className="t-alert">{t("error.generic")}</p>;
}
