"""Adversarial read-only original-source W4 ancestry census."""
from types import SimpleNamespace as Record

from tools.diag_gpt2_grid_component_first_failure import (
    inspect_native_source_parent_w4_ancestry,
)


def scope(*walls):
    return Record(records=walls)


def wall(wall_id, *fragments):
    return Record(wall_candidate_id=wall_id, source_edge_fragments=fragments)


def frag(edge_id, source_ids=("native-A",), geom=((0, 0), (10, 0))):
    return Record(
        edge_id=edge_id,
        source_primitive_ids=source_ids,
        geometry=geom,
    )


def test_exact_parent_survives_in_multiple_w4_candidates_without_reassignment():
    data = inspect_native_source_parent_w4_ancestry(
        scope(wall("wall-A", frag("split-1")),
              wall("wall-B", frag("split-2", geom=((10, 0), (20, 0))))),
        ["native-A"],
    )
    result = data["sources"][0]
    assert result["matched_w4_candidate_count"] == 2
    assert result["matched_source_w2_edge_count"] == 2
    assert [x["original_w4_wall_candidate_id"]
            for x in result["candidate_w4_ancestry_receipts"]] == [
                "wall-A", "wall-B"
            ]
    assert all(x["w4_identity_transfer_authorized"] is False
               for x in result["candidate_w4_ancestry_receipts"])
    assert result["source_wall_role_authenticated"] is False
    assert result["source_w4_receipt_universe_complete"] is False


def test_duplicate_wall_address_does_not_contribute_unique_source_receipts():
    data = inspect_native_source_parent_w4_ancestry(
        scope(wall("duplicate", frag("split-1")),
              wall("duplicate", frag("split-2"))),
        ["native-A"],
    )
    result = data["sources"][0]
    assert result["matched_w4_candidate_count"] == 0
    assert result["malformed_or_ambiguous_w4_receipt_count"] == 2


def test_invalid_source_geometry_or_parent_rejected():
    data = inspect_native_source_parent_w4_ancestry(
        scope(wall("good", frag("bad", geom=((0, 0), (0, 0))),
                   frag("foreign", source_ids=("native-A", "")),
                   frag("nonfinite", geom=((0, 0), (float("nan"), 0))))),
        ["native-A"],
    )
    result = data["sources"][0]
    assert result["matched_source_w2_edge_count"] == 0
    assert result["malformed_or_ambiguous_w4_receipt_count"] == 3


def test_empty_or_duplicated_source_selection_fails_closed():
    assert inspect_native_source_parent_w4_ancestry(scope(), [])["status"] == (
        "original_source_parent_selection_invalid"
    )
    assert inspect_native_source_parent_w4_ancestry(
        scope(), ["native-A", "native-A"]
    )["sources"] == []


def test_foreign_native_id_does_not_change_candidates():
    data = inspect_native_source_parent_w4_ancestry(
        scope(wall("wall-X", frag("split-1", source_ids=("other",)))),
        ["native-A"],
    )
    result = data["sources"][0]
    assert result["matched_w4_candidate_count"] == 0
    assert result["malformed_or_ambiguous_w4_receipt_count"] == 0
    assert data["candidate_only_no_w4_owner_assignment"] is True


def test_real_producer_flat_w4_source_line_is_valid_native_ancestry():
    # Production PhysicalWallSourceEdgeFragment.geometry is four scalars,
    # unlike the two-pair format used by source room polygon edges.
    data = inspect_native_source_parent_w4_ancestry(
        scope(wall("w4-from-production", frag(
            "split_21306", source_ids=("d50048i0",),
            geom=(260.16000366, 476.48010254, 226.31999207, 476.48010254),
        ))),
        ["d50048i0"],
    )
    row = data["sources"][0]
    assert row["matched_w4_candidate_count"] == 1
    assert row["matched_source_w2_edge_count"] == 1
    assert row["malformed_or_ambiguous_w4_receipt_count"] == 0
    assert row["candidate_w4_ancestry_receipts"][0]["source_w2_edge_id"] == "split_21306"
    assert row["source_wall_role_authenticated"] is False


def test_real_producer_flat_invalid_values_fail_closed():
    for geometry in (
        (float("nan"), 0, 1, 0),
        (float("inf"), 0, 1, 0),
        (0, 0, 0, 0),
        (0, 0, 1),
        None,
    ):
        data = inspect_native_source_parent_w4_ancestry(
            scope(wall("wall-A", frag("split-1", geom=geometry))),
            ["native-A"],
        )
        row = data["sources"][0]
        assert row["matched_source_w2_edge_count"] == 0
        assert row["malformed_or_ambiguous_w4_receipt_count"] == 1
        assert row["source_w4_receipt_universe_complete"] is False
