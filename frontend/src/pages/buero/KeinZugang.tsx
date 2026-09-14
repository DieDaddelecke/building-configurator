import { useTranslation } from "react-i18next";
import { useSearchParams } from "react-router";

import { staffLoginUrl } from "../../api/session";
import { Kopf } from "../../components/Kopf";
import { Kopfzeile } from "../../components/Kopfzeile";

const GRUENDE = ["unknown", "inactive", "email_unverified", "mfa", "fehler"] as const;

export function KeinZugang() {
  const { t } = useTranslation();
  const [params] = useSearchParams();
  const grund = GRUENDE.find((g) => g === params.get("grund")) ?? "fehler";
  return (
    <div className="emp">
      <Kopfzeile untertitel={t("office.area")} home="/buero" />
      <main className="max-w-xl mx-auto px-6 py-16 flex flex-col gap-8">
        <Kopf titel={t("office.noAccessTitle")}>
          <p role="alert">{t(`office.noAccess.${grund}`)}</p>
        </Kopf>
        <div>
          <a className="btn btn-ghost" href={staffLoginUrl()}>
            {t("office.backToLogin")}
          </a>
        </div>
      </main>
    </div>
  );
}
