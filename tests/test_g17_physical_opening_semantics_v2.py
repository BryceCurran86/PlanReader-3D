from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    STRUCTURAL_OPENING_CANDIDATE,
    VISIBLE_SOURCE_AUTHORITY_REQUIRED,
)
from tests.g17_phase2_test_support import make_resolved, selector


def test_caller_labeled_two_face_interruption_cannot_resolve_local_existence() -> None:
    _, published, _, physical, _, snapshot_id = make_resolved()
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.proposition is None
    assert result.existence_record is None
    assert result.candidate is not None
    assert VISIBLE_SOURCE_AUTHORITY_REQUIRED in result.candidate.reason_codes


def test_all_caller_labeled_structural_supports_remain_non_authoritative() -> None:
    _, published, _, physical, _, snapshot_id = make_resolved()
    candidate_ids = set()
    for observation_id in ("face-a", "face-b", "jamb-left", "jamb-right"):
        result = physical.prove_existence(selector(published, snapshot_id, observation_id))
        assert result.status is EvidenceResolutionStatus.CANDIDATE
        assert result.proposition is None
        assert result.existence_record is None
        assert result.candidate is not None
        candidate_ids.add(result.candidate.candidate_id)
    assert len(candidate_ids) == 1


def test_shared_native_lineage_cannot_manufacture_corroboration() -> None:
    _, published, _, physical, _, snapshot_id = make_resolved(shared_face_root=True)
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.proposition is None
    assert result.existence_record is None
    assert result.candidate is not None
    assert STRUCTURAL_OPENING_CANDIDATE in result.candidate.reason_codes
    assert VISIBLE_SOURCE_AUTHORITY_REQUIRED in result.candidate.reason_codes
