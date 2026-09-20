"""RE2020-Status aus dem Befund je Typ und Linie (Plan H3 3.7; Spez. 5.9.6, reduziert nach Plan H1 3.8).

Das Backend berechnet keine RE2020-Kennwerte (L7): Es gibt einen Befund des Katalogs weiter und nimmt einen
angegebenen Konformitätsaufpreis in den Korridor auf. Ohne Befund ist der Status offen, nie „bestanden“.
"""

from dataclasses import dataclass

from app.catalog.domain.offer import EnergyFinding


@dataclass(frozen=True)
class EnergyStatus:
    status: str
    """`compliant`, `action` (nicht konform, Maßnahmen nötig) oder `not_assessed`."""
    climate_zone: str | None = None
    verdict: str | None = None
    measures: str | None = None
    surcharge_cents: int | None = None
    """Konformitätsaufpreis, nur bei `action`; geht in beide Korridorgrenzen ein."""


def energy_status(finding: EnergyFinding | None) -> EnergyStatus:
    if finding is None:
        return EnergyStatus("not_assessed")
    if finding.compliant:
        return EnergyStatus("compliant", finding.climate_zone, finding.verdict)
    return EnergyStatus(
        "action", finding.climate_zone, finding.verdict, finding.measures, finding.surcharge_cents
    )
