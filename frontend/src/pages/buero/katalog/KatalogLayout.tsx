/** Büro: Rahmen der Katalogpflege (Modul H1, Plan H1 4.4) mit Unterreitern für Typen, Linien/Optionen und Preise. */

import { useTranslation } from "react-i18next";
import { NavLink, Outlet, useOutletContext } from "react-router";

import type { components } from "../../../api/schema";
import { Kopf } from "../../../components/Kopf";

type Staff = components["schemas"]["StaffInfo"];

const TABS = [
  { to: "/buero/katalog", key: "types", end: true },
  { to: "/buero/katalog/linien-optionen", key: "linesOptions", end: false },
  { to: "/buero/katalog/preise", key: "prices", end: false },
] as const;

export function KatalogLayout() {
  const { t } = useTranslation();
  const staff = useOutletContext<Staff>();
  return (
    <div className="flex flex-col gap-6">
      <Kopf titel={t("catalog.title")}>
        <p>{t("catalog.intro")}</p>
      </Kopf>
      <nav aria-label={t("catalog.title")} className="flex gap-1 flex-wrap border-b bd">
        {TABS.map((tab) => (
          <NavLink
            key={tab.key}
            to={tab.to}
            end={tab.end}
            className={({ isActive }) =>
              `px-3 py-2 -mb-px border-b-2 ${isActive ? "bd-accent t-ink font-medium" : "border-transparent t-mute"}`
            }
          >
            {t(`catalog.tabs.${tab.key}`)}
          </NavLink>
        ))}
      </nav>
      <Outlet context={staff} />
    </div>
  );
}
