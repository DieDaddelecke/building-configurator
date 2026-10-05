"""Demohäuser für den Ende-zu-Ende-Test des Kundenwegs (HM4, HM5): Demo-Katalog veröffentlichen und
die Demo-Templates (flaches Demohaus, R+1 mit Satteldach) als veröffentlichte, freigegebene Versionen anlegen,
ohne IFC (wie `publish_template` in den Tests). Im Betrieb entsteht ein Haustyp nur über Upload, Prüfung und
Freigabe im Büro (HM3).

    docker compose cp packages/domain/seed/demo-house api:/tmp/demo-house
    docker compose cp backend/tests api:/tmp/tests
    docker compose exec -T -e PYTHONPATH=/tmp api python -m tests.e2e_seed_house /tmp/demo-house

Ein zweiter Lauf ändert nichts, solange jeder Haustyp eine aktuelle Version hat.
"""

import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.house import service
from app.house.models import HouseTemplateRecord
from app.platform.db import get_sessionmaker
from tests.house_support import publish_template

TEMPLATES = ("template.json", "template-r1.json")


def main(directory: Path) -> None:
    catalog = json.loads((directory / "catalog.json").read_text(encoding="utf-8"))
    with get_sessionmaker()() as db:
        version, done = service.import_catalog(db, catalog, source="e2e", publish=True, actor="e2e")
        print(f"Katalog {version.version} ({', '.join(done) or 'unverändert'})")
        for name in TEMPLATES:
            template = json.loads((directory / name).read_text(encoding="utf-8"))
            slug = template["slug"]
            record = db.scalar(select(HouseTemplateRecord).where(HouseTemplateRecord.slug == slug))
            if record is not None and record.current_version_id is not None:
                print(f"Haustyp {slug} vorhanden")
                continue
            published = publish_template(db, version, template, actor="e2e")
            print(f"Haustyp {slug} v{published.version} veröffentlicht und freigegeben")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Aufruf: python -m tests.e2e_seed_house VERZEICHNIS")
    main(Path(sys.argv[1]))
