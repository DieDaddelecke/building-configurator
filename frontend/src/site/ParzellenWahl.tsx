/**
 * Schritt „Parzelle wählen“ (Plan 3.3): Adresse suchen oder Parzellennummer eingeben, auf der Karte eine
 * oder mehrere zusammenhängende Parzellen wählen, Grundstück bilden. Ohne Maus bedienbar über Suche,
 * Kandidatenliste und Parzellennummer.
 */

import { lazy, Suspense, useId, useState } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../api/client";
import {
  lookupParcels,
  useFormSite,
  useGeocode,
  useServiceArea,
  type AddressOut,
  type LookupOut,
} from "../api/site";
import type { Basemap, KartenFokus } from "../components/karte/Katasterkarte";
import { firstPosition, unionBbox } from "./geo";
import { useDebounced } from "./useDebounced";

const Katasterkarte = lazy(() => import("../components/karte/Katasterkarte"));
const MAX_PARCELS = 10;

function KarteLaedt() {
  const { t } = useTranslation();
  return (
    <div className="karte flex items-center justify-center" style={{ height: "min(70vh, 34rem)" }}>
      <span className="eyebrow">{t("loading")}</span>
    </div>
  );
}

function kurz(idu: string): string {
  return `${idu.slice(8, 10).replace(/^0/, "")} ${Number(idu.slice(10))}`;
}

interface ParzellenWahlProps {
  /** Liefert die Projektkennung und legt das Projekt beim ersten Bedarf an. */
  ensureProject: () => Promise<string>;
  initial: readonly string[];
  /** Kartenausschnitt beim Öffnen, z. B. das bisherige Grundstück. */
  initialFocus?: KartenFokus | null;
  onFormed: () => void;
  onCancel?: () => void;
}

export function ParzellenWahl({ ensureProject, initial, initialFocus = null, onFormed, onCancel }: ParzellenWahlProps) {
  const { t } = useTranslation();
  const inputId = useId();
  const [query, setQuery] = useState("");
  const deferred = useDebounced(query, 350);
  const [address, setAddress] = useState<AddressOut | null>(null);
  const [lookup, setLookup] = useState<LookupOut | null>(null);
  const [selected, setSelected] = useState<string[]>([...initial]);
  const [focus, setFocus] = useState<KartenFokus | null>(initialFocus);
  const [basemap, setBasemap] = useState<Basemap>("plan");
  const [reference, setReference] = useState({ section: "", number: "" });
  const [lookupError, setLookupError] = useState<string | null>(null);
  /** Gemeinde der Parzellennummer, von Hand gewählt; sonst die der Adresse oder die erste des Einzugsgebiets. */
  const [chosenCommune, setChosenCommune] = useState<string | null>(null);

  const serviceArea = useServiceArea(true);
  const suggestions = useGeocode(address ? "" : deferred);
  const formSite = useFormSite();
  const communes = serviceArea.data ?? [];
  const firstCommune = communes[0];

  const toggle = (idu: string) =>
    setSelected((current) =>
      current.includes(idu) ? current.filter((v) => v !== idu) : current.length < MAX_PARCELS ? [...current, idu] : current,
    );

  const runLookup = async (body: Parameters<typeof lookupParcels>[1]) => {
    setLookupError(null);
    try {
      const result = await lookupParcels(await ensureProject(), body);
      setLookup(result);
      if (result.contained_idu) setSelected([result.contained_idu]);
      const first = result.candidates[0];
      const position = first ? firstPosition(first.geometry_geojson) : null;
      if (first && position && "commune_insee" in body) setFocus({ lon: position[0], lat: position[1], key: first.idu });
    } catch (error) {
      setLookupError(error instanceof ApiError ? error.problem.title : t("error.generic"));
    }
  };

  const chooseAddress = (candidate: AddressOut) => {
    setAddress(candidate);
    setChosenCommune(null);
    setQuery(candidate.label);
    setFocus({ lon: candidate.lon, lat: candidate.lat, key: `${candidate.lon},${candidate.lat}` });
    void runLookup({ lon: candidate.lon, lat: candidate.lat });
  };

  const outside = (address && !address.in_service_area) || (lookup && !lookup.in_service_area);
  const commune = chosenCommune ?? (address?.in_service_area ? address.citycode : firstCommune?.insee);

  return (
    <div className="flex flex-col gap-8">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-8 items-start">
        <div className="lg:col-span-4 flex flex-col gap-6">
          <div className="flex flex-col gap-2">
            <label htmlFor={inputId} className="text-sm font-medium t-ink">
              {t("site.search.label")}
            </label>
            <input
              id={inputId}
              className="field"
              value={query}
              autoComplete="street-address"
              placeholder={t("site.search.placeholder")}
              onChange={(event) => {
                setQuery(event.target.value);
                setAddress(null);
              }}
              aria-describedby={`${inputId}-hint`}
            />
            <p id={`${inputId}-hint`} className="text-xs t-faint m-0">
              {t("site.search.hint")}
            </p>
            {suggestions.isError && (
              <p role="alert" className="text-sm t-alert m-0">
                {suggestions.error instanceof ApiError ? suggestions.error.problem.title : t("error.generic")}
              </p>
            )}
            {!address && suggestions.data && suggestions.data.length > 0 && (
              <ul className="m-0 p-0 list-none border bd bg-sheet" aria-label={t("site.search.results")}>
                {suggestions.data.map((candidate) => (
                  <li key={`${candidate.label}-${candidate.lon}`}>
                    <button
                      type="button"
                      className="w-full text-left px-3 py-2 border-b bd hover:bg-tint"
                      onClick={() => chooseAddress(candidate)}
                    >
                      <span className="t-ink">{candidate.label}</span>
                      {!candidate.in_service_area && <span className="block text-xs t-warn">{t("site.search.outside")}</span>}
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <details className="text-sm">
            <summary className="cursor-pointer t-accent">{t("site.reference.toggle")}</summary>
            <form
              className="flex flex-col gap-2 pt-3"
              onSubmit={(event) => {
                event.preventDefault();
                if (commune && reference.section && reference.number) {
                  void runLookup({ commune_insee: commune, section: reference.section, number: reference.number });
                }
              }}
            >
              {communes.length > 1 ? (
                <label className="flex flex-col gap-1">
                  <span>{t("site.reference.communeLabel")}</span>
                  <select className="field" value={commune ?? ""} onChange={(e) => setChosenCommune(e.target.value)}>
                    {communes.map((c) => (
                      <option key={c.insee} value={c.insee}>
                        {c.name}
                      </option>
                    ))}
                  </select>
                </label>
              ) : (
                <p className="m-0 t-mute">
                  {t("site.reference.commune", { commune: communes.find((c) => c.insee === commune)?.name ?? commune ?? "–" })}
                </p>
              )}
              <div className="flex gap-2">
                <label className="flex-1 flex flex-col gap-1">
                  <span>{t("site.reference.section")}</span>
                  <input className="field" value={reference.section} maxLength={2} onChange={(e) => setReference({ ...reference, section: e.target.value.toUpperCase() })} />
                </label>
                <label className="flex-1 flex flex-col gap-1">
                  <span>{t("site.reference.number")}</span>
                  <input className="field" value={reference.number} inputMode="numeric" maxLength={4} onChange={(e) => setReference({ ...reference, number: e.target.value.replace(/\D/g, "") })} />
                </label>
              </div>
              <button type="submit" className="btn btn-ghost self-start" disabled={!commune}>
                {t("site.reference.submit")}
              </button>
            </form>
          </details>

          {lookupError && (
            <p role="alert" className="text-sm t-alert m-0">
              {lookupError}
            </p>
          )}
          {outside && (
            <p role="status" className="bg-warn t-warn px-4 py-3 text-sm m-0">
              {t("site.outside")}
            </p>
          )}
          {lookup && lookup.in_service_area && lookup.candidates.length > 0 && (
            <section aria-labelledby="kandidaten">
              <h2 id="kandidaten" className="eyebrow mb-2">
                {lookup.contained_idu ? t("site.candidates.contained") : t("site.candidates.near")}
              </h2>
              <ul className="m-0 p-0 list-none flex flex-wrap gap-2">
                {lookup.candidates.map((candidate) => (
                  <li key={candidate.idu}>
                    <button type="button" className="chip" aria-pressed={selected.includes(candidate.idu)} onClick={() => toggle(candidate.idu)}>
                      {kurz(candidate.idu)}
                      {candidate.area_official_m2 != null && <span className="t-mute"> · {candidate.area_official_m2} m²</span>}
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {lookup && lookup.in_service_area && lookup.candidates.length === 0 && (
            <p className="text-sm t-mute m-0">{t("site.candidates.none")}</p>
          )}
        </div>

        <div className="lg:col-span-8 flex flex-col gap-3">
          <div role="group" aria-label={t("site.map.basemap")} className="flex gap-1 self-end">
            {(["plan", "photo"] as const).map((b) => (
              <button key={b} type="button" className="chip" aria-pressed={basemap === b} onClick={() => setBasemap(b)}>
                {t(`site.map.${b}`)}
              </button>
            ))}
          </div>
          {/* Die Karte übernimmt den Ausschnitt nur beim Anlegen, daher erst mit den Gemeinden */}
          {serviceArea.isPending ? (
            <KarteLaedt />
          ) : (
            <Suspense fallback={<KarteLaedt />}>
              <Katasterkarte
                selected={selected}
                candidates={lookup?.candidates.map((c) => c.idu) ?? []}
                onToggle={toggle}
                focus={focus}
                initialBounds={unionBbox(communes.map((c) => c.bbox))}
                basemap={basemap}
              />
            </Suspense>
          )}
        </div>
      </div>

      <section aria-labelledby="auswahl" className="border-t bd pt-6 flex flex-col gap-4">
        <h2 id="auswahl" className="eyebrow m-0">
          {t("site.selection.title", { count: selected.length })}
        </h2>
        {selected.length === 0 ? (
          <p className="t-mute text-sm m-0">{t("site.selection.empty")}</p>
        ) : (
          <ul className="m-0 p-0 list-none flex flex-wrap gap-2">
            {selected.map((idu) => (
              <li key={idu}>
                <button type="button" className="chip" aria-pressed="true" onClick={() => toggle(idu)} aria-label={t("site.selection.remove", { parcel: kurz(idu) })}>
                  {kurz(idu)} ×
                </button>
              </li>
            ))}
          </ul>
        )}
        {formSite.error instanceof ApiError && (
          <p role="alert" className="t-alert text-sm m-0">
            {formSite.error.problem.title}
          </p>
        )}
        <div className="flex flex-wrap gap-3">
          <button
            type="button"
            className="btn btn-primary"
            disabled={selected.length === 0 || formSite.isPending}
            onClick={() => void ensureProject().then((projectId) => formSite.mutate({ projectId, idus: selected }, { onSuccess: onFormed }))}
          >
            {formSite.isPending ? t("loading") : t("site.selection.submit")}
          </button>
          {onCancel && (
            <button type="button" className="btn btn-ghost" onClick={onCancel}>
              {t("site.selection.cancel")}
            </button>
          )}
        </div>
      </section>
    </div>
  );
}
