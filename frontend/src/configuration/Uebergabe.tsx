/**
 * Übergabe des Vorentwurfs (Modul V, docs/PLAN_V_VORENTWURF_UEBERGABE.md 3.2, 4.4): Abweichungen bestätigen,
 * Bestätigung und Einwilligung, bei neuen Kunden zuerst Kontakt und Code (aus Modul A). Der Server rechnet beim
 * Absenden neu; hat sich seit dem Anzeigen etwas geändert, lädt die Seite den neuen Stand und nennt, was.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import type { ConfigurationOut } from "../api/configuration";
import { useMyInquiry, type ContactIn } from "../api/inquiry";
import { submissionProblem, useSubmitDesign, type SubmitOut } from "../api/submission";
import { Fehler, KontaktFormular } from "../inquiry/AnfrageFormular";
import { useNotices } from "../site/GrundstueckPruefen";
import { checkText, deviationsOf } from "./format";

const NOTICE_KEYS = ["notice.design_confirmation", "consent.transmission_design"] as const;

function Aenderungen({ error }: { error: unknown }) {
  const { t } = useTranslation();
  const problem = submissionProblem(error);
  if (problem?.code === "review_changed") {
    return (
      <div role="alert" className="bg-tint px-4 py-3 text-sm flex flex-col gap-1" data-testid="uebergabe-geaendert">
        <strong>{t("submission.changed.title")}</strong>
        <ul className="m-0 pl-5">
          {(problem.changes ?? []).map((part) => (
            <li key={part}>{t(`submission.changed.${part}`)}</li>
          ))}
        </ul>
        <span className="t-mute">{t("submission.changed.intro")}</span>
      </div>
    );
  }
  if (problem?.code === "submission_incomplete") {
    const missing = (problem.missing ?? []).map((m) => t(`submission.missing.${m}`, { defaultValue: m })).join(", ");
    return (
      <p role="alert" className="t-alert m-0">
        {t("submission.incomplete", { missing })}
      </p>
    );
  }
  return <Fehler error={error} />;
}

interface FormularProps {
  projectId: string;
  configuration: ConfigurationOut;
  names: Record<string, string>;
  contact: ContactIn | null;
  onDone: (result: SubmitOut) => void;
}

function UebergabeFormular({ projectId, configuration, names, contact, onDone }: FormularProps) {
  const { t, i18n } = useTranslation();
  const [code, setCode] = useState("");
  const [design, setDesign] = useState(false);
  const [transmission, setTransmission] = useState(false);
  const [acknowledged, setAcknowledged] = useState(false);
  const submit = useSubmitDesign(projectId);
  const notices = useNotices(NOTICE_KEYS);
  const noticeText = (key: string, fallback: string) => notices.data?.find((n) => n.key === key)?.body ?? t(fallback);
  const deviations = deviationsOf(configuration);

  return (
    <form
      className="flex flex-col gap-4 max-w-2xl"
      onSubmit={(event) => {
        event.preventDefault();
        submit.mutate(
          {
            review_stamp: configuration.review_stamp ?? "",
            design_confirmation: design,
            transmission_design: transmission,
            deviations_acknowledged: deviations.length > 0 && acknowledged,
            code: contact ? code : null,
          },
          {
            onSuccess: onDone,
            // Neue Abweichungen nach einer Änderung sind erneut zu bestätigen
            onError: () => setAcknowledged(false),
          },
        );
      }}
    >
      {deviations.length > 0 && (
        <div className="flex flex-col gap-2" data-testid="uebergabe-abweichungen">
          <strong className="text-sm">{t("submission.deviations.title")}</strong>
          <p className="text-sm t-mute m-0">{t("submission.deviations.intro")}</p>
          <ul className="m-0 pl-5 text-sm t-alert">
            {deviations.map((check, index) => (
              <li key={`${check.code}-${index}`}>{checkText(check, t, i18n.language, names)}</li>
            ))}
          </ul>
          <label className="flex items-start gap-2">
            <input type="checkbox" checked={acknowledged} onChange={(e) => setAcknowledged(e.target.checked)} />
            <span className="text-sm">{t("submission.deviations.confirm")}</span>
          </label>
        </div>
      )}
      {contact && (
        <>
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
        </>
      )}
      <label className="flex items-start gap-2">
        <input type="checkbox" checked={design} onChange={(e) => setDesign(e.target.checked)} />
        <span className="text-sm">{noticeText("notice.design_confirmation", "submission.designFallback")}</span>
      </label>
      <label className="flex items-start gap-2">
        <input type="checkbox" checked={transmission} onChange={(e) => setTransmission(e.target.checked)} />
        <span className="text-sm">{noticeText("consent.transmission_design", "submission.transmissionFallback")}</span>
      </label>
      {submit.isError && <Aenderungen error={submit.error} />}
      <button
        type="submit"
        className="btn btn-primary self-start"
        disabled={submit.isPending || !design || !transmission || (deviations.length > 0 && !acknowledged)}
      >
        {t(contact ? "submission.submitWithCode" : "submission.submit")}
      </button>
    </form>
  );
}

interface UebergabeProps {
  projectId: string;
  configuration: ConfigurationOut;
  names: Record<string, string>;
}

export function Uebergabe({ projectId, configuration, names }: UebergabeProps) {
  const { t } = useTranslation();
  const mine = useMyInquiry(projectId, true);
  const [stage, setStage] = useState<
    { step: "form" } | { step: "code"; contact: ContactIn } | { step: "done"; result: SubmitOut }
  >({ step: "form" });

  let inhalt;
  if (stage.step === "done") {
    inhalt = (
      <div className="flex flex-col gap-2" data-testid="uebergabe-fertig">
        <strong>{t("submission.done.title")}</strong>
        <p className="m-0">{t("submission.done.text", { number: stage.result.number, sequence: stage.result.sequence })}</p>
        <Link className="link" to="/vorgang">
          {t("submission.done.link")}
        </Link>
      </div>
    );
  } else if (mine.isPending) {
    inhalt = <p className="t-mute m-0">{t("loading")}</p>;
  } else if (mine.data?.exists) {
    inhalt = (
      <>
        <p className="text-sm t-mute m-0">{t("submission.existing", { number: mine.data.number })}</p>
        <UebergabeFormular
          projectId={projectId}
          configuration={configuration}
          names={names}
          contact={null}
          onDone={(result) => setStage({ step: "done", result })}
        />
      </>
    );
  } else if (stage.step === "code") {
    inhalt = (
      <UebergabeFormular
        projectId={projectId}
        configuration={configuration}
        names={names}
        contact={stage.contact}
        onDone={(result) => setStage({ step: "done", result })}
      />
    );
  } else {
    inhalt = <KontaktFormular projectId={projectId} onSent={(contact) => setStage({ step: "code", contact })} />;
  }

  return (
    <section aria-labelledby="uebergabe-titel" className="flex flex-col gap-4 border-t bd pt-6" data-testid="uebergabe">
      <h3 id="uebergabe-titel" className="eyebrow m-0">
        {t("submission.title")}
      </h3>
      <p className="text-sm t-mute m-0 max-w-prose">{t("submission.intro")}</p>
      {inhalt}
    </section>
  );
}
