"""Topology rings expose unique native face refs; they are not quantities."""
from __future__ import annotations

from planreader_next.dimension_association import associate_dimension_inventory_to_native_faces
from planreader_next.dimension_index import inventory_page_dimensions
from planreader_next.enclosure import propose_room_enclosures
from planreader_next.engine import load_native_page
from planreader_next.topology_faces import native_finished_face_receipts
from tests.test_layered_wall_doorway_room_face_wiring_v1 import layered_room_pdf


def test_topology_ring_emits_unique_native_face_refs_without_publishing(tmp_path):
    pdf = tmp_path / "layered-faces.pdf"
    pdf.write_bytes(layered_room_pdf(door=True, swing=True, vertical_pairs="full_only"))
    page = load_native_page(pdf, 0)
    enclosure = propose_room_enclosures(page, pdf)
    assert enclosure["candidate_enclosed_regions"] == 1
    receipts = enclosure["topology_face_receipts"]
    assert receipts["commercial_publishable"] is False
    assert receipts["finished_face_authenticated"] is False
    assert receipts["physical_item_authenticated"] is False
    assert receipts["topology_only"] is True
    assert receipts["receipt_count"] >= 4
    refs = [item["face_segment_ref"] for item in receipts["item_faces"]]
    assert len(refs) == len(set(refs))
    assert all(item["item_kind"] == "room_finished_face" for item in receipts["item_faces"])
    item_faces = [
        {
            "item_id": item["item_id"],
            "item_kind": item["item_kind"],
            "face_segment_ref": item["face_segment_ref"],
        }
        for item in receipts["item_faces"]
    ]
    associated = associate_dimension_inventory_to_native_faces(
        page, inventory_page_dimensions(page), item_faces,
    )
    assert associated["commercial_publishable"] is False
    assert associated["official_score"] is None
    assert all(not row["physical_item_authenticated"] for row in associated["shadow_face_bindings"])


def test_doorway_closure_edges_are_not_finished_faces(tmp_path):
    pdf = tmp_path / "layered-door.pdf"
    pdf.write_bytes(layered_room_pdf(door=True, swing=True))
    page = load_native_page(pdf, 0)
    enclosure = propose_room_enclosures(page, pdf)
    receipts = native_finished_face_receipts(page, enclosure["regions"])
    region = enclosure["regions"][0]
    closure_edges = [
        index for index, owners in enumerate(region["edge_owner_ids"])
        if any(str(owner).startswith("layered_doorway_closure:") for owner in owners)
    ]
    assert closure_edges
    emitted = {item["item_id"] for item in receipts["item_faces"]}
    for index in closure_edges:
        assert f"{region['region_id']}/edge/{index}" not in emitted
