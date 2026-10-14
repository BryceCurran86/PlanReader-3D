"""Actual original source holes/overpaint, never repaired by filling pixels."""
from copy import deepcopy
from dataclasses import replace

import cv2
import fitz
import numpy as np
import pytest

from pb_g17_terminal_flank_source_shadow import build_g17_terminal_flank_source_shadow
from pb_source_visibility_authority import SourceVisibilityProducer
from tests.test_raster_framed_opening_g17_contract import (
    _sheet,_png,_selector,_corroborated_records,
)


def _prepare(*,hole='outer',turns=0,scale=1.,pad=0,split_image=False,overpaint=False,pages=1):
    gray=_sheet(frame_lines=2)
    if hole=='outer':
        gray[156:159,79:82]=255
    elif hole=='inner':
        gray[151:164,239:241]=255
    elif hole=='short':
        gray[156:159,235:238]=255
    gray=np.ascontiguousarray(np.rot90(gray,turns))
    gray=np.pad(gray,((pad,pad),(pad,pad)),constant_values=255)
    h,w=gray.shape
    with fitz.open() as pdf:
        for _ in range(pages):
            page=pdf.new_page(width=w*scale/2,height=h*scale/2)
            if split_image:
                mid=w//2
                page.insert_image(fitz.Rect(0,0,mid*scale/2,h*scale/2),stream=_png(gray[:,:mid]),keep_proportion=False)
                page.insert_image(fitz.Rect(mid*scale/2,0,w*scale/2,h*scale/2),stream=_png(gray[:,mid:]),keep_proportion=False)
            else:
                page.insert_image(page.rect,stream=_png(gray),keep_proportion=False)
            if overpaint:
                page.draw_rect(fitz.Rect(105,75,121,83),color=None,fill=(1,1,1),overlay=True)
        data=pdf.tobytes()
    source=SourceVisibilityProducer(producer_method='terminal-source-test',producer_version='1')
    page_ids=tuple(str(i+1) for i in range(pages))
    pub=source.ingest_native_pdf_bytes(document_id='terminal-source-test',source_bytes=data,
        source_locator='memory://terminal.pdf',page_ids=page_ids)
    pub=source.augment_with_raster_opening_primitives(pub.revision.revision_id,page_ids=page_ids)
    records=[r for r in _corroborated_records(source,pub) if r.page_id=='1']
    assert records
    record=max(records,key=lambda r:len(r.source_observation_ids))
    selector=_selector(pub,record.source_observation_ids[0])
    return source,pub,selector


def _run(source,selector):
    return build_g17_terminal_flank_source_shadow(source,selector)


def test_original_outer_hole_retains_negative_and_authenticates_only_terminal_source(monkeypatch):
    source,pub,selector=_prepare()
    before=deepcopy(source._producer._store.observations)
    def forbidden(*args,**kwargs):raise AssertionError('no source snapshot append')
    monkeypatch.setattr(source,'augment_with_raster_visible_segments',forbidden)
    monkeypatch.setattr(source,'augment_with_raster_opening_primitives',forbidden)
    r=_run(source,selector)
    positive=[f for f in r['flanks'] if f['terminal_source_atom'] is not None]
    assert positive
    for f in positive:
        assert not f['original_full_flank_source_supported']
        assert f['terminal_endpoint_span_pt']>=f['unchanged_minimum_line_length_pt']
        assert f['derived_terminal_paint_proof']['source_one_end_shadow_eligible']
        assert f['terminal_source_atom']['status']=='candidate'
        assert f['terminal_source_atom']['metadata']['source_observation_ids']
        assert f['derived_outer_end_cap_assumed'] is False
    assert source.published_snapshot_for_revision(pub.revision.revision_id)==pub
    assert source._producer._store.observations==before
    assert not any(r[k] for k in ('host_granted','structural_wall_role_granted','metric_quantity_granted','scope_complete'))


@pytest.mark.parametrize('hole,overpaint',[('inner',False),('outer',True)])
def test_unpainted_or_overpainted_jamb_cannot_skip_to_a_later_positive_run(hole,overpaint):
    source,pub,selector=_prepare(hole=hole,overpaint=overpaint)
    r=_run(source,selector)
    assert not any(f['terminal_source_atom'] for f in r['flanks'])


@pytest.mark.parametrize('turns,scale,pad,split',[(0,1.,0,False),(1,1.,0,False),
    (2,1.,0,False),(3,1.,0,False),(0,.75,0,False),(0,1.5,0,False),
    (0,1.,40,False),(0,1.,0,True)])
def test_transform_source_order_split_and_replay_keep_source_only_contract(turns,scale,pad,split):
    source,pub,selector=_prepare(turns=turns,scale=scale,pad=pad,split_image=split)
    a=_run(source,selector)
    source._producer._store.observations=dict(reversed(tuple(source._producer._store.observations.items())))
    assert _run(source,selector)==a
    assert any(f['terminal_source_atom'] for f in a['flanks'])
    assert not a['host_granted']


@pytest.mark.parametrize('damage',['bytes','parent','receipt','pixels','render','dpi'])
def test_warmed_original_source_damage_cannot_reissue_terminal(damage):
    source,pub,selector=_prepare();assert any(f['terminal_source_atom'] for f in _run(source,selector)['flanks'])
    store=source._producer._store;key=(selector.snapshot_id,selector.observation_id)
    if damage=='bytes':store.source_bytes_by_revision[selector.revision_id]=b'foreign'
    elif damage=='parent':store.observations.pop((key[0],store.observations[key].derivation_parent_ids[0]))
    elif damage=='receipt':source._raster_opening_primitive_receipts.pop(key)
    else:
        fields={'pixels':{'pixel_geometry':(1.,2.,3.,4.)},'render':{'render_sha256':'foreign'},'dpi':{'dpi':144}}[damage]
        source._raster_opening_primitive_receipts[key]=replace(source._raster_opening_primitive_receipts[key],**fields)
    with pytest.raises((RuntimeError,ValueError)):_run(source,selector)


@pytest.mark.parametrize('field',['document_id','revision_id','source_sha256','snapshot_id'])
def test_foreign_or_stale_selector_is_not_a_paint_proof(field):
    source,pub,selector=_prepare()
    with pytest.raises(ValueError):_run(source,replace(selector,**{field:'foreign'}))


def test_serialized_or_caller_supplied_geometry_is_not_a_source_producer():
    source,pub,selector=_prepare()
    with pytest.raises(TypeError):_run({'painted':True},selector)
    with pytest.raises(TypeError):_run(source,{'bbox':(0,0,100,100)})


def test_original_short_terminal_cannot_change_minimum_or_fill_the_hole():
    source,pub,selector=_prepare(hole='short')
    r=_run(source,selector)
    negatives=[f for f in r['flanks'] if not f['original_full_flank_source_supported']]
    assert negatives
    assert all(0<f['terminal_endpoint_span_pt']<f['unchanged_minimum_line_length_pt'] for f in negatives)
    assert all(f['terminal_source_atom'] is None for f in negatives)


@pytest.mark.parametrize('damage',['parent','receipt','bytes'])
def test_mid_read_source_damage_invalidates_complete_terminal_transaction(monkeypatch,damage):
    import pb_g17_terminal_flank_source_shadow as m
    source,pub,selector=_prepare();original=m._terminal
    def changed(*args,**kwargs):
        row=original(*args,**kwargs)
        if damage=='receipt':
            source._raster_opening_primitive_receipts.pop((selector.snapshot_id,selector.observation_id),None)
        elif damage=='parent':
            store=source._producer._store
            observation=store.observations[(selector.snapshot_id,selector.observation_id)]
            store.observations.pop((selector.snapshot_id,observation.derivation_parent_ids[0]),None)
        else:
            source._producer._store.source_bytes_by_revision[selector.revision_id]=b'changed'
        return row
    monkeypatch.setattr(m,'_terminal',changed)
    with pytest.raises((RuntimeError,ValueError)):_run(source,selector)


def test_page_inventory_reproves_every_opening_and_deterministic_replay():
    from pb_g17_terminal_flank_source_shadow import build_g17_terminal_flank_source_inventory_shadow as read
    source,pub,selector=_prepare()
    a=read(source,revision_id=pub.revision.revision_id,page_id='1')
    assert len(a['source_openings'])==1 and not a['scope_complete']
    assert a['source_openings'][0]==_run(source,selector)
    assert read(source,revision_id=pub.revision.revision_id,page_id='1')==a


@pytest.mark.parametrize('damage',['render','pixels','dpi'])
def test_other_page_original_receipt_damage_cannot_hide_behind_local_positive(damage):
    source,pub,selector=_prepare(pages=2)
    assert any(f['terminal_source_atom'] for f in _run(source,selector)['flanks'])
    store=source._producer._store
    oid=next(oid for oid in pub.raster_opening_primitive_observation_ids
        if store.observations[(pub.snapshot.snapshot_id,oid)].page_id=='2')
    key=(pub.snapshot.snapshot_id,oid)
    fields={'render':{'render_sha256':'foreign'},'pixels':{'pixel_geometry':(1.,2.,3.,4.)},'dpi':{'dpi':144}}[damage]
    source._raster_opening_primitive_receipts[key]=replace(source._raster_opening_primitive_receipts[key],**fields)
    with pytest.raises((ValueError,RuntimeError)):_run(source,selector)
