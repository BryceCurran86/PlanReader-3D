"""Exact source edge owner receipts do not authorize physical ring repair."""
from dataclasses import replace

from pb_source_room_face_authority import SourceRoomFaceRecord
from tools.diag_gpt2_freezer_source_crossing_wall_owners import (
    source_room_ring_crossing_wall_owner_census,
)


RING = ((0., 0.), (2., 2.), (0., 2.), (2., 0.))


def face(*, owners=None, ring=RING):
    return SourceRoomFaceRecord(
        record_id="original_source_face",
        face_id="face-original",
        document_id="document-original", revision_id="revision-original",
        source_sha256="a"*64, snapshot_id="snapshot-original",
        page_id="7", decision_scope_id="original-floor-plan",
        polygon_pdf_pts=ring, bounding_wall_ids=("w-a", "w-b"),
        area_page_pts2=4.0,
        boundary_wall_edges=(
            (("w-a", (RING[0], RING[1])),
             ("w-b", (RING[2], RING[3])))
            if owners is None else owners
        ),
    )


def test_two_exact_original_owner_receipts_do_not_repair_crossing_or_mint_metric():
    result = source_room_ring_crossing_wall_owner_census(face())
    assert result["source_room_face_record_id"] == "original_source_face"
    assert result["first_source_gate"] == (
        "both_original_ring_edges_have_exact_w4_receipts_crossing_unresolved"
    )
    assert [x["source_ring_edge_index"] for x in result[
        "indexed_original_w4_wall_owner_receipts"
    ]] == [0, 2]
    assert [x["original_indexed_w4_wall_candidate_ids"] for x in result[
        "indexed_original_w4_wall_owner_receipts"
    ]] == [["w-a"], ["w-b"]]
    assert all(x["unique_original_indexed_w4_owner_receipt"]
               for x in result["indexed_original_w4_wall_owner_receipts"])
    assert result["source_crossing_wall_roles_authenticated"] is False
    assert result["source_crossing_physical_wall_equivalence_authenticated"] is False
    assert result["source_room_polygon_repaired"] is False
    assert result["source_room_metric_area_published"] is False
    assert face().polygon_pdf_pts == RING


def test_nearby_parallel_or_partially_overlapping_source_receipt_never_matches():
    source = face(owners=(
        ("w-a", ((0.0001, 0.), (2.0001, 2.))),
        ("w-b", (RING[2], RING[3])),
    ))
    result = source_room_ring_crossing_wall_owner_census(source)
    assert result["first_source_gate"] == (
        "original_ring_crossing_edge_w4_receipt_missing_or_ambiguous"
    )
    assert [row["exact_source_boundary_edge_owner_count"] for row in
            result["indexed_original_w4_wall_owner_receipts"]] == [0, 1]
    assert all(not row["second_physical_room_face_proven"] for row in
               result["indexed_original_w4_wall_owner_receipts"])


def test_multiple_source_walls_on_one_crossing_edge_fails_closed():
    source = face(owners=(
        ("w-a", (RING[0], RING[1])),
        ("w-b", (RING[0], RING[1])),
        ("w-b", (RING[2], RING[3])),
    ))
    result = source_room_ring_crossing_wall_owner_census(source)
    assert result["first_source_gate"] == (
        "original_ring_crossing_edge_w4_receipt_missing_or_ambiguous"
    )
    assert result["indexed_original_w4_wall_owner_receipts"][0][
        "exact_source_boundary_edge_owner_count"
    ] == 2


def test_foreign_malformed_and_missing_source_receipts_abstain():
    original = face()
    for bad in (
        replace(original, boundary_wall_edges=(("foreign-wall",
                  (RING[0], RING[1])),)),
        replace(original, boundary_wall_edges=(("", (RING[0], RING[1])),)),
        replace(original, boundary_wall_edges=(("w-a",
                  ((0., 0.), (float("nan"), 1.))),)),
        replace(original, boundary_wall_edges=(("w-a",
                  ((0., 0.), (10**1000, 1.))),)),
        replace(original, boundary_wall_edges=(("w-a",
                  ((0., 0.), (True, 1.))),)),
        replace(original, boundary_wall_edges=()),
    ):
        result = source_room_ring_crossing_wall_owner_census(bad)
        assert result["source_room_metric_area_published"] is False
        assert result["source_room_polygon_repaired"] is False
        assert result["first_source_gate"] in (
            "original_source_boundary_owner_receipt_invalid",
            "original_ring_crossing_edge_w4_receipt_missing_or_ambiguous",
        )
    assert source_room_ring_crossing_wall_owner_census(object())[
        "first_source_gate"
    ] == "original_source_face_record_unavailable"
    valid = replace(original, polygon_pdf_pts=(
        (0., 0.), (2., 0.), (2., 2.), (0., 2.)
    ))
    assert source_room_ring_crossing_wall_owner_census(valid)[
        "first_source_gate"
    ] == "original_source_ring_crossing_not_verified"


def test_repeated_same_original_w4_candidate_is_not_distinct_physical_wall_proof():
    original = face(owners=(
        ("w-a", (RING[0], RING[1])),
        ("w-a", (RING[0], RING[1])),
        ("w-b", (RING[2], RING[3])),
    ))
    result = source_room_ring_crossing_wall_owner_census(original)
    first, second = result["indexed_original_w4_wall_owner_receipts"]
    assert first["exact_source_boundary_edge_owner_count"] == 2
    assert first["distinct_original_w4_candidate_id_count"] == 1
    assert first["repeated_same_w4_candidate_address_diagnostic_only"] is True
    assert first["competing_distinct_w4_candidate_addresses_diagnostic_only"] is False
    assert first["unique_original_indexed_w4_owner_receipt"] is False
    assert second["distinct_original_w4_candidate_id_count"] == 1
    assert result["first_source_gate"] == (
        "original_ring_crossing_edge_w4_receipt_missing_or_ambiguous"
    )
    assert result["source_room_polygon_repaired"] is False
    assert result["source_room_metric_area_published"] is False


def test_distinct_original_w4_candidate_addresses_remain_unproven():
    original = face(owners=(
        ("w-a", (RING[0], RING[1])),
        ("w-b", (RING[0], RING[1])),
        ("w-b", (RING[2], RING[3])),
    ))
    result = source_room_ring_crossing_wall_owner_census(original)
    first = result["indexed_original_w4_wall_owner_receipts"][0]
    assert first["exact_source_boundary_edge_owner_count"] == 2
    assert first["distinct_original_w4_candidate_id_count"] == 2
    assert first["repeated_same_w4_candidate_address_diagnostic_only"] is False
    assert first["competing_distinct_w4_candidate_addresses_diagnostic_only"] is True
    assert result["source_crossing_physical_wall_equivalence_authenticated"] is False
