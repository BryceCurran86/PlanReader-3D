"""Independent adversarial regression for PR #286.

This review intentionally adds only a failing test. It does not rewrite the
canonical wall/room model.
"""
from pb_canonical_wall_room_evidence_model import (
    FAMILY_NATIVE_LAYER_WALL_SUPPORT,
    FAMILY_U2_PHYSICAL_WALL_LINEWORK,
)
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
