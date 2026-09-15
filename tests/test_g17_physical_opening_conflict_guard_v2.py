from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES,
    OPENING_JAMB_BOUNDARY_KIND,
    WALL_FACE_INTERRUPTION_KIND,
)
from tests.g17_phase2_test_support import make_base, publish, selector


def test_incompatible_structural_groupings_remain_conflict() -> None:
    producer, published, _, physical, roots = make_base()
    specs = (
        ("face-a", WALL_FACE_INTERRUPTION_KIND, (100.0, 100.0, 140.0, 100.0), roots[0]),
        ("face-b", WALL_FACE_INTERRUPTION_KIND, (100.0, 110.0, 140.0, 110.0), roots[1]),
        ("jamb-ab-left", OPENING_JAMB_BOUNDARY_KIND, (100.0, 100.0, 100.0, 110.0), roots[2]),
        ("jamb-ab-right", OPENING_JAMB_BOUNDARY_KIND, (140.0, 100.0, 140.0, 110.0), roots[3]),
        ("face-c", WALL_FACE_INTERRUPTION_KIND, (100.0, 120.0, 140.0, 120.0), roots[4]),
        ("jamb-ac-left", OPENING_JAMB_BOUNDARY_KIND, (100.0, 100.0, 100.0, 120.0), roots[5]),
        ("jamb-ac-right", OPENING_JAMB_BOUNDARY_KIND, (140.0, 100.0, 140.0, 120.0), roots[6]),
    )
    snapshot_id = published.snapshot.snapshot_id
    for observation_id, kind, geometry, root_id in specs:
        snapshot_id = publish(
            producer,
            published,
            snapshot_id=snapshot_id,
            root_id=root_id,
            observation_id=observation_id,
            kind=kind,
            geometry=geometry,
        ).snapshot_id

    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.proposition is None
    assert result.existence_record is None
    assert AMBIGUOUS_PHYSICAL_OPENING_CANDIDATES in result.reason_codes
