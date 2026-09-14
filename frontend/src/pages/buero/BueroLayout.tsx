import { useTranslation } from "react-i18next";
import { NavLink, Outlet } from "react-router";

import { staffLoginUrl, useLogout, useSession } from "../../api/session";
import { Kopf } from "../../components/Kopf";
import { Kopfzeile } from "../../components/Kopfzeile";

/** Büro-Rahmen (Plan 3.2): Anmeldung, Navigation, Inhalt. Rechte prüft allein der Server. */
export function BueroLayout() {
  const { t } = useTranslation();
  const session = useSession();
  const logout = useLogout();
  const staff = session.data?.staff;

  return (
    <div className="emp">
      <Kopfzeile untertitel={t("office.area")} home="/buero">
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
        <main className="max-w-xl mx-auto px-6 py-16 flex flex-col gap-8 anim-seite">
          <Kopf titel={t("office.loginTitle")}>
            <p>{t("office.loginIntro")}</p>
          </Kopf>
          <div>
            <a className="btn btn-primary" href={staffLoginUrl(window.location.pathname)}>
              {t("office.login")}
            </a>
          </div>
        </main>
      )}

      {staff && (
        <div className="max-w-7xl mx-auto px-6 lg:px-10 py-8 grid gap-8 md:grid-cols-[12rem_1fr]">
          <nav aria-label={t("office.area")}>
            <ul className="flex md:flex-col gap-1 m-0 p-0 list-none">
              <li>
                <NavLink
                  to="/buero"
                  end
                  className={({ isActive }) => `block px-3 py-2 border-l-2 ${isActive ? "bd-accent t-ink font-medium" : "border-transparent t-mute"}`}
                >
                  {t("office.nav.home")}
                </NavLink>
              </li>
              <li>
                <NavLink
                  to="/buero/grundstuecke"
                  className={({ isActive }) => `block px-3 py-2 border-l-2 ${isActive ? "bd-accent t-ink font-medium" : "border-transparent t-mute"}`}
                >
                  {t("office.nav.sites")}
                </NavLink>
              </li>
            </ul>
          </nav>
          <main className="anim-seite">
            <Outlet context={staff} />
          </main>
        </div>
      )}
    </div>
  );
}
