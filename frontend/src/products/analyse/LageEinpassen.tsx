/**
 * Lage festlegen oder korrigieren (AN5, docs/PLAN_AN5_AUSGABE.md 3.2, E-AN5-1): Adresse suchen, den Umriss auf
 * der Katasterebene verschieben (Maus, Finger, Pfeiltasten 0,1 m, mit Umschalttaste 1 m) und drehen (Regler,
 * ±0,1°, ±1°), dann übernehmen. Maße und Fläche bleiben; der Server rechnet starr und fragt danach Gelände und
 * Risiken ab.
 */

import { lazy, Suspense, useId, useMemo, useState, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";

import { ApiError } from "../../api/client";
import { useGeocode, usePositionSite, type AddressOut, type SiteOut } from "../../api/site";
import type { Basemap } from "../../components/karte/kacheln";
import { formatNumber } from "../../site/geo";
import { useDebounced } from "../../site/useDebounced";
import { abstandM, tastenSchritt, umrissAufKarte, verschieben, winkel, type LonLat } from "./einpassen";

const EinpassKarte = lazy(() => import("./EinpassKarte"));

const DREHSCHRITTE = [-1, -0.1, 0.1, 1] as const;

export function LageEinpassen({ site, onFertig }: { site: SiteOut; onFertig: () => void }) {
  const { t, i18n } = useTranslation();
  const lng = i18n.language;
  const sucheId = useId();
  const drehId = useId();
  const hinweisId = useId();
  const placement = site.placement;
  const bisher = useMemo<LonLat | null>(() => {
    const [lon, lat] = placement?.pivot_wgs84 ?? [];
    return lon !== undefined && lat !== undefined ? { lon, lat } : null;
  }, [placement]);

  const [zentrum, setZentrum] = useState<LonLat | null>(bisher);
  const [delta, setDelta] = useState(0);
  const [basemap, setBasemap] = useState<Basemap>("plan");
  const [mitte, setMitte] = useState<LonLat | null>(null);
  const [fokus, setFokus] = useState<(LonLat & { key: string }) | null>(null);
  const [suche, setSuche] = useState("");
  const [gewaehlt, setGewaehlt] = useState<AddressOut | null>(null);
  const verzoegert = useDebounced(suche, 350);
  const vorschlaege = useGeocode(gewaehlt ? "" : verzoegert);
  const speichern = usePositionSite(site);

  const umriss = useMemo(
    () =>
      zentrum && placement
        ? umrissAufKarte(site.outline_local, placement.pivot_local, zentrum, placement.map_rotation_deg + delta)
        : [],
    [site.outline_local, placement, zentrum, delta],
  );

  if (!placement) return null;

  const adresseWaehlen = (adresse: AddressOut) => {
    setGewaehlt(adresse);
    setSuche(adresse.label);
    const punkt = { lon: adresse.lon, lat: adresse.lat };
    setZentrum(punkt);
    setFokus({ ...punkt, key: `${adresse.lon},${adresse.lat}` });
  };

  const taste = (event: KeyboardEvent<HTMLDivElement>) => {
    const schritt = tastenSchritt(event.key, event.shiftKey);
    if (!schritt || !zentrum) return;
    event.preventDefault();
    setZentrum(verschieben(zentrum, schritt[0], schritt[1]));
  };

  const versatz = bisher && zentrum ? abstandM(bisher, zentrum) : null;
  const geaendert = zentrum !== null && (bisher === null || (versatz ?? 0) >= 0.005 || delta !== 0);

  return (
    <section aria-labelledby="lage" className="karte p-5 flex flex-col gap-5">
      <div className="flex flex-col gap-1">
        <h2 id="lage" className="f-display text-xl m-0">
          {t(site.georeferenced ? "analyse.position.correct" : "analyse.position.set")}
        </h2>
        <p className="t-mute text-sm m-0">{t("analyse.position.intro")}</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
        <div className="lg:col-span-4 flex flex-col gap-5 min-w-0">
          <div className="flex flex-col gap-2">
            <label htmlFor={sucheId} className="text-sm font-medium t-ink">
              {t("site.search.label")}
            </label>
            <input
              id={sucheId}
              className="field"
              value={suche}
              autoComplete="street-address"
              placeholder={t("site.search.placeholder")}
              onChange={(event) => {
                setSuche(event.target.value);
                setGewaehlt(null);
              }}
            />
            {vorschlaege.isError && (
              <p role="alert" className="text-sm t-alert m-0">
                {vorschlaege.error instanceof ApiError ? vorschlaege.error.problem.title : t("error.generic")}
              </p>
            )}
            {!gewaehlt && vorschlaege.data && vorschlaege.data.length > 0 && (
              <ul className="m-0 p-0 list-none border bd bg-sheet" aria-label={t("site.search.results")}>
                {vorschlaege.data.map((adresse) => (
                  <li key={`${adresse.label}-${adresse.lon}`}>
                    <button
                      type="button"
                      className="w-full text-left px-3 py-2 border-b bd hover:bg-tint"
                      onClick={() => adresseWaehlen(adresse)}
                    >
                      {adresse.label}
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {mitte && (
              <button type="button" className="btn btn-ghost self-start" onClick={() => setZentrum(mitte)}>
                {t("analyse.position.toCentre")}
              </button>
            )}
          </div>

          <div className="flex flex-col gap-2">
            <label htmlFor={drehId} className="text-sm font-medium t-ink">
              {t("analyse.position.rotation")}{" "}
              <span className="f-mono num">
                {formatNumber(delta, lng, 1)}°
              </span>
            </label>
            <input
              id={drehId}
              type="range"
              min={-180}
              max={180}
              step={0.1}
              value={delta}
              disabled={!zentrum}
              onChange={(event) => setDelta(winkel(Number(event.target.value)))}
            />
            <div className="flex flex-wrap gap-1" role="group" aria-label={t("analyse.position.rotationSteps")}>
              {DREHSCHRITTE.map((schritt) => (
                <button
                  key={schritt}
                  type="button"
                  className="chip f-mono num"
                  disabled={!zentrum}
                  onClick={() => setDelta((value) => winkel(value + schritt))}
                  aria-label={t("analyse.position.rotateBy", { degrees: formatNumber(schritt, lng, 1) })}
                >
                  {schritt > 0 ? "+" : "−"}
                  {formatNumber(Math.abs(schritt), lng, 1)}°
                </button>
              ))}
            </div>
            <p className="text-xs t-mute m-0">{t("analyse.position.rotationHint")}</p>
          </div>

          <p id={hinweisId} className="text-sm t-mute m-0">
            {t(zentrum ? "analyse.position.moveHint" : "analyse.position.searchFirst")}
          </p>
          {versatz !== null && versatz >= 0.005 && (
            <p className="text-sm m-0" role="status">
              {t("analyse.position.moved", { metres: formatNumber(versatz, lng, versatz < 10 ? 2 : 1) })}
            </p>
          )}
          <p className="text-xs t-mute m-0">{t("analyse.position.accuracy")}</p>
        </div>

        <div className="lg:col-span-8 flex flex-col gap-3 min-w-0">
          <div role="group" aria-label={t("site.map.basemap")} className="flex gap-1 self-end">
            {(["plan", "photo"] as const).map((b) => (
              <button key={b} type="button" className="chip" aria-pressed={basemap === b} onClick={() => setBasemap(b)}>
                {t(`site.map.${b}`)}
              </button>
            ))}
          </div>
          {/* Pfeiltasten auf der Karte verschieben den Umriss; die Karte selbst hat keine Tastatursteuerung */}
          <div onKeyDown={taste} aria-describedby={hinweisId}>
            <Suspense
              fallback={
                <div className="karte flex items-center justify-center" style={{ height: "min(70vh, 34rem)" }}>
                  <span className="eyebrow">{t("loading")}</span>
                </div>
              }
            >
              <EinpassKarte
                basemap={basemap}
                umriss={umriss}
                zentrum={zentrum}
                fokus={fokus}
                onVerschieben={setZentrum}
                onMitte={setMitte}
              />
            </Suspense>
          </div>
        </div>
      </div>

      {speichern.error && (
        <p role="alert" className="t-alert text-sm m-0">
          {speichern.error instanceof ApiError ? speichern.error.problem.title : t("error.generic")}
        </p>
      )}
      <div className="flex flex-wrap gap-3">
        <button
          type="button"
          className="btn btn-primary"
          disabled={!geaendert || speichern.isPending}
          onClick={() =>
            zentrum && speichern.mutate({ lon: zentrum.lon, lat: zentrum.lat, rotation_deg: delta }, { onSuccess: onFertig })
          }
        >
          {speichern.isPending ? t("loading") : t("analyse.position.save")}
        </button>
        <button type="button" className="btn btn-ghost" onClick={onFertig}>
          {t("analyse.position.cancel")}
        </button>
      </div>
    </section>
  );
}
