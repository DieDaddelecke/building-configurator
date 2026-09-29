"""Monatsbudget der Auswertung je Organisation (AN6, docs/PLAN_AN6_MANDANTEN.md 3.4).

Zusätzlich zur Grenze der Instanz (`EMPRISE_RULES_BUDGET_MONTH_USD`): Jede fremde Organisation hat ihr
eigenes Budget; die Organisation `operator` nur, wenn eines gesetzt ist. Gezählt werden die Läufe, die die
Organisation bezahlt (`rule_extraction_run.organisation_id`), im Kalendermonat in UTC.
"""

import uuid
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.platform.models import Organisation
from app.platform.organisations import MONTH_FORMAT, budget_limit, month_start, register_cost_provider
from app.platform.problems import Problem
from app.rules.models import RuleExtractionRun

ORGANISATION_BUDGET_ERROR = "organisation_budget_exceeded"
"""Fehler am Kapitel, wenn die Grenze der Organisation griff (nicht die der Instanz, `budget_exceeded`)."""


def organisation_month_cost(
    session: Session, organisation_id: uuid.UUID, now: datetime | None = None
) -> float:
    total = session.execute(
        select(func.coalesce(func.sum(RuleExtractionRun.cost_usd), 0.0)).where(
            RuleExtractionRun.organisation_id == organisation_id,
            RuleExtractionRun.created_at >= month_start(now),
        )
    ).scalar_one()
    return float(total)


def organisation_budget_left(session: Session, settings: Settings, organisation_id: uuid.UUID | None) -> bool:
    """Reicht das Budget der Organisation für einen weiteren Aufruf? Ohne Organisation oder Grenze: ja."""
    if organisation_id is None:
        return True
    org = session.get(Organisation, organisation_id)
    if org is None:
        return True
    limit = budget_limit(settings, org)
    return limit is None or organisation_month_cost(session, organisation_id) < limit


def check_organisation_budget(
    session: Session, settings: Settings, organisation_id: uuid.UUID | None
) -> None:
    """Vor einer Wahl, die eine Auswertung einplant: lieber gleich ablehnen als ein Kapitel anlegen, das
    sofort stehen bleibt (3.4)."""
    if not organisation_budget_left(session, settings, organisation_id):
        raise Problem(409, ORGANISATION_BUDGET_ERROR)


def monthly_costs(session: Session, organisation_id: uuid.UUID, since: datetime) -> dict[str, float]:
    month = func.to_char(RuleExtractionRun.created_at, MONTH_FORMAT)
    rows = session.execute(
        select(month, func.sum(RuleExtractionRun.cost_usd))
        .where(RuleExtractionRun.organisation_id == organisation_id, RuleExtractionRun.created_at >= since)
        .group_by(month)
    ).all()
    return {str(key): float(value or 0.0) for key, value in rows}


register_cost_provider(monthly_costs)
