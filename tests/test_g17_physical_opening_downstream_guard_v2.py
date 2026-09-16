from dataclasses import fields

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningExistenceRecord
from tests.g17_phase2_test_support import make_resolved, selector


def test_g17_existence_contract_exposes_no_downstream_measurement_authority() -> None:
    names = {field.name for field in fields(PhysicalOpeningExistenceRecord)}
    assert names.isdisjoint(
        {
            "width",
            "height",
            "area",
            "host_id",
            "host_wall_id",
            "host_binding",
            "opening_universe_complete",
            "deduction",
            "net_wall_area",
            "firm",
        }
    )

    _, published, _, physical, _, snapshot_id = make_resolved()
    left = selector(published, snapshot_id, "face-a")
    raw_result = physical.prove_existence(left)
    assert raw_result.existence_record is None

    identity = physical.compare_identity(
        left,
        selector(published, snapshot_id, "jamb-left"),
    )
    assert identity.status is EvidenceResolutionStatus.ABSTAINED
    assert identity.proven_same is False

    assert physical.capabilities() == {
        "physical_opening_existence": True,
        "physical_opening_identity": True,
        "opening_universe_complete": False,
        "opening_dimensions": False,
        "host_identity": False,
        "host_binding": False,
        "physical_void": False,
        "net_wall_area": False,
    }
