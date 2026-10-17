"""A genuine FIRM room m² cannot be replayed as a second semantic object."""
from dataclasses import replace
import pytest
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_live_room_area_source_closed_export import _firm_room_area_quantities
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import QuantityEvidence
from pb_source_closed_run_export import SourceClosedRunConflictError


def _quantity():
    return QuantityEvidence(
        quantity_id="original-room-area-quantity",family="room_area",
        semantic_key="room_area:physical-room-a",value=12.5,unit="m2",
        input_entity_ids=("physical-room-a",),evidence_ids=("original-area-proof",),
        formula="original_figured_area",formula_version="1",
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status="firm",confidence=1.0,
    )


def _inventory(quantity):
    claim=object.__new__(LivePhysicalNetWallClaim)
    object.__setattr__(claim,"room_area_quantity_evidence",(quantity,))
    return claim


def test_original_firm_room_area_semantic_owner_is_retained():
    original=_quantity()
    assert _firm_room_area_quantities(_inventory(original)) == (original,)


@pytest.mark.parametrize("semantic", [
    "room_area:another-physical-room", "floor_finish_area:physical-room-a",
    "ceiling_lining:physical-room-a", "room_area:physical-room-a ",
])
def test_forged_or_rekeyed_original_semantic_owner_cannot_seal(semantic):
    with pytest.raises(SourceClosedRunConflictError,match="semantic"):
        _firm_room_area_quantities(_inventory(replace(_quantity(),semantic_key=semantic)))
