"""Prüfsumme über den Inhalt der Eingaben des Baurahmens (Plan G3 4.2, V 3.3), ohne Datenbank.

Steckbrief, Analyse und Prüfstempel der Übergabe hängen daran (REFACTORING_PLAN S16).
"""

import hashlib
import json
from typing import Any

import shapely
from shapely.geometry.base import BaseGeometry

from app.envelope.domain import ENGINE_VERSION
from app.envelope.domain.inputs import EnvelopeInput


def fingerprint(data: EnvelopeInput) -> str:
    """Prüfsumme über den Inhalt aller Eingaben (Plan G3 4.2).

    Nicht über Revisions- und Versionsnummern: Gelände trifft ohne neue Revision ein, Projektkorrekturen
    und der Wechsel auf den Rückfall-Planstand erzeugen keine neue Regelwerksversion.
    """
    return "sha256:" + _digest(_fingerprint_payload(data))


def fingerprint_parts(data: EnvelopeInput) -> dict[str, str]:
    """Dieselbe Prüfsumme in zwei Teilen: Grundstück (Umriss, Kanten, Gelände) und Regeln (Zonen, Vorgaben).
    Der Prüfstempel der Übergabe (V 3.3) benennt damit, was sich geändert hat."""
    payload = _fingerprint_payload(data)
    rules = {key: payload[key] for key in ("zones", "constraints", "rules_status")}
    # 12 Zeichen wie die übrigen Teile des Stempels (`configuration/review.py`)
    return {"site": _digest(payload["site"])[:12], "rules": _digest(rules)[:12]}


def _digest(payload: object) -> str:
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(raw.encode()).hexdigest()


def _fingerprint_payload(data: EnvelopeInput) -> dict[str, Any]:
    return {
        "engine": ENGINE_VERSION,
        "site": {
            "outline": _geometry_key(data.site.polygon),
            "edges": [
                [
                    e.seq,
                    e.ring,
                    e.kind,
                    e.classification_source,
                    round(e.confidence, 3),
                    _geometry_key(e.geometry),
                ]
                for e in data.site.edges
            ],
            "terrain": [
                data.site.terrain.status,
                data.site.terrain.slope_percent,
                data.site.terrain.reference_altitude_ngf,
            ],
            "warnings": sorted(data.site.warnings),
            "customer_edges_unconfirmed": data.site.customer_edges_unconfirmed,
        },
        "zones": [
            {
                "code": z.code,
                "status": z.status,
                "reason": z.reason,
                "polygon": _geometry_key(z.polygon),
                "rules": sorted(
                    [r.kind, r.building_kind, r.status, str(r.reason), json.dumps(r.params, sort_keys=True)]
                    for r in [*z.rules, *z.hints]
                ),
            }
            for z in data.zones
        ],
        "constraints": sorted(
            [c.category, c.type_code or "", c.label, _geometry_key(c.geometry)] for c in data.constraints
        ),
        "rules_status": [data.rules_status, data.rules_reason, round(data.uncovered_share, 4)],
    }


def _geometry_key(geometry: BaseGeometry) -> str:
    """Geometrie auf Millimeter gerundet als Hex-WKB: gleiche Fläche, gleiche Prüfsumme."""
    if geometry.is_empty:
        return ""
    return str(shapely.to_wkb(shapely.set_precision(geometry, 0.001), hex=True))
