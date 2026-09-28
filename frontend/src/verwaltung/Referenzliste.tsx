import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate, useParams } from "react-router";

import {
  exportReferenceList,
  useDeleteReferenceEntry,
  useDeleteReferenceList,
  usePatchReferenceList,
  useReferenceFromEvaluation,
  useReferenceList,
  useReferenceMeasurement,
  useSaveReferenceEntry,
  type MeasuredEntryOut,
  type ReferenceEntryIn,
  type ReferenceEntryOut,
} from "../api/reference";
import { useRuleKinds, type RuleKindFormOut, type RuleOut } from "../api/rules";
import { RegelFelder } from "../rules/RegelFormular";
import { entwurfAus, parameterAus, type Entwurf, type FeldFehler } from "../rules/felder";
import { ruleValue } from "../rules/format";
import { LISTEN_PFAD } from "./pfade";
import { fehlerText } from "./Referenzlisten";

const EXPECTED = ["effective", "not_regulated", "text_only", "graphic_reference", "not_expressible"] as const;
const BUILDING = ["any", "main", "annex", "pool"] as const;
const OUTCOME_CLASS: Record<string, string> = {
  hit: "t-ink",
  wrong_value: "t-alert",
  named_gap: "t-warn",
  dismissed: "t-warn",
  silent_gap: "t-alert",
};

function Werte({ entry }: { entry: ReferenceEntryIn }) {
  const { t, i18n } = useTranslation();
  if (entry.expected !== "effective") return <span className="t-mute">{t(`verwaltung.reference.expected.${entry.expected}`)}</span>;
  const rule = { kind: entry.kind, status: "effective", reason: null, params: entry.params ?? {} } as unknown as RuleOut;
  return <span>{ruleValue(rule, t, i18n.language)}</span>;
}

function Ergebnis({ result }: { result: MeasuredEntryOut | undefined }) {
  const { t } = useTranslation();
  if (!result) return <span className="t-mute">–</span>;
  return (
    <span className={OUTCOME_CLASS[result.outcome]}>
      {t(`verwaltung.reference.outcome.${result.outcome}`)}
      {result.detail && <span className="t-mute"> ({t(`rules.reason.${result.detail}`, { defaultValue: result.detail })})</span>}
    </span>
  );
}

const LEER: ReferenceEntryIn = { kind: "setback_street", building_kind: "main", expected: "effective", params: {}, page: null, quote: "", note: "" };

interface FormularProps {
  listId: string;
  entry?: ReferenceEntryOut;
  onDone: () => void;
}

/** Lädt die Formularbeschreibung der Regelarten (AN4, KR01), bevor die Felder ihren Entwurf bilden. */
function EintragFormular(props: FormularProps) {
  const { t } = useTranslation();
  const kinds = useRuleKinds();
  if (kinds.isPending) return <p className="t-mute m-0">{t("loading")}</p>;
  if (!kinds.data) return <p className="t-alert m-0">{t("error.generic")}</p>;
  return <EintragFelder {...props} kinds={kinds.data} />;
}

function EintragFelder({ listId, entry, onDone, kinds }: FormularProps & { kinds: RuleKindFormOut[] }) {
  const { t, i18n } = useTranslation();
  const save = useSaveReferenceEntry(listId);
  const [werte, setWerte] = useState<ReferenceEntryIn>(entry ?? LEER);
  const form = kinds.find((k) => k.kind === werte.kind);
  const [draft, setDraft] = useState<Entwurf>(() => (form ? entwurfAus(form.params, werte.params ?? {}, i18n.language) : {}));
  const [errors, setErrors] = useState<FeldFehler>({});
  const mitWerten = werte.expected === "effective" && werte.kind !== "text_only" && form !== undefined;
  const setKind = (kind: ReferenceEntryIn["kind"]) => {
    const next = kinds.find((k) => k.kind === kind);
    setWerte({ ...werte, kind, expected: kind === "text_only" ? "text_only" : werte.expected === "text_only" ? "effective" : werte.expected });
    setDraft(next ? entwurfAus(next.params, {}, i18n.language) : {});
  };
  return (
    <form
      className="karte p-4 flex flex-col gap-3"
      aria-label={t(entry ? "verwaltung.reference.editEntry" : "verwaltung.reference.addEntry")}
      onSubmit={(event) => {
        event.preventDefault();
        let params: Record<string, unknown> = {};
        if (mitWerten && form) {
          const parsed = parameterAus(form.params, draft);
          if (Object.keys(parsed.errors).length > 0) {
            setErrors(parsed.errors);
            return;
          }
          params = parsed.params;
        }
        save.mutate({ entryId: entry?.id, body: { ...werte, params } }, { onSuccess: onDone });
      }}
    >
      <div className="grid gap-3 sm:grid-cols-3">
        <label className="flex flex-col gap-1 text-sm">
          {t("rules.column.kind")}
          <select className="field" value={werte.kind} onChange={(e) => setKind(e.target.value as ReferenceEntryIn["kind"])}>
            {kinds.map((k) => (
              <option key={k.kind} value={k.kind}>
                {t(`rules.kind.${k.kind}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("verwaltung.reference.building")}
          <select
            className="field"
            value={werte.building_kind}
            onChange={(e) => setWerte({ ...werte, building_kind: e.target.value as ReferenceEntryIn["building_kind"] })}
          >
            {BUILDING.map((b) => (
              <option key={b} value={b}>
                {t(`rules.building.${b}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("verwaltung.reference.expectedLabel")}
          <select
            className="field"
            value={werte.expected}
            disabled={werte.kind === "text_only"}
            onChange={(e) => setWerte({ ...werte, expected: e.target.value as ReferenceEntryIn["expected"] })}
          >
            {EXPECTED.filter((x) => (werte.kind === "text_only" ? x === "text_only" : x !== "text_only")).map((x) => (
              <option key={x} value={x}>
                {t(`verwaltung.reference.expected.${x}`)}
              </option>
            ))}
          </select>
        </label>
      </div>
      {mitWerten && form && (
        <>
          <p className="text-xs t-mute m-0">{t("verwaltung.reference.paramsHint")}</p>
          <RegelFelder form={form} draft={draft} errors={errors} onChange={setDraft} />
        </>
      )}
      <div className="grid gap-3 sm:grid-cols-[8rem_1fr]">
        <label className="flex flex-col gap-1 text-sm">
          {t("verwaltung.reference.page")}
          <input
            type="number"
            min={1}
            className="field"
            value={werte.page ?? ""}
            onChange={(e) => setWerte({ ...werte, page: e.target.value ? Number(e.target.value) : null })}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          {t("verwaltung.reference.quote")}
          <textarea className="field" rows={3} required minLength={3} value={werte.quote} onChange={(e) => setWerte({ ...werte, quote: e.target.value })} />
        </label>
      </div>
      <label className="flex flex-col gap-1 text-sm">
        {t("verwaltung.reference.note")}
        <input className="field" value={werte.note ?? ""} onChange={(e) => setWerte({ ...werte, note: e.target.value })} />
      </label>
      {save.error != null && (
        <p role="alert" className="t-alert text-sm m-0">
          {fehlerText(save.error, t("error.generic"))}
        </p>
      )}
      <div className="flex gap-3">
        <button type="submit" className="btn btn-primary" disabled={save.isPending}>
          {t("verwaltung.reference.save")}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onDone}>
          {t("analyse.model.cancel")}
        </button>
      </div>
    </form>
  );
}

/** Eine Referenzliste: Messung der Auswertung dieser Instanz, Einträge, Pflege (VA10). */
export function Referenzliste() {
  const { t } = useTranslation();
  const { listId = "" } = useParams();
  const navigate = useNavigate();
  const list = useReferenceList(listId);
  const [version, setVersion] = useState<number | null>(null);
  const measurement = useReferenceMeasurement(listId, version, Boolean(list.data?.summary));
  const patch = usePatchReferenceList(listId);
  const fromEvaluation = useReferenceFromEvaluation(listId);
  const remove = useDeleteReferenceList(listId);
  const removeEntry = useDeleteReferenceEntry(listId);
  const [bearbeiten, setBearbeiten] = useState<string | "neu" | null>(null);
  const data = list.data;
  if (list.isPending) return <p className="t-mute">{t("loading")}</p>;
  if (!data) return <p className="t-alert">{t("error.generic")}</p>;
  const results = new Map((measurement.data?.results ?? []).map((r) => [r.entry_id, r]));
  const counts = measurement.data?.counts;

  return (
    <section aria-labelledby="referenzliste" className="flex flex-col gap-5">
      <Link className="link text-sm" to={LISTEN_PFAD}>
        {t("verwaltung.reference.back")}
      </Link>
      <div className="flex flex-wrap items-center gap-3">
        <h3 id="referenzliste" className="m-0 text-xl font-medium">
          {data.document_title} · {t("rules.zone", { code: data.sector })}
        </h3>
        <span className="chip">{t(`verwaltung.reference.state.${data.status}`)}</span>
      </div>
      {data.note && <p className="text-sm t-mute m-0 max-w-prose">{data.note}</p>}
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="btn btn-ghost"
          disabled={patch.isPending}
          onClick={() => patch.mutate({ status: data.status === "checked" ? "draft" : "checked" })}
        >
          {t(data.status === "checked" ? "verwaltung.reference.toDraft" : "verwaltung.reference.toChecked")}
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          disabled={fromEvaluation.isPending}
          onClick={() => {
            if (window.confirm(t("verwaltung.reference.fromEvaluationConfirm"))) fromEvaluation.mutate();
          }}
        >
          {t("verwaltung.reference.fromEvaluation")}
        </button>
        <button type="button" className="btn btn-ghost" onClick={() => void exportReferenceList(listId, `referenz-${data.sector}.json`)}>
          {t("verwaltung.reference.export")}
        </button>
        <button
          type="button"
          className="btn btn-ghost ml-auto"
          disabled={remove.isPending}
          onClick={() => {
            if (window.confirm(t("verwaltung.reference.deleteConfirm"))) remove.mutate(undefined, { onSuccess: () => navigate(LISTEN_PFAD) });
          }}
        >
          {t("verwaltung.reference.delete")}
        </button>
      </div>
      {fromEvaluation.error != null && (
        <p role="alert" className="t-alert text-sm m-0">
          {fehlerText(fromEvaluation.error, t("error.generic"))}
        </p>
      )}

      <div className="karte p-4 flex flex-col gap-2 text-sm" data-testid="messung">
        {!data.summary && <p className="t-mute m-0">{t("verwaltung.reference.notHere")}</p>}
        {measurement.data && counts && (
          <>
            <div className="flex flex-wrap items-center gap-3">
              <label className="flex items-center gap-2">
                {t("verwaltung.reference.version")}
                <select
                  className="field"
                  value={measurement.data.version}
                  onChange={(e) => setVersion(Number(e.target.value))}
                >
                  {measurement.data.versions.map((v) => (
                    <option key={v} value={v}>
                      {v}
                    </option>
                  ))}
                </select>
              </label>
              <span className="t-mute f-mono">{measurement.data.model ?? ""}</span>
            </div>
            <p className="m-0">
              {t("verwaltung.reference.counts", {
                hit: counts.hit ?? 0,
                total: counts.entries ?? 0,
                recall: Math.round(measurement.data.recall * 100),
                wrong: counts.wrong_value ?? 0,
                named: counts.named_gap ?? 0,
                dismissed: counts.dismissed ?? 0,
                silent: counts.silent_gap ?? 0,
              })}
            </p>
            {measurement.data.extra.length > 0 && (
              <p className="t-mute m-0">{t("verwaltung.reference.extra", { count: measurement.data.extra.length })}</p>
            )}
          </>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-sm border-collapse">
          <thead>
            <tr className="text-left border-b bd-strong">
              <th scope="col" className="py-2 pr-3 font-medium">{t("rules.column.kind")}</th>
              <th scope="col" className="py-2 pr-3 font-medium">{t("verwaltung.reference.expectedLabel")}</th>
              <th scope="col" className="py-2 pr-3 font-medium">{t("verwaltung.reference.quote")}</th>
              <th scope="col" className="py-2 pr-3 font-medium">{t("verwaltung.reference.result")}</th>
              <th scope="col" className="py-2 font-medium">
                <span className="sr-only">{t("verwaltung.reference.actions")}</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {data.entries.map((entry) => (
              <tr key={entry.id} className="border-b bd align-top">
                <th scope="row" className="py-2 pr-3 font-normal text-left">
                  {t(`rules.kind.${entry.kind}`)}
                  {entry.building_kind !== "any" && entry.building_kind !== "main" && (
                    <span className="t-mute"> · {t(`rules.building.${entry.building_kind}`)}</span>
                  )}
                  {entry.page != null && <span className="block text-xs t-mute">{t("rules.page", { page: entry.page })}</span>}
                </th>
                <td className="py-2 pr-3">
                  <Werte entry={entry} />
                </td>
                <td className="py-2 pr-3 t-mute text-xs max-w-md">{entry.quote}</td>
                <td className="py-2 pr-3">
                  <Ergebnis result={results.get(entry.id)} />
                </td>
                <td className="py-2 whitespace-nowrap">
                  <button type="button" className="link text-sm" onClick={() => setBearbeiten(entry.id)}>
                    {t("verwaltung.reference.edit")}
                  </button>{" "}
                  <button
                    type="button"
                    className="link text-sm"
                    disabled={removeEntry.isPending}
                    onClick={() => {
                      if (window.confirm(t("verwaltung.reference.deleteEntryConfirm"))) removeEntry.mutate(entry.id);
                    }}
                  >
                    {t("verwaltung.reference.deleteEntry")}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {bearbeiten !== null ? (
        <EintragFormular
          key={bearbeiten}
          listId={listId}
          entry={bearbeiten === "neu" ? undefined : data.entries.find((e) => e.id === bearbeiten)}
          onDone={() => setBearbeiten(null)}
        />
      ) : (
        <div>
          <button type="button" className="btn btn-ghost" onClick={() => setBearbeiten("neu")}>
            {t("verwaltung.reference.addEntry")}
          </button>
        </div>
      )}
    </section>
  );
}
