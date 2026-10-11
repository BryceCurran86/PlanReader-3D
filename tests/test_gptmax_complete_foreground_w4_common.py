"""Full original-positive source W4 cross-flank IDs are not authenticated hosts."""
from copy import deepcopy
from hashlib import sha256

import pytest

from tools.diag_gptmax_complete_foreground_w4_common import original_common_w4_candidates


def fixture():
    data=b"immutable original source bytes"
    sha=sha256(data).hexdigest()
    opening="physical_opening_existence_diagnostic"
    G17={"source_sha256":sha,"page_id":"3","host_publication_allowed":False,
         "benchmark_accuracy":None,
         "opening_rows":[{"opening_identity_id":opening,
                          "original_aperture_coordinate_basis":{
                              "origin":[0.,0.],"axis":[1.,0.],"normal":[0.,1.],
                              "length":10.,"thickness":2.}}]}
    flank={"source_sha256":sha,"page_id":"3","source_pdf_byte_sha_verified":True,
           "source_receipts_freshly_reauthenticated":False,
           "physical_equivalence_proven":False,"host_publication_allowed":False,
           "benchmark_accuracy":None,
           "opening_rows":[{"opening_identity_id":opening,
              "flanks":[{"role":role,"pixel_run_candidates":[{
                  "source_observation_id":sid,"host_publication_allowed":False,
                  "visible_wall_authority_proven":False,
                  "physical_wall_equivalence_proven":False
               }]} for role,sid in [("left","shadow-left"),("right","shadow-right")]]}]}
    graph={"input_source_count":2,
           "source_parent_census":[
               {"source_observation_id":"shadow-left","w2_edge_ids":["W2L"]},
               {"source_observation_id":"shadow-right","w2_edge_ids":["W2R"]}],
           "all_w2_edges":[
               {"edge_id":"W2L","source_observation_ids":["shadow-left"],
                "w3_retained":True,"w3_removed":False,
                "experimental_w4_candidate_ids":["wall-shared"]},
               {"edge_id":"W2R","source_observation_ids":["shadow-right"],
                "w3_retained":True,"w3_removed":False,
                "experimental_w4_candidate_ids":["wall-shared"]}],
           "all_experimental_w4_candidates":[
               {"candidate_id":"wall-shared",
                "w2_edge_ids":["W2L","W2R"],
                "centerline_pt":[[-5.,0.],[15.,0.]]}],
           "host_publication_allowed":False,"physical_equivalence_proven":False}
    full={"source_sha256":sha,"page_id":"3",
          "ordinary_source_snapshot_unchanged":True,
          "original_source_render_reauthenticated":True,
          "ordinary_visibility_rejects_shadow_kind":True,
          "host_publication_allowed":False,"physical_equivalence_proven":False,
          "opening_count_publication_allowed":False,
          "metric_quantity_publication_allowed":False,
          "benchmark_accuracy":None,"experimental_w2_w4":graph}
    return data,G17,flank,full,sha


def run(items):
    data,g17,flanks,full,sha=items
    # Diagnostic has a fixed seven-case source scope; exercise it without
    # hardcoded project truth by providing seven unique synthetic copies.
    original=g17["opening_rows"][0]
    flank=flanks["opening_rows"][0]
    if len(g17["opening_rows"])==1:
        g17["opening_rows"]=[
            {**deepcopy(original),"opening_identity_id":f"opening-{i}"}
            for i in range(7)]
        flanks["opening_rows"]=[
            {**deepcopy(flank),"opening_identity_id":f"opening-{i}"}
            for i in range(7)]
    return original_common_w4_candidates(data,g17,flanks,full,expected_source_sha=sha)


def test_source_owned_cross_flank_w4_single_candidate_does_not_create_a_host():
    input=fixture()
    out=run(input)
    assert len(out["opening_rows"])==7
    for row in out["opening_rows"]:
        single,=row["shared_experimental_w4_candidates"]
        assert single["candidate_id"]=="wall-shared"
        assert single["w4_centerline_axis_spans_aperture"]
        assert not single["physical_w4_wall_role_proven"]
        assert not single["opening_host_publication_allowed"]
    assert not out["physical_equivalence_proven"]
    assert not out["host_publication_allowed"]


def test_unrelated_retained_W4_owners_must_stay_unhosted():
    items=fixture()
    items[3]["experimental_w2_w4"]["all_w2_edges"][1]["experimental_w4_candidate_ids"]=[]
    items[3]["experimental_w2_w4"]["all_experimental_w4_candidates"][0]["w2_edge_ids"]=["W2L"]
    out=run(items)
    assert all(not row["shared_experimental_w4_candidates"] for row in out["opening_rows"])


@pytest.mark.parametrize("mutation",[
    "bad_pdf", "duplicate_source", "foreign_W2_parent", "removed_edge_claims_W4",
    "incomplete_census", "candidate_parent_mismatch","nan_centerline",
    "promoted_shadow","promoted_graph","changed_scope","wrong_source_count",
])
def test_unverifiable_W2_W3_W4_source_join_abstains(mutation):
    items=list(fixture())
    graph=items[3]["experimental_w2_w4"]
    if mutation=="bad_pdf": items[0]=b"not the original PDF"
    elif mutation=="duplicate_source":
        graph["source_parent_census"][1]["source_observation_id"]="shadow-left"
    elif mutation=="foreign_W2_parent":
        graph["all_w2_edges"][0]["source_observation_ids"]=["different"]
    elif mutation=="removed_edge_claims_W4":
        graph["all_w2_edges"][0]["w3_removed"]=True
    elif mutation=="incomplete_census":
        graph["source_parent_census"].pop()
    elif mutation=="candidate_parent_mismatch":
        graph["all_experimental_w4_candidates"][0]["w2_edge_ids"]=["W2L"]
    elif mutation=="nan_centerline":
        graph["all_experimental_w4_candidates"][0]["centerline_pt"][0][0]=float("nan")
    elif mutation=="promoted_shadow":
        items[2]["opening_rows"][0]["flanks"][0]["pixel_run_candidates"][0]["visible_wall_authority_proven"]=True
    elif mutation=="promoted_graph":
        graph["physical_equivalence_proven"]=True
    elif mutation=="changed_scope": items[2]["page_id"]="2"
    elif mutation=="wrong_source_count": graph["input_source_count"]=20001
    with pytest.raises((ValueError,TypeError)):
        run(items)
