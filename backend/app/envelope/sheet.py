"""Steckbrief des Baurahmens als PDF (Plan 3.5, Plan G3 4.2).

Der Lageplan wird hier als SVG erzeugt, damit der Steckbrief unabhängig vom Browser entsteht (L5: der
Server ist maßgeblich). Die Darstellung ist bewusst schlicht; maßgeblich sind dieselben Werte, die die
API liefert. Jede Seite trägt den Hinweis, dass es sich um eine ungeprüfte Simulation handelt (L7).
"""

import html
from typing import Any

from app.envelope.schemas import ContourOut, EnvelopeOut, LimitOut, PartOut
from app.platform.i18n import Locale, translate

PLAN_SIZE_MM = (170.0, 120.0)
PLAN_MARGIN_M = 3.0
COLORS = {
    "outline": "#1f2933",
    "part": "#f4f1ea",
    "lenient": "#b9c6b1",
    "strict": "#6f8b5f",
    "no_build": "#c9756b",
    "restricts": "#d8b26a",
    "band": "#8fa8c8",
    "street": "#2f6f8f",
}


def render_html(envelope: EnvelopeOut, *, reference: str, locale: Locale) -> str:
    """Vollständiges HTML des Steckbriefs (eine Vorlage, keine Template-Bibliothek)."""
    t = lambda key, **params: translate(key, locale, **params)  # noqa: E731  kurze Hilfe
    title = t("sheet.title")
    rows = "".join(_part_section(part, envelope, locale) for part in envelope.parts)
    warnings = "".join(f"<li>{html.escape(t('envelope.warning.' + code))}</li>" for code in envelope.warnings)
    return f"""<!DOCTYPE html>
<html lang="{locale}"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>
@page {{ size: A4; margin: 16mm 14mm 18mm 14mm;
  @bottom-center {{ content: "{html.escape(t("sheet.footer"))}"; font-size: 7pt; color: #6b7280; }}
  @bottom-right {{ content: counter(page) "/" counter(pages); font-size: 7pt; color: #6b7280; }} }}
body {{ font-family: "DejaVu Sans", sans-serif; font-size: 9pt; color: #1f2933; }}
h1 {{ font-size: 15pt; margin: 0 0 2mm 0; }}
h2 {{ font-size: 10pt; margin: 6mm 0 1mm 0; border-bottom: 0.3mm solid #1f2933; padding-bottom: 1mm; }}
.meta {{ color: #52606d; font-size: 8pt; }}
.stamp {{ margin: 3mm 0; padding: 2mm 3mm; background: #f6f1e7; border-left: 1mm solid #b08b4f;
  font-size: 8pt; }}
table {{ width: 100%; border-collapse: collapse; font-size: 8pt; }}
th, td {{ text-align: left; vertical-align: top; padding: 1mm 1.5mm; border-bottom: 0.2mm solid #d9dde1; }}
th {{ color: #52606d; font-weight: normal; }}
td.value {{ font-variant-numeric: tabular-nums; }}
td.quote {{ color: #52606d; font-size: 7pt; }}
ul {{ margin: 1mm 0; padding-left: 5mm; }}
.legend span {{ margin-right: 4mm; font-size: 7.5pt; }}
.swatch {{ display: inline-block; width: 3mm; height: 3mm; margin-right: 1mm; vertical-align: -0.3mm; }}
</style></head><body>
<h1>{html.escape(title)}</h1>
<div class="meta">{html.escape(reference)} · {html.escape(t("sheet.status." + envelope.status))}
 · {envelope.updated_at:%d.%m.%Y}</div>
<div class="stamp">{html.escape(t("sheet.simulation_notice"))}</div>
{_plan_svg(envelope)}
<div class="legend">{_legend(locale)}</div>
<h2>{html.escape(t("sheet.areas"))}</h2>
{_areas_table(envelope, locale)}
{rows}
{f"<h2>{html.escape(t('sheet.warnings'))}</h2><ul>{warnings}</ul>" if warnings else ""}
<h2>{html.escape(t("sheet.provenance"))}</h2>
<div class="meta">{html.escape(_provenance(envelope, locale))}</div>
</body></html>"""


def _legend(locale: Locale) -> str:
    items = [
        ("strict", "envelope.contour.strict"),
        ("lenient", "envelope.contour.lenient"),
        ("band", "envelope.legend.band"),
        ("no_build", "envelope.legend.no_build"),
        ("restricts", "envelope.legend.restricts"),
    ]
    return "".join(
        f'<span><span class="swatch" style="background:{COLORS[color]}"></span>'
        f"{html.escape(translate(key, locale))}</span>"
        for color, key in items
    )


def _areas_table(envelope: EnvelopeOut, locale: Locale) -> str:
    def area(contour: ContourOut, key: str) -> str:
        suffix = "" if contour.complete else " *"
        return (
            f"<tr><th>{html.escape(translate(key, locale))}</th>"
            f'<td class="value">{_number(contour.area_m2, 0)} m²{suffix}</td></tr>'
        )

    lenient = envelope.contours.get("lenient")
    strict = envelope.contours.get("strict")
    rows = [
        f"<tr><th>{html.escape(translate('sheet.site_area', locale))}</th>"
        f'<td class="value">{_number(envelope.area_m2, 0)} m²</td></tr>'
    ]
    if lenient is not None:
        rows.append(area(lenient, "envelope.contour.lenient"))
    if strict is not None:
        rows.append(area(strict, "envelope.contour.strict"))
        if not strict.complete:
            rows.append(
                f'<tr><td colspan="2" class="quote">* '
                f"{html.escape(translate('envelope.contour.incomplete', locale))}</td></tr>"
            )
    return "<table>" + "".join(rows) + "</table>"


def _part_section(part: PartOut, envelope: EnvelopeOut, locale: Locale) -> str:
    heading = translate("sheet.zone", locale, code=part.zone_code)
    if part.excluded:
        note = translate("envelope.excluded." + part.excluded, locale)
        return f'<h2>{html.escape(heading)}</h2><div class="meta">{html.escape(note)}</div>'
    rows = "".join(_limit_row(limit, locale) for limit in part.limits if limit.derived_from is None)
    derived = "".join(_limit_row(limit, locale) for limit in part.limits if limit.derived_from is not None)
    edges = "".join(_edge_row(edge, part.zone_code, locale) for edge in envelope.edges)
    return (
        f"<h2>{html.escape(heading)}</h2>"
        f'<div class="meta">{_number(part.area_m2, 0)} m² · '
        f"{html.escape(translate('envelope.zone_status.' + part.zone_status, locale))}</div>"
        f"<table><tr><th>{html.escape(translate('sheet.rule', locale))}</th>"
        f"<th>{html.escape(translate('sheet.value', locale))}</th>"
        f"<th>{html.escape(translate('sheet.source', locale))}</th></tr>"
        f"{derived}{rows}{edges}</table>"
    )


def _limit_row(limit: LimitOut, locale: Locale) -> str:
    label = translate(f"envelope.limit.{limit.key}", locale)
    if limit.building_kind not in ("main", "any"):
        label += f" ({translate('envelope.building_kind.' + limit.building_kind, locale)})"
    return (
        f"<tr><th>{html.escape(label)}</th>"
        f'<td class="value">{html.escape(_limit_value(limit, locale))}</td>'
        f'<td class="quote">{html.escape(_source(limit.citation, locale))}</td></tr>'
    )


def _edge_row(edge: Any, zone_code: str, locale: Locale) -> str:
    setbacks = [s for s in edge.setbacks if s.zone_code == zone_code]
    if not setbacks:
        return ""
    label = translate("envelope.edge." + edge.kind, locale) + f" {edge.seq}"
    if edge.street_name:
        label += f" · {edge.street_name}"
    value = _distance_text(edge.lenient_m, edge.strict_m, locale)
    citation = setbacks[0].citation
    return (
        f"<tr><th>{html.escape(label)}</th>"
        f'<td class="value">{html.escape(value)}</td>'
        f'<td class="quote">{html.escape(_source(citation, locale))}</td></tr>'
    )


def _distance_text(lenient: float | None, strict: float | None, locale: Locale) -> str:
    if lenient is None and strict is None:
        return translate("envelope.value.not_determined", locale)
    if lenient == strict:
        return f"{_number(lenient or 0.0, 2)} m"
    return (
        f"{_number(lenient, 2) if lenient is not None else '?'} – "
        f"{_number(strict, 2) if strict is not None else '?'} m"
    )


def _limit_value(limit: LimitOut, locale: Locale) -> str:
    if limit.status == "not_regulated":
        return translate("envelope.value.not_regulated", locale)
    if limit.status in ("unknown", "missing"):
        return translate("envelope.value.not_determined", locale)
    if limit.value is not None:
        return f"{_number(limit.value, 0)} m²"
    parts = [
        f"{translate('envelope.param.' + name, locale)} {_param_value(value, locale)}"
        for name, value in sorted(limit.params.items())
    ]
    return " · ".join(parts)


def _param_value(value: object, locale: Locale) -> str:
    if isinstance(value, bool):
        return translate("envelope.value." + ("yes" if value else "no"), locale)
    if isinstance(value, int | float):
        return _number(float(value), 2)
    if isinstance(value, list | tuple):
        return ", ".join(str(v) for v in value)
    return str(value)


def _source(citation: Any, locale: Locale) -> str:
    if citation is None or citation.page is None:
        return ""
    page = translate("sheet.page", locale, page=citation.page)
    return page if citation.quote_verified else f"{page} ({translate('sheet.unverified', locale)})"


def _provenance(envelope: EnvelopeOut, locale: Locale) -> str:
    p = envelope.provenance
    parts = [
        translate("sheet.engine", locale, version=envelope.engine_version),
        translate("sheet.hash", locale, hash=envelope.input_hash.removeprefix("sha256:")[:12]),
    ]
    if p.plan_title:
        parts.append(p.plan_title)
    if p.assumptions:
        parts.append(translate("sheet.assumptions", locale, items=", ".join(p.assumptions)))
    return " · ".join(parts)


def _number(value: float | None, digits: int) -> str:
    if value is None:
        return "?"
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


# ---------------------------------------------------------------------------
# Lageplan
# ---------------------------------------------------------------------------


def _plan_svg(envelope: EnvelopeOut) -> str:
    rings = [ring for ring in envelope.outline_local if ring]
    if not rings:
        return ""
    xs = [p[0] for ring in rings for p in ring]
    ys = [p[1] for ring in rings for p in ring]
    min_x, max_x = min(xs) - PLAN_MARGIN_M, max(xs) + PLAN_MARGIN_M
    min_y, max_y = min(ys) - PLAN_MARGIN_M, max(ys) + PLAN_MARGIN_M
    width, height = max_x - min_x, max_y - min_y
    layers = [
        _paths(_all_rings(envelope.parts), COLORS["part"], COLORS["part"], 0.0),
        _paths([ring for band in envelope.bands for ring in band.rings_local], "none", COLORS["band"], 0.15),
        _paths(
            _constraint_rings(envelope, "restricts"), COLORS["restricts"], COLORS["restricts"], 0.15, 0.35
        ),
        _paths(_constraint_rings(envelope, "no_build"), COLORS["no_build"], COLORS["no_build"], 0.15, 0.45),
        _paths(
            envelope.contours["lenient"].rings_local if "lenient" in envelope.contours else [],
            "none",
            COLORS["lenient"],
            0.3,
            dash="1.2 0.8",
        ),
        _paths(
            envelope.contours["strict"].rings_local if "strict" in envelope.contours else [],
            COLORS["strict"],
            COLORS["strict"],
            0.2,
            0.45,
        ),
        _paths(rings, "none", COLORS["outline"], 0.35),
        "".join(
            f'<polyline points="{_points(edge.coords_local)}" fill="none" '
            f'stroke="{COLORS["street"] if edge.kind == "street" else COLORS["outline"]}" '
            f'stroke-width="{0.5 if edge.kind == "street" else 0.25}" />'
            for edge in envelope.edges
            if edge.coords_local
        ),
    ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{PLAN_SIZE_MM[0]}mm" height="{PLAN_SIZE_MM[1]}mm" '
        f'viewBox="{min_x:.2f} {-max_y:.2f} {width:.2f} {height:.2f}">'
        f'<g transform="scale(1,-1)">{"".join(layers)}</g></svg>'
    )


def _all_rings(parts: list[PartOut]) -> list[list[list[float]]]:
    return [ring for part in parts for ring in part.rings_local]


def _constraint_rings(envelope: EnvelopeOut, effect: str) -> list[list[list[float]]]:
    return [ring for item in envelope.constraints if item.effect == effect for ring in item.rings_local]


def _paths(
    rings: list[list[list[float]]],
    fill: str,
    stroke: str,
    stroke_width: float,
    opacity: float = 1.0,
    dash: str | None = None,
) -> str:
    if not rings:
        return ""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return "".join(
        f'<polygon points="{_points(ring)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" '
        f'stroke-width="{stroke_width}"{dash_attr} />'
        for ring in rings
        if len(ring) >= 3
    )


def _points(ring: list[list[float]]) -> str:
    return " ".join(f"{p[0]:.2f},{p[1]:.2f}" for p in ring)


def render_pdf(envelope: EnvelopeOut, *, reference: str, locale: Locale = "fr") -> bytes:
    """HTML in ein PDF setzen (WeasyPrint im Worker, Plan 6.3)."""
    from weasyprint import HTML  # lokal: die Bibliothek lädt Schriften und gehört nicht in den API-Start

    document = HTML(string=render_html(envelope, reference=reference, locale=locale))
    return bytes(document.write_pdf())
