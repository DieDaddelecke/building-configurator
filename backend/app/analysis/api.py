"""Endpunkte des Moduls AN3 (docs/PLAN_AN3_ANALYSE.md 3.9), nur im Produkt „Emprise Analyse“.

Nur der angemeldete Architekt und nur für Projekte mit Eigentümer (`require_owned_project`, wie AN2). Das
Ändern der Annahmen kostet nichts; die Antwort ist gleich die neu gerechnete Analyse.
"""

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.analysis import service
from app.analysis.schemas import AnalysisComparisonOut, AnalysisOut, AnalysisParametersIn
from app.platform.auth.context import StaffPrincipal, require_owned_project
from app.platform.db import get_db

router = APIRouter(tags=["analysis"])


@router.get("/projects/{project_id}/analysis", response_model=AnalysisOut)
def get_analysis(
    project_id: uuid.UUID,
    staff: StaffPrincipal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> AnalysisOut:
    """Bindende Grundfläche, Vollgeschosse, Nutzfläche als Spanne und Vergleich der Zusatzdokumente."""
    return service.project_analysis(db, project_id)


@router.put("/projects/{project_id}/analysis/parameters", response_model=AnalysisOut)
def set_analysis_parameters(
    project_id: uuid.UUID,
    body: AnalysisParametersIn,
    staff: StaffPrincipal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> AnalysisOut:
    """Annahmen des Projekts ändern (E-AN3-1); jede als Bereich innerhalb ihrer Grenzen."""
    service.save_parameters(db, project_id, body, staff.actor_id)
    return service.project_analysis(db, project_id)


@router.delete("/projects/{project_id}/analysis/parameters", response_model=AnalysisOut)
def reset_analysis_parameters(
    project_id: uuid.UUID,
    staff: StaffPrincipal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> AnalysisOut:
    """Zurück auf die Vorgaben."""
    service.reset_parameters(db, project_id, staff.actor_id)
    return service.project_analysis(db, project_id)


@router.get("/projects/{project_id}/analysis/comparison", response_model=AnalysisComparisonOut)
def get_analysis_comparison(
    project_id: uuid.UUID,
    base: str = Query(default="automatic", max_length=40),
    staff: StaffPrincipal = Depends(require_owned_project),
    db: Session = Depends(get_db),
) -> AnalysisComparisonOut:
    """Zwei Stände nebeneinander (AN4, docs/PLAN_AN4_KORREKTUR.md 3.5): `automatic` – ohne und mit den
    Korrekturen des Projekts; eine Versions-ID – diese frühere Auswertung und die aktuelle, beide ohne
    Korrekturen. Die Antwort nennt auch alle angebotenen Vergleiche."""
    return service.comparison(db, project_id, base)
