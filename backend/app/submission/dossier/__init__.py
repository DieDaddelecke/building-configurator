"""Dossier einer Fassung (V 3.7): zwei PDFs (fr, de) und der Lageplan als DXF, allein aus dem Snapshot.

Aus demselben Snapshot entstehen immer dieselben Dateien; das Dossier lässt sich deshalb jederzeit neu
erzeugen, ohne den heutigen Stand von Regeln oder Katalog zu sehen.
"""

from dataclasses import dataclass
from typing import Any, Literal

from app.platform.i18n import SUPPORTED

DOSSIER_VERSION = "v-1.0.0"
"""Stand der Dossier-Vorlagen; steht im Snapshot und im PDF."""


@dataclass(frozen=True)
class DossierFile:
    name: str
    kind: Literal["pdf", "dxf"]
    locale: str | None
    variant: str | None
    content_type: str
    data: bytes


def file_names(snapshot: dict[str, Any]) -> list[tuple[str, Literal["pdf", "dxf"], str | None, str | None]]:
    """Namen der Dateien einer Fassung: `<Nummer>_F<n>_<fr|de>.pdf`, `…_L93.dxf` (nur mit Kataster),
    `…_local.dxf`."""
    stem = f"{snapshot['number']}_F{snapshot['sequence']}"
    names: list[tuple[str, Literal["pdf", "dxf"], str | None, str | None]] = [
        (f"{stem}_{locale}.pdf", "pdf", locale, None) for locale in SUPPORTED
    ]
    if (snapshot.get("site") or {}).get("origin") == "parcel":
        names.append((f"{stem}_L93.dxf", "dxf", None, "L93"))
    names.append((f"{stem}_local.dxf", "dxf", None, "local"))
    return names


def build(snapshot: dict[str, Any]) -> list[DossierFile]:
    from app.submission.dossier import dxf, pdf
    from app.submission.dossier import format as fmt
    from app.submission.dossier.plan import from_snapshot

    plan = from_snapshot(snapshot)
    names = file_names(snapshot)
    dxf_names = [name for name, kind, _, _ in names if kind == "dxf"]
    files: list[DossierFile] = []
    for name, kind, locale, variant in names:
        if kind == "pdf":
            assert locale in SUPPORTED
            data = pdf.render_pdf(snapshot, plan, locale, dxf_names)
            files.append(DossierFile(name, "pdf", locale, None, "application/pdf", data))
        else:
            notes = [
                f"{snapshot['number']} F{snapshot['sequence']} - {fmt.parcels(snapshot.get('site') or {})}",
                fmt.tr(f"dossier.dxf.{variant}", "fr", e=f"{plan.origin[0]:.3f}", n=f"{plan.origin[1]:.3f}"),
            ]
            if plan.georeferenced:
                notes.append(fmt.tr("dossier.sources", "fr"))
            data = dxf.render(plan, variant, notes)  # type: ignore[arg-type]
            files.append(DossierFile(name, "dxf", None, variant, "application/dxf", data))
    return files
