"""Auswahl von Linie und Optionen (Plan H3 3.1; Spez. 5.5.4, 5.5.6).

Rein: Das Angebot des Katalogs (`TypeOffer`) und die Wahl des Kunden gehen hinein, heraus kommen die wirksamen
Optionen und alle Gründe, warum eine Wahl nicht gilt. Konflikte werden nie still aufgelöst.
"""

from dataclasses import dataclass

from app.catalog.domain.offer import OptionOffer, PackageOffer, TypeOffer


@dataclass(frozen=True)
class Selection:
    """Was gespeichert ist oder gewünscht wird: Slugs, keine Versionen."""

    package_slug: str | None = None
    option_slugs: tuple[str, ...] = ()
    """Nur die ausdrücklich gewählten Optionen; die der Linie kommen von selbst dazu."""


@dataclass(frozen=True)
class Reason:
    code: str
    """`catalog_unavailable`, `unknown_package`, `unknown_option`, `not_offered`, `excluded_by`."""
    slug: str | None = None
    other: str | None = None
    """Bei `excluded_by` die Option, die den Ausschluss auslöst."""


@dataclass(frozen=True)
class Resolved:
    package: PackageOffer | None
    explicit: tuple[OptionOffer, ...]
    """Ausdrücklich gewählte, gültige Optionen (auch solche, die die Linie zugleich enthält)."""
    included: tuple[OptionOffer, ...]
    """Optionen, die die gewählte Linie ohne Aufpreis enthält."""
    invalid: tuple[Reason, ...]

    @property
    def included_slugs(self) -> frozenset[str]:
        return frozenset(o.slug for o in self.included)

    @property
    def effective(self) -> tuple[OptionOffer, ...]:
        """Alle Optionen, die auf das Haus wirken: gewählte und in der Linie enthaltene."""
        seen = {o.slug: o for o in self.explicit}
        for option in self.included:
            seen.setdefault(option.slug, option)
        return tuple(seen.values())

    def charged(self) -> tuple[OptionOffer, ...]:
        """Optionen, die etwas kosten: ausdrücklich gewählt und nicht in der Linie enthalten."""
        return tuple(o for o in self.explicit if o.slug not in self.included_slugs)


def resolve(offer: TypeOffer, selection: Selection) -> Resolved:
    invalid: list[Reason] = []
    package: PackageOffer | None = None
    if selection.package_slug:
        found = offer.package(selection.package_slug)
        if not offer.catalog_available:
            invalid.append(Reason("catalog_unavailable", selection.package_slug))
        elif found is None:
            invalid.append(Reason("unknown_package", selection.package_slug))
        elif not found.offered:
            invalid.append(Reason("not_offered", selection.package_slug))
        else:
            package = found

    explicit: list[OptionOffer] = []
    for slug in dict.fromkeys(selection.option_slugs):
        option = offer.option(slug)
        if not offer.catalog_available:
            invalid.append(Reason("catalog_unavailable", slug))
        elif option is None:
            invalid.append(Reason("unknown_option", slug))
        elif not option.offered:
            invalid.append(Reason("not_offered", slug))
        else:
            explicit.append(option)

    included: list[OptionOffer] = []
    if package is not None:
        for slug in package.included:
            option = offer.option(slug)
            if option is not None:
                included.append(option)

    resolved = Resolved(package, tuple(explicit), tuple(included), tuple(invalid))
    return Resolved(package, tuple(explicit), tuple(included), tuple(invalid) + _exclusions(resolved))


def _exclusions(resolved: Resolved) -> tuple[Reason, ...]:
    """Ausschlüsse zwischen wirksamen Optionen, von denen mindestens eine ausdrücklich gewählt ist.

    Enthält die Linie zwei sich ausschließende Optionen (Mockup: Signature), ist das ein Datenfehler
    des Büros, kein Fehler des Kunden; die Prüfung übergeht das Paar (Plan H3 3.1).
    """
    effective = {o.slug: o for o in resolved.effective}
    # Eine Option, die die Linie ohnehin enthält, ist keine eigene Entscheidung des Kunden mehr
    explicit = {o.slug for o in resolved.explicit} - resolved.included_slugs
    rank = {o.slug: i for i, o in enumerate(resolved.explicit)}
    reasons: list[Reason] = []
    seen: set[frozenset[str]] = set()
    for option in effective.values():
        # Zwei Optionen derselben Geometrieart (zwei Carports) schließen sich immer aus: Das Haus hat nur eine
        same_kind = [o.slug for o in effective.values() if o.kind != "plain" and o.kind == option.kind]
        for other_slug in (*option.excludes, *same_kind):
            other = effective.get(other_slug)
            if (
                other is None
                or other.slug == option.slug
                or (option.slug not in explicit and other.slug not in explicit)
            ):
                continue
            pair = frozenset((option.slug, other.slug))
            if pair in seen:
                continue
            seen.add(pair)
            # Den Grund trägt die zuletzt gewählte der beiden ausdrücklichen Optionen
            chosen = [m for m in (option, other) if m.slug in explicit]
            blamed = max(chosen, key=lambda m: rank.get(m.slug, -1))
            cause = other if blamed is option else option
            reasons.append(Reason("excluded_by", blamed.slug, cause.slug))
    return tuple(reasons)
