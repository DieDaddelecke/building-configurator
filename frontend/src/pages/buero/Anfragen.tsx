/** Büro: Anfragenliste mit Statusfilter (Modul A, Plan 3.6, Rolle architect/rules_admin/ops). */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { useInquiries, type InquiryStatus } from "../../api/inquiry";
import { Kopf } from "../../components/Kopf";
import { Fehler } from "./Grundstuecke";

const STATUSES: (InquiryStatus | "")[] = [
  "",
  "neu",
  "in_bearbeitung",
  "rueckfrage",
  "beantwortet",
  "geschlossen",
  "zurueckgezogen",
];

export function Anfragen() {
  const { t, i18n } = useTranslation();
  const [status, setStatus] = useState<InquiryStatus | "">("");
  const inquiries = useInquiries(status);
  return (
    <div className="flex flex-col gap-6">
      <Kopf titel={t("office.inquiries.title")}>
        <p>{t("office.inquiries.intro")}</p>
      </Kopf>
      <div role="group" aria-label={t("office.inquiries.statusFilter")} className="flex gap-1 flex-wrap">
        {STATUSES.map((value) => (
          <button key={value || "all"} type="button" className="chip" aria-pressed={status === value} onClick={() => setStatus(value)}>
            {value ? t(`inquiry.status.${value}`) : t("office.inquiries.allStatuses")}
          </button>
        ))}
      </div>
      {inquiries.isPending && <p className="t-mute">{t("loading")}</p>}
      {inquiries.isError && <Fehler error={inquiries.error} />}
      {inquiries.data && inquiries.data.length === 0 && <p className="t-mute">{t("office.inquiries.empty")}</p>}
      {inquiries.data && inquiries.data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-left border-b bd-strong">
                <th scope="col" className="py-2 pr-3 font-medium">{t("office.inquiries.number")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("inquiry.contact.name")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("office.inquiries.status")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("office.inquiries.envelope")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("office.inquiries.design")}</th>
                <th scope="col" className="py-2 font-medium">{t("office.inquiries.created")}</th>
              </tr>
            </thead>
            <tbody>
              {inquiries.data.map((item) => (
                <tr key={item.project_id} className="border-b bd">
                  <td className="py-2 pr-3">
                    <Link className="link f-mono" to={`/buero/anfragen/${item.project_id}`}>
                      {item.number}
                    </Link>
                  </td>
                  <td className="py-2 pr-3">{item.customer_name}</td>
                  <td className="py-2 pr-3">{t(`inquiry.status.${item.status}`)}</td>
                  <td className="py-2 pr-3">{item.has_envelope ? t("inquiry.yes") : t("inquiry.no")}</td>
                  <td className="py-2 pr-3">
                    {item.submissions ? t("office.inquiries.designCount", { count: item.submissions }) : t("office.inquiries.noDesign")}
                    {item.deviation_count ? (
                      <span className="t-alert"> · {t("office.inquiries.deviations", { count: item.deviation_count })}</span>
                    ) : null}
                  </td>
                  <td className="py-2 t-mute">{new Date(item.created_at).toLocaleString(i18n.language)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
