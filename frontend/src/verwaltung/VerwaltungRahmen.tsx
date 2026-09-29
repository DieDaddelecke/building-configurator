import { useTranslation } from "react-i18next";

import { staffLoginUrl, useLogout, useSession } from "../api/session";
import { Kopf } from "../components/Kopf";
import { Kopfzeile } from "../components/Kopfzeile";
import { darfVerwalten, Verwaltung } from "./Verwaltung";

/** Rahmen der Verwaltung unter `/verwaltung`: eigene Seite neben dem Büro, weil die Daten keinem Büro gehören
 *  (PLAN_G2_VOLLSTAENDIGKEIT 3.9). Anmeldung wie im Büro. */
export function VerwaltungRahmen() {
  const { t } = useTranslation();
  const session = useSession();
  const logout = useLogout();
  const staff = session.data?.staff;
  return (
    <div className="emp">
      <Kopfzeile untertitel={t("verwaltung.title")} home="/buero">
        {staff && (
          <div className="flex items-center gap-3">
            <span className="text-sm t-mute hidden md:inline">{staff.display_name ?? staff.email}</span>
            <button type="button" className="btn btn-ghost" onClick={() => logout.mutate()} disabled={logout.isPending}>
              {t("office.logout")}
            </button>
          </div>
        )}
      </Kopfzeile>
      {session.isPending && <p className="max-w-7xl mx-auto px-6 lg:px-10 py-12 t-mute">{t("loading")}</p>}
      {session.isError && <p className="max-w-7xl mx-auto px-6 lg:px-10 py-12 t-alert">{t("error.generic")}</p>}
      {session.isSuccess && !staff && (
        <main className="max-w-xl mx-auto px-6 py-16 flex flex-col gap-8 anim-seite">
          <Kopf titel={t("office.loginTitle")}>
            <p>{t("verwaltung.loginIntro")}</p>
          </Kopf>
          <div>
            <a className="btn btn-primary" href={staffLoginUrl(window.location.pathname)}>
              {t("office.login")}
            </a>
          </div>
        </main>
      )}
      {staff && (
        <main className="max-w-7xl mx-auto px-6 lg:px-10 py-8 anim-seite">
          <Verwaltung darf={darfVerwalten(staff.roles)} />
        </main>
      )}
    </div>
  );
}
