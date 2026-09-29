"""Bericht der Analyse als PDF (AN5, docs/PLAN_AN5_AUSGABE.md 3.6).

Die Projektakte des Büros: Kennzahlen, Lageplan, Gabarit mit Schnitten, Regeln je Zone mit Fundstelle und
Herkunft, Korrekturen mit Begründung (E-AN5-5), offene Punkte, Zusatzdokumente, Annahmen, Grundstück und Lage,
Unterlagen und Prüfsummen. Eine Vorlage in Python wie der Steckbrief, keine Vorlagenbibliothek (7.2).

Der Inhalt hängt nur an `ReportData`; deren Prüfsumme benennt den Bericht (`report_hash`). Gleicher Stand,
gleicher Bericht – für jede Person, deshalb nennt der Kopf keinen Bearbeiter (7.1 Nr. 19).
"""

import base64
import hashlib
import html
import json
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.analysis import drawing
from app.analysis.schemas import AnalysisOut, AnalysisPartOut, GabaritOut, SupplementAnalysisOut
from app.envelope.schemas import EnvelopeEdgeOut, EnvelopeOut, HeightsOut, SetbackOut
from app.platform.i18n import Locale, translate
from app.platform.organisations import HEX_COLOR, Branding
from app.rules.documents import SUPPLEMENT_WHOLE
from app.rules.format import reason_text, rule_value
from app.rules.schemas import ProjectOverrideOut, ProjectRegulationOut, ProjectRulesOut, RuleOut, ZoneRulesOut
from app.site.schemas import SiteOut

REPORT_VERSION = "an5-report-1"
"""Ändert sich Aufbau oder Inhalt des Berichts, entsteht mit der neuen Version ein neuer Bericht."""
STEEP_PERCENT = 5.0
"""Ab dieser Neigung fordert der Bericht, den Höhenbezug nach PLU zu prüfen (E-AN5-4)."""
HASH_CHARS = 12


@dataclass(frozen=True)
class ReportData:
    """Alles, was im Bericht steht, in der Form der API: Bericht und Oberfläche zeigen dieselben Werte."""

    branding: Branding | None
    """Erscheinungsbild der Organisation (AN6, docs/PLAN_AN6_MANDANTEN.md 3.5); None: Bericht wie vor AN6."""
    name: str | None
    note: str | None
    label: str
    site: SiteOut
    envelope: EnvelopeOut
    analysis: AnalysisOut
    rules: ProjectRulesOut
    overrides: list[ProjectOverrideOut]
    regulations: list[ProjectRegulationOut]


VOLATILE = {"runs", "cost_usd", "file_url", "source_url", "job_id", "updated_at"}
"""Felder ohne Einfluss auf den Inhalt; sie ändern sich ohne neuen Stand (Läufe, Adressen). `updated_at` setzt
der Baurahmen bei jeder Berechnung neu; die übrigen ändern sich nur mit Inhalten, die ohnehin eingehen."""


FILE_STEM_MAX = 60


def ascii_text(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").strip()


def file_stem(label: str) -> str:
    """Name oder Adresse auf ASCII vereinfacht, für Dateinamen von Bericht und DXF (3.4)."""
    stem = re.sub(r"[^A-Za-z0-9]+", "-", ascii_text(label)).strip("-")[:FILE_STEM_MAX].strip("-")
    return stem or "emprise-analyse"


def _stable(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: _stable(v) for k, v in value.items() if k not in VOLATILE}
    if isinstance(value, list):
        return [_stable(v) for v in value]
    return value


def report_hash(data: ReportData) -> str:
    """Prüfsumme über alles, was der Bericht zeigt (3.6), mit `REPORT_VERSION`; die Sprache steht daneben."""
    payload = {
        "version": REPORT_VERSION,
        "name": data.name,
        "note": data.note,
        "label": data.label,
        **{
            key: _stable(getattr(data, key).model_dump(mode="json"))
            for key in ("site", "envelope", "analysis", "rules")
        },
        "overrides": [_stable(o.model_dump(mode="json")) for o in data.overrides],
        "regulations": [_stable(r.model_dump(mode="json")) for r in data.regulations],
    }
    if data.branding is not None:
        # Nur mit Erscheinungsbild: Berichte ohne behalten ihre Prüfsumme (AN6, 7.1 Nr. 9)
        payload["branding_revision"] = data.branding.revision
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return "sha256:" + hashlib.sha256(raw.encode()).hexdigest()


# ---------------------------------------------------------------------------
# Hilfen
# ---------------------------------------------------------------------------


class _Text:
    def __init__(self, locale: Locale) -> None:
        self.locale = locale

    def __call__(self, key: str, **params: object) -> str:
        return translate(key, self.locale, **params)

    def e(self, key: str, **params: object) -> str:
        return html.escape(self(key, **params))


def _esc(value: object) -> str:
    return html.escape(str(value))


def _number(value: float | None, digits: int = 2) -> str:
    if value is None:
        return "?"
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")


def _m(value: float | None) -> str:
    return f"{_number(value, 2)} m"


def _m2(value: float | None) -> str:
    return f"{_number(value, 0)} m²"


def _short(value: str | None) -> str:
    return (value or "").removeprefix("sha256:")[:HASH_CHARS]


def _table(head: list[str], rows: list[list[str]], css: str = "") -> str:
    """Zeilen sind schon maskiert."""
    if not rows:
        return ""
    header = "".join(f"<th>{cell}</th>" for cell in head)
    body = "".join("<tr>" + "".join(f"<td>{cell}</td>" for cell in row) + "</tr>" for row in rows)
    return f'<table class="{css}"><thead><tr>{header}</tr></thead><tbody>{body}</tbody></table>'


def _pairs(rows: list[tuple[str, str]]) -> str:
    """Zweispaltige Tabelle (Bezeichnung, Wert); beides schon maskiert."""
    body = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows if v)
    return f'<table class="pairs">{body}</table>' if body else ""


# ---------------------------------------------------------------------------
# Abstände im Klartext (wie `frontend/src/analyse/abstand.ts`, EA10)
# ---------------------------------------------------------------------------


def _factor(factor: float) -> str:
    if abs(factor - 1) < 1e-6:
        return "H"
    inverse = 1 / factor
    if abs(inverse - round(inverse)) < 1e-6:
        return f"H/{round(inverse)}"
    return f"{_number(factor, 2)} × H"


def _height_for(heights: HeightsOut | None, basis: object) -> float | None:
    if heights is None:
        return None
    if basis == "eave" and heights.eave_m is not None:
        return heights.eave_m
    known = [v for v in (heights.ridge_m, heights.parapet_m, heights.eave_m) if v is not None]
    return max(known) if known else None


def distance_text(setback: SetbackOut, heights: HeightsOut | None, t: _Text) -> str:
    """„auf der Grenze zulässig, sonst mindestens 3,00 m“; nicht Ermitteltes bleibt „nicht ermittelt“."""
    if setback.status == "not_regulated":
        return t("report.distance.not_regulated")
    if setback.status != "effective":
        return t("report.distance.unknown")
    p = setback.params
    if setback.kind == "setback_street":
        mode = p.get("mode")
        if mode == "alignment":
            return t("report.distance.alignment")
        if mode == "fixed":
            return t("report.distance.fixed", value=_m(p.get("min_m")))
        if mode == "range":
            key = {"building": "range_building", "facade": "range_facade"}.get(str(p.get("band")), "range")
            return t(f"report.distance.{key}", min=_m(p.get("min_m")), max=_m(p.get("max_m")))
        return t("report.distance.min", value=_m(p.get("min_m")))
    factor = p.get("height_factor") if isinstance(p.get("height_factor"), int | float) else None
    minimum = p.get("min_m") if isinstance(p.get("min_m"), int | float) else None
    rest = ""
    if factor is not None:
        basis = t(f"report.basis.{p.get('height_basis') or 'undefined'}")
        rest = t("report.distance.factor", factor=_factor(float(factor)), basis=basis)
        if minimum is not None:
            rest += ", " + t("report.distance.at_least", value=_m(minimum))
        height = _height_for(heights, p.get("height_basis"))
        rest += " – " + (
            t("report.distance.height_unknown")
            if height is None
            else t(
                "report.distance.at_height",
                height=_m(height),
                value=_m(max(minimum or 0.0, float(factor) * height)),
            )
        )
    elif minimum is not None:
        rest = t("report.distance.min", value=_m(minimum))
    if not p.get("allow_on_boundary"):
        return rest or t("report.distance.unknown")
    limit = p.get("on_boundary_max_height_m")
    on_boundary = (
        t("report.distance.on_boundary_height", value=_m(limit))
        if isinstance(limit, int | float)
        else t("report.distance.on_boundary")
    )
    return t("report.distance.otherwise", first=on_boundary, second=rest) if rest else on_boundary


# ---------------------------------------------------------------------------
# Abschnitte
# ---------------------------------------------------------------------------


def _brand(branding: Branding | None) -> str:
    """Kopf der ersten Seite rechts: Logo, Name und Schriftfeld der Organisation (AN6, 3.5). Das Logo ist ein
    von Emprise neu geschriebenes PNG und kommt als data-URI, WeasyPrint lädt also nichts nach."""
    if branding is None:
        return ""
    logo = (
        f'<img class="brand-logo" src="data:image/png;base64,{base64.b64encode(branding.logo_png).decode()}">'
        if branding.logo_png
        else ""
    )
    lines = "".join(f"<div>{_esc(line)}</div>" for line in branding.contact_lines)
    return (
        f'<div class="brand">{logo}<div class="brand-name">{_esc(branding.display_name)}</div>'
        f'<div class="brand-lines">{lines}</div></div>'
    )


def _css_string(value: str) -> str:
    """Text für `content: "…"` in CSS: Backslash, Anführungszeichen und Zeilenumbrüche maskieren."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", " ")


def _head(data: ReportData, t: _Text, generated_at: datetime, report: str) -> str:
    site, analysis = data.site, data.analysis
    parcels = ", ".join(p.idu for p in site.parcels)
    meta = [
        (t.e("report.head.address"), _esc(site.address_label or "")),
        (t.e("report.head.parcels"), _esc(parcels)),
        (t.e("report.head.generated"), _esc(f"{generated_at:%d.%m.%Y %H:%M} UTC")),
        (t.e("report.head.status"), t.e(f"report.status.{analysis.status}")),
        (t.e("report.head.engine"), _esc(analysis.engine_version)),
        (t.e("report.head.hash"), _esc(_short(report))),
    ]
    note = f'<div class="note">{_esc(data.note)}</div>' if data.note else ""
    return (
        _brand(data.branding) + f'<div class="eyebrow">{t.e("report.eyebrow")}</div>'
        f"<h1>{_esc(data.label or t('report.untitled'))}</h1>"
        f"{_pairs(meta)}{note}"
        f'<div class="stamp">{t.e("report.disclaimer")}</div>'
    )


def _figures(data: ReportData, t: _Text) -> str:
    analysis, envelope = data.analysis, data.envelope
    rows: list[tuple[str, str]] = [(t.e("report.figures.site_area"), _esc(_m2(envelope.area_m2)))]
    for reading in ("lenient", "strict"):
        contour = envelope.contours.get(reading)
        if contour is not None:
            star = "" if contour.complete else " *"
            rows.append((t.e(f"report.figures.contour.{reading}"), _esc(_m2(contour.area_m2) + star)))
    part = next((p for p in analysis.parts if p.excluded is None), None)
    for reading in ("lenient", "strict"):
        total = analysis.footprint.get(reading)  # type: ignore[call-overload]
        if total is None:
            continue
        value = _m2(total.value_m2)
        footprint = part.footprint.get(reading) if part is not None else None  # type: ignore[call-overload]
        if footprint is not None and footprint.binding:
            value += " – " + t(f"report.figures.binding.{footprint.binding}")
        if not total.complete:
            value += " – " + t("report.figures.upper_bound")
        rows.append((t.e(f"report.figures.footprint.{reading}"), _esc(value)))
    if part is not None:
        rows.append((t.e("report.figures.storeys"), _esc(_storeys(part, t))))
    floor = analysis.floor_area
    if floor is not None:
        if floor.low_m2 is None and floor.high_m2 is None:
            value = t("report.value.not_determined")
        else:
            value = f"{_number(floor.low_m2, 0)} – {_number(floor.high_m2, 0)} m²"
            if floor.capped:
                value += " – " + t("report.figures.floor_capped")
            if not floor.complete:
                value += " – " + t("report.figures.upper_bound")
        rows.append((t.e("report.figures.floor_area"), _esc(value)))
    gabarit = analysis.gabarit
    if gabarit is not None:
        top = _m(gabarit.top_m) if gabarit.top_m is not None else t("report.value.not_determined")
        rows.append((t.e("report.figures.top"), _esc(top)))
    return f"<h2>{t.e('report.section.figures')}</h2>{_pairs(rows)}{_distances(data, t)}"


def _storeys(part: AnalysisPartOut, t: _Text) -> str:
    storeys = part.storeys
    if storeys.full_max is None:
        return t("report.value.not_determined")
    count = (
        str(storeys.full_max)
        if storeys.full_min in (None, storeys.full_max)
        else f"{storeys.full_min} – {storeys.full_max}"
    )
    if storeys.top != "none":
        count += " " + t(f"report.storeys.top.{storeys.top}" + ("" if storeys.top_certain else "_possible"))
    return f"{count} ({t('report.storeys.source.' + storeys.source)})"


def _edge_name(edge: EnvelopeEdgeOut, t: _Text) -> str:
    name = f"{t('report.edge.' + edge.kind)} {edge.seq}"
    return f"{name} · {edge.street_name}" if edge.street_name else name


def _distances(data: ReportData, t: _Text) -> str:
    heights = {part.zone_code: part.heights for part in data.envelope.parts}
    zones = len(heights) > 1
    rows = []
    for edge in data.envelope.edges:
        for setback in edge.setbacks:
            text = distance_text(setback, heights.get(setback.zone_code), t)
            prefix = f"{setback.zone_code}: " if zones else ""
            rows.append(
                [
                    _esc(_edge_name(edge, t)),
                    _esc(_m(edge.length_m)),
                    _esc(prefix + text),
                    _esc(_source(setback.citation, t)),
                ]
            )
    head = [
        t.e("report.distance.edge"),
        t.e("report.distance.length"),
        t.e("report.distance.rule"),
        t.e("report.col.source"),
    ]
    return f"<h3>{t.e('report.distance.title')}</h3>" + _table(head, rows)


def _source(citation: Any, t: _Text) -> str:
    if citation is None or getattr(citation, "page", None) is None:
        return ""
    page = t("report.page", page=citation.page)
    if getattr(citation, "from_scan", False):
        # Zitat aus einer per Texterkennung gelesenen Seite (AN7, PLAN_AN7_SCAN 3.3)
        page = f"{page} ({t('report.scan')})"
    return page if citation.quote_verified else f"{page} ({t('report.unverified')})"


def _legend(envelope: EnvelopeOut, t: _Text) -> str:
    """Nur, was der Lageplan zeigt."""
    contours = envelope.contours
    present = {
        "strict": "strict" in contours and bool(contours["strict"].rings_local),
        "lenient": "lenient" in contours and bool(contours["lenient"].rings_local),
        "band": any(band.rings_local for band in envelope.bands),
        "no_build": any(c.rings_local for c in envelope.constraints if c.effect == "no_build"),
        "restricts": any(c.rings_local for c in envelope.constraints if c.effect == "restricts"),
    }
    items = [
        f'<span><span class="swatch" style="background:{drawing.COLORS[key]}"></span>'
        f"{t.e('report.legend.' + key)}</span>"
        for key, shown in present.items()
        if shown
    ]
    return f'<div class="legend">{"".join(items)}</div>' if items else ""


def _plan(data: ReportData, t: _Text) -> str:
    svg = drawing.site_plan(data.envelope, t("report.section.plan"))
    note = t.e("report.plan.north_grid") if data.site.georeferenced else t.e("report.plan.north_sheet")
    title = t.e("report.section.plan")
    legend = _legend(data.envelope, t)
    return f'<h2>{title}</h2><div class="figure">{svg}</div>{legend}<p class="meta">{note}</p>'


def _differs(gabarit: GabaritOut) -> bool:
    for level in gabarit.levels:
        lenient, strict = level.contours.get("lenient"), level.contours.get("strict")
        if (lenient is None) != (strict is None):
            return True
        if (
            lenient
            and strict
            and (abs(lenient.area_m2 - strict.area_m2) > 0.005 or lenient.rings_local != strict.rings_local)
        ):
            return True
    return False


def _gabarit(data: ReportData, t: _Text) -> str:
    gabarit = data.analysis.gabarit
    title = f'<h2 class="page">{t.e("report.section.gabarit")}</h2>'
    if gabarit is None:
        return ""
    if gabarit.status == "unavailable":
        reason = t.e("report.gabarit.unavailable." + (gabarit.reason or "height_unknown"))
        return f'{title}<p class="meta">{reason}</p>'
    readings = ["lenient", "strict"] if _differs(gabarit) else ["lenient"]
    plans = "".join(
        f'<h3>{t.e("report.reading." + reading)}</h3><div class="figure">'
        + drawing.gabarit_plan(
            data.envelope, gabarit, data.analysis.sections, reading, t("report.section.gabarit")
        )
        + "</div>"
        for reading in readings
    )
    rows = []
    for level in gabarit.levels:
        cells = [
            _esc(f"{_number(level.from_m)} – {_number(level.to_m)} m")
            + (f'<br><span class="meta">{t.e("report.gabarit.roof")}</span>' if level.roof else "")
        ]
        for reading in ("lenient", "strict"):
            contour = level.contours.get(reading)
            cells.append(_esc(_m2(contour.area_m2) + ("" if contour.complete else " *")) if contour else "–")
        rows.append(cells)
    table = _table(
        [t.e("report.gabarit.level"), t.e("report.reading.lenient"), t.e("report.reading.strict")],
        rows,
        "num",
    )
    sections = "".join(
        f'<h3>{t.e("report.section.cut_" + section.key)}</h3><div class="figure">'
        + drawing.section_svg(section, gabarit, t, t("report.section.cut_" + section.key))
        + "</div>"
        for section in data.analysis.sections
    )
    terrain = any(section.terrain for section in data.analysis.sections)
    legend = (
        f'<p class="meta">{t.e("report.gabarit.legend")}'
        + (f" {t.e('report.gabarit.legend_terrain')}" if terrain else "")
        + "</p>"
        if sections
        else ""
    )
    return title + plans + table + sections + legend + _gabarit_notes(gabarit, t)


def _gabarit_notes(gabarit: GabaritOut, t: _Text) -> str:
    notes = [t("report.gabarit.note.reading")]
    slope = gabarit.terrain_slope_percent
    if gabarit.terrain_status != "ok" or slope is None:
        notes.append(t("report.gabarit.note.terrain_unknown"))
    else:
        reference = (
            _number(gabarit.reference_altitude_ngf) if gabarit.reference_altitude_ngf is not None else "?"
        )
        key = "terrain_steep" if slope > STEEP_PERCENT else "terrain"
        notes.append(t(f"report.gabarit.note.{key}", slope=_number(slope, 1), reference=reference))
    if any(level.roof for level in gabarit.levels):
        notes.append(t("report.gabarit.note.roof"))
    if gabarit.storey_height_m is not None:
        notes.append(t("report.gabarit.note.storeys", height=_number(gabarit.storey_height_m)))
    for reason in gabarit.reasons:
        if reason.startswith("height_unknown:"):
            notes.append(t("report.gabarit.note.height_unknown", zone=reason.split(":", 1)[1]))
    if any(
        level.contours.get("strict") and not level.contours["strict"].complete for level in gabarit.levels
    ):
        notes.append(t("report.gabarit.note.incomplete"))
    return "<ul>" + "".join(f"<li>{_esc(n)}</li>" for n in notes) + "</ul>"


def _rule_label(kind: str, building_kind: str, t: _Text) -> str:
    label = t(f"envelope.limit.{kind}")
    if building_kind not in ("main", "any"):
        label += f" ({t('envelope.building_kind.' + building_kind)})"
    return label


def _rule_value(kind: str, status: str, reason: str | None, params: dict[str, Any], t: _Text) -> str:
    return rule_value(kind, status, reason, params, t.locale)


def _quote(rule: RuleOut, t: _Text) -> str:
    if rule.page is None:
        return ""
    source = _esc(_source(rule, t))
    return source + (f'<div class="quote">«&#8239;{_esc(rule.quote)}&#8239;»</div>' if rule.quote else "")


def _zone(zone: ZoneRulesOut, data: ReportData, t: _Text) -> str:
    version = zone.version
    meta = [t(f"report.zone_status.{zone.status}"), f"{_number(zone.area_m2, 0)} m²"]
    if version is not None:
        meta.append(
            t(
                "report.rules.version",
                version=version.version,
                model=version.model or t("report.rules.office"),
                date=f"{version.created_at:%d.%m.%Y}",
            )
        )
    rows = [
        [
            _esc(_rule_label(rule.kind, rule.building_kind, t)),
            _esc(_rule_value(rule.kind, rule.status, rule.reason, rule.params, t)),
            _quote(rule, t),
            t.e(f"report.origin.{rule.origin}"),
        ]
        for rule in zone.rules
    ]
    head = [
        t.e("report.col.rule"),
        t.e("report.col.value"),
        t.e("report.col.source"),
        t.e("report.col.origin"),
    ]
    heading = t("report.rules.zone", code=zone.code) + (f" – {zone.label}" if zone.label else "")
    out = [f"<h3>{_esc(heading)}</h3>", f'<p class="meta">{_esc(" · ".join(meta))}</p>', _table(head, rows)]
    corrections = [o for o in data.overrides if o.zone_code == zone.code and o.active]
    if corrections:
        out.append(f"<h4>{t.e('report.rules.corrections')}</h4>")
        out.append(
            _table(
                [
                    t.e("report.col.rule"),
                    t.e("report.col.value"),
                    t.e("report.col.reason"),
                    t.e("report.col.source"),
                ],
                [
                    [
                        _esc(_rule_label(o.kind, o.building_kind, t)),
                        _esc(_rule_value(o.kind, o.status, None, o.params, t)),
                        _esc(o.note or t("report.rules.no_reason")),
                        _esc(
                            ", ".join(
                                x
                                for x in (
                                    o.source.document_title if o.source else None,
                                    t("report.page", page=o.source.page) if o.source else None,
                                )
                                if x
                            )
                        )
                        + (
                            f'<div class="quote">«&#8239;{_esc(o.source.quote)}&#8239;»</div>'
                            if o.source and o.source.quote
                            else ""
                        ),
                    ]
                    for o in corrections
                ],
            )
        )
    open_items = [
        f"{_rule_label(rule.kind, rule.building_kind, t)}: {reason_text(rule.reason, t.locale)}"
        + (f" – {rule.search_note}" if rule.search_note else "")
        for rule in zone.rules
        if rule.status == "unknown"
    ]
    if version is not None:
        open_items += [
            t("report.rules.open_passage", page=passage.page, text=passage.text[:160])
            for passage in version.open_passages
        ]
    out.append(f"<h4>{t.e('report.rules.open')}</h4>")
    out.append(
        "<ul>" + "".join(f"<li>{_esc(item)}</li>" for item in open_items) + "</ul>"
        if open_items
        else f'<p class="meta">{t.e("report.rules.none_open")}</p>'
    )
    if zone.hints:
        hints = [
            f"{_rule_label(h.kind, h.building_kind, t)}: "
            f"{_rule_value(h.kind, h.status, h.reason, h.params, t)} {_source(h, t)}"
            for h in zone.hints
        ]
        out.append(f"<h4>{t.e('report.rules.hints')}</h4>")
        out.append("<ul>" + "".join(f"<li>{_esc(hint.strip())}</li>" for hint in hints) + "</ul>")
    return "".join(out)


def _rules(data: ReportData, t: _Text) -> str:
    rules = data.rules
    title = f'<h2 class="page">{t.e("report.section.rules")}</h2>'
    if not rules.zones:
        return title + f'<p class="meta">{t.e("report.rules.none")}</p>'
    plan = f'<p class="meta">{_esc(rules.plan.title)}</p>' if rules.plan else ""
    return title + plan + "".join(_zone(zone, data, t) for zone in rules.zones)


def _scope(zone_code: str | None, t: _Text) -> str:
    """Zone des PLU („Uh“) oder Sektor eines Zusatzdokuments (`supplement_sector`: „Lot-12“ → „Lot 12“); das
    ganze Zusatzdokument braucht keinen Zusatz."""
    if not zone_code or zone_code == SUPPLEMENT_WHOLE:
        return ""
    if zone_code.startswith("Lot-"):
        return t("report.supplement.lot", lot=zone_code.removeprefix("Lot-"))
    return zone_code


def _supplement(item: SupplementAnalysisOut, t: _Text) -> str:
    scope = _scope(item.lot, t)
    heading = item.title + (f" – {scope}" if scope else "")
    rows = [
        [
            _esc(_rule_label(c.kind, c.building_kind, t)),
            _esc(_rule_value(c.kind, c.supplement.status, c.supplement.reason, c.supplement.params, t))
            + (f"<br>{_esc(_source(c.supplement.citation, t))}" if c.supplement.citation else ""),
            _esc(_rule_value(c.kind, c.plu.status, c.plu.reason, c.plu.params, t)) if c.plu else "–",
            t.e(f"report.verdict.{c.verdict}"),
        ]
        for c in item.comparisons
        if c.verdict in ("stricter", "mixed", "different", "only_supplement", "adopted", "unknown")
    ]
    head = [
        t.e("report.col.rule"),
        t.e("report.supplement.document"),
        t.e("report.supplement.plu"),
        t.e("report.col.verdict"),
    ]
    kind, status = t.e("report.supplement.type." + item.du_type), t.e("report.zone_status." + item.status)
    return f'<h3>{_esc(heading)}</h3><p class="meta">{kind} · {status}</p>' + (
        _table(head, rows) or f'<p class="meta">{t.e("report.supplement.nothing_stricter")}</p>'
    )


def _supplements(data: ReportData, t: _Text) -> str:
    items = data.analysis.supplements
    if not items:
        return ""
    return (
        f'<h2>{t.e("report.section.supplements")}</h2><p class="meta">{t.e("report.supplement.intro")}</p>'
        + "".join(_supplement(item, t) for item in items)
    )


def _assumptions(data: ReportData, t: _Text) -> str:
    analysis = data.analysis
    values = analysis.assumptions.values
    percent = {"wall_share", "attic_share", "attique_share"}
    rows = []
    for name in ("storey_height_m", "wall_share", "attic_share", "attique_share"):
        span = getattr(values, name)
        factor, digits = (100.0, 0) if name in percent else (1.0, 2)
        rows.append(
            (
                t.e(f"report.assumption.{name}"),
                _esc(f"{_number(span.low * factor, digits)} – {_number(span.high * factor, digits)}"),
            )
        )
    custom = (
        t.e("report.assumption.custom") if analysis.assumptions.custom else t.e("report.assumption.default")
    )
    not_counted = "".join(f"<li>{t.e('report.not_counted.' + key)}</li>" for key in analysis.not_counted)
    warnings = [t(f"report.warning.{w}") for w in analysis.warnings] + [
        t(f"envelope.warning.{w}") for w in data.envelope.warnings
    ]
    warning_list = "".join(f"<li>{_esc(w)}</li>" for w in warnings)
    return (
        f'<h2>{t.e("report.section.assumptions")}</h2><p class="meta">{custom}</p>{_pairs(rows)}'
        f"<h3>{t.e('report.not_counted.title')}</h3><ul>{not_counted}</ul>"
        + (f"<h3>{t.e('report.warnings')}</h3><ul>{warning_list}</ul>" if warnings else "")
    )


def _site(data: ReportData, t: _Text) -> str:
    site = data.site
    info = site.source_info
    position = info.get("position") or {}
    # Nach einem Scan nachgezeichnet (AN7, PLAN_AN7_SCAN 3.5): Datei und Maßstabsweg aus `trace`
    trace = info.get("trace") or {}
    origin = "traced" if trace else site.origin
    rows: list[tuple[str, str]] = [
        (t.e("report.site.origin"), t.e(f"report.origin_site.{origin}")),
        (t.e("report.site.area"), _esc(_m2(site.area_m2))),
        (t.e("report.site.file"), _esc(trace.get("file_name") or info.get("file_name") or "")),
    ]
    scale = trace.get("scale") or info.get("scale")
    if trace.get("scale_method") == "calibrated":
        length = _m(trace.get("reference_m"))
        rows.append((t.e("report.site.scale"), _esc(t("report.site.scale_calibrated", length=length))))
    elif scale:
        rows.append((t.e("report.site.scale"), _esc(f"1:{scale}")))
    if site.georeferenced:
        method = position.get("method") or ("cadastre" if site.origin == "parcel" else "file")
        rows.append((t.e("report.site.position"), t.e(f"report.site.position_{method}")))
        rows.append(
            (
                t.e("report.site.origin_l93"),
                _esc(
                    f"E {_number(site.local_origin.e, 3)} · N {_number(site.local_origin.n, 3)} (EPSG:2154)"
                ),
            )
        )
    else:
        rows.append((t.e("report.site.position"), t.e("report.site.position_none")))
    terrain = site.terrain
    if terrain.status == "ok":
        value = t(
            "report.site.terrain_value",
            reference=_number(terrain.reference_altitude_ngf),
            slope=_number(terrain.slope_percent, 1),
            samples=terrain.samples,
        )
    else:
        value = t(f"report.site.terrain_{terrain.status}")
    rows.append((t.e("report.site.terrain"), _esc(value)))
    risks = site.risks
    if risks.status == "ok" and risks.items:
        # Wie die Oberfläche (GelaendeRisiken): Art und Stufe aus `risk.*`, unbekannte Art mit Text der Quelle
        risk_rows = [
            [
                _esc(kind if (kind := t(f"risk.kind.{r.kind}")) != f"risk.kind.{r.kind}" else r.label),
                t.e(f"risk.level.{r.level}"),
                t.e(f"report.risk.scope.{r.scope}"),
            ]
            for r in risks.items
        ]
        risk_table = (
            f'<h3>{t.e("report.site.risks")}</h3><p class="meta">{t.e("report.site.risks_note")}</p>'
            + _table(
                [t.e("report.risk.kind"), t.e("report.risk.level_col"), t.e("report.risk.scope_col")],
                risk_rows,
            )
        )
    else:
        risk_table = (
            f'<p class="meta">{t.e("report.site.risks_" + risks.status)}</p>' if site.georeferenced else ""
        )
    return f"<h2>{t.e('report.section.site')}</h2>{_pairs(rows)}{risk_table}"


def _documents(data: ReportData, t: _Text, report: str) -> str:
    rows = []
    for link in data.regulations:
        document = link.document
        chapter = next((c for c in document.chapters if c.code == link.chapter_code), None)
        pages = (
            t("report.documents.pages", first=chapter.first_page, last=chapter.last_page) if chapter else ""
        )
        scope = _scope(link.zone_code, t)
        ocr = document.ocr
        # Seiten per Texterkennung gelesen (AN7, PLAN_AN7_SCAN 3.7)
        scanned = (
            f'<br><span class="meta">{t.e("report.documents.ocr", pages=ocr.pages_done)}</span>'
            if ocr is not None and ocr.state == "done" and ocr.pages_done
            else ""
        )
        rows.append(
            [
                t.e(f"report.documents.role.{link.role}"),
                _esc(document.title)
                + (f'<br><span class="meta">{_esc(document.file_name)}</span>' if document.file_name else "")
                + scanned,
                _esc(" · ".join(x for x in (scope, pages) if x)),
                _esc(_short(document.sha256)),
            ]
        )
    head = [
        t.e("report.documents.role_col"),
        t.e("report.documents.title"),
        t.e("report.documents.scope"),
        "SHA-256",
    ]
    versions = [
        (
            _esc(t("report.rules.zone", code=zone.code)),
            _esc(
                t(
                    "report.rules.version",
                    version=zone.version.version,
                    model=zone.version.model or t("report.rules.office"),
                    date=f"{zone.version.created_at:%d.%m.%Y}",
                )
            ),
        )
        for zone in data.rules.zones
        if zone.version is not None
    ]
    hashes = [
        (t.e("report.documents.hash_analysis"), _esc(_short(data.analysis.input_hash))),
        (t.e("report.documents.hash_envelope"), _esc(_short(data.envelope.input_hash))),
        (t.e("report.documents.hash_report"), _esc(_short(report))),
        (
            t.e("report.documents.engines"),
            _esc(f"{data.analysis.engine_version} · {data.envelope.engine_version} · {REPORT_VERSION}"),
        ),
    ]
    documents = _table(head, rows) if rows else f'<p class="meta">{t.e("report.documents.none")}</p>'
    return f"<h2>{t.e('report.section.documents')}</h2>{documents}{_pairs(versions)}{_pairs(hashes)}"


# ---------------------------------------------------------------------------
# Dokument
# ---------------------------------------------------------------------------

STYLE = """
@page { size: A4; margin: 16mm 14mm 20mm 14mm;
  @bottom-left { content: "%(footer)s"; font-size: 6.5pt; color: #6b7280; width: 75%%; }
  @bottom-right { content: "%(hash)s · " counter(page) "/" counter(pages); font-size: 6.5pt;
    color: #6b7280; } }
body { font-family: "DejaVu Sans", sans-serif; font-size: 8.5pt; color: #1f2933; line-height: 1.35; }
h1 { font-size: 16pt; margin: 0 0 3mm 0; }
h2 { font-size: 11pt; margin: 7mm 0 2mm 0; border-bottom: 0.3mm solid #1f2933; padding-bottom: 1mm; }
h2.page { break-before: page; margin-top: 0; }
h3 { font-size: 9.5pt; margin: 5mm 0 1.5mm 0; }
h4 { font-size: 8.5pt; margin: 3mm 0 1mm 0; color: #52606d; }
.eyebrow { font-size: 7.5pt; letter-spacing: 0.08em; text-transform: uppercase; color: #52606d; }
.meta { color: #52606d; font-size: 7.5pt; margin: 1mm 0; }
.note { margin: 2mm 0; padding: 2mm 3mm; background: #f3f4f6; white-space: pre-wrap; }
.stamp { margin: 3mm 0; padding: 2mm 3mm; background: #f6f1e7; border-left: 1mm solid #b08b4f;
  font-size: 8pt; }
table { width: 100%%; border-collapse: collapse; font-size: 7.5pt; margin: 1mm 0 2mm 0; }
th, td { text-align: left; vertical-align: top; padding: 1mm 1.5mm; border-bottom: 0.2mm solid #d9dde1; }
thead th { color: #52606d; font-weight: normal; }
table.pairs th { width: 38%%; color: #52606d; font-weight: normal; }
table.num td + td { text-align: right; }
tr { break-inside: avoid; }
.quote { color: #52606d; font-size: 6.8pt; font-style: italic; margin-top: 0.5mm; }
ul { margin: 1mm 0; padding-left: 5mm; }
.figure { margin: 2mm 0; break-inside: avoid; }
.legend span { margin-right: 4mm; font-size: 7pt; }
.swatch { display: inline-block; width: 3mm; height: 3mm; margin-right: 1mm; vertical-align: -0.3mm; }
.brand { float: right; width: 62mm; margin: 0 0 3mm 4mm; text-align: right; font-size: 7pt; color: #52606d; }
.brand-logo { max-width: 40mm; max-height: 16mm; margin-bottom: 1.5mm; }
.brand-name { font-size: 9pt; font-weight: bold; color: #1f2933; }
"""

BRAND_STYLE = """
@page { @top-right { content: "%(name)s"; font-size: 6.5pt; color: #6b7280; } }
"""
ACCENT_STYLE = """
h2 { border-bottom-color: %(color)s; }
.eyebrow, .brand-name { color: %(color)s; }
"""


def render_html(data: ReportData, *, locale: Locale, generated_at: datetime, report: str) -> str:
    """Vollständiges HTML des Berichts (3.6); mit Erscheinungsbild der Organisation deren Name in der
    Kopfzeile jeder Seite und die Akzentfarbe für Überschriften (AN6, 3.5)."""
    t = _Text(locale)
    footer = t("report.footer").replace('"', "'")
    style = STYLE % {"footer": footer, "hash": _short(report)}
    if data.branding is not None:
        style += BRAND_STYLE % {"name": _css_string(data.branding.display_name)}
        if data.branding.accent_color and HEX_COLOR.match(data.branding.accent_color):
            style += ACCENT_STYLE % {"color": data.branding.accent_color}
    body = "".join(
        [
            _head(data, t, generated_at, report),
            _figures(data, t),
            _plan(data, t),
            _gabarit(data, t),
            _rules(data, t),
            _supplements(data, t),
            _assumptions(data, t),
            _site(data, t),
            _documents(data, t, report),
        ]
    )
    return (
        f'<!DOCTYPE html><html lang="{locale}"><head><meta charset="utf-8">'
        f"<title>{_esc(data.label or t('report.untitled'))}</title><style>{style}</style></head>"
        f"<body>{body}</body></html>"
    )


def render_pdf(data: ReportData, *, locale: Locale, generated_at: datetime, report: str) -> bytes:
    """HTML in ein PDF setzen (WeasyPrint im Worker)."""
    from weasyprint import HTML  # lokal: die Bibliothek lädt Schriften und gehört nicht in den API-Start

    html_text = render_html(data, locale=locale, generated_at=generated_at, report=report)
    return bytes(HTML(string=html_text).write_pdf())
