from __future__ import annotations

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from tests.g17_phase2_test_support import make_resolved, selector


def test_jamb_bounded_two_face_interruption_resolves_local_existence() -> None:
    _, published, _, physical, _, snapshot_id = make_resolved()
    result = physical.prove_existence(selector(published, snapshot_id, "face-a"))
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == PHYSICAL_OPENING_EXISTS
    assert result.existence_record is not None
