"""Hilfen für die Tests des Moduls G2: PDF aus echter Textschicht, aufgezeichnete Modellantworten."""

import io
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.rules.domain.extraction import ExtractionError, ExtractionRequest, ExtractionResponse

FIXTURES = Path(__file__).parent / "fixtures" / "rules"
DOC_ID = "911b23511c396d7211def55c6bf40bd4"
PDF_NAME = "244400503_reglement_20260304.pdf"


def fixture_json(name: str) -> Any:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def _escape(line: str) -> bytes:
    raw = line.encode("cp1252", "replace")
    return raw.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")


def text_pdf(pages: list[str]) -> bytes:
    """Schlichtes PDF (Helvetica, WinAnsi) mit der gegebenen Textschicht je Seite.

    Die Originalplanunterlage ist mit eingebetteten Schriften zu groß für das Repository; für Kapitelsuche
    und Zitatprüfung zählt nur die Textschicht."""
    writer = PdfWriter()
    font = writer._add_object(
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
                NameObject("/Encoding"): NameObject("/WinAnsiEncoding"),
            }
        )
    )
    for text in pages:
        page = writer.add_blank_page(595, 842)
        page[NameObject("/Resources")] = DictionaryObject(
            {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
        )
        body = b"BT /F1 8 Tf 10 TL 30 815 Td\n"
        for line in text.splitlines():
            body += b"(" + _escape(line) + b") Tj T*\n"
        body += b"ET"
        stream = DecodedStreamObject()
        stream.set_data(body)
        page[NameObject("/Contents")] = writer._add_object(stream)
    buffer = io.BytesIO()
    writer.write(buffer)
    return buffer.getvalue()


def regulation_fixture() -> tuple[bytes, list[int]]:
    """PDF mit Inhaltsverzeichnis (Originalseiten 1–3) und Kapitel Uh (92–112) samt Originalseiten."""
    data = fixture_json("reglement-pages.json")
    return text_pdf(data["pages"]), data["original_pages"]


def gpu_directory(tmp_path: Path) -> Path:
    for source in FIXTURES.glob("*.json"):
        if source.name != "reglement-pages.json":
            (tmp_path / source.name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    pdf, _pages = regulation_fixture()
    (tmp_path / PDF_NAME).write_bytes(pdf)
    return tmp_path


def rule(
    sector: str,
    kind: str,
    params: dict[str, Any],
    quote: str,
    page: int,
    *,
    building_kind: str = "main",
    status: str = "regulated",
    document: str = "chapter",
) -> dict[str, Any]:
    """Regel im Ausgabeschema des Modells (`app.rules.domain.extraction.OUTPUT_SCHEMA`)."""
    items = []
    for name, value in params.items():
        entry: dict[str, Any] = {"name": name, "number": None, "text": None, "flag": None, "items": []}
        if isinstance(value, bool):
            entry["flag"] = value
        elif isinstance(value, int | float):
            entry["number"] = value
        elif isinstance(value, list):
            entry["items"] = value
        else:
            entry["text"] = value
        items.append(entry)
    return {
        "sector": sector,
        "kind": kind,
        "building_kind": building_kind,
        "status": status,
        "params": items,
        "document": document,
        "page": page,
        "quote": quote,
        "confidence": 0.9,
        "notes": "",
    }


def uh_output(*, footprint: float = 0.25) -> dict[str, Any]:
    """Auswertung des Kapitels Uh, wie das Modell sie liefern soll. Seiten sind Positionen im Kapitel-PDF
    (Originalseite 92 = Position 1). Zitate stammen wörtlich aus der Textschicht."""
    return {
        "remarks": "",
        "rules": [
            rule(
                "Uh",
                "setback_street",
                {"mode": "range", "min_m": 5, "max_m": 20, "band": "building"},
                "Les constructions principales, hors extension, doivent être implantées "
                "dans une bande située entre 5 m et 20m par rapport à l’alignement des voies .",
                6,
            ),
            rule(
                "Uh",
                "setback_side",
                {"min_m": 3, "allow_on_boundary": True},
                "Les constructions principales s’implantent soit en limite séparative, "
                "soit en retrait. En cas d’implantation en retrait, il doit être d’au moins 3 mètres.",
                7,
            ),
            rule(
                "Uh",
                "setback_rear",
                {"min_m": 3, "allow_on_boundary": True},
                "Les constructions principales s’implantent soit en limite séparative, "
                "soit en retrait. En cas d’implantation en retrait, il doit être d’au moins 3 mètres.",
                7,
            ),
            rule(
                "Uh",
                "max_footprint_ratio",
                {"ratio": footprint},
                "L’emprise au sol totale des constructions est limitée à 25% de la surface totale de l’unité "
                "foncière à l’intérieur de la zone.",
                8,
            ),
            rule(
                "Uh",
                "max_height",
                {"eave_m": 7, "ridge_m": 10},
                "La hauteur des constructions ne doit pas excéder 7 mètres à l’égout du toit "
                "(en cas de toiture à pans) ou à l’acrotère (en cas de toiture terrasse) "
                "et 10 mètres au point le plus haut de la construction",
                9,
            ),
            rule(
                "Uh",
                "setback_street",
                {"mode": "min", "min_m": 5},
                "Les annexes, garages (accolés ou non) et les piscines (margelles comprises) s’implantent en "
                "recul de 5 mètres minimum.",
                6,
                building_kind="annex",
            ),
            rule(
                "Uh",
                "text_only",
                {"summary": "Volumes simples et cohérence architecturale avec le hameau."},
                "Les constructions principales et leurs annexes, doivent présenter "
                "une simplicité de volume et une cohérence architecturale.",
                10,
            ),
            # Kein Sektor dieses Kapitels in der Gemeinde: fällt weg
            rule("Uc", "max_footprint_ratio", {"ratio": 0.3}, "egal", 1),
        ],
    }


def verification_output(output: dict[str, Any], claims: list[dict[str, Any]]) -> dict[str, Any]:
    """Gegenprüfung, wie sie ein Modell liefern würde, das den Text so liest wie in `output`: je Frage Status
    und Werte der passenden Regel, sonst `not_supported`."""

    def building(value: str) -> str:
        return "main" if value == "any" else value

    checks = []
    for claim in claims:
        match = next(
            (
                r
                for r in output["rules"]
                if r["sector"] == claim["sector"]
                and r["kind"] == claim["kind"]
                and building(r["building_kind"]) == building(claim["building_kind"])
                and r["status"] in ("regulated", "not_regulated")
            ),
            None,
        )
        checks.append(
            {
                "claim": claim["claim"],
                "status": match["status"] if match else "not_supported",
                "params": match["params"] if match else [],
                "notes": "",
            }
        )
    return {"checks": checks, "remarks": ""}


@dataclass
class FakeExtractor:
    """Liefert je Aufruf die nächste Antwort; eine `ExtractionError` in der Liste wird geworfen.

    Fragt die Anfrage eine Gegenprüfung ab und ist die Antwort eine Auswertung (`rules`), wird daraus die
    Gegenprüfung gebildet. So beschreibt `[uh_output(), uh_output(footprint=0.3)]` eine Gegenprüfung, die bei
    der Grundfläche einen anderen Wert liest."""

    responses: list[dict[str, Any] | ExtractionError | Callable[[ExtractionRequest], dict[str, Any]]]
    """Eine Funktion bekommt die Anfrage (Nachsuche: Antwort je Lücke nach Art)."""
    requests: list[ExtractionRequest] = field(default_factory=list)

    def extract(self, request: ExtractionRequest) -> ExtractionResponse:
        self.requests.append(request)
        item = self.responses[min(len(self.requests) - 1, len(self.responses) - 1)]
        if isinstance(item, ExtractionError):
            raise item
        if callable(item):
            item = item(request)
        if request.claims is not None and "checks" not in item:
            item = verification_output(item, request.claims)
        if request.gaps is not None and "gaps" not in item:
            item = {"gaps": [], "passages": [], "remarks": ""}
        return ExtractionResponse(
            output=item,
            model="anthropic/claude-opus-5",
            request_id=f"req_{len(self.requests)}",
            stop_reason="stop",
            usage={"input_tokens": 1000, "output_tokens": 2000, "cache_read_input_tokens": 50000},
            served_by_fallback=False,
            duration_ms=1234,
            cost_usd=0.08,
        )

    def factory(self) -> Callable[[], "FakeExtractor"]:
        return lambda: self
