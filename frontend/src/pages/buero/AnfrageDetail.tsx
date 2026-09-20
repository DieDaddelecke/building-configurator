/** Büro: Anfrage-Detail (Modul A, Plan 3.6/3.8) – stellt zusammen, was G1/G2/G3 einzeln schon prüfen lassen:
 * Kontakt, Status, Grundstück mit Kanten, Regeln mit Zitat, Baurahmen. Kein neuer Prüfmechanismus. Modul V
 * ergänzt die übergebenen Fassungen mit Dossier und die Nachrichten an den Kunden. */

import { useTranslation } from "react-i18next";
import { Link, useParams } from "react-router";

import { useStaffEnvelope } from "../../api/envelope";
import { useSetInquiryStatus, useStaffInquiry, type InquiryStatus, type OfficeStatus } from "../../api/inquiry";
import { useStaffSite } from "../../api/site";
import { Baurahmen } from "../../envelope/Baurahmen";
import { Kopf } from "../../components/Kopf";
import { Fassungen, Nachrichten } from "./AnfrageFassungen";
import { Detail as GrundstueckDetail, Fehler, ProjektRegeln } from "./Grundstuecke";

/** Zustände, die das Büro setzt; `zurueckgezogen` setzt nur der Kunde (V 3.8). */
const STATUSES: InquiryStatus[] = ["neu", "in_bearbeitung", "rueckfrage", "beantwortet", "geschlossen"];

function Kontakt({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const inquiry = useStaffInquiry(projectId);
  const setStatus = useSetInquiryStatus(projectId);
  if (inquiry.isPending) return <p className="t-mute">{t("loading")}</p>;
  if (inquiry.isError) return <Fehler error={inquiry.error} />;
  const data = inquiry.data;
  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center gap-3 flex-wrap">
        <span className="f-mono text-sm">{data.number}</span>
        <select
          className="field"
          value={data.status}
          onChange={(e) => setStatus.mutate(e.target.value as OfficeStatus)}
          disabled={setStatus.isPending}
        >
          {(data.status === "zurueckgezogen" ? [...STATUSES, data.status] : STATUSES).map((s) => (
            <option key={s} value={s} disabled={s === "zurueckgezogen"}>
              {t(`inquiry.status.${s}`)}
            </option>
          ))}
        </select>
      </div>
      <dl className="m-0 max-w-xl">
        {(
          [
            ["inquiry.contact.name", data.customer.name],
            ["inquiry.contact.email", data.customer.email],
            ["inquiry.contact.phone", data.customer.phone ?? "–"],
            ["inquiry.contact.desiredStart", data.customer.desired_start ?? "–"],
            [
              "inquiry.contact.financingClarified",
              data.customer.financing_clarified === null
                ? t("inquiry.contact.notAnswered")
                : t(data.customer.financing_clarified ? "inquiry.yes" : "inquiry.no"),
            ],
            ["inquiry.contact.lotissement", t(`inquiry.lotissement.${data.customer.lotissement}`)],
          ] as const
        ).map(([key, value]) => (
          <div key={key} className="flex justify-between gap-4 py-2 border-t bd">
            <dt className="t-mute">{t(key)}</dt>
            <dd className="m-0 t-ink text-right">{value}</dd>
          </div>
        ))}
      </dl>
      <ul className="m-0 p-0 list-none text-sm t-mute" aria-label={t("office.inquiries.consents")}>
        {data.consents.map((c, index) => (
          <li key={`${c.kind}-${index}`}>
            {t(`inquiry.consents.${c.kind}`)} · {new Date(c.confirmed_at).toLocaleString()}
          </li>
        ))}
      </ul>
      <Fassungen projectId={projectId} data={data} />
      <Nachrichten projectId={projectId} data={data} />
    </div>
  );
}

function BaurahmenBereich({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const envelope = useStaffEnvelope(projectId);
  if (envelope.isPending) return <p className="t-mute">{t("loading")}</p>;
  if (envelope.isError) return <Fehler error={envelope.error} />;
  return <Baurahmen envelope={envelope.data} projectId={projectId} rolle="architect" />;
}

export function AnfrageDetail() {
  const { t } = useTranslation();
  const { projectId = "" } = useParams();
  const site = useStaffSite(projectId);
  return (
    <div className="flex flex-col gap-8">
      <Link className="link text-sm" to="/buero/anfragen">
        {t("office.inquiries.back")}
      </Link>
      <Kopf titel={t("office.inquiries.detailTitle")}>
        <p className="f-mono text-sm">{projectId}</p>
      </Kopf>
      <Kontakt projectId={projectId} />
      <div className="border-t bd pt-8">
        <BaurahmenBereich projectId={projectId} />
      </div>
      {site.isPending && <p className="t-mute">{t("loading")}</p>}
      {site.isError && <Fehler error={site.error} />}
      {site.data && (
        <div className="border-t bd pt-8">
          <GrundstueckDetail site={site.data} />
        </div>
      )}
      <ProjektRegeln projectId={projectId} />
    </div>
  );
}
