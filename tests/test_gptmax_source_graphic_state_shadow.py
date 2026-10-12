"""Literal owned paint remains separate from topology and physical role."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

import pytest

from scripts import gptmax_source_graphic_state_shadow as shadow
from test_gptmax_exact_endpoint_flank_shadow import record
from test_gptmax_full_foreground_run_source import pdf


def fixture():
    records=(record('native',[0.,0.,10.,0.]),record('pixel',[10.,0.,20.,0.]))
    graph=shadow._trace_sources(records,exact_endpoint_shadow=True,exact_endpoint_index_shadow=True,
        w4_identity_abstention_shadow=True)
    segment=dict(id='raw-native',source_observation_id='native',document_id='original',page_id='1',
        x1=0.,y1=0.,x2=10.,y2=0.,stroke=(0.,0.,0.),width=.24,fill=None,
        width_present=True,stroke_present=True,fill_present=False)
    return graph,records,[segment]


def test_literal_source_state_is_not_a_sentinel_or_physical_wall_role():
    args=fixture();before=deepcopy(args)
    rows=shadow.join_graphic_state(*args)
    assert rows
    assert any('pixel' in r['missing_graphic_state_source_ids'] for r in rows)
    assert any(r['literal_source_graphic_state']['attribute_status']['width']=='agreed' for r in rows)
    assert all(r['structural_wall_role_proven'] is False and r['host_publication_allowed'] is False for r in rows)
    assert all(r['graphic_state_authentication_from_join_alone'] is False for r in rows)
    assert args==before


def test_competing_graphic_values_remain_conflict_without_first_selection():
    args=fixture(); other=dict(args[2][0],width=.48)
    rows=shadow.join_graphic_state(*args[:2],[*args[2],other])
    assert any(r['literal_source_graphic_state']['attribute_status']['width']=='conflict' for r in rows)
    assert rows==shadow.join_graphic_state(*args[:2],[other,*args[2]])


@pytest.mark.parametrize('damage',['foreign','geometry','document','page','parent','duplicate_edge'])
def test_foreign_or_contradictory_receipts_cannot_be_borrowed(damage):
    graph,records,segments=fixture()
    if damage=='foreign':segments[0]['source_observation_id']='foreign'
    elif damage=='geometry':segments[0]['x1']+=1
    elif damage=='document':segments[0]['document_id']='foreign'
    elif damage=='page':segments[0]['page_id']='2'
    elif damage=='parent':graph['all_w2_edges'][0]['source_observation_ids']=['foreign']
    else:graph['all_w2_edges'].append(deepcopy(graph['all_w2_edges'][0]))
    with pytest.raises(ValueError):shadow.join_graphic_state(graph,records,segments)


def test_fresh_pdf_source_graph_receipts_are_replayed_and_nonpublishing():
    b=pdf();r=shadow.original_graphic_state_report(b,page_id='1',expected_source_sha=sha256(b).hexdigest())
    assert r['original_source_reauthenticated'] is True and r['default_production_state_unchanged'] is True
    assert r==shadow.original_graphic_state_report(b,page_id='1',expected_source_sha=sha256(b).hexdigest())
    assert r['graphic_state_controls_topology_filtering'] is False
    assert r['structural_wall_role_proven'] is False and r['host_publication_allowed'] is False
    assert r['opening_count_publication_allowed'] is False and r['metric_quantity_publication_allowed'] is False
    assert r['benchmark_accuracy'] is None


@pytest.mark.parametrize('value',[b'foreign',{},None,'JSON'])
def test_original_pdf_cannot_be_replaced_by_caller_report(value):
    with pytest.raises(ValueError,match='SHA'):
        shadow.original_graphic_state_report(value,page_id='1',expected_source_sha='a'*64)


@pytest.mark.parametrize('turn',[0,1,2,3])
@pytest.mark.parametrize('scale',[1.,2.,4.])
def test_transformed_geometry_does_not_infer_or_scale_literal_paint(turn,scale):
    _,records,segments=fixture()
    def point(x,y):
        for _ in range(turn):x,y=-y,x
        return scale*x+90.,scale*y+70.
    records=tuple(replace(r,geometry=(*point(*r.geometry[:2]),*point(*r.geometry[2:]))) for r in records)
    segment=segments[0]
    segment['x1'],segment['y1'],segment['x2'],segment['y2']=records[0].geometry
    graph=shadow._trace_sources(records,exact_endpoint_shadow=True,exact_endpoint_index_shadow=True,
        w4_identity_abstention_shadow=True)
    rows=shadow.join_graphic_state(graph,records,segments)
    assert rows==shadow.join_graphic_state(graph,tuple(reversed(records)),segments)
    assert all(r['literal_source_graphic_state']['source_records'][0]['width']==.24 for r in rows)
    assert all(r['structural_wall_role_proven'] is False for r in rows)


def test_unrelated_owned_metadata_cannot_change_fragment_graphic_state():
    graph,records,segments=fixture();expected=shadow.join_graphic_state(graph,records,segments)
    extra=record('unrelated',[100.,100.,120.,100.])
    segment=dict(segments[0],source_observation_id='unrelated',x1=100.,y1=100.,x2=120.,y2=100.,width=99.)
    assert shadow.join_graphic_state(graph,(*records,extra),[*segments,segment])==expected


@pytest.mark.parametrize('bad',[None,0,1,'false',[]])
def test_coerced_presence_cannot_be_literal_source_evidence(bad):
    args=fixture();args[2][0]['width_present']=bad
    with pytest.raises(ValueError,match='explicit boolean'):shadow.join_graphic_state(*args)


def test_independent_changed_production_receipt_rejects_metadata_report(monkeypatch):
    original=shadow.source_face_report;calls=0
    def altered(*args,**kwargs):
        nonlocal calls
        calls+=1;r=original(*args,**kwargs)
        if calls==2:r['summary']['host_bindings']+=1
        return r
    monkeypatch.setattr(shadow,'source_face_report',altered)
    b=pdf()
    with pytest.raises(RuntimeError,match='production receipts'):
        shadow.original_graphic_state_report(b,page_id='1',expected_source_sha=sha256(b).hexdigest())


def test_real_parentless_fragment_is_retained_as_unknown_without_borrowing_graphic_state():
    graph,records,segments=fixture()
    graph['all_w2_edges'][0]['source_observation_ids']=[]
    row,=shadow.join_graphic_state(graph,records,segments)
    assert row['status']=='abstained'
    assert row['source_parent_ownership_available'] is False
    assert row['all_fragment_parents_have_graphic_state'] is False
    assert row['literal_source_graphic_state']['source_records']==[]
    assert set(row['literal_source_graphic_state']['attribute_status'].values())=={'unknown'}
    assert row['reason_codes']==['derived_fragment_source_parent_unavailable']


def test_ordinary_raster_descriptor_is_not_a_claim_of_available_vector_paint():
    graph,records,segments=fixture()
    unknown=dict(id='ordinary-raster',source_observation_id='pixel',document_id='original',page_id='1',
        x1=10.,y1=0.,x2=20.,y2=0.,width=0.,width_present=False,stroke=None,stroke_present=False,
        fill=None,fill_present=False,layer='',layer_present=False,dashes='',dashes_present=False,
        clip=None,clip_present=False)
    row,=shadow.join_graphic_state(graph,records,[*segments,unknown])
    assert row['all_fragment_parent_descriptors_available'] is True
    assert row['all_fragment_parents_have_graphic_state'] is False
    assert row['graphic_values_unavailable_source_ids']==['pixel']
    assert row['structural_wall_role_proven'] is False


def test_mutating_sidecar_cannot_change_actual_graph_or_owned_source_metadata():
    args=fixture();before=deepcopy(args)
    rows=shadow.join_graphic_state(*args)
    rows[0]['w2_fragment_geometry_pt'][0]+=100.
    rows[0]['literal_source_graphic_state']['source_records'][0]['width']=999.
    assert args==before
