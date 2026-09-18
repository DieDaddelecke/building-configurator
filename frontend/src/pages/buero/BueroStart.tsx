import { useTranslation } from "react-i18next";
import { Link, useOutletContext } from "react-router";

import type { components } from "../../api/schema";
import { Kopf } from "../../components/Kopf";

type Staff = components["schemas"]["StaffInfo"];

export function BueroStart() {
  const { t } = useTranslation();
  const staff = useOutletContext<Staff>();
  return (
    <div className="flex flex-col gap-6">
      <Kopf eyebrow={t("office.area")} titel={t("office.homeTitle")}>
        <p>{t("office.homeIntro")}</p>
      </Kopf>
      <ul className="m-0 p-0 list-none flex flex-col gap-3">
        <li className="karte p-4">
          <Link className="link font-medium" to="/buero/grundstuecke">
            {t("office.nav.sites")}
          </Link>
          <p className="text-sm t-mute m-0 mt-1">{t("office.modules.sites")}</p>
        </li>
        <li className="karte p-4">
          <Link className="link font-medium" to="/buero/regeln">
            {t("office.nav.rules")}
          </Link>
          <p className="text-sm t-mute m-0 mt-1">{t("office.modules.rules")}</p>
        </li>
        <li className="karte p-4">
          <Link className="link font-medium" to="/buero/katalog">
            {t("office.nav.catalog")}
          </Link>
          <p className="text-sm t-mute m-0 mt-1">{t("office.modules.catalog")}</p>
        </li>
      </ul>
      <p className="text-sm t-mute">
        {t("office.roles")}: <span className="f-mono">{staff.roles.join(", ") || "–"}</span>
      </p>
    </div>
  );
}
