"""Do not choose one candidate from 3 original window fragments by proximity."""
from dataclasses import replace
import pytest

from pb_original_window_canonical_representative_review import (
    compare_figured_window_source_to_canonical_representatives,
)
from pb_source_native_figured_window_bridge_review import (
    NativeFiguredWindowBridgeReview,
    NativeFiguredWindowBridgeReviewResult,
)
from pb_source_window_footprint_continuity import WindowFootprintBridge
from tests.test_live_opening_area_quantity_publication import _opening

SHA="a"*64

def _bridge(x, a, b, m, n):
    return WindowFootprintBridge(
        left_host_path_id=a,right_host_path_id=b,
        marker_path_ids=(m,n),label_text="ASW",
        bounds_pdf_pts=(float(x),0.,float(x+10),2.),
        axis="h",page_index=2,
    )

def _source_witness(bridge, token):
    return NativeFiguredWindowBridgeReview(
        receipt_id=token,source_sha256=SHA,page_index=2,
        native_host_path_ids=(bridge.left_host_path_id,bridge.right_host_path_id),
        native_window_marker_path_ids=bridge.marker_path_ids,
        figured_word_indices=(100,101,102,103),
        unordered_figured_axes_mm=(1200.,1810.),
        provisional_product_m2=2.172,
    )

def _source(*bridges):
    return NativeFiguredWindowBridgeReviewResult(
        source_sha256=SHA,page_index=2,
        native_window_bridge_count=len(bridges),
        source_figured_two_axis_window_line_count=len(bridges),
        unique_source_figured_window_bridges=tuple(
            _source_witness(b, f"window-review-{i}") for i,b in enumerate(bridges)
        ),ambiguous_lines_or_bridges=0,
    )

def _candidate(name,x,host=True,kind=None):
    return replace(
        _opening(canonical_id=name,kind=kind,area_m2=None,area_basis=None),
        source_geometries=((float(x),1.,float(x)+1.,1.),),
        host_wall_id=("wall-"+name if host else None),
        host_binding_record_id=("host-"+name if host else None),
        host_frame_record_id=None,
    )

def test_source_printed_two_axis_windows_group_native_representatives_not_installed_count():
    a,b,c=_bridge(10,11,12,13,14),_bridge(30,21,22,23,24),_bridge(50,31,32,33,34)
    objs=(
        _candidate("one-a",12,True), _candidate("one-b",14,False), _candidate("one-c",17,False),
        _candidate("two-a",32,True), _candidate("two-b",35,True),
    )
    r=compare_figured_window_source_to_canonical_representatives(
        _source(a,b,c), (a,b,c), objs, expected_source_sha256=SHA,
    )
    assert r["source_figured_window_witness_count"]==3
    assert r["source_canonical_window_representative_count"]==5
    assert r["windows_with_one_wall_id_representative"]==1
    assert r["windows_with_competing_wall_id_representatives"]==1
    assert r["windows_without_any_canonical_opening_representation"]==1
    assert [q["canonical_representative_count"] for q in r["window_source_review_rows"]]==[3,2,0]
    assert r["customer_quantity_authorized"] is False
    assert r["official_benchmark_scored"] is False
    assert "one-a" not in str(r) and "two-b" not in str(r)

def test_original_source_page_and_digest_must_match_before_correspondence():
    b=_bridge(10,11,12,13,14)
    bad=replace(_candidate("foreign",12), source_sha256="b"*64)
    wrong_page=replace(_candidate("other-page",12),page_id="4")
    r=compare_figured_window_source_to_canonical_representatives(
        _source(b),(b),(bad,wrong_page),expected_source_sha256=SHA,
    )
    assert r["windows_without_any_canonical_opening_representation"]==1
    with pytest.raises(ValueError,match="untrusted"):
        compare_figured_window_source_to_canonical_representatives(
            _source(b),(b),(),expected_source_sha256="b"*64,
        )

def test_duplicate_canonical_identity_fails_closed():
    b=_bridge(10,11,12,13,14)
    c=_candidate("same",12)
    with pytest.raises(ValueError,match="duplicate_or_untrusted"):
        compare_figured_window_source_to_canonical_representatives(
            _source(b),(b),(c,c),expected_source_sha256=SHA,
        )

def test_canonical_door_conflict_cannot_be_promoted_to_window():
    b=_bridge(10,11,12,13,14)
    r=compare_figured_window_source_to_canonical_representatives(
        _source(b),(b),(_candidate("door",12,kind="door"),),expected_source_sha256=SHA,
    )
    assert r["source_canonical_window_representative_count"]==0
    assert r["conflicting_existing_door_type_count"]==1
    assert r["opening_metric_authorized"] is False

def test_competing_overlapping_native_bridges_never_nearest_rank():
    b1,b2=_bridge(10,11,12,13,14),_bridge(10,21,22,23,24)
    r=compare_figured_window_source_to_canonical_representatives(
        _source(b1,b2),(b1,b2),(_candidate("overlap",12),),expected_source_sha256=SHA,
    )
    assert r["ambiguous_canonical_multispan_count"]==1
    assert r["source_canonical_window_representative_count"]==0

def test_source_window_witness_must_have_exact_native_host_and_marker_ids():
    b=_bridge(10,11,12,13,14)
    other=_bridge(10,21,22,23,24)
    with pytest.raises(ValueError,match="no_exact_original_bridge"):
        compare_figured_window_source_to_canonical_representatives(
            _source(b),(other,),(),expected_source_sha256=SHA,
        )

def test_duplicate_source_window_bridge_fails_closed():
    b=_bridge(10,11,12,13,14)
    with pytest.raises(ValueError,match="duplicate_native_source"):
        compare_figured_window_source_to_canonical_representatives(
            _source(b),(b,b),(),expected_source_sha256=SHA,
        )

def test_mutated_source_witness_receipt_fails_closed():
    b=_bridge(10,11,12,13,14)
    bad=replace(_source_witness(b,"bad"),native_host_path_ids=(11,))
    fake=replace(_source(b),unique_source_figured_window_bridges=(bad,))
    with pytest.raises(ValueError,match="witness_untrusted"):
        compare_figured_window_source_to_canonical_representatives(
            fake,(b,),(),expected_source_sha256=SHA,
        )
