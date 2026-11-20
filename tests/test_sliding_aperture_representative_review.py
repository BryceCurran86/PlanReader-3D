"""One original native sliding aperture can own several source candidates, not doors."""
from dataclasses import replace
import pytest

from pb_source_sliding_aperture_representative_review import (
    review_sliding_aperture_representative_owners,
)
from pb_source_sliding_door_footprint_continuity import ExteriorSlidingDoorFootprintBridge
from pb_live_opening_area_quantity_publication import _opening_quantity
from tests.test_live_opening_area_quantity_publication import _opening

SHA = "a" * 64

def _bridge(x, left, right):
    return ExteriorSlidingDoorFootprintBridge(
        first_host_path_id=left, second_host_path_id=right,
        jamb_cap_path_ids=(left+10,right+10),
        sliding_track_path_ids=(left+20,right+20),
        label_text="ASD",
        bounds_pdf_pts=(float(x),10.0,float(x+3),80.0),
        axis="v",page_index=2,
    )

def _candidate(id_,x,y,*,kind="door",page="3",sha=SHA):
    return replace(
        _opening(canonical_id=id_,kind=kind),
        source_sha256=sha,page_id=page,
        source_geometries=((float(x),float(y),float(x),float(y+2)),),
    )

def test_six_native_representatives_belong_to_two_not_six_bridges():
    c=(
        _candidate("left-a",11,11),
        _candidate("left-b",11,41),
        _candidate("left-c",11,76),
        _candidate("right-a",31,11),
        _candidate("right-b",31,41),
        _candidate("right-c",31,76),
    )
    q=(_opening_quantity(c[0]),_opening_quantity(c[3]))
    r=review_sliding_aperture_representative_owners(
        (_bridge(10,1,2),_bridge(30,3,4)),c,
        expected_source_sha256=SHA,published_quantities=q,
    )
    assert r["source_bridge_count"]==2
    assert r["source_door_candidates_with_unique_bridge"]==6
    assert r["bridges_with_multiple_native_representatives"]==2
    assert r["native_representatives_on_multi_candidate_bridges"]==6
    assert r["bridges_with_multiple_published_areas"]==0
    assert r["commercial_publication_allowed"] is False
    assert r["benchmark_score_granted"] is False

def test_replayed_second_area_on_same_native_bridge_is_flagged():
    c=(_candidate("a",11,20),_candidate("b",11,60))
    r=review_sliding_aperture_representative_owners(
        (_bridge(10,1,2),),c,
        expected_source_sha256=SHA,
        published_quantities=tuple(_opening_quantity(x) for x in c),
    )
    assert r["bridges_with_multiple_published_areas"]==1
    assert r["commercial_publication_allowed"] is False

def test_wrong_original_sha_and_nonplan_page_do_not_match():
    c=(
        _candidate("foreign",11,20,sha="f"*64),
        _candidate("wrong-page",11,20,page="4"),
        _candidate("window",11,20,kind="window"),
    )
    r=review_sliding_aperture_representative_owners(
        (_bridge(10,1,2),),c,expected_source_sha256=SHA,
    )
    assert r["source_typed_door_candidates_reviewed"]==0
    assert r["source_door_candidates_with_unique_bridge"]==0
    assert r["measurement_authorized"] is False

def test_two_overlapping_bridges_cannot_be_ranked_by_nearest():
    c=(_candidate("a",11,40),)
    r=review_sliding_aperture_representative_owners(
        (_bridge(10,1,2),_bridge(10,4,5)),c,
        expected_source_sha256=SHA,
    )
    assert r["source_door_candidates_overlapping_multiple_bridges"]==1
    assert r["source_door_candidates_with_unique_bridge"]==0

def test_duplicate_original_bridge_identity_fails():
    bridge=_bridge(10,1,2)
    with pytest.raises(ValueError,match="duplicate_native_source"):
        review_sliding_aperture_representative_owners(
            (bridge,bridge),(),expected_source_sha256=SHA,
        )

def test_source_checksum_bool_or_bad_hash_rejected():
    with pytest.raises(ValueError,match="full_original"):
        review_sliding_aperture_representative_owners(
            (),(),expected_source_sha256=True,
        )

def test_duplicate_physical_candidate_id_refused():
    x=_candidate("same",11,50)
    with pytest.raises(ValueError,match="duplicate_or_missing"):
        review_sliding_aperture_representative_owners(
            (_bridge(10,1,2),),(x,x),expected_source_sha256=SHA,
        )

def test_figure_and_distance_alone_do_not_prove_a_wall_or_quantity():
    c=(_candidate("orphan",11,20),)
    r=review_sliding_aperture_representative_owners(
        (_bridge(10,1,2),),c,expected_source_sha256=SHA,
    )
    assert r["source_door_candidates_with_unique_bridge"]==1
    assert r["physical_opening_authenticated"] is False
    assert r["measurement_authorized"] is False
    assert "orphan" not in str(r)
