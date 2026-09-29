"""Zeichnungen des Berichts als SVG (AN5, docs/PLAN_AN5_AUSGABE.md 3.6): Lageplan, Gabarit und Schnitte.

Serverseitig gezeichnet, damit der Bericht ohne Browser entsteht (L5). Lageplan und Gabarit folgen dem
Steckbrief (Farben aus `envelope/sheet.py`), der Schnitt dem der Oberfläche (`GabaritSchnitt.tsx`), dazu das
Geländeprofil. Koordinaten in Metern; im SVG zeigt y nach unten, deshalb wird Nord gespiegelt.
"""

import html
import math
from collections.abc import Callable, Sequence

from app.analysis.schemas import GabaritOut, SectionOut
from app.envelope.schemas import EnvelopeOut
from app.envelope.sheet import COLORS

Rings = Sequence[Sequence[Sequence[float]]]
Translate = Callable[..., str]

INK = COLORS["outline"]
MUTE = "#6b7280"
ACCENT = "#2f6f8f"
WARN = "#b45309"
TERRAIN = "#8a6d3b"
WIDTH_MM = 170.0
MAX_HEIGHT_MM = 125.0
SCALE_STEPS = (1, 2, 5, 10, 20, 50, 100, 200, 500)


def _number(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def _xy(point: Sequence[float]) -> str:
    return f"{point[0]:.2f},{-point[1]:.2f}"


def _path(rings: Rings) -> str:
    """Ringe als ein Pfad; mit `fill-rule="evenodd"` bleiben Löcher frei."""
    return "".join("M" + " L".join(_xy(p) for p in ring) + " Z" for ring in rings if len(ring) >= 3)


def _svg(bounds: tuple[float, float, float, float], body: str, label: str) -> str:
    """SVG in Blattbreite; `bounds` in Metern (min x, min y, max x, max y)."""
    min_x, min_y, max_x, max_y = bounds
    width, height = max(max_x - min_x, 1.0), max(max_y - min_y, 1.0)
    width_mm, height_mm = WIDTH_MM, WIDTH_MM * height / width
    if height_mm > MAX_HEIGHT_MM:
        width_mm, height_mm = MAX_HEIGHT_MM * width / height, MAX_HEIGHT_MM
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{html.escape(label)}" '
        f'width="{width_mm:.1f}mm" height="{height_mm:.1f}mm" '
        f'viewBox="{min_x:.2f} {-max_y:.2f} {width:.2f} {height:.2f}">{body}</svg>'
    )


def _text(x: float, y: float, value: str, size: float, colour: str = INK, anchor: str = "middle") -> str:
    """Text an (x, y) in Metern, y nach Norden."""
    return (
        f'<text x="{x:.2f}" y="{-y:.2f}" font-size="{size:.2f}" fill="{colour}" text-anchor="{anchor}" '
        f'font-family="DejaVu Sans, sans-serif">{html.escape(value)}</text>'
    )


def _frame(rings: Rings) -> tuple[float, float, float, float, float]:
    """Ausschnitt um die Ringe mit Rand; dazu die Größe als Maß für Strichstärken und Schrift."""
    xs = [p[0] for ring in rings for p in ring] or [0.0, 10.0]
    ys = [p[1] for ring in rings for p in ring] or [0.0, 10.0]
    size = max(max(xs) - min(xs), max(ys) - min(ys), 10.0)
    margin = max(4.0, size * 0.14)
    return min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin, size


def _north_and_scale(bounds: tuple[float, float, float, float], size: float) -> str:
    """Nordpfeil oben rechts (Blattoben = Gitternord in Lambert-93), Maßstabsleiste unten links."""
    min_x, min_y, max_x, max_y = bounds
    r = size / 30
    cx, cy = max_x - r * 2.2, max_y - r * 2.6
    arrow = (
        f'<circle cx="{cx:.2f}" cy="{-cy:.2f}" r="{r:.2f}" fill="none" stroke="{INK}" '
        f'stroke-width="{r * 0.05:.3f}"/>'
        f'<path d="M{cx:.2f},{-(cy + r):.2f} L{cx + r * 0.37:.2f},{-(cy - r * 0.6):.2f} '
        f'L{cx:.2f},{-(cy - r * 0.3):.2f} L{cx - r * 0.37:.2f},{-(cy - r * 0.6):.2f} Z" fill="{INK}"/>'
        + _text(cx, cy + r * 1.25, "N", r * 0.9)
    )
    wanted = (max_x - min_x) / 5
    length = min(SCALE_STEPS, key=lambda step: abs(step - wanted))
    x0, y0, bar = min_x + size * 0.04, min_y + size * 0.05, size / 120
    scale = (
        f'<rect x="{x0:.2f}" y="{-(y0 + bar):.2f}" width="{length:.2f}" height="{bar:.2f}" fill="{INK}"/>'
        + _text(x0, y0 + bar * 2.5, "0", size / 45, anchor="start")
        + _text(x0 + length, y0 + bar * 2.5, f"{length} m", size / 45)
    )
    return arrow + scale


def _layer(rings: Rings, fill: str, stroke: str, width: float, opacity: float = 1.0, dash: str = "") -> str:
    if not rings:
        return ""
    dash_attr = f' stroke-dasharray="{dash}"' if dash else ""
    return (
        f'<path d="{_path(rings)}" fill="{fill}" fill-opacity="{opacity}" fill-rule="evenodd" '
        f'stroke="{stroke}" stroke-width="{width:.3f}"{dash_attr}/>'
    )


def _cuts(sections: Sequence[SectionOut], size: float) -> str:
    out = []
    font = size / 32
    for section in sections:
        (x1, y1), (x2, y2) = section.start_local, section.end_local
        length = math.hypot(x2 - x1, y2 - y1) or 1.0
        ux, uy = (x2 - x1) / length, (y2 - y1) / length
        over = size * 0.05
        dash = f"{size / 40:.2f} {size / 120:.2f} {size / 300:.2f} {size / 120:.2f}"
        out.append(
            f'<line x1="{x1 - ux * over:.2f}" y1="{-(y1 - uy * over):.2f}" x2="{x2 + ux * over:.2f}" '
            f'y2="{-(y2 + uy * over):.2f}" stroke="{INK}" stroke-width="{size / 300:.3f}" '
            f'stroke-dasharray="{dash}"/>'
        )
        out.append(_text(x1 - ux * over * 1.8, y1 - uy * over * 1.8 - font / 3, section.key, font))
        out.append(_text(x2 + ux * over * 1.8, y2 + uy * over * 1.8 - font / 3, f"{section.key}'", font))
    return "".join(out)


def site_plan(envelope: EnvelopeOut, label: str) -> str:
    """Lageplan (3.6 Punkt 3): Grundstück, Kanten mit Nummer, Konturen, Bauband, Vorgaben, Nord, Maßstab."""
    outline = [ring for ring in envelope.outline_local if ring]
    if not outline:
        return ""
    *bounds_, size = _frame(outline)
    bounds = (bounds_[0], bounds_[1], bounds_[2], bounds_[3])

    def constraint(effect: str) -> list[list[list[float]]]:
        return [ring for item in envelope.constraints if item.effect == effect for ring in item.rings_local]

    contours = envelope.contours
    edges = []
    for edge in envelope.edges:
        if not edge.coords_local:
            continue
        street = edge.kind == "street"
        colour, width = (COLORS["street"], size / 120) if street else (INK, size / 250)
        edges.append(
            f'<polyline points="{" ".join(_xy(p) for p in edge.coords_local)}" fill="none" '
            f'stroke="{colour}" stroke-width="{width:.3f}"/>'
        )
        middle = edge.coords_local[len(edge.coords_local) // 2 - 1 : len(edge.coords_local) // 2 + 1]
        mx = sum(p[0] for p in middle) / len(middle)
        my = sum(p[1] for p in middle) / len(middle)
        az = math.radians(edge.normal_azimuth_deg)
        offset = size / 28
        edges.append(
            _text(
                mx + math.sin(az) * offset, my + math.cos(az) * offset - size / 110, str(edge.seq), size / 40
            )
        )
    body = "".join(
        [
            _layer([r for part in envelope.parts for r in part.rings_local], COLORS["part"], "none", 0),
            _layer(
                [r for band in envelope.bands for r in band.rings_local], "none", COLORS["band"], size / 300
            ),
            _layer(constraint("restricts"), COLORS["restricts"], COLORS["restricts"], size / 400, 0.35),
            _layer(constraint("no_build"), COLORS["no_build"], COLORS["no_build"], size / 400, 0.45),
            _layer(
                contours["lenient"].rings_local if "lenient" in contours else [],
                "none",
                COLORS["lenient"],
                size / 200,
                dash=f"{size / 80:.2f} {size / 120:.2f}",
            ),
            _layer(
                contours["strict"].rings_local if "strict" in contours else [],
                COLORS["strict"],
                COLORS["strict"],
                size / 300,
                0.45,
            ),
            _layer(outline, "none", INK, size / 170),
            *edges,
            _north_and_scale(bounds, size),
        ]
    )
    return _svg(bounds, body, label)


def gabarit_plan(
    envelope: EnvelopeOut, gabarit: GabaritOut, sections: Sequence[SectionOut], reading: str, label: str
) -> str:
    """Konturen der Höhenstufen einer Auslegung, höhere kräftiger, Dachstufen gestrichelt; Schnittlinien."""
    outline = [ring for ring in envelope.outline_local if ring]
    if not outline:
        return ""
    *bounds_, size = _frame(outline)
    bounds = (bounds_[0], bounds_[1], bounds_[2], bounds_[3])
    count = len(gabarit.levels)
    levels = []
    for index, level in enumerate(gabarit.levels):
        contour = level.contours.get(reading)  # type: ignore[call-overload]
        if contour is None:
            continue
        strength = 1.0 if count <= 1 else 0.35 + 0.65 * index / (count - 1)
        levels.append(
            f'<path d="{_path(contour.rings_local)}" fill="{ACCENT}" fill-opacity="0.07" fill-rule="evenodd" '
            f'stroke="{ACCENT}" stroke-opacity="{strength:.2f}" stroke-width="{size / 260:.3f}"'
            + (f' stroke-dasharray="{size / 90:.2f} {size / 140:.2f}"' if level.roof else "")
            + "/>"
        )
    body = (
        _layer(outline, "#ffffff", INK, size / 180)
        + "".join(levels)
        + _cuts(sections, size)
        + _north_and_scale(bounds, size)
    )
    return _svg(bounds, body, label)


def section_svg(section: SectionOut, gabarit: GabaritOut, t: Translate, label: str) -> str:
    """Schnitt mit Grenzen, Stufen beider Auslegungen, Abstandslinien, Höhen und Geländeprofil (3.3)."""
    top = gabarit.top_m if gabarit.top_m is not None else max([0.0, *(lv.to_m for lv in section.levels)])
    profile = section.terrain
    low = min([0.0, *(p[1] for p in profile)])
    high = max([0.0, *(p[1] for p in profile)])
    size = max(section.length_m, top + high - low, 10.0)
    font = size / 42
    left, right = -max(3.0, size * 0.1), section.length_m + max(3.0, size * 0.14)
    upper, lower = top + max(high, 0.0) + font * 3, low - font * 3.2
    parts: list[str] = []
    for reading, opacity in (("lenient", 0.1), ("strict", 0.3)):
        for level in section.levels:
            for a, b in level.intervals.get(reading, []):  # type: ignore[call-overload]
                parts.append(
                    f'<rect x="{a:.2f}" y="{-level.to_m:.2f}" width="{b - a:.2f}" '
                    f'height="{level.to_m - level.from_m:.2f}" fill="{ACCENT}" fill-opacity="{opacity}"/>'
                )
    if profile:
        line = " ".join(f"{s:.2f},{-dz:.2f}" for s, dz in profile)
        first, last = profile[0][0], profile[-1][0]
        base = low - font * 0.8
        parts.append(
            f'<polygon points="{first:.2f},{-base:.2f} {line} {last:.2f},{-base:.2f}" fill="{TERRAIN}" '
            f'fill-opacity="0.15"/>'
            f'<polyline points="{line}" fill="none" stroke="{TERRAIN}" stroke-width="{font * 0.1:.3f}" '
            f'stroke-dasharray="{font * 0.5:.2f} {font * 0.3:.2f}"/>'
        )
    # ±0,00: mit Profil nur noch als Bezugslinie gestrichelt
    parts.append(
        f'<line x1="{left:.2f}" y1="0" x2="{right:.2f}" y2="0" stroke="{INK}" '
        f'stroke-width="{font * 0.06:.3f}"'
        + (f' stroke-dasharray="{font * 0.2:.2f} {font * 0.4:.2f}"' if profile else "")
        + "/>"
    )
    for height_line in section.height_lines:
        y = height_line.height_m
        parts.append(
            f'<line x1="{height_line.start:.2f}" y1="{-y:.2f}" x2="{height_line.end:.2f}" y2="{-y:.2f}" '
            f'stroke="{MUTE}" stroke-width="{font * 0.05:.3f}" '
            f'stroke-dasharray="{font * 0.6:.2f} {font * 0.4:.2f}"/>'
        )
        text = f"{t('report.section.' + height_line.kind)} {_number(y)}{' *' if height_line.derived else ''}"
        parts.append(_text(height_line.end - font * 0.3, y + font * 0.3, text, font * 0.9, MUTE, "end"))
    for prospect in section.prospects:
        strict = prospect.reading == "strict"
        points = " ".join(f"{s:.2f},{-z:.2f}" for s, z in prospect.points)
        parts.append(
            f'<polyline points="{points}" fill="none" stroke="{WARN}" '
            f'stroke-width="{font * (0.09 if strict else 0.06):.3f}"'
            + ("" if strict else f' stroke-dasharray="{font * 0.3:.2f} {font * 0.3:.2f}"')
            + "/>"
        )
    for crossing in section.crossings:
        parts.append(
            f'<line x1="{crossing.s:.2f}" y1="{-(low - font * 0.8):.2f}" x2="{crossing.s:.2f}" '
            f'y2="{-(top + max(high, 0.0) + font):.2f}" stroke="{INK}" stroke-width="{font * 0.06:.3f}" '
            f'stroke-dasharray="{font * 0.25:.2f} {font * 0.25:.2f}"/>'
        )
        name = t("report.section.kind." + (crossing.kind or "other"))
        if crossing.edge_seq is not None:
            name += f" {crossing.edge_seq}"
        anchor = "start" if crossing.inward > 0 else "end"
        parts.append(_text(crossing.s, low - font * 2.2, name, font * 0.9, INK, anchor))
    for height in sorted({level.to_m for level in section.levels}):
        parts.append(
            f'<line x1="{left + font * 0.4:.2f}" y1="{-height:.2f}" x2="{left + font * 1.1:.2f}" '
            f'y2="{-height:.2f}" stroke="{MUTE}" stroke-width="{font * 0.06:.3f}"/>'
        )
        parts.append(
            _text(left + font * 1.3, height - font * 0.35, f"+{_number(height)}", font * 0.85, MUTE, "start")
        )
    parts.append(_text(left + font * 0.4, upper - font * 1.4, section.key, font * 1.2, INK, "start"))
    parts.append(_text(right - font * 0.4, upper - font * 1.4, f"{section.key}'", font * 1.2, INK, "end"))
    return _svg((left, lower, right, upper), "".join(parts), label)
