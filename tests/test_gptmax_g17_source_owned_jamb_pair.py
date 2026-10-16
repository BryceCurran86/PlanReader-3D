"""Source-paired original G17 W3 jambs are not physical W4 host authority."""
import hashlib
from copy import deepcopy

import pytest

from tools.diag_gptmax_g17_source_owned_jamb_pair import (
    source_owned_g17_jamb_pair_review,
)


def evidence():
    original=b"original-source-bytes"
    sha=hashlib.sha256(original).hexdigest()
    specs=[
        ("la","raster_wall_band_face",[0,0,10,0]),
        ("lb","raster_wall_band_face",[0,2.16,10,2.16]),
        ("le","raster_wall_band_end",[10,0,10,2.16]),
        ("ra","raster_wall_band_face",[35,0,65,0]),
        ("rb","raster_wall_band_face",[35,2.16,65,2.16]),
        ("re","raster_wall_band_end",[35,0,35,2.16]),
    ]
    obs=[{"observation_id":oid,"observation_kind":kind,
          "geometry_pdf_pts":line,
          "authenticated_source_parents":[{"observation_id":"parent:"+oid}]}
         for oid,kind,line in specs]
    record={"physical_opening_id":"original-physical-opening-1",
            "source_sha256":sha,"snapshot_id":"source-snapshot-proof",
            "page_id":"1","host_status":"abstained",
            "host_granted":False,"metric_quantity_granted":False,
            "source_g17_observations":obs}
    source={"source_sha256":sha,"snapshot_id":"source-snapshot-proof",
            "primitive_safety_cap":20000,
            "unhosted_raster_flank_source_receipts":[record]}
    probes=[]
    for triples in [specs[:3],specs[3:]]:
        ids=sorted(r[0] for r in triples)
        parents=sorted("parent:"+r[0] for r in triples)
        original_geom=[r[2] for r in triples]
        w2={"source_observation_ids":ids,
            "source_parent_observation_ids":parents,
            "w2_surviving_edges":3,
            "w2_snap_collapsed_fragments":0,
            "w2_excluded_source_segments":0,
            "w2_surviving_edge_geometry_pt":original_geom,
            "w2_surviving_source_fragment_ids":["split_0","split_1","split_2"],
            "w3_junction_types":["l_corner","near_junction_review","l_corner","near_junction_review"],
            "w4_shadow_candidate_source_edges":["split_0","split_1","split_2"],
            "canonical_w4_wall_id_granted":False,
            "structural_wall_role_granted":False,
            "host_binding_granted":False}
        probes.append({"source_observation_ids":ids,
                       "source_ink_shadow_eligible":True,
                       "source_ink_first_failure":None,
                       "default_w2_w3_w4":deepcopy(w2),
                       "exact_coordinate_w2_w3_w4":deepcopy(w2)})
    graph={"source_sha256":sha,"page_id":"1",
           "global_w4_or_snapshot_modified":False,
           "physical_wall_or_opening_host_granted":False,
           "source_flank_w2_w4_shadows":[
               {"physical_opening_id":"original-physical-opening-1","flanks":probes}]}
    return original,source,graph


def test_source_positive_two_jambs_have_closed_source_candidate_without_host():
    pdf,src,w2=evidence()
    before=deepcopy((src,w2))
    report=source_owned_g17_jamb_pair_review(pdf,src,w2,page_id="1")
    assert (src,w2)==before
    assert report["source_closed_two_flank_candidates"]==1
    assert report["original_g17_physical_opening_count"]==1
    assert all(x["retained"] for x in report["opening_source_ribbon_review"][0]["flank_source_proofs"])
    assert report["physical_w4_or_host_granted"] is False
    assert report["opening_area_or_count_granted"] is False
    assert report["customer_row_granted"] is False
    assert report["benchmark_score_granted"] is False


def test_order_independent_original_source_and_graph_parent_ids():
    pdf,src,w2=evidence()
    expected=source_owned_g17_jamb_pair_review(pdf,src,w2,page_id="1")
    src["unhosted_raster_flank_source_receipts"][0]["source_g17_observations"].reverse()
    w2["source_flank_w2_w4_shadows"][0]["flanks"].reverse()
    got=source_owned_g17_jamb_pair_review(pdf,src,w2,page_id="1")
    assert got==expected


@pytest.mark.parametrize("damage",[
    "bad_sha","source_rekey","duplicate_source","foreign_parent",
    "missing_w2_parent","w2_moved","missing_w3_corner",
    "w2_collapsed","w4_membership_lost","faked_w4_grant",
    "foreign_flank","duplicated_physical","positive_host",
])
def test_source_identity_or_wall_role_forgery_never_creates_ribbon(damage):
    pdf,src,w2=evidence()
    original=src["unhosted_raster_flank_source_receipts"][0]
    graph=w2["source_flank_w2_w4_shadows"][0]["flanks"][0]
    wm=graph["default_w2_w3_w4"]
    if damage=="bad_sha":
        src["source_sha256"]="a"*64
    elif damage=="source_rekey":
        original["snapshot_id"]="foreign"
    elif damage=="duplicate_source":
        original["source_g17_observations"][1]["observation_id"]="la"
    elif damage=="foreign_parent":
        original["source_g17_observations"][0]["authenticated_source_parents"]=[]
    elif damage=="missing_w2_parent":
        wm["source_parent_observation_ids"]=[]
    elif damage=="w2_moved":
        wm["w2_surviving_edge_geometry_pt"][0]=[0,0,11,0]
    elif damage=="missing_w3_corner":
        wm["w3_junction_types"]=["endpoint"]*4
    elif damage=="w2_collapsed":
        wm["w2_snap_collapsed_fragments"]=1
    elif damage=="w4_membership_lost":
        wm["w4_shadow_candidate_source_edges"]=[]
    elif damage=="faked_w4_grant":
        wm["canonical_w4_wall_id_granted"]=True
    elif damage=="foreign_flank":
        graph["source_observation_ids"]=["foreign"]
    elif damage=="duplicated_physical":
        w2["source_flank_w2_w4_shadows"].append(
            deepcopy(w2["source_flank_w2_w4_shadows"][0]))
    else:
        w2["physical_wall_or_opening_host_granted"]=True
    if damage in {"missing_w3_corner","w2_collapsed","w4_membership_lost","w2_moved"}:
        result=source_owned_g17_jamb_pair_review(pdf,src,w2,page_id="1")
        assert result["source_closed_two_flank_candidates"]==0
        assert result["physical_w4_or_host_granted"] is False
    else:
        with pytest.raises(ValueError):
            source_owned_g17_jamb_pair_review(pdf,src,w2,page_id="1")


def test_source_ink_opposed_g17_flank_stays_incomplete():
    pdf,src,w2=evidence()
    r=w2["source_flank_w2_w4_shadows"][0]["flanks"][0]
    r["source_ink_shadow_eligible"]=False
    r["source_ink_first_failure"]="original_source_ink_not_solid"
    result=source_owned_g17_jamb_pair_review(pdf,src,w2,page_id="1")
    assert result["source_closed_two_flank_candidates"]==0
    assert result["opening_source_ribbon_review"][0]["flank_source_proofs"][0]["retained"] is False
