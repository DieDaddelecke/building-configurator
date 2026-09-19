/**
 * Öffentliche Seite des Konfigurators, Teil H2 (Plan H2 4.4): Haustyp wählen und auf dem Grundstück
 * platzieren. Alles ist Simulation (D11, L7). Linie, Optionen und Kosten folgen mit H3.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import {
  CONFIGURATOR_FLAG,
  problemOf,
  usePatchConfiguration,
  useConfiguration,
  useTypes,
  type CheckOut,
} from "../../api/configuration";
import { ENVELOPE_FLAG, useEnvelope } from "../../api/envelope";
import { useSession } from "../../api/session";
import { useFlags, useSite } from "../../api/site";
import { Kopf } from "../../components/Kopf";
import { Kopfzeile } from "../../components/Kopfzeile";
import { Implantation } from "../../configuration/Implantation";
import { TypKarten } from "../../configuration/TypKarten";
import { useNotices } from "../../site/GrundstueckPruefen";

type Schritt = "type" | "placement";

/** Rückfalltexte, solange die Rechtstexte nach L7 nicht veröffentlicht sind (G16). */
const FALLBACK_NOTICES: Record<string, string> = {
  "notice.envelope_simulation": "envelope.notices.simulation",
  "notice.rules_simulation": "rules.notices.simulation",
  "notice.rules_lotissement": "rules.notices.lotissement",
  "notice.cadastre_accuracy": "site.notices.cadastre_accuracy",
  "notice.manual_sketch": "site.notices.manual_sketch",
};

function Schritte({ schritt, onGehe, typeChosen }: { schritt: Schritt; onGehe: (s: Schritt) => void; typeChosen: boolean }) {
  const { t } = useTranslation();
  const items: { key: Schritt; enabled: boolean }[] = [
    { key: "type", enabled: true },
    { key: "placement", enabled: typeChosen },
  ];
  return (
    <nav aria-label={t("configurator.steps.label")} className="flex flex-wrap gap-2">
      {items.map(({ key, enabled }, index) => (
        <button
          key={key}
          type="button"
          className="chip"
          aria-pressed={schritt === key}
          aria-current={schritt === key ? "step" : undefined}
          disabled={!enabled}
          onClick={() => onGehe(key)}
        >
          {index + 1} · {t(`configurator.steps.${key}`)}
        </button>
      ))}
    </nav>
  );
}

function Hinweise({ keys, freeReason }: { keys: readonly string[]; freeReason: string | null }) {
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

export function KonfiguratorSeite() {
  const { t } = useTranslation();
  const session = useSession();
  const flags = useFlags();
  const projectId = session.data?.project_id ?? null;
  const enabled = Boolean(flags.data?.[CONFIGURATOR_FLAG]);
  const envelopeEnabled = Boolean(flags.data?.[ENVELOPE_FLAG]);
  const site = useSite(projectId);
  const types = useTypes(projectId, enabled);
  const configuration = useConfiguration(projectId, enabled);
  const envelope = useEnvelope(projectId, envelopeEnabled && site.data?.origin !== "manual_sketch");
  const patch = usePatchConfiguration(projectId ?? "");
  const [gewaehlt, setSchritt] = useState<Schritt | null>(null);

  const current = configuration.data ?? null;
  const typeChosen = Boolean(current?.type);
  // Ohne Wahl beginnt der Kunde beim Typ, mit Wahl bei der Lage; er kann jederzeit wechseln
  const schritt: Schritt = gewaehlt ?? (typeChosen ? "placement" : "type");

  const select = (slug: string) => {
    patch.mutate(
      { body: { type_slug: slug }, revision: current?.revision ?? 0 },
      { onSuccess: () => setSchritt("placement") },
    );
  };

  let inhalt;
  if (flags.isPending || session.isPending || site.isPending) {
    inhalt = <p className="t-mute">{t("loading")}</p>;
  } else if (flags.isError || session.isError || site.isError) {
    inhalt = <p className="t-alert" role="alert">{t("error.generic")}</p>;
  } else if (!enabled) {
    inhalt = (
      <Kopf eyebrow={t("configurator.disabled.eyebrow")} titel={t("configurator.disabled.title")}>
        <p>{t("configurator.disabled.text")}</p>
        <Link className="link" to="/">
          {t("error.home")}
        </Link>
      </Kopf>
    );
  } else if (!site.data) {
    inhalt = (
      <div className="flex flex-col gap-4">
        <Kopf eyebrow={t("configurator.eyebrow")} titel={t("configurator.title")}>
          <p>{t("configurator.needSite")}</p>
        </Kopf>
        <Link className="link" to="/grundstueck">
          {t("configurator.back")}
        </Link>
      </div>
    );
  } else if (types.isPending || configuration.isPending) {
    inhalt = <p className="t-mute">{t("loading")}</p>;
  } else if (types.isError || configuration.isError) {
    inhalt = <p className="t-alert" role="alert">{t("configurator.types.loadError")}</p>;
  } else {
    const selectProblem = problemOf(patch.error);
    const failed = patch.variables?.body.type_slug;
    const error = selectProblem && failed ? { slug: failed, reasons: (selectProblem.reasons ?? []) as CheckOut[] } : null;
    inhalt = (
      <div className="flex flex-col gap-8">
        <Kopf eyebrow={t("configurator.eyebrow")} titel={t("configurator.title")}>
          <p>{t("configurator.intro")}</p>
        </Kopf>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <Schritte schritt={schritt} onGehe={setSchritt} typeChosen={typeChosen} />
          <Link className="link text-sm" to="/grundstueck">
            {t("configurator.back")}
          </Link>
        </div>
        <Hinweise keys={types.data.notices} freeReason={current?.free_reason ?? types.data.free_reason} />
        {schritt === "type" || !current?.type ? (
          <section aria-labelledby="konfigurator-typen" className="flex flex-col gap-5">
            <h2 id="konfigurator-typen" className="eyebrow m-0">{t("configurator.types.title")}</h2>
            <p className="text-sm t-mute m-0 max-w-prose">{t("configurator.types.intro")}</p>
            <TypKarten
              types={types.data.types}
              selectedSlug={current?.type?.slug ?? null}
              onSelect={select}
              pending={patch.isPending}
              error={error}
            />
          </section>
        ) : (
          <section aria-labelledby="konfigurator-lage" className="flex flex-col gap-5">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <h2 id="konfigurator-lage" className="eyebrow m-0">
                {t("configurator.placement.title")} · {current.type.name}
              </h2>
              <button type="button" className="link text-sm" onClick={() => setSchritt("type")}>
                {t("configurator.types.change")}
              </button>
            </div>
            <p className="text-sm t-mute m-0 max-w-prose">{t("configurator.placement.intro")}</p>
            <Implantation
              key={current.revision}
              projectId={site.data.project_id}
              site={site.data}
              configuration={current}
              envelope={envelope.data ?? null}
            />
            <p className="bg-tint t-ink px-4 py-3 text-sm m-0 max-w-prose">{t("configurator.placement.next")}</p>
          </section>
        )}
      </div>
    );
  }

  return (
    <div className="emp">
      <Kopfzeile untertitel={t("tagline")} />
      <main className="max-w-7xl mx-auto px-6 lg:px-10 py-10 anim-seite">{inhalt}</main>
    </div>
  );
}
