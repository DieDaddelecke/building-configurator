import type { TFunction } from "i18next";
import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../../api/client";
import {
  chosenChapter,
  useChooseZone,
  useProjectRegulations,
  useRefreshWhenStateChanges,
  useRemoveRegulation,
  useUploadRegulation,
  type DocumentChapterOut,
  type ProjectRegulationOut,
  type UploadDuType,
  type ZoneChoiceIn,
} from "../../api/regulations";
import { formatNumber } from "../../site/geo";

const DU_TYPES: UploadDuType[] = ["PLU", "PLUi", "PSMV"];

function fehlerText(t: TFunction, error: unknown): string | null {
  if (!error) return null;
  const code = error instanceof ApiError ? error.problem.code : "";
  return t([`analyse.plu.error.${code}`, "error.generic"]);
}

/** Grund eines gescheiterten Lesens oder einer gescheiterten Auswertung in Worten des Büros. */
function grund(t: TFunction, reason: string | null): string {
  if (!reason) return "";
  if (reason.startsWith("interrupted")) return t("analyse.plu.error.interrupted");
  return t([`analyse.plu.reason.${reason}`, `analyse.plu.error.${reason}`, "analyse.plu.reason.other"], { reason });
}

/** Bebauungsplan eines Projekts (AN2, docs/PLAN_AN2_PLU.md 3.8): PDF hochladen, Kapitel und Zone wählen, Stand der Auswertung. */
export function Bebauungsplan({ projectId }: { projectId: string }) {
  const { t } = useTranslation();
  const regulations = useProjectRegulations(projectId);
  const [neu, setNeu] = useState(false);
  const regulation = regulations.data?.[0];
  useRefreshWhenStateChanges(projectId, regulation);

  return (
    <section aria-labelledby="bebauungsplan" className="karte p-5 flex flex-col gap-4">
      <h2 id="bebauungsplan" className="eyebrow m-0">{t("analyse.plu.title")}</h2>
      {regulations.isPending && <p className="t-mute m-0">{t("loading")}</p>}
      {regulations.isError && <p className="t-alert m-0">{t("error.generic")}</p>}
      {regulations.isSuccess && (!regulation || neu) && (
        <PluHochladen projectId={projectId} onDone={() => setNeu(false)} onCancel={regulation ? () => setNeu(false) : undefined} />
      )}
      {regulation && !neu && <Dokument projectId={projectId} regulation={regulation} onReplace={() => setNeu(true)} />}
    </section>
  );
}

function PluHochladen({ projectId, onDone, onCancel }: { projectId: string; onDone: () => void; onCancel?: () => void }) {
  const { t } = useTranslation();
  const fileId = useId();
  const titleId = useId();
  const typeId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [duType, setDuType] = useState<UploadDuType>("PLU");
  const upload = useUploadRegulation(projectId);
  const fehler = fehlerText(t, upload.error);

  return (
    <div className="flex flex-col gap-4">
      <p className="t-mute text-sm m-0">{t("analyse.plu.intro")}</p>
      <div className="flex flex-col gap-1">
        <label htmlFor={fileId}>{t("analyse.plu.file")}</label>
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
            placeholder={t("analyse.plu.docTitleHint")}
            onChange={(event) => setTitle(event.target.value)}
          />
        </div>
        <div className="flex flex-col gap-1">
          <label htmlFor={typeId}>{t("analyse.plu.duType")}</label>
          <select id={typeId} className="field" value={duType} onChange={(event) => setDuType(event.target.value as UploadDuType)}>
            {DU_TYPES.map((value) => (
              <option key={value} value={value}>
                {value}
              </option>
            ))}
          </select>
        </div>
      </div>
      <p className="t-mute text-xs m-0">{t("analyse.plu.formats")}</p>
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
        {onCancel && (
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            {t("analyse.plu.cancel")}
          </button>
        )}
      </div>
    </div>
  );
}

function Dokument({
  projectId,
  regulation,
  onReplace,
}: {
  projectId: string;
  regulation: ProjectRegulationOut;
  onReplace: () => void;
}) {
  const { t } = useTranslation();
  const document = regulation.document;
  const remove = useRemoveRegulation(projectId);
  const [aendern, setAendern] = useState(false);
  const kapitel = chosenChapter(regulation);

  const loesen = () => {
    if (window.confirm(t("analyse.plu.removeConfirm"))) remove.mutate(document.id);
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="m-0">
          <span className="font-medium t-ink">{document.title}</span>
          <span className="t-mute">
            {" "}
            · {document.du_type}
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
          {t("analyse.plu.reading")}
        </p>
      )}
      {document.status === "failed" && (
        <p className="t-alert m-0" role="alert">
          {grund(t, document.error) || t("analyse.plu.error.document_failed")}
        </p>
      )}
      {document.status === "active" && document.empty_pages.length > 0 && (
        <p className="t-warn text-sm m-0">{t("analyse.plu.emptyPages", { count: document.empty_pages.length })}</p>
      )}

      {document.status === "active" && regulation.zone_code && kapitel && !aendern && (
        <Auswertung regulation={regulation} kapitel={kapitel} />
      )}
      {document.status === "active" && (!regulation.zone_code || aendern) && (
        <ZoneWahl
          projectId={projectId}
          regulation={regulation}
          onChosen={() => setAendern(false)}
          onCancel={aendern ? () => setAendern(false) : undefined}
        />
      )}

      <div className="flex flex-wrap gap-3">
        {document.status === "active" && regulation.zone_code && !aendern && (
          <button type="button" className="btn btn-ghost" onClick={() => setAendern(true)}>
            {t("analyse.plu.change")}
          </button>
        )}
        <button type="button" className="btn btn-ghost" onClick={onReplace}>
          {t("analyse.plu.replace")}
        </button>
        <button type="button" className="btn btn-ghost" onClick={loesen} disabled={remove.isPending}>
          {t("analyse.plu.remove")}
        </button>
      </div>
      {remove.isError && <p className="t-alert m-0">{t("error.generic")}</p>}
    </div>
  );
}

function Auswertung({ regulation, kapitel }: { regulation: ProjectRegulationOut; kapitel: DocumentChapterOut }) {
  const { t, i18n } = useTranslation();
  const laeuft = kapitel.status === "pending" || kapitel.status === "extracting";
  return (
    <div className="flex flex-col gap-1" role="status">
      <p className="m-0">
        <span className="font-medium t-ink">
          {t("analyse.plu.zone", { zone: regulation.zone_code, chapter: kapitel.code })}
        </span>
        <span className="t-mute">
          {" "}
          · {t("analyse.plu.chapterPages", { first: kapitel.first_page, last: kapitel.last_page })}
        </span>
      </p>
      <p className={`m-0 text-sm ${kapitel.status === "failed" ? "t-alert" : laeuft ? "t-warn" : "t-mute"}`}>
        {t(`analyse.plu.status.${kapitel.status}`)}
        {kapitel.runs > 0 && (
          <span className="t-mute">
            {" "}
            · {t("analyse.plu.runs", { count: kapitel.runs, cost: formatNumber(kapitel.cost_usd, i18n.language, 2) })}
          </span>
        )}
      </p>
      {kapitel.status === "failed" && <p className="m-0 text-sm t-mute">{grund(t, kapitel.error)}</p>}
    </div>
  );
}

const zahl = (value: string): number | undefined => (/^\d+$/.test(value.trim()) ? Number(value.trim()) : undefined);

function ZoneWahl({
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
  const chapters = regulation.document.chapters;
  const chapterId = useId();
  const zoneId = useId();
  const firstId = useId();
  const lastId = useId();
  const generalFirstId = useId();
  const generalLastId = useId();
  const [code, setCode] = useState(regulation.chapter_code ?? chapters[0]?.code ?? "");
  const [zone, setZone] = useState(regulation.zone_code ?? regulation.chapter_code ?? chapters[0]?.code ?? "");
  const [vonHand, setVonHand] = useState(chapters.length === 0);
  const [seiten, setSeiten] = useState({ first: "", last: "", generalFirst: "", generalLast: "" });
  const choose = useChooseZone(projectId, regulation.document.id);
  const fehler = fehlerText(t, choose.error);
  const gewaehlt = chapters.find((chapter) => chapter.code === code);
  const vorschlaege = gewaehlt ? [gewaehlt.code, ...gewaehlt.suggested_sectors] : [];

  const koerper = (): ZoneChoiceIn | null => {
    const zoneCode = zone.trim();
    if (!zoneCode) return null;
    if (!vonHand) return gewaehlt ? { zone_code: zoneCode, chapter_code: gewaehlt.code } : null;
    const first = zahl(seiten.first);
    const last = zahl(seiten.last);
    if (first === undefined || last === undefined) return null;
    const body: ZoneChoiceIn = { zone_code: zoneCode, first_page: first, last_page: last };
    const generalFirst = zahl(seiten.generalFirst);
    const generalLast = zahl(seiten.generalLast);
    if (generalFirst !== undefined && generalLast !== undefined) {
      body.general_first_page = generalFirst;
      body.general_last_page = generalLast;
    }
    return body;
  };
  const body = koerper();

  const seitenFeld = (id: string, label: string, key: keyof typeof seiten) => (
    <div className="flex flex-col gap-1">
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
  );

  return (
    <div className="flex flex-col gap-4">
      {chapters.length === 0 ? (
        <p className="t-warn text-sm m-0">{t("analyse.plu.noChapters")}</p>
      ) : (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" checked={vonHand} onChange={(event) => setVonHand(event.target.checked)} />
          {t("analyse.plu.manual")}
        </label>
      )}

      {!vonHand && (
        <div className="flex flex-col gap-1">
          <label htmlFor={chapterId}>{t("analyse.plu.chapters")}</label>
          <select
            id={chapterId}
            className="field"
            value={code}
            onChange={(event) => {
              setCode(event.target.value);
              setZone(event.target.value);
            }}
          >
            {chapters.map((chapter) => (
              <option key={chapter.code} value={chapter.code}>
                {`${chapter.code} – ${chapter.title} (${t("analyse.plu.chapterPages", {
                  first: chapter.first_page,
                  last: chapter.last_page,
                })})`}
              </option>
            ))}
          </select>
        </div>
      )}

      {vonHand && (
        <div className="flex flex-col gap-2">
          <div className="flex flex-wrap gap-4">
            {seitenFeld(firstId, t("analyse.plu.firstPage"), "first")}
            {seitenFeld(lastId, t("analyse.plu.lastPage"), "last")}
          </div>
          <div className="flex flex-wrap gap-4">
            {seitenFeld(generalFirstId, t("analyse.plu.generalFirst"), "generalFirst")}
            {seitenFeld(generalLastId, t("analyse.plu.generalLast"), "generalLast")}
          </div>
          <p className="t-mute text-xs m-0">{t("analyse.plu.generalHint")}</p>
        </div>
      )}

      <div className="flex flex-col gap-1">
        <label htmlFor={zoneId}>{t("analyse.plu.zoneCode")}</label>
        <input
          id={zoneId}
          className="field max-w-40 f-mono"
          value={zone}
          maxLength={20}
          placeholder={t("analyse.plu.zoneHint")}
          onChange={(event) => setZone(event.target.value)}
        />
        {!vonHand && vorschlaege.length > 1 && (
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <span className="t-mute">{t("analyse.plu.suggestions")}</span>
            {vorschlaege.map((sector) => (
              <button
                key={sector}
                type="button"
                className="chip f-mono"
                aria-pressed={zone === sector}
                onClick={() => setZone(sector)}
              >
                {sector}
              </button>
            ))}
          </div>
        )}
      </div>

      <p className="t-mute text-xs m-0">{t("analyse.plu.costHint")}</p>
      {fehler && (
        <p className="t-alert m-0" role="alert">
          {fehler}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="btn btn-primary"
          disabled={!body || choose.isPending}
          onClick={() => body && choose.mutate(body, { onSuccess: onChosen })}
        >
          {choose.isPending ? t("loading") : t("analyse.plu.choose")}
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
