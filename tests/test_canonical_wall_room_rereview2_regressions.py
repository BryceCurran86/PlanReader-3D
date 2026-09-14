"""Minimal adversarial regression from exact-head re-review of PR #286 @ cc8092d.

Test-only. No production/research architecture changes and no quantity publishing.
"""
from types import SimpleNamespace

from pb_canonical_wall_room_evidence_model import _native_layer_atom


def test_native_layer_support_fails_closed_if_any_contributing_edge_has_layer_conflict():
    """A conflicted contributing edge cannot be ignored while another A-WALL edge promotes the whole wall.

    The review contract requires candidate-wide fail-closed behavior for native-layer conflict.
    """
    wall = SimpleNamespace(
        candidate_id="mixed_conflict_wall",
        viewport_id="v1",
        face_a_segment_ids=("edge_wall", "edge_conflict"),
        face_b_segment_ids=(),
    )
    edges_by_id = {
        "edge_wall": {
            "id": "edge_wall",
            "primitive_lineage": {
                "attribute_status": {"layer": "agreed"},
                "source_records": [
                    {"layer_present": True, "layer": "A-WALL"},
                ],
            },
        },
        "edge_conflict": {
            "id": "edge_conflict",
            "primitive_lineage": {
                "attribute_status": {"layer": "conflict"},
                "source_records": [
                    {"layer_present": True, "layer": "A-WALL"},
                    {"layer_present": True, "layer": "Glazing"},
                ],
            },
        },
    }

    atom = _native_layer_atom(
        wall,
        edges_by_id,
        document_id="doc",
        page_id="page",
    )
    assert atom is None
