/**
 * Karte mit Parzellen des importierten Katasters (Plan 3.3). Hintergrund: Plan IGN oder Luftbild der
 * Géoplateforme. Die Parzellen kommen aus der eigenen API, damit Anzeige und Auswahl denselben Stand haben.
 *
 * Nur per `React.lazy` laden: MapLibre braucht WebGL und ist groß. Tastaturbedienung: Karte verschieben und
 * zoomen per Pfeiltasten und +/−; Parzellen lassen sich zusätzlich über die Liste unter der Karte wählen.
 */

import "maplibre-gl/dist/maplibre-gl.css";

import type { FeatureCollection, Geometry } from "geojson";
import {
  Map as MapLibreMap,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
  type GeoJSONSource,
  type LngLatBoundsLike,
  type MapLayerMouseEvent,
  type RasterTileSource,
  type StyleSpecification,
} from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import { fetchParcels, type ParcelCollection } from "../../api/site";
import { ATTRIBUTION, TILES, type Basemap } from "./kacheln";

setWorkerUrl(workerUrl);

const MIN_PARCEL_ZOOM = 16.5;
const EMPTY: ParcelCollection = { type: "FeatureCollection", truncated: false, features: [] };

export type { Basemap };

export interface KartenFokus {
  lon: number;
  lat: number;
  /** Wechselt bei jeder neuen Suche, damit die Karte auch zum selben Punkt erneut springt. */
  key: string;
}

interface KatasterkarteProps {
  selected: readonly string[];
  candidates: readonly string[];
  onToggle: (idu: string) => void;
  focus: KartenFokus | null;
  initialBounds: [number, number, number, number] | null;
  basemap: Basemap;
  outline?: Geometry | null;
}

function style(basemap: Basemap): StyleSpecification {
  return {
    version: 8,
    sources: {
      base: {
        type: "raster",
        tiles: [TILES[basemap]],
        tileSize: 256,
        maxzoom: basemap === "plan" ? 18 : 20,
        attribution: ATTRIBUTION,
      },
    },
    layers: [{ id: "base", type: "raster", source: "base" }],
  };
}

export default function Katasterkarte({ selected, candidates, onToggle, focus, initialBounds, basemap, outline }: KatasterkarteProps) {
  const { t } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const toggleRef = useRef(onToggle);
  const [zoomHint, setZoomHint] = useState(false);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    toggleRef.current = onToggle;
  }, [onToggle]);

  // Karte einmal anlegen
  useEffect(() => {
    if (!container.current) return;
    const map = new MapLibreMap({
      container: container.current,
      style: style(basemap),
      bounds: (initialBounds ?? [-5.2, 42.3, 8.3, 51.1]) as LngLatBoundsLike,
      maxZoom: 20,
      attributionControl: { compact: true },
      locale: {
        "Map.Title": t("site.map.label"),
        "NavigationControl.ZoomIn": t("site.map.zoomInButton"),
        "NavigationControl.ZoomOut": t("site.map.zoomOutButton"),
        "AttributionControl.ToggleAttribution": t("site.map.attribution"),
      },
    });
    mapRef.current = map;
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new ScaleControl({ unit: "metric" }), "bottom-left");

    let controller: AbortController | null = null;
    const addOverlays = () => {
      if (map.getSource("parcels")) return;
      map.addSource("parcels", { type: "geojson", data: EMPTY as unknown as FeatureCollection, promoteId: "idu" });
      map.addSource("outline", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
      map.addLayer({ id: "parcels-fill", type: "fill", source: "parcels", paint: { "fill-color": "#2b45b0", "fill-opacity": 0.02 } });
      map.addLayer({ id: "parcels-line", type: "line", source: "parcels", paint: { "line-color": "#1c2220", "line-width": 0.8, "line-opacity": 0.7 } });
      map.addLayer({
        id: "parcels-candidate",
        type: "line",
        source: "parcels",
        filter: ["in", ["get", "idu"], ["literal", []]],
        paint: { "line-color": "#7d5300", "line-width": 2.5, "line-dasharray": [2, 1] },
      });
      map.addLayer({
        id: "parcels-selected",
        type: "fill",
        source: "parcels",
        filter: ["in", ["get", "idu"], ["literal", []]],
        paint: { "fill-color": "#2b45b0", "fill-opacity": 0.35 },
      });
      map.addLayer({ id: "outline", type: "line", source: "outline", paint: { "line-color": "#2b45b0", "line-width": 3 } });
    };

    const loadParcels = () => {
      const source = map.getSource<GeoJSONSource>("parcels");
      if (!source) return;
      if (map.getZoom() < MIN_PARCEL_ZOOM) {
        setZoomHint(true);
        source.setData(EMPTY as unknown as FeatureCollection);
        return;
      }
      setZoomHint(false);
      controller?.abort();
      controller = new AbortController();
      const b = map.getBounds();
      fetchParcels([b.getWest(), b.getSouth(), b.getEast(), b.getNorth()], controller.signal)
        .then((data) => {
          setLoadError(false);
          source.setData(data as unknown as FeatureCollection);
        })
        .catch((error: unknown) => {
          if (!(error instanceof DOMException && error.name === "AbortError")) setLoadError(true);
        });
    };

    map.on("load", () => {
      addOverlays();
      loadParcels();
    });
    map.on("style.load", addOverlays);
    map.on("moveend", loadParcels);
    map.on("click", "parcels-fill", (event: MapLayerMouseEvent) => {
      const idu = event.features?.[0]?.properties?.idu;
      if (typeof idu === "string") toggleRef.current(idu);
    });
    map.on("mouseenter", "parcels-fill", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "parcels-fill", () => (map.getCanvas().style.cursor = ""));
    return () => {
      controller?.abort();
      map.remove();
      mapRef.current = null;
    };
    // Die Karte entsteht einmal; Hintergrund, Auswahl und Fokus folgen in eigenen Effekten
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      if (!map.getLayer("parcels-selected")) return;
      map.setFilter("parcels-selected", ["in", ["get", "idu"], ["literal", [...selected]]]);
      map.setFilter("parcels-candidate", ["in", ["get", "idu"], ["literal", [...candidates]]]);
    };
    if (map.isStyleLoaded()) apply();
    else map.once("idle", apply);
  }, [selected, candidates]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !focus) return;
    map.flyTo({ center: [focus.lon, focus.lat], zoom: 18.5, speed: 1.6 });
  }, [focus]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const base = map.getSource<RasterTileSource>("base");
    base?.setTiles([TILES[basemap]]);
  }, [basemap]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      const source = map.getSource<GeoJSONSource>("outline");
      source?.setData(outline ? { type: "Feature", geometry: outline, properties: {} } : { type: "FeatureCollection", features: [] });
    };
    if (map.isStyleLoaded()) apply();
    else map.once("idle", apply);
  }, [outline]);

  return (
    <div className="relative">
      <div
        ref={container}
        className="w-full border bd-strong"
        style={{ height: "min(70vh, 34rem)" }}
        role="application"
        aria-label={t("site.map.label")}
      />
      {zoomHint && (
        <p className="absolute top-3 left-3 bg-sheet border bd px-3 py-2 text-sm t-ink m-0" role="status">
          {t("site.map.zoomIn")}
        </p>
      )}
      {loadError && (
        <p className="absolute bottom-10 left-3 bg-alert border bd-alert px-3 py-2 text-sm t-alert m-0" role="alert">
          {t("site.map.loadError")}
        </p>
      )}
    </div>
  );
}
