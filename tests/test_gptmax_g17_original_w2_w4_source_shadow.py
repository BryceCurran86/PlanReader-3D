"""W2/W3/W4 original-G17 shadow cannot become a hosted measured opening."""
from copy import deepcopy
import hashlib

import pytest

from tools.diag_gptmax_g17_original_w2_w4_source_shadow import (
    original_g17_w2_w4_source_shadow,
    _original_flank_lines,
)


def _receipts():
    source=b"synthetic-original-pdf-source bytes"
    sha=hashlib.sha256(source).hexdigest()
    physical_id="physical_opening_existence_synthetic-g17-1"
    # Two genuine solid band face pairs, each with ONE INNER jamb end.
    specs=[
        ("l-a","raster_wall_band_face",[0.0,0.0,10.0,0.0]),
        ("l-b","raster_wall_band_face",[0.0,2.16,10.0,2.16]),
        ("l-end","raster_wall_band_end",[10.0,0.0,10.0,2.16]),
        ("r-a","raster_wall_band_face",[35.0,0.0,75.0,0.0]),
        ("r-b","raster_wall_band_face",[35.0,2.16,75.0,2.16]),
        ("r-end","raster_wall_band_end",[35.0,0.0,35.0,2.16]),
    ]
    rows=[{"observation_id":oid,"observation_kind":kind,
           "geometry_pdf_pts":coords,
           "authenticated_source_parents":[{"observation_id":"parent:"+oid}]}
          for oid,kind,coords in specs]
    original={
        "physical_opening_id":physical_id,"page_id":"1",
        "source_sha256":sha,"snapshot_id":"snapshot-original","host_status":"abstained",
        "host_granted":False,"metric_quantity_granted":False,
        "source_g17_observations":rows,
    }
    receipt={"source_sha256":sha,"primitive_safety_cap":20000,
             "snapshot_id":"snapshot-original",
             "unhosted_raster_flank_source_receipts":[original]}
    flank_paint=[]
    for ids,box,side in (
        (["l-a","l-b","l-end"],[0.0,0.0,10.0,2.16],"first"),
        (["r-a","r-b","r-end"],[35.0,0.0,75.0,2.16],"second"),
    ):
        flank_paint.append({
            "source_observation_ids":sorted(ids),
            "source_bbox_pdf_pts":box,
            "one_ended_G17_original_source_paint":{
                "original_source_observation_ids":sorted(ids),
                "source_one_end_shadow_eligible":True,
                "source_shadow_first_failure":None,
                "source_original_rgb_solid":True,
                "source_vs_full_rgb_identical":True,
                "original_image_region_owned":True,
                "structural_W2_or_W4_proven":False,
                "host_or_frame_granted":False,
            },
        })
    paint={"source_sha256":sha,"page_id":"1",
           "canonical_snapshot_modified":False,
           "physical_host_granted":False,
           "metric_area_or_count_granted":False,
           "source_openings":[{"physical_opening_id":physical_id,"flanks":flank_paint}]}
    return source,receipt,paint


def test_actual_w2_w3_w4_run_on_original_face_end_primitives_is_shadow_only():
    source,original,paint=_receipts()
    result=original_g17_w2_w4_source_shadow(
        source,original,paint,page_id="1")
    assert result["original_g17_physical_openings"]==1
    assert result["individual_flanks"]==2
    for flank in result["source_flank_w2_w4_shadows"][0]["flanks"]:
        assert flank["source_ink_shadow_eligible"] is True
        for name in ("default_w2_w3_w4","exact_coordinate_w2_w3_w4"):
            graph=flank[name]
            assert graph is not None
            assert len(graph["source_observation_ids"])==3
            assert len(graph["source_parent_observation_ids"])==3
            assert graph["structural_wall_role_granted"] is False
            assert graph["canonical_w4_wall_id_granted"] is False
            assert graph["host_binding_granted"] is False
    assert result["global_w4_or_snapshot_modified"] is False
    assert result["physical_wall_or_opening_host_granted"] is False
    assert result["metric_quantity_or_count_granted"] is False
    assert result["sealed_customer_output_modified"] is False


def test_source_order_invariance_preserves_isolated_w2_and_w4_ids():
    source,original,paint=_receipts()
    a=original_g17_w2_w4_source_shadow(source,original,paint,page_id="1")
    other=deepcopy(original)
    other["unhosted_raster_flank_source_receipts"][0]["source_g17_observations"].reverse()
    other_paint=deepcopy(paint)
    other_paint["source_openings"][0]["flanks"].reverse()
    b=original_g17_w2_w4_source_shadow(source,other,other_paint,page_id="1")
    assert a==b


def test_non_solid_original_source_stays_out_of_w2_w3_w4():
    source,original,paint=_receipts()
    negative=paint["source_openings"][0]["flanks"][0]["one_ended_G17_original_source_paint"]
    negative["source_one_end_shadow_eligible"]=False
    negative["source_original_rgb_solid"]=False
    negative["source_shadow_first_failure"]="original_source_ink_not_solid"
    result=original_g17_w2_w4_source_shadow(source,original,paint,page_id="1")
    first=result["source_flank_w2_w4_shadows"][0]["flanks"][0]
    assert first["source_ink_shadow_eligible"] is False
    assert first["default_w2_w3_w4"] is None
    assert first["exact_coordinate_w2_w3_w4"] is None
    assert result["physical_wall_or_opening_host_granted"] is False


@pytest.mark.parametrize("damage",[
    "source_sha", "missing_end","duplicate_parent","foreign_face",
    "contradictory_ink","promoted_ink","fake_bbox","foreign_page",
])
def test_original_source_forgery_and_missing_owned_topology_fail_closed(damage):
    source,original,paint=_receipts()
    row=original["unhosted_raster_flank_source_receipts"][0]
    side=paint["source_openings"][0]["flanks"][0]
    if damage=="source_sha":
        original["source_sha256"]="0"*64
    elif damage=="missing_end":
        row["source_g17_observations"]=[r for r in row["source_g17_observations"]
                                      if r["observation_id"]!="l-end"]
    elif damage=="duplicate_parent":
        row["source_g17_observations"][1]["observation_id"]="l-a"
    elif damage=="foreign_face":
        row["source_g17_observations"][0]["authenticated_source_parents"]=[]
    elif damage=="contradictory_ink":
        side["one_ended_G17_original_source_paint"]["original_source_observation_ids"]=["wrong"]
    elif damage=="promoted_ink":
        paint["physical_host_granted"]=True
    elif damage=="fake_bbox":
        side["source_bbox_pdf_pts"][2]=9.99
    else:
        paint["page_id"]="2"
    with pytest.raises(ValueError):
        original_g17_w2_w4_source_shadow(source,original,paint,page_id="1")


def test_unbound_source_lines_cannot_gain_w2_edge():
    source,original,paint=_receipts()
    side={"source_observation_ids":["l-a","l-b","l-end"]}
    lines=_original_flank_lines(original["unhosted_raster_flank_source_receipts"][0],side)
    assert len(lines)==3
    assert all(x["source_observation_id"] and x["source_parent_observation_id"] for x in lines)
    side["source_observation_ids"][0]="unknown-id"
    with pytest.raises(ValueError):
        _original_flank_lines(original["unhosted_raster_flank_source_receipts"][0],side)
