/**
 * Karte zum Einpassen (AN5, docs/PLAN_AN5_AUSGABE.md 3.2): Plan IGN oder Luftbild, darüber der Kataster als
 * Rasterebene der Géoplateforme (ohne eigenen Import) und der Umriss des Grundstücks. Der Umriss lässt sich mit
 * Maus oder Finger ziehen; die Pfeiltasten verschieben ihn (die Seite fängt sie ab), die Karte selbst verschiebt
 * sich dann nur mit der Maus.
 *
 * Nur per `React.lazy` laden: MapLibre braucht WebGL und ist groß.
 */

import "maplibre-gl/dist/maplibre-gl.css";

import {
  Map as MapLibreMap,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
  type GeoJSONSource,
  type MapLayerMouseEvent,
  type MapLayerTouchEvent,
  type RasterTileSource,
  type StyleSpecification,
} from "maplibre-gl";
import workerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import { useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";

import { ATTRIBUTION, CADASTRE_TILES, TILES, type Basemap } from "../../components/karte/kacheln";
import type { LonLat } from "./einpassen";

setWorkerUrl(workerUrl);

export interface EinpassKarteProps {
  basemap: Basemap;
  /** Umriss in Länge/Breite (geschlossene Ringe), leer, solange keine Lage gewählt ist. */
  umriss: [number, number][][];
  zentrum: LonLat | null;
  /** Wohin die Karte springt; `key` wechselt bei jeder neuen Suche. */
  fokus: (LonLat & { key: string }) | null;
  onVerschieben: (zentrum: LonLat) => void;
  onMitte: (mitte: LonLat) => void;
}

const LEER = { type: "FeatureCollection" as const, features: [] };

function style(basemap: Basemap): StyleSpecification {
  return {
    version: 8,
    sources: {
      base: { type: "raster", tiles: [TILES[basemap]], tileSize: 256, maxzoom: basemap === "plan" ? 18 : 20, attribution: ATTRIBUTION },
      cadastre: { type: "raster", tiles: [CADASTRE_TILES], tileSize: 256, minzoom: 14, maxzoom: 19 },
    },
    layers: [
      { id: "base", type: "raster", source: "base" },
      { id: "cadastre", type: "raster", source: "cadastre", minzoom: 15, paint: { "raster-opacity": 0.9 } },
    ],
  };
}

export default function EinpassKarte({ basemap, umriss, zentrum, fokus, onVerschieben, onMitte }: EinpassKarteProps) {
  const { t } = useTranslation();
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const zentrumRef = useRef(zentrum);
  const verschiebenRef = useRef(onVerschieben);
  const mitteRef = useRef(onMitte);

  useEffect(() => {
    zentrumRef.current = zentrum;
    verschiebenRef.current = onVerschieben;
    mitteRef.current = onMitte;
  }, [zentrum, onVerschieben, onMitte]);

  // Karte einmal anlegen
  useEffect(() => {
    if (!container.current) return;
    const start = zentrumRef.current;
    const map = new MapLibreMap({
      container: container.current,
      style: style(basemap),
      ...(start ? { center: [start.lon, start.lat] as [number, number], zoom: 18.5 } : { bounds: [-5.2, 42.3, 8.3, 51.1] }),
      maxZoom: 21,
      // Pfeiltasten verschieben den Umriss, nicht die Karte
      keyboard: false,
      attributionControl: { compact: true },
      locale: {
        "Map.Title": t("analyse.position.mapLabel"),
        "NavigationControl.ZoomIn": t("site.map.zoomInButton"),
        "NavigationControl.ZoomOut": t("site.map.zoomOutButton"),
        "AttributionControl.ToggleAttribution": t("site.map.attribution"),
      },
    });
    mapRef.current = map;
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new ScaleControl({ unit: "metric" }), "bottom-left");

    const addOverlays = () => {
      if (map.getSource("umriss")) return;
      map.addSource("umriss", { type: "geojson", data: LEER });
      map.addLayer({ id: "umriss-flaeche", type: "fill", source: "umriss", paint: { "fill-color": "#2b45b0", "fill-opacity": 0.18 } });
      map.addLayer({ id: "umriss-linie", type: "line", source: "umriss", paint: { "line-color": "#2b45b0", "line-width": 2.5 } });
    };

    // Ziehen: Versatz des Zeigers in Grad auf den Drehpunkt übertragen (Maße bleiben, der Server rechnet starr)
    let griff: { lng: number; lat: number; zentrum: LonLat } | null = null;
    const ziehen = (lng: number, lat: number) => {
      if (!griff) return;
      verschiebenRef.current({ lon: griff.zentrum.lon + lng - griff.lng, lat: griff.zentrum.lat + lat - griff.lat });
    };
    const loslassen = () => {
      griff = null;
      map.getCanvas().style.cursor = "";
    };
    const greifen = (lng: number, lat: number) => {
      const aktuell = zentrumRef.current;
      if (!aktuell) return false;
      griff = { lng, lat, zentrum: aktuell };
      map.getCanvas().style.cursor = "grabbing";
      return true;
    };

    map.on("load", addOverlays);
    map.on("style.load", addOverlays);
    map.on("mousedown", "umriss-flaeche", (event: MapLayerMouseEvent) => {
      if (greifen(event.lngLat.lng, event.lngLat.lat)) event.preventDefault();
    });
    map.on("touchstart", "umriss-flaeche", (event: MapLayerTouchEvent) => {
      if (event.points.length === 1 && greifen(event.lngLat.lng, event.lngLat.lat)) event.preventDefault();
    });
    map.on("mousemove", (event) => ziehen(event.lngLat.lng, event.lngLat.lat));
    map.on("touchmove", (event) => ziehen(event.lngLat.lng, event.lngLat.lat));
    map.on("mouseup", loslassen);
    map.on("touchend", loslassen);
    map.on("mouseenter", "umriss-flaeche", () => {
      if (!griff) map.getCanvas().style.cursor = "grab";
    });
    map.on("mouseleave", "umriss-flaeche", () => {
      if (!griff) map.getCanvas().style.cursor = "";
    });
    map.on("moveend", () => {
      const mitte = map.getCenter();
      mitteRef.current({ lon: mitte.lng, lat: mitte.lat });
    });
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // Die Karte entsteht einmal; Hintergrund, Umriss und Fokus folgen in eigenen Effekten
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const apply = () => {
      map.getSource<GeoJSONSource>("umriss")?.setData(
        umriss.length ? { type: "Feature", geometry: { type: "Polygon", coordinates: umriss }, properties: {} } : LEER,
      );
    };
    if (map.isStyleLoaded()) apply();
    else map.once("idle", apply);
  }, [umriss]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !fokus) return;
    map.flyTo({ center: [fokus.lon, fokus.lat], zoom: 18.5, speed: 1.6 });
  }, [fokus]);

  useEffect(() => {
    mapRef.current?.getSource<RasterTileSource>("base")?.setTiles([TILES[basemap]]);
  }, [basemap]);

  return (
    <div
      ref={container}
      className="w-full border bd-strong"
      style={{ height: "min(70vh, 34rem)" }}
      role="application"
      aria-label={t("analyse.position.mapLabel")}
    />
  );
}
