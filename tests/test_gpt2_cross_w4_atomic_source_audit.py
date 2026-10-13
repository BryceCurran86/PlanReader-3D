"""Cross-W4 source ancestry is a diagnostic, never inferred physical ownership."""
from types import SimpleNamespace as Record

from tools.diag_gpt2_grid_component_first_failure import (
    inspect_external_atomic_grid_w2_source_fragments,
)


def source_fragment(edge_id, geometry, ids=("native-page7-path",)):
    return Record(
        edge_id=edge_id, geometry=geometry, source_primitive_ids=ids,
    )


def first_gate(*records):
    input_scope = Record(records=records)
    union = {
        "physical_union_external_grid_atomic_subedges_diagnostic_only": [{
            "original_w4_wall_id": "wall-A",
            "original_atomic_wall_edge_pdf_pts": [
                [0.0, 0.0], [10.0, 0.0],
            ],
            "original_global_source_face_ids": ["source-face-1"],
        }]
    }
    return inspect_external_atomic_grid_w2_source_fragments(
        input_scope, union
    )[0]


def test_other_w4_exact_fragment_cannot_replace_missing_original_owner():
    own = Record(wall_candidate_id="wall-A", source_edge_fragments=())
    different = Record(
        wall_candidate_id="wall-B",
        source_edge_fragments=(
            source_fragment(
                "w2-split-original", ((-3, 0), (14, 0)),
                ("native-p0", "native-p1"),
            ),
        ),
    )
    row = first_gate(own, different)
    assert row["source_first_unclosed_gate"] == (
        "original_atomic_wall_subedge_w2_fragment_unavailable"
    )
    assert row["source_w2_fragment_candidates_diagnostic_only"] == []
    assert row["other_w4_source_fragments_diagnostic_only"] == [{
        "alternative_original_w4_wall_id": "wall-B",
        "alternative_source_w2_edge_id": "w2-split-original",
        "original_source_primitive_ids": ["native-p0", "native-p1"],
        "atomic_subedge_wholly_contained": True,
        "partial_original_overlap_pdf_pts": None,
        "candidate_only_no_wall_identity_transfer": True,
        "second_face_owner_authenticated": False,
    }]
    assert row["other_w4_alternative_owner_granted"] is False
    assert row["source_second_face_owner_authenticated"] is False


def test_partial_other_w4_source_overlap_stays_diagnostic_only():
    own = Record(wall_candidate_id="wall-A", source_edge_fragments=())
    another = Record(wall_candidate_id="wall-B", source_edge_fragments=(
        source_fragment("partial-w2", ((5, 0), (15, 0))),
    ))
    row = first_gate(own, another)
    entry = row["other_w4_source_fragments_diagnostic_only"][0]
    assert entry["atomic_subedge_wholly_contained"] is False
    assert entry["partial_original_overlap_pdf_pts"] == [
        [5.0, 0.0], [10.0, 0.0]
    ]
    assert row["source_first_unclosed_gate"] == (
        "original_atomic_wall_subedge_w2_fragment_unavailable"
    )


def test_conflicting_or_malformed_other_wall_cannot_be_promoted():
    own = Record(wall_candidate_id="wall-A", source_edge_fragments=())
    ambiguous = Record(
        wall_candidate_id="wall-B",
        source_edge_fragments=(
            source_fragment("bad", ((0, 0), (10, 0)), ids=("",)),
        ),
    )
    row = first_gate(own, ambiguous)
    assert row["other_w4_source_fragments_diagnostic_only"] == []
    assert row["other_w4_source_fragment_conflict_receipt_count"] >= 1
    assert row["other_w4_alternative_owner_granted"] is False
    duplicate = first_gate(
        own,
        Record(wall_candidate_id="wall-B", source_edge_fragments=(
            source_fragment("w2-one", ((0, 0), (10, 0))),)),
        Record(wall_candidate_id="wall-B", source_edge_fragments=(
            source_fragment("w2-two", ((0, 0), (10, 0))),)),
    )
    assert duplicate["other_w4_source_fragments_diagnostic_only"] == []
    assert duplicate["other_w4_source_fragment_conflict_receipt_count"] >= 1


def test_production_flat_w4_line_exact_owner_diagnostic_is_not_physical_proof():
    # The actual W4 source fragment contract is (x1,y1,x2,y2).
    own = Record(
        wall_candidate_id="wall-A",
        source_edge_fragments=(
            source_fragment("w2-native-child", (0.0, 0.0, 10.0, 0.0)),
        ),
    )
    row = first_gate(own)
    assert row["source_first_unclosed_gate"] == (
        "original_w2_fragment_observed_second_face_missing"
    )
    assert row["source_w2_fragment_candidates_diagnostic_only"][0][
        "original_w2_edge_id"
    ] == "w2-native-child"
    assert row["source_second_face_owner_authenticated"] is False
    assert row["source_room_geometry_or_area_published"] is False


def test_flat_line_in_alternative_w4_never_transfers_original_owner():
    own = Record(wall_candidate_id="wall-A", source_edge_fragments=())
    other = Record(
        wall_candidate_id="wall-B",
        source_edge_fragments=(
            source_fragment("w2-other", (0.0, 0.0, 10.0, 0.0)),
        ),
    )
    row = first_gate(own, other)
    assert row["source_first_unclosed_gate"] == (
        "original_atomic_wall_subedge_w2_fragment_unavailable"
    )
    assert row["other_w4_source_fragments_diagnostic_only"][0][
        "alternative_source_w2_edge_id"
    ] == "w2-other"
    assert row["other_w4_alternative_owner_granted"] is False
