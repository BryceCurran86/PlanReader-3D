"""An original-positive four-rail pixel pattern is not physical wall authority."""
import json
from hashlib import sha256
from copy import deepcopy

import pytest

from tools.diag_gptmax_cross_flank_rail_bands import inspect_cross_flank_rails


def fixture():
    pdf=b"source-immutable"
    digest=sha256(pdf).hexdigest()
    oid="physical_opening_existence_positive_geometry"
    original={"source_sha256":digest,"page_id":"3",
              "revision_id":"source-revision","snapshot_id":"source-snapshot",
              "host_publication_allowed":False,"benchmark_accuracy":None,
              "opening_rows":[{
                  "opening_identity_id":oid,
                  "original_aperture_coordinate_basis":{
                      "origin":[0.0,0.0],"axis":[1.0,0.0],
                      "normal":[0.0,1.0],"length":10.0,"thickness":2.0}}]}
    support=[]
    for side,x0,x1 in (("left",-6.,0.),("right",10.,16.)):
        for role,geometry in (("upper",[x0,1.,x1,1.]),
                              ("lower",[x0,-1.,x1,-1.]),
                              ("end",[x1 if side=="left" else x0,-1.,
                                      x1 if side=="left" else x0,1.])):
            sid=f"original-{side}-{role}"
            support.append(dict(requested_source_observation_id=sid,
                source_observation_id=sid,source_receipt_authenticated=True,
                source_sha256=digest,page_id="3",revision_id="source-revision",
                snapshot_id="source-snapshot",viewport_id=None,document_id="source",
                observation_kind="raster_wall_band_end" if role=="end" else "raster_wall_band_face",
                original_source_support_geometry_pt=geometry))
    original["opening_rows"][0].update(original_g17_support_receipts=support,
        original_g17_support_observation_ids=[x["source_observation_id"] for x in support])
    def source(name,x0,x1,y):
        return {"source_observation_id":name,
                "source_line_pt":[float(x0),float(y),float(x1),float(y)],
                "host_publication_allowed":False,
                "visible_wall_authority_proven":False,
                "physical_wall_equivalence_proven":False}
    flank={"source_sha256":digest,"page_id":"3",
           "source_pdf_byte_sha_verified":True,
           "source_receipts_freshly_reauthenticated":False,
           "physical_equivalence_proven":False,
           "structural_source_universe_complete":False,
           "opening_count_publication_allowed":False,
           "metric_quantity_publication_allowed":False,
           "host_publication_allowed":False,
           "benchmark_accuracy":None,
           "opening_rows":[{"opening_identity_id":oid,"flanks":[
               {"role":"left","pixel_run_candidates":[
                   source("left-top",-6,0,1),source("left-bottom",-6,0,-1)]},
               {"role":"right","pixel_run_candidates":[
                   source("right-top",10,16,1),source("right-bottom",10,16,-1)]},
           ]}]}
    return pdf,original,flank,digest


def run(pdf,original,flank,digest):
    return inspect_cross_flank_rails(
        json.dumps(original).encode("utf-8"),flank,pdf,expected_sha=digest)


def test_four_independent_original_pixel_rails_still_cannot_publish_host():
    args=fixture()
    before=deepcopy(args)
    result=run(*args)
    assert args==before
    assert result["original_pdf_byte_sha_verified"]
    assert not result["host_publication_allowed"]
    assert result["benchmark_accuracy"] is None
    row,=result["opening_rows"]
    assert row["paired_source_rails_by_side"] == {"left":1,"right":1}
    band,=row["cross_flank_source_pixel_band_alternatives"]
    assert band["left_source_observation_ids"]==["left-bottom","left-top"]
    assert band["right_source_observation_ids"]==["right-bottom","right-top"]
    assert not band["physical_wall_pair_equivalence_proven"]
    assert not band["physical_host_publication_allowed"]


def test_unchanged_source_runs_without_cross_flank_parallel_rail_pair_must_abstain():
    pdf,original,flank,digest=fixture()
    flank["opening_rows"][0]["flanks"][1]["pixel_run_candidates"][0]["source_line_pt"]=[10.,0.,16.,0.]
    result=run(pdf,original,flank,digest)
    assert result["opening_rows"][0]["cross_flank_source_pixel_band_alternatives"]==[]
    assert not result["host_publication_allowed"]


def test_duplicate_ink_across_opening_is_not_two_independent_source_rails():
    pdf,original,flank,digest=fixture()
    flank["opening_rows"][0]["flanks"][1]["pixel_run_candidates"][0]["source_observation_id"]="left-top"
    result=run(pdf,original,flank,digest)
    assert result["opening_rows"][0]["cross_flank_source_pixel_band_alternatives"]==[]


@pytest.mark.parametrize("mutate",[
    lambda original,flank: original.update(source_sha256="0"*64),
    lambda original,flank: flank.update(benchmark_accuracy=1.0),
    lambda original,flank: flank.update(source_receipts_freshly_reauthenticated=True),
    lambda original,flank: flank.update(structural_source_universe_complete=True),
    lambda original,flank: flank["opening_rows"][0]["flanks"][1]["pixel_run_candidates"][1].update(host_publication_allowed=True),
    lambda original,flank: flank["opening_rows"][0]["flanks"][1]["pixel_run_candidates"][1].update(source_observation_id="right-top"),
    lambda original,flank: flank["opening_rows"][0]["flanks"][0]["pixel_run_candidates"][0].update(source_line_pt=[-6.,1.,-6.,9.]),
    lambda original,flank: flank["opening_rows"][0]["flanks"][0]["pixel_run_candidates"][0].update(source_line_pt=[-6.,True,0.,1.]),
    lambda original,flank: flank["opening_rows"].append(dict(flank["opening_rows"][0])),
    lambda original,flank: flank["opening_rows"][0]["flanks"][0].update(role="right"),
])
def test_report_inconsistency_or_false_authority_never_crosses_host_gate(mutate):
    pdf,original,flank,digest=fixture()
    mutate(original,flank)
    with pytest.raises((ValueError, TypeError)):
        run(pdf,original,flank,digest)


def test_wrong_original_pdf_sha_fails_even_when_reports_agree():
    pdf,original,flank,digest=fixture()
    with pytest.raises(ValueError,match="source PDF"):
        run(pdf+b"extra",original,flank,digest)


@pytest.mark.parametrize("damage", ["remote", "opposite_side", "aperture_crossing",
                                   "outside_band", "missing_end", "foreign_support"])
def test_reported_side_requires_exact_original_g17_flank_contact(damage):
    pdf,original,flank,digest=fixture()
    rows=flank["opening_rows"][0]["flanks"][0]["pixel_run_candidates"]
    if damage == "remote":
        for r in rows: r["source_line_pt"][0]-=100.;r["source_line_pt"][2]-=100.
    elif damage == "opposite_side":
        for r in rows: r["source_line_pt"][0]+=16.;r["source_line_pt"][2]+=16.
    elif damage == "aperture_crossing":
        for r in rows: r["source_line_pt"][2]=16.
    elif damage == "outside_band":
        for r in rows: r["source_line_pt"][1]+=100.;r["source_line_pt"][3]+=100.
    elif damage == "missing_end":
        original["opening_rows"][0]["original_g17_support_receipts"].pop()
    else:
        original["opening_rows"][0]["original_g17_support_receipts"][0]["snapshot_id"]="foreign"
    before=deepcopy((pdf,original,flank,digest))
    with pytest.raises(ValueError): run(pdf,original,flank,digest)
    assert (pdf,original,flank,digest)==before


@pytest.mark.parametrize("rotation", [0,90,180,270])
def test_original_g17_and_source_run_locality_is_transform_and_order_invariant(rotation):
    import math
    pdf,original,flank,digest=fixture()
    angle=math.radians(rotation);c,s=round(math.cos(angle)),round(math.sin(angle))
    def point(p): return [c*p[0]-s*p[1]+55.,s*p[0]+c*p[1]-30.]
    def vector(p): return [c*p[0]-s*p[1],s*p[0]+c*p[1]]
    def line(p): return point(p[:2])+point(p[2:])
    basis=original["opening_rows"][0]["original_aperture_coordinate_basis"]
    basis["origin"]=point(basis["origin"])
    basis["axis"],basis["normal"]=vector(basis["axis"]),vector(basis["normal"])
    for r in original["opening_rows"][0]["original_g17_support_receipts"]:
        r["original_source_support_geometry_pt"]=line(r["original_source_support_geometry_pt"])
    for f in flank["opening_rows"][0]["flanks"]:
        for r in f["pixel_run_candidates"]: r["source_line_pt"]=line(r["source_line_pt"])
    expected=run(pdf,original,flank,digest)
    original["opening_rows"][0]["original_g17_support_receipts"].reverse()
    flank["opening_rows"][0]["flanks"].reverse()
    for f in flank["opening_rows"][0]["flanks"]:
        f["pixel_run_candidates"].reverse()
        for r in f["pixel_run_candidates"]:
            p=r["source_line_pt"];r["source_line_pt"]=p[2:]+p[:2]
    assert run(pdf,original,flank,digest)==expected
    assert len(expected["opening_rows"][0]["cross_flank_source_pixel_band_alternatives"])==1
