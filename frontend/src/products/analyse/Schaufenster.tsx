import { useTranslation } from "react-i18next";

import { Kopf } from "../../components/Kopf";

const SCHRITTE = ["site", "rules", "envelope"] as const;

/** Was das Werkzeug leistet – vor der Anmeldung (AN0, jetzt im Rahmen der Anmeldeseite).
 *  Der Text verspricht nichts, was noch nicht da ist: Regeln (AN2) und Baurahmen (AN3) fehlen. */
export function Schaufenster() {
  const { t } = useTranslation();
  return (
    <div className="grid gap-12 lg:grid-cols-[3fr_2fr]">
      <Kopf eyebrow={t("analyse.eyebrow")} titel={t("analyse.title")} gross>
        <p>{t("analyse.intro")}</p>
      </Kopf>
      <section aria-labelledby="schritte" className="karte p-5 self-start">
        <h2 id="schritte" className="eyebrow mb-3">
          {t("analyse.steps")}
        </h2>
        <ol className="flex flex-col gap-3 m-0 p-0 list-none num">
          {SCHRITTE.map((schritt, i) => (
            <li key={schritt} className="flex gap-3">
              <span className="f-mono t-faint">{String(i + 1).padStart(2, "0")}</span>
              <span>
                <span className="font-medium t-ink">{t(`analyse.step.${schritt}.title`)}</span>
                <span className="t-mute block text-sm">{t(`analyse.step.${schritt}.text`)}</span>
              </span>
            </li>
          ))}
        </ol>
        <p className="t-mute text-sm mt-4 mb-0">{t("analyse.soon")}</p>
      </section>
    </div>
  );
}
