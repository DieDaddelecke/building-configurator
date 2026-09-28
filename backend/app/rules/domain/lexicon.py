"""Alternativbezeichnungen je Regelart und Suche nach Zusatzseiten für die Nachsuche
(docs/PLAN_G2_VOLLSTAENDIGKEIT.md 3.4).

Die Begriffe stehen in der Form ohne Akzente, klein geschrieben; gesucht wird in derselben Form. Sie gehen
über `extraction.prompt_fingerprint` in die Prüfsumme der Eingabe ein: Eine Ergänzung wertet neu aus.
"""

import re
import unicodedata
from collections.abc import Iterable, Mapping

TERMS: dict[str, tuple[str, ...]] = {
    "setback_street": (
        "implantation des constructions par rapport aux voies",
        "emprises publiques",
        "alignement",
        "recul",
        "marge de recul",
        "retrait par rapport a la voie",
        "bande d'implantation",
        "bande de constructibilite",
    ),
    "setback_side": (
        "limites separatives",
        "limite separative",
        "limites laterales",
        "retrait",
        "prospect",
        "h/2",
        "l=h/2",
        "mitoyennete",
    ),
    "setback_rear": (
        "fond de parcelle",
        "limite de fond",
        "limites de fond",
        "fond de terrain",
        "limites separatives",
    ),
    "setback_between_buildings": (
        "les unes par rapport aux autres",
        "meme propriete",
        "meme unite fonciere",
        "non contigu",
        "entre deux constructions",
    ),
    "max_footprint_ratio": ("emprise au sol", "coefficient d'emprise", "c.e.s", "surface batie"),
    "max_height": ("hauteur", "faitage", "egout du toit", "acrotere", "gabarit", "niveaux", "r+1", "r + 1"),
    "roof": ("toiture", "couverture", "pente", "toiture terrasse", "toit terrasse", "deux pans", "debord"),
    "facade": (
        "facade",
        "enduit",
        "teinte",
        "couleur",
        "aspect exterieur",
        "nuancier",
        "parement",
        "bardage",
    ),
    "unsealed_min": (
        "espaces libres",
        "pleine terre",
        "non impermeabilise",
        "impermeabilis",
        "coefficient de biotope",
        "surface eco-amenageable",
        "espaces verts",
        "espace vert",
    ),
    "parking": ("stationnement", "places de stationnement", "aire de stationnement", "emplacement"),
    "planting": ("plantation", "arbre", "haute tige", "vegetalis", "essences locales"),
    "fence": ("cloture", "haie", "mur de cloture", "portail", "portillon"),
    "annex": ("annexe", "abri de jardin", "garage", "carport"),
    "max_area": ("surface de plancher maximale", "emprise au sol maximale de"),
}
"""Französische Bezeichnungen je Regelart (alte und modernisierte PLU)."""

ARTICLES: dict[str, str] = {
    "setback_street": "6",
    "setback_side": "7",
    "setback_rear": "7",
    "setback_between_buildings": "8",
    "max_footprint_ratio": "9",
    "max_height": "10",
    "roof": "11",
    "facade": "11",
    "fence": "11",
    "parking": "12",
    "unsealed_min": "13",
    "planting": "13",
}
"""Übliche Artikel alter PLU (Art. 1–16, vor der Modernisierung 2016)."""

MODERN_SECTIONS: tuple[str, ...] = (
    "Volumétrie et implantation des constructions",
    "Qualité urbaine, architecturale, environnementale et paysagère",
    "Traitement environnemental et paysager des espaces non bâtis et abords des constructions",
    "Stationnement",
)
"""Abschnitte modernisierter PLU (Code de l'urbanisme, R. 151-39 ff.)."""

BUILDING_TERMS: dict[str, tuple[str, ...]] = {
    "annex": ("construction annexe", "constructions annexes", "abri de jardin", "garage", "carport"),
    "pool": ("piscine", "bassin"),
}
"""Baukörper, die das Kapitel eigens regeln kann (Spez. 5.2.4)."""

REFERENCE_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"dispositions (?:generales|communes)"),
    re.compile(r"\blexique\b"),
    re.compile(r"\bglossaire\b"),
    re.compile(r"\bdefinitions?\b"),
    re.compile(r"\bannexe(?:s)? (?:n ?°? ?)?\d"),
    re.compile(r"\btitre [ivx]+\b"),
)
"""Verweise im Kapitel auf andere Teile des Dokuments."""


def plain(value: str) -> str:
    """Suchform: klein, ohne Akzente, einheitliche Apostrophe und Leerzeichen."""
    decomposed = unicodedata.normalize("NFKD", value.lower().replace("’", "'").replace(" ", " "))
    return re.sub(r"\s+", " ", "".join(c for c in decomposed if not unicodedata.combining(c)))


def terms_for(kind: str, building_kind: str = "main") -> tuple[str, ...]:
    return TERMS.get(kind, ()) + BUILDING_TERMS.get(building_kind, ())


def mentions(text: str, terms: Iterable[str]) -> int:
    """Anzahl Treffer der Begriffe in einem Text (Suchform)."""
    haystack = plain(text)
    return sum(haystack.count(term) for term in terms)


def kinds_mentioned(text: str) -> set[str]:
    """Regelarten, deren Begriffe im Text vorkommen (Anlass für eine Lücke, wenn keine Regel dazu besteht)."""
    haystack = plain(text)
    return {kind for kind, terms in TERMS.items() if any(term in haystack for term in terms)}


def building_kinds_mentioned(text: str) -> set[str]:
    haystack = plain(text)
    return {kind for kind, terms in BUILDING_TERMS.items() if any(term in haystack for term in terms)}


def extra_pages(
    pages: Mapping[int, str],
    candidates: Iterable[int],
    terms: Iterable[str],
    chapter_text: str,
    limit: int,
) -> list[int]:
    """Zusatzseiten für die Nachsuche: unter `candidates` (Seiten außerhalb des Kapitels, der schon gesendeten
    allgemeinen Seiten und der Kapitel anderer Zonen) die mit den meisten Treffern der gesuchten Begriffe;
    verweist das Kapitel auf Lexique, Annexes oder allgemeine Bestimmungen, zählen Seiten mit diesen Titeln
    doppelt. Seiten ohne Treffer kommen nicht in Frage."""
    wanted = [plain(term) for term in terms]
    referenced = [pattern for pattern in REFERENCE_PATTERNS if pattern.search(plain(chapter_text))]
    scored: list[tuple[int, int]] = []
    for page in candidates:
        text = plain(pages.get(page, ""))
        score = sum(text.count(term) for term in wanted)
        if score and any(pattern.search(text[:400]) for pattern in referenced):
            score *= 2
        if score:
            scored.append((score, page))
    best = sorted(scored, key=lambda item: (-item[0], item[1]))[:limit]
    return sorted(page for _, page in best)
