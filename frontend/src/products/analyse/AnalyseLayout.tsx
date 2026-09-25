import { useTranslation } from "react-i18next";
import { Outlet, useSearchParams } from "react-router";

import { staffLoginUrl, useLogout, useSession } from "../../api/session";
import { Kopfzeile } from "../../components/Kopfzeile";
import { Schaufenster } from "./Schaufenster";

/** Rahmen des Analyse-Produkts (AN1): Anmeldung als Mitarbeiter, Kopfzeile, Inhalt.
 *  Rechte prüft allein der Server; ohne Rolle `architect` liefern die Endpunkte 403 oder 404. */
export function AnalyseLayout() {
  const { t } = useTranslation();
  const [suchparameter] = useSearchParams();
  const session = useSession();
  const logout = useLogout();
  const staff = session.data?.staff;
  // Abgelehnte Anmeldung kommt als `?grund=` zurück (app/products.py `staff_denied`)
  const grund = suchparameter.get("grund");

  return (
    <div className="emp">
      <Kopfzeile untertitel={t("analyse.tagline")}>
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

      {session.isPending && <p className="max-w-7xl mx-auto px-6 lg:px-10 py-12 t-mute">{t("loading")}</p>}
      {session.isError && <p className="max-w-7xl mx-auto px-6 lg:px-10 py-12 t-alert">{t("error.generic")}</p>}

      {session.isSuccess && !staff && (
        <main className="max-w-7xl mx-auto px-6 lg:px-10 py-12 flex flex-col gap-10 anim-seite">
          <Schaufenster />
          <div>
            {grund && (
              <p className="t-alert mb-3" role="alert">
                {t([`analyse.login.denied.${grund}`, "analyse.login.denied.fehler"])}
              </p>
            )}
            <a className="btn btn-primary" href={staffLoginUrl(window.location.pathname)}>
              {t("office.login")}
            </a>
            <p className="t-mute text-sm mt-3 mb-0">{t("analyse.login.intro")}</p>
          </div>
        </main>
      )}

      {staff && (
        <main className="max-w-7xl mx-auto px-6 lg:px-10 py-8 anim-seite">
          <Outlet />
        </main>
      )}

      {/* Hinweis nach E-A5, solange nur das eigene Büro arbeitet; vor AN6 juristisch prüfen */}
      <footer className="max-w-7xl mx-auto px-6 lg:px-10 py-8">
        <p className="t-faint text-xs m-0">{t("analyse.disclaimer")}</p>
      </footer>
    </div>
  );
}
