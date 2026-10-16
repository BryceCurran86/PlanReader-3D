"""A floor-plan F07 receipt cannot supply a missing host, frame or metric axis."""
from copy import deepcopy

import pytest

from tools.diag_gptmax_lot16_host_frame_gpt1_handoff import assess_gpt1_opening_candidates

ROOT = {
    "document_id": "live-source:example",
    "revision_id": "source_revision_example",
    "source_sha256": "a"*64,
    "snapshot_id": "source_snapshot_example",
}
VIEW = {
    "status": "SOURCE_VIEW_CANDIDATE_SAME_ROOT_ONLY",
    "selected_view_id": "source_plan_view_source_example",
    "selected_bbox_pt": [0,0,200,200],
}


def fixture():
    def canonical(identity, host=None, frame=None):
        return {
            "physical_opening_id": identity,
            "canonical_opening_id": identity,
            **ROOT, "page_id": "3", "opening_kind": "window",
            "host_binding_record_id": host,
            "host_wall_id": "wall-grp" if host else None,
            "host_frame_record_id": frame,
            "figured_area_record_id": "figured",
            "width_record_id": None, "height_record_id": None,
            "width_m": None, "height_m": None,
            "geometry_complete": False,
        }
    def row(identity, host=None, frame=None, area=False):
        label = {"status":"corroborated", "evidence":{
            "opening_record_id": identity,
            "evidence_id":"figured",
            "dimension_values_mm":[1200,1800],
            "axis_order_resolved":False,
            "area_m2":2.16,
        }} if area else {"status":"abstained","evidence":None}
        return {
            "physical_opening_id":identity,
            "canonical_opening_id":identity,
            **ROOT, "page_id":"3",
            "attempted_host_selector":{"decision_scope_id":"wall-source:page-3"},
            "physical_existence_record":{"record_id":identity},
            "host_record":None if not host else {
                "record_id":host,"host_wall_id":"wall-grp",
                "opening_identity_id":identity,
                "member_wall_candidate_ids":["wall-a"],
            },
            "frame_record":None if not frame else {
                "record_id":frame,"opening_identity_id":identity,
                "host_binding_record_id":host,"host_wall_id":"wall-grp",
                "coordinate_unit":"pdf_point",
                "whole_wall_candidate_ids":["wall-a"],
                "source_observation_ids":["source-own-1"],
                "whole_wall_length_pt":50.0, "u0_pt":10.0,"u1_pt":22.0,
                "wall_thickness_pt":2.5,
                "axis_unit":[1.,0.], "normal_unit":[0.,1.],
                "origin_pt":[5.,10.],
            },
            "original_label_dimension_result":label,
            "frame_reason_codes":["opening_host_frame_resolved"] if frame else ["frame_blocked"],
            "host_reason_codes":["opening_host_binding_resolved"] if host else ["no_authenticated_host_wall_band"],
            "quantity_id":None,
        }
    rows=[
        row("physical-1"),
        row("physical-2","binding-2"),
        row("physical-3","binding-3","frame-3",area=True),
    ]
    c=[
        canonical("physical-1"),
        canonical("physical-2","binding-2"),
        canonical("physical-3","binding-3","frame-3"),
    ]
    return rows,c


def run(rows=None,c=None,view=None):
    base,canonical=fixture()
    return assess_gpt1_opening_candidates(
        base if rows is None else rows,
        canonical if c is None else c,
        VIEW if view is None else view,
        source_root=ROOT)


def test_independent_host_frame_axis_and_figured_source_gates_are_not_conflated():
    r=run()
    assert r["original_physical_opening_count"]==3
    assert r["original_authenticated_hosts"]==2
    assert r["original_complete_host_frames"]==1
    assert r["first_gate_counts"]=={
        "structural_host_unavailable":1,
        "whole_wall_frame_unavailable":1,
        "width_height_axis_authority_unproven":1,
    }
    assert r["opening_decisions"][2]["figured_pair_area_support"]
    assert not r["opening_decisions"][2]["axis_order_authenticated"]
    assert all(not x["new_gpt1_candidate_handoff"]
               and not x["measurement_published"]
               and not x["customer_seal_granted"]
               and not x["opening_count_granted"] for x in r["opening_decisions"])
    assert not r["gpt1_new_handoff_candidates"]


def test_original_input_order_and_source_immutability():
    rows,canonical=fixture()
    original=deepcopy((rows,canonical))
    first=run(rows,canonical)
    assert first==run(rows[::-1],canonical[::-1])
    assert original==(rows,canonical)


def test_unproven_f07_cannot_promote_existing_frame():
    v=dict(VIEW,status="ABSTAIN")
    r=run(view=v)
    assert r["first_gate_counts"]=={"source_owned_floor_plan_unavailable":3}
    assert not r["gpt1_new_handoff_candidates"]


def test_valid_source_axes_only_emits_unpublished_gpt1_review_candidate():
    rows,c=fixture()
    index=2
    c[index].update(width_record_id="width-3",height_record_id="height-3",
                    width_m=1.2,height_m=1.8,geometry_complete=True)
    rows[index]["original_label_dimension_result"]["evidence"]["axis_order_resolved"]=True
    r=run(rows,c)
    assert len(r["gpt1_new_handoff_candidates"])==1
    assert r["gpt1_new_handoff_candidates"][0]["physical_opening_id"]=="physical-3"
    assert not r["signed_customer_publisher_activated"]
    assert not r["global_opening_count_granted"]


def test_existing_signed_area_is_not_republished_as_new_candidate():
    rows,c=fixture()
    c[2].update(width_record_id="width",height_record_id="height",
                width_m=1.2,height_m=1.8,geometry_complete=True)
    rows[2]["original_label_dimension_result"]["evidence"]["axis_order_resolved"]=True
    rows[2]["quantity_id"]="previously-signed-quantity"
    assert not run(rows,c)["gpt1_new_handoff_candidates"]


@pytest.mark.parametrize("mutate",[
    lambda r,c:r[1]["host_record"].update(host_wall_id="foreign"),
    lambda r,c:c[2].update(host_frame_record_id="foreign"),
    lambda r,c:r[2]["frame_record"].update(u1_pt=80),
    lambda r,c:r[2]["frame_record"].update(wall_thickness_pt=0),
    lambda r,c:r[2]["frame_record"].update(normal_unit=[1.,0.]),
    lambda r,c:r[2]["frame_record"].update(source_observation_ids=[]),
    lambda r,c:r[2]["frame_record"].update(whole_wall_length_pt=float("nan")),
    lambda r,c:r[2]["original_label_dimension_result"]["evidence"].update(area_m2=5.0),
    lambda r,c:r[1].update(snapshot_id="old-snapshot"),
    lambda r,c:c[1].update(source_sha256="0"*64),
    lambda r,c:r[1]["physical_existence_record"].update(record_id="other"),
])
def test_corrupted_producer_lineage_or_geometry_fails_closed(mutate):
    rows,c=fixture()
    mutate(rows,c)
    with pytest.raises(ValueError):
        run(rows,c)


def test_duplicate_original_opening_fails_closed():
    rows,c=fixture()
    rows.append(deepcopy(rows[0]))
    with pytest.raises(ValueError,match="inventory"):
        run(rows,c)
