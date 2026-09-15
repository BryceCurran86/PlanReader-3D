from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, STRUCTURAL_OPENING_CANDIDATE
from tests.g17_phase2_test_support import make_resolved, selector


def test_jamb_bounded_two_face_interruption_resolves_local_existence() -> None:
    _, published, _, physical, _, snapshot_id = make_resolved()
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == PHYSICAL_OPENING_EXISTS
    assert result.existence_record is not None
    assert len(result.existence_record.source_lineage_root_ids) == 4


def test_all_structural_supports_resolve_same_record_id() -> None:
    _, published, _, physical, _, snapshot_id = make_resolved()
    record_ids = set()
    for observation_id in ("face-a", "face-b", "jamb-left", "jamb-right"):
        result = physical.prove_existence(selector(published, snapshot_id, observation_id))
        assert result.existence_record is not None
        record_ids.add(result.existence_record.record_id)
    assert len(record_ids) == 1


def test_shared_native_lineage_cannot_manufacture_corroboration() -> None:
    _, published, _, physical, _, snapshot_id = make_resolved(shared_face_root=True)
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.proposition is None
    assert result.existence_record is None
    assert result.candidate is not None
    assert STRUCTURAL_OPENING_CANDIDATE in result.candidate.reason_codes
