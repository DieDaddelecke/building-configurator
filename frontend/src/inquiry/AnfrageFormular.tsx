/** Anfrage an das Büro (Modul A, Plan 3.6): Kontaktformular, Codebestätigung, Ergebnis mit Vorgangsnummer.
 * Unabhängig davon, ob ein Baurahmen vorliegt (G18, Weg E) – nur ein Grundstück wird voraussetzt. */

import { useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";
import {
  useConfirmContact,
  useMyInquiry,
  useSubmitContact,
  type ContactIn,
} from "../api/inquiry";
import { useNotices } from "../site/GrundstueckPruefen";

const EMPTY_CONTACT: ContactIn = {
  name: "",
  email: "",
  phone: null,
  desired_start: null,
  financing_clarified: null,
  lotissement: "unknown",
};

function Fehler({ error }: { error: unknown }) {
  const { t } = useTranslation();
  return (
    <p role="alert" className="t-alert m-0">
      {error instanceof ApiError ? (error.problem.detail ?? error.problem.title) : t("error.generic")}
    </p>
  );
}

function TriConfirm({
  value,
  onChange,
  name,
}: {
  value: boolean | null | undefined;
  onChange: (v: boolean | null) => void;
  name: string;
}) {
  const { t } = useTranslation();
  return (
    <select
      className="field"
      value={value == null ? "unknown" : value ? "yes" : "no"}
      onChange={(e) => onChange(e.target.value === "unknown" ? null : e.target.value === "yes")}
      aria-label={t(`inquiry.contact.${name}`)}
    >
      <option value="unknown">{t("inquiry.contact.notAnswered")}</option>
      <option value="yes">{t("inquiry.yes")}</option>
      <option value="no">{t("inquiry.no")}</option>
    </select>
  );
}

function KontaktFormular({ projectId, onSent }: { projectId: string; onSent: (body: ContactIn) => void }) {
  const { t } = useTranslation();
  const [body, setBody] = useState<ContactIn>(EMPTY_CONTACT);
  const submit = useSubmitContact(projectId);
  return (
    <form
      className="flex flex-col gap-4 max-w-xl"
      onSubmit={(event) => {
        event.preventDefault();
        submit.mutate(body, { onSuccess: () => onSent(body) });
      }}
    >
      <label className="flex flex-col gap-1">
        {t("inquiry.contact.name")}
        <input
          className="field"
          required
          value={body.name}
          onChange={(e) => setBody((b) => ({ ...b, name: e.target.value }))}
        />
      </label>
      <label className="flex flex-col gap-1">
        {t("inquiry.contact.email")}
        <input
          type="email"
          className="field"
          required
          value={body.email}
          onChange={(e) => setBody((b) => ({ ...b, email: e.target.value }))}
        />
      </label>
      <label className="flex flex-col gap-1">
        {t("inquiry.contact.phone")}
        <input
          className="field"
          value={body.phone ?? ""}
          onChange={(e) => setBody((b) => ({ ...b, phone: e.target.value || null }))}
        />
      </label>
      <label className="flex flex-col gap-1">
        {t("inquiry.contact.desiredStart")}
        <input
          className="field"
          value={body.desired_start ?? ""}
          onChange={(e) => setBody((b) => ({ ...b, desired_start: e.target.value || null }))}
        />
      </label>
      <label className="flex flex-col gap-1">
        {t("inquiry.contact.financingClarified")}
        <TriConfirm
          name="financingClarified"
          value={body.financing_clarified}
          onChange={(v) => setBody((b) => ({ ...b, financing_clarified: v }))}
        />
      </label>
      <label className="flex flex-col gap-1">
        {t("inquiry.contact.lotissement")}
        <select
          className="field"
          value={body.lotissement}
          onChange={(e) => setBody((b) => ({ ...b, lotissement: e.target.value as ContactIn["lotissement"] }))}
        >
          <option value="unknown">{t("inquiry.contact.notAnswered")}</option>
          <option value="yes">{t("inquiry.yes")}</option>
          <option value="no">{t("inquiry.no")}</option>
        </select>
      </label>
      {submit.isError && <Fehler error={submit.error} />}
      <button type="submit" className="btn btn-primary self-start" disabled={submit.isPending}>
        {t("inquiry.contact.submit")}
      </button>
    </form>
  );
}

function CodeBestaetigung({
  projectId,
  contact,
  onResend,
  onDone,
}: {
  projectId: string;
  contact: ContactIn;
  onResend: () => void;
  onDone: (number: string) => void;
}) {
  const { t } = useTranslation();
  const [code, setCode] = useState("");
  const [simulationConfirmation, setSimulationConfirmation] = useState(false);
  const [transmissionOffice, setTransmissionOffice] = useState(false);
  const confirm = useConfirmContact(projectId);
  const resend = useSubmitContact(projectId);
  const notices = useNotices(["notice.simulation_confirmation", "consent.transmission_office"]);
  const noticeText = (key: string, fallback: string) => notices.data?.find((n) => n.key === key)?.body ?? t(fallback);

  return (
    <form
      className="flex flex-col gap-4 max-w-xl"
      onSubmit={(event) => {
        event.preventDefault();
        confirm.mutate(
          { code, simulation_confirmation: simulationConfirmation, transmission_office: transmissionOffice },
          { onSuccess: (result) => onDone(result.number) },
        );
      }}
    >
      <p className="t-mute m-0">{t("inquiry.code.intro", { email: contact.email })}</p>
      <label className="flex flex-col gap-1">
        {t("inquiry.code.label")}
        <input
          className="field f-mono"
          required
          pattern="\d{6}"
          inputMode="numeric"
          value={code}
          onChange={(e) => setCode(e.target.value)}
        />
      </label>
      <label className="flex items-start gap-2">
        <input
          type="checkbox"
          checked={simulationConfirmation}
          onChange={(e) => setSimulationConfirmation(e.target.checked)}
        />
        <span className="text-sm">{noticeText("notice.simulation_confirmation", "inquiry.consents.simulationFallback")}</span>
      </label>
      <label className="flex items-start gap-2">
        <input type="checkbox" checked={transmissionOffice} onChange={(e) => setTransmissionOffice(e.target.checked)} />
        <span className="text-sm">{noticeText("consent.transmission_office", "inquiry.consents.transmissionFallback")}</span>
      </label>
      {confirm.isError && <Fehler error={confirm.error} />}
      <div className="flex gap-3 items-center">
        <button type="submit" className="btn btn-primary" disabled={confirm.isPending}>
          {t("inquiry.code.submit")}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={resend.isPending}
          onClick={() => resend.mutate(contact, { onSuccess: onResend })}
        >
          {t("inquiry.code.resend")}
        </button>
      </div>
      {resend.isSuccess && <p className="t-mute text-sm m-0">{t("inquiry.code.resent")}</p>}
    </form>
  );
}

export function AnfrageFormular({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const mine = useMyInquiry(projectId, true);
  const [stage, setStage] = useState<{ step: "form" } | { step: "code"; contact: ContactIn } | { step: "done"; number: string }>({
    step: "form",
  });

  if (mine.isPending) return <p className="t-mute">{t("loading")}</p>;

  if (mine.data?.exists) {
    return (
      <div className="flex flex-col gap-2">
        <h2 className="eyebrow m-0">{t("inquiry.title")}</h2>
        <p className="m-0">{t("inquiry.status.summary", { number: mine.data.number, status: t(`inquiry.status.${mine.data.status}`) })}</p>
      </div>
    );
  }

  if (stage.step === "done") {
    return (
      <div className="flex flex-col gap-2">
        <h2 className="eyebrow m-0">{t("inquiry.done.title")}</h2>
        <p className="m-0">{t("inquiry.done.text", { number: stage.number })}</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <h2 className="eyebrow m-0">{t("inquiry.title")}</h2>
      <p className="t-mute m-0 max-w-prose">{t("inquiry.intro")}</p>
      {stage.step === "form" && (
        <KontaktFormular projectId={projectId} onSent={(contact) => setStage({ step: "code", contact })} />
      )}
      {stage.step === "code" && (
        <CodeBestaetigung
          projectId={projectId}
          contact={stage.contact}
          onResend={() => undefined}
          onDone={(number) => setStage({ step: "done", number })}
        />
      )}
    </div>
  );
}
