"""Exact endpoint experiments retain source geometry without host authority."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import SourceObservationRecord
from scripts import gptmax_exact_endpoint_flank_shadow as shadow
from tools.diag_gptmax_full_foreground_run_source import _trace_sources
from test_gptmax_full_foreground_flank_stages import _fixture
from test_gptmax_full_foreground_run_source import pdf


def record(key, line):
    return SourceObservationRecord(observation_id=key, document_id='original',
        revision_id='revision', source_sha256='a'*64, source_partition_id='page',
        page_id='1', viewport_id=None, observation_kind='raster_full_foreground_run_shadow',
        source_primitive_ref=key, raw_text='', geometry=tuple(line), origin_kind='raster',
        derivation_parent_ids=(), producer_method='synthetic', producer_version='1',
        producer_generation=1, snapshot_id='snapshot', observation_payload_sha256='b'*64,
        status=EvidenceResolutionStatus.CORROBORATED)


def fixture():
    joined, original, required, _ = _fixture()
    joined['opening_rows'][0]['flanks'][0]['pixel_run_candidates'][0]['source_line_pt'] = [19.,20.,20.,20.]
    records = (record('original-pixel', [19.,20.,20.,20.]),
        record('continuation', [16.,20.,19.,20.]))
    return joined, original, required, records


def run(args):
    return shadow.compare_local_flank_graphs(*args)[0]


def sources(mode):
    return mode['opening_rows'][0]['flanks'][0]['source_run_rows'][0]


def test_real_w2_short_source_collapse_is_separate_from_exact_shadow_survival():
    args = fixture()
    before = deepcopy(args)
    result = run(args)
    default = sources(result['default_snap_local_shadow'])
    exact = sources(result['exact_endpoint_local_shadow'])
    assert default['observed_geometry_barrier'] == 'W2_NO_SURVIVING_REQUIRED_FLANK_FRAGMENT'
    assert default['actual_snap_collapsed_rows']
    assert exact['actual_w2_edge_rows']
    assert any(e['w3_retained'] for e in exact['actual_w2_edge_rows'])
    assert exact['observed_geometry_barrier'] == 'W4_LOCAL_CANDIDATES_AWAIT_WALL_ROLE_AND_EQUIVALENCE'
    assert result['identical_local_source_inputs_for_both_modes'] is True
    for mode in ('default_snap_local_shadow','exact_endpoint_local_shadow'):
        graph = result[mode]['source_graph']
        assert graph['input_source_count'] == 2
        assert graph['host_publication_allowed'] is False
        assert graph['physical_equivalence_proven'] is False
        assert all(e['physical_host_authority'] is False for e in graph['all_w2_edges'])
    assert args == before
    control = _trace_sources(args[3])
    control['scope_authority'] = 'local source bounds experiment only; no authenticated floor-plan viewport'
    assert control == result['default_snap_local_shadow']['source_graph']


def test_parallel_faces_and_annotation_lookalikes_remain_separate_candidates():
    args = fixture()
    args = (*args[:3], (*args[3], record('parallel', [19.,20.5,20.,20.5]),
        record('tick', [19.5,19.,19.5,21.])))
    local, _ = shadow._local_records(args[3], ['original-pixel','parallel'])
    graph = _trace_sources(local, exact_endpoint_shadow=True)
    assert len(graph['all_experimental_w4_candidates']) > 1
    assert graph['host_publication_allowed'] is False
    assert graph['physical_equivalence_proven'] is False
    assert {p['source_observation_id'] for p in graph['source_parent_census']} == {
        'original-pixel','continuation','parallel','tick'}
    assert all(w['physical_host_authority'] is False for w in graph['all_experimental_w4_candidates'])


def test_exact_joins_do_not_bridge_a_real_unpainted_gap():
    records = (record('left',[0.,0.,4.,0.]), record('right',[4.5,0.,8.,0.]))
    graph = _trace_sources(records, exact_endpoint_shadow=True)
    assert len(graph['all_experimental_w4_candidates']) == 2
    assert all(len(w['w2_edge_ids']) == 1 for w in graph['all_experimental_w4_candidates'])
    assert not graph['host_publication_allowed']


def test_source_scope_keeps_every_intersecting_full_line_without_clipping():
    records = fixture()[3] + (record('crossing',[19.5,-100.,19.5,100.]),
        record('outside',[200.,200.,201.,200.]))
    local, bounds = shadow._local_records(records, ['original-pixel'])
    assert bounds == (19.,20.,20.,20.)
    assert {r.observation_id for r in local} == {'original-pixel','continuation','crossing'}
    assert next(r.geometry for r in local if r.observation_id == 'crossing') == (19.5,-100.,19.5,100.)


def test_order_unrelated_source_and_repeat_run_invariance():
    args = fixture()
    expected = run(args)
    reversed_args = (*deepcopy(args[:3]), tuple(reversed(args[3])) +
        (record('unrelated', [100.,100.,101.,100.]),))
    assert run(reversed_args) == expected == run(args)


@pytest.mark.parametrize('turn', [0,1,2,3])
@pytest.mark.parametrize('scale', [1.,2.,4.])
def test_rotation_translation_scale_retain_exact_source_geometry_without_promotion(turn, scale):
    args = fixture()
    def rotate(p):
        x,y = p
        for _ in range(turn): x,y = -y,x
        return x,y
    def point(p):
        x,y = rotate(p)
        return [scale*x+90, scale*y+70]
    basis = args[1]['opening_rows'][0]['original_aperture_coordinate_basis']
    basis['origin'] = point(basis['origin'])
    for field in ('axis','normal'): basis[field] = rotate(basis[field])
    for field in ('length','thickness'): basis[field] *= scale
    flank = args[2]['opening_rows'][0]['flanks'][0]
    for field in ('axis_span_pt','normal_span_pt'): flank[field] = [scale*v for v in flank[field]]
    flank['end_axis_coordinate_pt'] *= scale
    pixel = args[0]['opening_rows'][0]['flanks'][0]['pixel_run_candidates'][0]
    pixel['source_line_pt'] = point(pixel['source_line_pt'][:2]) + point(pixel['source_line_pt'][2:])
    transformed = tuple(replace(r,geometry=tuple(point(r.geometry[:2])+point(r.geometry[2:]))) for r in args[3])
    result = run((*args[:3], transformed))
    exact = sources(result['exact_endpoint_local_shadow'])
    assert any(e['w3_retained'] for e in exact['actual_w2_edge_rows'])
    assert exact['host_publication_allowed'] is False
    assert exact['physical_equivalence_proven'] is False
    assert result['local_scope_is_authenticated_floor_plan_viewport'] is False


def test_source_split_at_real_intersection_retains_parent_without_inventing_geometry():
    args = fixture()
    exact = _trace_sources((*args[3],record('split-tick',[19.5,19.,19.5,21.])),exact_endpoint_shadow=True)
    rows = [e for e in exact['all_w2_edges'] if 'original-pixel' in e['source_observation_ids']]
    assert len(rows) == 2
    assert sorted(tuple(e['w2_fragment_geometry_pt']) for e in rows) == [
        (16.,20.,19.5,20.), (19.5,20.,20.,20.)]
    assert not exact['host_publication_allowed']


@pytest.mark.parametrize('bad',[True, '1', float('nan'), float('inf'), 10**400])
def test_bad_original_geometry_never_reaches_either_graph(bad):
    records = (record('original-pixel',[bad,20.,20.,20.]),)
    with pytest.raises(ValueError): shadow._local_records(records,['original-pixel'])


@pytest.mark.parametrize('damage',['duplicate','foreign_sha','foreign_page','missing_seed','duplicate_seed','empty'])
def test_foreign_or_incomplete_source_scope_fails_closed(damage):
    records, seeds = fixture()[3], ['original-pixel']
    if damage == 'duplicate': records += (records[0],)
    elif damage == 'foreign_sha': records = (records[0],replace(records[1],source_sha256='c'*64))
    elif damage == 'foreign_page': records = (records[0],replace(records[1],page_id='2'))
    elif damage == 'missing_seed': seeds = ['foreign']
    elif damage == 'duplicate_seed': seeds *= 2
    else: records = ()
    with pytest.raises(ValueError): shadow._local_records(records,seeds)


def test_original_twenty_thousand_input_cap_is_not_a_derived_fragment_limit(monkeypatch):
    monkeypatch.setattr(shadow,'MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS',1)
    with pytest.raises(ValueError,match='safety bound'):
        shadow._local_records(fixture()[3],['original-pixel'])


@pytest.mark.parametrize('mode',[None,0,1,'true'])
def test_exact_mode_cannot_be_enabled_by_truthy_configuration(mode):
    with pytest.raises(ValueError,match='boolean'):
        _trace_sources(fixture()[3],exact_endpoint_shadow=mode)


def test_public_reader_rejects_foreign_pdf_before_any_source_ingest():
    with pytest.raises(ValueError,match='SHA'):
        shadow.exact_endpoint_source_report(b'foreign',page_id='1',expected_source_sha='a'*64)


def test_public_reader_reauthenticates_real_pdf_and_retains_default_receipts():
    data = pdf()
    result = shadow.exact_endpoint_source_report(data,page_id='1',expected_source_sha=sha256(data).hexdigest())
    assert result['original_source_reauthenticated'] is True
    assert result['default_production_state_unchanged'] is True
    assert result['source_primitive_safety_cap'] == 20000
    assert result['host_publication_allowed'] is False
    assert result['opening_count_publication_allowed'] is False
    assert result['metric_quantity_publication_allowed'] is False
    assert result['benchmark_accuracy'] is None


def test_independent_post_shadow_production_replay_must_remain_identical(monkeypatch):
    data = pdf()
    original = shadow.original_raster_host_ancestry_census
    calls = 0
    def changed(*args,**kwargs):
        nonlocal calls
        calls += 1
        result = original(*args,**kwargs)
        if calls == 2: result['source_original_host_count'] += 1
        return result
    monkeypatch.setattr(shadow,'original_raster_host_ancestry_census',changed)
    with pytest.raises(RuntimeError,match='production source state'):
        shadow.exact_endpoint_source_report(data,page_id='1',expected_source_sha=sha256(data).hexdigest())


def pixel_fragments(*, gap=False, discarded=False, offset=False):
    rows = []
    for i in range(8):
        if gap and i==3: continue
        rows.append(dict(edge_id=f'edge-{i}', source_observation_ids=['pixel'],
            w2_fragment_geometry_pt=[16.+i/2,20.+(1. if offset else 0.),16.+(i+1)/2,20.+(1. if offset else 0.)],
            w3_retained=not(discarded and i==3),
            matches_original_required_flank_geometry=False))
    return dict(source_observation_id='pixel',source_line_pt=[16.,20.,20.,20.],
        actual_w2_edge_rows=rows)


def test_complete_owned_interval_coverage_does_not_require_one_large_fragment():
    pixel = pixel_fragments()
    before = deepcopy(pixel)
    coverage = shadow.source_interval_coverage(pixel)
    assert coverage['complete_actual_w2_source_span_coverage'] is True
    assert coverage['complete_actual_w3_retained_source_span_coverage'] is True
    assert len(coverage['exact_owned_fragment_intervals']) == 8
    assert coverage['w2_uncovered_source_intervals_pt'] == []
    assert coverage['combined_graph_edge_created'] is False
    assert coverage['physical_wall_authority'] is False
    assert coverage['host_publication_allowed'] is False
    assert pixel == before
    pixel['actual_w2_edge_rows'].reverse()
    assert shadow.source_interval_coverage(pixel)==coverage


def test_real_source_interval_gap_is_never_closed_by_adjacent_or_duplicate_spans():
    pixel = pixel_fragments(gap=True)
    pixel['actual_w2_edge_rows'].append({**pixel['actual_w2_edge_rows'][0],'edge_id':'duplicate-geometry'})
    coverage = shadow.source_interval_coverage(pixel)
    assert coverage['w2_uncovered_source_intervals_pt']==[[17.5,18.]]
    assert coverage['w3_uncovered_source_intervals_pt']==[[17.5,18.]]
    assert coverage['complete_actual_w2_source_span_coverage'] is False


def test_w3_discarded_fragment_never_transfers_coverage_to_retained_sibling():
    coverage = shadow.source_interval_coverage(pixel_fragments(discarded=True))
    assert coverage['complete_actual_w2_source_span_coverage'] is True
    assert coverage['complete_actual_w3_retained_source_span_coverage'] is False
    assert coverage['w3_uncovered_source_intervals_pt']==[[17.5,18.]]


def test_parallel_offset_or_remote_owned_edges_cannot_fill_local_source_interval():
    pixel = pixel_fragments(offset=True)
    pixel['actual_w2_edge_rows'].append(dict(edge_id='remote',source_observation_ids=['pixel'],
        w2_fragment_geometry_pt=[200.,20.,201.,20.],w3_retained=True))
    coverage = shadow.source_interval_coverage(pixel)
    assert coverage['w2_uncovered_source_intervals_pt']==[[16.,20.]]
    assert not coverage['exact_owned_fragment_intervals']


@pytest.mark.parametrize('turn',[0,1,2,3])
def test_rotated_translated_scaled_source_interval_coverage_keeps_all_receipt_addresses(turn):
    pixel = pixel_fragments()
    def line(coords):
        result=[]
        for x,y in (coords[:2],coords[2:]):
            for _ in range(turn): x,y = -y,x
            result.extend([x*4.+99.,y*4.+77.])
        return result
    pixel['source_line_pt']=line(pixel['source_line_pt'])
    for edge in pixel['actual_w2_edge_rows']:
        edge['w2_fragment_geometry_pt']=line(edge['w2_fragment_geometry_pt'])
    coverage = shadow.source_interval_coverage(pixel)
    assert coverage['complete_actual_w2_source_span_coverage'] is True
    assert coverage['complete_actual_w3_retained_source_span_coverage'] is True
    assert {r['edge_id'] for r in coverage['exact_owned_fragment_intervals']}=={f'edge-{i}' for i in range(8)}


@pytest.mark.parametrize('damage',['foreign_parent','duplicate_address','truthy_retained','nonfinite','non_axis_source'])
def test_forged_source_interval_facts_fail_closed(damage):
    pixel = pixel_fragments()
    if damage=='foreign_parent': pixel['actual_w2_edge_rows'][0]['source_observation_ids']=['foreign']
    elif damage=='duplicate_address': pixel['actual_w2_edge_rows'][1]['edge_id']='edge-0'
    elif damage=='truthy_retained': pixel['actual_w2_edge_rows'][0]['w3_retained']=1
    elif damage=='nonfinite': pixel['actual_w2_edge_rows'][0]['w2_fragment_geometry_pt'][0]=float('nan')
    else: pixel['source_line_pt']=[16.,19.,20.,20.]
    with pytest.raises(ValueError): shadow.source_interval_coverage(pixel)


def test_single_fragment_predicate_failure_is_not_misreported_as_absent_source_geometry():
    _, original, required, _ = _fixture()
    pixel = pixel_fragments()
    rows=[dict(opening_identity_id='original-opening',flanks=[dict(role='left',source_run_rows=[pixel])])]
    shadow.annotate_source_span_coverage(rows,original,required)
    assert pixel['original_source_span_meets_required_flank_geometry'] is True
    assert pixel['single_fragment_contact_failure_with_complete_retained_source_span'] is True
    assert pixel['exact_source_span_coverage']['combined_graph_edge_created'] is False
    pixel['actual_w2_edge_rows'][0]['w3_retained']=False
    shadow.annotate_source_span_coverage(rows,original,required)
    assert pixel['single_fragment_contact_failure_with_complete_retained_source_span'] is False
