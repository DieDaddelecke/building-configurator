import { useEffect, useId, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router";

import { ApiError } from "../api/client";
import { useRulesModel, useRulesModels, useSetRulesModel, type RulesModelOut } from "../api/rules";

const usd = (value: number, language: string) =>
  new Intl.NumberFormat(language, { style: "currency", currency: "USD", maximumFractionDigits: 2 }).format(value);

/**
 * KI-Modell der Auswertung (PLAN_AN2_PLU 8, ANNAHMEN PU11): eine Einstellung für alle künftigen Auswertungen
 * in Konfigurator und Analyse, gepflegt in der Verwaltung (VA09). Ändern dürfen `ops` und `rules_admin`, weil
 * die Wahl die Kosten aller Projekte bestimmt; anderswo zeigt der Abschnitt das Modell und verweist mit
 * `aendernUnter` auf die Verwaltung. Liste und Preise kommen vom Server (Liste von OpenRouter). Modelle ohne
 * PDF-Eingabe bekommen die Textschicht der Seiten (PU12); der Dialog sagt, was dabei verloren geht.
 */
export function ModellWahl({ darfAendern, aendernUnter }: { darfAendern: boolean; aendernUnter?: string }) {
  const { t, i18n } = useTranslation();
  const modell = useRulesModel();
  const [offen, setOffen] = useState(false);
  if (!modell.data) return null;
  const aktuell = modell.data;
  const sprache = i18n.language;

  return (
    <section aria-labelledby="ki-modell" className="karte p-4 flex flex-col gap-2">
      <h2 id="ki-modell" className="eyebrow m-0">
        {t("analyse.model.title")}
      </h2>
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="f-mono break-all" data-testid="ki-modell">
          {aktuell.model}
        </span>
        {aktuell.source === "default" && <span className="chip">{t("analyse.model.default")}</span>}
        {aktuell.input === "text" && <span className="chip">{t("analyse.model.asText")}</span>}
        <span className="text-sm t-mute">
          {t("analyse.model.prices", {
            input: usd(aktuell.price_input_per_mtok, sprache),
            output: usd(aktuell.price_output_per_mtok, sprache),
          })}
        </span>
        {darfAendern && (
          <button type="button" className="btn btn-ghost" onClick={() => setOffen(true)}>
            {t("analyse.model.change")}
          </button>
        )}
        {!darfAendern && aendernUnter && (
          <Link className="link text-sm" to={aendernUnter}>
            {t("analyse.model.changeInAdmin")}
          </Link>
        )}
      </div>
      <p className="text-sm t-mute m-0">
        {t("analyse.model.cost", { spent: usd(aktuell.month_cost_usd, sprache), budget: usd(aktuell.budget_month_usd, sprache) })}
        {aktuell.updated_by_name && <> · {t("analyse.model.chosenBy", { name: aktuell.updated_by_name })}</>}
      </p>
      {!aktuell.configured && <p className="text-sm t-warn m-0">{t("analyse.model.noKey")}</p>}
      {offen && <ModellDialog aktuell={aktuell} onClose={() => setOffen(false)} />}
    </section>
  );
}

function ModellDialog({ aktuell, onClose }: { aktuell: RulesModelOut; onClose: () => void }) {
  const { t, i18n } = useTranslation();
  const titelId = useId();
  const liste = useRulesModels(true);
  const setzen = useSetRulesModel();
  const [suche, setSuche] = useState("");
  const [wahl, setWahl] = useState(aktuell.model);
  const sucheRef = useRef<HTMLInputElement>(null);
  const listeRef = useRef<HTMLDivElement>(null);
  const geladen = Boolean(liste.data);

  useEffect(() => {
    // Die Liste hat rund hundert Modelle, sortiert nach Anbieter: das eingestellte beim Öffnen zeigen
    const gewaehlt = listeRef.current?.querySelector("input:checked")?.closest("label");
    if (gewaehlt && typeof gewaehlt.scrollIntoView === "function") gewaehlt.scrollIntoView({ block: "center" });
  }, [geladen]);

  useEffect(() => {
    sucheRef.current?.focus();
    const taste = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", taste);
    return () => document.removeEventListener("keydown", taste);
  }, [onClose]);

  const treffer = useMemo(() => {
    const begriff = suche.trim().toLowerCase();
    return (liste.data ?? []).filter((m) => !begriff || m.name.toLowerCase().includes(begriff) || m.id.includes(begriff));
  }, [liste.data, suche]);

  const speichern = (model: string) => setzen.mutate(model, { onSuccess: onClose });
  const fehler =
    setzen.error instanceof ApiError ? (setzen.error.problem.detail ?? setzen.error.problem.title) : setzen.error ? t("error.generic") : null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start sm:items-center justify-center p-4 overflow-y-auto"
      style={{ background: "rgb(0 0 0 / 0.45)" }}
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <div role="dialog" aria-modal="true" aria-labelledby={titelId} className="karte w-full max-w-2xl p-5 flex flex-col gap-4">
        <h2 id={titelId} className="m-0 text-lg font-medium">
          {t("analyse.model.dialogTitle")}
        </h2>
        <p className="text-sm t-mute m-0">{t("analyse.model.hint")}</p>
        <label className="flex flex-col gap-1 text-sm">
          {t("analyse.model.search")}
          <input ref={sucheRef} type="search" className="field" value={suche} onChange={(e) => setSuche(e.target.value)} />
        </label>

        {liste.isPending && <p className="t-mute m-0">{t("loading")}</p>}
        {liste.isError && (
          <p role="alert" className="t-alert m-0">
            {t("analyse.model.listError")}
          </p>
        )}
        {liste.data && (
          <fieldset className="m-0 p-0 border-0 flex flex-col gap-1 min-w-0">
            <legend className="text-sm t-mute flex justify-between w-full mb-1">
              <span>{t("analyse.model.count", { count: treffer.length })}</span>
              <span>{t("analyse.model.priceHead")}</span>
            </legend>
            <div ref={listeRef} className="max-h-[50vh] overflow-y-auto border bd">
              {treffer.length === 0 && <p className="t-mute text-sm m-0 p-3">{t("analyse.model.none")}</p>}
              {treffer.map((m) => (
                <label
                  key={m.id}
                  className="flex items-start gap-3 px-3 py-2 border-b bd cursor-pointer"
                  style={wahl === m.id ? { background: "var(--accent-tint)" } : undefined}
                >
                  <input type="radio" name="ki-modell" className="mt-1" value={m.id} checked={wahl === m.id} onChange={() => setWahl(m.id)} />
                  <span className="flex-1 min-w-0">
                    <span className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{m.name}</span>
                      {m.id === aktuell.model && <span className="chip">{t("analyse.model.current")}</span>}
                      {m.id === aktuell.default_model && <span className="chip">{t("analyse.model.default")}</span>}
                      {!m.reads_pdf && <span className="chip">{t("analyse.model.asText")}</span>}
                    </span>
                    <span className="block f-mono text-xs t-mute break-all">{m.id}</span>
                  </span>
                  <span className="text-sm f-mono num whitespace-nowrap text-right">
                    {usd(m.price_input_per_mtok, i18n.language)} / {usd(m.price_output_per_mtok, i18n.language)}
                  </span>
                </label>
              ))}
            </div>
          </fieldset>
        )}

        <p className={`text-sm m-0 ${wahl.startsWith("anthropic/") ? "t-mute" : "t-warn"}`}>{t("analyse.model.claudeHint")}</p>
        {liste.data?.some((m) => m.id === wahl && !m.reads_pdf) && <p className="text-sm m-0 t-warn">{t("analyse.model.textHint")}</p>}
        {fehler && (
          <p role="alert" className="t-alert text-sm m-0">
            {fehler}
          </p>
        )}
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" className="btn btn-primary" disabled={wahl === aktuell.model || setzen.isPending} onClick={() => speichern(wahl)}>
            {t("analyse.model.save")}
          </button>
          <button type="button" className="btn btn-ghost" onClick={onClose}>
            {t("analyse.model.cancel")}
          </button>
          {/* Auch ohne Liste von OpenRouter: die Vorgabe der Umgebung braucht keine */}
          {aktuell.source === "setting" && (
            <button type="button" className="btn btn-ghost ml-auto" disabled={setzen.isPending} onClick={() => speichern(aktuell.default_model)}>
              {t("analyse.model.reset", { model: aktuell.default_model })}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
