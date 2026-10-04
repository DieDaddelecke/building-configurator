/** Gemeinsame Bausteine des Hausmodells im Büro: Rechte, Statusmarke, Zeitpunkte. */

import { useTranslation } from "react-i18next";

import type { HouseTemplateStatus } from "../../api/haus";
import type { components } from "../../api/schema";

type Staff = components["schemas"]["StaffInfo"];

/** Bearbeiten darf nur `catalog_admin` (docs/PLAN_HAUSMODELL.md 3.6); Architekt und Betrieb lesen. Durchsetzung: Server. */
export const canEditHouse = (staff: Staff) => staff.roles.includes("catalog_admin");

const STATUS_CLASS: Record<HouseTemplateStatus, string> = {
  draft: "t-warn bd-warn",
  reviewed: "t-ink bd-ink",
  published: "t-accent bd-accent",
  rejected: "t-mute bd",
  retired: "t-mute bd",
};

export function HausStatusmarke({ status }: { status: HouseTemplateStatus }) {
  const { t } = useTranslation();
  return <span className={`border px-2 py-0.5 text-xs f-mono ${STATUS_CLASS[status]}`}>{t(`house.status.${status}`)}</span>;
}

export const zeitpunkt = (value: string, language: string) => new Date(value).toLocaleString(language);
