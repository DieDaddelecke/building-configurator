"""Stand der Auswertung ohne Aufruf des Sprachmodells: Eingabe-Hash, Stand der Texterkennung, Monatskosten
und die Zeitgrenze laufender Kapitel.

Aus `extract` gelöst (REFACTORING_PLAN S11, B-68): Lesepfade wie `rules/service` und der Upload über
`rules/sources` brauchen diese Werte, sollen den Adapter zum Sprachmodell (`openai`) aber nicht laden.
"""

import hashlib
import json
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import Settings
from app.platform.db import utcnow
from app.rules.domain import PROMPT_VERSION
from app.rules.domain.extraction import TEXT_INPUT_NOTE, DocumentKind, prompt_fingerprint
from app.rules.models import RegulationChapter, RuleExtractionRun, SourceFile

RUNNING_STALE_AFTER = timedelta(minutes=70)
"""Länger als das Zeitlimit des Jobs (60 min) „läuft“ kein Kapitel; danach gilt der Lauf als abgebrochen."""


def input_hash(
    settings: Settings,
    source_sha256: str,
    chapter: RegulationChapter,
    kind: DocumentKind = "plu",
    ocr: str | None = None,
) -> str:
    """Eingabe der Aufrufe. Die Version der Schranken gehört nicht dazu: Sie ändert nur die Bewertung. Der
    Prompt hängt an der Dokumentart (PLU oder Zusatzdokument, AN3). `ocr` (`ocr_stamp`) zählt nur im
    Textmodus: Dort ändert die Texterkennung die Eingabe, im PDF-Modus sieht das Modell dieselben Seitenbilder
    (AN7, PLAN_AN7_SCAN 3.4)."""
    payload = {
        "source": source_sha256,
        "chapter": [chapter.code, chapter.first_page, chapter.last_page],
        "general": chapter.general_pages,
        "sectors": sorted(chapter.sectors),
        "model": settings.rules_model,
        "effort": settings.rules_effort,
        "runs": settings.rules_runs,
        "gap_search": [settings.rules_gap_search, settings.rules_gap_extra_pages_max],
        "prompt": [PROMPT_VERSION, prompt_fingerprint(kind)],
    }
    if settings.rules_input == "text":
        # Nur dann: Der Hash der PDF-Auswertungen bleibt, gespeicherte Teilantworten bleiben verwendbar (PU12)
        payload["input"] = ["text", hashlib.sha256(TEXT_INPUT_NOTE.encode()).hexdigest()[:16]]
        if ocr:
            payload["ocr"] = ocr
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()


def ocr_stamp(source: SourceFile | None) -> str | None:
    """Kennung der abgeschlossenen Texterkennung einer Datei; None ohne Erkennung (bisherige Kennungen
    bleiben)."""
    if source is None or source.ocr_state != "done" or source.ocr_finished_at is None:
        return None
    return source.ocr_finished_at.isoformat()


def month_cost(session: Session, now: datetime | None = None) -> float:
    current = now or utcnow()
    start = datetime(current.year, current.month, 1, tzinfo=UTC)
    total = session.execute(
        select(func.coalesce(func.sum(RuleExtractionRun.cost_usd), 0.0)).where(
            RuleExtractionRun.created_at >= start
        )
    ).scalar_one()
    return float(total)
