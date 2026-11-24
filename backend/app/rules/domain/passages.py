"""Stellen mit Vorschriftscharakter im Zonenkapitel und ihre Abdeckung durch Zitate
(docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.3).

Die Textschicht zerreißt Sätze über Zeilen. Zeilen werden zu Absätzen verbunden (neuer Absatz nach einem
Satzende, vor Aufzählungen und Nummern, vor Überschriften), Aufzählungen bleiben bei ihrem Einleitungssatz
(„… est“ / „- de 90 % …“), Absätze werden in Sätze geteilt. Eine Stelle hat Vorschriftscharakter, wenn sie
eine Zahl mit Einheit oder ein Normwort enthält; Kopfzeilen („dossier approbation 14“) und Beschriftungen
von Skizzen („3 m voie publique“) fallen über Einheit und Mindestlänge heraus.

Zugeordnet ist eine Stelle, wenn Zitate von Regeln mindestens die Hälfte ihrer Zeichen in der Vergleichsform
überdecken – gleich, welchen Status die Regel hat.
"""

import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass

from app.rules.domain import lexicon
from app.rules.domain.text import line_key, normalize, partial_match, running_lines

PASSAGE_MIN_CHARS = 25
"""Kürzere Stellen (Vergleichsform) sind Beschriftungen oder Kopfzeilen."""
PASSAGE_MAX_CHARS = 500
"""So viel einer Stelle geht an die Nachsuche und in die Anzeige."""
COVERED_SHARE = 0.5
QUOTE_MATCH_MIN = 0.85
"""Mindestähnlichkeit eines Zitatabschnitts mit dem Seitentext, damit er eine Stelle überdeckt."""

_BULLET = re.compile(r"^(?:[-–•·]\s+|\d+(?:\s*\.\s*\d+)*\s*[-–.)]\s+)")
_HEADING = re.compile(r"^(?:ARTICLE|ART\.|CHAPITRE|SECTION|TITRE|ZONE)\b", re.IGNORECASE)
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-ZÀ-ÖØ-Ý«\"“])")
_ELLIPSIS = re.compile(r"\.\.\.+|…|\[\.\.\.\]|\(\.\.\.\)")
_NUMBER_UNIT = re.compile(
    r"\d+(?:[.,]\d+)?\s*(?:m²|m2|m\b|metres?\b|cm\b|%|°|degres?\b|places?\b|arbres?\b|logements?\b|pieces?\b)"
)
NORM_WORDS: tuple[str, ...] = (
    "doit",
    "doivent",
    "interdit",
    "autorise",
    "admis",
    "au moins",
    "au plus",
    "maximum",
    "maximal",
    "minimum",
    "minimal",
    "ne peut",
    "ne peuvent",
    "soumis",
    "limite a",
    "limitee a",
    "exceder",
    "obligatoire",
    "proscrit",
    "impose",
    "exig",
    "peut",
    "peuvent",
    "derog",
)
"""In der Form ohne Akzente, klein geschrieben. Erlaubnisse („peuvent être implantées“) und Abweichungen
(„il peut être dérogé“) sind Vorschriften wie Gebote: Beyenes UC 11.1 (zeitgenössische Architektur) fehlte
sonst still (Probelauf, PLAN_G2_VOLLSTAENDIGKEIT 7.4)."""


@dataclass(frozen=True)
class Passage:
    page: int
    text: str
    has_number: bool = False

    @property
    def short(self) -> str:
        return self.text if len(self.text) <= PASSAGE_MAX_CHARS else self.text[: PASSAGE_MAX_CHARS - 1] + "…"


@dataclass(frozen=True)
class PassageCoverage:
    total: int
    assigned: int
    open: list[Passage]


def normative(text: str) -> tuple[bool, bool]:
    """(Vorschriftscharakter, enthält Zahl mit Einheit)."""
    plain = lexicon.plain(text)
    has_number = bool(_NUMBER_UNIT.search(plain))
    return has_number or any(word in plain for word in NORM_WORDS), has_number


def _is_heading(line: str) -> bool:
    letters = [c for c in line if c.isalpha()]
    return bool(_HEADING.match(line)) or (len(letters) >= 3 and all(c.isupper() for c in letters))


def _blocks(text: str, skip: set[str]) -> list[str]:
    blocks: list[list[str]] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line_key(line) in skip:
            if blocks and blocks[-1]:
                blocks.append([])
            continue
        previous = blocks[-1][-1] if blocks and blocks[-1] else ""
        # Aufzählungen bleiben beim Einleitungssatz, wenn der nicht mit einem Satzende schloss
        lead_in = bool(previous) and not previous.endswith((".", ";", "!", "?"))
        starts_new = (
            not previous
            or _is_heading(line)
            or _is_heading(previous)
            or (bool(_BULLET.match(line)) and not lead_in)
            or previous.endswith((".", "!", "?"))
        )
        if starts_new:
            blocks.append([line])
        else:
            blocks[-1].append(line)
    return [" ".join(block) for block in blocks if block and not _is_heading(" ".join(block))]


def split_passages(page: int, text: str, skip: set[str] | None = None) -> list[Passage]:
    """Stellen mit Vorschriftscharakter einer Seite, in Reihenfolge. `skip`: Kopf- und Fußzeilen."""
    passages: list[Passage] = []
    for block in _blocks(text, skip or set()):
        for sentence in _SENTENCE_END.split(block):
            sentence = sentence.strip()
            if len(normalize(sentence)) < PASSAGE_MIN_CHARS:
                continue
            relevant, has_number = normative(sentence)
            if relevant:
                passages.append(Passage(page, sentence, has_number))
    return passages


def chapter_passages(page_texts: Mapping[int, str], pages: Iterable[int]) -> list[Passage]:
    ordered = list(pages)
    skip = running_lines(page_texts, ordered)
    return [p for page in ordered for p in split_passages(page, page_texts.get(page, ""), skip)]


def _quote_spans(
    quotes: Iterable[tuple[int | None, str]], normalized_pages: Mapping[int, str]
) -> dict[int, list[tuple[int, int]]]:
    """Lage der Zitatabschnitte im Seitentext (Vergleichsform), je Seite. Ohne Seite: alle Seiten."""
    spans: dict[int, list[tuple[int, int]]] = {}
    for page, quote in quotes:
        candidates = [p for p in (page, page - 1, page + 1) if p in normalized_pages] if page else []
        for raw in _ELLIPSIS.split(quote or ""):
            segment = normalize(raw)
            if len(segment) < 8:
                continue
            best: tuple[float, int, int, int] | None = None
            for candidate in candidates or list(normalized_pages):
                haystack = normalized_pages[candidate]
                similarity, window = partial_match(segment, haystack)
                if similarity >= QUOTE_MATCH_MIN and (best is None or similarity > best[0]):
                    start = haystack.find(window)
                    best = (similarity, candidate, start, start + len(window))
            if best is not None:
                spans.setdefault(best[1], []).append((best[2], best[3]))
    return spans


def coverage(
    passages: Sequence[Passage], quotes: Iterable[tuple[int | None, str]], page_texts: Mapping[int, str]
) -> PassageCoverage:
    """Welche Stellen die Zitate überdecken. `quotes`: (Seite im Original, Zitat) aller Regeln."""
    normalized = {page: normalize(text) for page, text in page_texts.items()}
    spans = _quote_spans(quotes, normalized)
    open_passages: list[Passage] = []
    cursor: dict[int, int] = {}
    for passage in passages:
        needle = normalize(passage.text)
        haystack = normalized.get(passage.page, "")
        start = haystack.find(needle, cursor.get(passage.page, 0))
        if start < 0:
            start = haystack.find(needle)
        if start < 0:
            open_passages.append(passage)
            continue
        end = start + len(needle)
        cursor[passage.page] = end
        covered = sum(max(0, min(end, e) - max(start, s)) for s, e in _merged(spans.get(passage.page, [])))
        if covered < COVERED_SHARE * len(needle):
            open_passages.append(passage)
    return PassageCoverage(len(passages), len(passages) - len(open_passages), open_passages)


def _merged(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def for_search(passages: Sequence[Passage], limit: int) -> list[Passage]:
    """Offene Stellen für die Nachsuche: mit Zahl zuerst, sonst in Reihenfolge des Dokuments."""
    ranked = sorted(enumerate(passages), key=lambda item: (not item[1].has_number, item[0]))
    return [passage for _, passage in sorted(ranked[:limit])]
