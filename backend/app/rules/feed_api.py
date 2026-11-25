"""Regeldienst für andere Dienste, z. B. die Massenstudie (docs/PLAN_REGELDIENST.md 4, ADR-12).

Zugang nur mit Service-Token (`Authorization: Bearer emps_…`, Recht `rules:read`); keine Sitzung, kein
Feature-Flag, kein Projekt. Beide Routen lesen nur und lösen nie eine Auswertung aus. Format für die
Gegenseite: docs/API_REGELDIENST.md.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from sqlalchemy.orm import Session

from app.platform.auth.context import ServicePrincipal, require_service_token
from app.platform.db import get_db
from app.rules import feed
from app.rules.domain.kinds import RuleScope
from app.rules.schemas import FeedCommuneOut, FeedZoneRulesOut

router = APIRouter(prefix="/service/rules", tags=["rules-service"])

RulesReader = Depends(require_service_token("rules:read"))
Insee = Annotated[str, Path(pattern=r"^[0-9][0-9AB][0-9]{3}$", description="INSEE-Code der Gemeinde")]


@router.get("/communes/{insee}", response_model=FeedCommuneOut)
def get_commune(
    insee: Insee, _: ServicePrincipal = RulesReader, db: Session = Depends(get_db)
) -> FeedCommuneOut:
    """Planstand der Gemeinde und ihre Zonen mit dem Stand je Umfang (`house`, `collectif`)."""
    return feed.commune_overview(db, insee)


@router.get("/communes/{insee}/zones/{zone_code}", response_model=FeedZoneRulesOut)
def get_zone_rules(
    insee: Insee,
    zone_code: Annotated[str, Path(max_length=20)],
    scope: Annotated[RuleScope, Query(description="Umfang der Auswertung")] = "collectif",
    _: ServicePrincipal = RulesReader,
    db: Session = Depends(get_db),
) -> FeedZoneRulesOut:
    """Regeln der Zone im Umfang mit Zitat, Seite und Link auf das PDF; Format `emprise-rules/1`."""
    return feed.zone_rules(db, insee, zone_code, scope)
