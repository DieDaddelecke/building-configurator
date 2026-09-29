"""Endpunkte des Moduls AN3 (docs/PLAN_AN3_ANALYSE.md 3.9), nur im Produkt „Emprise Analyse“.

Nur Architekt oder API-Schlüssel der Organisation des Projekts (`require_owned_project`, wie AN2; AN6). Das
Ändern der Annahmen kostet nichts; die Antwort ist gleich die neu gerechnete Analyse.
"""

import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query, Request, Response
from sqlalchemy.orm import Session

from app.analysis import export, service
from app.analysis.report import file_stem
from app.analysis.schemas import (
    AnalysisComparisonOut,
    AnalysisOut,
    AnalysisParametersIn,
    ReportIn,
    ReportLocale,
    ReportOut,
)
from app.config import get_settings
from app.platform import projects, rate_limit
from app.platform.auth.context import Principal, require_owned_project
from app.platform.db import get_db, utcnow

router = APIRouter(tags=["analysis"])


@router.get("/projects/{project_id}/analysis", response_model=AnalysisOut)
def get_analysis(
    project_id: uuid.UUID,
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> AnalysisOut:
    """Bindende Grundfläche, Vollgeschosse, Nutzfläche als Spanne und Vergleich der Zusatzdokumente."""
    return service.project_analysis(db, project_id)


@router.put("/projects/{project_id}/analysis/parameters", response_model=AnalysisOut)
def set_analysis_parameters(
    project_id: uuid.UUID,
    body: AnalysisParametersIn,
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> AnalysisOut:
    """Annahmen des Projekts ändern (E-AN3-1); jede als Bereich innerhalb ihrer Grenzen."""
    service.save_parameters(db, project_id, body, staff.actor_id)
    return service.project_analysis(db, project_id)


@router.delete("/projects/{project_id}/analysis/parameters", response_model=AnalysisOut)
def reset_analysis_parameters(
    project_id: uuid.UUID,
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> AnalysisOut:
    """Zurück auf die Vorgaben."""
    service.reset_parameters(db, project_id, staff.actor_id)
    return service.project_analysis(db, project_id)


@router.get("/projects/{project_id}/analysis/comparison", response_model=AnalysisComparisonOut)
def get_analysis_comparison(
    project_id: uuid.UUID,
    base: str = Query(default="automatic", max_length=40),
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> AnalysisComparisonOut:
    """Zwei Stände nebeneinander (AN4, docs/PLAN_AN4_KORREKTUR.md 3.5): `automatic` – ohne und mit den
    Korrekturen des Projekts; eine Versions-ID – diese frühere Auswertung und die aktuelle, beide ohne
    Korrekturen. Die Antwort nennt auch alle angebotenen Vergleiche."""
    return service.comparison(db, project_id, base)


# ---------------------------------------------------------------------------
# Ausgabe (AN5, docs/PLAN_AN5_AUSGABE.md 3.4–3.6)
# ---------------------------------------------------------------------------


@router.get("/projects/{project_id}/analysis/export/dxf")
def export_dxf(
    project_id: uuid.UUID,
    variant: Literal["local", "L93"] = Query(default="local"),
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> Response:
    """Lageplan mit Baurahmen, Bauband, Vorgaben, Schnitten und Gabarit (Höhenlinien und Körper) als DXF.
    `L93` nur mit Lage (409 `export_not_georeferenced`); Z dann in m NGF, wenn das Gelände bekannt ist."""
    content, name = export.dxf_file(export.load(db, project_id), variant)
    return Response(
        content=content,
        media_type="application/dxf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.get("/projects/{project_id}/analysis/export/geojson")
def export_geojson(
    project_id: uuid.UUID,
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> Response:
    """Dieselben Ebenen als FeatureCollection in WGS84 (RFC 7946); nur mit Lage (E-AN5-6)."""
    source = export.load(db, project_id)
    collection = export.geojson(db, source)
    name = f"{file_stem(source.label)}_{utcnow():%Y-%m-%d}.geojson"
    return Response(
        content=json.dumps(collection, ensure_ascii=False),
        media_type="application/geo+json",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


@router.post("/projects/{project_id}/analysis/report", response_model=ReportOut)
def create_report(
    request: Request,
    response: Response,
    project_id: uuid.UUID,
    body: ReportIn,
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> ReportOut:
    """Bericht anfordern. Liegt er für diesen Stand und diese Sprache vor, kommt er sofort (`ready`)."""
    rate_limit.check(request, "analysis_report", get_settings().envelope_sheet_limit_per_hour, 3600)
    result = service.request_report(db, project_id, body.locale, staff.actor_id)
    if result.status == "pending":
        response.status_code = 202
    return result


@router.get("/projects/{project_id}/analysis/report")
def download_report(
    project_id: uuid.UUID,
    locale: ReportLocale = Query(default="fr"),
    staff: Principal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> Response:
    """Fertiger Bericht zum aktuellen Stand; sonst 409 `report_not_ready` mit der Prüfsumme."""
    content, name = service.report_file(db, project_id, locale)
    return Response(
        content=content,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{name}"'},
    )


projects.register_storage_keys(service.report_storage_keys)
