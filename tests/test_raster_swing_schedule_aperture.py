"""Real source-owned raster swing tags, schedules and metric authority gates."""
from dataclasses import replace
import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_opening_height_authority import OpeningHeightProducer, OpeningHeightSelector
from pb_schedule_opening_instance_binding_authority import ScheduleOpeningInstanceBindingProducer
from pb_schedule_row_height_authority import ScheduleRowHeightProducer, ScheduleRowHeightSelector
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from test_raster_door_swing_g17_contract import _png, _sheet
from test_schedule_opening_instance_binding_authority_v2_regressions import _insert_schedule


def _fixture(*, tags=(('D1',150.),), rows=None, partial=False, scale=1., dx=0.,dy=0.):
    doc = fitz.open()
    page = doc.new_page(width=(340.+dx)*scale,height=(200.+dy)*scale)
    page.insert_image(fitz.Rect(dx*scale,dy*scale,(320.+dx)*scale,(180.+dy)*scale),
        stream=_png(_sheet(leaf=True,arc=True)),keep_proportion=False)
    for text,x in tags:
        page.insert_text(((x+dx)*scale,(80.+dy)*scale),text,fontsize=4.*scale)
    schedule = doc.new_page(width=700.,height=650.)
    _insert_schedule(schedule, rows or (('MARK','ROWDTH-MM','ROHT-MM'),('D1','820','2100')))
    source = SourceVisibilityProducer(producer_method='swing-schedule-test',producer_version='1')
    published = source.ingest_native_pdf_bytes(document_id='swing-schedule-test',source_bytes=doc.tobytes(),
        source_locator='memory://swing-schedule-test.pdf',page_ids=('1',) if partial else None)
    doc.close()
    published = source.augment_with_raster_opening_primitives(published.revision.revision_id,page_ids=('1',))
    physical = source.physical_opening_authority()
    selectors = {}
    for oid in sorted(published.raster_opening_primitive_observation_ids):
        selector = ObservationSelector(document_id=published.revision.document_id,revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,snapshot_id=published.snapshot.snapshot_id,observation_id=oid)
        opening = physical.prove_existence(selector).existence_record
        if opening is not None and opening.structural_pattern=='raster_door_swing_wall_band_interruption':
            selectors.setdefault(opening.record_id,(selector,opening))
    assert len(selectors)==1
    selector,opening = next(iter(selectors.values()))
    producer = ScheduleOpeningInstanceBindingProducer.from_source_visibility_producer(source)
    return source,producer,selector,opening


def _bind(producer, selector):
    return producer.publish_scope(opening_selector=selector,decision_scope_id='swing-schedule:page-1')


@pytest.mark.parametrize('scale,dx,dy', [(1.,0.,0.),(1.,17.,9.),(.7,7.,11.),(1.4,0.,0.)])
def test_exact_swing_tag_and_rough_opening_schedule_prove_height_without_defaults(scale,dx,dy):
    source,producer,selector,opening = _fixture(scale=scale,dx=dx,dy=dy)
    result = _bind(producer,selector)
    assert result.status is Status.CORROBORATED
    assert result.record.tag_mark=='D1'
    assert result.record.schedule_row_dimension_basis=='rough_opening'
    assert result.record.schedule_row_width_mm==820
    assert result.record.schedule_row_height_mm==2100
    assert result.record.schedule_row_count is None
    assert not result.record.schedule_row_count_explicit
    rows = ScheduleRowHeightProducer.from_source_visibility_producer(source)
    record = result.record
    row = rows.publish_scope(ScheduleRowHeightSelector(document_id=record.document_id,revision_id=record.revision_id,
        source_sha256=record.source_sha256,snapshot_id=record.snapshot_id,schedule_page_id=record.schedule_page_id,
        schedule_row_observation_ids=record.schedule_row_observation_ids))
    assert row.status is Status.CORROBORATED
    heights = OpeningHeightProducer.from_authorities(source,producer.authority(),rows.authority())
    height_selector = OpeningHeightSelector(document_id=selector.document_id,revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,snapshot_id=selector.snapshot_id,decision_scope_id='swing-schedule:page-1',
        opening_record_id=opening.record_id)
    height = heights.publish_scope(height_selector)
    assert height.status is Status.CORROBORATED and height.evidence.height_mm==2100
    assert heights.publish_scope(height_selector)==height
    assert _bind(producer,selector)==result


@pytest.mark.parametrize('kwargs,reason,status', [
    ({'tags':()},'schedule_opening_instance_binding_no_contained_tag',Status.ABSTAINED),
    ({'tags':(('D1',70.),)},'schedule_opening_instance_binding_no_contained_tag',Status.ABSTAINED),
    ({'tags':(('D1',150.),('D2',170.))},'schedule_opening_instance_binding_ambiguous_tags',Status.CONFLICT),
    ({'rows':(('MARK','WIDTH','HEIGHT'),('D9','820','2100'))},'schedule_opening_instance_binding_no_matching_row',Status.ABSTAINED),
    ({'rows':(('MARK','WIDTH','HEIGHT'),('D1','820','2100'),('D1','820','2100'))},'schedule_opening_instance_binding_ambiguous_rows',Status.CONFLICT),
    ({'partial':True},'schedule_opening_instance_binding_partial_source_coverage',Status.ABSTAINED),
])
def test_missing_conflicting_or_partial_source_cannot_bind_swing(kwargs,reason,status):
    _source,producer,selector,_opening = _fixture(**kwargs)
    result = _bind(producer,selector)
    assert result.status is status and reason in result.reason_codes and result.record is None


def test_stale_source_selector_cannot_bind_current_swing():
    _source,producer,selector,_opening = _fixture()
    result = _bind(producer,replace(selector,source_sha256='0'*64))
    assert result.status is Status.ABSTAINED and result.record is None


def test_generic_schedule_numbers_do_not_prove_metric_opening_height():
    source,producer,selector,_opening = _fixture(rows=(('MARK','WIDTH','HEIGHT'),('D1','820','2100')))
    result = _bind(producer,selector)
    assert result.status is Status.CORROBORATED
    assert not result.record.schedule_row_dimension_basis
    record=result.record
    rows=ScheduleRowHeightProducer.from_source_visibility_producer(source)
    row=rows.publish_scope(ScheduleRowHeightSelector(document_id=record.document_id,revision_id=record.revision_id,
        source_sha256=record.source_sha256,snapshot_id=record.snapshot_id,schedule_page_id=record.schedule_page_id,
        schedule_row_observation_ids=record.schedule_row_observation_ids))
    assert row.status is Status.ABSTAINED and row.evidence is None
