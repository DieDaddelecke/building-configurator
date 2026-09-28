import { useTranslation } from "react-i18next";

import type { components } from "../api/schema";

type VersionOut = components["schemas"]["VersionOut"];
type PassageOut = components["schemas"]["PassageOut"];

/**
 * Abdeckung der Textstellen einer Regelwerksversion (docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.8): wie viele Stellen
 * mit Vorschriftscharakter einer Regel zugeordnet sind, welche offen blieben und welche die Nachsuche als
 * „betrifft kein Einfamilienhaus“ eingestuft hat. Offene Stellen prüft der Architekt selbst – nichts fehlt still.
 * Ältere Versionen ohne Zählung zeigen nichts.
 */
export function Abdeckung({ version, documentUrl }: { version: VersionOut | null | undefined; documentUrl?: string | null }) {
  const { t } = useTranslation();
  const counts = version?.coverage;
  if (!version || !counts || counts.passages_total == null) return null;
  const link = (page: number) => (documentUrl ? `${documentUrl}#page=${page}` : undefined);
  const stelle = (passage: PassageOut, index: number) => (
    <li key={index} className="py-1 border-t bd">
      {link(passage.page) ? (
        <a className="link f-mono" href={link(passage.page)} target="_blank" rel="noreferrer">
          {t("rules.page", { page: passage.page })}
        </a>
      ) : (
        <span className="f-mono">{t("rules.page", { page: passage.page })}</span>
      )}{" "}
      {passage.reason && <span className="chip">{t(`rules.coverage.reason.${passage.reason}`, { defaultValue: passage.reason })}</span>}{" "}
      <span className="t-mute">{passage.text}</span>
    </li>
  );
  return (
    <div className="text-sm flex flex-col gap-1" data-testid="abdeckung">
      <p className="m-0">
        {t("rules.coverage.line", {
          assigned: counts.passages_assigned ?? 0,
          total: counts.passages_total,
          open: counts.passages_open ?? 0,
        })}
        {!counts.gap_search && <span className="t-mute"> · {t("rules.coverage.notSearched")}</span>}
      </p>
      {version.open_passages.length > 0 && (
        <details>
          <summary className="cursor-pointer t-warn">{t("rules.coverage.openTitle", { count: version.open_passages.length })}</summary>
          <p className="t-mute m-0 mt-1">{t("rules.coverage.openHint")}</p>
          <ul className="m-0 p-0 list-none">{version.open_passages.map(stelle)}</ul>
        </details>
      )}
      {version.out_of_scope_passages.length > 0 && (
        <details>
          <summary className="cursor-pointer t-mute">
            {t("rules.coverage.outOfScopeTitle", { count: version.out_of_scope_passages.length })}
          </summary>
          <ul className="m-0 p-0 list-none">{version.out_of_scope_passages.map(stelle)}</ul>
        </details>
      )}
    </div>
  );
}
