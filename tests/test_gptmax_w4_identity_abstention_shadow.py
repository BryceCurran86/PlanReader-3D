"""Actual constructor ambiguity stays negative; other chains remain observable."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

import pytest

from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport
from pb_wall_room_topology_wall_assembly import assemble_wall_candidates
from tools.diag_gptmax_full_foreground_run_source import _trace_sources
from scripts.gptmax_full_page_exact_endpoint_shadow import full_page_endpoint_source_report
from test_gptmax_exact_endpoint_flank_shadow import record
from test_gptmax_full_foreground_run_source import pdf


def collision_records():
    return (record('a',[0.,0.,10.,0.]),record('b',[10.,0.,4e-8,0.]),
        record('unrelated',[50.,50.,100.,50.]))


def trace(records,**kwargs):
    return _trace_sources(records,exact_endpoint_shadow=True,
        exact_endpoint_index_shadow=True,**kwargs)


def test_real_default_guard_still_raises_and_explicit_shadow_retains_actual_chain():
    records=collision_records(); before=deepcopy(records)
    with pytest.raises(ValueError,match='cannot start and end'): trace(records)
    out=trace(records,w4_identity_abstention_shadow=True)
    row,=out['all_w4_abstained_chain_rows']
    assert row['status']=='abstained'
    assert row['end_node_ids'][0]==row['end_node_ids'][1]
    assert row['raw_endpoint_node_indices'][0]!=row['raw_endpoint_node_indices'][1]
    assert row['raw_endpoint_positions_pt'][0]!=row['raw_endpoint_positions_pt'][1]
    assert row['candidate_membership_available'] is False
    assert row['source_parents_authenticated'] is False
    assert row['actual_owned_w3_fragment_rows'][0]['source_observation_ids']==['a','b']
    assert out['w4_candidate_universe_complete'] is False
    assert out['all_actual_w3_edges_have_w4_chain_disposition'] is True
    wall,=out['all_experimental_w4_candidates']
    assert wall['centerline_pt']==((50.,50.),(100.,50.))
    assert all(e['physical_host_authority'] is False for e in out['all_w2_edges'])
    assert records==before


def test_unrelated_valid_chain_is_byte_equal_to_default_and_no_mutation():
    records=(collision_records()[-1],)
    default=trace(records); out=trace(records,w4_identity_abstention_shadow=True)
    assert out['all_experimental_w4_candidates']==default['all_experimental_w4_candidates']
    assert out['all_w4_abstained_chain_rows']==[]
    assert out['w4_candidate_universe_complete'] is True
    assert out['structural_source_universe_complete'] is False
    assert out['opening_count_publication_allowed'] is False
    assert out['metric_quantity_publication_allowed'] is False


@pytest.mark.parametrize('turn',[0,1,2,3])
@pytest.mark.parametrize('scale',[1.,2.,4.])
def test_rotation_scale_translation_and_source_permutation_preserve_abstention(turn,scale):
    def point(p):
        x,y=p
        for _ in range(turn): x,y=-y,x
        return scale*x+90.,scale*y+70.
    records=tuple(replace(r,geometry=(*point(r.geometry[:2]),*point(r.geometry[2:])))
        for r in collision_records())
    out=trace(records,w4_identity_abstention_shadow=True)
    assert out==trace(tuple(reversed(records)),w4_identity_abstention_shadow=True)
    assert len(out['all_w4_abstained_chain_rows'])==1
    assert len(out['all_experimental_w4_candidates'])==1


def test_split_original_input_keeps_all_parents_without_creating_a_wall():
    records=(record('a-left',[0.,0.,5.,0.]),record('a-right',[5.,0.,10.,0.]),
        *collision_records()[1:])
    out=trace(records,w4_identity_abstention_shadow=True)
    row,=out['all_w4_abstained_chain_rows']
    assert {p for e in row['actual_owned_w3_fragment_rows'] for p in e['source_observation_ids']}=={
        'a-left','a-right','b'}
    assert row['host_publication_allowed'] is False
    assert row['physical_equivalence_proven'] is False


@pytest.mark.parametrize('bad',[None,0,1,'true',[],{}])
def test_truthy_or_nonboolean_diagnostic_configuration_rejected(bad):
    with pytest.raises(ValueError,match='explicit boolean'):
        trace(collision_records(),w4_identity_abstention_shadow=bad)
    with pytest.raises(ValueError,match='explicit boolean'):
        full_page_endpoint_source_report(b'foreign',page_id='1',expected_source_sha='a'*64,
            include_w4_identity_abstention_shadow=bad)


@pytest.mark.parametrize('flag,sink',[(True,None),(True,()),(True,[{}]),(False,[])])
def test_assembler_requires_fresh_explicit_output_contract(flag,sink):
    with pytest.raises(ValueError,match='output|shadow'):
        assemble_wall_candidates({},(),(),viewport_id='vp',
            identity_abstention_shadow=flag,abstained_chain_rows=sink)


def test_raw_graph_ancestry_is_not_claimed_authenticated_and_sink_is_detached():
    segments=[dict(id='a',kind='line',x1=0.,y1=0.,x2=10.,y2=0.),
        dict(id='b',kind='line',x1=10.,y1=0.,x2=4e-8,y2=0.)]
    graph=build_wall_graph_for_viewport(segments,gap_snap_tolerance_pt=0.,exact_endpoint_index_shadow=True)
    junctions,relationships=classify_junctions(graph,document_id='d',page_id='1',viewport_id='vp')
    before=deepcopy(graph); sink=[]
    walls,mapping=assemble_wall_candidates(graph,junctions,relationships,viewport_id='vp',
        identity_abstention_shadow=True,abstained_chain_rows=sink)
    assert walls==[] and mapping=={}
    assert sink[0]['source_parents_authenticated'] is False
    sink[0]['actual_owned_w3_fragment_rows'][0]['primitive_lineage']['source_primitive_ids'].append('foreign')
    assert graph==before


@pytest.mark.parametrize('damage',['foreign','missing','duplicate','geometry','drop'])
def test_foreign_contradictory_or_dropped_abstention_cannot_claim_complete_disposition(monkeypatch,damage):
    import tools.diag_gptmax_full_foreground_run_source as diag
    original=diag.assemble_wall_candidates
    def corrupted(*args,**kwargs):
        result=original(*args,**kwargs)
        sink=kwargs['abstained_chain_rows']; fragment=sink[0]['actual_owned_w3_fragment_rows'][0]
        if damage=='foreign': fragment['primitive_lineage']['source_primitive_ids']=['foreign']
        elif damage=='missing': fragment['primitive_lineage']=None
        elif damage=='duplicate': sink.append(deepcopy(sink[0]))
        elif damage=='geometry': fragment['w2_fragment_geometry_pt'][0]+=1
        else: sink.clear()
        return result
    monkeypatch.setattr(diag,'assemble_wall_candidates',corrupted)
    with pytest.raises(ValueError,match='fragment|partition|address collision'):
        trace(collision_records(),w4_identity_abstention_shadow=True)


def test_fresh_pdf_third_mode_preserves_original_controls_and_production():
    data=pdf(); kwargs=dict(page_id='1',expected_source_sha=sha256(data).hexdigest())
    default=full_page_endpoint_source_report(data,**kwargs)
    out=full_page_endpoint_source_report(data,**kwargs,include_w4_identity_abstention_shadow=True)
    third=out.pop('indexed_w4_identity_abstention_full_page_shadow')
    assert out==default
    assert third['identical_original_full_page_source_inputs'] is True
    assert third['partial_candidates_are_complete_physical_wall_universe'] is False
    assert third['source_graph']['host_publication_allowed'] is False


def test_multiple_collisions_have_separate_records_and_linear_edge_references():
    base=collision_records()
    other=tuple(replace(r,observation_id=r.observation_id+'-2',
        source_primitive_ref=r.source_primitive_ref+'-2',
        geometry=tuple(v+20. for v in r.geometry)) for r in base[:2])
    out=trace(base+other,w4_identity_abstention_shadow=True)
    rows=out['all_w4_abstained_chain_rows']
    assert len(rows)==2 and len({r['record_id'] for r in rows})==2
    known={r['record_id'] for r in rows}
    for edge in out['all_w2_edges']:
        assert 'w4_abstained_chain_rows' not in edge
        assert set(edge['w4_abstained_chain_record_ids'])<=known
        assert len(edge['w4_abstained_chain_record_ids'])<=1
    assert len(out['all_experimental_w4_candidates'])==1


def test_flank_reader_distinguishes_abstained_membership_from_known_empty_owner_set():
    from test_gptmax_full_foreground_flank_stages import _fixture, _row
    args=_fixture()
    edge=args[3]['all_w2_edges'][1]
    edge['w4_candidate_membership_available']=False
    edge['w4_abstained_chain_record_ids']=['actual-attempt']
    edge['experimental_w4_candidate_ids']=[]
    row=_row(args)
    assert row['observed_geometry_barrier']=='W4_CHAIN_NODE_IDENTITY_ABSTAINED'
    assert row['host_publication_allowed'] is False
    kept,=(e for e in row['actual_w2_edge_rows'] if e['edge_id']=='kept')
    assert kept['w4_candidate_membership_available'] is False
