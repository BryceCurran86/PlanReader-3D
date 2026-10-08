"""Source geometry cannot be invented from snapped paths or parent extents."""
from dataclasses import asdict, replace
from types import SimpleNamespace
import math

import pytest

from pb_physical_wall_candidate_authority import PhysicalWallSourceEdgeFragment
from pb_raster_source_wall_frame_projection import source_edge_axis_projection


def _fixture():
    geometry = SimpleNamespace(origin=(20., 5.), axis=(1., 0.), normal=(0., 1.), thickness=4.)
    wall = SimpleNamespace(is_curved=False, reason_codes=(),
        centerline_pts=((-10., 5.), (0., 5.), (2., 5.3), (12., 5.), (15., 5.)))
    identity = SimpleNamespace(usable=True, edge_ids=('a', 'b'), source_primitive_ids=('source',))
    fragments = (PhysicalWallSourceEdgeFragment('a', (-10., 5., 0., 5.), ('source',)),
        PhysicalWallSourceEdgeFragment('b', (0., 5., 15., 5.), ('source',)))
    record = SimpleNamespace(wall_candidate=wall, physical_identity=identity,
        source_edge_fragments=fragments)
    return record, geometry, {'source': (-30., 5., 90., 5.)}


def test_source_extent_is_owned_fragments_and_not_remote_parent_extent():
    record, geometry, lines = _fixture()
    before = repr((record, geometry, lines))
    assert source_edge_axis_projection(record, geometry, lines) == (-30., -5., 0.)
    assert repr((record, geometry, lines)) == before
    assert source_edge_axis_projection(record, geometry, lines) == (-30., -5., 0.)


@pytest.mark.parametrize('kind', ['missing_edge', 'duplicate_edge', 'foreign_edge',
    'unknown_ancestor', 'unowned_ancestor', 'perpendicular_ancestor', 'offset_ancestor',
    'short_ancestor', 'bent_edge', 'gap', 'opposing_offsets', 'curved', 'unusable',
    'non_simple', 'backtrack', 'outside_band', 'remote_chain', 'nan'])
def test_unproven_source_or_chain_keeps_projection_unknown(kind):
    record, geometry, lines = _fixture()
    a, b = record.source_edge_fragments
    if kind == 'missing_edge': record.source_edge_fragments = (a,)
    elif kind == 'duplicate_edge': record.source_edge_fragments = (a, b, b)
    elif kind == 'foreign_edge': record.source_edge_fragments = (a, replace(b, edge_id='foreign'))
    elif kind == 'unknown_ancestor': lines = {}
    elif kind == 'unowned_ancestor': record.physical_identity.source_primitive_ids = ('other',)
    elif kind == 'perpendicular_ancestor': lines['source'] = (0., -30., 0., 90.)
    elif kind == 'offset_ancestor': lines['source'] = (-30., 5.1, 90., 5.1)
    elif kind == 'short_ancestor': lines['source'] = (-10., 5., 14., 5.)
    elif kind == 'bent_edge': record.source_edge_fragments = (a, replace(b, geometry=(0., 5., 15., 5.1)))
    elif kind == 'gap': record.source_edge_fragments = (a, replace(b, geometry=(.01, 5., 15., 5.)))
    elif kind == 'opposing_offsets':
        record.source_edge_fragments = (a, replace(b, geometry=(0., 5.1, 15., 5.1), source_primitive_ids=('other',)))
        record.physical_identity.source_primitive_ids = ('source', 'other')
        lines['other'] = (0., 5.1, 15., 5.1)
    elif kind == 'curved': record.wall_candidate.is_curved = True
    elif kind == 'unusable': record.physical_identity.usable = False
    elif kind == 'non_simple': record.wall_candidate.reason_codes = ('non_simple_chain_topology_fallback_ordering',)
    elif kind == 'backtrack': record.wall_candidate.centerline_pts = ((-10., 5.), (14., 5.), (12., 5.), (15., 5.))
    elif kind == 'outside_band': record.wall_candidate.centerline_pts = ((-10., 5.), (0., 7.1), (15., 5.))
    elif kind == 'remote_chain': record.wall_candidate.centerline_pts = ((-30., 5.), (90., 5.))
    elif kind == 'nan': record.source_edge_fragments = (a, replace(b, geometry=(0., 5., math.nan, 5.)))
    assert source_edge_axis_projection(record, geometry, lines) is None


@pytest.mark.parametrize('theta,scale,dx,dy', [(0., 1., 33., -17.), (.8, 1., 0., 0.),
    (2.3, .7, 80., 95.), (1.57, 2.1, -32., 16.)])
def test_rigid_transform_scale_order_and_split_invariance(theta, scale, dx, dy):
    record, geometry, lines = _fixture()
    c, s = math.cos(theta), math.sin(theta)
    def point(p): return (scale*(p[0]*c-p[1]*s)+dx, scale*(p[0]*s+p[1]*c)+dy)
    def line(v): return (*point(v[:2]), *point(v[2:]))
    geometry.origin = point(geometry.origin)
    geometry.axis = (c, s)
    geometry.normal = (-s, c)
    geometry.thickness *= scale
    record.wall_candidate.centerline_pts = tuple(point(p) for p in record.wall_candidate.centerline_pts)
    record.source_edge_fragments = tuple(replace(f, geometry=line(f.geometry)) for f in reversed(record.source_edge_fragments))
    lines = {k: line(v) for k,v in lines.items()}
    expected = (-30.*scale, -5.*scale, 0.)
    assert source_edge_axis_projection(record, geometry, lines) == pytest.approx(expected)
    a, b = record.source_edge_fragments
    midpoint = tuple((a.geometry[i]+a.geometry[i+2])/2 for i in (0,1))
    record.source_edge_fragments = (b, replace(a, edge_id='split1', geometry=(*a.geometry[:2], *midpoint)),
        replace(a, edge_id='split2', geometry=(*midpoint, *a.geometry[2:])))
    record.physical_identity.edge_ids = ('a', 'split1', 'split2')
    assert source_edge_axis_projection(record, geometry, lines) == pytest.approx(expected)


def test_real_wall_producer_retains_complete_edge_facts_without_mutation():
    from test_raster_connected_host_frame import _fixture, _scope
    _source, _composition, producer, bound = _fixture()
    scope = _scope(producer, bound)
    before = asdict(scope)
    for record in scope.records:
        assert {f.edge_id for f in record.source_edge_fragments} == set(record.physical_identity.edge_ids)
        assert {p for f in record.source_edge_fragments for p in f.source_primitive_ids} == set(record.physical_identity.source_primitive_ids)
    assert asdict(_scope(producer, bound)) == before


def _snapped_scope(producer, bound):
    from test_raster_connected_host_frame import _scope
    import pb_opening_host_binding_authority as host
    scope = _scope(producer, bound)
    common = set(bound[0][3].member_wall_candidate_ids) & set(bound[1][3].member_wall_candidate_ids)
    assert len(common) == 1
    record = next(r for r in scope.records if r.wall_candidate_id in common)
    start, end = record.wall_candidate.centerline_pts[0], record.wall_candidate.centerline_pts[-1]
    length = math.dist(start, end)
    axis = tuple((end[i]-start[i])/length for i in (0,1))
    normal = (-axis[1], axis[0])
    def point(u,n=0.): return tuple(start[i]+axis[i]*u+normal[i]*n for i in (0,1))
    points = (start, point(length*.3), point(length*.3+1., .3), point(length*.6), end)
    snapped = replace(record, wall_candidate=replace(record.wall_candidate, centerline_pts=points))
    geometry = host._opening_geometry(producer._opening, bound[0][1])
    assert host._candidate_axis_data(snapped, geometry) is None
    records = tuple(snapped if r.wall_candidate_id == record.wall_candidate_id else r for r in scope.records)
    return replace(scope, records=records), snapped, geometry


def test_sealed_source_projection_proves_snapped_frames_and_retains_visible_receipts(monkeypatch):
    from test_raster_connected_host_frame import _fixture, _publish
    from pb_migration_contracts import EvidenceResolutionStatus as Status
    _source, _composition, producer, bound = _fixture()
    expected = _publish(producer, bound)
    from pb_opening_host_frame_authority import OpeningHostFrameProducer
    producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=producer._opening, host_binding_authority=producer._host,
        physical_wall_candidate_authority=producer._walls)
    scope, record, geometry = _snapped_scope(producer, bound)
    before = asdict(scope)
    source = producer._raster_source_projection(record=record, opening=bound[0][1],
        geometry=geometry, wall_scope=scope)
    assert source is not None and source[1]
    monkeypatch.setattr(producer._walls, 'resolve_scope', lambda _s: scope)
    results = _publish(producer, bound)
    assert all(r.status is Status.CORROBORATED for r in results)
    for actual, baseline in zip(results, expected):
        assert actual.evidence.whole_wall_frame_id == baseline.evidence.whole_wall_frame_id
        assert actual.evidence.whole_wall_length_pt == baseline.evidence.whole_wall_length_pt
        assert set(source[1]) <= set(actual.evidence.source_observation_ids)
    assert _publish(producer, bound) == results
    assert asdict(scope) == before


@pytest.mark.parametrize('damage', ['missing_fragment', 'foreign_ancestor', 'bent_source_edge',
    'missing_receipt', 'wrong_dpi', 'wrong_source_geometry'])
def test_frame_cannot_promote_damaged_source_projection(monkeypatch, damage):
    from test_raster_connected_host_frame import _fixture, _publish
    from pb_migration_contracts import EvidenceResolutionStatus as Status
    source, _composition, producer, bound = _fixture()
    scope, record, geometry = _snapped_scope(producer, bound)
    if damage in {'missing_fragment','foreign_ancestor','bent_source_edge'}:
        fragments = record.source_edge_fragments
        if damage == 'missing_fragment': fragments = ()
        elif damage == 'foreign_ancestor': fragments = tuple(replace(f,source_primitive_ids=('unknown',)) for f in fragments)
        else:
            f = fragments[0]
            fragments = (replace(f, geometry=(*f.geometry[:3], f.geometry[3]+.1)), *fragments[1:])
        damaged = replace(record, source_edge_fragments=fragments)
        scope = replace(scope, records=tuple(damaged if r.wall_candidate_id==record.wall_candidate_id else r for r in scope.records))
    else:
        proof = producer._raster_source_projection(record=record, opening=bound[0][1],
            geometry=geometry, wall_scope=scope)
        key = bound[0][0].snapshot_id, proof[1][0]
        if damage == 'missing_receipt': del source._raster_visibility_receipts[key]
        elif damage == 'wrong_dpi': source._raster_visibility_receipts[key] = replace(source._raster_visibility_receipts[key],dpi=999)
        else:
            observation = source._producer._store.observations[key]
            source._producer._store.observations[key] = replace(observation,geometry=(0.,0.,1.,0.))
    monkeypatch.setattr(producer._walls, 'resolve_scope', lambda _s: scope)
    assert all(r.status is Status.ABSTAINED for r in _publish(producer, bound))
