"""Zonen erkennen (docs/PLAN_HAUSMODELL.md 3.6 Nr. 1–3, E-HM-23): Quellen in fester Reihenfolge,
Normalisierung und Zuordnung über die Aliasse des Katalogs. Jede Zone landet in genau einer Gruppe: Raumzone
mit Raumtyp, ignoriert oder nicht erkannt; keine geht still verloren.
"""

import re
import unicodedata
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Literal

SourceKind = Literal["type", "category", "object_type", "long_name", "name", "classification"]
SOURCES: tuple[SourceKind, ...] = ("type", "category", "object_type", "long_name", "name", "classification")
"""Name des `IfcSpaceType` (Archicad schreibt die Zonenkategorie in IFC4 so), `Pset_SpaceCommon.Category`,
`ObjectType`, `LongName` (Zonenname), `Name` (Zonennummer), Name und Kennung der Klassifizierung."""
IGNORABLE: frozenset[SourceKind] = frozenset({"type", "category"})
"""Kategorien ohne Raum gelten nur hier, damit ein Zonenname wie „SDP“ keine Raumzone verwirft (3.6 Nr. 3)."""

_KEEP = re.compile(r"[^\w/+&°º]|_")
_PARTS = re.compile(r"[/+&]")
_AND = re.compile(r"\bET\b")
_NUMBER = re.compile(r"\b(?:N|NO|NR|NUM|NUMERO)\s*[°º]?\s*\d+|[°º]|\d+")


def normalize(value: str) -> str:
    """Schlüssel einer Zonenkategorie: Akzente weg, Großschreibung, Satzzeichen und Unterstriche zu
    Leerzeichen, Nummern weg; `/`, `+`, `&` und „et“ trennen Teile ohne Reihenfolge. „Cuisine + Séjour“ und
    „SEJOUR/CUISINE“ → „CUISINE/SEJOUR“; „CHAMBRE 1“, „Chambre_02“, „chambre n°3“, „CHAMBRE1“ → „CHAMBRE“.
    Leer, wenn nichts bleibt."""
    text = unicodedata.normalize("NFKD", value)
    text = "".join(c for c in text if not unicodedata.combining(c)).upper()
    text = _KEEP.sub(" ", text)
    parts: set[str] = set()
    for part in _PARTS.split(text):
        for piece in _AND.split(part):
            words = " ".join(_NUMBER.sub(" ", piece).split())
            if words:
                parts.add(words)
    return "/".join(sorted(parts))


@dataclass(frozen=True)
class ZoneTable:
    """Zuordnungstabelle aus dem Katalog: normalisierter Alias → Raumtyp, Kategorien ohne Raum."""

    aliases: Mapping[str, str]
    ignored: frozenset[str]

    @classmethod
    def build(cls, room_types: Iterable[tuple[str, Iterable[str]]], ignored: Iterable[str]) -> "ZoneTable":
        """Hebt `ValueError`, wenn ein Alias leer normalisiert, zwei Raumtypen trifft oder ignoriert ist."""
        aliases: dict[str, str] = {}
        for room_type_id, names in room_types:
            for name in names:
                key = normalize(name)
                if not key:
                    raise ValueError(f"Alias „{name}“ von {room_type_id} ist nach der Normalisierung leer")
                if aliases.get(key, room_type_id) != room_type_id:
                    raise ValueError(f"Alias „{name}“ ({key}) gehört zu {aliases[key]} und {room_type_id}")
                aliases[key] = room_type_id
        skipped: set[str] = set()
        for name in ignored:
            key = normalize(name)
            if not key:
                raise ValueError(f"Kategorie ohne Raum „{name}“ ist nach der Normalisierung leer")
            if key in aliases:
                raise ValueError(f"„{name}“ ({key}) ist Alias von {aliases[key]} und Kategorie ohne Raum")
            skipped.add(key)
        return cls(aliases, frozenset(skipped))


@dataclass(frozen=True)
class SourceValue:
    kind: SourceKind
    raw: str


@dataclass(frozen=True)
class Conflict:
    """Eine spätere Quelle trifft einen anderen Raumtyp oder widerspricht „ohne Raum“ (Warnung)."""

    kind: SourceKind
    raw: str
    room_type_id: str


@dataclass(frozen=True)
class ZoneMatch:
    result: Literal["room", "ignored", "unrecognized"]
    room_type_id: str | None
    source: SourceKind | None
    raw: str | None
    conflicts: tuple[Conflict, ...]


def classify(values: Iterable[SourceValue], table: ZoneTable) -> ZoneMatch:
    """Es gilt die erste Quelle, deren Wert in der Tabelle steht (Alias oder, bei Typ und Category,
    Kategorie ohne Raum); `values` werden nach `SOURCES` geordnet."""
    order = {kind: index for index, kind in enumerate(SOURCES)}
    decided: ZoneMatch | None = None
    conflicts: list[Conflict] = []
    for value in sorted(values, key=lambda v: order[v.kind]):
        key = normalize(value.raw)
        if not key:
            continue
        room_type_id = table.aliases.get(key)
        if room_type_id is not None:
            if decided is None:
                decided = ZoneMatch("room", room_type_id, value.kind, value.raw, ())
            elif decided.room_type_id != room_type_id:
                conflicts.append(Conflict(value.kind, value.raw, room_type_id))
        elif decided is None and value.kind in IGNORABLE and key in table.ignored:
            decided = ZoneMatch("ignored", None, value.kind, value.raw, ())
    if decided is None:
        return ZoneMatch("unrecognized", None, None, None, ())
    return ZoneMatch(decided.result, decided.room_type_id, decided.source, decided.raw, tuple(conflicts))
