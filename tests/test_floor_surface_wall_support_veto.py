"""Focused tests for generic zero-physical-wall-support veto (MAX #7235431173, Claude #7235439333)."""
from __future__ import annotations

from types import SimpleNamespace

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_floor_surface_wall_support_veto import (
    FLOOR_SURFACE_CANDIDATE_WALL_EVIDENCE_ONLY,
    FLOOR_SURFACE_POLYGON_INVALID_CANNOT_JUDGE,
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


def test_face_polygon_invalid_returns_cannot_judge_not_zero_wall_support() -> None:
    # Claude #7235942026 edge case 1: self-intersecting/degenerate polygon yields
    # edges=[] with reason="face_polygon_invalid" -> distinct cannot-judge code.
    def _invalid_poly_predicate(poly, drawings, closures=()):
        return {"edges": [], "reason": "face_polygon_invalid"}

    verdicts = evaluate_floor_surface_zero_wall_support_veto(
        surfaces=(_surf("s_bowtie", "q_bowtie", SQUARE),),
        drawings=(),
        wall_support_predicate=_invalid_poly_predicate,
        expected_document_id="doc1",
        expected_revision_id="rev1",
        expected_source_sha256=SHA,
    )
    assert len(verdicts) == 1
    v = verdicts[0]
    assert v.vetoed is True
    assert v.status is EvidenceResolutionStatus.ABSTAINED
    assert v.reason_codes == (
        FLOOR_SURFACE_POLYGON_INVALID_CANNOT_JUDGE,
        "face_polygon_invalid",
    )
    assert FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT not in v.reason_codes


def test_panel_or_wide_candidate_only_room_is_not_falsely_vetoed() -> None:
    # Claude #7235942026 edge case 2: room bounded solely by white-filled panel
    # or wide_candidate walls has unsupported==length but positive candidate evidence.
    def _panel_only_predicate(poly, drawings, closures=()):
        x1 = poly[1][0]
        if x1 == 80.0:
            return {
                "edges": [
                    {"length": 80.0, "unsupported": 80.0, "panel_candidate": 72.0},
                    {"length": 80.0, "unsupported": 80.0, "panel_candidate": 0.0},
                ]
            }
        return SimpleNamespace(
            edges=(
                SimpleNamespace(length=100.0, unsupported=100.0, wide_candidate=60.0),
                SimpleNamespace(length=100.0, unsupported=100.0, wide_candidate=0.0),
            )
        )

    panel_room = _surf("s_panel", "q_panel", ((0.0, 0.0), (80.0, 0.0), (80.0, 80.0), (0.0, 80.0)))
    wide_room = _surf("s_wide", "q_wide", SQUARE)

    verdicts = evaluate_floor_surface_zero_wall_support_veto(
        surfaces=(panel_room, wide_room),
        drawings=(),
        wall_support_predicate=_panel_only_predicate,
        expected_document_id="doc1",
        expected_revision_id="rev1",
        expected_source_sha256=SHA,
    )
    by_id = {v.surface_entity_id: v for v in verdicts}

    for sid in ("s_panel", "s_wide"):
        v = by_id[sid]
        assert v.vetoed is False
        assert v.status is EvidenceResolutionStatus.CORROBORATED
        assert v.supported_fraction == 0.0
        assert v.reason_codes == (FLOOR_SURFACE_CANDIDATE_WALL_EVIDENCE_ONLY,)
        assert v.shadow_only is True
        assert v.commercial_authority_granted is False
