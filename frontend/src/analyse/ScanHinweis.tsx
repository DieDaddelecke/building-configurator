/**
 * Gescannte Reglements und Zusatzdokumente (AN7, docs/PLAN_AN7_SCAN.md 3.2, 3.7): Hinweis vor der Texterkennung mit
 * Seitenzahl, Dauer und Grenzen; Fortschritt; Zusammenfassung danach. Bei einzelnen Seiten ohne Text (eingefügte
 * Änderungsseiten, Pläne) die Schaltfläche an der Zeile „n Seiten ohne Text“. Die Erkennung kostet nichts, dauert aber.
 */

import type { TFunction } from "i18next";
import { useTranslation } from "react-i18next";

import { useRequestOcr, type OcrOut, type RegulationDocumentOut } from "../api/regulations";
import { fehlerText, grund } from "./fehler";

const PREFIX = "analyse.scan";
/** Längere Seitenlisten kürzen: Die Zusammenfassung soll eine Zeile bleiben. */
const MAX_LISTED_PAGES = 8;

export function seitenListe(pages: number[]): string {
  const shown = pages.slice(0, MAX_LISTED_PAGES).join(", ");
  return pages.length > MAX_LISTED_PAGES ? `${shown} …` : shown;
}

/** Dauer in ganzen Minuten, mindestens eine. */
export function dauer(seconds: number, t: TFunction): string {
  return t(`${PREFIX}.duration`, { count: Math.max(1, Math.round(seconds / 60)) });
}

/** „74 Seiten erkannt, 3 davon unsicher (S. 12, 40, 41); 2 auch danach ohne Text.“ */
export function zusammenfassung(ocr: OcrOut, t: TFunction): string {
  const parts = [t(`${PREFIX}.done`, { count: ocr.pages_done })];
  if (ocr.uncertain_pages.length > 0) {
    parts.push(t(`${PREFIX}.uncertain`, { count: ocr.uncertain_pages.length, pages: seitenListe(ocr.uncertain_pages) }));
  }
  const text = parts.join(", ");
  if (ocr.still_empty_pages.length === 0) return text;
  // Trennzeichen in der Übersetzung: Französisch setzt ein Leerzeichen vor das Semikolon
  const empty = t(`${PREFIX}.stillEmpty`, { count: ocr.still_empty_pages.length, pages: seitenListe(ocr.still_empty_pages) });
  return t(`${PREFIX}.withEmpty`, { summary: text, empty });
}

/** Abbruch des Jobs: erkannte Seiten bleiben, ein neuer Start setzt fort. Sonst Grund wie beim Lesen (`ocr_unavailable`). */
function ocrFehler(ocr: OcrOut, t: TFunction): string {
  if (ocr.error?.startsWith("interrupted")) return t(`${PREFIX}.interrupted`);
  return grund(t, ocr.error) || t(`${PREFIX}.failed`);
}

export function ScanHinweis({ projectId, document }: { projectId: string; document: RegulationDocumentOut }) {
  const { t } = useTranslation();
  const request = useRequestOcr(projectId, document.id);
  const ocr = document.ocr;
  const fehler = fehlerText(t, request.error);
  const starten = (label: string, primary: boolean) => (
    <div>
      <button
        type="button"
        className={`btn ${primary ? "btn-primary" : "btn-ghost"}`}
        disabled={request.isPending}
        onClick={() => request.mutate()}
      >
        {request.isPending ? t("loading") : label}
      </button>
    </div>
  );
  const fehlerZeile = fehler && (
    <p className="t-alert m-0" role="alert">
      {fehler}
    </p>
  );

  if (ocr?.state === "running") {
    return (
      <div className="flex flex-col gap-1" role="status">
        <p className="m-0 t-warn">
          {t(`${PREFIX}.progress`, { done: ocr.pages_done, total: ocr.pages_total })}
          <span className="t-mute"> · {t(`${PREFIX}.remaining`, { duration: dauer(ocr.estimated_seconds, t) })}</span>
        </p>
        <progress className="w-full" max={ocr.pages_total} value={ocr.pages_done} aria-label={t(`${PREFIX}.progressLabel`)} />
        <p className="t-mute text-xs m-0">{t(`${PREFIX}.others`)}</p>
      </div>
    );
  }

  if (document.status === "scan" && ocr) {
    return (
      <div className="bg-warn px-4 py-3 flex flex-col gap-2" role="note">
        <p className="m-0 t-ink">
          {t(`${PREFIX}.notice`, {
            empty: ocr.pages_total,
            pages: document.page_count ?? ocr.pages_total,
            duration: dauer(ocr.estimated_seconds, t),
          })}
        </p>
        <p className="m-0 text-sm t-mute">{t(`${PREFIX}.limits`)}</p>
        {ocr.state === "failed" && <p className="m-0 text-sm t-alert">{ocrFehler(ocr, t)}</p>}
        {fehlerZeile}
        {starten(t(ocr.state === "failed" ? `${PREFIX}.retry` : `${PREFIX}.start`), true)}
      </div>
    );
  }

  if (document.status !== "active") return null;
  if (ocr?.state === "done" && ocr.pages_done > 0) {
    return <p className="t-mute text-sm m-0">{zusammenfassung(ocr, t)}</p>;
  }
  if (document.empty_pages.length === 0) return null;
  return (
    <div className="flex flex-col gap-2">
      <p className="t-warn text-sm m-0">{t("analyse.plu.emptyPages", { count: document.empty_pages.length })}</p>
      {ocr?.state === "failed" && <p className="m-0 text-sm t-alert">{ocrFehler(ocr, t)}</p>}
      {fehlerZeile}
      {ocr &&
        starten(
          t(`${PREFIX}.startPages`, { count: ocr.pages_total - ocr.pages_done, duration: dauer(ocr.estimated_seconds, t) }),
          false,
        )}
    </div>
  );
}
