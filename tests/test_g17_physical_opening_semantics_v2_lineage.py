from pb_migration_contracts import EvidenceResolutionStatus
from tests.g17_phase2_test_support import make_resolved, selector


def test_replayed_structural_observation_does_not_create_second_existence() -> None:
    _, published, _, physical, _, snapshot_id = make_resolved(duplicate_face=True)
    first = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    replay = physical.prove_existence(selector(published, snapshot_id, "face-a-duplicate"))
    assert first.status is EvidenceResolutionStatus.CORROBORATED
    assert replay.status is EvidenceResolutionStatus.CORROBORATED
    assert first.existence_record is not None
    assert replay.existence_record is not None
    assert first.existence_record.record_id == replay.existence_record.record_id
