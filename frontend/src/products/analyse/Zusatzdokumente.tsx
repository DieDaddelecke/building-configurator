/**
 * Zusatzdokumente eines Projekts (AN3, docs/PLAN_AN3_ANALYSE.md 3.7, 3.8): règlement de lotissement und cahier
 * des charges hochladen, das Lot wählen (kostet wie die Zonenwahl), Stand der Auswertung und Vergleich mit den
 * PLU-Regeln. Die Werte wirken nicht in Regeln, Baurahmen und Analyse – ob das Dokument gilt, beurteilt der
 * Architekt (E-AN3-2).
 */

import type { TFunction } from "i18next";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { useAnalysis, type RuleComparisonOut, type SupplementAnalysisOut } from "../../api/analysis";
import type { LimitOut } from "../../api/envelope";
import {
  chosenChapter,
  MAX_SUPPLEMENTS,
  supplementsOf,
  useChooseLot,
  useProjectRegulations,
  useRemoveRegulation,
  useUploadRegulation,
  type LotChoiceIn,
  type ProjectRegulationOut,
  type SupplementDuType,
} from "../../api/regulations";
import type { RuleOut } from "../../api/rules";
import { ruleValue } from "../../rules/format";
import { Auswertung, fehlerText, grund } from "./Bebauungsplan";

const TYPES: SupplementDuType[] = ["lotissement", "cahier_des_charges"];
const PREFIX = "analyse.supplement";

/** `Lot-12` → „Lot 12“, `Ensemble` → „ganzes Dokument“. */
export function lotLabel(zone: string | null | undefined, t: TFunction): string {
  if (!zone) return "";
  return zone.startsWith("Lot-") ? t(`${PREFIX}.lotLabel`, { lot: zone.slice(4) }) : t(`${PREFIX}.whole`);
}

export function Zusatzdokumente({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const regulations = useProjectRegulations(projectId);
  const analysis = useAnalysis(projectId);
  const [neu, setNeu] = useState(false);
  const supplements = supplementsOf(regulations.data);

  return (
    <section aria-labelledby="zusatzdokumente" className="karte p-5 flex flex-col gap-4">
      <h2 id="zusatzdokumente" className="eyebrow m-0">{t(`${PREFIX}.title`)}</h2>
      <p className="t-mute text-sm m-0">{t(`${PREFIX}.intro`)}</p>
      {supplements.map((regulation) => (
        <Zusatzdokument
          key={regulation.document.id}
          projectId={projectId}
          regulation={regulation}
          vergleich={analysis.data?.supplements.find((item) => item.document_id === regulation.document.id)}
        />
      ))}
      {regulations.isSuccess &&
        (neu ? (
          <Hochladen projectId={projectId} onDone={() => setNeu(false)} />
        ) : supplements.length < MAX_SUPPLEMENTS ? (
          <div>
            <button type="button" className="btn btn-ghost" onClick={() => setNeu(true)}>
              {t(`${PREFIX}.add`)}
            </button>
          </div>
        ) : (
          <p className="t-mute text-sm m-0">{t(`${PREFIX}.limit`)}</p>
        ))}
    </section>
  );
}

function Hochladen({ projectId, onDone }: { projectId: string; onDone: () => void }) {
  const { t } = useTranslation();
  const fileId = useId();
  const titleId = useId();
  const typeId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [duType, setDuType] = useState<SupplementDuType>("lotissement");
  const upload = useUploadRegulation(projectId);
  const fehler = fehlerText(t, upload.error, PREFIX);

  return (
    <div className="flex flex-col gap-4 border-t bd pt-4">
      <div className="flex flex-col gap-1">
        <label htmlFor={fileId}>{t(`${PREFIX}.file`)}</label>
        <input
          id={fileId}
          className="field"
          type="file"
          accept=".pdf,application/pdf"
          onChange={(event) => {
            setFile(event.target.files?.[0] ?? null);
            upload.reset();
          }}
        />
      </div>
      <div className="grid gap-4 sm:grid-cols-[1fr_auto]">
        <div className="flex flex-col gap-1">
          <label htmlFor={titleId}>{t("analyse.plu.docTitle")}</label>
          <input
            id={titleId}
            className="field"
            value={title}
            maxLength={300}
            placeholder={t(`${PREFIX}.titleHint`)}
            onChange={(event) => setTitle(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={typeId}>{t("analyse.plu.duType")}</label>
          <select id={typeId} className="field" value={duType} onChange={(event) => setDuType(event.target.value as SupplementDuType)}>
            {TYPES.map((value) => (
              <option key={value} value={value}>
                {t(`${PREFIX}.type.${value}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {fehler && (
        <p className="t-alert m-0" role="alert">
          {fehler}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="btn btn-primary"
          disabled={!file || upload.isPending}
          onClick={() => file && upload.mutate({ file, title, duType }, { onSuccess: onDone })}
        >
          {upload.isPending ? t("loading") : t("analyse.plu.submit")}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onDone}>
          {t("analyse.plu.cancel")}
        </button>
      </div>
    </div>
  );
}

function Zusatzdokument({
  projectId,
  regulation,
  vergleich,
}: {
  projectId: string;
  regulation: ProjectRegulationOut;
  vergleich: SupplementAnalysisOut | undefined;
}) {
  const { t } = useTranslation();
  const document = regulation.document;
  const remove = useRemoveRegulation(projectId);
  const [aendern, setAendern] = useState(false);
  const kapitel = chosenChapter(regulation);
  const loesen = () => {
    if (window.confirm(t(`${PREFIX}.removeConfirm`))) remove.mutate(document.id);
  };

  return (
    <article className="flex flex-col gap-3 border-t bd pt-4" aria-label={document.title}>
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="m-0">
          <span className="font-medium t-ink">{document.title}</span>
          <span className="t-mute">
            {" "}
            · {t(`${PREFIX}.type.${document.du_type}`, { defaultValue: document.du_type })}
            {document.page_count != null && <> · {t("analyse.plu.pages", { count: document.page_count })}</>}
          </span>
        </p>
        {document.file_url && (
          <a className="link text-sm" href={document.file_url} target="_blank" rel="noreferrer">
            {t("analyse.plu.open")}
          </a>
        )}
      </div>
      {document.status === "importing" && (
        <p className="t-mute m-0" role="status">
          {t(`${PREFIX}.reading`)}
        </p>
      )}
      {document.status === "failed" && (
        <p className="t-alert m-0" role="alert">
          {grund(t, document.error) || t("analyse.plu.error.document_failed")}
        </p>
      )}
      {document.status === "active" && regulation.zone_code && kapitel && !aendern && (
        <Auswertung regulation={regulation} kapitel={kapitel} titel={lotLabel(regulation.zone_code, t)} />
      )}
      {document.status === "active" && (!regulation.zone_code || aendern) && (
        <LotWahl
          projectId={projectId}
          regulation={regulation}
          onChosen={() => setAendern(false)}
          onCancel={aendern ? () => setAendern(false) : undefined}
        />
      )}
      {vergleich && vergleich.comparisons.length > 0 && <Vergleich vergleich={vergleich} />}
      <div className="flex flex-wrap gap-3">
        {document.status === "active" && regulation.zone_code && !aendern && (
          <button type="button" className="btn btn-ghost" onClick={() => setAendern(true)}>
            {t(`${PREFIX}.change`)}
          </button>
        )}
        <button type="button" className="btn btn-ghost" onClick={loesen} disabled={remove.isPending}>
          {t("analyse.plu.remove")}
        </button>
      </div>
      {remove.isError && <p className="t-alert m-0">{t("error.generic")}</p>}
    </article>
  );
}

const zahl = (value: string): number | undefined => (/^\d+$/.test(value.trim()) ? Number(value.trim()) : undefined);

function LotWahl({
  projectId,
  regulation,
  onChosen,
  onCancel,
}: {
  projectId: string;
  regulation: ProjectRegulationOut;
  onChosen: () => void;
  onCancel?: () => void;
}) {
  const { t } = useTranslation();
  const lotId = useId();
  const firstId = useId();
  const lastId = useId();
  const current = regulation.zone_code?.startsWith("Lot-") ? regulation.zone_code.slice(4) : "";
  const [lot, setLot] = useState(current);
  const [vonHand, setVonHand] = useState(false);
  const [seiten, setSeiten] = useState({ first: "", last: "" });
  const choose = useChooseLot(projectId, regulation.document.id);
  const fehler = fehlerText(t, choose.error, PREFIX);
  const gueltig = lot.trim() === "" || /^[0-9A-Za-z][0-9A-Za-z_-]{0,15}$/.test(lot.trim());

  const body = (): LotChoiceIn | null => {
    if (!gueltig) return null;
    const result: LotChoiceIn = lot.trim() ? { lot: lot.trim() } : {};
    if (!vonHand) return result;
    const first = zahl(seiten.first);
    const last = zahl(seiten.last);
    return first !== undefined && last !== undefined ? { ...result, first_page: first, last_page: last } : null;
  };
  const koerper = body();

  return (
    <div className="flex flex-col gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor={lotId}>{t(`${PREFIX}.lot`)}</label>
        <input
          id={lotId}
          className="field max-w-40 f-mono"
          value={lot}
          maxLength={16}
          placeholder={t(`${PREFIX}.lotHint`)}
          aria-invalid={!gueltig}
          onChange={(event) => setLot(event.target.value)}
        />
        <p className="t-mute text-xs m-0">{t(`${PREFIX}.lotExplain`)}</p>
      </div>
      <label className="flex items-center gap-2 text-sm">
        <input type="checkbox" checked={vonHand} onChange={(event) => setVonHand(event.target.checked)} />
        {t(`${PREFIX}.manual`)}
      </label>
      {vonHand && (
        <div className="flex flex-wrap gap-4">
          {(
            [
              [firstId, "first", t("analyse.plu.firstPage")],
              [lastId, "last", t("analyse.plu.lastPage")],
            ] as const
          ).map(([id, key, label]) => (
            <div key={key} className="flex flex-col gap-1">
              <label htmlFor={id} className="text-sm">
                {label}
              </label>
              <input
                id={id}
                className="field max-w-28"
                inputMode="numeric"
                value={seiten[key]}
                onChange={(event) => setSeiten({ ...seiten, [key]: event.target.value })}
              />
            </div>
          ))}
        </div>
      )}
      <p className="t-mute text-xs m-0">{t(`${PREFIX}.costHint`)}</p>
      {fehler && (
        <p className="t-alert m-0" role="alert">
          {fehler}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="btn btn-primary"
          disabled={!koerper || choose.isPending}
          onClick={() => koerper && choose.mutate(koerper, { onSuccess: onChosen })}
        >
          {choose.isPending ? t("loading") : t(`${PREFIX}.choose`)}
        </button>
        {onCancel && (
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            {t("analyse.plu.cancel")}
          </button>
        )}
      </div>
    </div>
  );
}

const VERDICT_TONE: Record<RuleComparisonOut["verdict"], string> = {
  stricter: "t-warn",
  only_supplement: "t-warn",
  mixed: "t-warn",
  different: "t-warn",
  looser: "t-mute",
  equal: "t-mute",
  no_own_rule: "t-mute",
  unknown: "t-mute",
};

function Wert({ limit }: { limit: LimitOut | null | undefined }) {
  const { t, i18n } = useTranslation();
  if (!limit) return <span className="t-mute">{t(`${PREFIX}.noRule`)}</span>;
  const citation = limit.citation;
  return (
    <>
      {ruleValue(limit as unknown as RuleOut, t, i18n.language)}
      {citation?.page != null && citation.source_url && (
        <>
          {" · "}
          <a className="link" href={citation.source_url} target="_blank" rel="noreferrer" title={citation.quote ?? undefined}>
            {t("rules.page", { page: citation.page })}
          </a>
        </>
      )}
    </>
  );
}

function Vergleich({ vergleich }: { vergleich: SupplementAnalysisOut }) {
  const { t } = useTranslation();
  return (
    <div className="flex flex-col gap-2">
      <p className="t-mute text-xs m-0">{t(`${PREFIX}.notApplied`)}</p>
      {vergleich.updating && <p className="t-warn text-xs m-0">{t(`${PREFIX}.updating`)}</p>}
      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <caption className="sr-only">{t(`${PREFIX}.comparison`, { title: vergleich.title })}</caption>
          <thead>
            <tr className="text-left border-b bd-strong">
              <th scope="col" className="py-2 pr-3 font-medium">{t("rules.column.kind")}</th>
              <th scope="col" className="py-2 pr-3 font-medium">{t(`${PREFIX}.plu`)}</th>
              <th scope="col" className="py-2 pr-3 font-medium">{t(`${PREFIX}.document`)}</th>
              <th scope="col" className="py-2 font-medium">{t(`${PREFIX}.verdictColumn`)}</th>
            </tr>
          </thead>
          <tbody>
            {vergleich.comparisons.map((comparison) => (
              <tr key={`${comparison.kind}-${comparison.building_kind}`} className="border-b bd align-top">
                <th scope="row" className="py-2 pr-3 font-normal text-left">
                  {t(`rules.kind.${comparison.kind}`)}
                  {comparison.building_kind !== "main" && comparison.building_kind !== "any" && (
                    <span className="t-mute"> · {t(`rules.building.${comparison.building_kind}`)}</span>
                  )}
                </th>
                <td className="py-2 pr-3">
                  <Wert limit={comparison.plu} />
                </td>
                <td className="py-2 pr-3 t-ink">
                  <Wert limit={comparison.supplement} />
                </td>
                <td className={`py-2 ${VERDICT_TONE[comparison.verdict]}`}>{t(`${PREFIX}.verdict.${comparison.verdict}`)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {vergleich.hints.length > 0 && (
        <ul className="m-0 pl-5 text-sm t-mute flex flex-col gap-1">
          {vergleich.hints.map((hint, index) => (
            <li key={index}>{String(hint.params.summary ?? "")}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
