"""Straßenachsen der BD TOPO (IGN) über den WFS der Géoplateforme (Spez. 5.1.4; geprüft am 14.09.2026).

`GET {base}/wfs/ows?SERVICE=WFS&VERSION=2.0.0&REQUEST=GetFeature&TYPENAMES=BDTOPO_V3:troncon_de_route`
`&OUTPUTFORMAT=application/json&SRSNAME=EPSG:2154&BBOX=x0,y0,x1,y1,urn:ogc:def:crs:EPSG::2154`
`&COUNT=5000&STARTINDEX=n&SORTBY=cleabs` – höchstens 5000 Objekte je Seite.
"""

import gzip
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import httpx2

from app.config import Settings
from app.integrations import http
from app.integrations.http import ExternalServiceError

SERVICE = "ign_bdtopo"
PAGE_SIZE = 5000
MAX_PAGES = 40
PROPERTIES = (
    "cleabs,nature,nom_collaboratif_gauche,nom_voie_ban_gauche,prive,fictif,"
    "position_par_rapport_au_sol,largeur_de_chaussee,geometrie"
)
EXCLUDED_NATURES = frozenset({"Sentier", "Escalier", "Piste cyclable", "Bac ou liaison maritime"})
"""Keine Erschließung im Sinne der Abstandsregeln zur Straße."""


@dataclass(frozen=True)
class RoadSegment:
    cleabs: str
    name: str | None
    nature: str
    private: bool
    width_m: float | None
    coords: tuple[tuple[float, float], ...]
    """Lambert-93, ohne Höhe."""


class RoadSource(Protocol):
    def fetch(self, commune: str, bbox: tuple[float, float, float, float]) -> list[RoadSegment]: ...


def parse(payload: Any) -> list[RoadSegment]:
    try:
        features = payload["features"]
    except (TypeError, KeyError) as exc:
        raise ExternalServiceError(SERVICE, "unexpected_payload") from exc
    segments: list[RoadSegment] = []
    for feature in features:
        props = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        if props.get("fictif") or geometry.get("type") != "LineString":
            continue
        if str(props.get("position_par_rapport_au_sol", "0")).startswith("-"):
            continue  # Tunnel
        nature = str(props.get("nature") or "")
        if nature in EXCLUDED_NATURES:
            continue
        coords = tuple((float(c[0]), float(c[1])) for c in geometry.get("coordinates") or [])
        if len(coords) < 2:
            continue
        name = props.get("nom_voie_ban_gauche") or props.get("nom_collaboratif_gauche")
        width = props.get("largeur_de_chaussee")
        segments.append(
            RoadSegment(
                cleabs=str(props.get("cleabs") or feature.get("id")),
                name=str(name) if name else None,
                nature=nature,
                private=bool(props.get("prive")),
                width_m=float(width) if isinstance(width, int | float) else None,
                coords=coords,
            )
        )
    return segments


class GeoplateformeRoads:
    def __init__(self, client: httpx2.Client, settings: Settings) -> None:
        self.client = client
        self.url = f"{settings.geoplateforme_base_url}/wfs/ows"

    def fetch(self, commune: str, bbox: tuple[float, float, float, float]) -> list[RoadSegment]:
        segments: list[RoadSegment] = []
        for page in range(MAX_PAGES):
            payload = http.get_json(
                self.client,
                SERVICE,
                self.url,
                params={
                    "SERVICE": "WFS",
                    "VERSION": "2.0.0",
                    "REQUEST": "GetFeature",
                    "TYPENAMES": "BDTOPO_V3:troncon_de_route",
                    "OUTPUTFORMAT": "application/json",
                    "SRSNAME": "EPSG:2154",
                    "BBOX": ",".join(f"{v:.2f}" for v in bbox) + ",urn:ogc:def:crs:EPSG::2154",
                    "PROPERTYNAME": PROPERTIES,
                    "SORTBY": "cleabs",
                    "COUNT": PAGE_SIZE,
                    "STARTINDEX": page * PAGE_SIZE,
                },
                attempts=3,
            )
            segments.extend(parse(payload))
            if len(payload.get("features") or []) < PAGE_SIZE:
                return segments
        raise ExternalServiceError(SERVICE, "too_many_pages")


class DirectoryRoads:
    """Liest `bdtopo-{insee}-troncons.json.gz` (WFS-Antwort) aus einem Ordner."""

    def __init__(self, directory: Path) -> None:
        self.directory = directory

    def fetch(self, commune: str, bbox: tuple[float, float, float, float]) -> list[RoadSegment]:
        path = self.directory / f"bdtopo-{commune}-troncons.json.gz"
        if not path.exists():
            raise ExternalServiceError(SERVICE, f"missing_file_{path.name}")
        return parse(json.loads(gzip.decompress(path.read_bytes())))
