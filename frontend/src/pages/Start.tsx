import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { Link } from "react-router";

import { api, unwrap } from "../api/client";
import { staffLoginUrl, useLogout, useSession } from "../api/session";
import { SITE_FLAG, useFlags } from "../api/site";
import { Kopf } from "../components/Kopf";
import { Kopfzeile } from "../components/Kopfzeile";
import { darfVerwalten } from "../verwaltung/Verwaltung";

/** Öffentliche Startseite: Marke, Sprache, rechtliche Hinweise; Einstieg in die Grundstückswahl hinter Flag.
 *  Anmeldung für Büro und Architekten; angemeldet die Bereiche der Anwendung (ADR-02, ADR-03). */
export function Start() {
  const { t, i18n } = useTranslation();
  const session = useSession();
  const logout = useLogout();
  const staff = session.data?.staff;
  const flags = useFlags();
  const notices = useQuery({
    queryKey: ["legal-notices", i18n.resolvedLanguage],
    queryFn: async () => unwrap(await api.GET("/api/v1/legal/notices")),
  });

  return (
    <div className="emp">
      <Kopfzeile untertitel={t("tagline")}>
        {session.isSuccess && !staff && (
          <a className="btn btn-ghost" href={staffLoginUrl("/")}>
            {t("start.login")}
          </a>
        )}
        {staff && (
          <div className="flex items-center gap-3">
            <span className="text-sm t-mute hidden md:inline" data-testid="staff-email">
              {staff.display_name ?? staff.email}
            </span>
            <button type="button" className="btn btn-ghost" onClick={() => logout.mutate()} disabled={logout.isPending}>
              {t("office.logout")}
            </button>
          </div>
        )}
      </Kopfzeile>
      <main className="max-w-7xl mx-auto px-6 lg:px-10 py-12 lg:py-20 grid gap-12 lg:grid-cols-[3fr_2fr] anim-seite">
        <div className="flex flex-col gap-10">
          <Kopf eyebrow={t("start.eyebrow")} titel={t("start.title")} gross>
            <p>{t("start.intro")}</p>
            {flags.data?.[SITE_FLAG] && (
              <Link className="btn btn-primary mt-4" to="/grundstueck">
                {t("start.cta")}
              </Link>
            )}
          </Kopf>
          {staff && (
            <section aria-labelledby="bereiche" className="flex flex-col gap-4">
              <div>
                <h2 id="bereiche" className="eyebrow mb-1">
                  {t("start.areas")}
                </h2>
                <p className="t-mute text-sm m-0">{t("start.areasIntro", { email: staff.display_name ?? staff.email })}</p>
              </div>
              <ul className="m-0 p-0 list-none grid gap-3 sm:grid-cols-2">
                {flags.data?.[SITE_FLAG] && (
                  <Bereich titel={t("start.configurator")} text={t("start.configuratorText")} ziel="/grundstueck" />
                )}
                {/* Analyse und Verwaltung haben einen eigenen Router: Wechsel mit Neuladen (src/main.tsx) */}
                <Bereich titel={t("start.analysis")} text={t("start.analysisText")} ziel="/analyse" neuLaden />
                <Bereich titel={t("start.office")} text={t("start.officeText")} ziel="/buero" />
                {darfVerwalten(staff.roles) && (
                  <Bereich titel={t("verwaltung.title")} text={t("verwaltung.intro")} ziel="/analyse/verwaltung" neuLaden />
                )}
              </ul>
            </section>
          )}
        </div>
        <section aria-labelledby="hinweise" className="karte p-5 self-start">
          <h2 id="hinweise" className="eyebrow mb-3">
            {t("start.notices")}
          </h2>
          {notices.isPending && <p className="t-mute">{t("loading")}</p>}
          {notices.isError && <p className="t-alert">{t("error.generic")}</p>}
          {notices.data && notices.data.length === 0 && <p className="t-mute">{t("start.noNotices")}</p>}
          {notices.data && notices.data.length > 0 && (
            <ul className="flex flex-col gap-3 m-0 p-0 list-none">
              {notices.data.map((notice) => (
                <li key={notice.key} lang={notice.locale}>
                  <div className="font-medium t-ink">{notice.title}</div>
                  <p className="t-mute text-sm m-0">{notice.body}</p>
                </li>
              ))}
            </ul>
          )}
        </section>
      </main>
    </div>
  );
}

function Bereich({ titel, text, ziel, neuLaden }: { titel: string; text: string; ziel: string; neuLaden?: boolean }) {
  return (
    <li className="karte p-4">
      {neuLaden ? (
        <a className="link font-medium" href={ziel}>
          {titel}
        </a>
      ) : (
        <Link className="link font-medium" to={ziel}>
          {titel}
        </Link>
      )}
      <p className="text-sm t-mute m-0 mt-1">{text}</p>
    </li>
  );
}
