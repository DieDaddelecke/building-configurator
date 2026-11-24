"""Zonenkapitel und allgemeine Bestimmungen im règlement écrit finden (Spez. 5.2.3 Schritt 2, Plan 3.4).

Seitennummern sind 1-basiert und beziehen sich auf das PDF, nicht auf die gedruckte Seitenzahl.
Drei Wege: die laufende Kopfzeile jeder Seite („PLUi Règlement littéral Zone UD1“, „RÈGLEMENT TOME 1
ZONE URBAINE GÉNÉRALE (UG)“), das Inhaltsverzeichnis (Titel und gedruckte Seite) und die Überschriften der
Seiten. Die Kopfzeile ist das sicherste Signal: Sie steht auf jeder Seite und benennt auch den Teil für alle
Zonen („Toutes zones“, „Dispositions générales“). Sie gilt, wenn sie mindestens so viele Kapitel findet wie
die anderen Wege; sonst gelten die Überschriften, wenn sie mehr finden als das Verzeichnis (Erstbefund Paris
und Rennes, 24.11.2026).
"""

import re
import unicodedata
from collections import Counter
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field, replace
from typing import Literal

TOC_MAX_PAGES = 8
HEADING_LINES = 12
OFFSET_SEARCH = range(-3, 11)
GENERAL_MAX_PAGES = 40
CHAPTER_MAX_PAGES = 150
"""Kapitel und allgemeine Seiten zusammen; längere Kapitel werden nicht ausgewertet (`chapter_too_long`)."""
TOC_MIN_HEADINGS = 3
"""Eine Seite mit so vielen verschiedenen Zonenüberschriften ist ein Inhaltsverzeichnis, kein Kapitelanfang.
Nötig, seit die Texterkennung gescannter Seiten Füllpunkte und Seitenzahlen verliert und aus „CHAPITRE 1 :
LA ZONE Ua …… 13“ eine Überschrift „CHAPITRE 1 : LA ZONE Ua“ wird (AN7, PLAN_AN7_SCAN 7.5)."""

_TOC_LINE = re.compile(r"^(?P<title>\S.*?)\s*(?:\.{2,}|…+|\s{2,}|\s(?=\d+\s*$))\s*(?P<page>\d{1,4})\s*$")
_ZONE_WORD = r"Z\s?ONES?"
"""„ZONE“; pypdf zerreißt große Anfangsbuchstaben in Kopfzeilen („Z ONE URBAINE GÉNÉRALE (UG)“)."""
_ZONE_TITLE = re.compile(rf"\b{_ZONE_WORD}\s+(?P<code>.+)$", re.IGNORECASE)
_ZONE_CODE = re.compile(r"^\d?[A-Z]{1,4}[a-z0-9]{0,5}$")
_HEADING = re.compile(
    r"^(?:CHAPITRE\s*\d+\s*[:\-–]?\s*)?(?:DISPOSITIONS\s+APPLICABLES\s+(?:A|À)\s+)?(?:LA\s+)?"
    rf"{_ZONE_WORD}\s+(?P<code>.+)$",
    re.IGNORECASE,
)
_CODE_IN_PARENTHESES = re.compile(r"\(\s*(?P<code>[^()]{1,12}?)\s*\)\s*[.:;\-–]?\s*$")
"""Kürzel hinter einem beschreibenden Namen: „ZONE URBAINE GÉNÉRALE (UG)“ (Paris)."""

_SUB_ENTRY = re.compile(
    r"^\s*(?:ARTICLE|ART\.|SECTION|SOUS[-\s]SECTION|PARAGRAPHE|§|\d+\.\d+|\d+\s*[.)]\s+\D"
    r"|\d?[A-Z]{1,4}[a-z0-9]{0,5}\.\d)",
    re.IGNORECASE,
)
"""Einträge unterhalb eines Kapitels im Inhaltsverzeichnis („Article Ub 7“, „Section 2“, „2.3“,
„2. Implantation des constructions“ in Rennes, „UG.3.2 Hauteur“ in Paris)."""

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


PartKind = Literal["zone", "common", "definitions", "application", "other"]
"""Teile eines Reglements: Zonenkapitel; Regeln für alle Zonen („Toutes zones“, „Dispositions générales“);
Begriffsbestimmungen; Anwendungsregeln („Modalités d'application“); Übriges (Inhalt, Abbildungen, Anhänge)."""


@dataclass(frozen=True)
class Part:
    kind: PartKind
    label: str
    first_page: int
    last_page: int
    code: str | None = None

    @property
    def pages(self) -> list[int]:
        return list(range(self.first_page, self.last_page + 1))


@dataclass(frozen=True)
class Structure:
    chapters: list[Chapter]
    general_pages: list[int]
    """Seiten, die mit jedem Zonenkapitel an das Modell gehen (höchstens `GENERAL_MAX_PAGES`)."""
    method: str
    """`running_headers`, `toc`, `headings` oder `none`."""
    common_pages: list[int] = field(default_factory=list)
    """Alle Seiten mit Regeln für alle Zonen (Rangfolge: allgemein vor Zone, S9d); ohne Obergrenze. Nur die
    Kopfzeile erkennt sie sicher; die anderen Wege lassen die Liste leer."""
    parts: list[Part] = field(default_factory=list)


def _plain(value: str) -> str:
    """Großbuchstaben ohne Akzente, Leerraum und Satzzeichen: für Stichwortvergleiche."""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(c for c in text if not unicodedata.combining(c)).upper()
    return re.sub(r"[^0-9A-Z]", "", text)


def _code(raw: str) -> str | None:
    """„U b“ → „Ub“; „1AUz“ bleibt; „URBAINE GÉNÉRALE (UG)“ → „UG“. Liefert None, wenn der Rest kein
    Zonenkürzel ist."""
    parenthesised = _CODE_IN_PARENTHESES.search(raw)
    if parenthesised:
        inner = re.sub(r"\s+", "", parenthesised.group("code"))
        if _ZONE_CODE.match(inner):
            return inner
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
    """Zonenkapitel und allgemeine Seiten bestimmen. Leere Liste von Kapiteln, wenn nichts erkennbar ist.

    Die laufende Kopfzeile gilt, wenn sie mindestens so viele Zonenkapitel findet wie die anderen Wege; die
    Titel kommen dann aus dem Verzeichnis, soweit es sie hat.

    Finden die Überschriften der Seiten mehr Zonenkapitel als das Inhaltsverzeichnis, gelten sie:
    Verzeichnisse lassen Kapitel aus (Beyenes: Zone UE fehlt, ihre Seiten lagen still im Kapitel UR), und die
    Texterkennung liest Füllpunkte und Kürzel im Verzeichnis schlecht, die großen Überschriften der
    Kapitelseiten dagegen sicher. Titel und allgemeine Seiten kommen dann weiter aus dem Verzeichnis, soweit
    es sie hat (AN7, PLAN_AN7_SCAN 7.5)."""
    if not pages:
        return Structure([], [], "none")
    last_page = max(pages)
    toc = _structure_from_toc(pages, last_page)
    headings = _structure_from_headings(pages, last_page)
    running = structure_from_running_headers(pages)
    if running is not None and len(running.chapters) >= max(
        len(headings.chapters), len(toc.chapters) if toc else 0
    ):
        titles = {c.code: c.title for c in toc.chapters} if toc else {}
        return replace(
            running, chapters=[replace(c, title=titles.get(c.code, c.title)) for c in running.chapters]
        )
    if toc is None:
        return headings
    if len(headings.chapters) <= len(toc.chapters):
        return toc
    titles = {c.code: c.title for c in toc.chapters}
    return Structure(
        [replace(c, title=titles.get(c.code, c.title)) for c in headings.chapters],
        toc.general_pages or headings.general_pages,
        "headings",
    )


def _structure_from_toc(pages: dict[int, str], last_page: int) -> Structure | None:
    entries = parse_toc(pages)
    offset = _offset(pages, entries, last_page) if entries else None
    if not entries or offset is None:
        return None
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
            chapter_end = [
                p
                for p, t in starts[index + 1 :]
                if p > first and (not _SUB_ENTRY.match(t) or _zone_code_of_title(t))
            ]
            chapters.append(Chapter(code, title, first, (chapter_end[0] - 1) if chapter_end else last_page))
    return Structure(chapters, _general_pages(ranges), "toc") if chapters else None


def _zone_headings(text: str) -> set[str]:
    codes: set[str] = set()
    for raw in text.splitlines():
        match = _HEADING.match(re.sub(r"\s+", " ", raw).strip())
        code = _code(match.group("code")) if match else None
        if code:
            codes.add(code)
    return codes


def _structure_from_headings(pages: dict[int, str], last_page: int) -> Structure:
    starts: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for number in sorted(pages):
        if len(_zone_headings(pages[number])) >= TOC_MIN_HEADINGS:
            continue
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


RUNNING_HEADER_LINES = 3
"""In so vielen ersten Zeilen einer Seite steht die Kopfzeile."""
RUNNING_HEADER_MIN_SHARE = 0.5
"""Anteil der Seiten, die den gemeinsamen Anfang der Kopfzeile tragen müssen."""
RUNNING_PREFIX_MIN_CHARS = 4

PART_KEYWORDS: tuple[tuple[PartKind, tuple[str, ...]], ...] = (
    (
        "common",
        ("TOUTESZONES", "TOUTESLESZONES", "DISPOSITIONSGENERALES", "DISPOSITIONSCOMMUNES", "REGLESCOMMUNES"),
    ),
    ("definitions", ("DEFINITION", "LEXIQUE", "GLOSSAIRE")),
    ("application", ("MODALITES", "MODEDEMPLOI", "CHAMPDAPPLICATION")),
)
"""Teile außerhalb der Zonen nach dem Text der Kopfzeile (Vergleichsform ohne Akzente und Leerraum)."""
GENERAL_RANK: dict[str, int] = {"definitions": 0, "common": 1, "application": 2}
"""Reihenfolge, in der Teile in die allgemeinen Seiten für das Modell kommen (wie `GENERAL_KEYWORDS`)."""

_RUNNING_ZONE = re.compile(rf"(?:^|\s){_ZONE_WORD}\s+(?P<rest>\S.*)$", re.IGNORECASE)


def _compact(value: str) -> str:
    return re.sub(r"\s+", "", value)


def _strip_compact_prefix(line: str, prefix: str) -> str | None:
    """Rest der Zeile hinter einem Anfang, der ohne Leerraum verglichen wird; None ohne diesen Anfang."""
    if not _compact(line).startswith(prefix):
        return None
    seen = 0
    for index, char in enumerate(line):
        if seen == len(prefix):
            return line[index:].strip()
        if not char.isspace():
            seen += 1
    return ""


_TORN_CAPITAL = re.compile(r"\b([A-ZÀ-Ý]) (?=[A-ZÀ-Ý]{2})")


def _clean_label(label: str) -> str:
    """„D ISPOSITIONS GÉNÉRALES“ → „DISPOSITIONS GÉNÉRALES“ (zerrissener Anfangsbuchstabe)."""
    return _TORN_CAPITAL.sub(r"\1", label).strip()


def _header_lines(text: str) -> list[str]:
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.splitlines()]
    return [line for line in lines if line][:RUNNING_HEADER_LINES]


def _zone_of_label(label: str) -> str | None:
    match = re.match(rf"^{_ZONE_WORD}\s+(?P<code>\S.*)$", label, re.IGNORECASE)
    return _code(match.group("code")) if match else None


def _part_kind(label: str) -> PartKind:
    plain = _plain(label)
    for kind, keywords in PART_KEYWORDS:
        if any(keyword in plain for keyword in keywords):
            return kind
    return "other"


def _running_prefix(pages: Mapping[int, str]) -> str | None:
    """Gemeinsamer Anfang der Kopfzeilen von Zonenseiten („RÈGLEMENTTOME1“, „PLUiRèglementlittéral“)."""
    prefixes: Counter[str] = Counter()
    for text in pages.values():
        for line in _header_lines(text):
            match = _RUNNING_ZONE.search(line)
            if match and _zone_of_label(line[match.start() :].strip()):
                prefix = _compact(line[: match.start()])
                if len(prefix) >= RUNNING_PREFIX_MIN_CHARS:
                    prefixes[prefix] += 1
                break
    if not prefixes:
        return None
    prefix = prefixes.most_common(1)[0][0]
    carrying = sum(
        1 for text in pages.values() if any(_compact(line).startswith(prefix) for line in _header_lines(text))
    )
    return prefix if carrying >= RUNNING_HEADER_MIN_SHARE * len(pages) else None


def _page_labels(pages: Mapping[int, str], prefix: str) -> dict[int, str | None]:
    labels: dict[int, str | None] = {}
    for number, text in pages.items():
        labels[number] = None
        for line in _header_lines(text):
            rest = _strip_compact_prefix(line, prefix)
            if rest is not None:
                labels[number] = _clean_label(rest)
                break
    return labels


def structure_from_running_headers(pages: Mapping[int, str]) -> Structure | None:
    """Gliederung aus der laufenden Kopfzeile: je Seite der Text hinter dem gemeinsamen Anfang.

    Seiten ohne Kopfzeile (leere Seiten, Abbildungen) gehören zum Teil davor, wenn danach derselbe Teil
    weitergeht. None, wenn kein gemeinsamer Anfang auf mindestens der Hälfte der Seiten steht oder keine
    Zone erkannt wird."""
    if not pages:
        return None
    prefix = _running_prefix(pages)
    if prefix is None:
        return None
    labels = _page_labels(pages, prefix)
    PartKey = tuple[PartKind, str]
    keyed: list[tuple[int, PartKey | None, str]] = []
    for number in sorted(pages):
        label = labels[number]
        code = _zone_of_label(label) if label is not None else None
        key: PartKey | None = None
        if label is not None:
            key = ("zone", code) if code else (_part_kind(label), _plain(label))
        keyed.append((number, key, label or ""))
    # Seiten ohne Kopfzeile zwischen zwei Seiten desselben Teils gehören dazu
    for index, (number, key, _label) in enumerate(keyed):
        if key is not None:
            continue
        before = next((k for _, k, _ in reversed(keyed[:index]) if k is not None), None)
        after = next((k for _, k, _ in keyed[index + 1 :] if k is not None), None)
        if before is not None and before == after:
            keyed[index] = (number, before, "")
    parts: list[Part] = []
    part_keys: list[PartKey] = []
    for number, found, label in keyed:
        part_key: PartKey = found if found is not None else ("other", "")
        if parts and part_keys[-1] == part_key and parts[-1].last_page == number - 1:
            parts[-1] = replace(parts[-1], last_page=number)
            continue
        kind, value = part_key
        parts.append(Part(kind, label, number, number, value if kind == "zone" else None))
        part_keys.append(part_key)
    chapters: list[Chapter] = []
    for part in parts:
        if part.kind != "zone" or part.code is None or any(c.code == part.code for c in chapters):
            continue
        chapters.append(Chapter(part.code, part.label, part.first_page, part.last_page))
    if not chapters:
        return None
    common = sorted({p for part in parts if part.kind == "common" for p in part.pages})
    return Structure(chapters, _general_from_parts(parts), "running_headers", common, parts)


def _general_from_parts(parts: Iterable[Part]) -> list[int]:
    selected: set[int] = set()
    ranked = sorted(
        (GENERAL_RANK[part.kind], part.first_page, part.last_page)
        for part in parts
        if part.kind in GENERAL_RANK
    )
    for _rank, first, last in ranked:
        span = set(range(first, last + 1))
        if len(selected | span) > GENERAL_MAX_PAGES:
            continue
        selected |= span
    return sorted(selected)


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


_SCOPE_CONTEXT = re.compile(r"\b(?:zones?|secteurs?|sous-secteurs?)\b[^.;:!?]{0,60}$", re.IGNORECASE)
_SCOPE_SHORT_CONTEXT = re.compile(r"\b(?:zones?|secteurs?)\s*$", re.IGNORECASE)
SCOPE_LEADING_CHARS = 3
"""Ein Kürzel ganz vorn gilt ohne „zone“ davor („UD2a Dans une bande …“, Rennes)."""


def zone_scope(text: str, codes: Iterable[str]) -> frozenset[str]:
    """Zonen und Sektoren, auf die ein Absatz sich beschränkt („dans les zones UB1 et UD1“, „en secteur
    UD1h“). Leer: gilt für alle Zonen. `codes`: Kürzel der Zonenkapitel des Dokuments; Sektoren sind ein
    Kürzel mit Kleinbuchstaben oder Ziffern dahinter („UD1a“). Einbuchstabige Kürzel („A“, „N“) nur direkt
    nach „zone“ oder „secteur“."""
    ordered = sorted(set(codes), key=len, reverse=True)
    if not ordered:
        return frozenset()
    pattern = re.compile(
        r"(?<![0-9A-Za-zÀ-ÿ])((?:"
        + "|".join(re.escape(c) for c in ordered)
        + r")[a-z0-9]{0,3})(?![0-9A-Za-zÀ-ÿ])"
    )
    found: set[str] = set()
    for match in pattern.finditer(text):
        code = match.group(1)
        before = text[max(0, match.start() - 80) : match.start()]
        if len(code) == 1:
            if _SCOPE_SHORT_CONTEXT.search(before[-15:]):
                found.add(code)
            continue
        if (
            _SCOPE_CONTEXT.search(before)
            or not text[: match.start()].strip(" -–•·(")
            or (match.start() < SCOPE_LEADING_CHARS)
        ):
            found.add(code)
    return frozenset(found)


def scope_applies(scope: Iterable[str], zone: str) -> bool:
    """Gilt ein Absatz mit dieser Beschränkung für die Zone oder den Sektor? Ohne Beschränkung immer; sonst,
    wenn er die Zone nennt, ihr Kapitel („UD1“ für „UD1a“) oder einen ihrer Sektoren („UD1a“ für „UD1“)."""
    names = set(scope)
    if not names:
        return True
    for code in names:
        if code == zone:
            return True
        longer, shorter = (zone, code) if len(zone) > len(code) else (code, zone)
        if longer.startswith(shorter) and (longer[len(shorter)].islower() or longer[len(shorter)].isdigit()):
            return True
    return False
