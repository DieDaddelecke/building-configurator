"""Messung ohne Modell: Gliederung und Erreichbarkeit der Sollwerte (BESTANDSAUFNAHME_PLU_PIPELINE S2).

Für jeden Eintrag einer Referenzliste wird geprüft, was die deterministischen Stufen leisten, bevor ein
Modell etwas liest:

1. **Zitat belegt:** Das Soll-Zitat steht auf der Textschicht (`text.verify_quote`, auch über den
   Seitenwechsel).
2. **Ebene:** Zu welchem Teil des Dokuments die Fundstelle gehört – Zonenkapitel des Sektors, Regeln für alle
   Zonen, Begriffe, Anwendungsregeln, ein anderes Zonenkapitel oder nichts davon.
3. **Erreichbar:** Die Gliederung ordnet die Stelle dem Sektor zu – im Zonenkapitel oder in den Teilen für
   alle Zonen, ohne dass der Absatz auf andere Zonen beschränkt ist (`chapters.zone_scope`).
4. **Im Modellkontext:** Die Seite gehört zu den Seiten, die heute mit dem Kapitel an das Modell gehen
   (Kapitel und `general_pages`).

Ziel: Jeder Eintrag ist belegt und erreichbar. Eine fehlende Variante ist ein Fehler wie jeder andere
Eintrag (S9b): gezählt wird je Eintrag, nicht je Regelart.
"""

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from app.rules.domain.chapters import Chapter, Structure, chapter_for_zone, scope_applies, zone_scope
from app.rules.domain.passages import split_passages
from app.rules.domain.reference import ReferenceEntry
from app.rules.domain.text import QuoteCheck, quotes_overlap, running_lines, verify_quote

Layer = str
"""`zone`, `common`, `definitions`, `application`, `other_zone`, `other` oder `unknown` (ohne Seite)."""
REACHABLE_LAYERS = frozenset({"zone", "common", "definitions", "application"})


@dataclass(frozen=True)
class EntryReach:
    entry: ReferenceEntry
    quote: QuoteCheck
    layer: Layer
    scope: frozenset[str]
    """Zonen, auf die der Absatz mit dem Zitat beschränkt ist; leer: alle."""
    reachable: bool
    in_model: bool

    @property
    def problem(self) -> str | None:
        if not self.quote.verified:
            return f"quote:{self.quote.reason}"
        if self.layer not in REACHABLE_LAYERS:
            return f"layer:{self.layer}"
        if not self.reachable:
            return "scope:" + ",".join(sorted(self.scope))
        return None


@dataclass(frozen=True)
class StructureReport:
    sector: str
    chapter: Chapter | None
    general_pages: list[int]
    common_pages: list[int]
    results: list[EntryReach] = field(default_factory=list)

    @property
    def counts(self) -> dict[str, int]:
        layers = Counter(r.layer for r in self.results)
        return {
            "entries": len(self.results),
            "quote_verified": sum(r.quote.verified for r in self.results),
            "reachable": sum(r.reachable for r in self.results),
            "in_model": sum(r.in_model for r in self.results),
        } | {f"layer_{name}": count for name, count in sorted(layers.items())}


def _layer(page: int | None, sector_chapter: Chapter | None, structure: Structure) -> Layer:
    if page is None:
        return "unknown"
    if sector_chapter is not None and sector_chapter.first_page <= page <= sector_chapter.last_page:
        return "zone"
    if page in structure.common_pages:
        return "common"
    for part in structure.parts:
        if part.first_page <= page <= part.last_page and part.kind in ("definitions", "application"):
            return part.kind
    if any(c.first_page <= page <= c.last_page for c in structure.chapters):
        return "other_zone"
    return "other"


def _scope(
    entry: ReferenceEntry, page: int, page_texts: Mapping[int, str], skip: set[str], codes: Sequence[str]
) -> frozenset[str]:
    """Beschränkung des Absatzes, in dem das Zitat steht (Seite und Folgeseite bei Seitenwechsel)."""
    for number in (page, page + 1):
        for passage in split_passages(number, page_texts.get(number, ""), skip):
            if quotes_overlap(entry.quote, passage.text):
                return zone_scope(passage.text, codes)
    return frozenset()


def evaluate_structure(
    page_texts: Mapping[int, str], structure: Structure, sector: str, entries: Sequence[ReferenceEntry]
) -> StructureReport:
    """Erreichbarkeit der Einträge eines Sektors in der erkannten Gliederung."""
    pages = dict(page_texts)
    chapter = chapter_for_zone(sector, structure.chapters)
    model_pages = set(structure.general_pages) | (set(chapter.pages) if chapter else set())
    skip = running_lines(pages, sorted(pages))
    codes = [c.code for c in structure.chapters]
    results: list[EntryReach] = []
    for entry in entries:
        check = (
            verify_quote(entry.quote, pages, entry.page)
            if entry.page is not None
            else QuoteCheck(False, None, 0.0, "page_unknown")
        )
        page = check.page if check.verified else entry.page
        layer = _layer(page, chapter, structure)
        scope = (
            _scope(entry, page, pages, skip, codes) if page is not None and layer != "zone" else frozenset()
        )
        reachable = check.verified and layer in REACHABLE_LAYERS and scope_applies(scope, sector)
        in_model = page is not None and (page in model_pages or (check.verified and page + 1 in model_pages))
        results.append(EntryReach(entry, check, layer, scope, reachable, in_model))
    return StructureReport(
        sector=sector,
        chapter=chapter,
        general_pages=list(structure.general_pages),
        common_pages=list(structure.common_pages),
        results=results,
    )


def _ranges(pages: Sequence[int]) -> str:
    if not pages:
        return "–"
    spans: list[tuple[int, int]] = []
    for page in sorted(pages):
        if spans and page == spans[-1][1] + 1:
            spans[-1] = (spans[-1][0], page)
        else:
            spans.append((page, page))
    return ", ".join(str(a) if a == b else f"{a}–{b}" for a, b in spans)


def report_lines(report: StructureReport) -> list[str]:
    counts = report.counts
    chapter = report.chapter
    lines = [
        f"Sektor {report.sector}: Kapitel "
        + (f"{chapter.code} S. {chapter.first_page}–{chapter.last_page}" if chapter else "NICHT ERKANNT"),
        f"  allgemeine Seiten an das Modell: {_ranges(report.general_pages)}",
        f"  Regeln für alle Zonen: {_ranges(report.common_pages)}",
        f"  Einträge {counts['entries']} · Zitat belegt {counts['quote_verified']} · erreichbar "
        f"{counts['reachable']} · im Modellkontext {counts['in_model']}",
        "  Ebenen: "
        + " · ".join(f"{k.removeprefix('layer_')} {v}" for k, v in counts.items() if k.startswith("layer_")),
    ]
    for result in report.results:
        problem = result.problem
        missing_context = result.reachable and not result.in_model
        if problem is None and not missing_context:
            continue
        label = problem or "nicht im Modellkontext"
        lines.append(f"  {label:<32} {result.entry.kind} S. {result.entry.page}: {result.entry.quote[:70]}")
    return lines
