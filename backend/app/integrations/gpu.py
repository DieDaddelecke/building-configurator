"""Géoportail de l'Urbanisme (GPU): Planwerke, Zonen, überlagernde Vorgaben, Planunterlagen (Spez. 9).

Geprüft am 14.09.2026:
- API Carto, Modul GPU (`apicarto.ign.fr/api/gpu`): `municipality?insee=`, `zone-urba`,
  `prescription-surf|lin|pct`, `info-surf`, `assiette-sup-s` je Geometrie (POST mit GeoJSON). Antworten sind
  FeatureCollections mit `partition` (z. B. `DU_244400503` für den PLUi Erdre et Gesvres) und `gpu_doc_id`.
- Am Rand einer Gemeinde liefern Abfragen auch Zonen des Nachbarplans; `plan_import` wählt deshalb das
  Planwerk mit der größten Fläche in der Gemeinde.
- Dokument (`www.geoportail-urbanisme.gouv.fr/api/document/{id}/details` und `/files`): Status, Datum,
  Dateiliste.
- Dateien liegen unter `data.geopf.fr/annexes/gpu/documents/{partition}/{id}/{name}`; die API leitet
  dorthin weiter.
"""

from dataclasses import dataclass
from typing import Any

import httpx2

from app.config import Settings
from app.integrations import http
from app.integrations.http import ExternalServiceError

SERVICE = "gpu"
FILES_SERVICE = "gpu_files"
DOWNLOAD_TIMEOUT_SECONDS = 120.0
OVERLAY_ENDPOINTS = (
    "prescription-surf",
    "prescription-lin",
    "prescription-pct",
    "info-surf",
    "assiette-sup-s",
)


@dataclass(frozen=True)
class Municipality:
    insee: str
    name: str
    is_rnu: bool
    geometry: dict[str, Any]
    """GeoJSON in WGS84."""


@dataclass(frozen=True)
class GpuFeature:
    endpoint: str
    properties: dict[str, Any]
    geometry: dict[str, Any]


@dataclass(frozen=True)
class GpuFile:
    name: str
    title: str
    path: str | None


@dataclass(frozen=True)
class GpuDocument:
    id: str
    partition: str
    du_type: str
    title: str
    legal_status: str | None
    effective_status: str | None
    update_date: str | None
    files: list[GpuFile]


def _features(payload: Any, endpoint: str) -> list[GpuFeature]:
    if not isinstance(payload, dict) or not isinstance(payload.get("features"), list):
        raise ExternalServiceError(SERVICE, "unexpected_payload")
    matched = payload.get("numberMatched", payload.get("totalFeatures"))
    returned = payload.get("numberReturned")
    if isinstance(matched, int) and isinstance(returned, int) and returned < matched:
        # Ohne Blätterfunktion wären Zonen unvollständig; lieber scheitern als eine Zone übersehen
        raise ExternalServiceError(SERVICE, f"truncated:{returned}/{matched}")
    return [
        GpuFeature(endpoint, dict(f.get("properties") or {}), dict(f.get("geometry") or {}))
        for f in payload["features"]
        if f.get("geometry")
    ]


def municipality(client: httpx2.Client, settings: Settings, insee: str) -> Municipality:
    payload = http.get_json(
        client, SERVICE, f"{settings.apicarto_base_url}/gpu/municipality", params={"insee": insee}
    )
    features = _features(payload, "municipality")
    if not features:
        raise ExternalServiceError(SERVICE, "municipality_not_found")
    props = features[0].properties
    return Municipality(
        insee=str(props.get("insee", insee)),
        name=str(props.get("name", "")),
        is_rnu=bool(props.get("is_rnu")),
        geometry=features[0].geometry,
    )


def features_in(
    client: httpx2.Client, settings: Settings, endpoint: str, geometry: dict[str, Any]
) -> list[GpuFeature]:
    """Objekte eines Endpunkts, die die Geometrie (GeoJSON, WGS84) schneiden."""
    payload = http.post_json(
        client, SERVICE, f"{settings.apicarto_base_url}/gpu/{endpoint}", {"geom": geometry}, timeout=60.0
    )
    return _features(payload, endpoint)


def document(client: httpx2.Client, settings: Settings, gpu_doc_id: str) -> GpuDocument:
    base = f"{settings.gpu_api_base_url}/document/{gpu_doc_id}"
    details = http.get_json(client, SERVICE, f"{base}/details")
    files = http.get_json(client, SERVICE, f"{base}/files")
    if not isinstance(details, dict) or not isinstance(files, list):
        raise ExternalServiceError(SERVICE, "unexpected_document_payload")
    return GpuDocument(
        id=str(details.get("id", gpu_doc_id)),
        partition=str(details.get("name", "")),
        du_type=str(details.get("type", "")),
        title=str(details.get("title", ""))[:300],
        legal_status=details.get("legalStatus"),
        effective_status=details.get("effectiveStatus"),
        update_date=details.get("updateDate"),
        files=[
            GpuFile(str(f.get("name", "")), str(f.get("title", "")), f.get("path"))
            for f in files
            if isinstance(f, dict) and f.get("name")
        ],
    )


def regulation_file(doc: GpuDocument) -> GpuFile | None:
    """Das règlement écrit: Titel „Règlement écrit“, sonst Dateiname mit `_reglement_` ohne „graphique“."""
    for file in doc.files:
        title = file.title.lower()
        if "règlement écrit" in title or "reglement ecrit" in title:
            return file
    candidates = [
        f
        for f in doc.files
        if "_reglement_" in f.name.lower()
        and "graph" not in f.name.lower()
        and f.name.lower().endswith(".pdf")
    ]
    return candidates[0] if len(candidates) == 1 else None


def file_url(settings: Settings, doc: GpuDocument, name: str) -> str:
    return f"{settings.gpu_files_base_url}/{doc.partition}/{doc.id}/{name}"


def download(client: httpx2.Client, settings: Settings, url: str, max_bytes: int) -> bytes:
    response = http.get(client, FILES_SERVICE, url, timeout=DOWNLOAD_TIMEOUT_SECONDS)
    if len(response.content) > max_bytes:
        raise ExternalServiceError(FILES_SERVICE, "file_too_large")
    return response.content
