"""Géoplateforme (IGN): Adresssuche und Höhendienst (Spez. 9, geprüft am 14.09.2026).

- Geokodierung: `GET {base}/geocodage/search?q=&index=address&limit=` → GeoJSON mit `x`, `y` in Lambert-93
- Höhen: `GET {base}/altimetrie/1.0/calcul/alti/rest/elevation.json?lon=a|b&lat=a|b&resource=ign_rge_alti_wld`
  → `{"elevations": [{"lon", "lat", "z"}]}`; fehlende Werte als `-99999`
- Kacheln (Frontend): `{base}/wmts?…&LAYER=GEOGRAPHICALGRIDSYSTEMS.PLANIGNV2` bzw. `ORTHOIMAGERY.ORTHOPHOTOS`
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

import httpx2

from app.config import Settings
from app.integrations import http
from app.integrations.http import ExternalServiceError

GEOCODE = "geoplateforme_geocode"
ALTIMETRY = "geoplateforme_altimetry"
NO_DATA = -99_000.0


@dataclass(frozen=True)
class AddressCandidate:
    label: str
    kind: str
    lon: float
    lat: float
    x: float
    y: float
    citycode: str
    postcode: str | None
    city: str
    score: float


def parse_search(payload: Any) -> list[AddressCandidate]:
    try:
        features = payload["features"]
    except (TypeError, KeyError) as exc:
        raise ExternalServiceError(GEOCODE, "unexpected_payload") from exc
    result: list[AddressCandidate] = []
    for feature in features:
        props = feature.get("properties") or {}
        coords = (feature.get("geometry") or {}).get("coordinates") or []
        if len(coords) != 2 or "x" not in props or "citycode" not in props:
            continue
        result.append(
            AddressCandidate(
                label=str(props.get("label", "")),
                kind=str(props.get("type", "")),
                lon=float(coords[0]),
                lat=float(coords[1]),
                x=float(props["x"]),
                y=float(props["y"]),
                citycode=str(props["citycode"]),
                postcode=props.get("postcode"),
                city=str(props.get("city", "")),
                score=round(float(props.get("score", 0.0)), 4),
            )
        )
    return result


def search_addresses(
    client: httpx2.Client, settings: Settings, query: str, *, limit: int = 5
) -> list[AddressCandidate]:
    payload = http.get_json(
        client,
        GEOCODE,
        f"{settings.geoplateforme_base_url}/geocodage/search",
        params={"q": query, "index": "address", "limit": limit},
        attempts=1,
    )
    return parse_search(payload)


def parse_elevations(payload: Any, count: int) -> list[float | None]:
    try:
        values = [item.get("z") for item in payload["elevations"]]
    except (TypeError, KeyError, AttributeError) as exc:
        raise ExternalServiceError(ALTIMETRY, "unexpected_payload") from exc
    if len(values) != count:
        raise ExternalServiceError(ALTIMETRY, "count_mismatch")
    return [float(z) if isinstance(z, int | float) and z > NO_DATA else None for z in values]


def elevations(
    client: httpx2.Client, settings: Settings, points: Sequence[tuple[float, float]]
) -> list[float | None]:
    """Höhen in m NGF für Punkte `(lon, lat)` in WGS84."""
    if not points:
        return []
    payload = http.get_json(
        client,
        ALTIMETRY,
        f"{settings.geoplateforme_base_url}/altimetrie/1.0/calcul/alti/rest/elevation.json",
        params={
            "lon": "|".join(f"{lon:.7f}" for lon, _ in points),
            "lat": "|".join(f"{lat:.7f}" for _, lat in points),
            "resource": "ign_rge_alti_wld",
            "zonly": "false",
        },
    )
    return parse_elevations(payload, len(points))
