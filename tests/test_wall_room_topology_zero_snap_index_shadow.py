"""Zero-index shadow must retain every historical graph/lineage decision."""
from copy import deepcopy
import json
import math
import random

import pytest

import pb_wall_room_topology_stage_a as stage
from pb_vector_geometry_v130 import snap_geometry


def seg(i, a, b):
    return dict(id=f's{i}', x1=a[0], y1=a[1], x2=b[0], y2=b[1],
        width=1., metadata={'owned': [i]}, primitive_lineage={'source_primitive_ids': [f'owner{i}']})


def exact(rows, **kwargs):
    before = deepcopy(rows)
    expected = snap_geometry(rows, tolerance_pt=0.)
    actual = stage._snap_geometry_indexed(rows, tolerance_pt=0.,
        exact_endpoint_index_shadow=True, **kwargs)
    assert actual == expected
    assert json.dumps(actual, sort_keys=True) == json.dumps(expected, sort_keys=True)
    assert rows == before
    return actual


@pytest.mark.parametrize('seed', range(40))
def test_full_graph_randomized_legacy_parity(seed):
    rng = random.Random(seed)
    pool = [(rng.choice([0.1, 0.3, -0., 1., -1., 0.5]), rng.randrange(-3, 4)/4) for _ in range(25)]
    rows = [seg(i, rng.choice(pool), rng.choice(pool) if i%3 else (rng.uniform(-50,50),rng.uniform(-50,50))) for i in range(90)]
    exact(rows)
    exact(list(reversed(rows)))


@pytest.mark.parametrize('value', [0.1,0.3,-0.1,-0.,1.,math.nextafter(1.,0.),math.nextafter(1.,2.),5e-324,-5e-324,1e308,-1e308])
def test_decimal_drift_signed_zero_subnormal_and_overflow(value):
    rows = [seg(i,(value,value),(i+10.,-i-10.)) for i in range(18)]
    actual = exact(rows)
    if value == 0.1:
        # Repeated arithmetic is intentionally preserved. Ideal coordinate
        # hashing would incorrectly collapse these historical distinct nodes.
        assert len({e['a'] for e in actual['edges']}) > 1


@pytest.mark.parametrize('scale', [0.25,1.,10.])
@pytest.mark.parametrize('rotation', [0,1,2,3])
def test_transform_split_and_unrelated_content_legacy_parity(scale,rotation):
    def transform(p):
        x,y=p
        for _ in range(rotation): x,y=-y,x
        return x*scale-1024.,y*scale+2048.
    points=[(0.,0.),(4.,0.),(8.,0.),(4.,-3.),(4.,3.)]
    lines=[(0,1),(1,2),(3,1),(1,4)]
    rows=[seg(i,transform(points[a]),transform(points[b])) for i,(a,b) in enumerate(lines)]
    exact(rows)
    extra=seg(99,transform((200.,200.)),transform((210.,200.)))
    for ordered in (rows+[extra],list(reversed(rows))+[extra]):
        exact(ordered)
    base=stage.build_wall_graph_for_viewport(rows,gap_snap_tolerance_pt=0.)
    indexed=stage.build_wall_graph_for_viewport(rows,gap_snap_tolerance_pt=0.,exact_endpoint_index_shadow=True)
    assert indexed == base
    assert indexed == stage.build_wall_graph_for_viewport(deepcopy(rows),gap_snap_tolerance_pt=0.,exact_endpoint_index_shadow=True)


def test_zero_audit_metadata_and_missing_duplicate_ids_stay_legacy():
    rows=[seg(0,(0.,0.),(2.,0.)),seg(0,(2.,0.),(3.,0.))]
    rows[0].pop('id')
    result=exact(rows,include_endpoint_assignments=True)
    assert 'endpoint_snap_assignments' not in result


@pytest.mark.parametrize('invalid',[None,1,0,'true',[],{}])
def test_opt_in_is_genuine_boolean(invalid):
    with pytest.raises(ValueError,match='explicit boolean'):
        stage._snap_geometry_indexed([],tolerance_pt=0.,exact_endpoint_index_shadow=invalid)
    with pytest.raises(ValueError,match='explicit boolean'):
        stage.build_wall_graph_for_viewport([],gap_snap_tolerance_pt=0.,exact_endpoint_index_shadow=invalid)


@pytest.mark.parametrize('tolerance',[-1.,0.1,2.5])
def test_opt_in_cannot_change_other_tolerances(tolerance):
    with pytest.raises(ValueError,match='zero tolerance'):
        stage._snap_geometry_indexed([],tolerance_pt=tolerance,exact_endpoint_index_shadow=True)
    with pytest.raises(ValueError,match='zero tolerance'):
        stage.build_wall_graph_for_viewport([],gap_snap_tolerance_pt=tolerance,exact_endpoint_index_shadow=True)


@pytest.mark.parametrize('value',[float('nan'),float('inf'),float('-inf')])
def test_nonfinite_zero_inputs_keep_actual_legacy_fallback(monkeypatch,value):
    rows=[seg(0,(value,0.),(2.,0.))]
    expected=object()
    def legacy(actual,tolerance_pt):
        assert actual is rows and tolerance_pt==0.
        return expected
    monkeypatch.setattr(stage,'snap_geometry',legacy)
    assert stage._snap_geometry_indexed(rows,tolerance_pt=0.,exact_endpoint_index_shadow=True) is expected


def test_no_opt_in_still_calls_unchanged_zero_legacy(monkeypatch):
    expected=object()
    monkeypatch.setattr(stage,'snap_geometry',lambda segments,tolerance_pt:expected)
    assert stage._snap_geometry_indexed([],tolerance_pt=0.) is expected
    assert stage._snap_geometry_indexed([],tolerance_pt=-1.) is expected


def test_sparse_lookup_work_is_linear_and_no_source_cap_is_tuned(monkeypatch):
    rows=[seg(i,(i*20.,0.),(i*20.+5.,0.)) for i in range(5000)]
    calls=0
    original=stage.math.hypot
    def counted(*args):
        nonlocal calls
        calls+=1
        return original(*args)
    monkeypatch.setattr(stage.math,'hypot',counted)
    graph=stage._snap_geometry_indexed(rows,tolerance_pt=0.,exact_endpoint_index_shadow=True)
    assert len(graph['nodes'])==10000 and len(graph['edges'])==5000
    assert calls<15000


def test_shadow_trace_reuses_same_w2_w3_w4_stack_without_authority():
    from test_gptmax_exact_endpoint_flank_shadow import record
    from tools.diag_gptmax_full_foreground_run_source import _trace_sources
    rows=(record('a',[0.,0.,4.,0.]),record('b',[4.5,0.,8.,0.]),record('tick',[2.,-2.,2.,2.]))
    legacy=_trace_sources(rows,exact_endpoint_shadow=True)
    indexed=_trace_sources(rows,exact_endpoint_shadow=True,exact_endpoint_index_shadow=True)
    assert legacy==indexed
    assert indexed['physical_equivalence_proven'] is False
    assert indexed['host_publication_allowed'] is False
    assert len(indexed['all_experimental_w4_candidates'])>1
    with pytest.raises(ValueError,match='requires exact endpoint'):
        _trace_sources(rows,exact_endpoint_index_shadow=True)
    with pytest.raises(ValueError,match='explicit boolean'):
        _trace_sources(rows,exact_endpoint_shadow=True,exact_endpoint_index_shadow=1)
