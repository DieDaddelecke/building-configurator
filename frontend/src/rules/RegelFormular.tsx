/**
 * Regelformular (AN4, docs/PLAN_AN4_KORREKTUR.md 3.1, 3.2) statt JSON (RW15): Felder aus der Beschreibung der Regelarten
 * des Servers, Status, Fundstelle (Dokument, Seite, Zitat) und Pflichtbegründung. Gemeinsam für das Analyse-Produkt und
 * das Büro des Konfigurators; `RegelFelder` allein für die Zonenversion im Büro.
 */

import type { TFunction } from "i18next";
import { useId, useMemo, useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";
import type { ParamFieldOut, ProjectOverrideIn, RuleKindFormOut } from "../api/rules";
import { entwurfAus, grenzen, optionKey, parameterAus, parseZahl, zahlText, type Entwurf, type FeldFehler } from "./felder";

export type Baukoerper = ProjectOverrideIn["building_kind"];
export type KorrekturStatus = ProjectOverrideIn["status"];

export interface Dokument {
  id: string;
  title: string;
  pageCount?: number | null;
}

/** Ausgangswerte: eine gelesene Regel, eine Korrektur oder ein Vorschlag aus einem Zusatzdokument. */
export interface Vorlage {
  kind: string;
  building_kind: Baukoerper;
  status: KorrekturStatus;
  params: Record<string, unknown>;
  source?: { document_id: string; page: number; quote?: string | null } | null;
  note?: string;
}

const UNIT_LABEL: Record<string, string> = {
  m: "m",
  m2: "m²",
  deg: "°",
  share: "%",
  factor: "× H",
  per_area: "m²",
  count: "",
};

function feldLabel(t: TFunction, field: ParamFieldOut): string {
  return t(`rules.param.${field.name}`, { defaultValue: field.name });
}

/** Text zu einem Fehler des Servers: Parameter ungültig (mit Grund) oder ein benannter Fehler. */
export function korrekturFehler(t: TFunction, error: unknown): string | null {
  if (!error) return null;
  if (!(error instanceof ApiError)) return t("error.generic");
  const { code, detail } = error.problem;
  if (code === "rule_params_invalid" && detail) {
    return detail
      .split("; ")
      .map((part) => {
        const [name] = part.split("=");
        return part.includes("=")
          ? t("rules.paramError.implausible", { name: t(`rules.param.${name}`, { defaultValue: name }) })
          : t(`rules.paramError.${part.split(":")[0]}`, { defaultValue: part });
      })
      .join(" · ");
  }
  return t([`rules.form.error.${code}`, "error.generic"]);
}

interface RegelFelderProps {
  form: RuleKindFormOut;
  draft: Entwurf;
  errors?: FeldFehler;
  onChange: (draft: Entwurf) => void;
}

/** Eingabefelder einer Regelart; Werte in der Einheit der Eingabe (Prozent, Kehrwert). */
export function RegelFelder({ form, draft, errors = {}, onChange }: RegelFelderProps) {
  const { t, i18n } = useTranslation();
  const idPrefix = useId();
  const set = (name: string, value: Entwurf[string]) => onChange({ ...draft, [name]: value });
  return (
    <div className="grid gap-3 sm:grid-cols-2 [&>*]:min-w-0">
      {form.params.map((field) => {
        const id = `${idPrefix}-${field.name}`;
        const error = errors[field.name];
        const label = feldLabel(t, field);
        if (field.type === "flag") {
          return (
            <label key={field.name} className="flex items-center gap-2 text-sm sm:col-span-2">
              <input type="checkbox" checked={Boolean(draft[field.name])} onChange={(e) => set(field.name, e.target.checked)} />
              {label}
            </label>
          );
        }
        if (field.type === "items") {
          const selected = new Set(Array.isArray(draft[field.name]) ? (draft[field.name] as string[]) : []);
          return (
            <fieldset key={field.name} className="flex flex-col gap-1 sm:col-span-2 border-0 p-0 m-0">
              <legend className="text-sm mb-1">{label}</legend>
              <div className="flex flex-wrap gap-x-4 gap-y-1">
                {field.options.map((option) => (
                  <label key={option} className="flex items-center gap-1 text-sm">
                    <input
                      type="checkbox"
                      checked={selected.has(option)}
                      onChange={(e) => {
                        const next = new Set(selected);
                        if (e.target.checked) next.add(option);
                        else next.delete(option);
                        set(
                          field.name,
                          field.options.filter((o) => next.has(o)),
                        );
                      }}
                    />
                    {t(optionKey(field.name, option), { defaultValue: option })}
                  </label>
                ))}
              </div>
            </fieldset>
          );
        }
        if (field.type === "choice") {
          return (
            <div key={field.name} className="flex flex-col gap-1">
              <label htmlFor={id} className="text-sm">
                {label}
              </label>
              <select id={id} className="field" value={String(draft[field.name] ?? "")} onChange={(e) => set(field.name, e.target.value)}>
                {field.default == null && <option value="">{t("rules.form.none")}</option>}
                {field.options.map((option) => (
                  <option key={option} value={option}>
                    {t(optionKey(field.name, option), { defaultValue: option })}
                  </option>
                ))}
              </select>
            </div>
          );
        }
        const unit = field.unit ? UNIT_LABEL[field.unit] : "";
        const [low, high] = field.type === "number" ? grenzen(field) : [null, null];
        return (
          <div key={field.name} className="flex flex-col gap-1">
            <label htmlFor={id} className="text-sm">
              {label}
              {field.required && <span aria-hidden="true"> *</span>}
            </label>
            <div className="flex items-center gap-2">
              {field.unit === "per_area" && <span className="text-sm t-mute">{t("rules.form.onePer")}</span>}
              <input
                id={id}
                className={`field ${field.type === "number" ? "max-w-32 num" : ""}`}
                inputMode={field.type === "number" ? "decimal" : undefined}
                value={String(draft[field.name] ?? "")}
                aria-invalid={Boolean(error)}
                required={field.required}
                placeholder={field.name === "storeys" ? "R+1+C" : undefined}
                onChange={(e) => set(field.name, e.target.value)}
              />
              {unit && <span className="text-sm t-mute">{unit}</span>}
            </div>
            {error && (
              <p className="t-alert text-xs m-0">
                {t(`rules.form.fieldError.${error}`, {
                  low: low != null ? zahlText(low, i18n.language) : "–",
                  high: high != null ? zahlText(high, i18n.language) : "–",
                })}
              </p>
            )}
          </div>
        );
      })}
    </div>
  );
}

interface RegelFormularProps {
  kinds: RuleKindFormOut[];
  zoneCode: string;
  vorlage: Vorlage;
  /** Wählbare Arten (Regel ergänzen); ohne Angabe ist die Art fest. */
  kindChoices?: string[];
  /** Baukörper wählbar (neue Regel einer baukörperbezogenen Art). */
  buildingChoice?: boolean;
  documents: Dokument[];
  pending: boolean;
  error: unknown;
  hint?: ReactNode;
  onSubmit: (body: ProjectOverrideIn) => void;
  onCancel?: () => void;
}

export function RegelFormular({
  kinds,
  zoneCode,
  vorlage,
  kindChoices,
  buildingChoice = false,
  documents,
  pending,
  error,
  hint,
  onSubmit,
  onCancel,
}: RegelFormularProps) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const ids = useId();
  const byKind = useMemo(() => new Map(kinds.map((k) => [k.kind as string, k])), [kinds]);
  const [kind, setKind] = useState(vorlage.kind);
  const form = byKind.get(kind);
  const [building, setBuilding] = useState<Baukoerper>(vorlage.building_kind);
  const [status, setStatus] = useState<KorrekturStatus>(vorlage.status);
  const [draft, setDraft] = useState<Entwurf>(() => entwurfAus(form?.params ?? [], vorlage.params, lng));
  const [documentId, setDocumentId] = useState(vorlage.source?.document_id ?? "");
  const [page, setPage] = useState(vorlage.source?.page != null ? String(vorlage.source.page) : "");
  const [quote, setQuote] = useState(vorlage.source?.quote ?? "");
  const [note, setNote] = useState(vorlage.note ?? "");
  const [errors, setErrors] = useState<FeldFehler>({});
  const [pageError, setPageError] = useState(false);
  const serverError = korrekturFehler(t, error);

  if (!form) return null;

  const chooseKind = (next: string) => {
    const nextForm = byKind.get(next);
    setKind(next);
    setBuilding(nextForm?.building_specific ? "main" : "any");
    setDraft(entwurfAus(nextForm?.params ?? [], {}, lng));
    setErrors({});
  };

  const submit = () => {
    const { params, errors: fieldErrors } = status === "effective" ? parameterAus(form.params, draft) : { params: {}, errors: {} };
    setErrors(fieldErrors);
    const pageNumber = parseZahl(page);
    const pageInvalid = documentId !== "" && (pageNumber === null || Number.isNaN(pageNumber) || pageNumber < 1 || !Number.isInteger(pageNumber));
    setPageError(pageInvalid);
    if (Object.keys(fieldErrors).length > 0 || pageInvalid) return;
    onSubmit({
      zone_code: zoneCode,
      kind: kind as ProjectOverrideIn["kind"],
      building_kind: building,
      status,
      params,
      note: note.trim(),
      source: documentId && pageNumber ? { document_id: documentId, page: pageNumber, quote: quote.trim() || null } : null,
    });
  };

  return (
    <form
      noValidate
      className="karte p-4 flex flex-col gap-4 text-sm"
      aria-label={t("rules.form.title", { kind: t(`rules.kind.${kind}`) })}
      onSubmit={(event) => {
        event.preventDefault();
        submit();
      }}
    >
      {kindChoices ? (
        <div className="flex flex-col gap-1">
          <label htmlFor={`${ids}-kind`}>{t("rules.column.kind")}</label>
          <select id={`${ids}-kind`} className="field" value={kind} onChange={(e) => chooseKind(e.target.value)}>
            {kindChoices.map((k) => (
              <option key={k} value={k}>
                {t(`rules.kind.${k}`)}
              </option>
            ))}
          </select>
        </div>
      ) : (
        <p className="m-0 font-medium t-ink">
          {t(`rules.kind.${kind}`)}
          {building !== "main" && building !== "any" && <span className="t-mute"> · {t(`rules.building.${building}`)}</span>}
        </p>
      )}
      {hint}
      <div className="grid gap-3 sm:grid-cols-2 [&>*]:min-w-0">
        {buildingChoice && form.building_specific && (
          <div className="flex flex-col gap-1">
            <label htmlFor={`${ids}-building`}>{t("rules.form.building")}</label>
            <select id={`${ids}-building`} className="field" value={building} onChange={(e) => setBuilding(e.target.value as Baukoerper)}>
              {(["main", "annex", "pool", "any"] as const).map((b) => (
                <option key={b} value={b}>
                  {t(`rules.form.buildingKind.${b}`)}
                </option>
              ))}
            </select>
          </div>
        )}
        <div className="flex flex-col gap-1">
          <label htmlFor={`${ids}-status`}>{t("office.rules.status")}</label>
          <select id={`${ids}-status`} className="field" value={status} onChange={(e) => setStatus(e.target.value as KorrekturStatus)}>
            {(["effective", "not_regulated", "unknown"] as const).map((s) => (
              <option key={s} value={s}>
                {t(`rules.form.status.${s}`)}
              </option>
            ))}
          </select>
        </div>
      </div>
      {status === "effective" && <RegelFelder form={form} draft={draft} errors={errors} onChange={setDraft} />}

      <fieldset className="flex flex-col gap-3 border-0 p-0 m-0">
        <legend className="eyebrow mb-2">{t("rules.form.source")}</legend>
        <div className="grid gap-3 sm:grid-cols-[1fr_auto] [&>*]:min-w-0">
          <div className="flex flex-col gap-1">
            <label htmlFor={`${ids}-document`}>{t("rules.form.document")}</label>
            <select id={`${ids}-document`} className="field" value={documentId} onChange={(e) => setDocumentId(e.target.value)}>
              <option value="">{t("rules.form.noSource")}</option>
              {documents.map((d) => (
                <option key={d.id} value={d.id}>
                  {d.title}
                </option>
              ))}
            </select>
          </div>
          {documentId && (
            <div className="flex flex-col gap-1">
              <label htmlFor={`${ids}-page`}>{t("rules.form.page")}</label>
              <input
                id={`${ids}-page`}
                className="field max-w-24 num"
                inputMode="numeric"
                value={page}
                aria-invalid={pageError}
                onChange={(e) => setPage(e.target.value)}
              />
            </div>
          )}
        </div>
        {pageError && <p className="t-alert text-xs m-0">{t("rules.form.pageRequired")}</p>}
        {documentId && (
          <div className="flex flex-col gap-1">
            <label htmlFor={`${ids}-quote`}>{t("rules.form.quote")}</label>
            <textarea id={`${ids}-quote`} className="field" rows={2} maxLength={4000} lang="fr" value={quote} onChange={(e) => setQuote(e.target.value)} />
            <p className="t-mute text-xs m-0">{t("rules.form.quoteHint")}</p>
          </div>
        )}
      </fieldset>

      <div className="flex flex-col gap-1">
        <label htmlFor={`${ids}-note`}>{t("rules.form.note")}</label>
        <textarea
          id={`${ids}-note`}
          className="field"
          rows={2}
          required
          minLength={3}
          maxLength={2000}
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        <p className="t-mute text-xs m-0">{t("rules.form.noteHint")}</p>
      </div>

      {serverError && (
        <p role="alert" className="t-alert m-0">
          {serverError}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <button type="submit" className="btn btn-primary" disabled={pending || note.trim().length < 3}>
          {pending ? t("loading") : t("rules.form.save")}
        </button>
        {onCancel && (
          <button type="button" className="btn btn-ghost" onClick={onCancel}>
            {t("rules.form.cancel")}
          </button>
        )}
      </div>
    </form>
  );
}
