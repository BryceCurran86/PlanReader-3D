"""Source first: never turn native short W4 gaps into fictional room polygons."""
import hashlib

import fitz
import pytest

from tools.diag_gptmax_original_room_boundary_gap_sources import (
    inspect_original_source_gaps,
    short_source_gap_candidates,
)


def _edge(wall, edge, primitive, geometry):
    return {
        "wall_candidate_id": wall,
        "source_edge_fragments": [{
            "edge_id": edge, "source_primitive_ids": [primitive],
            "geometry": geometry,
        }],
    }


def scope(second_start=121.96):
    return {
        "status": "corroborated",
        "records": [
            _edge("wall:left-upper", "split:upper", "d0i0", [100, 80, 100, 120]),
            _edge("wall:left-lower", "split:lower", "d1i0",
                  [100, second_start, 100, 180]),
            _edge("wall:right", "split:right", "d2i0", [200, 80, 200, 180]),
        ],
    }


def test_short_collinear_original_source_gap_reports_both_owners_no_bridge():
    gaps = short_source_gap_candidates(scope(), max_gap_pt=2.5)
    assert len(gaps) == 1
    g = gaps[0]
    assert g["gap_width_pdf_pts"] == pytest.approx(1.96)
    assert g["first_w2_edge_id"] == "split:upper"
    assert g["second_w2_edge_id"] == "split:lower"
    assert g["first_source_primitive_ids"] == ["d0i0"]
    assert g["second_source_primitive_ids"] == ["d1i0"]
    assert g["virtual_wall_bridge_authorized"] is False


def test_missing_collinear_or_outside_tolerance_cannot_be_bridged():
    assert short_source_gap_candidates(scope(second_start=125), max_gap_pt=2.5) == []
    not_same = scope()
    not_same["records"][1]["source_edge_fragments"][0]["geometry"] = [101, 121.96, 101, 180]
    assert short_source_gap_candidates(not_same, max_gap_pt=2.5) == []


def test_native_pdf_ink_is_read_only_and_not_a_room_authority():
    doc=fitz.open()
    page=doc.new_page(width=300,height=300)
    page.draw_line((100, 80), (100, 120), width=0.3)
    page.draw_line((100, 121.96), (100, 180), width=0.3)
    page.insert_text((130, 132), "BED", fontsize=8)
    source=doc.tobytes()
    doc.close()
    sha=hashlib.sha256(source).hexdigest()
    result=inspect_original_source_gaps(source,{
        "source_sha256":sha,"primitive_safety_cap":20000,
        "source_owned_wall_scopes":[dict(scope(),source_sha256=sha,page_id="1")],
    },page_id="1")
    assert result["source_gap_count"] == 1
    g=result["source_primitive_gaps"][0]
    assert g["gap_width_pdf_pts"]==pytest.approx(1.96)
    assert g["first_source_primitive_ids"]==["d0i0"]
    assert g["second_source_primitive_ids"]==["d1i0"]
    assert g["original_full_render_crop_size"][0]>0
    assert g["nearby_native_room_words"][0]["text"]=="BED"
    assert result["physical_room_face_granted"] is False
    assert result["metric_room_area_granted"] is False
    assert result["customer_quantity_granted"] is False
    assert result["benchmark_score_granted"] is False


@pytest.mark.parametrize("bad", [
    {"status":"abstained","records":[]},
    {"status":"corroborated","records":[_edge("same","one","p1",[1,1,1,3]),
                                             _edge("same","two","p2",[1,4,1,5])]},
    {"status":"corroborated","records":[_edge("w","one","p1",[1,1,float("nan"),3])]},
    {"status":"corroborated","records":[_edge("w","one",None,[1,1,1,3])]},
])
def test_untrusted_or_duplicate_original_source_fails_closed(bad):
    with pytest.raises(ValueError):
        short_source_gap_candidates(bad,max_gap_pt=2.5)


@pytest.mark.parametrize("gap", [-1,0,3.5,float("nan")])
def test_unbounded_gap_rule_is_never_assumed(gap):
    with pytest.raises(ValueError):
        short_source_gap_candidates(scope(),max_gap_pt=gap)
