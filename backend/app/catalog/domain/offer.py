"""Was der Katalog für einen Typ anbietet, als Eingabe der Auswertung (Plan H3 4.1).

Reine Datenklassen: `catalog.service.offer_for_type` füllt sie aus der Datenbank, die Fachlogik von H3 rechnet
damit, ohne die Datenbank zu kennen. Je Slug gibt es genau einen Eintrag; eine gespeicherte Version (L4)
ersetzt
die jüngste veröffentlichte, damit eine Konfiguration ihren Stand behält.
"""

from dataclasses import dataclass, field
from typing import Any


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
