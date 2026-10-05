/** Rechtliche Hinweise und freier Modus über dem Konfigurator und dem Hausmodell (L7, D11). */

import { useTranslation } from "react-i18next";

import { useNotices } from "../site/GrundstueckPruefen";

/** Rückfalltexte, solange die Rechtstexte nach L7 nicht veröffentlicht sind (G16). */
const FALLBACK_NOTICES: Record<string, string> = {
  "notice.envelope_simulation": "envelope.notices.simulation",
  "notice.rules_simulation": "rules.notices.simulation",
  "notice.rules_lotissement": "rules.notices.lotissement",
  "notice.cadastre_accuracy": "site.notices.cadastre_accuracy",
  "notice.manual_sketch": "site.notices.manual_sketch",
};

export function Hinweise({ keys, freeReason }: { keys: readonly string[]; freeReason: string | null }) {
  const { t } = useTranslation();
  const notices = useNotices(keys);
  return (
    <section className="flex flex-col gap-2 text-sm" aria-label={t("site.notices.title")}>
      {freeReason && <p className="bg-warn t-ink px-4 py-3 m-0">{t(`configurator.mode.${freeReason}`)}</p>}
      {keys.map((key) => {
        const published = notices.data?.find((n) => n.key === key);
        return (
          <p key={key} className="m-0 t-mute" lang={published?.locale}>
            {published ? published.body : t(FALLBACK_NOTICES[key] ?? key, { defaultValue: key })}
          </p>
        );
      })}
    </section>
  );
}
