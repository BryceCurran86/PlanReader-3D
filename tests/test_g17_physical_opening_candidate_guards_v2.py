from pb_migration_contracts import EvidenceResolutionStatus
from tests.g17_phase2_test_support import make_base, publish, selector


def _single_candidate(kind: str, observation_id: str):
    producer, published, _, physical, roots = make_base()
    snapshot = publish(
        producer,
        published,
        snapshot_id=published.snapshot.snapshot_id,
        root_id=roots[0],
        observation_id=observation_id,
        kind=kind,
        geometry=(100.0, 100.0, 140.0, 100.0),
    )
    return physical.prove_existence(selector(published, snapshot.snapshot_id, observation_id))


def test_swing_arc_alone_remains_candidate() -> None:
    result = _single_candidate("opening_swing_arc", "swing-only")
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.proposition is None
    assert result.existence_record is None


def test_wall_gap_alone_remains_candidate() -> None:
    result = _single_candidate("wall_gap_candidate", "gap-only")
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.proposition is None
    assert result.existence_record is None
