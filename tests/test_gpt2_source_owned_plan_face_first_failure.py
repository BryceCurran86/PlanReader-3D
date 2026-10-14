"""Fail-closed tests for source-owned W4 -> SourceRoomFace shadow receipts."""
from types import SimpleNamespace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from tools.diag_gpt2_source_owned_plan_face_first_failure import (
    _face_report, _shadow_local_face_boundary_census, replay,
)


def _wall(**changes):
    attrs = dict(
        document_id="document-a", revision_id="source-revision-a",
        source_sha256="source-sha-a", snapshot_id="source-snapshot-a",
        page_id="11", decision_scope_id="wall-source:viewport:11:original",
        viewport_id="source-proven-view", viewport_view_type="floor_finish_plan",
        viewport_bbox=(10.0, 20.0, 150.0, 160.0),
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=True, reason_codes=(), records=(
            SimpleNamespace(wall_candidate_id="wall-a"),
            SimpleNamespace(wall_candidate_id="wall-b"),
        ),
        boundary_evaluation=SimpleNamespace(
            status="evaluated",
            evaluated_wall_candidate_ids=("wall-a", "wall-b"),
            boundary_tainted_wall_candidate_ids=(),
            excluded_boundary_primitives=(),
        ),
    )
    return SimpleNamespace(**dict(attrs, **changes))


def _face(**changes):
    attrs = dict(
        document_id="document-a", revision_id="source-revision-a",
        source_sha256="source-sha-a", snapshot_id="source-snapshot-a",
        page_id="11", decision_scope_id="wall-source:viewport:11:original",
        status=EvidenceResolutionStatus.ABSTAINED, scope_complete=False,
        face_universe_complete=False,
        reason_codes=("source_room_face_boundary_unresolved",),
        records=(), abstained_faces=(),
        ownership_evaluation=SimpleNamespace(
            status="evaluated", competing_edge_count=1,
            unowned_edge_count=2, unresolved_face_ids=("source-face-a",),
            unresolved_faces=(), owned_face_ids=(),
            degenerate_owned_face_ids=(), largest_owned_face_area_pt2=0.0,
            face_count=1,
            competing_wall_ids=("wall-a", "wall-b"),
        ),
    )
    return SimpleNamespace(**dict(attrs, **changes))


def test_real_unresolved_edge_receipts_remain_explicit_abstentions():
    report = _face_report(_wall(), _face())
    assert report["w4_candidate_count"] == 2
    assert report["w4_boundary_evaluation_status"] == "evaluated"
    assert report["w4_boundary_tainted_wall_count"] == 0
    assert report["w4_boundary_evaluated_wall_count"] == 2
    assert report["w4_boundary_excluded_native_primitive_count"] == 0
    assert report["source_room_face_record_count"] == 0
    assert report["shadow_competing_wall_ids"] == ("wall-a", "wall-b")
    assert report["shadow_unowned_edge_count"] == 2
    assert report["shadow_evaluated_face_count"] == 1
    assert report["shadow_owned_face_count"] == 0
    assert report["shadow_owned_face_publication_granted"] is False
    assert report["source_room_face_universe_complete"] is False
    assert all(
        report[key] is False
        for key in (
            "unique_physical_room_label_claim_granted",
            "physical_cross_sheet_equivalence_granted",
            "ft3_definition_claim_granted",
            "metric_quantity_claim_granted",
            "customer_row_claim_granted",
            "benchmark_match_claim_granted",
        )
    )


@pytest.mark.parametrize("changed", [
    {"source_sha256": "wrong-source-sha"},
    {"revision_id": "wrong-source-revision"},
    {"snapshot_id": "other-source-snapshot"},
    {"page_id": "7"},
    {"decision_scope_id": "wall-source:viewport:7:foreign"},
    {"document_id": "foreign-document"},
])
def test_source_face_scope_owner_is_exact(changed):
    with pytest.raises(ValueError, match="source_face_cross_revision_or_scope_mismatch"):
        _face_report(_wall(), _face(**changed))


def test_bad_page_address_cannot_be_used_to_invent_source_room():
    for page in (0, -1, 1.5, "11", None):
        with pytest.raises(ValueError, match="source_page_number_invalid"):
            replay(b"not-a-pdf", page_number=page)


def test_competing_source_wall_ancestors_are_reported_without_winner():
    from pb_source_room_face_authority import EDGE_OWNERSHIP_COMPETING

    contender_a = SimpleNamespace(
        wall_candidate_id="wall-a",
        physical_identity=SimpleNamespace(source_primitive_ids=("native:a",)),
        source_edge_fragments=(
            SimpleNamespace(edge_id="edge:a", geometry=(1.0, 2.0, 3.0, 2.0),
                            source_primitive_ids=("native:a",)),
        ),
        source_snap_collapsed_fragments=(),
    )
    contender_b = SimpleNamespace(
        wall_candidate_id="wall-b",
        physical_identity=SimpleNamespace(source_primitive_ids=("native:b",)),
        source_edge_fragments=(
            SimpleNamespace(edge_id="edge:b", geometry=(1.0, 2.0, 3.0, 2.0),
                            source_primitive_ids=("native:b",)),
        ),
        source_snap_collapsed_fragments=(),
    )
    finding = SimpleNamespace(
        face_id="face-one", edge_findings=(SimpleNamespace(
            kind=EDGE_OWNERSHIP_COMPETING,
            edge=((1.0, 2.0), (3.0, 2.0)),
            wall_ids=("wall-a", "wall-b"),
        ),),
    )
    evaluation = SimpleNamespace(
        status="evaluated", competing_edge_count=1,
        unowned_edge_count=0, unresolved_face_ids=("face-one",),
        competing_wall_ids=("wall-a", "wall-b"),
        unresolved_faces=(finding,), owned_face_ids=(),
        degenerate_owned_face_ids=(), largest_owned_face_area_pt2=0.0,
        face_count=1,
    )
    report = _face_report(
        _wall(records=(contender_a, contender_b)),
        _face(ownership_evaluation=evaluation),
    )
    edge, = report["competing_source_edges"]
    assert edge["face_id"] == "face-one"
    assert edge["unique_source_wall_owner_granted"] is False
    assert edge["existing_local_source_interval_proof"] is False
    assert edge["pairwise_source_equivalence_receipts"] == [{
        "left_wall_id": "wall-a", "right_wall_id": "wall-b",
        "sealed_w4_equivalence_classes": (),
    }]
    assert {item["wall_id"] for item in edge["candidate_walls"]} == {
        "wall-a", "wall-b"
    }
    assert {tuple(item["source_primitive_ids"]) for item in edge["candidate_walls"]} == {
        ("native:a",), ("native:b",)
    }
    assert all(not item["structural_wall_role_proven_by_this_report"]
               for item in edge["candidate_walls"])


def test_shadow_edge_owned_faces_can_be_boundary_tainted_without_publication():
    face = _face(ownership_evaluation=SimpleNamespace(
        status="evaluated", owned_face_ids=("face-a", "face-b"),
        degenerate_owned_face_ids=("face-b",),
    ))
    wall = _wall(boundary_evaluation=SimpleNamespace(
        status="evaluated", boundary_tainted_wall_candidate_ids=("wall-a",),
        evaluated_wall_candidate_ids=("wall-a", "wall-b"),
        excluded_boundary_primitives=(),
    ))
    candidates = (
        {"face_id": "face-a", "bounding_wall_ids": ("wall-a",),
         "polygon_pdf_pts": ((0., 0.), (4., 0.), (4., 3.), (0., 3.))},
        {"face_id": "face-b", "bounding_wall_ids": ("wall-b",),
         "polygon_pdf_pts": ((10., 0.), (11., 0.), (11., 1.), (10., 1.))},
    )
    result = _shadow_local_face_boundary_census(wall, face, witnesses=candidates)
    assert result == {
        "status": "evaluated",
        "original_edge_owned": 2,
        "boundary_tainted": 1,
        "boundary_clean": 1,
        "boundary_clean_non_degenerate": 0,
        "source_room_publication_granted": False,
    }
    face2 = _face(ownership_evaluation=SimpleNamespace(
        status="evaluated", owned_face_ids=("face-b",),
        degenerate_owned_face_ids=(),
    ))
    second = _shadow_local_face_boundary_census(
        wall, face2, witnesses=candidates[1:]
    )
    assert second["boundary_clean_non_degenerate"] == 1
    assert second["source_room_publication_granted"] is False


def test_shadow_witnesses_cannot_omit_or_repeat_producer_face_ids():
    face = _face(ownership_evaluation=SimpleNamespace(
        status="evaluated", owned_face_ids=("source-one",),
        degenerate_owned_face_ids=(),
    ))
    with pytest.raises(RuntimeError, match="shadow_source_face_witness_census_mismatch"):
        _shadow_local_face_boundary_census(_wall(), face, witnesses=())
    with pytest.raises(RuntimeError, match="shadow_source_face_witness_census_mismatch"):
        _shadow_local_face_boundary_census(_wall(), face, witnesses=(
            {"face_id":"source-one","bounding_wall_ids":(),
             "polygon_pdf_pts":((0,0),(1,0),(0,1))},
            {"face_id":"source-one","bounding_wall_ids":(),
             "polygon_pdf_pts":((0,0),(1,0),(0,1))},
        ))
