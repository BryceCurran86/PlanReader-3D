"""GPT1 source-owned plan-view ingress is not room/metric authority."""
from hashlib import sha256
from types import SimpleNamespace

import pytest

from pb_source_figured_plan_plane_shadow import original_figured_plan_plane_shadow
from pb_viewport_segmentation import (
    is_authoritative_derived_viewport, segment_source_page_viewports,
)
from tests.test_gpt1_source_figured_plan_plane_shadow import _audit
from tests.test_source_owned_physical_plan_view import _sheet, _source


def _real_room(data, pub, plan, **changes):
    values = dict(
        document_id=pub.revision.document_id,
        revision_id=pub.revision.revision_id,
        snapshot_id=pub.snapshot.snapshot_id,
        source_sha256=sha256(data).hexdigest(),
        page_id="1",
        viewport_id=plan.view_id,
        physical_room_id="r:KITCHEN",
        source_room_face_record_id="original-face",
        room_label_binding_record_id="original-word-owner",
        room_label_evidence_ids=("original-word",),
        room_label="KITCHEN",
        geometry_complete=True,
        polygon_pdf_pts=(
            (120., 120.), (150., 120.), (150., 150.), (120., 150.)
        ),
    )
    return SimpleNamespace(**dict(values, **changes))


def _run(data, source, pub, rooms):
    return original_figured_plan_plane_shadow(
        data, expected_source_sha256=sha256(data).hexdigest(),
        page_index=0, rooms=rooms, witness_audit=_audit(),
        source_visibility_producer=source,
        source_revision_id=pub.revision.revision_id,
    )


def test_producer_owned_floor_plan_advances_exact_original_first_gate_without_area():
    data = _sheet()
    source, pub = _source(data)
    plan, = [v for v in segment_source_page_viewports(
        source, revision_id=pub.revision.revision_id,
        page_id="1", physical_plan_view_shadow=True,
    ) if is_authoritative_derived_viewport(v)]
    assert tuple(plan.bounding_box) == (50.,50.,350.,350.)
    before = source.published_snapshot_for_revision(pub.revision.revision_id)
    baseline = original_figured_plan_plane_shadow(
        data, expected_source_sha256=sha256(data).hexdigest(),
        page_index=0, rooms=(_real_room(data,pub,plan),), witness_audit=_audit(),
    )
    result = _run(data,source,pub,(_real_room(data,pub,plan),))
    assert baseline["source_proven_floor_plan_viewports"] == []
    assert result["source_plan_view_proof_mode"] == "producer_source_owned"
    assert result["source_proven_floor_plan_viewports"] == [{
        "viewport_id":plan.view_id,"native_bbox_pdf_points":[50.,50.,350.,350.]
    }]
    room = result["per_room"][0]
    assert room["source_room_snapshot_owned_by_this_view_producer"] is True
    assert room["source_own_viewport_and_axes_candidate"] is True
    assert room["first_unclosed_gate"] == "room_specific_source_wall_scale_registration_unproven"
    assert room["metric_room_area_m2"] is None and room["signed_quantity_id"] is None
    assert not result["physical_scale_authority_granted"]
    assert not result["room_metric_area_authority_granted"]
    assert result["published_quantities"] == []
    assert not result["commercial_projection_allowed"]
    assert source.published_snapshot_for_revision(pub.revision.revision_id) == before


def test_matching_geometry_but_foreign_room_snapshot_cannot_borrow_viewport():
    data = _sheet()
    source, pub = _source(data)
    view, = [v for v in segment_source_page_viewports(
        source,revision_id=pub.revision.revision_id,page_id="1",
        physical_plan_view_shadow=True,
    ) if is_authoritative_derived_viewport(v)]
    fake = _real_room(data,pub,view,snapshot_id="another-source-snapshot")
    result = _run(data,source,pub,(fake,))
    room = result["per_room"][0]
    assert not room["source_room_snapshot_owned_by_this_view_producer"]
    assert room["first_unclosed_gate"]=="physical_room_source_revision_or_snapshot_unmatched"
    assert not room["source_own_viewport_and_axes_candidate"]
    assert result["published_quantities"]==[]


def test_same_source_but_foreign_viewport_id_cannot_borrow_box():
    data=_sheet()
    source,pub=_source(data)
    view, = [v for v in segment_source_page_viewports(
        source,revision_id=pub.revision.revision_id,page_id="1",
        physical_plan_view_shadow=True,
    ) if is_authoritative_derived_viewport(v)]
    room=_real_room(data,pub,view,viewport_id="other-drawing")
    result=_run(data,source,pub,(room,))
    assert result["per_room"][0]["first_unclosed_gate"] == (
        "physical_room_source_viewport_identity_unresolved"
    )
    assert not result["per_room"][0]["source_own_viewport_and_axes_candidate"]


@pytest.mark.parametrize("changes", [
    {"no_frame":True},{"no_dimensions":True},{"one_axis":True},
    {"second":True},{"hidden_role":True},{"role":"FRONT ELEVATION"},
])
def test_real_source_view_unsupported_or_competing_never_supplies_room_measurement(changes):
    data=_sheet(**changes)
    source,pub=_source(data)
    room=SimpleNamespace(
        physical_room_id="r:x",source_sha256=sha256(data).hexdigest(),
        page_id="1",viewport_id="fake",source_room_face_record_id="face",
        room_label_binding_record_id="label",room_label_evidence_ids=("word",),
        geometry_complete=True,polygon_pdf_pts=(
            (120.,120.),(150.,120.),(150.,150.),(120.,150.)),
        document_id=pub.revision.document_id,
        revision_id=pub.revision.revision_id,snapshot_id=pub.snapshot.snapshot_id,
    )
    result=_run(data,source,pub,(room,))
    assert result["source_proven_floor_plan_viewports"] == []
    assert result["per_room"][0]["first_unclosed_gate"]=="unique_original_source_floor_plan_viewport_unavailable"
    assert result["published_quantities"]==[]


def test_reject_copied_source_corruption_stale_revision_and_unpaired_source_arguments():
    data=_sheet()
    source,pub=_source(data)
    with pytest.raises(TypeError):
        original_figured_plan_plane_shadow(
            data,expected_source_sha256=sha256(data).hexdigest(),
            page_index=0,rooms=(),witness_audit=_audit(),
            source_visibility_producer=source,
        )
    with pytest.raises(TypeError):
        original_figured_plan_plane_shadow(
            data,expected_source_sha256=sha256(data).hexdigest(),
            page_index=0,rooms=(),witness_audit=_audit(),
            source_visibility_producer=object(),source_revision_id=pub.revision.revision_id,
        )
    source._producer._store.source_bytes_by_revision[pub.revision.revision_id]=b"changed"
    with pytest.raises(ValueError,match="foreign, stale, or incomplete"):
        _run(data,source,pub,())
    source,pub=_source(data)
    source.ingest_native_pdf_bytes(
        document_id="source-test",source_bytes=_sheet(unrelated=True),
        source_locator="memory://different.pdf",page_ids=("1",),
    )
    with pytest.raises(ValueError,match="foreign, stale, or incomplete"):
        _run(data,source,pub,())
