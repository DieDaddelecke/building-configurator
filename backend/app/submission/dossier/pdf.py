"""Projektbeschreibung als PDF (V 3.7; Spez. 5.10.6 gekürzt), allein aus dem Snapshot der Fassung.

Eine Vorlage für beide Sprachen, gesetzt mit WeasyPrint wie der Steckbrief (`envelope/sheet.py`). Jede Seite
trägt den Hinweis auf die unverbindliche Simulation (L7); Preise erscheinen nur als Spanne und Einzelposten,
nie als Gesamtpreis (L1).
"""

import html
from typing import Any

from app.plan.geometry import PLAN_MM, Edge, Plan, Ring, choose_scale
from app.platform.i18n import Locale
from app.submission.dossier import format as fmt

COLORS = {
    "outline": "#1f2933",
    "neighbour": "#c9ced4",
    "lenient": "#b9c6b1",
    "strict": "#6f8b5f",
    "street": "#2f6f8f",
    "house": "#d9c7a7",
    "projection": "#8a7a5c",
    "terrace": "#c8a97e",
    "carport": "#9aa5b1",
    "driveway": "#e4e0d8",
}
STATUS_ORDER = {"fail": 0, "unknown": 1, "hint": 2, "not_applicable": 3, "pass": 4}
QUOTE_CHARS = 300
PAGE_NOTE = "font-size: 7pt; color: #6b7280;"
CSS = """
body { font-family: "DejaVu Sans", sans-serif; font-size: 8.5pt; color: #1f2933; }
h1 { font-size: 15pt; margin: 0 0 2mm 0; }
h2 { font-size: 10pt; margin: 6mm 0 1.5mm 0; border-bottom: 0.3mm solid #1f2933; padding-bottom: 1mm; }
.meta { color: #52606d; font-size: 8pt; }
.stamp { margin: 3mm 0; padding: 2mm 3mm; background: #f6f1e7; border-left: 1mm solid #b08b4f;
  font-size: 8pt; }
.alert { color: #9b2c2c; font-weight: bold; }
table { width: 100%; border-collapse: collapse; font-size: 8pt; }
th, td { text-align: left; vertical-align: top; padding: 1mm 1.5mm; border-bottom: 0.2mm solid #d9dde1; }
th { color: #52606d; font-weight: normal; width: 38%; }
table.list th { width: auto; }
td.num { text-align: right; white-space: nowrap; }
.quote { color: #52606d; font-size: 7pt; }
ul { margin: 1mm 0; padding-left: 5mm; }
.legend span { margin-right: 3mm; font-size: 7pt; white-space: nowrap; }
.swatch { display: inline-block; width: 3mm; height: 3mm; margin-right: 1mm; vertical-align: -0.3mm; }
.scalebar { display: inline-block; height: 1.5mm; border: 0.2mm solid #1f2933; border-top: none;
  vertical-align: middle; }
"""


def _e(value: object) -> str:
    return html.escape(str(value))


def render_html(snapshot: dict[str, Any], plan: Plan, locale: Locale, attachments: list[str]) -> str:
    t = lambda key, **params: _e(fmt.tr(key, locale, **params))  # noqa: E731  kurze Hilfe
    number, sequence = snapshot["number"], snapshot["sequence"]
    title = fmt.tr("dossier.title", locale)
    sections = [
        _summary(snapshot, locale),
        _customer(snapshot, locale),
        _plan_section(snapshot, plan, locale),
        _site(snapshot, locale),
        _placement(snapshot, plan, locale),
        _checks(snapshot, locale),
        _areas(snapshot, locale),
        _costs(snapshot, locale),
        _energy(snapshot, locale),
        _closing(snapshot, plan, locale, attachments),
    ]
    return f"""<!DOCTYPE html>
<html lang="{locale}"><head><meta charset="utf-8"><title>{_e(title)} {_e(number)}</title>
<style>
@page {{ size: A4; margin: 16mm 14mm 18mm 14mm;
  @bottom-left {{ content: "{_e(number)} · {t("dossier.version", n=sequence)}"; {PAGE_NOTE} }}
  @bottom-center {{ content: "{t("dossier.footer")}"; {PAGE_NOTE} }}
  @bottom-right {{ content: counter(page) "/" counter(pages); {PAGE_NOTE} }} }}
{CSS}
</style></head><body>
<h1>{_e(title)}</h1>
<div class="meta">{_e(number)} · {t("dossier.version", n=sequence)}
 · {_e(fmt.date(snapshot["submitted_at"], locale))} · {_e(fmt.parcels(snapshot.get("site") or {}))}</div>
<div class="stamp">{t("dossier.simulation_notice")}</div>
{"".join(sections)}
</body></html>"""


def render_pdf(snapshot: dict[str, Any], plan: Plan, locale: Locale, attachments: list[str]) -> bytes:
    from weasyprint import HTML  # lokal: die Bibliothek lädt Schriften und gehört nicht in den API-Start

    return bytes(HTML(string=render_html(snapshot, plan, locale, attachments)).write_pdf())


# ---------------------------------------------------------------------------
# Abschnitte
# ---------------------------------------------------------------------------


def _rows(rows: list[tuple[str, str]]) -> str:
    return "<table>" + "".join(f"<tr><th>{_e(k)}</th><td>{v}</td></tr>" for k, v in rows) + "</table>"


def _h2(key: str, locale: Locale) -> str:
    return f"<h2>{_e(fmt.tr(key, locale))}</h2>"


def _names(snapshot: dict[str, Any], locale: Locale) -> dict[str, str]:
    catalog = snapshot.get("catalog") or {}
    items = [catalog.get("package"), *(catalog.get("options") or [])]
    return {str(i["slug"]): fmt.label(i, locale) or str(i["slug"]) for i in items if i}


def _summary(snapshot: dict[str, Any], locale: Locale) -> str:
    catalog = snapshot.get("catalog") or {}
    configuration = snapshot.get("configuration") or {}
    type_ = catalog.get("type") or {}
    facts = (configuration.get("fit") or {}).get("facts") or {}
    package = catalog.get("package")
    options = catalog.get("options") or []
    retired = [
        fmt.label(item, locale) or type_.get("name")
        for item in [type_ if type_ else None, package, *options]
        if item and item.get("status") == "retired"
    ]
    option_text = ", ".join(
        (fmt.label(o, locale) or o["slug"])
        + (f" ({fmt.tr('dossier.included', locale)})" if o.get("included") else "")
        for o in options
    )
    deviations = len(snapshot.get("deviations") or [])
    rows = [
        (fmt.tr("dossier.type", locale), _e(f"{type_.get('name', '–')} · v{type_.get('version', '–')}")),
        (fmt.tr("dossier.package", locale), _e(fmt.label(package, locale) or fmt.tr("dossier.none", locale))),
        (fmt.tr("dossier.options", locale), _e(option_text or fmt.tr("dossier.none", locale))),
        (
            fmt.tr("dossier.facts", locale),
            _e(
                fmt.tr(
                    "dossier.facts_value",
                    locale,
                    living=fmt.number(facts.get("living_area_m2"), locale, 0),
                    footprint=fmt.number(facts.get("footprint_m2"), locale, 0),
                    ridge=fmt.number(facts.get("ridge_height_m"), locale, 2),
                    eave=fmt.number(facts.get("eave_height_m"), locale, 2),
                    storeys=facts.get("storeys", "–"),
                )
            ),
        ),
        (
            fmt.tr("dossier.costs.title", locale),
            _e(fmt.costs_text(configuration.get("costs"), locale))
            + f'<div class="quote">{_e(fmt.tr("dossier.costs.hint", locale))}</div>',
        ),
        (
            fmt.tr("dossier.deviations", locale),
            # Abweichungen gibt es nur mit Bestätigung des Kunden (V 3.4)
            f'<span class="alert">{deviations}</span> · {_e(fmt.tr("dossier.acknowledged", locale))}'
            if deviations
            else "0",
        ),
        (fmt.tr("dossier.open_points", locale), _e(snapshot.get("open_points", 0))),
    ]
    if retired:
        rows.append((fmt.tr("dossier.retired", locale), _e(", ".join(str(r) for r in retired))))
    return _h2("dossier.section.summary", locale) + _rows(rows)


def _yes_no(value: object, locale: Locale) -> str:
    key = {True: "yes", False: "no", "yes": "yes", "no": "no"}.get(value, "unknown")
    return fmt.tr(f"dossier.answer.{key}", locale)


def _customer(snapshot: dict[str, Any], locale: Locale) -> str:
    customer = snapshot.get("customer") or {}
    rows = [
        (fmt.tr("dossier.customer.name", locale), _e(customer.get("name") or "–")),
        (fmt.tr("dossier.customer.email", locale), _e(customer.get("email") or "–")),
        (fmt.tr("dossier.customer.phone", locale), _e(customer.get("phone") or "–")),
        (fmt.tr("dossier.customer.start", locale), _e(customer.get("desired_start") or "–")),
        (
            fmt.tr("dossier.customer.financing", locale),
            _e(_yes_no(customer.get("financing_clarified"), locale)),
        ),
        (fmt.tr("dossier.customer.lotissement", locale), _e(_yes_no(customer.get("lotissement"), locale))),
    ]
    consents = "".join(
        f"<li>{_e(c['legal_text_key'])} v{_e(c['legal_text_version'])} · "
        f"{_e(fmt.date(c['confirmed_at'], locale))}</li>"
        for c in snapshot.get("consents") or []
    )
    return (
        _h2("dossier.section.customer", locale)
        + _rows(rows)
        + f'<div class="meta">{_e(fmt.tr("dossier.consents", locale))}</div><ul class="quote">{consents}</ul>'
    )


def _plan_section(snapshot: dict[str, Any], plan: Plan, locale: Locale) -> str:
    scale = choose_scale(plan)
    min_x, min_y, max_x, max_y = plan.bounds()
    width_mm = (max_x - min_x) * 1000 / scale
    height_mm = (max_y - min_y) * 1000 / scale
    shrink = min(1.0, PLAN_MM[0] / width_mm, PLAN_MM[1] / height_mm)
    width_mm, height_mm = width_mm * shrink, height_mm * shrink
    approximate = shrink < 1.0
    bar_m = next((m for m in (5, 10, 20, 50, 100, 200) if m * 1000 / scale * shrink >= 15), 200)
    scale_text = fmt.tr("dossier.plan.scale_approx" if approximate else "dossier.plan.scale", locale, n=scale)
    north = (
        fmt.tr(
            "dossier.plan.north",
            locale,
            deg=fmt.number(plan.convergence_deg or 0.0, locale, 1),
        )
        if plan.georeferenced
        else fmt.tr("dossier.plan.no_geo", locale)
    )
    bar_mm = bar_m * 1000 / scale * shrink
    return (
        _h2("dossier.section.plan", locale)
        + _svg(plan, scale / shrink, width_mm, height_mm)
        + f'<div class="legend">{_legend(locale)}</div>'
        + f'<div class="meta">{_e(scale_text)} · <span class="scalebar" style="width:{bar_mm:.1f}mm">'
        + f"</span> {bar_m} m · {_e(north)}</div>"
    )


def _legend(locale: Locale) -> str:
    items = [
        ("house", "dossier.legend.house"),
        ("terrace", "dossier.legend.terrace"),
        ("carport", "dossier.legend.carport"),
        ("driveway", "dossier.legend.driveway"),
        ("strict", "dossier.legend.strict"),
        ("lenient", "dossier.legend.lenient"),
        ("street", "dossier.legend.street"),
    ]
    return "".join(
        f'<span><span class="swatch" style="background:{COLORS[c]}"></span>{_e(fmt.tr(k, locale))}</span>'
        for c, k in items
    )


def _points(ring: Ring) -> str:
    return " ".join(f"{x:.2f},{y:.2f}" for x, y in ring)


def _svg(plan: Plan, scale: float, width_mm: float, height_mm: float) -> str:
    min_x, min_y, max_x, max_y = plan.bounds()
    unit = scale / 1000  # Meter je Millimeter Papier

    def polygons(
        rings: list[Ring], fill: str, stroke: str, width_mm_: float, opacity: float = 1.0, dash: str = ""
    ) -> str:
        dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
        return "".join(
            f'<polygon points="{_points(r)}" fill="{fill}" fill-opacity="{opacity}" stroke="{stroke}" '
            f'stroke-width="{width_mm_ * unit:.3f}"{dash_attr} />'
            for r in rings
            if len(r) >= 3
        )

    def label(edge: Edge) -> str:
        color = COLORS["street"] if edge.kind == "street" else COLORS["outline"]
        x = sum(p[0] for p in edge.coords) / len(edge.coords)
        y = sum(p[1] for p in edge.coords) / len(edge.coords)
        # Doppelt gespiegelt (Gruppe und Text), damit die Nummer aufrecht steht
        return (
            f'<text x="{x:.2f}" y="{-y:.2f}" transform="scale(1,-1)" font-size="{2.2 * unit:.2f}" '
            f'fill="{color}" text-anchor="middle">{edge.seq}</text>'
        )

    labels = "".join(label(e) for e in plan.edges if e.coords)
    layers = [
        polygons(plan.neighbour_parcels, "none", COLORS["neighbour"], 0.15),
        polygons(plan.neighbour_buildings, COLORS["neighbour"], COLORS["neighbour"], 0.1, 0.6),
        polygons(plan.parcel, "#faf8f3", COLORS["outline"], 0.35),
        polygons(plan.lenient, "none", COLORS["lenient"], 0.3, dash=f"{1.2 * unit:.2f} {0.8 * unit:.2f}"),
        polygons(plan.strict, COLORS["strict"], COLORS["strict"], 0.2, 0.3),
        polygons(plan.driveways, COLORS["driveway"], COLORS["outline"], 0.15),
        polygons([plan.terrace] if plan.terrace else [], COLORS["terrace"], COLORS["outline"], 0.2),
        polygons([plan.carport] if plan.carport else [], COLORS["carport"], COLORS["outline"], 0.2, 0.8),
        polygons(
            [plan.projection] if plan.projection else [],
            "none",
            COLORS["projection"],
            0.2,
            dash=f"{0.8 * unit:.2f} {0.6 * unit:.2f}",
        ),
        polygons([plan.facade] if plan.facade else [], COLORS["house"], COLORS["outline"], 0.4),
        "".join(
            f'<polyline points="{_points(e.coords)}" fill="none" stroke="{COLORS["street"]}" '
            f'stroke-width="{0.7 * unit:.3f}" />'
            for e in plan.edges
            if e.kind == "street"
        ),
        labels,
    ]
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width_mm:.1f}mm" height="{height_mm:.1f}mm" '
        f'viewBox="{min_x:.2f} {-max_y:.2f} {max_x - min_x:.2f} {max_y - min_y:.2f}" overflow="hidden">'
        f'<g transform="scale(1,-1)">{"".join(layers)}</g></svg>'
    )


def _site(snapshot: dict[str, Any], locale: Locale) -> str:
    site = snapshot.get("site") or {}
    parcels = "".join(
        f"<tr><td>{_e(p['idu'])}</td><td>{_e(p['section'])} {_e(int(p['number']))}</td>"
        f'<td class="num">{_e(fmt.number(p.get("area_official_m2"), locale, 0))} m²</td>'
        f'<td class="num">{_e(fmt.number(p.get("area_geometric_m2"), locale, 0))} m²</td>'
        f"<td>{_e(p.get('accuracy_class', ''))}</td></tr>"
        for p in site.get("parcels") or []
    )
    edges = "".join(
        f"<tr><td>{_e(fmt.edge_name(e['kind'], e['seq'], locale))}</td>"
        f"<td>{_e(fmt.tr('dossier.source.' + str(e.get('classification_source')), locale))}</td>"
        f'<td class="num">{_e(fmt.number(e.get("length_m"), locale, 2))} m</td>'
        f"<td>{_e(e.get('street_name') or '')}</td></tr>"
        for e in site.get("edges") or []
    )
    terrain = site.get("terrain") or {}

    def risk(item: dict[str, Any]) -> str:
        kind = f"risk.kind.{item.get('kind')}"
        name = fmt.tr(kind, locale) if fmt.known(kind, locale) else str(item.get("label") or item.get("kind"))
        level = fmt.tr(f"risk.level.{item.get('level')}", locale)
        scope = f" · {fmt.tr('dossier.site.commune', locale)}" if item.get("scope") == "commune" else ""
        return f"<li>{_e(name)}: {_e(level)}{_e(scope)}</li>"

    risks = "".join(risk(r) for r in (site.get("risks") or {}).get("items") or [])
    header = lambda *keys: "".join(f"<th>{_e(fmt.tr(k, locale))}</th>" for k in keys)  # noqa: E731
    out = _h2("dossier.section.site", locale)
    if parcels:
        out += (
            '<table class="list"><tr>'
            + header(
                "dossier.site.idu",
                "dossier.site.parcel",
                "dossier.site.official",
                "dossier.site.geometric",
                "dossier.site.accuracy",
            )
            + f"</tr>{parcels}</table>"
        )
    else:
        out += f'<div class="meta">{_e(fmt.tr("dossier.plan.no_geo", locale))}</div>'
    out += (
        '<table class="list"><tr>'
        + header("dossier.site.edge", "dossier.site.source", "dossier.site.length", "dossier.site.street")
        + f"</tr>{edges}</table>"
    )
    out += _rows(
        [
            (fmt.tr("dossier.site.area", locale), _e(f"{fmt.number(site.get('area_m2'), locale, 0)} m²")),
            (
                fmt.tr("dossier.site.terrain", locale),
                _e(
                    fmt.tr(
                        f"dossier.terrain.{terrain.get('status', 'unavailable')}",
                        locale,
                        slope=fmt.number(terrain.get("slope_percent"), locale, 1),
                        altitude=fmt.number(terrain.get("reference_altitude_ngf"), locale, 1),
                    )
                ),
            ),
        ]
    )
    if risks:
        out += f'<div class="meta">{_e(fmt.tr("dossier.site.risks", locale))}</div><ul>{risks}</ul>'
    return out


def _placement(snapshot: dict[str, Any], plan: Plan, locale: Locale) -> str:
    configuration = snapshot.get("configuration") or {}
    evaluation = configuration.get("evaluation") or {}
    rows: list[tuple[str, str]] = []
    if plan.house_origin is not None:
        east, north = plan.house_origin
        if plan.georeferenced:
            east, north = east + plan.origin[0], north + plan.origin[1]
            key = "dossier.placement.origin_l93"
        else:
            key = "dossier.placement.origin_local"
        rows.append(
            (fmt.tr(key, locale), _e(f"E {fmt.number(east, locale, 2)} · N {fmt.number(north, locale, 2)}"))
        )
        rows.append(
            (fmt.tr("dossier.placement.rotation", locale), _e(f"{fmt.number(plan.rotation_deg, locale, 1)}°"))
        )
    orientation = configuration.get("orientation") or {}
    for role, azimuth in sorted((orientation.get("facades") or {}).items()):
        if role in ("garden", "street"):
            rows.append(
                (
                    fmt.tr(f"dossier.placement.facade_{role}", locale),
                    _e(f"{fmt.compass(float(azimuth), locale)} ({fmt.number(float(azimuth), locale, 0)}°)"),
                )
            )

    def required(edge: dict[str, Any]) -> str:
        value = edge.get("required_m")
        return f"{fmt.number(value, locale, 2)} m" if value is not None else "–"

    edges = "".join(
        f"<tr><td>{_e(fmt.edge_name(e['kind'], e['seq'], locale))}</td>"
        f'<td class="num">{_e(fmt.number(e.get("measured_m"), locale, 2))} m</td>'
        f'<td class="num">{_e(required(e))}</td>'
        f"<td>{_e(fmt.tr('check_status.' + str(e.get('status')), locale))}</td></tr>"
        for e in evaluation.get("edges") or []
    )
    header = "".join(
        f"<th>{_e(fmt.tr(k, locale))}</th>"
        for k in (
            "dossier.site.edge",
            "dossier.placement.measured",
            "dossier.placement.required",
            "dossier.status",
        )
    )
    return (
        _h2("dossier.section.placement", locale)
        + _rows(rows)
        + (f'<table class="list"><tr>{header}</tr>{edges}</table>' if edges else "")
    )


def _checks(snapshot: dict[str, Any], locale: Locale) -> str:
    configuration = snapshot.get("configuration") or {}
    seen: set[tuple[Any, ...]] = set()
    checks: list[dict[str, Any]] = []
    for source in (
        (configuration.get("fit") or {}).get("reasons") or [],
        (configuration.get("evaluation") or {}).get("checks") or [],
        (configuration.get("compliance") or {}).get("checks") or [],
    ):
        for check in source:
            key = (
                check["code"],
                check.get("zone_code"),
                check.get("edge_seq"),
                (check.get("params") or {}).get("subject"),
            )
            if key not in seen:
                seen.add(key)
                checks.append(check)
    checks.sort(key=lambda c: STATUS_ORDER.get(c["status"], 5))
    names = _names(snapshot, locale)
    rows = []
    for check in checks:
        citation = check.get("citation") or {}
        quote = str(citation.get("quote") or "")
        if len(quote) > QUOTE_CHARS:
            quote = quote[:QUOTE_CHARS] + " …"
        source = ""
        if citation.get("page"):
            source = fmt.tr("dossier.page", locale, page=citation["page"])
            if not citation.get("quote_verified"):
                source += f" ({fmt.tr('dossier.unverified', locale)})"
        status = fmt.tr(f"check_status.{check['status']}", locale)
        binding = fmt.tr("dossier.binding" if check.get("binding") else "dossier.not_binding", locale)
        css = ' class="alert"' if check["status"] == "fail" and check.get("binding") else ""
        rows.append(
            f"<tr><td{css}>{_e(fmt.check_text(check, locale, names))}"
            + (f'<div class="quote">{_e(source)} {_e(quote)}</div>' if source or quote else "")
            + f"</td><td>{_e(status)}</td><td>{_e(binding)}</td></tr>"
        )
    header = "".join(
        f"<th>{_e(fmt.tr(k, locale))}</th>"
        for k in ("dossier.check", "dossier.status", "dossier.binding_col")
    )
    body = f'<table class="list"><tr>{header}</tr>{"".join(rows)}</table>' if rows else ""
    return _h2("dossier.section.checks", locale) + (
        body or f'<div class="meta">{_e(fmt.tr("dossier.none", locale))}</div>'
    )


def _areas(snapshot: dict[str, Any], locale: Locale) -> str:
    areas = (snapshot.get("configuration") or {}).get("areas")
    if not areas:
        return ""
    keys = ["site", "house", "carport", "terrace", "driveway", "paths", "emprise", "sealed", "unsealed"]
    rows = [
        (fmt.tr(f"area.{k}", locale), _e(f"{fmt.number(areas.get(f'{k}_m2'), locale, 1)} m²"))
        for k in keys
        if areas.get(f"{k}_m2") or k in ("site", "house", "emprise", "sealed", "unsealed")
    ]
    return _h2("dossier.section.areas", locale) + _rows(rows)


def _costs(snapshot: dict[str, Any], locale: Locale) -> str:
    costs = (snapshot.get("configuration") or {}).get("costs")
    if not costs:
        return ""
    rows = []
    for item in costs.get("items") or []:
        label = fmt.label(item, locale) or fmt.tr(f"dossier.cost_kind.{item['kind']}", locale)
        if item.get("included"):
            amount = fmt.tr("dossier.included", locale)
        elif item["min_cents"] == item["max_cents"]:
            amount = fmt.money(item["min_cents"], locale)
        else:
            amount = f"{fmt.money(item['min_cents'], locale)} – {fmt.money(item['max_cents'], locale)}"
        detail = ""
        if item.get("quantity") and item.get("unit_price_cents"):
            unit = {"m2": "m²", "m3": "m³"}.get(str(item.get("unit")), str(item.get("unit") or ""))
            quantity = f"{fmt.number(item['quantity'], locale, 1)} {unit}"
            detail = (
                f'<div class="quote">{_e(quantity)} × {_e(fmt.money(item["unit_price_cents"], locale))}</div>'
            )
        rows.append(f'<tr><td>{_e(label)}{detail}</td><td class="num">{_e(amount)}</td></tr>')
    summary = _rows(
        [
            (fmt.tr("dossier.costs.title", locale), _e(fmt.costs_text(costs, locale))),
            (
                fmt.tr("dossier.costs.basis", locale),
                _e(
                    fmt.tr(
                        "dossier.costs.basis_value",
                        locale,
                        vat=fmt.number((costs.get("vat_rate") or 0) * 100, locale, 1),
                        version=costs.get("catalog_version") or "–",
                    )
                ),
            ),
        ]
    )
    return (
        _h2("dossier.section.costs", locale)
        + f'<table class="list">{"".join(rows)}</table>'
        + summary
        + f'<div class="quote">{_e(fmt.tr("dossier.costs.hint", locale))}</div>'
    )


def _energy(snapshot: dict[str, Any], locale: Locale) -> str:
    energy = (snapshot.get("configuration") or {}).get("energy")
    if not energy:
        return ""
    rows = [
        (fmt.tr("dossier.energy.status", locale), _e(fmt.tr(f"dossier.energy.{energy['status']}", locale))),
        (fmt.tr("dossier.energy.zone", locale), _e(energy.get("climate_zone") or "–")),
    ]
    if energy.get("verdict"):
        rows.append((fmt.tr("dossier.energy.verdict", locale), _e(energy["verdict"])))
    if energy.get("measures"):
        rows.append((fmt.tr("dossier.energy.measures", locale), _e(energy["measures"])))
    return _h2("dossier.section.energy", locale) + _rows(rows)


def _closing(snapshot: dict[str, Any], plan: Plan, locale: Locale, attachments: list[str]) -> str:
    notices = "".join(f"<li>{_e(fmt.tr(f'dossier.notice.{i}', locale))}</li>" for i in range(1, 6))
    rules = snapshot.get("rules") or {}
    plan_title = (rules.get("plan") or {}).get("title")
    engine = snapshot.get("engine") or {}
    provenance = " · ".join(
        part
        for part in (
            plan_title,
            fmt.tr(
                "dossier.engine",
                locale,
                configuration=engine.get("configuration"),
                dossier=engine.get("dossier"),
            ),
            fmt.tr("dossier.stamp", locale, stamp=snapshot.get("review_stamp")),
        )
        if part
    )
    sources = f'<div class="meta">{_e(fmt.tr("dossier.sources", locale))}</div>' if plan.georeferenced else ""
    files = "".join(f"<li>{_e(name)}</li>" for name in attachments)
    return (
        _h2("dossier.section.notes", locale)
        + f"<ul>{notices}</ul>"
        + sources
        + f'<div class="quote">{_e(provenance)}</div>'
        + (
            f'<div class="meta">{_e(fmt.tr("dossier.attachments", locale))}</div><ul>{files}</ul>'
            if files
            else ""
        )
    )
