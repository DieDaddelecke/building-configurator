/** Büro: Fassungen des Vorentwurfs und Nachrichten an den Kunden (Modul V, docs/PLAN_V_VORENTWURF_UEBERGABE.md
 * 3.1, 3.7, 3.8). Die Fassung zeigt den übergebenen Stand aus ihrem Snapshot, nicht die Live-Konfiguration. */

import { useState } from "react";
import { useTranslation } from "react-i18next";

import type { InquiryDetailOut } from "../../api/inquiry";
import { staffFileUrl, useOfficeMessage, useRegenerateDossier, type StaffSubmissionOut } from "../../api/submission";
import { checkText, localLabel, money } from "../../configuration/format";
import { Fehler } from "./Grundstuecke";

function Fassung({ projectId, submission, revision }: { projectId: string; submission: StaffSubmissionOut; revision: number | null }) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const regenerate = useRegenerateDossier(projectId);
  const summary = submission.summary;
  const names = Object.fromEntries(summary.options.map((o) => [o.slug, localLabel(o, lng)]));
  const changed = submission.status === "current" && revision != null && revision > submission.configuration_revision;
  return (
    <li className="border-t bd pt-4 flex flex-col gap-2" data-testid={`fassung-${submission.sequence}`}>
      <div className="flex flex-wrap gap-2 items-baseline">
        <strong>{t("office.inquiries.version", { sequence: submission.sequence })}</strong>
        <span className="t-mute text-sm">
          · {t(submission.status === "current" ? "office.inquiries.current" : "office.inquiries.superseded")} ·{" "}
          {new Date(submission.created_at).toLocaleString(lng)}
        </span>
      </div>
      {changed && <p className="t-warn text-sm m-0">{t("office.inquiries.changedSince", { revision })}</p>}
      <dl className="m-0 text-sm grid grid-cols-1 sm:grid-cols-4 gap-x-4 gap-y-1">
        <dt className="t-mute">{t("office.inquiries.type")}</dt>
        <dd className="m-0 sm:col-span-3">
          {summary.type_name ?? "–"} {summary.type_version != null && <span className="t-mute">v{summary.type_version}</span>}
          {summary.type_retired && <span className="t-warn"> · {t("office.inquiries.retired")}</span>}
        </dd>
        <dt className="t-mute">{t("office.inquiries.package")}</dt>
        <dd className="m-0 sm:col-span-3">{summary.package_label_de || summary.package_label_fr ? localLabel({ label_de: summary.package_label_de, label_fr: summary.package_label_fr }, lng) : "–"}</dd>
        <dt className="t-mute">{t("office.inquiries.options")}</dt>
        <dd className="m-0 sm:col-span-3">
          {summary.options.length ? summary.options.map((o) => localLabel(o, lng) + (o.included ? ` (${t("configurator.options.included")})` : "")).join(", ") : "–"}
        </dd>
        <dt className="t-mute">{t("office.inquiries.costs")}</dt>
        <dd className="m-0 sm:col-span-3 num">
          {summary.costs_display
            ? t("configurator.costs.range", { min: money(summary.costs_display.min_cents, lng), max: money(summary.costs_display.max_cents, lng) })
            : t("office.inquiries.noCosts")}
        </dd>
      </dl>
      <p className={`text-sm m-0 ${submission.deviation_count ? "t-alert" : "t-mute"}`}>
        {submission.deviation_count
          ? t("office.inquiries.deviations", { count: submission.deviation_count })
          : t("office.inquiries.noDeviations")}
        {" · "}
        {t("office.inquiries.openPoints", { count: submission.open_points })}
      </p>
      {summary.deviations.length > 0 && (
        <ul className="m-0 pl-5 text-sm t-alert">
          {summary.deviations.map((check, index) => (
            <li key={`${check.code}-${index}`}>{checkText(check, t, lng, names)}</li>
          ))}
        </ul>
      )}
      <div className="flex flex-wrap gap-3 items-center text-sm">
        {submission.dossier_status === "ready" &&
          submission.files.map((file) => (
            <a key={file.name} className="link" href={staffFileUrl(projectId, submission.sequence, file.name)} download>
              {file.kind === "pdf" ? `PDF ${file.locale?.toUpperCase()}` : `DXF ${file.variant === "L93" ? "Lambert-93" : "local"}`}
            </a>
          ))}
        {submission.dossier_status === "pending" && <span className="t-mute">{t("office.inquiries.dossier.pending")}</span>}
        {submission.dossier_status === "failed" && (
          <>
            <span className="t-alert">{t("office.inquiries.dossier.failed", { error: submission.dossier_error ?? "" })}</span>
            <button type="button" className="btn btn-ghost" disabled={regenerate.isPending} onClick={() => regenerate.mutate(submission.sequence)}>
              {t("office.inquiries.regenerate")}
            </button>
          </>
        )}
      </div>
      {regenerate.isError && <Fehler error={regenerate.error} />}
    </li>
  );
}

export function Fassungen({ projectId, data }: { projectId: string; data: InquiryDetailOut }) {
  const { t } = useTranslation();
  if (data.submissions.length === 0) return null;
  return (
    <section aria-labelledby="anfrage-fassungen" className="flex flex-col gap-2">
      <h2 id="anfrage-fassungen" className="eyebrow m-0">{t("office.inquiries.versions")}</h2>
      <ul className="m-0 p-0 list-none flex flex-col gap-3">
        {data.submissions.map((submission) => (
          <Fassung key={submission.sequence} projectId={projectId} submission={submission} revision={data.configuration_revision} />
        ))}
      </ul>
    </section>
  );
}

export function Nachrichten({ projectId, data }: { projectId: string; data: InquiryDetailOut }) {
  const { t, i18n } = useTranslation();
  const [body, setBody] = useState("");
  const send = useOfficeMessage(projectId);
  return (
    <section aria-labelledby="anfrage-nachrichten" className="flex flex-col gap-3">
      <h2 id="anfrage-nachrichten" className="eyebrow m-0">{t("office.inquiries.messages")}</h2>
      {data.messages.length === 0 ? (
        <p className="t-mute m-0 text-sm">{t("office.inquiries.noMessages")}</p>
      ) : (
        <ol className="m-0 p-0 list-none flex flex-col gap-2 max-w-3xl">
          {data.messages.map((m) => (
            <li key={m.id} className={`px-4 py-3 text-sm ${m.author === "office" ? "bg-tint" : "border bd"}`}>
              <div className="t-mute text-xs pb-1">
                {t(m.author === "office" ? "office.inquiries.office" : "office.inquiries.customer")} ·{" "}
                {new Date(m.created_at).toLocaleString(i18n.language)}
              </div>
              <p className="m-0 whitespace-pre-line">{m.body}</p>
            </li>
          ))}
        </ol>
      )}
      <form
        className="flex flex-col gap-2 max-w-3xl"
        onSubmit={(event) => {
          event.preventDefault();
          send.mutate(body.trim(), { onSuccess: () => setBody("") });
        }}
      >
        <label className="flex flex-col gap-1">
          {t("office.inquiries.message")}
          <textarea className="field" rows={4} maxLength={4000} required value={body} onChange={(e) => setBody(e.target.value)} />
        </label>
        <p className="text-xs t-mute m-0">{t("office.inquiries.sendHint")}</p>
        {send.isError && <Fehler error={send.error} />}
        <button type="submit" className="btn btn-primary self-start" disabled={send.isPending || !body.trim()}>
          {t("office.inquiries.send")}
        </button>
      </form>
    </section>
  );
}
