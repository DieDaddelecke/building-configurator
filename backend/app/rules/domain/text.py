"""Text der Planunterlagen normalisieren und Zitate prüfen (Spez. 5.2.3 Schritt 4, Plan 3.4).

Die Textschicht von PDFs zerreißt Wörter („U b“, „G esvres“) und wechselt Anführungszeichen und
Bindestriche. Verglichen wird deshalb ohne Leerraum, klein geschrieben, mit vereinheitlichten Zeichen.
"""

import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

QUOTE_SIMILARITY_MIN = 0.9
"""Mindestähnlichkeit zwischen Zitat und Seitentext (Spez. 5.2.3 Schritt 4)."""
QUOTE_MIN_CHARS = 12
"""Kürzere Zitate (normalisiert) belegen nichts: „3 mètres“ steht auf vielen Seiten."""
SEGMENT_MIN_CHARS = 8

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


def normalize(value: str) -> str:
    """Vergleichsform: NFKC, klein, einheitliche Zeichen, ohne Leerraum und ohne Anführungszeichen."""
    text = unicodedata.normalize("NFKC", value).translate(_TRANSLATE).lower()
    return _SPACE.sub("", text).replace('"', "")


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


def _numbers_match(quote_segment: str, window: str) -> bool:
    """Jede Zahl des Zitats steht auch im gefundenen Ausschnitt (mit etwas Rand für verschobene Grenzen).

    Ohne diese Prüfung gälte „recul de 6 mètres“ bei einem Text mit „3 mètres“ als belegt: Ein einzelnes
    Zeichen senkt die Ähnlichkeit kaum unter die Schwelle.
    """
    available = numbers(window)
    for value in numbers(quote_segment):
        match = next((i for i, n in enumerate(available) if abs(n - value) <= NUMBER_TOLERANCE), None)
        if match is None:
            return False
        available.pop(match)
    return True


@dataclass(frozen=True)
class QuoteCheck:
    verified: bool
    page: int | None
    """Seite im Originaldokument (1-basiert), auf der das Zitat gefunden wurde."""
    similarity: float
    reason: str | None = None


def _quote_similarity(quote: str, page_text: str) -> float:
    """Zitate mit Auslassungen („…“) werden je Abschnitt geprüft; maßgeblich ist der schwächste Abschnitt.
    Stimmt eine Zahl nicht mit der gefundenen Stelle überein, ist die Ähnlichkeit 0."""
    segments = [normalize(s) for s in _ELLIPSIS.split(quote)]
    segments = [s for s in segments if len(s) >= SEGMENT_MIN_CHARS]
    if not segments:
        return 0.0
    haystack = normalize(page_text)
    weakest = 1.0
    for segment in segments:
        similarity, window = partial_match(segment, haystack)
        start = haystack.find(window)
        margin = haystack[max(0, start - 6) : start + len(window) + 6] if start >= 0 else window
        if not _numbers_match(segment, margin):
            return 0.0
        weakest = min(weakest, similarity)
    return weakest


def values_in_quote(values: list[float], quote: str) -> list[float]:
    """Zahlenwerte einer Regel, die das Zitat nicht enthält. Erlaubt sind der Wert selbst, der Wert in Prozent
    (0,4 ↔ 40 %) und der Kehrwert (0,5 ↔ H/2, 0,02 ↔ 1 place pour 50 m²)."""
    found = numbers(quote)
    missing: list[float] = []
    for value in values:
        forms = [value, value * 100]
        if value > 0:
            forms.append(1 / value)
        if not any(abs(form - n) <= max(NUMBER_TOLERANCE, abs(n) * 0.001) for form in forms for n in found):
            missing.append(value)
    return missing


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
