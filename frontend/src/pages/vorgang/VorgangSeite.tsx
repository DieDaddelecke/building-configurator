/**
 * Seite „Mein Vorgang“ (Modul V, docs/PLAN_V_VORENTWURF_UEBERGABE.md 3.8, 4.4): Status der Anfrage, übergebene
 * Fassungen mit PDF, Nachrichten des Büros mit Antwortfeld, Zurückziehen. Ohne Vorgang auf diesem Gerät:
 * Zugangslink anfordern. Erreichbar mit Flag `inquiry` oder `submission` (V 3.11).
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { INQUIRY_FLAG, useMyInquiry, type MyInquiryOut } from "../../api/inquiry";
import { useSession } from "../../api/session";
import { useFlags } from "../../api/site";
import { SUBMISSION_FLAG, fileUrl, useCustomerMessage, useWithdraw } from "../../api/submission";
import { Kopf } from "../../components/Kopf";
import { Kopfzeile } from "../../components/Kopfzeile";
import { Fehler } from "../../inquiry/AnfrageFormular";
import { ZugangAnfordern } from "../../inquiry/ZugangAnfordern";

function Fassungen({ projectId, data }: { projectId: string; data: MyInquiryOut }) {
  const { t, i18n } = useTranslation();
  if (data.submissions.length === 0) return <p className="t-mute m-0">{t("case.noVersions")}</p>;
  return (
    <ul className="m-0 p-0 list-none flex flex-col gap-3" data-testid="fassungen">
      {data.submissions.map((s) => (
        <li key={s.sequence} className="border-t bd pt-3 flex flex-col gap-1">
          <div className="flex flex-wrap gap-2 items-baseline">
            <strong>{t("case.version", { sequence: s.sequence, date: new Date(s.created_at).toLocaleDateString(i18n.language) })}</strong>
            <span className="t-mute text-sm">· {t(s.status === "current" ? "case.current" : "case.superseded")}</span>
            {s.deviation_count > 0 && <span className="t-warn text-sm">· {t("case.deviations", { count: s.deviation_count })}</span>}
          </div>
          {s.dossier_status === "ready" ? (
            <div className="flex flex-wrap gap-3 text-sm">
              {s.files.map((file) => (
                <a key={file.name} className="link" href={fileUrl(projectId, s.sequence, file.name)} download>
                  PDF ({file.locale?.toUpperCase()})
                </a>
              ))}
            </div>
          ) : (
            <span className="text-sm t-mute">{t(s.dossier_status === "failed" ? "case.dossierFailed" : "case.dossierPending")}</span>
          )}
        </li>
      ))}
    </ul>
  );
}

function Nachrichten({ projectId, data }: { projectId: string; data: MyInquiryOut }) {
  const { t, i18n } = useTranslation();
  const [body, setBody] = useState("");
  const send = useCustomerMessage(projectId);
  const withdrawn = data.status === "zurueckgezogen";
  return (
    <div className="flex flex-col gap-3">
      {data.messages.length === 0 ? (
        <p className="t-mute m-0">{t("case.noMessages")}</p>
      ) : (
        <ol className="m-0 p-0 list-none flex flex-col gap-3" data-testid="nachrichten">
          {data.messages.map((m) => (
            <li key={m.id} className={`px-4 py-3 text-sm ${m.author === "office" ? "bg-tint" : "border bd"}`}>
              <div className="t-mute text-xs pb-1">
                {t(m.author === "office" ? "case.office" : "case.you")} · {new Date(m.created_at).toLocaleString(i18n.language)}
              </div>
              <p className="m-0 whitespace-pre-line">{m.body}</p>
            </li>
          ))}
        </ol>
      )}
      {!withdrawn && (
        <form
          className="flex flex-col gap-2 max-w-2xl"
          onSubmit={(event) => {
            event.preventDefault();
            send.mutate(body.trim(), { onSuccess: () => setBody("") });
          }}
        >
          <label className="flex flex-col gap-1">
            {t("case.reply")}
            <textarea className="field" rows={4} maxLength={4000} required value={body} onChange={(e) => setBody(e.target.value)} />
          </label>
          {send.isError && <Fehler error={send.error} />}
          <button type="submit" className="btn btn-primary self-start" disabled={send.isPending || !body.trim()}>
            {t("case.send")}
          </button>
        </form>
      )}
    </div>
  );
}

function Vorgang({ projectId, data }: { projectId: string; data: MyInquiryOut }) {
  const { t } = useTranslation();
  const withdraw = useWithdraw(projectId);
  return (
    <div className="flex flex-col gap-8">
      <p className="m-0" data-testid="vorgang-status">
        {t("case.summary", { number: data.number, status: t(`inquiry.status.${data.status}`) })}
      </p>
      {data.status === "zurueckgezogen" && <p className="bg-tint px-4 py-3 text-sm m-0 max-w-prose">{t("case.withdrawn")}</p>}
      <section aria-labelledby="vorgang-fassungen" className="flex flex-col gap-3">
        <h2 id="vorgang-fassungen" className="eyebrow m-0">{t("case.versions")}</h2>
        <Fassungen projectId={projectId} data={data} />
      </section>
      <section aria-labelledby="vorgang-nachrichten" className="flex flex-col gap-3">
        <h2 id="vorgang-nachrichten" className="eyebrow m-0">{t("case.messages")}</h2>
        <Nachrichten projectId={projectId} data={data} />
      </section>
      {data.can_withdraw && (
        <div className="flex flex-col gap-2">
          {withdraw.isError && <Fehler error={withdraw.error} />}
          <button
            type="button"
            className="btn btn-ghost self-start"
            disabled={withdraw.isPending}
            onClick={() => {
              if (window.confirm(t("case.withdrawConfirm"))) withdraw.mutate();
            }}
          >
            {t("case.withdraw")}
          </button>
        </div>
      )}
    </div>
  );
}

export function VorgangSeite() {
  const { t } = useTranslation();
  const session = useSession();
  const flags = useFlags();
  const projectId = session.data?.project_id ?? null;
  const enabled = Boolean(flags.data?.[INQUIRY_FLAG] || flags.data?.[SUBMISSION_FLAG]);
  const mine = useMyInquiry(projectId, enabled);

  let inhalt;
  if (session.isPending || flags.isPending || (projectId && enabled && mine.isPending)) {
    inhalt = <p className="t-mute">{t("loading")}</p>;
  } else if (projectId && mine.data?.exists) {
    inhalt = <Vorgang projectId={projectId} data={mine.data} />;
  } else {
    inhalt = (
      <div className="flex flex-col gap-6">
        <p className="m-0">{t("case.none")}</p>
        <ZugangAnfordern />
        <Link className="link" to="/konfigurator">
          {t("case.toConfigurator")}
        </Link>
      </div>
    );
  }

  return (
    <div className="emp">
      <Kopfzeile untertitel={t("tagline")} />
      <main className="max-w-5xl mx-auto px-6 lg:px-10 py-10 anim-seite flex flex-col gap-8">
        <Kopf eyebrow={t("configurator.eyebrow")} titel={t("case.title")}>
          <p>{t("case.intro")}</p>
        </Kopf>
        {inhalt}
      </main>
    </div>
  );
}
