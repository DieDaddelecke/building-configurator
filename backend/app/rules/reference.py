"""Referenzlisten laden und eine Auswertung dieser Instanz daran messen (PLAN_G2_VOLLSTAENDIGKEIT 3.10).

Bis zur gemeinsamen Verwaltung (Schritt D2) liegen Referenzlisten als Datei vor
(`app/rules/reference_seed/*.json`, Format `emprise-reference/1`); gemessen wird über die Kommandozeile
(`reference-check`).
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.rules.domain.chapters import detect_structure
from app.rules.domain.evaluation import StructureReport, evaluate_structure, report_lines
from app.rules.domain.passages import Passage
from app.rules.domain.reference import (
    FoundRule,
    Measurement,
    ReferenceEntry,
    ReferenceProblem,
    parse_entries,
)
from app.rules.models import LandUsePlan, RegulationChapter, Rule, RuleSet, RuleSetVersion, SourceFile

FORMAT = "emprise-reference/1"
SEED_DIR = Path(__file__).parent / "reference_seed"


@dataclass(frozen=True)
class ReferenceList:
    title: str
    sha256: str
    sector: str
    status: str
    note: str
    entries: list[ReferenceEntry]


def parse_list(data: dict[str, Any]) -> ReferenceList:
    if data.get("format") != FORMAT:
        raise ReferenceProblem(f"format must be {FORMAT}")
    document = data.get("document") or {}
    sha256 = str(document.get("sha256") or "")
    sector = str(data.get("sector") or "")
    if len(sha256) != 64 or not sector:
        raise ReferenceProblem("document.sha256 and sector required")
    return ReferenceList(
        title=str(document.get("title") or ""),
        sha256=sha256,
        sector=sector,
        status=str(data.get("status") or "draft"),
        note=str(data.get("note") or ""),
        entries=parse_entries(data.get("entries") or []),
    )


def load_file(path: Path) -> ReferenceList:
    return parse_list(json.loads(path.read_text(encoding="utf-8")))


def versions_for(session: Session, sha256: str, sector: str) -> list[RuleSetVersion]:
    """Regelwerksversionen des Sektors zum Dokument, älteste zuerst (jüngster aktiver Planstand hier)."""
    plan_id = session.execute(
        select(RegulationChapter.land_use_plan_id)
        .join(SourceFile, SourceFile.id == RegulationChapter.source_file_id)
        .join(LandUsePlan, LandUsePlan.id == RegulationChapter.land_use_plan_id)
        .where(
            SourceFile.sha256 == sha256,
            RegulationChapter.sectors.any(sector),  # type: ignore[arg-type]
            LandUsePlan.status == "active",
        )
        .order_by(LandUsePlan.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()
    if plan_id is None:
        return []
    rule_set_id = session.execute(
        select(RuleSet.id).where(RuleSet.land_use_plan_id == plan_id, RuleSet.zone_code == sector)
    ).scalar_one_or_none()
    if rule_set_id is None:
        return []
    return list(
        session.execute(
            select(RuleSetVersion)
            .where(RuleSetVersion.rule_set_id == rule_set_id)
            .order_by(RuleSetVersion.version)
        ).scalars()
    )


def found_rules(session: Session, version: RuleSetVersion) -> list[FoundRule]:
    return [
        FoundRule(r.kind, r.building_kind, r.status, r.reason, dict(r.params or {}), r.page, r.quote)
        for r in session.execute(select(Rule).where(Rule.rule_set_version_id == version.id)).scalars()
    ]


LABELS = {
    "hit": "richtig",
    "wrong_value": "FALSCH",
    "named_gap": "offen (benannt)",
    "dismissed": "verworfen",
    "silent_gap": "FEHLT STILL",
}


def passages(version: RuleSetVersion) -> tuple[list[Passage], list[Passage]]:
    """Offene und als nicht einschlägig eingestufte Stellen der Version (ab der Nachsuche)."""
    return (
        [Passage(p["page"], p["text"]) for p in version.open_passages or []],
        [Passage(p["page"], p["text"]) for p in version.out_of_scope_passages or []],
    )


def report(reference: ReferenceList, version: RuleSetVersion, measurement: Measurement) -> str:
    counts = measurement.counts
    coverage = version.coverage or {}
    lines = [
        f"Version {version.version} · {version.model or version.origin} · "
        f"{version.created_at:%d.%m.%Y %H:%M}",
        f"  richtig {counts['hit']} · falsch {counts['wrong_value']} · offen benannt {counts['named_gap']} · "
        f"verworfen {counts['dismissed']} · still fehlend {counts['silent_gap']} · von {counts['entries']} "
        f"(Trefferquote {measurement.recall:.0%}); zusätzlich {counts['extra']} Regeln, "
        f"{counts['extra_hints']} Hinweise",
    ]
    if "passages_total" in coverage:
        lines.append(
            f"  Abdeckung: {coverage.get('passages_assigned', 0)} von {coverage['passages_total']} Stellen "
            f"zugeordnet, {coverage.get('passages_open', 0)} offen, "
            f"{coverage.get('passages_out_of_scope', 0)} nicht einschlägig"
        )
    for result in measurement.results:
        if result.outcome == "hit":
            continue
        entry = result.entry
        found = result.found
        got = f" – gefunden: {found.status} {json.dumps(found.params, ensure_ascii=False)}" if found else ""
        detail = f" [{result.detail}]" if result.detail else ""
        lines.append(
            f"  {LABELS[result.outcome]:<16} {entry.kind}/{entry.building_kind} S. {entry.page}{detail}{got}"
        )
    for extra in measurement.extra:
        lines.append(
            f"  {'zusätzlich':<16} {extra.kind}/{extra.building_kind} S. {extra.page} {extra.status} "
            f"{json.dumps(extra.params, ensure_ascii=False)}"
        )
    return "\n".join(lines)


def evaluate_document(page_texts: dict[int, str], references: list[ReferenceList]) -> list[StructureReport]:
    """Gliederung erkennen und die Referenzlisten daran messen, ohne Datenbank und ohne Modell (S2)."""
    structure = detect_structure(page_texts)
    return [evaluate_structure(page_texts, structure, ref.sector, ref.entries) for ref in references]


def evaluation_report(page_texts: dict[int, str], references: list[ReferenceList]) -> str:
    structure = detect_structure(page_texts)
    lines = [
        f"Gliederung: {structure.method}, {len(structure.chapters)} Zonenkapitel ("
        + ", ".join(f"{c.code} {c.first_page}–{c.last_page}" for c in structure.chapters[:12])
        + (" …" if len(structure.chapters) > 12 else "")
        + ")"
    ]
    for ref in references:
        lines += report_lines(evaluate_structure(page_texts, structure, ref.sector, ref.entries))
    return "\n".join(lines)
