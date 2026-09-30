import inspect

from pb_explicit_floor_area_evidence import (
    DECLARED_FLOOR_AREA_AUTHORITY,
    DECLARED_FLOOR_AREA_BINDING,
    ExplicitFloorAreaEvidence,
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
    assert ev.authority == DECLARED_FLOOR_AREA_AUTHORITY
    assert ev.binding == DECLARED_FLOOR_AREA_BINDING


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


def test_declared_claim_has_no_physical_authority_by_default():
    ev = extract_explicit_floor_area_evidence(
        "GROUND FLOOR PLAN TOTAL FLOOR AREA: 222.5m2", source_page=3
    )
    assert ev is not None
    assert ev.binding == "unbound"
    assert ev.authority == "declared_floor_area_reconciliation_only"
    assert "explicit_drawing_floor_area" not in ev.authority


def test_revision_mismatched_declared_claims_do_not_resolve_together():
    first = ExplicitFloorAreaEvidence(
        area_m2=100.0,
        source_pages=(1,),
        raw_evidence=("FLOOR AREA 100.0m2",),
        source_sha256="a" * 64,
        revision_id="R1",
    )
    stale = ExplicitFloorAreaEvidence(
        area_m2=100.0,
        source_pages=(2,),
        raw_evidence=("FLOOR AREA 100.0m2",),
        source_sha256="a" * 64,
        revision_id="R0",
    )
    assert resolve_explicit_floor_area_evidence((first, stale)) is None


def test_source_hash_mismatched_declared_claims_do_not_resolve_together():
    first = ExplicitFloorAreaEvidence(
        area_m2=100.0,
        source_pages=(1,),
        raw_evidence=("FLOOR AREA 100.0m2",),
        source_sha256="a" * 64,
        revision_id="R1",
    )
    other = ExplicitFloorAreaEvidence(
        area_m2=100.0,
        source_pages=(2,),
        raw_evidence=("FLOOR AREA 100.0m2",),
        source_sha256="b" * 64,
        revision_id="R1",
    )
    assert resolve_explicit_floor_area_evidence((first, other)) is None


def test_declared_claim_resolution_is_input_order_invariant():
    a = ExplicitFloorAreaEvidence(
        area_m2=88.0,
        source_pages=(2,),
        raw_evidence=("FLOOR AREA 88.0m2",),
        source_sha256="c" * 64,
        revision_id="R2",
    )
    b = ExplicitFloorAreaEvidence(
        area_m2=88.0,
        source_pages=(1,),
        raw_evidence=("FLOOR AREA 88.0m2",),
        source_sha256="c" * 64,
        revision_id="R2",
    )
    forward = resolve_explicit_floor_area_evidence((a, b))
    reverse = resolve_explicit_floor_area_evidence((b, a))
    assert forward is not None and reverse is not None
    assert forward.area_m2 == reverse.area_m2
    assert forward.source_pages == reverse.source_pages == (1, 2)
    assert set(forward.raw_evidence) == set(reverse.raw_evidence)
    assert forward.binding == reverse.binding == "unbound"


def test_extract_and_resolve_do_not_mutate_inputs():
    source = "GROUND FLOOR PLAN FLOOR AREA 75.0m2"
    before = source
    ev = extract_explicit_floor_area_evidence(source, source_page=1)
    assert source == before
    assert ev is not None
    items = [ev]
    snapshot = list(items)
    resolved = resolve_explicit_floor_area_evidence(items)
    assert items == snapshot
    assert resolved is not None


def test_explicit_area_module_contains_no_benchmark_or_gold_access():
    import pb_explicit_floor_area_evidence as module

    source = inspect.getsource(module).lower()
    for forbidden in (
        "expected_boq_summary",
        "benchmark_rules",
        "expected_quantity",
        "benchmarks/public_tenders",
        "kstvet",
        "murera",
        "ghazi",
        "umma",
    ):
        assert forbidden not in source
