import { useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError, type Problem } from "../api/client";
import { useUploadParcel, type UploadResultOut } from "../api/site";
import { formatNumber } from "../site/geo";
import { auswahlFlaeche, bezeichnung, KonturWahl } from "./KonturWahl";
import { ScanNachzeichnen } from "./ScanNachzeichnen";

interface ParzelleHochladenProps {
  projectId: string;
  onFormed: () => void;
  onCancel: () => void;
}

const istPdf = (file: File | null) => Boolean(file?.name.toLowerCase().endsWith(".pdf"));
/** Bilder gehen direkt zum Nachzeichnen; der Upload der Parzelle selbst liest nur DXF, GeoJSON und PDF (AN7). */
const istBild = (file: File | null) => /.(jpe?g|png)$/i.test(file?.name ?? "");

/**
 * Parzelle aus DXF, GeoJSON oder vektoriellem PDF (AN1, PLAN_AN1 3.2, 8 und 9). Mehrere Konturen: erst im Plan
 * wählen, dann übernehmen; zerschneidet eine fremde Linie die Parzelle, werden ihre Teile zusammen gewählt
 * (UP17). Bei PDF braucht es einen Maßstab; steht er im Plan, wird er übernommen, sonst hier angegeben (UP14).
 * Ein gescanntes PDF oder ein Bild wird als Vorlage nachgezeichnet (AN7, docs/PLAN_AN7_SCAN.md 3.5).
 */
export function ParzelleHochladen({ projectId, onFormed, onCancel }: ParzelleHochladenProps) {
  const { t, i18n } = useTranslation();
  const fileId = useId();
  const labelId = useId();
  const scaleId = useId();
  const [file, setFile] = useState<File | null>(null);
  const [label, setLabel] = useState("");
  const [massstab, setMassstab] = useState("");
  const [auswahl, setAuswahl] = useState<UploadResultOut | null>(null);
  const [gewaehlt, setGewaehlt] = useState<number[]>([]);
  const [nachzeichnen, setNachzeichnen] = useState(false);
  const upload = useUploadParcel(projectId);

  const scale = istPdf(file) && /^\d+$/.test(massstab.trim()) ? Number(massstab.trim()) : undefined;

  const senden = (index?: readonly number[], festerMassstab?: number) => {
    if (!file || !label.trim()) return;
    upload.mutate(
      // Nur ein von Hand angegebener Maßstab geht mit; einer aus dem Plan wird beim zweiten Lesen wieder
      // gefunden und bleibt so in der Herkunft als „aus dem Plan“ vermerkt
      { file, addressLabel: label.trim(), index, scale: festerMassstab ?? scale },
      {
        onSuccess: (result) => {
          if (result.site) onFormed();
          else {
            setAuswahl(result);
            setGewaehlt([]);
          }
        },
      },
    );
  };

  const neueDatei = (next: File | null) => {
    setFile(next);
    setAuswahl(null);
    setGewaehlt([]);
    upload.reset();
  };

  const fehler = upload.error instanceof ApiError ? (upload.error.problem as Problem & { scales?: number[] }) : null;
  const umschalten = (index: number) =>
    setGewaehlt((liste) => (liste.includes(index) ? liste.filter((i) => i !== index) : [...liste, index]));
  const einzeln = gewaehlt.length === 1 ? (auswahl?.candidates.find((c) => c.index === gewaehlt[0]) ?? null) : null;

  if (nachzeichnen && file) {
    return (
      <ScanNachzeichnen
        projectId={projectId}
        file={file}
        addressLabel={label.trim()}
        onFormed={onFormed}
        onCancel={() => setNachzeichnen(false)}
      />
    );
  }

  return (
    <section className="karte p-5 flex flex-col gap-4" aria-labelledby="upload-titel">
      <h3 id="upload-titel" className="f-display text-xl">{t("analyse.upload.title")}</h3>
      <p className="t-mute text-sm m-0">{t("analyse.upload.formats")}</p>

      <div className="flex flex-col gap-1">
        <label htmlFor={labelId}>{t("analyse.upload.label")}</label>
        <input
          id={labelId}
          className="field"
          value={label}
          maxLength={200}
          onChange={(event) => setLabel(event.target.value)}
          placeholder={t("analyse.upload.labelHint")}
        />
      </div>

      <div className="flex flex-col gap-1">
        <label htmlFor={fileId}>{t("analyse.upload.file")}</label>
        <input
          id={fileId}
          className="field"
          type="file"
          accept=".dxf,.geojson,.json,.pdf,.jpg,.jpeg,.png"
          onChange={(event) => neueDatei(event.target.files?.[0] ?? null)}
        />
      </div>

      {istPdf(file) && (
        <div className="flex flex-col gap-1">
          <label htmlFor={scaleId}>{t("analyse.upload.scale")}</label>
          <div className="flex items-center gap-2">
            <span className="f-mono">1&nbsp;:</span>
            <input
              id={scaleId}
              className="field max-w-40"
              inputMode="numeric"
              value={massstab}
              onChange={(event) => setMassstab(event.target.value)}
              placeholder={t("analyse.upload.scaleAuto")}
            />
          </div>
          <p className="t-mute text-xs m-0">{t("analyse.upload.scaleHint")}</p>
        </div>
      )}

      {fehler && (
        <div className="t-alert" role="alert">
          <p className="m-0">{t([`analyse.upload.error.${fehler.code}`, "error.generic"])}</p>
          {fehler.code === "upload_scale_ambiguous" && fehler.scales && (
            <div className="flex flex-wrap gap-2 mt-2">
              {fehler.scales.map((wert) => (
                <button
                  key={wert}
                  type="button"
                  className="chip f-mono"
                  onClick={() => {
                    setMassstab(String(wert));
                    senden(undefined, wert);
                  }}
                >
                  1:{wert}
                </button>
              ))}
            </div>
          )}
          {fehler.detail && fehler.code !== "upload_scale_ambiguous" && (
            <span className="block text-sm t-mute">{fehler.detail}</span>
          )}
          {fehler.code === "upload_pdf_no_vector" && (
            <button type="button" className="btn btn-primary mt-2" onClick={() => setNachzeichnen(true)}>
              {t("analyse.trace.start")}
            </button>
          )}
        </div>
      )}

      {auswahl && auswahl.candidates.length > 0 && (
        <div className="flex flex-col gap-3">
          <p className="m-0">{t("analyse.upload.choose", { count: auswahl.candidates.length })}</p>
          {auswahl.scale !== null && (
            <p className="t-mute text-sm m-0">
              {t(auswahl.scale_source === "input" ? "analyse.upload.scaleUsedInput" : "analyse.upload.scaleUsedFile", {
                scale: auswahl.scale,
              })}
            </p>
          )}
          <KonturWahl candidates={auswahl.candidates} selected={gewaehlt} onToggle={umschalten} />
          {gewaehlt.length > 0 && (
            <div className="flex flex-wrap items-center gap-3">
              {einzeln ? (
                <span>
                  <span className="font-medium">{bezeichnung(einzeln)}</span>
                  <span className="t-mute f-mono num"> · {formatNumber(einzeln.area_m2, i18n.language)} m²</span>
                </span>
              ) : (
                <span>
                  {t("analyse.upload.selectedSum", {
                    count: gewaehlt.length,
                    area: formatNumber(auswahlFlaeche(auswahl.candidates, gewaehlt), i18n.language, 0),
                  })}
                </span>
              )}
              <button type="button" className="btn btn-primary" disabled={upload.isPending} onClick={() => senden(gewaehlt)}>
                {t("analyse.upload.take")}
              </button>
            </div>
          )}
        </div>
      )}

      <div className="flex gap-3">
        {!auswahl && istBild(file) && (
          <button type="button" className="btn btn-primary" disabled={!label.trim()} onClick={() => setNachzeichnen(true)}>
            {t("analyse.trace.start")}
          </button>
        )}
        {!auswahl && !istBild(file) && (
          <button
            type="button"
            className="btn btn-primary"
            disabled={!file || !label.trim() || upload.isPending}
            onClick={() => senden()}
          >
            {upload.isPending ? t("loading") : t("analyse.upload.submit")}
          </button>
        )}
        <button type="button" className="btn btn-ghost" onClick={onCancel}>
          {t("analyse.upload.cancel")}
        </button>
      </div>
    </section>
  );
}
