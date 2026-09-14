"""Kataster-Massendaten von Etalab je Gemeinde (Plan 3.3; geprüft am 14.09.2026).

`{base}/latest/geojson/communes/{dep}/{insee}/cadastre-{insee}-{dataset}.json.gz` leitet auf den
aktuellen Stand weiter (`…/etalab-cadastre/2026-06-01/…`); Stände erscheinen etwa vierteljährlich.
Datensätze: `parcelles` (Eigenschaften `id` = IDU, `commune`, `prefixe`, `section`, `numero`,
`contenance`, `updated`), `batiments` (`type` 01 = massiv, 02 = leicht), `communes` (`id`, `nom`).
Koordinaten WGS84. Eigentümer sind nicht enthalten.
"""

import gzip
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal, Protocol

import httpx2

from app.config import Settings
from app.integrations.http import ExternalServiceError

SERVICE = "etalab_cadastre"
DOWNLOAD_TIMEOUT_SECONDS = 300.0
Dataset = Literal["parcelles", "batiments", "communes"]
_RELEASE = re.compile(r"/etalab-cadastre/(\d{4}-\d{2}-\d{2})/")


@dataclass(frozen=True)
class Download:
    commune: str
    dataset: Dataset
    release: str
    sha256: str
    features: list[dict[str, Any]]


class CadastreSource(Protocol):
    def latest_release(self, commune: str) -> str: ...

    def fetch(self, commune: str, dataset: Dataset, release: str) -> Download: ...


def department(commune: str) -> str:
    return commune[:3] if commune.startswith("97") else commune[:2]


def _decode(commune: str, dataset: Dataset, release: str, raw: bytes) -> Download:
    try:
        data = json.loads(gzip.decompress(raw))
        features = data["features"]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ExternalServiceError(SERVICE, f"invalid_{dataset}") from exc
    return Download(commune, dataset, release, hashlib.sha256(raw).hexdigest(), features)


class EtalabCadastre:
    def __init__(self, client: httpx2.Client, settings: Settings) -> None:
        self.client = client
        self.base = settings.cadastre_base_url.rstrip("/")

    def _url(self, release: str, commune: str, dataset: Dataset) -> str:
        return (
            f"{self.base}/{release}/geojson/communes/{department(commune)}/{commune}/"
            f"cadastre-{commune}-{dataset}.json.gz"
        )

    def latest_release(self, commune: str) -> str:
        try:
            response = self.client.head(self._url("latest", commune, "communes"), follow_redirects=False)
        except httpx2.HTTPError as exc:
            raise ExternalServiceError(SERVICE, f"transport:{type(exc).__name__}") from exc
        match = _RELEASE.search(response.headers.get("location", ""))
        if response.status_code not in (301, 302, 303, 307, 308) or not match:
            raise ExternalServiceError(SERVICE, f"no_release_redirect_http_{response.status_code}")
        return match.group(1)

    def fetch(self, commune: str, dataset: Dataset, release: str) -> Download:
        try:
            response = self.client.get(self._url(release, commune, dataset), timeout=DOWNLOAD_TIMEOUT_SECONDS)
        except httpx2.HTTPError as exc:
            raise ExternalServiceError(SERVICE, f"transport:{type(exc).__name__}") from exc
        if response.status_code != 200:
            raise ExternalServiceError(SERVICE, f"http_{response.status_code}")
        return _decode(commune, dataset, release, response.content)


class DirectoryCadastre:
    """Liest `cadastre-{insee}-{dataset}.json.gz` aus einem Ordner (Tests, Betrieb ohne Internet)."""

    def __init__(self, directory: Path, release: str) -> None:
        self.directory = directory
        self.release = release

    def latest_release(self, commune: str) -> str:
        return self.release

    def fetch(self, commune: str, dataset: Dataset, release: str) -> Download:
        path = self.directory / f"cadastre-{commune}-{dataset}.json.gz"
        if not path.exists():
            raise ExternalServiceError(SERVICE, f"missing_file_{path.name}")
        return _decode(commune, dataset, release, path.read_bytes())
