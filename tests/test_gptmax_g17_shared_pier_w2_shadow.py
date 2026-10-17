"""Original dual-ended G17 ring must stay source-only in W2/W3/W4."""
from copy import deepcopy

import pytest

from tools import diag_gptmax_g17_shared_pier_w2_shadow as module


def source(sid,kind,p):
    return {
        "id":sid,"kind":kind,"geometry_pdf_pts":p,
        "parents":["original-"+sid],
        "source_primitive_ref":"visible:raster_opening_primitive:original:2.0.0:"+sid,
    }


def sample():
    a={"f1":source("f1","raster_wall_band_face",[0,1,6,1]),
       "f2":source("f2","raster_wall_band_face",[0,3,6,3]),
       "end-a":source("end-a","raster_wall_band_end",[0,1,0,3])}
    b={"f1":deepcopy(a["f1"]),"f2":deepcopy(a["f2"]),
       "end-b":source("end-b","raster_wall_band_end",[6,1,6,3])}
    match={"opening_ids":["pA","pB"],"source_closed_pier_candidate":True,
           "source_closed_source_observation_ids":["f1","f2","end-a","end-b"]}
    return match,{"pA":a,"pB":b}


def test_replays_existing_producer_at_normal_and_zero_snap(monkeypatch):
    calls=[]
    def real_source_graph(segments,**kw):
        calls.append((segments,kw))
        return {"canonical_w4_wall_id_granted":False,
                "structural_wall_role_granted":False,
                "host_binding_granted":False,
                "w2_edges":4 if kw["tolerance"]==0.0 else 2}
    monkeypatch.setattr(module,"_isolated_graph",real_source_graph)
    match,observed=sample()
    result=module.isolated_original_dual_end_w2_w4(
        match,observed,source_sha="a"*64,page_id="3")
    assert len(calls)==2
    assert calls[0][1]["tolerance"]==module.DEFAULT_GAP_SNAP_TOLERANCE_PT
    assert calls[1][1]["tolerance"]==0.0
    assert all(len(x[0])==4 for x in calls)
    assert {x["id"] for x in calls[0][0]}=={
        "raster_opening_primitive:original:2.0.0:"+k
        for k in ("f1","f2","end-a","end-b")}
    assert result["source_rectangle_role_proven"] is False
    assert result["original_W4_structural_member_granted"] is False
    assert result["original_host_binding_granted"] is False
    assert result["metric_width_height_granted"] is False


@pytest.mark.parametrize("corrupt",[
    lambda match,source: match.update(source_closed_pier_candidate=False),
    lambda match,source: match["source_closed_source_observation_ids"].pop(),
    lambda match,source: match["source_closed_source_observation_ids"].append("f1"),
    lambda match,source: match.update(opening_ids=["pA","pA"]),
    lambda match,source: match.update(opening_ids=["pA","foreign"]),
    lambda match,source: source["pA"]["f1"].update(
        source_primitive_ref="fake-raster-segment"),
    lambda match,source: source["pB"]["f1"]["geometry_pdf_pts"].__setitem__(0,0.5),
    lambda match,source: source["pA"]["end-a"].update(parents=[]),
    lambda match,source: source["pB"]["end-b"].update(kind="raster_line_run"),
    lambda match,source: source["pB"]["end-b"].update(
        source_primitive_ref="visible:raster_opening_primitive:original:2.0.0:end-a"),
])
def test_foreign_missing_or_conflicting_source_fails_before_w2(monkeypatch,corrupt):
    def forbidden(*a,**kw):
        raise AssertionError("No graph may run on foreign G17 input")
    monkeypatch.setattr(module,"_isolated_graph",forbidden)
    match,original=sample()
    corrupt(match,original)
    with pytest.raises(ValueError):
        module.isolated_original_dual_end_w2_w4(
            match,original,source_sha="a"*64,page_id="3")


def test_source_graph_must_never_claim_canonical_physical_wall(monkeypatch):
    def illegally_positive(*args,**kw):
        return {"canonical_w4_wall_id_granted":True,
                "structural_wall_role_granted":False,
                "host_binding_granted":False}
    monkeypatch.setattr(module,"_isolated_graph",illegally_positive)
    match,original=sample()
    with pytest.raises(ValueError,match="forbidden"):
        module.isolated_original_dual_end_w2_w4(
            match,original,source_sha="a"*64,page_id="3")


def test_original_source_order_cannot_change_source_member_graph(monkeypatch):
    monkeypatch.setattr(module,"_isolated_graph",
       lambda segs,**k: {"canonical_w4_wall_id_granted":False,
                         "structural_wall_role_granted":False,
                         "host_binding_granted":False,
                         "original_members":sorted(x["id"] for x in segs)})
    match,original=sample()
    a=module.isolated_original_dual_end_w2_w4(
        match,original,source_sha="a"*64,page_id="3")
    reversed_={k:dict(reversed(list(v.items())))
               for k,v in reversed(list(original.items()))}
    b=module.isolated_original_dual_end_w2_w4(
        match,reversed_,source_sha="a"*64,page_id="3")
    assert a==b
