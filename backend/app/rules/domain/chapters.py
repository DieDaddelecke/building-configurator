"""Zonenkapitel und allgemeine Bestimmungen im règlement écrit finden (Spez. 5.2.3 Schritt 2, Plan 3.4).

Seitennummern sind 1-basiert und beziehen sich auf das PDF, nicht auf die gedruckte Seitenzahl.
Erster Weg ist das Inhaltsverzeichnis (Titel und gedruckte Seite), zweiter die Überschriften der Seiten.
"""

import re
import unicodedata
from dataclasses import dataclass

TOC_MAX_PAGES = 8
HEADING_LINES = 12
OFFSET_SEARCH = range(-3, 11)
GENERAL_MAX_PAGES = 40
CHAPTER_MAX_PAGES = 150
"""Kapitel und allgemeine Seiten zusammen; längere Kapitel werden nicht ausgewertet (`chapter_too_long`)."""

_TOC_LINE = re.compile(r"^(?P<title>\S.*?)\s*(?:\.{2,}|…+|\s{2,}|\s(?=\d+\s*$))\s*(?P<page>\d{1,4})\s*$")
_ZONE_TITLE = re.compile(r"\bZONES?\s+(?P<code>.+)$", re.IGNORECASE)
_ZONE_CODE = re.compile(r"^\d?[A-Z]{1,4}[a-z0-9]{0,5}$")
_HEADING = re.compile(
    r"^(?:CHAPITRE\s*\d+\s*[:\-–]?\s*)?(?:DISPOSITIONS\s+APPLICABLES\s+(?:A|À)\s+)?(?:LA\s+)?ZONES?\s+(?P<code>.+)$",
    re.IGNORECASE,
)

_SUB_ENTRY = re.compile(
    r"^\s*(?:ARTICLE|ART\.|SECTION|SOUS[-\s]SECTION|PARAGRAPHE|§|\d+\.\d+)", re.IGNORECASE
)
"""Einträge unterhalb eines Kapitels im Inhaltsverzeichnis („Article Ub 7“, „Section 2“, „2.3“)."""

GENERAL_KEYWORDS: tuple[tuple[str, int], ...] = (
    ("DEFINITION", 0),
    ("LEXIQUE", 0),
    ("GLOSSAIRE", 0),
    ("MODEDEMPLOI", 1),
    ("DISPOSITIONSGENERALES", 1),
    ("DISPOSITIONSCOMMUNES", 1),
    ("CHAMPDAPPLICATION", 1),
    ("DIVISIONDUTERRITOIRE", 2),
    ("VOIES", 2),
    ("STATIONNEMENT", 3),
    ("TRAMEVERTE", 3),
)
"""Abschnitte, die für alle Zonen gelten, mit Rang: Begriffsbestimmungen zuerst (Messweise von Höhen und
Abständen), dann Anwendungsregeln, dann Querbezüge aus den Zonenkapiteln."""


@dataclass(frozen=True)
class TocEntry:
    title: str
    printed_page: int


@dataclass(frozen=True)
class Chapter:
    code: str
    title: str
    first_page: int
    last_page: int

    @property
    def pages(self) -> list[int]:
        return list(range(self.first_page, self.last_page + 1))


@dataclass(frozen=True)
class Structure:
    chapters: list[Chapter]
    general_pages: list[int]
    method: str
    """`toc` oder `headings`."""


def _plain(value: str) -> str:
    """Großbuchstaben ohne Akzente, Leerraum und Satzzeichen: für Stichwortvergleiche."""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(c for c in text if not unicodedata.combining(c)).upper()
    return re.sub(r"[^0-9A-Z]", "", text)


def _code(raw: str) -> str | None:
    """„U b“ → „Ub“; „1AUz“ bleibt. Liefert None, wenn der Rest kein Zonenkürzel ist."""
    candidate = re.sub(r"\s+", "", raw.strip().rstrip(".:;-–"))
    candidate = candidate.split("(")[0]
    return candidate if _ZONE_CODE.match(candidate) else None


def parse_toc(pages: dict[int, str]) -> list[TocEntry]:
    last_page = max(pages, default=0)
    entries: list[TocEntry] = []
    for number in sorted(pages)[:TOC_MAX_PAGES]:
        pending_title: str | None = None
        for raw_line in pages[number].splitlines():
            line = raw_line.strip()
            if not line:
                continue
            match = _TOC_LINE.match(line)
            if match and len(match.group("title").strip(" .…")) >= 4:
                entries.append(TocEntry(match.group("title").strip(" .…"), int(match.group("page"))))
                pending_title = None
            elif match and pending_title:
                # Zweizeiliger Eintrag: Titel in der Zeile davor, hier nur Füllpunkte und Seitenzahl
                entries.append(TocEntry(pending_title, int(match.group("page"))))
                pending_title = None
            elif line.isdigit() and pending_title:
                entries.append(TocEntry(pending_title, int(line)))
                pending_title = None
            else:
                pending_title = line if len(line) >= 10 else None
    # Verzeichnisse sind aufsteigend; Kopfzeilen mit Seitenzahl werden so aussortiert
    result: list[TocEntry] = []
    for entry in entries:
        if not 1 <= entry.printed_page <= last_page:
            continue
        if result and entry.printed_page < result[-1].printed_page:
            continue
        result.append(entry)
    return result if sum(1 for e in result if _zone_code_of_title(e.title)) >= 1 else []


def _zone_code_of_title(title: str) -> str | None:
    match = _ZONE_TITLE.search(title)
    return _code(match.group("code")) if match else None


def _heading_lines(text: str) -> list[str]:
    return [re.sub(r"\s+", " ", line).strip() for line in text.splitlines() if line.strip()][:HEADING_LINES]


def _page_has_heading(text: str, code: str) -> bool:
    for line in _heading_lines(text):
        match = _HEADING.match(line)
        if match and _code(match.group("code")) == code:
            return True
    return False


def _offset(pages: dict[int, str], entries: list[TocEntry], last_page: int) -> int | None:
    for entry in entries:
        code = _zone_code_of_title(entry.title)
        if code is None:
            continue
        for delta in OFFSET_SEARCH:
            page = entry.printed_page + delta
            if 1 <= page <= last_page and _page_has_heading(pages.get(page, ""), code):
                return delta
    return None


def _general_pages(ranges: list[tuple[str, int, int]]) -> list[int]:
    ranked: list[tuple[int, int, int]] = []
    for title, first, last in ranges:
        plain = _plain(title)
        ranks = [rank for keyword, rank in GENERAL_KEYWORDS if keyword in plain]
        if ranks and not _zone_code_of_title(title):
            ranked.append((min(ranks), first, last))
    selected: set[int] = set()
    for _rank, first, last in sorted(ranked):
        span = set(range(first, last + 1))
        if len(selected | span) > GENERAL_MAX_PAGES:
            continue
        selected |= span
    return sorted(selected)


def detect_structure(pages: dict[int, str]) -> Structure:
    """Zonenkapitel und allgemeine Seiten bestimmen. Leere Liste von Kapiteln, wenn nichts erkennbar ist."""
    if not pages:
        return Structure([], [], "none")
    last_page = max(pages)
    entries = parse_toc(pages)
    offset = _offset(pages, entries, last_page) if entries else None
    if entries and offset is not None:
        starts = sorted(
            {(e.printed_page + offset, e.title) for e in entries if 1 <= e.printed_page + offset <= last_page}
        )
        ranges: list[tuple[str, int, int]] = []
        chapters: list[Chapter] = []
        for index, (first, title) in enumerate(starts):
            following = [p for p, _ in starts[index + 1 :] if p > first]
            end = (following[0] - 1) if following else last_page
            ranges.append((title, first, end))
            code = _zone_code_of_title(title)
            if code and not any(c.code == code for c in chapters):
                # Artikel und Abschnitte im Verzeichnis beenden das Zonenkapitel nicht
                chapter_end = [p for p, t in starts[index + 1 :] if p > first and not _SUB_ENTRY.match(t)]
                chapters.append(
                    Chapter(code, title, first, (chapter_end[0] - 1) if chapter_end else last_page)
                )
        if chapters:
            return Structure(chapters, _general_pages(ranges), "toc")
    return _structure_from_headings(pages, last_page)


def _structure_from_headings(pages: dict[int, str], last_page: int) -> Structure:
    starts: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for number in sorted(pages):
        for line in _heading_lines(pages[number]):
            match = _HEADING.match(line)
            code = _code(match.group("code")) if match else None
            if code and code not in seen:
                seen.add(code)
                starts.append((number, code, line))
                break
    chapters = [
        Chapter(code, title, first, (starts[i + 1][0] - 1) if i + 1 < len(starts) else last_page)
        for i, (first, code, title) in enumerate(starts)
    ]
    chapters = [c for c in chapters if c.last_page >= c.first_page]
    general = list(range(1, min(chapters[0].first_page, GENERAL_MAX_PAGES + 1))) if chapters else []
    return Structure(chapters, general, "headings" if chapters else "none")


SECTOR_SUGGESTIONS_MAX = 12
SECTOR_CONTEXT_CHARS = 60
_SECTOR_CONTEXT = re.compile(r"\b(?:sous-secteurs?|secteurs?|zones?|indices?)\b", re.IGNORECASE)


def sector_candidates(text: str, chapter_code: str, other_codes: frozenset[str] = frozenset()) -> list[str]:
    """Zonencodes im Kapiteltext, die Sektoren des Kapitels sein können („Uba“, „Ub1“ im Kapitel „Ub“).

    Nur Vorschläge für die Zonenwahl eines hochgeladenen Reglements (AN2, docs/PLAN_AN2_PLU.md 3.3); der
    Architekt wählt oder schreibt selbst. Ein Treffer zählt nur, wenn in den 60 Zeichen davor „secteur“,
    „zone“ oder „indice“ steht – so fällt ein großgeschriebener Satzanfang meist weg („Ne sont pas …“ im
    Kapitel N). Codes anderer Kapitel sind keine Sektoren. Kürzere Codes zuerst.
    """
    pattern = re.compile(rf"(?<!\w){re.escape(chapter_code)}[a-z0-9]{{1,5}}(?!\w)")
    found: set[str] = set()
    for match in pattern.finditer(text):
        code = match.group(0)
        if code in other_codes or not _ZONE_CODE.match(code):
            continue
        before = text[max(0, match.start() - SECTOR_CONTEXT_CHARS) : match.start()]
        if _SECTOR_CONTEXT.search(before):
            found.add(code)
    return sorted(found, key=lambda code: (len(code), code))[:SECTOR_SUGGESTIONS_MAX]


def chapter_for_zone(zone_code: str, chapters: list[Chapter]) -> Chapter | None:
    """Kapitel einer Zone oder eines Sektors: exakt, sonst längstes Präfix, dem ein Kleinbuchstabe oder eine
    Ziffer folgt („Uba“ → „Ub“, „1AUz1“ → „1AUz“, nicht „AU“ → „A“)."""
    exact = [c for c in chapters if c.code == zone_code]
    if exact:
        return exact[0]
    best: Chapter | None = None
    for chapter in chapters:
        if zone_code.startswith(chapter.code) and len(zone_code) > len(chapter.code):
            follower = zone_code[len(chapter.code)]
            if (follower.islower() or follower.isdigit()) and (
                best is None or len(chapter.code) > len(best.code)
            ):
                best = chapter
    return best
