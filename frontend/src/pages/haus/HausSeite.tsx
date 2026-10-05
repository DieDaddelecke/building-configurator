/**
 * Kundenweg des Hausmodells (docs/PLAN_HAUSMODELL.md 3.10, HM4) hinter der Fahne `house_model`: Haustyp wählen,
 * Ausstattung und Lage festlegen, Richtpreis und Prüfung sehen. Jede Änderung wird sofort gespeichert; den Preis
 * rechnet zuerst der Kern im Browser, maßgeblich ist der Server, der ihn beim Speichern vergleicht (L5).
 * Alles ist Simulation (D11, L7). 2D, 3D und die Wahl je Raum oder Element folgen mit HM2.
 */

import type { HouseConfiguration } from "@emprise/domain";
import type { TFunction } from "i18next";
import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { ENVELOPE_FLAG, useEnvelope, type EnvelopeOut } from "../../api/envelope";
import {
  HOUSE_MODEL_FLAG,
  useHouseConfiguration,
  useHouseDocuments,
  useHouseTemplates,
  type HouseConfigurationOut,
  type HouseConfigurationPatch,
  type HouseTemplatesOut,
} from "../../api/hausKonfiguration";
import { useSession } from "../../api/session";
import { useFlags, useSite, type SiteOut } from "../../api/site";
import { Kopf } from "../../components/Kopf";
import { Kopfzeile } from "../../components/Kopfzeile";
import { Hinweise } from "../../configuration/Hinweise";
import type { Lage } from "../../configuration/Lageplan";
import { Ausstattung } from "../../haus/Ausstattung";
import { Ergebnisse } from "../../haus/Ergebnisse";
import { HausLage } from "../../haus/HausLage";
import { HausTypen } from "../../haus/HausTypen";
import { DOMAIN_VERSION, dokumente, gleich, rechne, type Dokumente } from "../../haus/kern";
import { kundenpreis } from "../../haus/preis";
import { Preisleiste, type Aufpreis } from "../../haus/Preisleiste";
import { useSpeichern, type Fehler } from "../../haus/speichern";
import { label } from "../../haus/texte";

function fehlerText(fehler: Fehler | null, t: TFunction): string | null {
  if (!fehler || fehler.art === "typ") return null;
  const problem = fehler.problem;
  if (problem?.code === "revision_conflict") return t("houseConfigurator.save.conflict");
  if (problem?.code === "engine_unavailable") return t("houseConfigurator.save.engine");
  if (problem?.code === "house_selection_invalid") {
    return t("houseConfigurator.save.selection", { reason: (problem as { reason?: string }).reason ?? problem.code });
  }
  return t("houseConfigurator.save.error");
}

/** Aufpreise mit Bezeichnung von Slot und gewähltem Wert, in der Reihenfolge des Katalogs. */
function aufpreiseMitText(
  betraege: Record<string, number>,
  docs: Dokumente | null,
  configuration: HouseConfiguration,
  lng: string,
): Aufpreis[] {
  const slots = docs ? [...docs.catalog.slots].sort((a, b) => a.sort_order - b.sort_order) : [];
  const order = (slot: string) => {
    const index = slots.findIndex((s) => s.id === slot);
    return index < 0 ? slots.length : index;
  };
  return Object.entries(betraege)
    .filter(([, betrag]) => betrag !== 0)
    .sort(([a], [b]) => order(a) - order(b))
    .map(([slot, betrag]) => {
      const definition = slots.find((s) => s.id === slot);
      const valueId = configuration.selections[slot]?.value?.option_value_id;
      const option = docs?.catalog.option_values.find((o) => o.id === valueId);
      const text = definition ? `${label(definition.name, lng)}${option ? ` – ${label(option.name, lng)}` : ""}` : slot;
      return { slot, text, betrag };
    });
}

interface HausKonfiguratorProps {
  projectId: string;
  site: SiteOut;
  templates: HouseTemplatesOut;
  current: HouseConfigurationOut;
  envelope: EnvelopeOut | null;
}

function HausKonfigurator({ projectId, site, templates, current, envelope }: HausKonfiguratorProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const documents = useHouseDocuments(projectId, current);
  const docs = useMemo(() => (documents.data ? dokumente(documents.data) : null), [documents.data]);
  const [entwurf, setEntwurf] = useState<HouseConfiguration | null>(null);
  const [typWahl, setTypWahl] = useState(false);
  const speichern = useSpeichern(projectId, current.revision, () => setEntwurf(null));

  const gespeichert = current.configuration as unknown as HouseConfiguration;
  const auswahl = entwurf ?? gespeichert;
  const offen = entwurf !== null && !gleich(entwurf, gespeichert);
  const vorschau = useMemo(() => {
    if (!docs || !current.template) return null;
    try {
      return rechne(docs, auswahl);
    } catch {
      return null;
    }
  }, [docs, auswahl, current.template]);

  const template = current.template;
  const names = template ? { [template.slug]: label(template.name, lng) } : {};
  const browserPreis = vorschau ? kundenpreis(vorschau.price) : null;
  const zeigeVorschau = offen && browserPreis !== null;
  const gesamt = zeigeVorschau ? browserPreis.gesamt : (current.price?.gross_rounded ?? browserPreis?.gesamt ?? null);
  const betraege = zeigeVorschau ? browserPreis.aufpreise : (current.price?.deltas_rounded ?? {});

  const waehle = (next: HouseConfiguration) => {
    setEntwurf(next);
    const body: HouseConfigurationPatch = { configuration: next as unknown as HouseConfigurationPatch["configuration"] };
    if (docs) {
      try {
        body.client_price = { net_amount: rechne(docs, next).price.net_amount, domain_version: DOMAIN_VERSION };
      } catch {
        // Lässt sich die Wahl im Browser nicht rechnen, entscheidet der Server allein
      }
    }
    speichern.senden(body);
  };

  const waehleTyp = (slug: string) => {
    if (slug === template?.slug) {
      setTypWahl(false);
      return;
    }
    setEntwurf(null);
    speichern.senden({ template_slug: slug }, () => setTypWahl(false));
  };

  const platziere = ({ origin, rotation }: Lage) =>
    speichern.senden({ placement: { origin: { e: origin[0], n: origin[1] }, rotation_deg: rotation } });

  const zeigeTypen = !template || typWahl;
  const lageFehler = speichern.fehler?.art === "lage" ? speichern.fehler.problem : null;

  return (
    <div className="flex flex-col gap-8">
      <Kopf eyebrow={t("houseConfigurator.eyebrow")} titel={t("houseConfigurator.title")}>
        <p>{t("houseConfigurator.intro")}</p>
      </Kopf>
      <div className="flex flex-wrap items-center justify-between gap-4">
        {template && !typWahl ? (
          <div className="flex flex-wrap items-baseline gap-3">
            <h2 className="f-display text-2xl font-semibold t-ink m-0" data-testid="haus-name">
              {label(template.name, lng)}
            </h2>
            <button type="button" className="link text-sm" onClick={() => setTypWahl(true)}>
              {t("houseConfigurator.types.change")}
            </button>
          </div>
        ) : (
          <span />
        )}
        <Link className="link text-sm" to="/grundstueck">
          {t("houseConfigurator.back")}
        </Link>
      </div>
      <Hinweise keys={current.notices} freeReason={current.free_reason ?? templates.free_reason} />

      {zeigeTypen ? (
        <section aria-labelledby="haus-typen" className="flex flex-col gap-5">
          <div className="flex flex-wrap items-baseline justify-between gap-3">
            <h2 id="haus-typen" className="eyebrow m-0">
              {t("houseConfigurator.types.title")}
            </h2>
            {template && (
              <button type="button" className="link text-sm" onClick={() => setTypWahl(false)}>
                {t("houseConfigurator.types.keep")}
              </button>
            )}
          </div>
          <p className="text-sm t-mute m-0 max-w-prose">{t("houseConfigurator.types.intro")}</p>
          {template && <p className="text-sm t-warn m-0 max-w-prose">{t("houseConfigurator.types.changeHint")}</p>}
          <HausTypen
            templates={templates.templates}
            selectedSlug={template?.slug ?? null}
            onSelect={waehleTyp}
            pending={speichern.laeuft}
            failedSlug={speichern.fehler?.art === "typ" ? speichern.fehler.slug : null}
          />
        </section>
      ) : (
        <>
          {current.update_available && (
            <p className="bg-tint t-ink px-4 py-3 text-sm m-0 max-w-prose" data-testid="neue-version">
              {t("houseConfigurator.notice.update")}
            </p>
          )}
          {template?.retired && <p className="bg-warn t-ink px-4 py-3 text-sm m-0 max-w-prose">{t("houseConfigurator.notice.retired")}</p>}

          <section aria-labelledby="haus-ausstattung" className="flex flex-col gap-5">
            <h2 id="haus-ausstattung" className="eyebrow m-0">
              {t("houseConfigurator.equipment.title")}
            </h2>
            <p className="text-sm t-mute m-0 max-w-prose">{t("houseConfigurator.equipment.intro")}</p>
            {docs ? (
              <Ausstattung docs={docs} configuration={auswahl} onChange={waehle} />
            ) : documents.isError ? (
              <p className="t-alert" role="alert">
                {t("houseConfigurator.loadError")}
              </p>
            ) : (
              <p className="t-mute">{t("loading")}</p>
            )}
          </section>

          <section aria-labelledby="haus-lage" className="flex flex-col gap-5">
            <h2 id="haus-lage" className="eyebrow m-0">
              {t("houseConfigurator.placement.title")}
            </h2>
            <p className="text-sm t-mute m-0 max-w-prose">{t("houseConfigurator.placement.intro")}</p>
            <HausLage
              key={current.revision}
              projectId={projectId}
              site={site}
              current={current}
              envelope={envelope}
              pending={speichern.laeuft}
              problem={lageFehler}
              onPlace={platziere}
              onBoundary={(options) => speichern.senden({ boundary_options: options })}
              names={names}
            />
          </section>

          <Ergebnisse current={current} docs={docs} names={names} veraltet={offen || speichern.laeuft} />

          <Preisleiste
            gesamt={gesamt}
            aufpreise={aufpreiseMitText(betraege, docs, auswahl, lng)}
            vorschau={zeigeVorschau}
            laeuft={speichern.laeuft}
            gespeichert={current.revision > 0 && !offen}
            fehler={fehlerText(speichern.fehler, t)}
            preisGleich={speichern.preisGleich}
          />
        </>
      )}
    </div>
  );
}

export function HausSeite() {
  const { t } = useTranslation();
  const session = useSession();
  const flags = useFlags();
  const projectId = session.data?.project_id ?? null;
  const enabled = Boolean(flags.data?.[HOUSE_MODEL_FLAG]);
  const envelopeEnabled = Boolean(flags.data?.[ENVELOPE_FLAG]);
  const site = useSite(projectId);
  const withSite = enabled && Boolean(site.data);
  const templates = useHouseTemplates(projectId, withSite);
  const configuration = useHouseConfiguration(projectId, withSite);
  const envelope = useEnvelope(projectId, withSite && envelopeEnabled && site.data?.origin !== "manual_sketch");

  let inhalt;
  if (flags.isPending || session.isPending || (Boolean(projectId) && site.isPending)) {
    inhalt = <p className="t-mute">{t("loading")}</p>;
  } else if (flags.isError || session.isError || site.isError) {
    inhalt = (
      <p className="t-alert" role="alert">
        {t("error.generic")}
      </p>
    );
  } else if (!enabled) {
    inhalt = (
      <Kopf eyebrow={t("houseConfigurator.disabled.eyebrow")} titel={t("houseConfigurator.disabled.title")}>
        <p>{t("houseConfigurator.disabled.text")}</p>
        <Link className="link" to="/">
          {t("error.home")}
        </Link>
      </Kopf>
    );
  } else if (!projectId || !site.data) {
    inhalt = (
      <div className="flex flex-col gap-4">
        <Kopf eyebrow={t("houseConfigurator.eyebrow")} titel={t("houseConfigurator.title")}>
          <p>{t("houseConfigurator.needSite")}</p>
        </Kopf>
        <Link className="link" to="/grundstueck">
          {t("houseConfigurator.back")}
        </Link>
      </div>
    );
  } else if (templates.isPending || configuration.isPending) {
    inhalt = <p className="t-mute">{t("loading")}</p>;
  } else if (templates.isError || configuration.isError) {
    inhalt = (
      <p className="t-alert" role="alert">
        {t("houseConfigurator.loadError")}
      </p>
    );
  } else {
    inhalt = (
      <HausKonfigurator
        projectId={projectId}
        site={site.data}
        templates={templates.data}
        current={configuration.data}
        envelope={envelope.data ?? null}
      />
    );
  }

  return (
    <div className="emp">
      <Kopfzeile untertitel={t("tagline")} />
      <main className="max-w-7xl mx-auto px-6 lg:px-10 py-10 anim-seite">{inhalt}</main>
    </div>
  );
}
