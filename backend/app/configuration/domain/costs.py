"""Kostenkorridor aus festen Preisspannen (Plan H3 3.8; Spez. 5.6.5, 5.6.6).

```
K_min = Basis_min + Linienaufpreis + Σ Optionsaufpreise (nicht in der Linie enthalten) + Konformitätsaufpreis
K_max = Basis_max + dieselben Aufschläge
```

Beträge in Cent, gerechnet netto. Es gibt bewusst keinen Einzelbetrag (L1): nur `min`, `max` und die auf
1.000 € gerundete Anzeige. Ein Posten ohne Preiszeile im veröffentlichten Katalog ist nicht
wählbar (Anwendbarkeit, Plan H3 3.1) und kommt hier deshalb nicht vor.
"""

from dataclasses import dataclass

from app.catalog.domain.offer import TypeOffer
from app.configuration.domain.energy import EnergyStatus
from app.configuration.domain.options import Resolved

ROUND_CENTS = 100_000
"""Anzeige auf 1.000 € (Spez. 5.6.5)."""


@dataclass(frozen=True)
class CostItem:
    code: str
    kind: str
    """`base`, `package`, `option` oder `energy`."""
    slug: str | None
    min_cents: int
    max_cents: int
    included: bool = False
    """In der gewählten Linie enthalten: kostet nichts und steht trotzdem da."""
    quantity: float | None = None
    unit: str | None = None
    unit_price_cents: int | None = None
    source: str | None = None
    """Herkunft des Basispreises: `catalog` oder `type_version` (L3)."""


@dataclass(frozen=True)
class Range:
    min_cents: int
    max_cents: int


@dataclass(frozen=True)
class Costs:
    available: bool
    reason: str | None
    net: Range | None
    gross: Range | None
    vat_rate: float
    display: Range | None
    """Brutto auf 1.000 € gerundet: nur damit wird angezeigt („ca. X – Y €“)."""
    catalog_version: int | None
    catalog_version_id: str | None
    items: tuple[CostItem, ...]


def round_thousand(cents: int) -> int:
    """Kaufmännisch auf 1.000 € (337.500 € → 338.000 €, wie das Mockup)."""
    return (cents + ROUND_CENTS // 2) // ROUND_CENTS * ROUND_CENTS


def _unavailable(offer: TypeOffer, reason: str) -> Costs:
    return Costs(
        False, reason, None, None, offer.vat_rate, None, offer.catalog_version, offer.catalog_version_id, ()
    )


def compute_costs(
    offer: TypeOffer, resolved: Resolved, energy: EnergyStatus, terrace_areas: dict[str, float]
) -> Costs:
    """Kosten der Auswahl. `terrace_areas`: Fläche je Terrassenoption in m² (hängt nur vom Typ ab)."""
    if not offer.catalog_available:
        return _unavailable(offer, "catalog_unavailable")
    if offer.base is None:
        return _unavailable(offer, "base_price_missing")

    items: list[CostItem] = [
        CostItem(
            "TYPE_BASE",
            "base",
            None,
            offer.base.min_cents,
            offer.base.max_cents,
            source=offer.base.source,
        )
    ]
    if resolved.package is not None and resolved.package.surcharge_cents is not None:
        surcharge = resolved.package.surcharge_cents
        items.append(
            CostItem(
                f"PKG_{resolved.package.slug.upper()}", "package", resolved.package.slug, surcharge, surcharge
            )
        )
    for option in resolved.explicit:
        code = f"MOD_{option.slug.upper()}"
        if option.slug in resolved.included_slugs:
            items.append(CostItem(code, "option", option.slug, 0, 0, included=True))
        elif option.price_cents is not None and option.per_m2:
            area = terrace_areas.get(option.slug, 0.0)
            amount = round(option.price_cents * area)
            items.append(
                CostItem(
                    code,
                    "option",
                    option.slug,
                    amount,
                    amount,
                    quantity=area,
                    unit="m2",
                    unit_price_cents=option.price_cents,
                )
            )
        elif option.price_cents is not None:
            items.append(CostItem(code, "option", option.slug, option.price_cents, option.price_cents))
    for option in resolved.included:
        if option.slug not in {o.slug for o in resolved.explicit}:
            items.append(CostItem(f"MOD_{option.slug.upper()}", "option", option.slug, 0, 0, included=True))
    if energy.status == "action" and energy.surcharge_cents:
        items.append(
            CostItem("RE2020_CONFORMITY", "energy", None, energy.surcharge_cents, energy.surcharge_cents)
        )

    net = Range(sum(i.min_cents for i in items), sum(i.max_cents for i in items))
    gross = Range(round(net.min_cents * (1 + offer.vat_rate)), round(net.max_cents * (1 + offer.vat_rate)))
    display = Range(round_thousand(gross.min_cents), round_thousand(gross.max_cents))
    return Costs(
        True,
        None,
        net,
        gross,
        offer.vat_rate,
        display,
        offer.catalog_version,
        offer.catalog_version_id,
        tuple(items),
    )
