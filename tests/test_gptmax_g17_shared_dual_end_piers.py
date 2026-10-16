"""Original exact shared G17 source face plus two opening-owned ends."""
from copy import deepcopy
from hashlib import sha256

import pytest

from tools.diag_gptmax_g17_shared_dual_end_piers import (
    STATUS,audit_shared_original_g17_dual_end_piers,
    source_original_dual_end_replay,
)


def item(i,kind,geo,parents=None):
    return {"id":i,"kind":kind,"geometry_pdf_pts":list(geo),
            "parents":parents or ["parent-"+i]}


def pair():
    faces={
        "face-l":item("face-l","raster_wall_band_face",(0,1,5,1)),
        "face-r":item("face-r","raster_wall_band_face",(0,3,5,3)),
    }
    return {
        "physical-a":{**deepcopy(faces),"end-first":
                      item("end-first","raster_wall_band_end",(0,1,0,3))},
        "physical-b":{**deepcopy(faces),"end-last":
                      item("end-last","raster_wall_band_end",(5,1,5,3))},
    }


def one(result):
    assert result["status"]==STATUS
    rows=result["source_sharing_pairs"]
    assert len(rows)==1
    assert not any(result[x] for x in (
        "new_source_derived_W4_host_granted",
        "cross_resolution_equivalence_granted","metric_width_height_granted",
        "opening_count_granted"))
    return rows[0]


def test_original_two_ends_and_identical_face_source_positive_not_host():
    result=one(audit_shared_original_g17_dual_end_piers(pair()))
    assert result["source_closed_pier_candidate"]
    assert result["reason"]=="complete_own_source_two_end_pier_geometry"
    assert result["source_closed_source_observation_ids"]==[
        "end-first","end-last","face-l","face-r"]
    assert result["opening_ids"]==["physical-a","physical-b"]
    assert result["source_closed_pier_geometry_candidate"]=={
        "axis":"horizontal","original_axis_span_pt":[0,5],
        "original_cross_offsets_pt":[1,3]}
    assert not result["physical_structural_wall_role_granted"]
    assert not result["cross_resolution_equivalence_granted"]
    assert not result["wall_host_granted"]
    assert not result["metric_quantity_granted"]


def test_vertical_shared_pier_has_same_contract():
    p=pair()
    for owner in p.values():
        for row in owner.values():
            a,b,c,d=row["geometry_pdf_pts"]
            row["geometry_pdf_pts"]=[b,a,d,c]
    r=one(audit_shared_original_g17_dual_end_piers(p))
    assert r["source_closed_pier_candidate"]
    assert r["source_closed_pier_geometry_candidate"]["axis"]=="vertical"


@pytest.mark.parametrize("modify",[
    lambda x:x["physical-a"].pop("end-first"),
    lambda x:x["physical-b"].pop("end-last"),
    lambda x:x["physical-a"]["end-first"]["geometry_pdf_pts"].__setitem__(0,0.3),
    lambda x:x["physical-b"]["end-last"]["geometry_pdf_pts"].__setitem__(1,1.2),
    lambda x:x["physical-b"].update({"second-high":
        item("second-high","raster_wall_band_end",(5,1,5,3))}),
])
def test_missing_shifted_or_competing_end_abstains(modify):
    p=pair()
    modify(p)
    row=one(audit_shared_original_g17_dual_end_piers(p))
    assert not row["source_closed_pier_candidate"]
    assert row["reason"]=="competing_or_missing_original_two_end_caps"


def test_shared_face_geometry_drift_abstains():
    p=pair()
    p["physical-b"]["face-l"]["geometry_pdf_pts"][0]=0.2
    r=one(audit_shared_original_g17_dual_end_piers(p))
    assert r["reason"]=="shared_source_faces_geometry_or_parent_conflict"
    assert not r["source_closed_pier_candidate"]


def test_shared_parent_identity_drift_abstains():
    p=pair()
    p["physical-b"]["face-l"]["parents"]=["new-unrelated-parent"]
    assert one(audit_shared_original_g17_dual_end_piers(p))[
        "source_closed_pier_candidate"] is False


def test_shared_face_competing_third_opening_fails_not_first_pair():
    p=pair()
    p["physical-c"]={**deepcopy({
        "face-l":p["physical-a"]["face-l"],
        "face-r":p["physical-a"]["face-r"]}),
        "end-extra":item("end-extra","raster_wall_band_end",(0,1,0,3))}
    r=audit_shared_original_g17_dual_end_piers(p)
    assert len(r["source_sharing_pairs"])==3
    assert not any(x["source_closed_pier_candidate"] for x in r["source_sharing_pairs"])
    assert all(not x["wall_host_granted"] for x in r["source_sharing_pairs"])


def test_irrelevant_third_opening_preserves_positive_and_negative():
    p=pair()
    p["physical-c"]={"unrelated":
        item("unrelated","raster_wall_band_face",(10,0,20,0))}
    assert one(audit_shared_original_g17_dual_end_piers(p))["source_closed_pier_candidate"]


def test_permutation_never_picks_nearest_face_or_end():
    p=pair()
    a=audit_shared_original_g17_dual_end_piers(p)
    q={k:dict(reversed(list(v.items()))) for k,v in reversed(list(p.items()))}
    b=audit_shared_original_g17_dual_end_piers(q)
    assert a==b


@pytest.mark.parametrize("modify",[
    lambda p:p["physical-a"]["face-l"].update(id="foreign"),
    lambda p:p["physical-a"]["face-l"].update(parents=[]),
    lambda p:p["physical-a"]["face-l"].update(parents=["same","same"]),
    lambda p:p["physical-a"]["face-l"]["geometry_pdf_pts"].__setitem__(0,float("inf")),
])
def test_corrupt_original_source_ids_parents_or_geometry_fail_closed(modify):
    p=pair()
    modify(p)
    with pytest.raises(ValueError):
        audit_shared_original_g17_dual_end_piers(p)


def test_empty_source_inventory_nothing_promoted():
    r=audit_shared_original_g17_dual_end_piers({})
    assert r["source_sharing_pairs"]==[]
    assert r["new_source_derived_W4_host_granted"] is False


def test_bad_source_hash_cannot_ask_producer_for_opening():
    with pytest.raises(ValueError,match="SHA"):
        source_original_dual_end_replay(b"fake original",sha256(b"other").hexdigest())
