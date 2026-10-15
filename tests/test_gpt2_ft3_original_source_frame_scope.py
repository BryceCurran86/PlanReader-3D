"""Generic fail-closed native finish-label to vector-frame locality tests."""
from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import pytest

from tools.diag_gpt2_ft3_original_source_frame_scope import (
    audit_source_frame_locality,
)

SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
FRAME=(100.0,100.0,300.0,300.0)
TABLE=(310.0,100.0,480.0,300.0)


def _census(*boxes,verified=True):
    return {
        "original_source_sha256":SHA,"page_id":"11",
        "viewports_non_overlapping":True,
        "marks":[{
            "source_word_observation_id":f"source_observation_{i:03d}",
            "native_bbox_pdf_points":list(b),
            "source_text_verified":verified,
            "text":"FT3",
        } for i,b in enumerate(boxes)]
    }


def test_five_native_marks_in_one_frame_not_enough_to_mint_plan_or_quantity():
    boxes=[(120.,110.+i*20,133.,119.+i*20) for i in range(5)]
    boxes.append((510.,500.,523.,509.))
    r=audit_source_frame_locality(
        _census(*boxes),[FRAME,TABLE],[],
        expected_sha=SHA,
        frame_table_roles={TABLE:(True,True)},
    )
    assert r["source_mark_count"]==6
    assert r["single_native_frame_max_whole_mark_count"]==5
    assert [x["whole_mark_count"] for x in r["native_frames_source_first_gates"]]==[5,0]
    assert r["original_source_uncontained_mark_observation_ids"]==["source_observation_005"]
    assert r["authenticated_floor_finish_plan_viewport_count"]==0
    assert r["source_first_unclosed_authority"]=="source_plan_viewport_unresolved"
    assert not r["material_occurrence_universe_complete"]
    assert not r["metric_floor_finish_area_published"]
    assert not r["new_customer_quantity_published"]
    assert not r["benchmark_identity_or_score_granted"]


def test_frame_source_permutation_does_not_elect_a_floor_plan():
    marks=_census((120.,120.,125.,125.),(320.,120.,325.,125.))
    a=audit_source_frame_locality(marks,[TABLE,FRAME],[],expected_sha=SHA)
    b=audit_source_frame_locality(marks,[FRAME,TABLE],[],expected_sha=SHA)
    assert a==b
    assert all(v["candidate_only_not_a_source_plan_owner"] for v in a["native_frames_source_first_gates"])


def test_two_frames_containing_same_original_word_remain_unowned():
    wider=(90.,90.,490.,490.)
    r=audit_source_frame_locality(
        _census((120.,120.,125.,125.)),[FRAME,wider],[],
        expected_sha=SHA
    )
    assert sum(x["whole_mark_count"] for x in r["native_frames_source_first_gates"])==2
    assert r["source_first_unclosed_authority"]=="source_plan_viewport_unresolved"
    assert r["authenticated_floor_finish_plan_viewport_count"]==0


def test_false_copied_viewport_payload_cannot_mint_producer_identity():
    forged=SimpleNamespace(view_type="floor_finish_plan",status="resolved",
        bounding_box=FRAME,view_id="guessed-source-plan")
    r=audit_source_frame_locality(
        _census((120.,120.,125.,125.)),[FRAME],[forged],
        expected_sha=SHA
    )
    assert r["authenticated_floor_finish_plan_viewport_count"]==0
    assert r["source_first_unclosed_authority"]=="source_plan_viewport_unresolved"


@pytest.mark.parametrize("mutation",[
    "wrong-sha","other-page","duplicate-observation",
    "missing-observation","invalid-bbox","duplicate-frame",
])
def test_malformed_or_replayed_source_lineage_fails_closed(mutation):
    c=_census((120.,120.,125.,125.))
    frames=[FRAME]
    expected_sha=SHA
    if mutation=="wrong-sha": expected_sha="a"*64
    elif mutation=="other-page": c["page_id"]="9"
    elif mutation=="duplicate-observation":c["marks"].append(deepcopy(c["marks"][0]))
    elif mutation=="missing-observation":c["marks"][0]["source_word_observation_id"]=""
    elif mutation=="invalid-bbox":c["marks"][0]["native_bbox_pdf_points"]=[float("nan"),0,1,2]
    elif mutation=="duplicate-frame":frames=[FRAME,FRAME]
    with pytest.raises(ValueError):
        audit_source_frame_locality(c,frames,[],expected_sha=expected_sha)


def test_non_verified_original_native_word_never_closes_source_authority():
    r=audit_source_frame_locality(
        _census((120.,120.,125.,125.),verified=False),[FRAME],[],
        expected_sha=SHA
    )
    assert not r["all_native_source_mark_text_authenticated"]
    assert r["source_first_unclosed_authority"]=="source_plan_viewport_unresolved"
    assert r["new_customer_quantity_published"] is False
