"""Executable current-main guards for the future Opening Deduction Authority.

TEST ONLY. These tests do not authorize legacy deduction arithmetic. They preserve
fail-closed semantics that the future producer-owned authority must not weaken.
"""
from __future__ import annotations

from pb_opening_deduction_readiness import (
    build_opening_deduction_quantities,
    build_opening_deduction_quantity,
)
from tests.test_opening_deduction_readiness import (
    _ctx,
    _doc,
    _entity,
    _ev,
    _host,
    _viewport,
)


def test_missing_dimensions_remain_unknown_not_zero() -> None:
    result = build_opening_deduction_quantity(
        host=_host(),
        wall_id="WALL-1",
        context=_ctx(),
        document=_doc(),
        viewport=_viewport(),
        opening_entity=_entity("OP-1", ids=()),
        width_evidence=None,
        height_evidence=None,
    )

    assert result.abstained
    assert result.value is None
    assert "opening_width_missing" in result.blocking_reasons
    assert "opening_height_missing" in result.blocking_reasons


def test_no_opening_records_do_not_materialize_evidenced_zero() -> None:
    results = build_opening_deduction_quantities(
        hosts=(),
        wall_id="WALL-1",
        context=_ctx(),
        document=_doc(),
        viewport=_viewport(),
        opening_entities={},
        width_evidence={},
        height_evidence={},
    )

    assert results == ()


def test_duplicate_candidate_identity_blocks_instead_of_double_deducting() -> None:
    hosts = (_host("OP-1"), _host("OP-1"))
    results = build_opening_deduction_quantities(
        hosts=hosts,
        wall_id="WALL-1",
        context=_ctx(),
        document=_doc("ev-w", "ev-h"),
        viewport=_viewport(),
        opening_entities={"OP-1": _entity("OP-1")},
        width_evidence={"OP-1": _ev("ev-w", "opening_width_dimension", 900.0)},
        height_evidence={"OP-1": _ev("ev-h", "opening_height_dimension", 2100.0)},
    )

    assert len(results) == 2
    assert all(result.value is None for result in results)
    assert all("duplicate_opening_identity" in result.blocking_reasons for result in results)


def test_same_size_distinct_openings_are_not_deduplicated_by_dimensions() -> None:
    hosts = (_host("OP-1"), _host("OP-2"))
    results = build_opening_deduction_quantities(
        hosts=hosts,
        wall_id="WALL-1",
        context=_ctx(),
        document=_doc("w1", "h1", "w2", "h2"),
        viewport=_viewport(),
        opening_entities={
            "OP-1": _entity("OP-1", ids=("w1", "h1")),
            "OP-2": _entity("OP-2", ids=("w2", "h2")),
        },
        width_evidence={
            "OP-1": _ev("w1", "opening_width_dimension", 900.0, opening_id="OP-1"),
            "OP-2": _ev("w2", "opening_width_dimension", 900.0, opening_id="OP-2"),
        },
        height_evidence={
            "OP-1": _ev("h1", "opening_height_dimension", 2100.0, opening_id="OP-1"),
            "OP-2": _ev("h2", "opening_height_dimension", 2100.0, opening_id="OP-2"),
        },
    )

    assert len(results) == 2
    for result in results:
        assert "duplicate_opening_identity" not in result.blocking_reasons
        assert "duplicate_physical_opening_identity" not in result.blocking_reasons
        assert "opening_dimension_evidence_reused_across_identities" not in result.blocking_reasons
        assert result.value is None  # still blocked by current missing physical authority


def test_same_claimed_physical_opening_under_two_candidates_fails_closed() -> None:
    first = _entity("OP-1", ids=("w1", "h1"))
    second = _entity("OP-2", ids=("w2", "h2"))
    second = type(second)(
        candidate_entity_id=second.candidate_entity_id,
        candidate_type=second.candidate_type,
        evidence_ids=second.evidence_ids,
        status=second.status,
        confidence=second.confidence,
        metadata={**second.metadata, "physical_opening_id": "OP-1"},
    )
    results = build_opening_deduction_quantities(
        hosts=(_host("OP-1"), _host("OP-2")),
        wall_id="WALL-1",
        context=_ctx(),
        document=_doc("w1", "h1", "w2", "h2"),
        viewport=_viewport(),
        opening_entities={"OP-1": first, "OP-2": second},
        width_evidence={
            "OP-1": _ev("w1", "opening_width_dimension", 900.0, opening_id="OP-1"),
            "OP-2": _ev("w2", "opening_width_dimension", 900.0, opening_id="OP-2"),
        },
        height_evidence={
            "OP-1": _ev("h1", "opening_height_dimension", 2100.0, opening_id="OP-1"),
            "OP-2": _ev("h2", "opening_height_dimension", 2100.0, opening_id="OP-2"),
        },
    )

    assert len(results) == 2
    assert all(result.value is None for result in results)
    assert all("duplicate_physical_opening_identity" in result.blocking_reasons for result in results)


def test_wrong_wall_scope_blocks_deduction() -> None:
    result = build_opening_deduction_quantity(
        host=_host(wall_id="WALL-1"),
        wall_id="WALL-2",
        context=_ctx(),
        document=_doc("ev-w", "ev-h"),
        viewport=_viewport(),
        opening_entity=_entity("OP-1"),
        width_evidence=_ev("ev-w", "opening_width_dimension", 900.0),
        height_evidence=_ev("ev-h", "opening_height_dimension", 2100.0),
    )

    assert result.abstained
    assert result.value is None
    assert "opening_host_wall_mismatch" in result.blocking_reasons
