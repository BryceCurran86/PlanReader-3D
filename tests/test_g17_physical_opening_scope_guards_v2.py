from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import OPENING_JAMB_BOUNDARY_KIND, WALL_FACE_INTERRUPTION_KIND
from tests.g17_phase2_test_support import make_base, publish, selector


def _publish_structure(*, left_x: float = 100.0, jamb_viewport: str = "vp-1", jamb_page: str = "1"):
    producer, published, _, physical, roots = make_base()
    specs = (
        ("face-a", WALL_FACE_INTERRUPTION_KIND, (100.0, 100.0, 140.0, 100.0), roots[0], "vp-1", "1"),
        ("face-b", WALL_FACE_INTERRUPTION_KIND, (100.0, 110.0, 140.0, 110.0), roots[1], "vp-1", "1"),
        ("jamb-left", OPENING_JAMB_BOUNDARY_KIND, (left_x, 100.0, left_x, 110.0), roots[2], jamb_viewport, jamb_page),
        ("jamb-right", OPENING_JAMB_BOUNDARY_KIND, (140.0, 100.0, 140.0, 110.0), roots[3], "vp-1", "1"),
    )
    snapshot_id = published.snapshot.snapshot_id
    for observation_id, kind, geometry, root_id, viewport_id, page_id in specs:
        snapshot_id = publish(
            producer,
            published,
            snapshot_id=snapshot_id,
            root_id=root_id,
            observation_id=observation_id,
            kind=kind,
            geometry=geometry,
            viewport_id=viewport_id,
            page_id=page_id,
        ).snapshot_id
    return published, physical, snapshot_id


def _assert_not_resolved(published, physical, snapshot_id: str) -> None:
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.proposition is None
    assert result.existence_record is None


def test_nearby_jamb_does_not_self_assemble_by_proximity() -> None:
    _assert_not_resolved(*_publish_structure(left_x=100.01))


def test_cross_viewport_structural_evidence_does_not_combine() -> None:
    _assert_not_resolved(*_publish_structure(jamb_viewport="vp-other"))


def test_cross_page_structural_evidence_does_not_combine() -> None:
    _assert_not_resolved(*_publish_structure(jamb_page="2"))
