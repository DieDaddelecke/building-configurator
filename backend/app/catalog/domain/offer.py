"""Was der Katalog für einen Typ anbietet, als Eingabe der Auswertung (Plan H3 4.1).

Reine Datenklassen: `catalog.service.offer_for_type` füllt sie aus der Datenbank, die Fachlogik von H3 rechnet
damit, ohne die Datenbank zu kennen. Je Slug gibt es genau einen Eintrag; eine gespeicherte Version (L4)
ersetzt
die jüngste veröffentlichte, damit eine Konfiguration ihren Stand behält.
"""

from collections.abc import Collection, Iterable
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class PackageOffer:
    slug: str
    version_id: str
    version: int
    status: str
    label_de: str
    label_fr: str
    scope: tuple[str, ...] = ()
    included: tuple[str, ...] = ()
    """Slugs der Optionen, die diese Linie ohne Aufpreis enthält."""
    regulatory: dict[str, str] = field(default_factory=dict)
    surcharge_cents: int | None = None
    """Aufpreis für diesen Typ; `None`, wenn der Preiskatalog keine Zeile hat (dann nicht anwendbar)."""

    @property
    def offered(self) -> bool:
        return self.surcharge_cents is not None


@dataclass(frozen=True)
class OptionOffer:
    slug: str
    version_id: str
    version: int
    status: str
    kind: str
    label_de: str
    label_fr: str
    params: dict[str, Any] = field(default_factory=dict)
    regulatory: dict[str, str] = field(default_factory=dict)
    excludes: tuple[str, ...] = ()
    price_cents: int | None = None
    """Aufschlag für diesen Typ, bei `terrace` je m²; `None`: nicht anwendbar."""

    @property
    def offered(self) -> bool:
        return self.price_cents is not None

    @property
    def per_m2(self) -> bool:
        return self.kind == "terrace"


@dataclass(frozen=True)
class EnergyFinding:
    package_slug: str
    climate_zone: str
    verdict: str
    compliant: bool
    surcharge_cents: int | None = None
    measures: str | None = None


@dataclass(frozen=True)
class BasePrice:
    min_cents: int
    max_cents: int
    source: str
    """`catalog` (Preiskatalog) oder `type_version` (Basispreis der Typversion)."""


@dataclass(frozen=True)
class TypeOffer:
    catalog_version_id: str | None
    catalog_version: int | None
    vat_rate: float
    base: BasePrice | None
    packages: tuple[PackageOffer, ...] = ()
    options: tuple[OptionOffer, ...] = ()
    energy: tuple[EnergyFinding, ...] = ()

    @property
    def catalog_available(self) -> bool:
        return self.catalog_version_id is not None

    def package(self, slug: str | None) -> PackageOffer | None:
        return next((p for p in self.packages if p.slug == slug), None) if slug else None

    def option(self, slug: str) -> OptionOffer | None:
        return next((o for o in self.options if o.slug == slug), None)

    def finding(self, package_slug: str | None) -> EnergyFinding | None:
        return (
            next((e for e in self.energy if e.package_slug == package_slug), None) if package_slug else None
        )


def base_price(catalog: tuple[int, int] | None, type_version: tuple[int, int]) -> BasePrice | None:
    """Basispreis aus dem veröffentlichten Preiskatalog, sonst aus der Typversion, wenn sie einen hat."""
    if catalog is not None:
        return BasePrice(catalog[0], catalog[1], "catalog")
    if type_version[0] > 0:
        return BasePrice(type_version[0], type_version[1], "type_version")
    return None


class _Slugged(Protocol):
    @property
    def slug(self) -> str: ...


def latest_per_slug[T: _Slugged](entries: Iterable[T]) -> list[T]:
    """Je Slug der letzte Eintrag, nach Slug sortiert. Erst kommen die jüngsten veröffentlichten Versionen,
    dann gespeicherte: Eine gespeicherte Version ersetzt die jüngste (L4)."""
    by_slug = {entry.slug: entry for entry in entries}
    return [by_slug[slug] for slug in sorted(by_slug)]


def offered_options(
    options: Iterable[OptionOffer],
    packages: Iterable[PackageOffer],
    *,
    stored_package_id: str | None = None,
    stored_option_ids: Collection[str] = (),
) -> list[OptionOffer]:
    """Optionen im Angebot: mit Preiszeile für den Typ, in einer angebotenen oder der gespeicherten Linie
    enthalten (sie wirken, kosten aber nichts) oder selbst gespeichert (L4)."""
    included = {
        slug for p in packages if p.offered or p.version_id == stored_package_id for slug in p.included
    }
    return [o for o in options if o.offered or o.slug in included or o.version_id in stored_option_ids]
