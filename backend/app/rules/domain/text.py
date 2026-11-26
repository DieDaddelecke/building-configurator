"""Text der Planunterlagen normalisieren und Zitate prüfen (Spez. 5.2.3 Schritt 4, Plan 3.4).

Die Textschicht von PDFs zerreißt Wörter („U b“, „G esvres“) und wechselt Anführungszeichen und
Bindestriche. Verglichen wird deshalb ohne Leerraum, klein geschrieben, mit vereinheitlichten Zeichen.
"""

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from difflib import SequenceMatcher

from app.rules.domain.kinds import PERCENT_PARAMS, RECIPROCAL_PARAMS

QUOTE_SIMILARITY_MIN = 0.9
"""Mindestähnlichkeit zwischen Zitat und Seitentext (Spez. 5.2.3 Schritt 4)."""
QUOTE_MIN_CHARS = 12
"""Kürzere Zitate (normalisiert) belegen nichts: „3 mètres“ steht auf vielen Seiten."""
SEGMENT_MIN_CHARS = 8
ELLIPSIS_MAX_GAP_CHARS = 600
"""Abschnitte eines Zitats mit Auslassung müssen in dieser Reihenfolge und nah beieinander stehen."""
QUOTE_OVERLAP_MIN_CHARS = 40
"""Gemeinsamer Text zweier Zitate (Vergleichsform), ab dem sie dieselbe Stelle belegen; bei kürzeren
Zitaten genügt die Hälfte des kürzeren (Referenzlisten, doppelte Hinweise; PLAN_G2_VOLLSTAENDIGKEIT)."""

_TRANSLATE = str.maketrans(
    {
        "’": "'",
        "‘": "'",
        "`": "'",
        "´": "'",
        "“": '"',
        "”": '"',
        "«": '"',
        "»": '"',
        "–": "-",
        "—": "-",
        "‑": "-",
        "‐": "-",
        "­": None,
        " ": " ",
        " ": " ",
    }
)
_SPACE = re.compile(r"\s+")
_ELLIPSIS = re.compile(r"\.\.\.+|…|\[\.\.\.\]|\(\.\.\.\)")

MEANING_MARKERS: tuple[str, ...] = (
    "pas",
    "n'",
    "non",
    "aucun",
    "jamais",
    "interdi",
    "sauf",
    "except",
    "uniquement",
    "seul",
)
"""Wörter, die eine Aussage umkehren oder einschränken. Die Ähnlichkeit allein ließe ein fehlendes „ne … pas“
durch („sont autorisées“ gegen „ne sont pas autorisées“: 0,96). Ihre Anzahl muss im Zitat und an der
Fundstelle gleich sein. Verglichen wird in der Vergleichsform ohne Leerraum; Teilwörter („dépasser“)
zählen auf beiden Seiten gleich."""

NOT_REGULATED_MARKERS: tuple[str, ...] = (
    "nonregle",
    "pasreglement",
    "sansobjet",
    "pasderegle",
    "aucuneregle",
    "pasdeprescription",
    "aucuneprescription",
    "sansprescription",
    "nonfixe",
    "pasfixe",
    "nonimpose",
    "pasimpose",
    "nonlimite",
    "paslimite",
    "nonsoumis",
    "passoumis",
)
"""Formeln für „nicht geregelt“ in der Vergleichsform ohne Akzente („non réglementé“, „sans objet“,
„il n'est pas fixé de règle“). Ohne eine davon belegt ein Zitat kein `not_regulated`."""


def normalize(value: str) -> str:
    """Vergleichsform: NFKC, klein, einheitliche Zeichen, ohne Leerraum und ohne Anführungszeichen."""
    text = unicodedata.normalize("NFKC", value).translate(_TRANSLATE).lower()
    return _SPACE.sub("", text).replace('"', "")


def _without_accents(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    return "".join(c for c in decomposed if not unicodedata.combining(c))


_NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
NUMBER_TOLERANCE = 0.005


def numbers(value: str) -> list[float]:
    """Zahlen in einem Text; Komma als Dezimaltrennzeichen („3,50“ → 3.5)."""
    return [float(n.replace(",", ".")) for n in _NUMBER.findall(value)]


def partial_match(needle: str, haystack: str) -> tuple[float, str]:
    """Beste Ähnlichkeit (0–1) von `needle` mit einem gleich langen Ausschnitt von `haystack` und dieser."""
    if not needle:
        return 0.0, ""
    position = haystack.find(needle)
    if position >= 0:
        return 1.0, haystack[position : position + len(needle)]
    size = len(needle)
    if len(haystack) <= size:
        return SequenceMatcher(None, needle, haystack, autojunk=False).ratio(), haystack
    step = max(1, size // 4)
    best, best_start = 0.0, 0
    for start in range(0, len(haystack) - size + step, step):
        ratio = SequenceMatcher(None, needle, haystack[start : start + size], autojunk=False).ratio()
        if ratio > best:
            best, best_start = ratio, start
    low, high = max(0, best_start - step), min(len(haystack) - size, best_start + step)
    for start in range(low, high + 1):
        ratio = SequenceMatcher(None, needle, haystack[start : start + size], autojunk=False).ratio()
        if ratio > best:
            best, best_start = ratio, start
    return best, haystack[best_start : best_start + size]


def partial_similarity(needle: str, haystack: str) -> float:
    return partial_match(needle, haystack)[0]


_UNIT_EXPONENT = re.compile(r"(?<=m)[23](?![0-9])")
"""Hochzahl von m² und m³ in der Vergleichsform (NFKC macht aus „m²“ „m2“). Sie ist kein Wert; die
Texterkennung liest sie oft als „m?“ oder „m°“, dann fehlte dem Scan eine Zahl, die das Zitat hat (AN7,
PLAN_AN7_SCAN 7.5)."""


def _numbers_match(quote_segment: str, window: str) -> bool:
    """Jede Zahl des Zitats steht auch im gefundenen Ausschnitt (mit etwas Rand für verschobene Grenzen).

    Ohne diese Prüfung gälte „recul de 6 mètres“ bei einem Text mit „3 mètres“ als belegt: Ein einzelnes
    Zeichen senkt die Ähnlichkeit kaum unter die Schwelle. Hochzahlen von Einheiten zählen nicht.
    """
    available = numbers(_UNIT_EXPONENT.sub("", window))
    for value in numbers(_UNIT_EXPONENT.sub("", quote_segment)):
        match = next((i for i, n in enumerate(available) if abs(n - value) <= NUMBER_TOLERANCE), None)
        if match is None:
            return False
        available.pop(match)
    return True


def _markers(value: str) -> list[int]:
    return [value.count(marker) for marker in MEANING_MARKERS]


def _meaning_matches(segment: str, window: str, margin: str) -> bool:
    """Gleich viele umkehrende oder einschränkende Wörter im Zitat und an der Fundstelle. Der Rand fängt
    Wörter ab, die die Grenze des gleich langen Ausschnitts gerade durchschneidet."""
    expected = _markers(segment)
    return expected == _markers(window) or expected == _markers(margin)


@dataclass(frozen=True)
class QuoteCheck:
    verified: bool
    page: int | None
    """Seite im Originaldokument (1-basiert), auf der das Zitat gefunden wurde."""
    similarity: float
    reason: str | None = None


def _quote_similarity(quote: str, page_text: str) -> float:
    """Zitate mit Auslassungen („…“) werden je Abschnitt geprüft; maßgeblich ist der schwächste Abschnitt.

    Ähnlichkeit 0, wenn eine Zahl nicht an der Fundstelle steht, ein zu kurzer Abschnitt eine Zahl enthält
    (sonst ließe „… 2 m“ jede Zahl zu), die Abschnitte nicht in Reihenfolge und nah beieinander stehen oder
    sich die Anzahl verneinender Wörter unterscheidet."""
    segments: list[str] = []
    for raw in _ELLIPSIS.split(quote):
        segment = normalize(raw)
        if len(segment) >= SEGMENT_MIN_CHARS:
            segments.append(segment)
        elif _NUMBER.search(segment):
            return 0.0
    if not segments:
        return 0.0
    haystack = normalize(page_text)
    weakest = 1.0
    previous_end: int | None = None
    for segment in segments:
        similarity, window = partial_match(segment, haystack)
        start = haystack.find(window, previous_end or 0)
        if start < 0:
            start = haystack.find(window)
        if previous_end is not None and (
            start < previous_end or start - previous_end > ELLIPSIS_MAX_GAP_CHARS
        ):
            return 0.0
        margin = haystack[max(0, start - 6) : start + len(window) + 6] if start >= 0 else window
        if not _numbers_match(segment, margin) or not _meaning_matches(segment, window, margin):
            return 0.0
        weakest = min(weakest, similarity)
        previous_end = start + len(window) if start >= 0 else previous_end
    return weakest


def _value_forms(name: str, value: float) -> list[float]:
    """Schreibweisen eines Werts im Text: der Wert selbst; bei Anteilen auch in Prozent (0,4 ↔ 40 %); bei
    Faktoren und Dichten auch der Kehrwert (0,5 ↔ H/2, 0,02 ↔ 1 place pour 50 m²)."""
    forms = [value]
    if name in PERCENT_PARAMS:
        forms.append(value * 100)
    if name in RECIPROCAL_PARAMS and value > 0:
        forms.append(1 / value)
    return forms


def _form_matches(form: float, number: float) -> bool:
    return abs(form - number) <= max(NUMBER_TOLERANCE, abs(number) * 0.001)


_HEIGHT_FACTOR_WORDS: tuple[tuple[float, re.Pattern[str]], ...] = (
    (0.5, re.compile(r"\bmoiti[ée]\s+de\s+la\s+hauteur")),
    (1 / 3, re.compile(r"\btiers\s+de\s+la\s+hauteur")),
    (0.25, re.compile(r"\bquart\s+de\s+la\s+hauteur")),
    (1.0, re.compile(r"[ée]ga(?:le|l)s?\s+(?:au\s+moins\s+)?à\s*:?\s*[-–•]?\s*la\s+hauteur")),
)
"""Faktoren der Höhe in Worten („la moitié de la hauteur“, „au moins égale à la hauteur“), Messung
Palaiseau (docs/PLAN_REGELDIENST.md 9): Die Zahl steht dort nicht im Text."""
_HEIGHT_FACTORS = frozenset({"height_factor", "blind_height_factor"})
_LIST_INTRO = re.compile(r"[ée]ga(?:le|l)s?\s+(?:au\s+moins\s+)?à\s*:")
_LIST_HEIGHT = re.compile(r"(?:^|[\s,;])[-–•]\s*la\s+hauteur")
"""Aufzählung nach „égale à :“, deren Punkt „- la hauteur …“ den Faktor 1 setzt."""


def value_positions(name: str, value: float, quote: str) -> list[tuple[int, int]]:
    """Stellen im Zitat, an denen der Wert eines Parameters in einer zulässigen Schreibweise steht."""
    forms = _value_forms(name, value)
    found = [
        (match.start(), match.end())
        for match in _NUMBER.finditer(quote)
        if any(_form_matches(form, float(match.group().replace(",", "."))) for form in forms)
    ]
    if name in _HEIGHT_FACTORS:
        lowered = quote.lower()
        for factor, pattern in _HEIGHT_FACTOR_WORDS:
            if abs(factor - value) <= 0.01:
                found += [(m.start(), m.end()) for m in pattern.finditer(lowered)]
        if abs(value - 1.0) <= 0.01:
            # „au moins égale à : - la moitié de la hauteur …, - la hauteur …“: der Faktor 1 ist ein Punkt der
            # Aufzählung nach „égale à“, nicht direkt daneben (Messung Palaiseau, Abstand zwischen Gebäuden)
            intro = _LIST_INTRO.search(lowered)
            if intro is not None:
                found += [(m.start(), m.end()) for m in _LIST_HEIGHT.finditer(lowered, intro.end())]
    return found


def values_in_quote(values: Mapping[str, float], quote: str) -> list[str]:
    """Namen der Parameter, deren Zahlenwert das Zitat in keiner zulässigen Schreibweise enthält."""
    return [name for name, value in values.items() if not value_positions(name, value, quote)]


def states_not_regulated(quote: str) -> bool:
    """Sagt das Zitat ausdrücklich, dass nichts geregelt ist?"""
    plain = _without_accents(normalize(quote))
    return any(marker in plain for marker in NOT_REGULATED_MARKERS)


def verify_quote(quote: str, pages: dict[int, str], page: int) -> QuoteCheck:
    """Zitat auf der angegebenen Seite suchen; sonst auf der Nachbarseite oder über den Seitenwechsel.

    `pages`: Seitennummer im Originaldokument (1-basiert) → Text. Wird das Zitat nur auf einer Nachbarseite
    gefunden, gilt es als belegt und die Seite wird berichtigt (Annahme G2-Zitate, docs/ANNAHMEN.md).
    """
    if len(normalize(_ELLIPSIS.sub("", quote))) < QUOTE_MIN_CHARS:
        return QuoteCheck(False, None, 0.0, "quote_too_short")
    # Einzelseiten vor Seitenwechseln, damit ein Zitat ganz auf der Nachbarseite auch dieser zugeordnet wird
    candidates: list[tuple[int, str]] = [(p, pages[p]) for p in (page, page - 1, page + 1) if p in pages]
    for first in (page, page - 1):
        if first in pages and first + 1 in pages:
            candidates.append((first, pages[first] + "\n" + pages[first + 1]))
    if not candidates:
        return QuoteCheck(False, None, 0.0, "page_unknown")
    best_page, best = None, 0.0
    for candidate_page, text in candidates:
        similarity = _quote_similarity(quote, text)
        if similarity > best + 1e-9:
            best_page, best = candidate_page, similarity
        if best >= 1.0:
            break
    if best >= QUOTE_SIMILARITY_MIN:
        return QuoteCheck(True, best_page, round(best, 3))
    return QuoteCheck(False, best_page, round(best, 3), "quote_not_found")


def quotes_overlap(a: str | None, b: str | None) -> bool:
    """Belegen zwei Zitate dieselbe Stelle? Abschnitte um „…“ getrennt, Vergleichsform wie beim Prüfen."""
    if not a or not b:
        return False
    for left in (normalize(part) for part in _ELLIPSIS.split(a)):
        for right in (normalize(part) for part in _ELLIPSIS.split(b)):
            if not left or not right:
                continue
            match = SequenceMatcher(None, left, right, autojunk=False).find_longest_match(
                0, len(left), 0, len(right)
            )
            if match.size >= min(QUOTE_OVERLAP_MIN_CHARS, max(12, min(len(left), len(right)) // 2)):
                return True
    return False
