"""Independent source quantities cannot reuse one figured pair for two rooms."""
from dataclasses import replace
import pytest
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_live_room_area_source_closed_export import _firm_room_area_quantities
from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
from pb_migration_contracts import QuantityEvidence
from pb_source_closed_run_export import SourceClosedRunConflictError


def _original(n,pair):
    return QuantityEvidence(
        quantity_id=f"room-area-{n}",family="room_area",
        semantic_key=f"room_area:physical-room-{n}",value=15.25,unit="m2",
        input_entity_ids=(f"physical-room-{n}",),evidence_ids=(f"area-source-{n}",),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status="firm",confidence=1.0,metadata={"figured_dimension_ids":list(pair)},
    )


def _claim(*quantities):
    claim=object.__new__(LivePhysicalNetWallClaim)
    object.__setattr__(claim,"room_area_quantity_evidence",tuple(quantities))
    return claim


def test_independent_real_source_dimension_pairs_remain_eligible():
    a=_original("a",("horizontal-a","vertical-a"))
    b=_original("b",("horizontal-b","vertical-b"))
    assert _firm_room_area_quantities(_claim(a,b)) == (a,b)


def test_same_original_figured_axes_reused_for_other_room_cannot_seal():
    a=_original("a",("h-shared","v-shared"))
    b=_original("b",("v-shared","h-shared"))
    for source in ((a,b),(b,a)):
        with pytest.raises(SourceClosedRunConflictError,match="competing rooms"):
            _firm_room_area_quantities(_claim(*source))


def test_one_shared_axis_with_two_original_independent_verticals_is_allowed():
    a=_original("a",("h-shared","v-a"))
    b=_original("b",("h-shared","v-b"))
    assert len(_firm_room_area_quantities(_claim(a,b))) == 2


def test_invalid_original_figured_pair_receipt_cannot_seal():
    source=replace(_original("a",("h","v")),metadata={"figured_dimension_ids":["same","same"]})
    with pytest.raises(SourceClosedRunConflictError,match="figured pair invalid"):
        _firm_room_area_quantities(_claim(source))


def test_same_original_pair_cannot_reissue_second_quantity_to_same_room():
    original=_original("a",("h-original","v-original"))
    duplicate=replace(
        original,
        quantity_id="room-area-a-reissued",
        evidence_ids=("new-area-observation-id",),
    )
    for order in ((original,duplicate),(duplicate,original)):
        with pytest.raises(SourceClosedRunConflictError,match="second room-area quantity"):
            _firm_room_area_quantities(_claim(*order))
