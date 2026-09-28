"""Korrigieren und begründen (AN4, docs/PLAN_AN4_KORREKTUR.md): Formularbeschreibung der Regelarten und
Übernahme aus Zusatzdokumenten – reine Fachlogik ohne Datenbank."""

from dataclasses import replace
from typing import get_args

from app.analysis.domain.analyse import SupplementInput, analyse
from app.analysis.domain.compare import compare, compare_rule, merge_stricter, stricter_kinds
from app.analysis.domain.parameters import DEFAULTS
from app.envelope.domain.derive import derive_envelope
from app.envelope.domain.inputs import Citation, EnvelopeInput
from app.rules.domain.form import UNITS, kind_forms
from app.rules.domain.kinds import BOUNDS, PARAM_MODELS, PARAM_TYPES, RuleKind, validate_params
from app.rules.schemas import RuleKindFormOut
from tests.envelope_support import edges_of_rectangle, envelope_input, rectangle, rule, site, ub_rules, zone

# ---------------------------------------------------------------------------
# Formularbeschreibung (3.1)
# ---------------------------------------------------------------------------


def test_every_kind_and_parameter_is_described() -> None:
    forms = {form.kind: form for form in kind_forms()}
    assert set(forms) == set(PARAM_MODELS) == set(get_args(RuleKind))
    for kind, model in PARAM_MODELS.items():
        assert [p.name for p in forms[kind].params] == list(model.model_fields)
    # Dieselben Typen wie im Ausgabeschema des Modells (eine Quelle, RW15)
    expected = {"number": {"number"}, "flag": {"flag"}, "items": {"items"}, "text": {"text", "choice"}}
    for form in forms.values():
        for param in form.params:
            assert param.type in expected[PARAM_TYPES[param.name]], (form.kind, param.name)
            if param.type == "number":
                assert param.unit == UNITS.get(param.name)
                assert (param.min, param.max) == BOUNDS.get(param.name, (None, None))
            else:
                assert param.unit is None
            if param.type in ("choice", "items") and param.name not in ("counting",):
                assert param.options, (form.kind, param.name)
    # Die Beschreibung passt in das Schema der API
    for form in kind_forms():
        RuleKindFormOut.model_validate(
            {
                "kind": form.kind,
                "building_specific": form.building_specific,
                "mandatory": form.mandatory,
                "params": [p.__dict__ for p in form.params],
            }
        )


def test_form_details_of_typical_kinds() -> None:
    forms = {form.kind: {p.name: p for p in form.params} for form in kind_forms()}
    ratio = forms["max_footprint_ratio"]["ratio"]
    assert (ratio.type, ratio.required, ratio.unit, ratio.min, ratio.max) == (
        "number",
        True,
        "share",
        0.0,
        1.0,
    )
    mode = forms["setback_street"]["mode"]
    assert (mode.type, mode.default, mode.options) == (
        "choice",
        "min",
        ("min", "fixed", "range", "alignment"),
    )
    assert forms["setback_street"]["band"].default is None
    assert forms["roof"]["allowed_forms"].type == "items"
    assert "gable" in forms["roof"]["allowed_forms"].options
    assert forms["facade"]["materials_forbidden"].options[0] == "render"
    assert forms["setback_side"]["allow_on_boundary"].type == "flag"
    assert forms["setback_side"]["height_factor"].unit == "factor"
    assert forms["parking"]["spaces_per_m2_sdp"].unit == "per_area"
    assert forms["max_height"]["storeys"].type == "text"
    kinds = {form.kind: form for form in kind_forms()}
    assert kinds["max_height"].building_specific and not kinds["max_area"].building_specific
    assert kinds["max_height"].mandatory and not kinds["parking"].mandatory


def test_defaults_of_the_form_are_valid_parameters() -> None:
    """Ein Formular mit Vorgaben und den Pflichtwerten ergibt gültige Parameter (keine Scheinwerte)."""
    forms = {form.kind: form for form in kind_forms()}
    filled = {
        "max_footprint_ratio": {"ratio": 0.3},
        "setback_street": {"min_m": 5.0},
        "setback_side": {"min_m": 3.0},
        "text_only": {"summary": "Hinweis"},
    }
    for kind, values in filled.items():
        defaults = {p.name: p.default for p in forms[kind].params if p.default not in (None, [])}
        assert validate_params(kind, {**defaults, **values})


# ---------------------------------------------------------------------------
# Übernahme aus Zusatzdokumenten (3.4)
# ---------------------------------------------------------------------------

LOT = "lot-document"


def test_adoption_keeps_what_only_the_plu_regulates() -> None:
    """7.1 Nr. 1: „First 8 m“ aus dem Lotissement darf die Traufe 7 m des PLU nicht fallen lassen."""
    plu = rule("max_height", {"eave_m": 7.0, "ridge_m": 10.0})
    lot = rule("max_height", {"ridge_m": 8.0})
    comparison = compare_rule(lot, plu, LOT)
    assert comparison.verdict == "stricter"
    assert comparison.proposal == {
        "eave_m": 7.0,
        "ridge_m": 8.0,
        "reference": "natural_terrain",
        "measured_at": "highest_point",
        "includes_roof_installations": False,
    }


def test_merge_takes_the_stricter_value_per_parameter() -> None:
    mixed = merge_stricter(
        "max_height",
        rule("max_height", {"eave_m": 6.0, "ridge_m": 10.0}),
        rule("max_height", {"eave_m": 7.0, "ridge_m": 8.0}),
    )
    assert (mixed["eave_m"], mixed["ridge_m"]) == (6.0, 8.0)
    side = merge_stricter(
        "setback_side",
        rule("setback_side", {"min_m": 3.0, "allow_on_boundary": True}),
        rule("setback_side", {"min_m": 4.0, "allow_on_boundary": False}),
    )
    assert (side["min_m"], side["allow_on_boundary"]) == (4.0, False)
    roof = merge_stricter(
        "roof",
        rule("roof", {"allowed_forms": ["gable", "hip"], "flat_roof": "allowed"}),
        rule("roof", {"allowed_forms": ["gable", "flat"], "flat_roof": "forbidden"}),
    )
    assert (roof["allowed_forms"], roof["flat_roof"]) == (["gable"], "forbidden")
    facade = merge_stricter(
        "facade",
        rule("facade", {"materials_forbidden": ["metal"]}),
        rule("facade", {"materials_forbidden": ["wood"]}),
    )
    assert facade["materials_forbidden"] == ["metal", "wood"]
    storeys = merge_stricter(
        "max_height", rule("max_height", {"storeys": "R+1"}), rule("max_height", {"storeys": "R+2"})
    )
    assert storeys["storeys"] == "R+1"


def test_merge_treats_empty_lists_as_unrestricted_and_contradictions_as_the_supplement() -> None:
    """7.1 Nr. 10: Eine leere Liste schränkt nicht ein; eine leere Schnittmenge ist ein Widerspruch."""
    open_plu = merge_stricter(
        "roof",
        rule("roof", {"allowed_forms": [], "pitch_max_deg": 45.0}),
        rule("roof", {"allowed_forms": ["gable"]}),
    )
    assert open_plu["allowed_forms"] == ["gable"] and open_plu["pitch_max_deg"] == 45.0
    contradiction = merge_stricter(
        "roof", rule("roof", {"allowed_forms": ["hip"]}), rule("roof", {"allowed_forms": ["flat"]})
    )
    assert contradiction["allowed_forms"] == ["flat"]


def test_invalid_merge_falls_back_to_the_supplement() -> None:
    """Traufe aus dem PLU über dem First des Zusatzdokuments: keine gültige Regel → Werte des Dokuments."""
    merged = merge_stricter(
        "max_height", rule("max_height", {"eave_m": 9.0}), rule("max_height", {"ridge_m": 8.0})
    )
    assert merged == {"ridge_m": 8.0}


def test_proposals_only_where_an_adoption_changes_something() -> None:
    plu = rule("max_height", {"eave_m": 7.0, "ridge_m": 10.0})
    assert compare_rule(rule("max_height", {"ridge_m": 12.0}), plu).proposal is None
    assert compare_rule(rule("max_height", {"ridge_m": 10.0}), plu).proposal is None
    assert compare_rule(rule("setback_side", status="not_regulated"), None).proposal is None
    only = compare_rule(rule("max_area", {"sdp_m2": 180.0}, building_kind="any"), None)
    assert (only.verdict, only.proposal) == ("only_supplement", {"sdp_m2": 180.0})


def test_adopted_values_are_recognised_by_their_document() -> None:
    lot = rule("max_height", {"ridge_m": 8.0})
    adopted = replace(
        rule("max_height", {"eave_m": 7.0, "ridge_m": 8.0}),
        citation=Citation(page=2, origin="project", document_id=LOT, quote_verified=True),
    )
    assert compare_rule(lot, adopted, LOT).verdict == "adopted"
    # Eine Korrektur aus einem anderen Dokument ist keine Übernahme
    other = replace(adopted, citation=replace(adopted.citation, document_id="plu"))
    assert compare_rule(lot, other, LOT).verdict == "equal"
    comparisons = compare([lot, rule("max_area", {"sdp_m2": 180.0}, building_kind="any")], [adopted], LOT)
    assert [c.verdict for c in comparisons] == ["adopted", "only_supplement"]
    assert stricter_kinds(comparisons) == ["max_area"]


def test_analysis_drops_adopted_kinds_from_the_warning() -> None:
    adopted = replace(
        rule("max_height", {"eave_m": 6.0, "ridge_m": 8.0}),
        citation=Citation(page=2, origin="project", document_id=LOT, quote_verified=True),
    )
    rules = [r for r in ub_rules() if r.kind != "max_height"] + [adopted]
    outline = rectangle(20, 31)
    data: EnvelopeInput = envelope_input(
        site_input=site(polygon=outline, edges=edges_of_rectangle(20, 31)),
        zones=[zone(polygon=outline, rules=rules)],
    )
    supplement = SupplementInput(
        document_id=LOT,
        title="Lotissement",
        du_type="lotissement",
        lot="Lot-12",
        status="simulated",
        reason=None,
        rules=[rule("max_height", {"ridge_m": 8.0})],
    )
    result = analyse(data, derive_envelope(data), DEFAULTS, [supplement])
    assert [c.verdict for c in result.supplements[0].comparisons] == ["adopted"]
    assert result.supplement_stricter == [] and "supplement_stricter" not in result.warnings
