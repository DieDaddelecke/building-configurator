/** Kacheln der Géoplateforme für die Karten (Plan 3.3, AN5). Ohne MapLibre, damit Seiten die Auswahl zeigen
 *  können, ohne die Kartenbibliothek zu laden. */

const WMTS = "https://data.geopf.fr/wmts?SERVICE=WMTS&REQUEST=GetTile&VERSION=1.0.0";

export const TILES = {
  plan: `${WMTS}&STYLE=normal&TILEMATRIXSET=PM&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2&FORMAT=image/png&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}`,
  photo: `${WMTS}&STYLE=normal&TILEMATRIXSET=PM&LAYER=ORTHOIMAGERY.ORTHOPHOTOS&FORMAT=image/jpeg&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}`,
};

/** Parcellaire Express (PCI) als Rasterebene: Parzellen, Nummern und Gebäude ohne eigenen Katasterimport
 *  (PLAN_AN5_AUSGABE 2, am 28.09.2026 geprüft). Kachelschema bis Zoomstufe 19. */
export const CADASTRE_TILES = `${WMTS}&STYLE=PCI%20vecteur&TILEMATRIXSET=PM_0_19&LAYER=CADASTRALPARCELS.PARCELLAIRE_EXPRESS&FORMAT=image/png&TILEMATRIX={z}&TILEROW={y}&TILECOL={x}`;

export const ATTRIBUTION = "© IGN – Géoplateforme · Cadastre : DGFiP / Etalab";

export type Basemap = keyof typeof TILES;
