from pb_explicit_floor_area_evidence import (
    extract_explicit_floor_area_evidence,
    resolve_explicit_floor_area_evidence,
)


def test_extracts_labelled_floor_area_on_floor_plan():
    ev = extract_explicit_floor_area_evidence(
        "DRAWING TITLE DESIGN SCHEME ( Plan ) PLAN : FLOOR LAYOUT "
        "AREA in M2 FLOOR AREA - 162.69M2",
        source_page=7,
    )
    assert ev is not None
    assert ev.area_m2 == 162.69
    assert ev.source_pages == (7,)
    assert ev.evidence_role == "declared_source_area_claim"
    assert ev.authority == "declared_source_area_claim"
    assert ev.binding == "unbound"


def test_accepts_common_square_metre_unit_spellings():
    values = []
    for token in ("84.5 m2", "84.5m²", "84.5 sqm", "84.5 sq m"):
        ev = extract_explicit_floor_area_evidence(
            f"GROUND FLOOR PLAN FLOOR AREA - {token}", source_page=3
        )
        assert ev is not None
        values.append(ev.area_m2)
    assert values == [84.5, 84.5, 84.5, 84.5]


def test_mutating_source_value_mutates_output_without_lookup():
    a = extract_explicit_floor_area_evidence(
        "FLOOR PLAN FLOOR AREA 101.25 m2", source_page=1
    )
    b = extract_explicit_floor_area_evidence(
        "FLOOR PLAN FLOOR AREA 137.75 m2", source_page=1
    )
    assert a is not None and b is not None
    assert a.area_m2 == 101.25
    assert b.area_m2 == 137.75


def test_requires_floor_plan_semantics():
    assert extract_explicit_floor_area_evidence(
        "WINDOW SCHEDULE FLOOR AREA - 162.69M2", source_page=4
    ) is None


def test_requires_explicit_floor_area_label_and_units():
    assert extract_explicit_floor_area_evidence(
        "FLOOR PLAN ROOM AREA - 162.69M2", source_page=4
    ) is None
    assert extract_explicit_floor_area_evidence(
        "FLOOR PLAN FLOOR AREA - 162.69", source_page=4
    ) is None


def test_scale_and_dimension_noise_are_ignored():
    assert extract_explicit_floor_area_evidence(
        "FLOOR PLAN SCALE 1:100 15950 11050 200 200", source_page=2
    ) is None


def test_two_different_floor_areas_on_same_page_fail_closed():
    assert extract_explicit_floor_area_evidence(
        "FLOOR PLAN FLOOR AREA 100.0M2 FLOOR AREA 120.0M2", source_page=2
    ) is None


def test_identical_repeated_annotation_is_not_ambiguous():
    ev = extract_explicit_floor_area_evidence(
        "FLOOR PLAN FLOOR AREA 100.0M2 FLOOR AREA 100.0M2", source_page=2
    )
    assert ev is not None
    assert ev.area_m2 == 100.0


def test_cross_page_agreement_resolves_and_preserves_pages():
    first = extract_explicit_floor_area_evidence(
        "GROUND FLOOR PLAN FLOOR AREA 144.25M2", source_page=8
    )
    second = extract_explicit_floor_area_evidence(
        "FLOOR LAYOUT FLOOR AREA 144.25 sqm", source_page=9
    )
    assert first is not None and second is not None
    resolved = resolve_explicit_floor_area_evidence([first, second])
    assert resolved is not None
    assert resolved.area_m2 == 144.25
    assert resolved.source_pages == (8, 9)


def test_cross_page_disagreement_fails_closed():
    first = extract_explicit_floor_area_evidence(
        "FLOOR PLAN FLOOR AREA 144.25M2", source_page=8
    )
    second = extract_explicit_floor_area_evidence(
        "FLOOR PLAN FLOOR AREA 155.50M2", source_page=9
    )
    assert first is not None and second is not None
    assert resolve_explicit_floor_area_evidence([first, second]) is None


def test_empty_evidence_fails_closed():
    assert resolve_explicit_floor_area_evidence([]) is None

def test_resolution_is_input_order_deterministic_and_does_not_mutate_inputs():
    first = extract_explicit_floor_area_evidence(
        "GROUND FLOOR PLAN FLOOR AREA 80.00M2", source_page=1
    )
    second = extract_explicit_floor_area_evidence(
        "GROUND FLOOR PLAN FLOOR AREA 80.00M2", source_page=2
    )
    assert first is not None and second is not None
    items = [first, second]
    snapshot = list(items)

    forward = resolve_explicit_floor_area_evidence(items)
    reverse = resolve_explicit_floor_area_evidence(reversed(items))

    assert items == snapshot
    assert forward == reverse
    assert forward is not None
    assert forward.source_pages == (1, 2)


def test_numerically_equal_claims_remain_unbound_declarations():
    first = extract_explicit_floor_area_evidence(
        "GROUND FLOOR PLAN FLOOR AREA 80.00M2", source_page=1
    )
    second = extract_explicit_floor_area_evidence(
        "GROUND FLOOR PLAN FLOOR AREA 80.00M2", source_page=2
    )
    resolved = resolve_explicit_floor_area_evidence([first, second])
    assert resolved is not None
    assert resolved.area_m2 == 80.0
    assert resolved.binding == "unbound"
    assert resolved.evidence_role == "declared_source_area_claim"

def test_summary_total_with_component_rows_remains_one_unbound_claim():
    ev = extract_explicit_floor_area_evidence(
        "GROUND FLOOR PLAN MAIN LIVING AREA 60.0m2 GARAGE AREA 20.0m2 "
        "PORCH AREA 5.0m2 TOTAL FLOOR AREA 85.0m2",
        source_page=4,
    )
    assert ev is not None
    assert ev.area_m2 == 85.0
    assert ev.binding == "unbound"
    assert ev.evidence_role == "declared_source_area_claim"

