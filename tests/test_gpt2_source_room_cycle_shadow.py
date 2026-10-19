"""Source-neutral ring oracle: never promote a geometric loop to physical room."""
from __future__ import annotations

import math
from random import Random

import pytest
from tools.diag_gpt2_source_room_cycle_shadow import audit_source_ring


SHA = "a" * 64
SCOPE = dict(
    source_sha256=SHA, page_id="7", snapshot_id="snapshot",
    decision_scope_id="wall-source:page-7",
)
BOX = [(0, 0), (300, 0), (300, 200), (0, 200)]


def _segments(points):
    return list(zip(points, points[1:] + points[:1]))


def _receipts(segments):
    return [
        dict(
            edge_id=f"edge-{i}", points=[a, b],
            wall_candidate_id=f"wall-{i}",
            source_primitive_ids=[f"primitive-{i}"], **SCOPE
        )
        for i, (a, b) in enumerate(segments)
    ]


@pytest.mark.parametrize("seed", range(20))
def test_closed_loop_is_only_candidate_with_unmodified_original_receipts(seed):
    items = _receipts(_segments(BOX))
    original = [repr(row) for row in items]
    Random(seed).shuffle(items)
    report = audit_source_ring(items, **SCOPE)
    assert report["status"] == "CANDIDATE"
    assert report["blocking_reasons"] == []
    assert len(report["geometry_ring_vertices_page_points"]) == 4
    assert report["physical_room_boundary_authority"] is False
    assert report["original_source_membership_reproven"] is False
    assert report["source_finish_area_ceiling_or_count_granted"] is False
    assert sorted(original) == sorted(repr(row) for row in items)


@pytest.mark.parametrize("angle", (0, 29, 90, 180, 270))
def test_translation_rotation_preserve_candidate_only(angle):
    theta = math.radians(angle)

    def transformed(p):
        x, y = p
        return (
            round(x * math.cos(theta) - y * math.sin(theta) + 1000, 6),
            round(x * math.sin(theta) + y * math.cos(theta) + 800, 6),
        )
    result = audit_source_ring(
        _receipts(_segments([transformed(p) for p in BOX])), **SCOPE
    )
    assert result["status"] == "CANDIDATE"
    assert result["physical_room_boundary_authority"] is False


def test_open_passage_has_no_fabricated_closing_edge():
    report = audit_source_ring(_receipts(_segments(BOX))[:-1], **SCOPE)
    assert report["status"] == "ABSTAINED"
    assert "open_passage_or_branch_endpoint_degree_not_two" in report["blocking_reasons"]
    assert report["geometry_ring_vertices_page_points"] is None


def test_freezer_style_bowtie_is_not_accepted_as_a_room():
    pts = [(0, 0), (100, 100), (0, 100), (100, 0)]
    report = audit_source_ring(_receipts(_segments(pts)), **SCOPE)
    assert report["status"] == "ABSTAINED"
    assert "self_intersecting_source_room_perimeter" in report["blocking_reasons"]


def test_closed_dimension_or_furniture_loop_is_not_structural_authority():
    report = audit_source_ring(_receipts(_segments(BOX)), **SCOPE)
    assert report["status"] == "CANDIDATE"
    assert report["source_only_positive_wall_role_required"]
    assert not report["physical_room_boundary_authority"]


@pytest.mark.parametrize("expected", (
    "source_edge_id_missing_or_reused",
    "source_edge_ancestry_not_authenticated",
    "structural_wall_candidate_address_missing",
    "source_edge_scope_or_snapshot_conflict",
    "coincident_source_edges_compete_for_wall_owner",
))
def test_source_identity_competitors_are_never_elected_by_order(expected):
    rows = _receipts(_segments(BOX))
    if expected == "source_edge_id_missing_or_reused":
        rows[2]["edge_id"] = rows[1]["edge_id"]
    elif expected == "source_edge_ancestry_not_authenticated":
        rows[2]["source_primitive_ids"] = []
    elif expected == "structural_wall_candidate_address_missing":
        rows[2]["wall_candidate_id"] = None
    elif expected == "source_edge_scope_or_snapshot_conflict":
        rows[2]["snapshot_id"] = "foreign"
    elif expected == "coincident_source_edges_compete_for_wall_owner":
        rows.append(dict(
            rows[0], edge_id="foreign-source-edge",
            wall_candidate_id="foreign-source-wall"
        ))
    report = audit_source_ring(rows, **SCOPE)
    assert report["status"] == "ABSTAINED"
    assert expected in report["blocking_reasons"]


def test_two_disconnected_closed_regions_cannot_be_one_physical_room():
    other = [(500, 0), (800, 0), (800, 200), (500, 200)]
    result = audit_source_ring(
        _receipts(_segments(BOX) + _segments(other)), **SCOPE
    )
    assert "disconnected_or_multiple_source_cycles" in result["blocking_reasons"]


def test_invalid_source_scope_and_nan_fail_closed():
    with pytest.raises(ValueError):
        audit_source_ring(_receipts(_segments(BOX)),
                          source_sha256="bad", page_id="7",
                          snapshot_id="snapshot",
                          decision_scope_id="wall-source:page-7")
    rows = _receipts(_segments(BOX))
    rows[0]["points"][0] = (float("nan"), 0)
    result = audit_source_ring(rows, **SCOPE)
    assert "original_source_segment_geometry_unavailable" in result["blocking_reasons"]
