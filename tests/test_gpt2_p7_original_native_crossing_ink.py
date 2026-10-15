"""Original indexed native ink positive/negative controls; no room authority."""
from copy import deepcopy
import fitz
import pytest
from tools.diag_gpt2_p7_original_native_crossing_ink import (
    census_original_native_linear_ink,replay_original_source,
)


def drawings():
    return [
        {"type":"s","items":[("l",fitz.Point(0,0),fitz.Point(10,0))],
         "seqno":4,"width":1.0,"layer":"UNKNOWN","color":(0,0,0)},
        {"type":"s","items":[("re",fitz.Rect(30,30,40,40),1)],
         "seqno":5,"width":1.0,"layer":"GRID","color":(0,0,0)},
        {"type":"s","items":[("l",fitz.Point(0,0),fitz.Point(10,0))],
         "seqno":6,"width":1.0,"layer":"OTHER"},
        {"type":"f","items":[("c",fitz.Point(0,0),fitz.Point(1,1),
                                 fitz.Point(2,2),fitz.Point(3,3))],
         "seqno":7},
    ]


def test_complete_indexed_source_census_retains_all_competing_paint_not_roles():
    native=drawings()
    old=deepcopy(native)
    report=census_original_native_linear_ink(
        native,source_atoms=[
            ((2,0),(9,0)),
            ((30,31),(30,39)),
            ((20,0),(25,0)),
        ],
    )
    rows=report["source_native_linear_ink_queries"]
    assert rows[0]["original_indexed_linear_native_full_span_count"]==2
    assert [x["original_native_primitive_ref"]
            for x in rows[0]["original_indexed_native_linear_receipts"]]==[
                "d0i0","d2i0",
            ]
    assert rows[1]["original_indexed_linear_native_full_span_count"]==1
    assert rows[1]["original_indexed_native_linear_receipts"][0][
        "original_native_primitive_ref"]=="d1i0e3"
    assert rows[2]["original_indexed_linear_native_full_span_count"]==0
    assert not report["source_role_or_room_authentication_granted"]
    assert report["new_commercial_quantities"]==[]
    assert native==old


@pytest.mark.parametrize("atom",[
    ((2,0.0002),(8,0.0002)),
    ((-1,0),(4,0)),
    ((2,0),(12,0)),
    ((2,0),(2,3)),
])
def test_original_line_not_fully_spanning_query_never_passes(atom):
    report=census_original_native_linear_ink(drawings(),source_atoms=[atom])
    assert not report["source_native_linear_ink_queries"][0][
        "original_indexed_native_linear_receipts"
    ]


def test_duplicate_or_nonfinite_source_queries_rejected():
    with pytest.raises(ValueError,match="duplicate_original_producer_atom_query"):
        census_original_native_linear_ink(
            drawings(),source_atoms=[((0,0),(1,0)),((0,0),(1,0))]
        )
    with pytest.raises(ValueError,match="selected native wall edge invalid"):
        census_original_native_linear_ink(
            drawings(),source_atoms=[((float("nan"),0),(1,0))]
        )
    with pytest.raises(ValueError,match="original_native_drawing_universe_unavailable"):
        census_original_native_linear_ink([],source_atoms=[((0,0),(1,0))])


def test_foreign_source_sha_or_page_never_reaches_native_census():
    with pytest.raises(ValueError,match="original_source_sha_mismatch"):
        replay_original_source(
            b"%PDF-source",original_sha256="f"*64,page_no=7,
            source_atoms=[((0,0),(1,0))]
        )
    with pytest.raises(ValueError,match="original_source_pdf_bytes_and_page_required"):
        replay_original_source(
            b"%PDF-source",original_sha256="f"*64,page_no=0,
            source_atoms=[((0,0),(1,0))]
        )


def test_same_native_source_profile_yields_order_independent_candidate_ids():
    a=census_original_native_linear_ink(drawings(),source_atoms=[((2,0),(9,0))])
    b=census_original_native_linear_ink(list(reversed(drawings())),
        source_atoms=[((2,0),(9,0))])
    assert a["source_native_linear_ink_queries"][0][
        "original_indexed_linear_native_full_span_count"]==2
    assert b["source_native_linear_ink_queries"][0][
        "original_indexed_linear_native_full_span_count"]==2
    # Absolute original source drawing path indices are NOT invariant to
    # an actual source-path reorder; we never alias those identities.
    assert a["source_native_linear_ink_queries"][0][
        "original_indexed_native_linear_receipts"] != b[
            "source_native_linear_ink_queries"][0][
            "original_indexed_native_linear_receipts"]


def test_real_pdf_degenerate_native_line_is_retained_as_negative_not_fatal():
    native=drawings()
    native.insert(0,{"type":"s","items":[
        ("l",fitz.Point(5,5),fitz.Point(5,5)),
        ("re",fitz.Rect(8,8,8,12),1),
    ],"seqno":2})
    report=census_original_native_linear_ink(
        native,source_atoms=[((2,0),(9,0))]
    )
    assert report["original_indexed_degenerate_linear_source_count"]>=1
    assert "d0i0" in report["original_indexed_degenerate_linear_source_ids"]
    assert report["source_native_linear_ink_queries"][0][
        "original_indexed_linear_native_full_span_count"]==2
    assert report["new_commercial_quantities"]==[]
