"""Ansichten einer Fassung aus Zeile und Snapshot (V 4.3), ohne Datenbankabfrage.

Das Modul A (`inquiry.service`) setzt damit Vorgangsdetail und Kundenansicht zusammen; es importiert nur
diese Datei und die Modelle, nicht den Dienst der Übergabe (der seinerseits A benutzt).
"""

from typing import Any

from app.configuration.schemas import CheckOut, RangeOut
from app.submission.models import Submission
from app.submission.schemas import (
    StaffSubmissionOut,
    SubmissionFileOut,
    SubmissionSummaryOut,
    SummaryOptionOut,
)


def files_out(row: Submission, *, pdf_only: bool = False) -> list[SubmissionFileOut]:
    return [
        SubmissionFileOut(
            name=f["name"],
            kind=f["kind"],
            locale=f.get("locale"),
            variant=f.get("variant"),
            size_bytes=int(f["size_bytes"]),
        )
        for f in row.dossier_files
        if not pdf_only or f["kind"] == "pdf"
    ]


def summary_out(snapshot: dict[str, Any]) -> SubmissionSummaryOut:
    catalog = snapshot.get("catalog") or {}
    type_ = catalog.get("type") or {}
    package = catalog.get("package") or {}
    configuration = snapshot.get("configuration") or {}
    costs = configuration.get("costs") or {}
    display = costs.get("display")
    return SubmissionSummaryOut(
        type_name=type_.get("name"),
        type_version=type_.get("version"),
        type_retired=type_.get("status") == "retired",
        package_label_de=package.get("label_de"),
        package_label_fr=package.get("label_fr"),
        options=[
            SummaryOptionOut(
                slug=o["slug"],
                label_de=o.get("label_de") or o["slug"],
                label_fr=o.get("label_fr") or o["slug"],
                included=bool(o.get("included")),
            )
            for o in catalog.get("options") or []
        ],
        costs_display=RangeOut(**display) if display and costs.get("available") else None,
        vat_rate=costs.get("vat_rate"),
        catalog_version=costs.get("catalog_version"),
        deviations=[CheckOut(**c) for c in snapshot.get("deviations") or []],
        site_origin=(snapshot.get("site") or {}).get("origin"),
    )


def staff_out(row: Submission) -> StaffSubmissionOut:
    return StaffSubmissionOut(
        sequence=row.sequence,
        status=row.status,
        created_at=row.created_at,
        configuration_revision=row.configuration_revision,
        deviations_acknowledged=row.deviations_acknowledged,
        deviation_count=row.deviation_count,
        open_points=row.open_points,
        dossier_status=row.dossier_status,
        dossier_error=row.dossier_error,
        files=files_out(row),
        summary=summary_out(row.snapshot),
    )
