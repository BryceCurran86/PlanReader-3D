"""Exact live producer F.07 drawing scope is not physical room measurement."""
from dataclasses import replace
from hashlib import sha256
from types import SimpleNamespace

import pytest

from pb_live_physical_net_wall_integration import (
    _unique_authenticated_containing_floor_plan_viewport as unique_plan,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_scale_authority import (
    PhysicalScaleProducer, PhysicalScaleSelector, PHYSICAL_SCALE_BAR_UNAVAILABLE,
)
from pb_viewport_segmentation import (
    is_authoritative_derived_viewport, segment_source_page_viewports,
)
from tests.test_source_owned_physical_plan_view import _sheet, _source


def _room(data, published, **changes):
    values=dict(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=sha256(data).hexdigest(),
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        viewport_id=None,
        polygon_pdf_pts=((120.,120.),(150.,120.),(150.,150.),(120.,150.)),
    )
    return SimpleNamespace(**(values | changes))


def _binding(data, *, room_changes=None):
    source,published=_source(data)
    room=_room(data,published,**(room_changes or {}))
    bound=unique_plan(
        source=source,scope_rooms=(room,),page_id="1",
        snapshot_id=room.snapshot_id,
    )
    return source,published,room,bound


def test_same_live_source_owned_floor_plan_can_reach_scale_scope_without_m2():
    data=_sheet()
    source,published,room,bound=_binding(data)
    views=segment_source_page_viewports(
        source,revision_id=published.revision.revision_id,
        page_id="1",physical_plan_view_shadow=True,
    )
    signed=[v for v in views if is_authoritative_derived_viewport(v)]
    assert len(signed)==1 and signed[0].view_type=="floor_plan"
    assert bound==(signed[0].view_id,(50.,50.,350.,350.))

    prior=source.published_snapshot_for_revision(published.revision.revision_id)
    scale=PhysicalScaleProducer.from_source_visibility_producer(source).publish_scope(
        PhysicalScaleSelector(
            document_id=room.document_id,
            revision_id=room.revision_id,
            source_sha256=room.source_sha256,
            snapshot_id=room.snapshot_id,
            page_id=room.page_id,
            viewport_id=bound[0],
        )
    )
    assert scale.status is EvidenceResolutionStatus.ABSTAINED
    assert scale.reason_codes==(PHYSICAL_SCALE_BAR_UNAVAILABLE,)
    assert scale.evidence is None
    assert source.published_snapshot_for_revision(published.revision.revision_id)==prior


@pytest.mark.parametrize("change",[
    {"snapshot_id":"foreign-source-root"},
    {"revision_id":"foreign-revision"},
    {"source_sha256":"f"*64},
    {"document_id":"other-document"},
    {"page_id":"2"},
    {"viewport_id":"borrowed-page-view"},
    {"polygon_pdf_pts":((120.,120.),(150.,120.),(450.,150.))},
    {"polygon_pdf_pts":((120.,120.),(150.,120.))},
    {"polygon_pdf_pts":((True,120.),(150.,120.),(150.,150.))},
])
def test_foreign_room_identity_and_off_view_geometry_never_borrow_plan(change):
    data=_sheet()
    source,published,room,bound=_binding(data,room_changes=change)
    assert bound is None


@pytest.mark.parametrize("config",[
    {"no_frame":True},{"no_dimensions":True},{"one_axis":True},
    {"second":True},{"hidden_role":True},{"role":"FRONT ELEVATION"},
])
def test_original_unproven_competing_source_views_never_resolve_measurement_scope(config):
    _,_,_,bound=_binding(_sheet(**config))
    assert bound is None


def test_same_source_plan_cannot_authorize_foreign_second_room():
    data=_sheet()
    source,pub=_source(data)
    first=_room(data,pub)
    other=_room(data,pub,source_sha256="0"*64)
    assert unique_plan(source=source,scope_rooms=(first,other),
                       page_id="1",snapshot_id=first.snapshot_id) is None


def test_existing_source_pdf_hash_tampering_cannot_be_translated_to_scope():
    data=_sheet()
    source,pub=_source(data)
    source._producer._store.source_bytes_by_revision[pub.revision.revision_id]=b"not original pdf"
    with pytest.raises(RuntimeError, match="producer_integrity_failure|immutable_bytes_unavailable|source_plan"):
        unique_plan(source=source,scope_rooms=(_room(data,pub),),
                    page_id="1",snapshot_id=pub.snapshot.snapshot_id)


def test_same_root_plan_scope_is_input_order_invariant_deterministic_and_nonmutating():
    data = _sheet()
    source, published = _source(data)
    rooms = (
        _room(data, published),
        _room(
            data, published,
            polygon_pdf_pts=((190., 190.), (210., 190.), (210., 210.), (190., 210.)),
        ),
    )
    source_before = source.published_snapshot_for_revision(published.revision.revision_id)
    expected = unique_plan(
        source=source, scope_rooms=rooms, page_id="1",
        snapshot_id=published.snapshot.snapshot_id,
    )
    assert expected is not None
    for order in (rooms, tuple(reversed(rooms)), rooms):
        assert unique_plan(
            source=source, scope_rooms=order, page_id="1",
            snapshot_id=published.snapshot.snapshot_id,
        ) == expected
        assert source.published_snapshot_for_revision(
            published.revision.revision_id
        ) == source_before


def test_existing_unowned_legacy_w4_selector_does_not_borrow_f07_fallback(monkeypatch):
    # An authenticated old W4 selector that does not own this room must
    # block fallback; absence and source disagreement are different claims.
    from pb_live_physical_net_wall_integration import PhysicalWallCandidateProducer

    class LegacyAuthority:
        def selectors_for_authenticated_viewports(self, **_kwargs):
            return (object(),)

        def resolve_scope(self, _selector):
            return SimpleNamespace(
                status=EvidenceResolutionStatus.ABSTAINED,
                viewport_id="old-unowned-plan",
                viewport_bbox=None,
            )

    class LegacyProducer:
        def authority(self):
            return LegacyAuthority()

    monkeypatch.setattr(
        PhysicalWallCandidateProducer, "from_authenticated_viewports",
        staticmethod(lambda *_args, **_kwargs: LegacyProducer()),
    )
    data = _sheet()
    source, published = _source(data)
    room = _room(data, published)
    assert unique_plan(
        source=source, scope_rooms=(room,), page_id="1",
        snapshot_id=published.snapshot.snapshot_id,
    ) is None
