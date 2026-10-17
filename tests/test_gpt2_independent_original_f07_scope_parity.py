"""Original F07 sibling read-only parity: independent source not a cache alias."""
from copy import deepcopy
from types import SimpleNamespace

import pytest

from pb_viewport_segmentation import (
    SegmentedViewport, _stamp_segment_page_viewports_product,
)
from tools.diag_gpt2_independent_f07_original_scope_parity import (
    classify_independent_f07_siblings, replay_original_source_f07_first_gate,
)


def published():
    return SimpleNamespace(
        revision=SimpleNamespace(
            document_id="original-source-doc", revision_id="revision-r1",
            source_sha256="f" * 64,
        ),
        snapshot=SimpleNamespace(snapshot_id="sealed-snapshot-1"),
    )


def owned_views(sibling_note="original"):
    plan=SegmentedViewport(
        view_id="actual-plan", page_number=11, view_type="floor_finish_plan",
        label="SOURCE FLOOR FINISHES PLAN", title_bbox=(10., 10., 100., 30.),
        bounding_box=(5., 5., 205., 205.),
        status="resolved", boundary_source="vector_frame", confidence=1.0,
        provenance={"source_owned_plan_view_proven": True, "frame_id": "d1i0"},
    )
    sibling=SegmentedViewport(
        view_id="other-schedule", page_number=11, view_type="schedule",
        label="SOURCE SCHEDULE", title_bbox=(310., 10., 400., 30.),
        bounding_box=(300., 5., 500., 205.),
        status="resolved", boundary_source="vector_frame", confidence=1.0,
        notes=[sibling_note], provenance={"frame_id": "d2i0"},
    )
    return tuple(_stamp_segment_page_viewports_product((plan,sibling)))


def classify(views, scopes):
    return classify_independent_f07_siblings(
        viewports=views, published=published(), page_no=11,
        original_w4_scope_ids=tuple(scopes),
    )


def test_original_source_sibling_scope_positive_requires_exact_existing_w4_id():
    views=owned_views()
    probe=classify(views,())
    expected,=probe["replayed_source_plan_scope_candidates"]
    report=classify(views,(expected,))
    assert report["status"] == "independent_source_f07_replay_exact_w4_scope_parity"
    assert report["original_w4_scope_id_parity_verified"] is True
    assert report["all_original_f07_view_count"] == 2
    assert report["all_source_owned_views"][0]["source_f07_view_id"] == "actual-plan"
    assert all(x["source_view_producer_seal_verified"] for x in report["all_source_owned_views"])
    assert report["room_or_wall_authority_granted"] is False
    assert report["diagnostic_only"] is True


def test_original_sibling_change_blocks_prior_producer_scope_with_no_rekey():
    before=classify(owned_views("original"),())
    exact,=before["replayed_source_plan_scope_candidates"]
    after=classify(owned_views("changed source note"),(exact,))
    assert after["original_w4_scope_id_parity_verified"] is False
    assert after["status"] == "independent_source_f07_replay_w4_scope_conflict_or_unavailable"
    assert after["replayed_source_plan_scope_candidates"] != [exact]
    assert after["original_w4_scopes_from_first_producer"] == [exact]
    assert not after["room_or_wall_authority_granted"]


def test_unsealed_or_mutated_original_view_does_not_gain_source_authority():
    unsealed=SegmentedViewport(
        view_id="user-drawn-plan", page_number=11, view_type="floor_finish_plan",
        label="PLAN", title_bbox=(0., 0., 10., 10.),
        bounding_box=(0., 0., 100., 100.), status="resolved",
        boundary_source="vector_frame", confidence=1.0,
        provenance={"source_owned_plan_view_proven": True},
    )
    report=classify((unsealed,),("fake",))
    assert report["status"] == "independent_f07_producer_unavailable_or_unsealed"
    assert report["original_w4_scope_id_parity_verified"] is False
    authentic=list(owned_views())
    authentic[0].notes.append("mutated after source seal")
    assert classify(authentic,())["status"] == "independent_f07_producer_unavailable_or_unsealed"


def test_duplicate_source_view_identifiers_refuse_ambiguous_owner():
    a,b=owned_views()
    duplicate=deepcopy(a)
    # deepcopy destroys private producer token; re-seal only an entirely
    # synthetic fixture to exercise duplicate producer-address rejection.
    c=SegmentedViewport(
        view_id=a.view_id, page_number=11, view_type="legend",
        label="LEGEND", title_bbox=(700.,10.,770.,30.),
        bounding_box=(650.,5.,850.,205.), status="resolved",
        boundary_source="vector_frame", confidence=1.0,
    )
    _stamp_segment_page_viewports_product((c,))
    report=classify((a,b,c),())
    assert report["status"] == "independent_f07_duplicate_or_invalid_view_identity"
    assert report["original_w4_scope_id_parity_verified"] is False


@pytest.mark.parametrize("scopes", [(), ("wrong-wall-scope",),
                                   ("wrong-wall-scope","other-scope")])
def test_no_original_w4_scope_or_different_scope_does_not_publish(scopes):
    report=classify(owned_views(),scopes)
    assert report["original_w4_scope_id_parity_verified"] is False
    assert report["room_or_wall_authority_granted"] is False


def test_nonplan_and_unsupported_view_not_elected_as_wall_scope():
    plan,sched=owned_views()
    plan.status="unsupported"  # invalidate stamped source record
    assert classify((plan,sched),())["status"] == "independent_f07_producer_unavailable_or_unsealed"
    # Genuine source-sealed schedule alone has no source physical PLAN owner.
    from pb_viewport_segmentation import _stamp_segment_page_viewports_product
    schedule=SegmentedViewport(
        view_id="schedule-alone", page_number=11, view_type="schedule",
        label="FINISH SCHEDULE", title_bbox=(5.,5.,50.,20.),
        bounding_box=(0.,0.,80.,100.), status="resolved",
        boundary_source="vector_frame", confidence=1.0,
    )
    _stamp_segment_page_viewports_product((schedule,))
    assert not classify((schedule,),())["replayed_source_plan_scope_candidates"]


def test_no_source_bytes_or_foreign_original_page_replay():
    with pytest.raises(ValueError,match="original_pdf_bytes_and_page_required"):
        replay_original_source_f07_first_gate("not bytes",page_no=11)
    with pytest.raises(ValueError,match="original_pdf_bytes_and_page_required"):
        replay_original_source_f07_first_gate(b"%PDF",page_no=0)
