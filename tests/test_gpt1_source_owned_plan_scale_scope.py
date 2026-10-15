"""A source-owned plan view cannot by itself measure a room or establish scale."""
from dataclasses import replace
from hashlib import sha256

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_scale_authority import (
    PHYSICAL_SCALE_BAR_UNAVAILABLE, PHYSICAL_SCALE_VIEWPORT_UNAVAILABLE,
    PhysicalScaleProducer, PhysicalScaleSelector,
)
from pb_viewport_segmentation import is_authoritative_derived_viewport, segment_source_page_viewports
from tests.test_source_owned_physical_plan_view import _sheet, _source


def _original(source, pub, *, viewport_id):
    return PhysicalScaleSelector(
        document_id=pub.revision.document_id,
        revision_id=pub.revision.revision_id,
        source_sha256=pub.revision.source_sha256,
        snapshot_id=pub.snapshot.snapshot_id,
        page_id="1",
        viewport_id=viewport_id,
    )


def test_real_producer_owned_plan_view_accepts_scope_but_not_forged_metric_scale():
    data=_sheet()
    source,pub=_source(data)
    original=source.published_snapshot_for_revision(pub.revision.revision_id)
    views=segment_source_page_viewports(
        source,revision_id=pub.revision.revision_id,page_id="1",
        physical_plan_view_shadow=True,
    )
    signed=[v for v in views if is_authoritative_derived_viewport(v)]
    assert len(signed)==1 and signed[0].view_type=="floor_plan"
    producer=PhysicalScaleProducer.from_source_visibility_producer(source)
    selector=_original(source,pub,viewport_id=signed[0].view_id)
    result=producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes==(PHYSICAL_SCALE_BAR_UNAVAILABLE,)
    assert result.evidence is None
    assert producer.publish_scope(selector)==result
    assert source.published_snapshot_for_revision(pub.revision.revision_id)==original


def test_original_unrecognized_name_cannot_select_producer_owned_scope():
    data=_sheet()
    source,pub=_source(data)
    producer=PhysicalScaleProducer.from_source_visibility_producer(source)
    for bad in ("view_p1_fake", "borrowed_drawing", ""):
        if not bad:
            with pytest.raises(ValueError):
                _original(source,pub,viewport_id=bad)
            continue
        result=producer.publish_scope(_original(source,pub,viewport_id=bad))
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert PHYSICAL_SCALE_VIEWPORT_UNAVAILABLE in result.reason_codes
        assert result.evidence is None


@pytest.mark.parametrize("kwargs", [
    {"no_frame":True},{"one_axis":True},{"second":True},
    {"hidden_role":True},{"role":"FRONT ELEVATION"},
])
def test_unbounded_competing_or_nonplan_source_never_passes_scale_scope(kwargs):
    source,pub=_source(_sheet(**kwargs))
    producer=PhysicalScaleProducer.from_source_visibility_producer(source)
    result=producer.publish_scope(_original(source,pub,viewport_id="unattested-viewport"))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert PHYSICAL_SCALE_VIEWPORT_UNAVAILABLE in result.reason_codes
    assert result.evidence is None


def test_exact_selector_revision_and_snapshot_guard_precede_view_source():
    source,pub=_source(_sheet())
    producer=PhysicalScaleProducer.from_source_visibility_producer(source)
    original=_original(source,pub,viewport_id="foreign-viewport")
    for changes in (
        {"source_sha256":"f"*64},
        {"snapshot_id":"foreign"},
        {"revision_id":"foreign"},
        {"document_id":"different-document"},
    ):
        result=producer.publish_scope(replace(original,**changes))
        assert result.status is EvidenceResolutionStatus.ABSTAINED
        assert result.evidence is None


def test_original_page_without_source_view_retains_old_page_graphic_scale_behavior():
    from tests.test_physical_scale_authority import _near_agreeing_bar_pdf
    payload,_=_near_agreeing_bar_pdf()
    source=_source_for_bar(payload)
    pub=source.published_snapshot_for_revision(next(iter(source._published_by_revision)))
    producer=PhysicalScaleProducer.from_source_visibility_producer(source)
    selector=PhysicalScaleSelector(
        document_id=pub.revision.document_id,revision_id=pub.revision.revision_id,
        source_sha256=pub.revision.source_sha256,snapshot_id=pub.snapshot.snapshot_id,
        page_id="1",
    )
    result=producer.publish_scope(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.points_per_mm>0


def _source_for_bar(payload):
    from pb_source_visibility_authority import SourceVisibilityProducer
    source=SourceVisibilityProducer(
        producer_method="gpt1-source-view-scale-bar-regression",producer_version="1",
    )
    source.ingest_native_pdf_bytes(
        document_id="scale-bar-without-plan",source_bytes=payload,
        source_locator="memory://original-bar.pdf",
    )
    return source
