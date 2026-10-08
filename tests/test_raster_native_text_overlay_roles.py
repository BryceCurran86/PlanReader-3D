"""Pixel ownership, not a nearby word, excludes raster copies of text."""
from copy import deepcopy
from dataclasses import replace

import cv2
import fitz
import numpy as np
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer, RASTER_PDF_VISIBLE_SEGMENT
from test_raster_door_swing_g17_contract import _png


def _source(*, dx=0, dy=0, scale=1, rotation=0, text='90', mixed=None, duplicate=False, unrelated=False):
    doc=fitz.open();page=doc.new_page(width=300*scale,height=160*scale)
    image=np.full((320,600),255,np.uint8)
    if mixed=='image':
        cv2.rectangle(image,(204+2*dx,111+2*dy),(241+2*dx,114+2*dy),0,-1)
    page.insert_image(page.rect,stream=_png(image),keep_proportion=False)
    if mixed=='occluded_vector':
        page.draw_line(((115+dx)*scale,(56.5+dy)*scale),
            ((118+dx)*scale,(56.5+dy)*scale),width=.2*scale)
    page.insert_text(((100+dx)*scale,(70+dy)*scale),text,fontsize=20*scale)
    if duplicate:
        page.insert_text(((100+dx)*scale,(70+dy)*scale),text,fontsize=20*scale)
    if mixed=='vector':
        page.draw_line(((98+dx)*scale,(64+dy)*scale),((120+dx)*scale,(64+dy)*scale),width=2*scale)
    if unrelated:
        page.insert_text((240*scale,140*scale),'unrelated',fontsize=8*scale)
    page.set_rotation(rotation)
    data=doc.tobytes();doc.close()
    source=SourceVisibilityProducer(producer_method='text-pixel-test',producer_version='1')
    published=source.ingest_native_pdf_bytes(document_id='text-pixel-test',source_bytes=data,
        source_locator='memory://text-pixel-test.pdf',page_ids=('1',))
    published=source.augment_with_raster_visible_segments(published.revision.revision_id,page_ids=('1',))
    rows=[r for (snapshot,_),r in source._producer._store.observations.items()
        if snapshot==published.snapshot.snapshot_id and r.observation_kind==RASTER_PDF_VISIBLE_SEGMENT]
    assert rows
    selector=ObservationSelector(document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,observation_id=rows[0].observation_id)
    return source,published,selector,tuple(r.source_primitive_ref.removeprefix('visible:') for r in rows)


def test_all_primitives_have_only_candidate_opposition_and_no_measurement():
    source,published,selector,primitives=_source()
    before=deepcopy(source._producer._store.observations)
    result=source.raster_text_overlay_evidence(selector,source_primitive_ids=primitives)
    assert len(result)==1
    atom=result[0]
    assert atom.status is Status.CANDIDATE and atom.kind=='symbol'
    assert atom.metadata['polarity']=='opposing'
    assert set(atom.metadata['source_primitive_ids'])==set(primitives)
    assert atom.metadata['all_source_primitives_covered'] is True
    assert atom.normalized_value is None and atom.unit is None and atom.raw_text==''
    assert result==source.raster_text_overlay_evidence(selector,source_primitive_ids=tuple(reversed(primitives)))
    assert source._producer._store.observations==before
    assert source.physical_opening_authority().raster_text_overlay_evidence(
        selector,source_primitive_ids=primitives)==result
    assert published.snapshot.snapshot_id==selector.snapshot_id


@pytest.mark.parametrize('kwargs',[dict(dx=25,dy=20),dict(scale=2),dict(rotation=90),
    dict(rotation=180),dict(rotation=270),dict(unrelated=True),dict(text='88'),dict(text='BO')])
def test_source_role_transforms_and_unrelated_content_preserve_complete_ownership(kwargs):
    source,_,selector,primitives=_source(**kwargs)
    assert source.raster_text_overlay_evidence(selector,source_primitive_ids=primitives)


@pytest.mark.parametrize('kwargs',[dict(mixed='image'),dict(mixed='vector'),
    dict(mixed='occluded_vector'),dict(duplicate=True)])
def test_competing_or_mixed_paint_cannot_prove_complete_text_role(kwargs):
    source,_,selector,primitives=_source(**kwargs)
    assert source.raster_text_overlay_evidence(selector,source_primitive_ids=primitives)==()


def test_graphics_layer_rejects_native_paint_hidden_by_identical_text_pixels():
    source,_,selector,primitives=_source(mixed='occluded_vector')
    assert source.raster_text_overlay_evidence(selector,source_primitive_ids=primitives)==()
    (full,_images,text_pixels,graphics),_hashes,_rotation=next(
        iter(source._raster_text_overlay_page_cache.values()))
    assert np.array_equal(full,text_pixels)
    assert np.any(graphics<255)


@pytest.mark.parametrize('defect',['geometry','visibility','text','text_page','source_bytes','stale'])
def test_cached_pixels_cannot_bypass_current_source_authentication(defect):
    source,published,selector,primitives=_source()
    assert source.raster_text_overlay_evidence(selector,source_primitive_ids=primitives)
    if defect=='geometry':
        key=(selector.snapshot_id,selector.observation_id)
        source._producer._store.observations[key]=replace(source._producer._store.observations[key],geometry=(0.,0.,10.,0.))
    elif defect=='visibility':
        del source._raster_visibility_receipts[(selector.snapshot_id,selector.observation_id)]
    elif defect=='text':
        source._text_integrity_receipts.clear()
    elif defect=='text_page':
        key=(selector.snapshot_id,published.text_observation_ids[0])
        source._producer._store.observations[key]=replace(source._producer._store.observations[key],page_id='2')
    elif defect=='source_bytes':
        source._producer._store.source_bytes_by_revision[selector.revision_id]=b'tampered'
    else:
        doc=fitz.open();doc.new_page();data=doc.tobytes();doc.close()
        source.ingest_native_pdf_bytes(document_id=selector.document_id,source_bytes=data,source_locator='memory://changed.pdf')
    with pytest.raises(RuntimeError):
        source.raster_text_overlay_evidence(selector,source_primitive_ids=primitives)


def test_missing_or_mixed_primitives_cannot_be_silently_ignored():
    source,_,selector,primitives=_source()
    for selected in ((),(*primitives,'native_segment:other'),(*primitives,'raster_segment:missing')):
        assert source.raster_text_overlay_evidence(selector,source_primitive_ids=selected)==()


def test_source_renderer_layer_views_reject_mixed_views_and_caller_clips():
    source,_,selector,_=_source()
    kwargs=dict(document_id=selector.document_id,revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,snapshot_id=selector.snapshot_id,page_id='1')
    with pytest.raises(ValueError,match='mutually exclusive'):
        source._producer.render_native_page_png(**kwargs,images_only=True,text_only=True)
    with pytest.raises(ValueError,match='text_only render cannot'):
        source._producer.render_native_page_png(**kwargs,text_only=True,clip_pt=(0,0,20,20))
    with pytest.raises(ValueError,match='mutually exclusive'):
        source._producer.render_native_page_png(**kwargs,text_only=True,graphics_only=True)
    with pytest.raises(ValueError,match='graphics_only render cannot'):
        source._producer.render_native_page_png(**kwargs,graphics_only=True,clip_pt=(0,0,20,20))
