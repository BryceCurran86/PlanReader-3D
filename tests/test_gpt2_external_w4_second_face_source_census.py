"""Fail-closed source face/abstention receipts for an original external W4 edge."""
from types import SimpleNamespace as Record

from tools.diag_gpt2_grid_component_first_failure import (
    inspect_original_external_atomic_second_face_scope,
)

LINEAGE = dict(
    document_id="doc", revision_id="r", source_sha256="sha",
    snapshot_id="s", page_id="p", decision_scope_id="scope",
)
ATOMIC = ((0.0, 0.0), (10.0, 0.0))


def face(face_id, wall="w4", edge=ATOMIC, *, abstained=False, reason=None, **changes):
    data = dict(
        face_id=face_id, record_id="rec-" + face_id,
        boundary_wall_edges=((wall, edge),), **LINEAGE,
    )
    data.update(changes)
    if abstained:
        data["reason"] = reason or "source_room_face_boundary_unresolved"
    return Record(**data)


def run(published, withheld=(), source_complete=False):
    scope = Record(
        records=tuple(published), abstained_faces=tuple(withheld),
        face_universe_complete=source_complete, **LINEAGE,
    )
    union = {
        "physical_union_external_grid_atomic_subedges_diagnostic_only": [{
            "original_w4_wall_id": "w4",
            "original_atomic_wall_edge_pdf_pts": [[0.0, 0.0], [10.0, 0.0]],
            "original_global_source_face_ids": ["face-existing"],
        }]
    }
    return inspect_original_external_atomic_second_face_scope(scope, union)[0]


def test_real_original_other_published_face_is_candidate_not_second_side():
    result = run((face("face-existing"), face("face-opposite")), source_complete=True)
    matches = result["other_published_same_w4_edge_faces_diagnostic_only"]
    assert len(matches) == 1
    assert matches[0]["source_face_id"] == "face-opposite"
    assert matches[0]["source_edge_wholly_contains_atomic"]
    assert matches[0]["source_second_side_authenticated"] is False
    assert result["candidate_only_no_second_face_or_wall_transfer"]
    assert result["second_source_face_authenticated_by_diagnostic"] is False


def test_withheld_source_face_remains_abstained_even_if_exact_same_w4_edge():
    result = run(
        (face("face-existing"),),
        (face("face-unpublished", abstained=True, reason="ambiguous_original_wall"),),
    )
    assert result["other_published_same_w4_edge_faces_diagnostic_only"] == []
    withheld = result["withheld_same_w4_edge_faces_diagnostic_only"]
    assert len(withheld) == 1 and withheld[0]["withheld_reason"] == "ambiguous_original_wall"
    assert not withheld[0]["published_physical_face"]
    assert result["source_room_face_universe_complete"] is False


def test_collinear_other_w4_does_not_transfer_physical_owner():
    result = run((face("face-existing"), face("face-foreign", wall="other-w4")))
    assert result["other_published_same_w4_edge_faces_diagnostic_only"] == []
    assert result["other_w4_collinear_face_receipts_diagnostic_only"][0]["source_w4_wall_id"] == "other-w4"
    assert result["second_source_face_authenticated_by_diagnostic"] is False


def test_foreign_scope_and_duplicate_face_receipts_rejected():
    result = run((
        face("face-existing"),
        face("face-duplicate"),
        face("face-duplicate"),
        face("face-other-scope", source_sha256="foreign"),
    ))
    assert result["malformed_or_conflicting_original_face_receipt_count"] >= 3
    assert result["other_published_same_w4_edge_faces_diagnostic_only"] == []


def test_partial_overlap_is_recorded_but_never_authorizes_side():
    result = run((face("face-existing"),
                  face("face-short", edge=((0.0, 0.0), (5.0, 0.0)))))
    row = result["other_published_same_w4_edge_faces_diagnostic_only"][0]
    assert not row["source_edge_wholly_contains_atomic"]
    assert row["source_positive_overlap_pdf_pts"] == [[0.0, 0.0], [5.0, 0.0]]
    assert not result["room_or_quantity_published"]


def test_invalid_geometry_and_missing_original_owner_fail_closed():
    result = run((face("face-existing"),
                  face("face-invalid", edge=((0.0, 0.0), (float("nan"), 0.0)))))
    assert result["malformed_or_conflicting_original_face_receipt_count"] >= 1
    assert result["other_published_same_w4_edge_faces_diagnostic_only"] == []
    scope = Record(records=(), abstained_faces=(), face_universe_complete=False, **LINEAGE)
    assert inspect_original_external_atomic_second_face_scope(
        scope, {"physical_union_external_grid_atomic_subedges_diagnostic_only": [{
            "original_w4_wall_id": "w4",
            "original_atomic_wall_edge_pdf_pts": [[0, 0], [10, 0]],
            "original_global_source_face_ids": [],
        }]}
    ) == []
