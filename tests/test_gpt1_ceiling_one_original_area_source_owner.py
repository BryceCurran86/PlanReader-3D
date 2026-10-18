"""Same source room measurement cannot fund two whole ceiling material m² rows."""
import pytest
from pb_live_ceiling_lining_source_closed_export import _require_one_ceiling_per_original_area
from pb_source_closed_run_export import SourceClosedRunConflictError


def _add(owners,area,ceiling):
    _require_one_ceiling_per_original_area(
        owners,upstream_area_id=area,canonical_ceiling_id=ceiling,
    )


def test_one_original_room_area_supports_one_ceiling_object():
    owners={}
    _add(owners,"original-figured-room-area-a","physical-ceiling-a")
    assert owners == {"original-figured-room-area-a":"physical-ceiling-a"}
    _add(owners,"original-figured-room-area-a","physical-ceiling-a")


def test_independently_measured_two_ceiling_physical_zones_are_allowed():
    owners={}
    _add(owners,"original-area-a","ceiling-a")
    _add(owners,"original-area-b","ceiling-b")
    assert len(owners)==2


def test_same_original_measured_room_area_cannot_issue_second_material_surface():
    owners={}
    _add(owners,"source-figured-room-area-1","ceiling-ipf1")
    with pytest.raises(SourceClosedRunConflictError,match="competing ceiling"):
        _add(owners,"source-figured-room-area-1","ceiling-grid")
    assert owners["source-figured-room-area-1"] == "ceiling-ipf1"


@pytest.mark.parametrize("bad", [None,True,""," source-area","source-area "])
def test_missing_or_modified_original_room_area_source_fails_closed(bad):
    with pytest.raises(SourceClosedRunConflictError,match="upstream"):
        _add({},bad,"ceiling-a")
