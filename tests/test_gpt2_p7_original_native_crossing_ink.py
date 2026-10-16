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



def test_original_indexed_cubic_true_collinear_source_and_fill_roles_preserved():
    from tools.diag_gpt2_p7_original_native_crossing_ink import (
        census_original_native_cubic_ink,
    )
    native = [
        {"type": "s", "color": (0, 0, 0), "items": [(
            "c", fitz.Point(0, 0), fitz.Point(3, 0),
            fitz.Point(7, 0), fitz.Point(10, 0),
        )]},
        {"type": "f", "fill": (1, 1, 1), "items": [(
            "c", fitz.Point(10, 0), fitz.Point(7, 0),
            fitz.Point(3, 0), fitz.Point(0, 0),
        )]},
        {"type": "s", "items": [(
            "c", fitz.Point(0, 0), fitz.Point(3, 0),
            fitz.Point(7, 0.001), fitz.Point(10, 0),
        )]},
        {"type": "s", "items": [(
            "c", fitz.Point(3, 0), fitz.Point(4, 0),
            fitz.Point(6, 0), fitz.Point(7, 0),
        )]},
        {"type": "s", "items": [(
            "c", fitz.Point(0, 0), fitz.Point(3, 0),
            fitz.Point(7, 0), fitz.Point(float("nan"), 0),
        )]},
    ]
    before = repr(native)
    rowset = census_original_native_cubic_ink(
        native, source_atoms=[((2, 0), (8, 0))],
    )
    row = rowset["source_native_cubic_ink_queries"][0]
    assert row["original_indexed_cubic_full_span_count"] == 2
    receipts = row["original_indexed_cubic_candidate_receipts"]
    assert [r["original_native_curve_ref"] for r in receipts] == [
        "d0i0", "d1i0",
    ]
    assert [r["original_stroked_cubic"] for r in receipts] == [True, False]
    assert rowset["original_native_cubic_item_count"] == 5
    assert rowset["invalid_native_cubic_source_ids"] == ["d4i0"]
    assert rowset["all_original_native_cubic_items_examined"]
    assert not rowset["complete_source_universe_including_raster_or_clip"]
    assert not rowset["physical_wall_or_room_role_granted"]
    assert rowset["metric_quantities_published"] == 0
    assert repr(native) == before


def test_curve_control_polygon_never_means_ink_fully_covers_query():
    from tools.diag_gpt2_p7_original_native_crossing_ink import (
        census_original_native_cubic_ink,
    )
    native = [{"type": "s", "items": [(
        "c", fitz.Point(3, 0), fitz.Point(0, 0),
        fitz.Point(10, 0), fitz.Point(7, 0),
    )]}]
    r = census_original_native_cubic_ink(
        native, source_atoms=[((2, 0), (8, 0))],
    )
    assert r["source_native_cubic_ink_queries"][0][
        "original_indexed_cubic_full_span_count"
    ] == 0


def test_cubic_fullspan_reordered_original_paths_no_alias():
    from tools.diag_gpt2_p7_original_native_crossing_ink import (
        census_original_native_cubic_ink,
    )
    strokes = [
        {"type": "s", "items": [(
            "c", fitz.Point(0, 0), fitz.Point(3, 0),
            fitz.Point(7, 0), fitz.Point(10, 0),
        )]},
        {"type": "s", "items": [(
            "c", fitz.Point(5, 1), fitz.Point(6, 2),
            fitz.Point(7, 3), fitz.Point(9, 4),
        )]},
    ]
    reports = [
        census_original_native_cubic_ink(order, source_atoms=[((2, 0), (8, 0))])
        for order in (strokes, list(reversed(strokes)))
    ]
    assert [r["source_native_cubic_ink_queries"][0][
        "original_indexed_cubic_full_span_count"] for r in reports] == [1, 1]
    assert [r["source_native_cubic_ink_queries"][0][
        "original_indexed_cubic_candidate_receipts"][0]["original_native_curve_ref"]
        for r in reports] == ["d0i0", "d1i0"]
    assert all(r["diagnostic_only"] for r in reports)


def test_cubic_source_query_gates_reject_bad_or_duplicate():
    from tools.diag_gpt2_p7_original_native_crossing_ink import (
        census_original_native_cubic_ink,
    )
    with pytest.raises(ValueError, match="original_native_drawing_universe_unavailable"):
        census_original_native_cubic_ink([], source_atoms=[((0, 0), (1, 0))])
    with pytest.raises(ValueError, match="duplicate_original_producer_atom_query"):
        census_original_native_cubic_ink(
            drawings(), source_atoms=[((0, 0), (1, 0)), ((0, 0), (1, 0))]
        )
    with pytest.raises(ValueError, match="selected native wall edge invalid"):
        census_original_native_cubic_ink(
            drawings(), source_atoms=[((0, 0), (float("inf"), 0))]
        )



def test_source_native_split_partial_ink_union_and_gaps_are_diagnostic_only():
    from tools.diag_gpt2_p7_original_native_crossing_ink import (
        census_original_native_partial_linear_ink,
    )
    shapes = [
        {"type": "s", "color": (0, 0, 0), "items": [
            ("l", fitz.Point(0, 0), fitz.Point(5, 0))]},
        {"type": "s", "color": (0, 0, 0), "items": [
            ("l", fitz.Point(10, 0), fitz.Point(5, 0))]},
        {"type": "f", "fill": (1, 1, 1), "items": [
            ("l", fitz.Point(5, .1), fitz.Point(7, .1))]},
        {"type": "s", "items": [
            ("l", fitz.Point(5, 0), fitz.Point(5, 4))]},
    ]
    before = repr(shapes)
    report = census_original_native_partial_linear_ink(
        shapes, source_atoms=[((2, 0), (8, 0))]
    )
    row = report["source_native_linear_partial_queries"][0]
    assert [part["original_native_primitive_ref"] for part in row[
        "original_native_linear_partial_receipts"]] == ["d0i0", "d1i0"]
    assert row["stroke_only_geometric_coverage"][
        "source_query_geometrically_covered_diagnostic_only"]
    assert row["stroke_only_geometric_coverage"]["source_query_gaps_pt"] == []
    assert not row["source_structural_wall_role_authenticated"]
    assert report["new_commercial_quantities"] == []
    assert repr(shapes) == before


def test_native_partial_source_gap_and_fill_only_not_stroke():
    from tools.diag_gpt2_p7_original_native_crossing_ink import (
        census_original_native_partial_linear_ink,
    )
    shapes = [
        {"type": "s", "items": [("l", fitz.Point(0, 0), fitz.Point(4, 0))]},
        {"type": "f", "items": [("l", fitz.Point(4, 0), fitz.Point(6, 0))]},
        {"type": "s", "items": [("l", fitz.Point(6, 0), fitz.Point(10, 0))]},
    ]
    row = census_original_native_partial_linear_ink(
        shapes, source_atoms=[((2, 0), (8, 0))]
    )["source_native_linear_partial_queries"][0]
    assert row["all_native_paint_geometric_coverage"][
        "source_query_geometrically_covered_diagnostic_only"]
    assert not row["stroke_only_geometric_coverage"][
        "source_query_geometrically_covered_diagnostic_only"]
    assert row["stroke_only_geometric_coverage"][
        "source_query_gaps_pt"] == [[2., 4.]]
    assert row["source_structural_wall_role_authenticated"] is False


def test_native_partial_ink_near_miss_and_diagonal_do_not_bridge_gap():
    from tools.diag_gpt2_p7_original_native_crossing_ink import (
        census_original_native_partial_linear_ink,
    )
    shapes = [
        {"type": "s", "items": [("l", fitz.Point(0, 0), fitz.Point(5, 0))]},
        {"type": "s", "items": [("l", fitz.Point(5, .0003), fitz.Point(10, .0003))]},
        {"type": "s", "items": [("l", fitz.Point(5, 0), fitz.Point(10, .01))]},
        {"type": "s", "items": [("l", fitz.Point(5, -3), fitz.Point(5, 3))]},
    ]
    row = census_original_native_partial_linear_ink(
        shapes, source_atoms=[((0, 0), (10, 0))]
    )["source_native_linear_partial_queries"][0]
    assert [x["original_native_primitive_ref"] for x in row[
        "original_native_linear_partial_receipts"]] == ["d0i0"]
    assert row["stroke_only_geometric_coverage"]["source_query_gaps_pt"] == [[5., 10.]]


def test_native_partial_ink_keeps_duplicated_original_ancestry_and_reverse_query():
    from tools.diag_gpt2_p7_original_native_crossing_ink import (
        census_original_native_partial_linear_ink,
    )
    shapes = [
        {"type": "s", "items": [("l", fitz.Point(0, 0), fitz.Point(10, 0))]},
        {"type": "s", "items": [("l", fitz.Point(0, 0), fitz.Point(10, 0))]},
    ]
    for query in (((2, 0), (8, 0)), ((8, 0), (2, 0))):
        row = census_original_native_partial_linear_ink(
            shapes, source_atoms=[query]
        )["source_native_linear_partial_queries"][0]
        assert len(row["original_native_linear_partial_receipts"]) == 2
        assert {x["original_native_primitive_ref"] for x in row[
            "original_native_linear_partial_receipts"]} == {"d0i0", "d1i0"}
        assert row["stroke_only_geometric_coverage"][
            "source_query_geometrically_covered_diagnostic_only"]
        assert not row["source_room_ring_closed"]


def test_native_partial_ink_invalid_source_and_duplicate_queries_fail_closed():
    from tools.diag_gpt2_p7_original_native_crossing_ink import (
        census_original_native_partial_linear_ink,
    )
    with pytest.raises(ValueError, match="original_native_drawing_universe_unavailable"):
        census_original_native_partial_linear_ink(
            [], source_atoms=[((0, 0), (1, 0))]
        )
    with pytest.raises(ValueError, match="duplicate_original_producer_atom_query"):
        census_original_native_partial_linear_ink(
            drawings(), source_atoms=[((0, 0), (1, 0)), ((0, 0), (1, 0))]
        )
    with pytest.raises(ValueError, match="selected native wall edge invalid"):
        census_original_native_partial_linear_ink(
            drawings(), source_atoms=[((float("nan"), 0), (1, 0))]
        )



def test_original_image_placements_are_not_raster_or_wall_evidence():
    from tools.diag_gpt2_p7_original_native_crossing_ink import (
        census_original_image_placements,
    )
    class Page:
        def get_image_info(self, *, xrefs):
            assert xrefs is True
            return [
                {"bbox": (0, 0, 10, 10), "xref": 0,
                 "width": 100, "height": 100},
                {"bbox": (20, 20, 30, 30), "xref": 38,
                 "width": 200, "height": 100},
            ]
    row = census_original_image_placements(
        Page(), source_atoms=[((2, 2), (8, 8)), ((12, 12), (14, 14))]
    )
    assert row["status"] == "ORIGINAL_SOURCE_IMAGE_PLACEMENTS_SCANNED"
    assert row["source_image_universe_complete"]
    assert row["original_image_placement_count"] == 2
    assert row["image_placements"][0]["original_image_xref"] == 0
    assert [r["overlapping_original_image_placement_indices"]
            for r in row["query_rows"]] == [[0], []]
    assert all(q["bbox_overlap_only_not_pixel_or_wall_evidence"]
               for q in row["query_rows"])
    assert not row["physical_wall_or_raster_role_granted"]


def test_image_source_malformed_bbox_is_partial_not_false_absence():
    from tools.diag_gpt2_p7_original_native_crossing_ink import (
        census_original_image_placements,
    )
    class Page:
        def get_image_info(self, *, xrefs):
            return [
                {"bbox": (0, 0, float("nan"), 10), "xref": 12,
                 "width": 10, "height": 10},
                {"bbox": (0, 0, 10, 10), "xref": 14,
                 "width": 10, "height": 10},
            ]
    row = census_original_image_placements(
        Page(), source_atoms=[((1, 1), (9, 9))]
    )
    assert row["status"] == "ORIGINAL_SOURCE_IMAGE_PLACEMENT_PARTIAL"
    assert not row["source_image_universe_complete"]
    assert row["original_invalid_image_placement_indices"] == [0]
    assert row["query_rows"][0]["overlapping_original_image_placement_indices"] == [1]
    assert not row["physical_wall_or_raster_role_granted"]


def test_missing_image_api_remains_unknown_not_no_images():
    from tools.diag_gpt2_p7_original_native_crossing_ink import (
        census_original_image_placements,
    )
    report = census_original_image_placements(
        object(), source_atoms=[((1, 1), (9, 9))]
    )
    assert report["status"] == "ORIGINAL_SOURCE_IMAGE_API_UNAVAILABLE"
    assert not report["source_image_universe_complete"]
    assert not report["physical_wall_or_raster_role_granted"]
