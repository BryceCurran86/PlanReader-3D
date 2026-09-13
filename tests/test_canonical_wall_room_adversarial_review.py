"""Independent adversarial regressions for PR #286.

This review intentionally adds only failing tests. It does not rewrite the
canonical wall/room model.
"""
from pb_canonical_wall_room_evidence_model import (
    FAMILY_NATIVE_LAYER_WALL_SUPPORT,
    FAMILY_U2_PHYSICAL_WALL_LINEWORK,
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
