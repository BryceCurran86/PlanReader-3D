from copy import deepcopy

import pytest

from pb_g17_infill_endpoint_opposition_shadow import (
    _endpoint_infill_witnesses, build_g17_infill_endpoint_opposition_shadow,
)
from pb_g17_plan_wall_scope_shadow import _graph
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY
from tests.test_g17_plan_wall_scope_shadow import _prepare


def _edge(a=0.,b=0.,c=20.,d=0.,raw='frame'):
    return dict(id='e',x1=a,y1=b,x2=c,y2=d,**{LINEAGE_KEY:{'source_primitive_ids':[raw]}})


def _interval(lo=1.,hi=20.,owner='opening',raw='frame'):
    return dict(physical_opening_id=owner,source_primitive_id=raw,
        source_observation_id='original-'+raw,geometry=(lo,0.,hi,0.))


def test_only_owned_actual_endpoint_can_oppose_local_continuation():
    edge=_edge();interval=_interval();before=deepcopy((edge,interval))
    w=_endpoint_infill_witnesses(edge,(20.1,0.1),(interval,),tolerance=2.5)
    assert w and all(tuple(r['actual_edge_endpoint'])==(20.,0.) for r in w)
    assert not _endpoint_infill_witnesses(edge,(0.,0.),(interval,),tolerance=2.5)
    assert (edge,interval)==before


@pytest.mark.parametrize('edge,junction,intervals,tol',[
    (_edge(),(20.,0.),(_interval(lo=1.,hi=19.),),0.),
    (_edge(),(20.,0.),(_interval(lo=1.,hi=20.,raw='foreign'),),0.),
    (_edge(),(0.,0.),(_interval(lo=1.,hi=20.),),0.),
    (_edge(),(50.,0.),(_interval(),),2.5),
    (_edge(c=2.),(1.,0.),(_interval(lo=0.,hi=2.),),2.5),
    (_edge(),(20.,0.),(_interval(lo=20.,hi=30.),),0.),
])
def test_remote_middle_foreign_ambiguous_or_point_contact_cannot_select_a_port(edge,junction,intervals,tol):
    assert not _endpoint_infill_witnesses(edge,junction,intervals,tolerance=tol)


@pytest.mark.parametrize('reverse',[False,True])
def test_endpoint_partition_preserves_original_geometry_and_whole_edge_unknown(reverse):
    segments=[dict(id=k,kind='line',x1=a,y1=b,x2=c,y2=d) for k,a,b,c,d in (
        ('left',-10.,0.,0.,0.),('frame',0.,0.,20.,0.),('right',20.,0.,30.,0.),
        ('left-return',0.,0.,0.,8.),('right-return',20.,0.,20.,8.))]
    if reverse:segments.reverse()
    kwargs=dict(root={'document_id':'d','page_id':'1'},scope_id='vp',tolerance=0.,
        infill_intervals=(_interval(),))
    old=_graph(segments,**kwargs)
    new=_graph(segments,**kwargs,infill_endpoint_opposition=True)
    assert not old['source_opposed_continuations']
    assert new['source_endpoint_opposed_continuations']
    assert new['w2_edges']==old['w2_edges'] and new['w3_relationships']==old['w3_relationships']
    assert not new['source_infill_edge_ids']
    assert len(new['w4_records'])>len(old['w4_records'])
    # The uncovered first endpoint still joins the original left chain.
    assert any({'left','frame'}<=set(r['physical_identity']['source_primitive_ids']) for r in new['w4_records'])
    assert not any({'frame','right'}<=set(r['physical_identity']['source_primitive_ids']) for r in new['w4_records'])


@pytest.mark.parametrize('options',[{}, {'dx':13.,'dy':29.},{'scale':1.5},
    {'reverse':True},{'split':True},{'unrelated':True},{'expanded':True}])
def test_actual_source_replay_transform_and_ownership(options):
    source,pub=_prepare(**options)
    before=deepcopy(source._producer._store.observations)
    def run():return build_g17_infill_endpoint_opposition_shadow(source,revision_id=pub.revision.revision_id,page_id='1')
    a=run();assert run()==a
    assert a['source_viewport_ownership_id'] and a['original_infill_intervals']
    assert a['baseline_w2_geometry_unchanged'] and not a['host_granted']
    assert source._producer._store.observations==before


def test_foreign_report_or_revision_cannot_supply_endpoint_roles():
    source,pub=_prepare()
    with pytest.raises(TypeError):
        build_g17_infill_endpoint_opposition_shadow({'opposed':True},revision_id=pub.revision.revision_id,page_id='1')
    with pytest.raises(ValueError):
        build_g17_infill_endpoint_opposition_shadow(source,revision_id='foreign',page_id='1')


@pytest.mark.parametrize('turns,scale,dx,dy',[(0,1.,0.,0.),(1,1.,0.,0.),
    (2,1.,0.,0.),(3,1.,0.,0.),(1,1.5,13.,29.)])
def test_actual_endpoint_relation_is_rotation_translation_and_scale_invariant(turns,scale,dx,dy):
    def point(x,y):
        for _ in range(turns):x,y=-y,x
        return (x*scale+dx,y*scale+dy)
    a,b=point(0.,0.),point(20.,0.)
    lo,hi=point(1.,0.),point(20.,0.)
    edge=_edge(*a,*b);interval=dict(_interval(),geometry=(*lo,*hi))
    w=_endpoint_infill_witnesses(edge,b,(interval,),tolerance=0.)
    assert w and w[0]['actual_edge_endpoint']==b
    assert not _endpoint_infill_witnesses(edge,a,(interval,),tolerance=0.)


@pytest.mark.parametrize('damage',['native','pixel'])
def test_mid_read_source_damage_aborts_endpoint_partition(monkeypatch,damage):
    from dataclasses import replace
    import pb_g17_source_infill_opposition_shadow as module
    source,pub=_prepare();original=module._graph
    def changed(*args,**kwargs):
        r=original(*args,**kwargs)
        if damage=='native':
            key=(pub.snapshot.snapshot_id,pub.visible_observation_ids[0]);store=source._producer._store
            if key not in store.observations:
                key=(key[0], source._visibility_receipts[key])
            store.observations[key]=replace(store.observations[key],geometry=(1.,2.,3.,4.))
        else:
            key=(pub.snapshot.snapshot_id,pub.raster_opening_primitive_observation_ids[0])
            source._raster_opening_primitive_receipts[key]=replace(
                source._raster_opening_primitive_receipts[key],pixel_geometry=(1.,2.,3.,4.))
        return r
    monkeypatch.setattr(module,'_graph',changed)
    with pytest.raises((RuntimeError,ValueError)):
        build_g17_infill_endpoint_opposition_shadow(source,revision_id=pub.revision.revision_id,page_id='1')
