"""Same source room measurement cannot fund two whole ceiling material m² rows."""
import pytest
from pb_live_ceiling_lining_source_closed_export import _require_one_ceiling_per_original_area
from pb_source_closed_run_export import SourceClosedRunConflictError


ORIGINAL_ROOT = ("a" * 64, "rev-1")


def _add(owners, area, ceiling, *, source_root=ORIGINAL_ROOT):
    _require_one_ceiling_per_original_area(
        owners, source_root=source_root,
        upstream_area_id=area, canonical_ceiling_id=ceiling,
    )


def test_one_original_room_area_supports_one_ceiling_object():
    owners={}
    _add(owners,"original-figured-room-area-a","physical-ceiling-a")
    assert owners == {(*ORIGINAL_ROOT, "original-figured-room-area-a"): "physical-ceiling-a"}
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
    assert owners[(*ORIGINAL_ROOT, "source-figured-room-area-1")] == "ceiling-ipf1"


@pytest.mark.parametrize("bad", [None,True,""," source-area","source-area "])
def test_missing_or_modified_original_room_area_source_fails_closed(bad):
    with pytest.raises(SourceClosedRunConflictError,match="upstream"):
        _add({},bad,"ceiling-a")


def test_original_area_helper_requires_exact_root_scoped_ownership():
    owners = {}
    _add(owners, "same-local-original-area", "ceiling-one")
    _add(owners, "same-local-original-area", "ceiling-two",
         source_root=("b" * 64, "rev-2"))
    assert len(owners) == 2
    with pytest.raises(SourceClosedRunConflictError, match="competing ceiling"):
        _add(owners, "same-local-original-area", "third-ceiling")
