"""Géorisques: Standortrisiken als Hinweise (Spez. 5.9.5, 9; geprüft am 14.09.2026).

API v1 ohne Token: `GET {base}/resultats_rapport_risque?latlon=lon,lat` und `GET {base}/rga?latlon=lon,lat`.
API v2 verlangt ein kostenloses Token (Header `Authorization: Bearer`); der Adapter sendet es, wenn
`EMPRISE_GEORISQUES_TOKEN` gesetzt ist, damit der Wechsel nur Konfiguration ist.
"""

from dataclasses import dataclass
from typing import Any, Literal

import httpx2

from app.config import Settings
from app.integrations import http
from app.integrations.http import ExternalServiceError

SERVICE = "georisques"
RiskLevel = Literal["low", "moderate", "high", "present", "unknown"]

# Schlüssel im Bericht → Risikoart in `site_risk.kind`
REPORT_KINDS = {
    "inondation": "flood",
    "remonteeNappe": "groundwater_rise",
    "risqueCotier": "coastal",
    "seisme": "seismic",
    "mouvementTerrain": "ground_movement",
    "reculTraitCote": "coastal_erosion",
    "retraitGonflementArgile": "clay_shrink_swell",
    "avalanche": "avalanche",
    "feuForet": "forest_fire",
    "eruptionVolcanique": "volcanic",
    "cyclone": "storm",
    "radon": "radon",
    "icpe": "industrial",
    "nucleaire": "nuclear",
    "canalisationsMatieresDangereuses": "hazardous_pipeline",
    "pollutionSols": "soil_pollution",
    "ruptureBarrage": "dam_failure",
    "risqueMinier": "mining",
}
RGA_LEVELS: dict[str, RiskLevel] = {"1": "low", "2": "moderate", "3": "high"}


@dataclass(frozen=True)
class RiskItem:
    kind: str
    level: RiskLevel
    scope: Literal["address", "commune"]
    label: str


def level_from_status(status: str | None) -> RiskLevel | None:
    """„Risque Existant - modéré“ → `moderate`; „Risque Inconnu“ → `unknown`; leer → None."""
    if not status:
        return None
    text = status.lower()
    if "inconnu" in text or "non connu" in text:
        return "unknown"
    if "important" in text or "fort" in text:
        return "high"
    if "modéré" in text or "modere" in text or "moyen" in text:
        return "moderate"
    if "faible" in text:
        return "low"
    return "present"


def parse_report(payload: Any) -> list[RiskItem]:
    try:
        groups = [payload["risquesNaturels"], payload["risquesTechnologiques"]]
    except (TypeError, KeyError) as exc:
        raise ExternalServiceError(SERVICE, "unexpected_payload") from exc
    items: list[RiskItem] = []
    for group in groups:
        for key, entry in group.items():
            kind = REPORT_KINDS.get(key)
            if kind is None or not entry or not entry.get("present"):
                continue
            address = level_from_status(entry.get("libelleStatutAdresse"))
            commune = level_from_status(entry.get("libelleStatutCommune"))
            if address is not None and address != "unknown":
                items.append(RiskItem(kind, address, "address", str(entry.get("libelleStatutAdresse"))))
            elif commune is not None:
                items.append(RiskItem(kind, commune, "commune", str(entry.get("libelleStatutCommune"))))
            else:
                items.append(RiskItem(kind, "unknown", "commune", str(entry.get("libelle", key))))
    return items


def parse_rga(payload: Any) -> RiskItem | None:
    """Exposition gegenüber Schrumpfen und Quellen toniger Böden an der Adresse; 0 = nicht exponiert."""
    if not isinstance(payload, dict):
        raise ExternalServiceError(SERVICE, "unexpected_payload")
    level = RGA_LEVELS.get(str(payload.get("codeExposition")))
    if level is None:
        return None
    return RiskItem("clay_shrink_swell", level, "address", str(payload.get("exposition", "")))


def site_risks(client: httpx2.Client, settings: Settings, lon: float, lat: float) -> list[RiskItem]:
    headers = (
        {"Authorization": f"Bearer {settings.georisques_token.get_secret_value()}"}
        if settings.georisques_token
        else None
    )
    params = {"latlon": f"{lon:.6f},{lat:.6f}"}
    base = settings.georisques_base_url
    report = parse_report(
        http.get_json(client, SERVICE, f"{base}/resultats_rapport_risque", params=params, headers=headers)
    )
    rga = parse_rga(http.get_json(client, SERVICE, f"{base}/rga", params=params, headers=headers))
    if rga is not None:
        # Die Karte der tonigen Böden ist genauer als der Sammelbericht
        report = [item for item in report if item.kind != "clay_shrink_swell"] + [rga]
    return sorted(report, key=lambda item: item.kind)
