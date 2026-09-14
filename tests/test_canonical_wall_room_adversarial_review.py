"""Independent adversarial regressions for PR #286.

This review intentionally adds only failing tests. It does not rewrite the
canonical wall/room model.
"""
from types import SimpleNamespace

from pb_canonical_wall_room_evidence_model import (
    FAMILY_NATIVE_LAYER_WALL_SUPPORT,
    FAMILY_PAIRED_WALL_FACES,
    FAMILY_U2_PHYSICAL_WALL_LINEWORK,
    FAMILY_VALID_JUNCTION_BEHAVIOR,
    _paired_face_atom,
)
from pb_wall_room_topology_wall_identity_v2 import canonical_wall_candidate_id_v2
from tests.test_canonical_wall_room_model import _existence_status, _run_pipeline, _seg


def test_same_native_metadata_source_does_not_count_as_independent_corroboration():
    """Solid-stroke + layer-name support are partly dependent evidence.

    Both are attributes of the same native primitive. They must not, by
    themselves, satisfy a rule requiring two causally independent sources.
    """
    out = _run_pipeline([_seg("lonely", 0, 0, 100, 0, layer="Wall")])
    assert len(out["resolved"]) == 1
    wall = out["resolved"][0]
    families = set(wall.metadata.get("physical_evidence_families", []))
    assert {FAMILY_U2_PHYSICAL_WALL_LINEWORK, FAMILY_NATIVE_LAYER_WALL_SUPPORT} <= families
    assert _existence_status(wall) != "corroborated"


def test_provenance_first_identity_must_distinguish_distinct_geometry_from_same_native_source():
    """One native primitive can contribute to more than one derived wall hypothesis.

    Re-chunking of the same physical wall should be stable, but distinct
    derived geometry must not collide merely because the U1 source-id set is
    identical.
    """
    edges = {
        "left": {"id": "left", "primitive_lineage": {"source_primitive_ids": ["native_whole"]}},
        "right": {"id": "right", "primitive_lineage": {"source_primitive_ids": ["native_whole"]}},
    }
    left_id = canonical_wall_candidate_id_v2("v1", ["left"], edges, (0.0, 0.0), (40.0, 0.0))
    right_id = canonical_wall_candidate_id_v2("v1", ["right"], edges, (60.0, 0.0), (100.0, 0.0))
    assert left_id != right_id


def test_one_end_connected_short_tick_does_not_become_existence_corroborated():
    """A short tick touching a carrier at one end is not a physical wall proof.

    Current junction logic treats T_JUNCTION+ENDPOINT as a valid independent
    family; together with the near-universal solid-stroke U2 atom that is
    enough to mark this hatch/dimension-like tick as existence-corroborated.
    """
    out = _run_pipeline(
        [
            _seg("carrier", -50, 0, 50, 0, layer="Layer 1"),
            _seg("tick", 0, 0, 0, 3.6, layer="Layer 1"),
        ]
    )
    short_wall = min(
        out["resolved"],
        key=lambda w: sum(
            ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5
            for a, b in zip(w.centerline_pts, w.centerline_pts[1:])
        ),
    )
    families = set(short_wall.metadata.get("physical_evidence_families", []))
    assert FAMILY_U2_PHYSICAL_WALL_LINEWORK in families
    assert FAMILY_VALID_JUNCTION_BEHAVIOR in families
    assert _existence_status(short_wall) != "corroborated"


def test_paired_face_support_must_not_leak_to_unrelated_descendant_sharing_native_parent():
    """A native face-pair hit is not proof for every split descendant.

    Two derived wall candidates can share the same U1 native parent while
    occupying disjoint subspans. A face pair that supports one subspan must
    not automatically support the other merely because both lineage sets
    contain the same native primitive id.
    """
    edges_by_id = {
        "left_child": {
            "id": "left_child",
            "primitive_lineage": {"source_primitive_ids": ["native_shared"]},
        },
        "right_child": {
            "id": "right_child",
            "primitive_lineage": {"source_primitive_ids": ["native_shared"]},
        },
    }
    right_wall = SimpleNamespace(
        candidate_id="right_wall",
        viewport_id="v1",
        face_a_segment_ids=("right_child",),
        face_b_segment_ids=(),
    )
    pair_for_left_subspan = {
        "face_a": "native_shared",
        "face_b": "native_parallel_partner",
        "gap_pt": 10.0,
    }
    atom = _paired_face_atom(
        right_wall,
        [pair_for_left_subspan],
        edges_by_id,
        document_id="doc",
        page_id="page",
    )
    assert atom is None
