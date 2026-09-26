"""Regelwerk-Ausschnitt für den Ende-zu-Ende-Test (G2): Planstand aus aufgezeichneten GPU-Antworten und die
aufgezeichnete Auswertung der Zone Uh, ohne Aufruf des Sprachmodells über OpenRouter.

    docker compose cp backend/tests api:/tmp/tests
    docker compose exec -T -e EMPRISE_OPENROUTER_API_KEY=e2e-ohne-aufruf -e PYTHONPATH=/tmp api \
        python -m tests.e2e_seed_rules

Der Worker kann parallel den echten Planstand desselben Dokuments laden. Beide Wege enden mit einem aktiven
Plan und dem Kapitel Uh an denselben Positionen im Kapitel-PDF; das Skript wartet auf einen laufenden Import.
"""

import tempfile
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.platform.db import get_sessionmaker
from app.rules.extract import extract_chapter
from app.rules.models import LandUsePlan, RegulationChapter
from app.rules.plan_import import DirectoryGpu, import_commune
from tests.rules_support import FakeExtractor, gpu_directory, uh_output


@contextmanager
def sessions() -> Iterator[Session]:
    session = get_sessionmaker()()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def main() -> None:
    settings = get_settings()
    with tempfile.TemporaryDirectory() as directory:
        source = DirectoryGpu(gpu_directory(Path(directory)))
        for attempt in range(30):
            with sessions() as session:
                importing = session.execute(
                    select(LandUsePlan.id).where(LandUsePlan.status == "importing")
                ).first()
                if importing is None:
                    try:
                        result = import_commune(session, source, settings, "44209")
                        print(f"plu: {result.status}")
                        break
                    except IntegrityError:
                        session.rollback()
            time.sleep(2 + attempt)
        else:
            raise SystemExit("Planstand nicht importierbar")
    with sessions() as session:
        chapter_id = session.execute(
            select(RegulationChapter.id)
            .join(LandUsePlan, LandUsePlan.id == RegulationChapter.land_use_plan_id)
            .where(LandUsePlan.status == "active", RegulationChapter.code == "Uh")
        ).scalar_one()
    outcome = extract_chapter(
        sessions, settings, chapter_id, FakeExtractor([uh_output(), uh_output()]).factory(), force=True
    )
    print(f"Uh: {outcome.status} {outcome.counts}")
    if outcome.status != "succeeded":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
