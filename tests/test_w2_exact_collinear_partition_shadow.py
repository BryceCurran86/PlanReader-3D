"""Exact overlapping paint is an interval union, never a physical wall grant."""
from copy import deepcopy
import math

import pytest

from pb_wall_room_topology_collinear_partition_shadow import partition_exact_collinear_fragments as partition
from pb_wall_room_topology_primitive_lineage import LINEAGE_KEY, lineage_from_source_segments
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_junction_classifier import classify_junctions
from tests.test_w2_overlap_preservation_shadow import segment


def fragment(identity,a,b,**attributes):
    row=segment(identity,a,b);row.update(attributes)
    row[LINEAGE_KEY]=lineage_from_source_segments([row])
    return row


def spans(rows):
    return {(r['x1'],r['y1'],r['x2'],r['y2']):tuple(r[LINEAGE_KEY]['source_primitive_ids']) for r in rows}


def graph(rows,enabled=True):
    return build_wall_graph_for_viewport(rows,gap_snap_tolerance_pt=0.,exact_endpoint_index_shadow=True,
        exact_split_parent_lineage_shadow=True,preserve_overlapping_spans_shadow=True,
        immutable_exact_endpoints_shadow=True,partition_exact_collinear_overlaps_shadow=enabled)


def test_partial_overlap_partitions_with_all_actual_source_records_and_no_mutation():
    rows=[fragment('long',(0.,0.),(40.,0.),stroke=(0.,0.,0.)),
          fragment('contained',(20.,0.),(23.,0.),stroke=(1.,0.,0.))]
    before=deepcopy(rows);out=partition(rows)
    assert spans(out)=={(0.,0.,20.,0.):('long',),(20.,0.,23.,0.):('contained','long'),(23.,0.,40.,0.):('long',)}
    middle=out[1][LINEAGE_KEY]
    assert {r['id'] for r in middle['source_records']}=={'long','contained'}
    assert 'stroke' in middle['attribute_conflicts']
    assert out[1]['stroke'] is None
    assert partition(list(reversed(rows)))==out
    assert partition(rows)==out and rows==before
    out[1][LINEAGE_KEY]['source_records'][0]['id']='damaged-copy'
    assert rows==before


@pytest.mark.parametrize('transform',[
    lambda x,y:(x,y),lambda x,y:(100.-y,-50.+x),
    lambda x,y:(3*x-4*y+101.,4*x+3*y-207.),
    lambda x,y:(.125*x+17.,.125*y-31.),
    lambda x,y:(-x-y+8.,x-y-13.)])
def test_exact_similarity_transforms_input_order_and_reversed_source_directions(transform):
    a,b,c,d=[transform(x,0.) for x in (0.,20.,23.,40.)]
    rows=[fragment('long',a,d),fragment('contained',b,c)]
    expected={tuple(sorted(pair)) for pair in ((a,b),(b,c),(c,d))}
    ids=None
    for variant in (rows,list(reversed(rows)),[
            fragment('long',d,a),fragment('contained',c,b)]):
        out=partition(variant)
        assert {tuple(sorted(((r['x1'],r['y1']),(r['x2'],r['y2'])))) for r in out}==expected
        # Source records retain direction, so only identical inputs/order share IDs.
        if variant is rows:ids=[r['id'] for r in out]
        elif variant==list(reversed(rows)):assert [r['id'] for r in out]==ids


@pytest.mark.parametrize('other',[
    ((20.,math.nextafter(0.,math.inf)),(23.,math.nextafter(0.,math.inf))),
    ((20.,.001),(23.,.001)),((40.01,0.),(45.,0.)),
    ((20.,0.),(23.,.01)),((20.,-5.),(20.,5.))])
def test_offsets_one_ulp_real_gaps_and_noncollinear_crossings_are_not_union_evidence(other):
    rows=[fragment('long',(0.,0.),(40.,0.)),fragment('other',*other)]
    out=partition(rows)
    assert len(out)==2
    assert all(len(r[LINEAGE_KEY]['source_primitive_ids'])==1 for r in out)


def test_same_side_duplicates_opposite_sources_and_multiple_nested_spans_keep_every_parent():
    rows=[fragment('a',(0.,0.),(40.,0.)),fragment('b',(40.,0.),(0.,0.)),
          fragment('c',(5.,0.),(10.,0.)),fragment('d',(8.,0.),(30.,0.))]
    out=partition(rows)
    assert len(out)==5 and len({r['id'] for r in out})==5
    assert spans(out)[(8.,0.,10.,0.)]==('a','b','c','d')
    for row in rows:
        sid=row['id'];lo,hi=sorted((row['x1'],row['x2']))
        owned=[r for r in out if sid in r[LINEAGE_KEY]['source_primitive_ids']]
        assert sum(r['x2']-r['x1'] for r in owned)==hi-lo
        assert all(lo<=r['x1']<r['x2']<=hi for r in owned)


def test_segment_splitting_and_unrelated_viewport_expansion_preserve_source_coverage():
    a=fragment('long',(0.,0.),(40.,0.));b=fragment('short',(20.,0.),(23.,0.))
    split_a=deepcopy(a);split_a.update(id='derived-left',x2=10.)
    split_b=deepcopy(a);split_b.update(id='derived-right',x1=10.)
    remote=fragment('remote',(100.,100.),(120.,100.))
    for rows in ([a,b],[split_a,split_b,b],[remote,split_a,split_b,b]):
        out=partition(rows)
        owned=[r for r in out if 'long' in r[LINEAGE_KEY]['source_primitive_ids']]
        assert sum(r['x2']-r['x1'] for r in owned)==40.
        assert all(r['y1']==r['y2']==0. for r in owned)


def test_full_existing_w2_w3_path_resolves_redundant_branch_but_keeps_source_ancestry():
    rows=[segment('long',(-20.,0.),(23.,0.)),segment('contained',(0.,0.),(3.,0.)),
          segment('stem',(0.,-100.),(0.,0.))]
    before=deepcopy(rows)
    old=graph(rows,False);new=graph(rows)
    def junction(g):
        js,_=classify_junctions(g,document_id='source',page_id='1',viewport_id='shadow')
        return next(j for j in js if j.position_pt==(0.,0.))
    assert 'degenerate_angle_group_size_over_two' in junction(old).reason_codes
    assert junction(new).junction_type.value=='t_junction'
    assert any({'long','contained'}<=set(e[LINEAGE_KEY]['source_primitive_ids']) for e in new['edges'])
    assert graph(rows)==new and rows==before
    assert build_wall_graph_for_viewport(rows)==build_wall_graph_for_viewport(rows,partition_exact_collinear_overlaps_shadow=False)


def test_real_short_isolated_arm_is_still_ambiguous_after_partition():
    rows=[segment('a',(-100.,0.),(100.,0.)),segment('overtrace',(20.,0.),(23.,0.)),
          segment('short',(0.,0.),(0.,1.))]
    js,_=classify_junctions(graph(rows),document_id='source',page_id='1',viewport_id='shadow')
    assert 'short_isolated_arm_present' in next(j for j in js if j.position_pt==(0.,0.)).reason_codes


@pytest.mark.parametrize('bad',[1,None,'true',[]])
def test_explicit_shadow_only(bad):
    with pytest.raises(ValueError,match='explicit boolean'):
        build_wall_graph_for_viewport([],partition_exact_collinear_overlaps_shadow=bad)


@pytest.mark.parametrize('missing',['exact_endpoint_index_shadow','exact_split_parent_lineage_shadow',
    'preserve_overlapping_spans_shadow','immutable_exact_endpoints_shadow'])
def test_no_inexact_policy_can_consume_source_partition(missing):
    options=dict(gap_snap_tolerance_pt=0.,exact_endpoint_index_shadow=True,
        exact_split_parent_lineage_shadow=True,preserve_overlapping_spans_shadow=True,
        immutable_exact_endpoints_shadow=True,partition_exact_collinear_overlaps_shadow=True)
    options[missing]=False
    with pytest.raises(ValueError,match='requires all exact'):
        build_wall_graph_for_viewport([],**options)


@pytest.mark.parametrize('bad',[math.inf,-math.inf,math.nan])
def test_nonfinite_input_remains_unavailable(bad):
    with pytest.raises(ValueError,match='finite'):
        partition([fragment('bad',(bad,0.),(1.,0.))])


def test_unknown_lineage_degenerate_and_duplicate_fragment_addresses_are_rejected():
    a=fragment('a',(0.,0.),(10.,0.))
    for rows in ([a,a],[dict(a,x2=0.)],[segment('missing',(0.,0.),(1.,0.))]):
        with pytest.raises(ValueError):partition(rows)
