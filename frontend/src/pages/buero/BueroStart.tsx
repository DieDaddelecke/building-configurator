import { useTranslation } from "react-i18next";
import { useOutletContext } from "react-router";

import type { components } from "../../api/schema";
import { Kopf } from "../../components/Kopf";

type Staff = components["schemas"]["StaffInfo"];

export function BueroStart() {
  const { t } = useTranslation();
  const staff = useOutletContext<Staff>();
  return (
    <div className="flex flex-col gap-6">
      <Kopf eyebrow={t("office.area")} titel={t("office.homeTitle")}>
        <p>{t("office.homeEmpty")}</p>
      </Kopf>
      <p className="text-sm t-mute">
        {t("office.roles")}: <span className="f-mono">{staff.roles.join(", ") || "–"}</span>
      </p>
    </div>
  );
}
