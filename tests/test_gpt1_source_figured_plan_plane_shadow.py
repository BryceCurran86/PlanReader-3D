"""Original figured dimension + physical floor plan scope never self-mints m²."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import fitz
import pytest

import pb_source_figured_plan_plane_shadow as shadow


def _pdf():
    doc = fitz.open()
    for _ in range(3):
        doc.new_page(width=400, height=400)
    data = doc.tobytes()
    doc.close()
    return data


def _room(data, *, view="view_p3_1", face="source-face:7", label="WC"):
    return SimpleNamespace(
        physical_room_id="room:WC",
        source_room_face_record_id=face,
        source_sha256=sha256(data).hexdigest(),
        page_id="3", viewport_id=view,
        geometry_complete=True, room_label=label,
        room_label_binding_record_id="original-label",
        room_label_evidence_ids=("source:word:WC",),
        polygon_pdf_pts=((120.,120.),(150.,120.),(150.,150.),(120.,150.)),
    )


def _audit():
    rows=[]
    for h in ("a","b"):
        for v in ("a","b"):
            rows.append({
                "horizontal_dimension_id":"source-h:"+h,
                "horizontal_value_mm":1000.,
                "horizontal_endpoints_pt":((100.,100.),(200.,100.)),
                "horizontal_source_witness_ids":("source:htick:"+h+":0","source:htick:"+h+":1"),
                "horizontal_witness_segments":((100.,95.,100.,105.),(200.,95.,200.,105.)),
                "vertical_dimension_id":"source-v:"+v,
                "vertical_value_mm":500.,
                "vertical_endpoints_pt":((95.,100.),(95.,150.)),
                "vertical_source_witness_ids":("source:vtick:"+v+":0","source:vtick:"+v+":1"),
                "vertical_witness_segments":((90.,100.,100.,100.),(90.,150.,100.,150.)),
            })
    return {"attempted_pairs":4,"intersecting_pairs":0,"failed_pair_samples":rows}


def _view(*, box=(50.,50.,350.,350.),status="resolved",view_id="view_p3_1",kind="floor_plan"):
    return SimpleNamespace(
        view_id=view_id,
        view_type=kind,
        status=status,
        bounding_box=box,
        boundary_source="vector_frame",
    )


def _run(monkeypatch, data, *, views=None, rooms=None, audit=None):
    monkeypatch.setattr(shadow,"segment_page_viewports",lambda *a, **k: tuple(views or ()))
    return shadow.original_figured_plan_plane_shadow(
        data, expected_source_sha256=sha256(data).hexdigest(),
        page_index=2,
        rooms=rooms if rooms is not None else [_room(data)],
        witness_audit=audit if audit is not None else _audit(),
    )


def test_genuine_one_scope_only_creates_registration_candidate_never_metric(monkeypatch):
    data=_pdf()
    result=_run(monkeypatch,data,views=[_view()])
    r=result["per_room"][0]
    assert result["source_proven_floor_plan_viewports"][0]["viewport_id"]=="view_p3_1"
    assert r["source_own_viewport_and_axes_candidate"] is True
    assert r["first_unclosed_gate"]=="room_specific_source_wall_scale_registration_unproven"
    assert r["metric_room_area_m2"] is None and r["signed_quantity_id"] is None
    assert result["physical_scale_authority_granted"] is False
    assert result["room_metric_area_authority_granted"] is False
    assert result["published_quantities"]==[]
    assert result["commercial_projection_allowed"] is False


def test_unowned_room_does_not_borrow_other_viewport(monkeypatch):
    data=_pdf()
    r=_run(monkeypatch,data,views=[_view()],rooms=[_room(data,view="foreign_view")])
    assert r["per_room"][0]["first_unclosed_gate"]=="physical_room_source_viewport_identity_unresolved"
    assert not r["per_room"][0]["source_own_viewport_and_axes_candidate"]


def test_source_missing_plan_frame_remains_unavailable(monkeypatch):
    data=_pdf()
    r=_run(monkeypatch,data,views=[_view(kind="schedule")])
    assert r["source_proven_floor_plan_viewports"]==[]
    assert r["per_room"][0]["first_unclosed_gate"]=="unique_original_source_floor_plan_viewport_unavailable"


def test_competing_overlapping_original_frames_never_authorize(monkeypatch):
    data=_pdf()
    r=_run(monkeypatch,data,views=[
        _view(),_view(view_id="second",box=(70.,70.,330.,330.)),
    ])
    assert not r["source_viewport_nonoverlap"]
    assert not r["per_room"][0]["source_own_viewport_and_axes_candidate"]


def test_native_witness_outside_plan_frame_is_not_source_same_plane(monkeypatch):
    data=_pdf()
    rows=_audit()
    for row in rows["failed_pair_samples"]:
        row["vertical_witness_segments"]=((20.,100.,25.,100.),(20.,150.,25.,150.))
    r=_run(monkeypatch,data,views=[_view()],audit=rows)
    assert r["per_room"][0]["first_unclosed_gate"]=="two_source_figured_axis_systems_not_within_owned_viewport"


def test_untrusted_figured_system_works_only_as_shadow_not_area(monkeypatch):
    data=_pdf()
    rows=_audit()
    rows["attempted_pairs"]=999
    r=_run(monkeypatch,data,views=[_view()],audit=rows)
    assert not r["original_figured_dimensions_consistent"]
    assert not r["per_room"][0]["source_own_viewport_and_axes_candidate"]


def test_duplicate_or_missing_room_source_identity_abstains(monkeypatch):
    data=_pdf()
    room=_room(data,face="")
    r=_run(monkeypatch,data,views=[_view()],rooms=[room])
    assert r["per_room"][0]["first_unclosed_gate"]=="physical_room_source_receipts_incomplete"
    r=_run(monkeypatch,data,views=[_view()],rooms=[room,room])
    assert all(x["first_unclosed_gate"]=="physical_room_source_receipts_incomplete" for x in r["per_room"])


def test_different_pdf_sha_never_reuses_source_plane(monkeypatch):
    data=_pdf()
    with pytest.raises(ValueError,match="source SHA conflict"):
        shadow.original_figured_plan_plane_shadow(
            data,expected_source_sha256="bad",page_index=2,rooms=[],witness_audit=_audit())
