"""No physical room or material inferred from a genuine source label."""
from types import SimpleNamespace as O
from copy import deepcopy
import pytest
from tools.diag_gpt2_positive_room_label_canonical_projection import (
    original_source_label_to_canonical_first_gates as audit,
)

SHA="a"*64
FACE="original-source-face-receipt"
FACE_ID="positive-physical-face-id"
OBS="trusted-original-observation-id"


def source():
    return {"original_pdf_sha_verified":SHA,
            "source_scope_first_failures":[{
                "page_id":"7","decision_scope_id":"wall-source:viewport:7:v",
                "original_source_label_gate":{
                   "direct_source_label_count":1,
                   "direct_source_labels":[{
                       "label":"SALES","source_face_receipt_id":FACE,
                       "source_face_id":FACE_ID,
                       "original_text_observation_ids":[OBS],
                   }],
                },
            }]}


def room():
    return O(source_room_face_record_id=FACE,source_sha256=SHA,page_id="7",
             canonical_room_id="real-canonical-room-1",
             room_label="SALES",room_label_binding_record_id="label-record-1",
             room_label_evidence_ids=(OBS,))


def report(original=None,rooms=None,sha=SHA):
    return audit(original if original is not None else source(),
                 rooms if rooms is not None else (room(),),
                 expected_original_sha=sha)


def gate(result):
    return result["first_projection_gates"][0]["first_unproved_projection_gate"]


def test_positive_exact_source_face_and_word_receipt_may_project_without_quantity():
    d=report()
    assert d["authentic_positive_original_label_count"]==1
    assert gate(d)=="ORIGINAL_SOURCE_LABEL_PROJECTION_PRESENT"
    assert d["benchmark_accuracy"] is None
    r=d["first_projection_gates"][0]
    assert r["original_source_face_receipt_id"]==FACE
    assert r["original_source_text_observation_ids"]==[OBS]
    assert not r["source_room_geometry_inferred"]
    assert not r["metric_area_or_finish_published"]


@pytest.mark.parametrize("change,reason",[
    ("missing","ORIGINAL_SOURCE_FACE_MISSING_IN_CANONICAL"),
    ("duplicate","ORIGINAL_SOURCE_FACE_DUPLICATED_IN_CANONICAL"),
    ("foreign_sha","CANONICAL_FACE_SOURCE_PROVENANCE_MISMATCH"),
    ("foreign_page","CANONICAL_FACE_SOURCE_PROVENANCE_MISMATCH"),
    ("no_canonical_id","CANONICAL_FACE_SOURCE_PROVENANCE_MISMATCH"),
    ("unlabeled","CANONICAL_ROOM_LABEL_BINDING_UNAVAILABLE"),
    ("wrong_name","CANONICAL_ROOM_LABEL_LITERAL_CONFLICT"),
    ("missing_word","ORIGINAL_TEXT_RECEIPTS_NOT_RETAINED_IN_CANONICAL"),
    ("wrong_word","ORIGINAL_TEXT_RECEIPTS_NOT_RETAINED_IN_CANONICAL"),
    ("missing_label_id","ORIGINAL_TEXT_RECEIPTS_NOT_RETAINED_IN_CANONICAL"),
])
def test_canonical_label_ownership_gate_distinguishes_true_first_failure(change,reason):
    r=room()
    records=(r,)
    if change=="missing":records=()
    elif change=="duplicate":records=(r,deepcopy(r))
    elif change=="foreign_sha":r.source_sha256="b"*64
    elif change=="foreign_page":r.page_id="11"
    elif change=="no_canonical_id":r.canonical_room_id=None
    elif change=="unlabeled":r.room_label=None
    elif change=="wrong_name":r.room_label="FOOD SERVICE"
    elif change=="missing_word":r.room_label_evidence_ids=()
    elif change=="wrong_word":r.room_label_evidence_ids=("unrelated-word",)
    elif change=="missing_label_id":r.room_label_binding_record_id=None
    d=report(rooms=records)
    assert gate(d)==reason
    assert d["first_projection_gates"][0]["metric_area_or_finish_published"] is False


@pytest.mark.parametrize("damage",[
    "wrong_pdf_sha","duplicate_original_face","duplicate_original_word",
    "foreign_page","duplicate_scope","missing_label","missing_word",
    "blank_source_face","not_sealed_canonical_inventory",
    "duplicate_original_physical_face","unhashable_original_word",
    "boolean_source_label_count",
])
def test_untrusted_original_label_replay_cannot_attach_geometry(damage):
    d=source()
    row=d["source_scope_first_failures"][0]["original_source_label_gate"]["direct_source_labels"][0]
    if damage=="wrong_pdf_sha":d["original_pdf_sha_verified"]="b"*64
    elif damage=="duplicate_original_face":
        d["source_scope_first_failures"][0]["original_source_label_gate"]["direct_source_labels"].append(deepcopy(row))
        d["source_scope_first_failures"][0]["original_source_label_gate"]["direct_source_label_count"]=2
    elif damage=="duplicate_original_word":
        other=deepcopy(row);other["source_face_receipt_id"]="other-face"
        d["source_scope_first_failures"][0]["original_source_label_gate"]["direct_source_labels"].append(other)
        d["source_scope_first_failures"][0]["original_source_label_gate"]["direct_source_label_count"]=2
    elif damage=="duplicate_original_physical_face":
        other=deepcopy(row)
        other["source_face_receipt_id"]="distinct-receipt-for-same-source-face"
        other["original_text_observation_ids"]=["separate-source-word"]
        d["source_scope_first_failures"][0]["original_source_label_gate"]["direct_source_labels"].append(other)
        d["source_scope_first_failures"][0]["original_source_label_gate"]["direct_source_label_count"]=2
    elif damage=="unhashable_original_word":
        row["original_text_observation_ids"]=[["malformed-nested-word"]]
    elif damage=="boolean_source_label_count":
        d["source_scope_first_failures"][0]["original_source_label_gate"]["direct_source_label_count"]=True
    elif damage=="foreign_page":d["source_scope_first_failures"][0]["page_id"]="11"
    elif damage=="duplicate_scope":d["source_scope_first_failures"].append(deepcopy(d["source_scope_first_failures"][0]))
    elif damage=="missing_label":row["label"]=""
    elif damage=="missing_word":row["original_text_observation_ids"]=[]
    elif damage=="blank_source_face":row["source_face_receipt_id"]=" "
    elif damage=="not_sealed_canonical_inventory":
        with pytest.raises(ValueError):report(rooms=[room()])
        return
    with pytest.raises(ValueError):report(original=d)


def test_original_positive_label_with_no_matching_canonical_must_remain_unpublished():
    result=report(rooms=())
    row=result["first_projection_gates"][0]
    assert row["canonical_matched_source_face_count"]==0
    assert row["canonical_room_id"] is None
    assert row["metric_area_or_finish_published"] is False


def test_malformed_canonical_word_receipt_cannot_retain_source_label():
    r=room()
    r.room_label_evidence_ids=(["unhashable-nested-word"],)
    d=report(rooms=(r,))
    assert gate(d)=="ORIGINAL_TEXT_RECEIPTS_NOT_RETAINED_IN_CANONICAL"
    assert d["first_projection_gates"][0]["metric_area_or_finish_published"] is False
