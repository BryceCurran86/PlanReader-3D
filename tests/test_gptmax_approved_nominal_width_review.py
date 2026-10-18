"""Explicit single-width review retains unknown height and source ownership."""
from copy import deepcopy
from dataclasses import asdict, replace
import json
import zipfile

import pytest

from pb_geometry_takeoff_model import MeasurementRecord
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_nominal_opening_canonical_shadow import _build_approved_single_width_review
from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
from pb_opening_source_review_shadow import build_opening_review_packets, nominal_opening_obj_shadow
from pb_source_observation_authority import ObservationSelector
from tools.build_opening_source_review_package import build_opening_source_review_package
from tools.diag_gptmax_producer_owned_g17_wall_shadow import _retention
from test_opening_label_dimension_authority import _pdf, _ingest


def _world(text="870 DOOR"):
    source,published=_ingest(_pdf(labels=((88.,124.,text),)),"approved-width")
    composition=compose_live_wall_opening_authority(
        source_visibility_producer=source,revision_id=published.revision.revision_id,page_ids=("1",))
    voids=compose_live_physical_opening_voids(
        source_visibility_producer=source,wall_opening_composition=composition)
    current,=voids.canonical_openings
    selector=ObservationSelector(current.document_id,current.revision_id,current.source_sha256,
        current.snapshot_id,current.representative_observation_id)
    label=OpeningLabelDimensionProducer.from_source_visibility_producer(source).publish_scope(selector).evidence
    assert label is not None
    approval=MeasurementRecord(value=label.dimension_values_mm[0],unit="mm",source_type="user_approved",confidence=1.,
        sheet="",page=1,scale="",geometry_ref=current.physical_opening_id,
        authority_status="user_approved",approved_by="Fixture owner",
        approved_at="2026-01-01T00:00:00+00:00",
        metadata={**{k:getattr(current,k) for k in (
            "document_id","revision_id","source_sha256","snapshot_id","page_id")},
            "axis":"width","label_evidence_id":label.evidence_id,
            "source_text_observation_ids":list(label.source_text_observation_ids)})
    return source,composition,voids,current,selector,approval


@pytest.fixture(scope="module")
def world():
    return _world()


def test_width_approval_does_not_invent_a_door_or_window_kind(world,monkeypatch):
    source,comp,_voids,current,selector,approval=world
    original=OpeningLabelDimensionProducer.publish_scope
    def missing_kind(self,selector):
        result=original(self,selector)
        return (replace(result,evidence=replace(result.evidence,semantic_kind=None))
                if result.evidence is not None else result)
    monkeypatch.setattr(OpeningLabelDimensionProducer,"publish_scope",missing_kind)
    obj=_build_approved_single_width_review(source,selector,approval=approval,current_opening=current)
    assert obj.opening_type=="GENERIC" and not obj.metadata["opening_kind_resolved"]
    row,=build_opening_review_packets(source,comp,nominal_width_approvals=(approval,))
    assert "source_owned_filling_kind" in row["next_required_evidence"]
    assert "owned_nominal_height" in row["next_required_evidence"]


def test_one_axis_approval_cannot_reinterpret_an_owned_two_axis_label():
    source,_comp,_voids,current,selector,approval=_world("2127 STACKER")
    with pytest.raises(ValueError,match="single-figure"):
        _build_approved_single_width_review(source,selector,approval=approval,current_opening=current)


def test_approved_width_reaches_existing_canonical_review_without_area_or_height(world):
    source,comp,voids,current,selector,approval=world
    before=_retention(comp,voids,verify_customer_rows=True)
    source_label=asdict(OpeningLabelDimensionProducer.from_source_visibility_producer(source).publish_scope(selector))
    unapproved=build_opening_review_packets(source,comp)
    assert unapproved[0]["canonical_nominal_review"] is None
    rows=build_opening_review_packets(source,comp,nominal_width_approvals=(approval,))
    row,=rows
    canonical=row["canonical_nominal_review"]
    assert canonical["id"]==current.physical_opening_id
    assert canonical["width_m"]==.87 and canonical["height_m"] is None
    assert canonical["wall_id"] is canonical["sill_height_m"] is canonical["offset_along_wall_m"] is None
    assert not canonical["takeoff_eligible"] and not canonical["deduction_authority"]
    assert not canonical["metadata"]["source_width_authority_granted"]
    assert "owned_nominal_height" in row["next_required_evidence"]
    assert "opening_universe_completeness" in row["next_required_evidence"]
    assert asdict(OpeningLabelDimensionProducer.from_source_visibility_producer(source).publish_scope(selector))==source_label
    assert _retention(comp,voids,verify_customer_rows=True)==before
    assert build_opening_review_packets(source,comp)==unapproved


@pytest.mark.parametrize("field,value",[
    ("source_type","documented_dimension"),("authority_status","firm"),
    ("approved_by",""),("approved_at",""),("approved_at","2026-01-01"),
    ("value",920.),("value",True),("value",float("nan")),
    ("unit","m"),("page",True),("geometry_ref","another-opening"),
])
def test_unapproved_or_different_value_never_becomes_a_width_annotation(world,field,value):
    source,_comp,_voids,current,selector,approval=world
    bad=replace(approval,**{field:value}) if field!="value" or value==value else deepcopy(approval)
    if field=="value" and value!=value:bad.value=value
    with pytest.raises(ValueError):
        _build_approved_single_width_review(source,selector,approval=bad,current_opening=current)


@pytest.mark.parametrize("field,value",[
    ("axis","height"),("document_id","other"),("revision_id","old"),
    ("source_sha256","0"*64),("snapshot_id","other"),("page_id","2"),
    ("label_evidence_id","other"),("source_text_observation_ids",[]),
])
def test_approval_cannot_transfer_to_another_source_owner_or_dimension(world,field,value):
    source,_comp,_voids,current,selector,approval=world
    bad=deepcopy(approval);bad.metadata[field]=value
    with pytest.raises(ValueError):
        _build_approved_single_width_review(source,selector,approval=bad,current_opening=current)


@pytest.mark.parametrize("changes",[
    {"schedule_binding_record_id":"schedule"},{"schedule_declared_width_mm":920},
    {"schedule_declared_height_mm":2040},{"width_record_id":"source-width"},
    {"width_m":.92},{"snapshot_id":"other"},
])
def test_existing_schedule_and_source_measurements_are_never_overridden(world,changes):
    source,_comp,_voids,current,selector,approval=world
    with pytest.raises(ValueError):
        _build_approved_single_width_review(source,selector,approval=approval,
            current_opening=replace(current,**changes))


def test_record_order_replay_and_post_call_mutation_leave_approval_evidence_stable(world):
    source,_comp,_voids,current,selector,approval=world
    def run(a):return _build_approved_single_width_review(source,selector,approval=a,current_opening=current)
    a=deepcopy(approval)
    first=run(a).to_dict()
    a.metadata["source_text_observation_ids"].reverse()
    assert run(a).to_dict()==first
    a.value=int(a.value)
    assert run(a).to_dict()==first
    a.metadata["source_text_observation_ids"].append("foreign")
    assert first["metadata"]["nominal_width_approval"]["metadata"]==approval.metadata
    with pytest.raises(ValueError):run(a)
    with pytest.raises(ValueError):nominal_opening_obj_shadow(run(approval))


def test_duplicate_unknown_and_empty_approval_scopes_do_not_select_a_target(world):
    source,comp,_voids,_current,_selector,approval=world
    with pytest.raises(ValueError,match="duplicate"):
        build_opening_review_packets(source,comp,nominal_width_approvals=(approval,approval))
    with pytest.raises(ValueError,match="absent"):
        build_opening_review_packets(source,comp,
            nominal_width_approvals=(replace(approval,geometry_ref="absent"),))
    with pytest.raises(TypeError):build_opening_review_packets(source,comp,nominal_width_approvals=True)


def test_offline_package_keeps_width_evidence_without_inventing_a_rectangular_asset(world,tmp_path):
    source,comp,voids,_current,_selector,approval=world
    rows=build_opening_review_packets(source,comp,nominal_width_approvals=(approval,))
    receipt=_retention(comp,voids,verify_customer_rows=True)
    report={"status":"original_issuer_preserved_additional_source_shadow",
        "original_issuer_body_unchanged_during_fork":True,
        "new_authority_promotion_granted":False,"customer_publication_granted":False,
        "original_source_sha256":approval.metadata["source_sha256"],
        "original_opening_review_packets":rows,"alternate_opening_review_packets":rows,
        "original_receipt":receipt,"alternate_receipt":receipt}
    archive=tmp_path/"partial.zip"
    build_opening_source_review_package(report,archive)
    with zipfile.ZipFile(archive) as z:
        assert not any(p.endswith(".obj") for p in z.namelist())
        data=json.loads(z.read("original/evidence/"+rows[0]["packet_id"]+".json"))
        assert data["canonical_nominal_review"]["height_m"] is None
        assert "height unresolved" in z.read("review.html").decode()
    bad=deepcopy(report)
    bad["alternate_opening_review_packets"][0]["canonical_nominal_review"]["height_m"]=2.1
    rejected=tmp_path/"invented-height.zip"
    with pytest.raises(ValueError):build_opening_source_review_package(bad,rejected)
    assert not rejected.exists()
