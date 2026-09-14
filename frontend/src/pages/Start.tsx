import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import { api, unwrap } from "../api/client";
import { useSession } from "../api/session";
import { Kopf } from "../components/Kopf";
import { Kopfzeile } from "../components/Kopfzeile";

/** Öffentliche Startseite in R0: Marke, Sprache, rechtliche Hinweise. Der Bebaubarkeitscheck folgt in R1. */
export function Start() {
  const { t, i18n } = useTranslation();
  useSession();
  const notices = useQuery({
    queryKey: ["legal-notices", i18n.resolvedLanguage],
    queryFn: async () => unwrap(await api.GET("/api/v1/legal/notices")),
  });

  return (
    <div className="emp">
      <Kopfzeile untertitel={t("tagline")} />
      <main className="max-w-7xl mx-auto px-6 lg:px-10 py-12 lg:py-20 grid gap-12 lg:grid-cols-[3fr_2fr] anim-seite">
        <Kopf eyebrow={t("start.eyebrow")} titel={t("start.title")} gross>
          <p>{t("start.intro")}</p>
        </Kopf>
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
