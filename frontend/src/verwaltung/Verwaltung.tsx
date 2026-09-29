import { useTranslation } from "react-i18next";
import { NavLink, Route, Routes } from "react-router";

import { Kopf } from "../components/Kopf";
import { ModellWahl } from "./ModellWahl";
import { LISTEN_PFAD, VERWALTUNG_PFAD } from "./pfade";
import { Referenzliste } from "./Referenzliste";
import { Referenzlisten } from "./Referenzlisten";

export const VERWALTUNG_ROLLEN = ["ops", "rules_admin"] as const;

/** Darf die Anmeldung die gemeinsame Verwaltung sehen? Rechte prüft allein der Server. */
export function darfVerwalten(roles: readonly string[] | undefined): boolean {
  return (roles ?? []).some((r) => (VERWALTUNG_ROLLEN as readonly string[]).includes(r));
}

const tab = ({ isActive }: { isActive: boolean }) =>
  `px-1 py-2 -mb-px border-b-2 ${isActive ? "bd-accent t-ink font-medium" : "border-transparent t-mute"}`;

/**
 * Verwaltung für Konfigurator und Analyse (docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.9–3.10): KI-Modell der Auswertung
 * und Referenzlisten. Dieselben Seiten unter `/verwaltung` (eigener Rahmen) und `/analyse/verwaltung` (im Rahmen
 * der Analyse); die Daten gehören keinem Büro.
 */
export function Verwaltung({ darf }: { darf: boolean }) {
  const { t } = useTranslation();
  if (!darf) {
    return (
      <p className="t-alert" role="alert">
        {t("verwaltung.noAccess")}
      </p>
    );
  }
  return (
    <div className="flex flex-col gap-6">
      <Kopf titel={t("verwaltung.title")}>
        <p>{t("verwaltung.intro")}</p>
      </Kopf>
      <nav aria-label={t("verwaltung.title")} className="flex gap-6 border-b bd">
        <NavLink to={VERWALTUNG_PFAD} end className={tab}>
          {t("verwaltung.nav.model")}
        </NavLink>
        <NavLink to={LISTEN_PFAD} className={tab}>
          {t("verwaltung.nav.reference")}
        </NavLink>
      </nav>
      <Routes>
        <Route index element={<ModellWahl darfAendern />} />
        <Route path="referenzlisten" element={<Referenzlisten />} />
        <Route path="referenzlisten/:listId" element={<Referenzliste />} />
      </Routes>
    </div>
  );
}
