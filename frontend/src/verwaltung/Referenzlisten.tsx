import { useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useNavigate } from "react-router";

import { ApiError } from "../api/client";
import {
  useCreateReferenceList,
  useImportReferenceList,
  useReferenceCandidates,
  useReferenceLists,
  type ReferenceListOut,
} from "../api/reference";
import { LISTEN_PFAD } from "./pfade";

export function fehlerText(error: unknown, fallback: string): string | null {
  if (!error) return null;
  return error instanceof ApiError ? (error.problem.detail ?? error.problem.title ?? fallback) : fallback;
}

function Messung({ list }: { list: ReferenceListOut }) {
  const { t } = useTranslation();
  if (!list.summary) return <span className="t-mute">{t("verwaltung.reference.notHere")}</span>;
  const counts = list.summary.counts;
  return (
    <span>
      {t("verwaltung.reference.recall", { recall: Math.round(list.summary.recall * 100), version: list.summary.version })}
      {(counts.wrong_value ?? 0) > 0 && <span className="t-alert"> · {t("verwaltung.reference.wrong", { count: counts.wrong_value })}</span>}
      {(counts.silent_gap ?? 0) > 0 && <span className="t-warn"> · {t("verwaltung.reference.silent", { count: counts.silent_gap })}</span>}
    </span>
  );
}

function NeueListe({ onDone }: { onDone: () => void }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const candidates = useReferenceCandidates(true);
  const create = useCreateReferenceList();
  const [auswahl, setAuswahl] = useState("");
  const options = (candidates.data ?? []).flatMap((c) => c.sectors.map((s) => ({ key: `${c.document_sha256}|${s}`, c, s })));
  const chosen = options.find((o) => o.key === auswahl) ?? options[0];
  if (candidates.isPending) return <p className="t-mute m-0">{t("loading")}</p>;
  if (options.length === 0) return <p className="t-mute m-0">{t("verwaltung.reference.noCandidates")}</p>;
  return (
    <form
      className="flex flex-wrap items-end gap-3"
      onSubmit={(event) => {
        event.preventDefault();
        if (!chosen) return;
        create.mutate(
          { document_sha256: chosen.c.document_sha256, document_title: chosen.c.document_title, sector: chosen.s, note: "" },
          {
            onSuccess: (data) => {
              onDone();
              navigate(`${LISTEN_PFAD}/${data.id}`);
            },
          },
        );
      }}
    >
      <label className="flex flex-col gap-1 text-sm">
        {t("verwaltung.reference.document")}
        <select className="field" value={chosen?.key ?? ""} onChange={(e) => setAuswahl(e.target.value)}>
          {options.map((o) => (
            <option key={o.key} value={o.key}>
              {o.c.document_title} · {t("rules.zone", { code: o.s })}
            </option>
          ))}
        </select>
      </label>
      <button type="submit" className="btn btn-primary" disabled={create.isPending}>
        {t("verwaltung.reference.create")}
      </button>
      <button type="button" className="btn btn-ghost" onClick={onDone}>
        {t("analyse.model.cancel")}
      </button>
      {create.error != null && (
        <p role="alert" className="t-alert text-sm m-0 w-full">
          {fehlerText(create.error, t("error.generic"))}
        </p>
      )}
    </form>
  );
}

function Import() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const input = useRef<HTMLInputElement>(null);
  const importieren = useImportReferenceList();
  const [ersetzen, setErsetzen] = useState(false);
  const [lesefehler, setLesefehler] = useState(false);
  return (
    <div className="flex flex-wrap items-end gap-3 text-sm">
      <label className="flex flex-col gap-1">
        {t("verwaltung.reference.import")}
        <input
          ref={input}
          type="file"
          accept="application/json,.json"
          className="field"
          onChange={async (event) => {
            const file = event.target.files?.[0];
            if (!file) return;
            setLesefehler(false);
            try {
              const data = JSON.parse(await file.text()) as Record<string, unknown>;
              importieren.mutate({ data, replace: ersetzen }, { onSuccess: (list) => navigate(`${LISTEN_PFAD}/${list.id}`) });
            } catch {
              setLesefehler(true);
            }
            if (input.current) input.current.value = "";
          }}
        />
      </label>
      <label className="flex items-center gap-2 pb-2">
        <input type="checkbox" checked={ersetzen} onChange={(e) => setErsetzen(e.target.checked)} />
        {t("verwaltung.reference.replace")}
      </label>
      {(lesefehler || importieren.error != null) && (
        <p role="alert" className="t-alert m-0 w-full">
          {lesefehler ? t("verwaltung.reference.fileError") : fehlerText(importieren.error, t("error.generic"))}
        </p>
      )}
    </div>
  );
}

/** Referenzlisten (VA10): je Dokument und Sektor die Soll-Regeln, gemessen an der Auswertung dieser Instanz. */
export function Referenzlisten() {
  const { t, i18n } = useTranslation();
  const lists = useReferenceLists();
  const [neu, setNeu] = useState(false);
  return (
    <section aria-labelledby="referenzlisten" className="flex flex-col gap-4">
      <h3 id="referenzlisten" className="eyebrow m-0">
        {t("verwaltung.nav.reference")}
      </h3>
      <p className="text-sm t-mute m-0 max-w-prose">{t("verwaltung.reference.intro")}</p>
      {lists.isPending && <p className="t-mute m-0">{t("loading")}</p>}
      {lists.isError && <p className="t-alert m-0">{t("error.generic")}</p>}
      {lists.data && lists.data.length === 0 && <p className="t-mute m-0">{t("verwaltung.reference.empty")}</p>}
      {lists.data && lists.data.length > 0 && (
        <div className="overflow-x-auto">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="text-left border-b bd-strong">
                <th scope="col" className="py-2 pr-3 font-medium">{t("verwaltung.reference.document")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("verwaltung.reference.status")}</th>
                <th scope="col" className="py-2 pr-3 font-medium">{t("verwaltung.reference.entries")}</th>
                <th scope="col" className="py-2 font-medium">{t("verwaltung.reference.measurement")}</th>
              </tr>
            </thead>
            <tbody>
              {lists.data.map((list) => (
                <tr key={list.id} className="border-b bd align-top">
                  <th scope="row" className="py-2 pr-3 font-normal text-left">
                    <Link className="link" to={`${LISTEN_PFAD}/${list.id}`}>
                      {list.document_title} · {t("rules.zone", { code: list.sector })}
                    </Link>
                    <span className="block text-xs t-mute">
                      {t(list.updated_by_name ? "verwaltung.reference.updated" : "verwaltung.reference.updatedAt", {
                        date: new Date(list.updated_at).toLocaleString(i18n.language),
                        who: list.updated_by_name,
                      })}
                    </span>
                  </th>
                  <td className="py-2 pr-3">
                    <span className="chip">{t(`verwaltung.reference.state.${list.status}`)}</span>
                  </td>
                  <td className="py-2 pr-3 num">{list.entries_count}</td>
                  <td className="py-2">
                    <Messung list={list} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {neu ? (
        <NeueListe onDone={() => setNeu(false)} />
      ) : (
        <div>
          <button type="button" className="btn btn-ghost" onClick={() => setNeu(true)}>
            {t("verwaltung.reference.new")}
          </button>
        </div>
      )}
      <Import />
    </section>
  );
}
