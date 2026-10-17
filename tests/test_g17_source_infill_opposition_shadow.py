"""Original opening proof owns opposing infill, never a structural wall grant."""
from copy import deepcopy
from dataclasses import replace

import fitz
import pytest

from pb_g17_source_infill_opposition_shadow import build_g17_source_infill_opposition_shadow
from tests.test_g17_plan_wall_scope_shadow import _prepare
from tests.test_source_owned_physical_plan_view import _sheet,_source
from tests.test_raster_framed_opening_g17_contract import _png,_sheet as raster


def _run(source,pub):
    return build_g17_source_infill_opposition_shadow(source,revision_id=pub.revision.revision_id,page_id="1")


def test_actual_framed_opening_produces_only_source_owned_opposing_atoms():
    source,pub=_prepare()
    before=deepcopy(source._producer._store.observations)
    result=_run(source,pub)
    assert result['source_viewport_ownership_id']
    assert result['original_infill_intervals']
    assert result['opposing_atoms']
    for atom in result['opposing_atoms']:
        assert atom['status']=='candidate' and atom['kind']=='symbol'
        assert atom['metadata']['polarity']=='opposing'
        assert atom['metadata']['source_snapshot_id']==pub.snapshot.snapshot_id
        assert atom['metadata']['source_observation_id']
        assert atom['metadata']['physical_opening_id']
        assert atom['metadata']['source_role']=='opening_infill'
    assert not any(result[k] for k in ('host_granted','structural_wall_role_granted',
        'physical_wall_equivalence_granted','metric_quantity_granted'))
    assert source.published_snapshot_for_revision(pub.revision.revision_id)==pub
    assert source._producer._store.observations==before


@pytest.mark.parametrize('frames',[0,1])
def test_bare_or_weak_gap_cannot_supply_an_infill_semantic_role(frames):
    with fitz.open(stream=_sheet(),filetype='pdf') as pdf:
        pdf[0].insert_image(fitz.Rect(60,260,340,330),stream=_png(raster(frame_lines=frames)),keep_proportion=False)
        data=pdf.tobytes()
    source,pub=_source(data)
    pub=source.augment_with_raster_opening_primitives(pub.revision.revision_id,page_ids=('1',))
    result=_run(source,pub)
    assert not result['original_infill_intervals'] and not result['opposing_atoms']
    assert not result['host_granted']


@pytest.mark.parametrize('options',[{}, {'dx':13.,'dy':29.},{'scale':1.5},
    {'reverse':True},{'split':True},{'unrelated':True},{'expanded':True}])
def test_replay_transform_and_unrelated_source_keep_opposition_and_default_graph(options):
    source,pub=_prepare(**options)
    a=_run(source,pub);b=_run(source,pub)
    assert a==b and a['opposing_atoms']
    assert a['baseline_w2_geometry_unchanged']
    assert a['ordinary_source_snapshot_unchanged']
    assert not a['host_granted']


@pytest.mark.parametrize('damage',['source','receipt','parent'])
def test_warmed_damaged_original_cannot_supply_a_new_role(damage):
    source,pub=_prepare();assert _run(source,pub)['opposing_atoms']
    store=source._producer._store
    key=(pub.snapshot.snapshot_id,pub.raster_opening_primitive_observation_ids[0])
    if damage=='source':store.source_bytes_by_revision[pub.revision.revision_id]=b'foreign'
    elif damage=='receipt':source._raster_opening_primitive_receipts.pop(key)
    else:store.observations.pop((key[0],store.observations[key].derivation_parent_ids[0]))
    with pytest.raises((ValueError,RuntimeError)):_run(source,pub)


def test_copied_report_and_foreign_revision_cannot_enter_source_role_builder():
    source,pub=_prepare();report=_run(source,pub)
    with pytest.raises(TypeError):_run(report,pub)
    with pytest.raises(ValueError):
        build_g17_source_infill_opposition_shadow(source,revision_id='foreign',page_id='1')


def test_partial_infill_overlap_does_not_relabel_an_entire_remote_edge():
    from pb_g17_plan_wall_scope_shadow import _graph
    r=_graph([dict(id='source-frame',kind='line',x1=0.,y1=0.,x2=100.,y2=0.)],
        root={'document_id':'d','page_id':'1'},scope_id='vp',tolerance=0.,
        infill_intervals=({'physical_opening_id':'opening','source_primitive_id':'source-frame','geometry':(20.,0.,30.,0.)},))
    assert not r['source_infill_edge_ids'] and not r['source_opposed_continuations']
    assert len(r['w4_records'])==1


@pytest.mark.parametrize('split',[False,True])
def test_owned_infill_blocks_only_cross_role_union_and_retains_every_edge(split):
    from pb_g17_plan_wall_scope_shadow import _graph
    segments=[dict(id=k,kind='line',x1=a,y1=b,x2=c,y2=d) for k,a,b,c,d in (
        ('left',0.,0.,10.,0.),('right',20.,0.,30.,0.),
        ('return-a',10.,0.,10.,8.),('return-b',20.,0.,20.,8.))]
    frame=[('frame',10.,20.)] if not split else [('frame-a',10.,15.),('frame-b',15.,20.)]
    segments += [dict(id=k,kind='line',x1=lo,y1=0.,x2=hi,y2=0.) for k,lo,hi in frame]
    intervals=tuple(dict(physical_opening_id='opening',source_primitive_id=k,geometry=(lo,0.,hi,0.)) for k,lo,hi in frame)
    before=deepcopy(segments)
    kwargs=dict(root={'document_id':'d','page_id':'1'},scope_id='vp',tolerance=0.)
    baseline=_graph(segments,**kwargs)
    guarded=_graph(segments,**kwargs,infill_intervals=intervals)
    assert guarded['source_opposed_continuations']
    assert guarded['w2_edges']==baseline['w2_edges']
    assert guarded['w3_relationships']==baseline['w3_relationships']
    assert len(guarded['w4_records'])>len(baseline['w4_records'])
    assert not any('left' in w['physical_identity']['source_primitive_ids']
        and 'right' in w['physical_identity']['source_primitive_ids'] for w in guarded['w4_records'])
    assert segments==before


@pytest.mark.parametrize('damage',['native_geometry','g17_pixel_receipt'])
def test_mid_read_native_or_raster_change_cannot_escape_source_transaction(monkeypatch,damage):
    import pb_g17_source_infill_opposition_shadow as module
    source,pub=_prepare();original=module._graph
    def mutate(*args,**kwargs):
        r=original(*args,**kwargs)
        if damage=='native_geometry':
            key=(pub.snapshot.snapshot_id,pub.visible_observation_ids[0])
            store=source._producer._store
            if key not in store.observations:
                key=(key[0], source._visibility_receipts[key])
            store.observations[key]=replace(store.observations[key],geometry=(1.,2.,3.,4.))
        else:
            key=(pub.snapshot.snapshot_id,pub.raster_opening_primitive_observation_ids[0])
            source._raster_opening_primitive_receipts[key]=replace(
                source._raster_opening_primitive_receipts[key],render_sha256='changed during read')
        return r
    monkeypatch.setattr(module,'_graph',mutate)
    with pytest.raises((RuntimeError,ValueError)):_run(source,pub)
