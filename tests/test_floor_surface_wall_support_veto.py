"""Focused tests for generic zero-physical-wall-support veto (MAX #7235431173, Claude #7235439333)."""
from __future__ import annotations

from types import SimpleNamespace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_floor_surface_wall_support_veto import (
    FLOOR_SURFACE_POLYGON_UNAVAILABLE,
    FLOOR_SURFACE_POSITIVE_WALL_SUPPORT,
    FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT,
    FloorSurfaceWallSupportInput,
    evaluate_floor_surface_zero_wall_support_veto,
)

SHA = "d" * 64
SQUARE = ((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0))


def _surf(sid: str, qid: str, poly=SQUARE, *, rev="rev1"):
    return FloorSurfaceWallSupportInput(
        surface_entity_id=sid,
        quantity_id=qid,
        document_id="doc1",
        revision_id=rev,
        source_sha256=SHA,
        page_id="7",
        viewport_id="view_p7_2",
        polygon_pdf_pts=poly,
    )


def test_zero_wall_support_false_cell_vetoed_while_partial_28pct_room_retained() -> None:
    # Mimics Claude #7235439333: 0% cell vetoed, 28% partial paired-wall room NOT vetoed.
    def _fake_predicate(poly, drawings, closures=()):
        x1 = poly[1][0]
        if x1 == 34.0:
            # 0% supported drafting cell (every edge unsupported == length)
            return SimpleNamespace(
                edges=(
                    SimpleNamespace(length=34.0, unsupported=34.0),
                    SimpleNamespace(length=34.0, unsupported=34.0),
                    SimpleNamespace(length=34.0, unsupported=34.0),
                    SimpleNamespace(length=34.0, unsupported=34.0),
                )
            )
        # 28% paired-wall supported room (e.g. cold room with panel walls)
        return SimpleNamespace(
            edges=(
                SimpleNamespace(length=100.0, unsupported=0.0),
                SimpleNamespace(length=100.0, unsupported=88.0),
                SimpleNamespace(length=100.0, unsupported=100.0),
                SimpleNamespace(length=100.0, unsupported=100.0),
            )
        )

    false_cell = _surf("surf_false", "q_false", ((0.0, 0.0), (34.0, 0.0), (34.0, 34.0), (0.0, 34.0)))
    genuine_partial = _surf("surf_partial", "q_partial", SQUARE)

    verdicts = evaluate_floor_surface_zero_wall_support_veto(
        surfaces=(false_cell, genuine_partial),
        drawings=(),
        wall_support_predicate=_fake_predicate,
        expected_document_id="doc1",
        expected_revision_id="rev1",
        expected_source_sha256=SHA,
    )
    by_id = {v.surface_entity_id: v for v in verdicts}

    v_false = by_id["surf_false"]
    assert v_false.vetoed is True
    assert v_false.status is EvidenceResolutionStatus.ABSTAINED
    assert v_false.supported_fraction == 0.0
    assert v_false.reason_codes == (FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT,)
    assert v_false.shadow_only is True
    assert v_false.commercial_authority_granted is False

    v_partial = by_id["surf_partial"]
    assert v_partial.vetoed is False
    assert v_partial.status is EvidenceResolutionStatus.CORROBORATED
    assert v_partial.supported_fraction == 0.28
    assert v_partial.supported_edge_count == 2
    assert v_partial.reason_codes == (FLOOR_SURFACE_POSITIVE_WALL_SUPPORT,)


def test_missing_polygon_and_cross_revision_fail_closed() -> None:
    def _never_called(poly, drawings, closures=()):
        raise AssertionError("predicate should not be called for invalid/cross-rev surfaces")

    verdicts = evaluate_floor_surface_zero_wall_support_veto(
        surfaces=(
            _surf("s_empty", "q1", ()),
            _surf("s_cross_rev", "q2", SQUARE, rev="other_rev"),
        ),
        drawings=(),
        wall_support_predicate=_never_called,
        expected_document_id="doc1",
        expected_revision_id="rev1",
        expected_source_sha256=SHA,
    )
    assert verdicts[0].vetoed is True
    assert verdicts[0].reason_codes == (FLOOR_SURFACE_POLYGON_UNAVAILABLE,)
    assert verdicts[1].vetoed is True
    assert verdicts[1].reason_codes == ("floor_surface_provenance_scope_mismatch",)
