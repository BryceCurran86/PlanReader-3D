from copy import deepcopy
from types import SimpleNamespace

import pytest

import pb_opening_host_binding_authority as host
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_physical_wall_identity import PhysicalEquivalenceClass as Class
from test_raster_opening_split_centerline_host import _record, _equivalence, OPENING


def _support():
    return tuple(SimpleNamespace(observation_kind=kind, geometry=line) for kind, line in (
        ('raster_wall_band_face', (20., 50., 100., 50.)),
        ('raster_wall_band_face', (20., 60., 100., 60.)),
        ('raster_wall_band_end', (100., 50., 100., 60.)),
        ('raster_wall_band_face', (140., 50., 220., 50.)),
        ('raster_wall_band_face', (140., 60., 220., 60.)),
        ('raster_wall_band_end', (140., 50., 140., 60.)),
    ))


def _fixture():
    records = (_record('left', start=20., end=100., offset=-2., source_ids=('raw:left',)),
               _record('right', start=140., end=220., offset=1., source_ids=('raw:right',)))
    return records, {'raw:left': (20., 53., 100., 53.), 'raw:right': (140., 56., 220., 56.)}


def _resolve(records, lines, support=None, opening=OPENING, pairs=()):
    return host._resolve_raster_source_band_host_from_records(
        _support() if support is None else support, records, opening,
        _equivalence(records, pair_classifications=pairs), lines,
    )


def test_distinct_flanks_bind_only_through_authenticated_solid_band_membership():
    records, lines = _fixture()
    before = deepcopy((records, lines))
    result = _resolve(records, lines)
    assert result.status is Status.CORROBORATED
    assert result.reason_codes == (host.RASTER_SOURCE_BAND_HOST_RESOLVED,)
    assert result.bands[0].member_ids == ('left', 'right')
    assert (records, lines) == before
    assert _resolve(tuple(reversed(records)), dict(reversed(tuple(lines.items()))), tuple(reversed(_support()))) == result


@pytest.mark.parametrize('defect', ['ancestry', 'remote', 'outside', 'missing_end', 'end_conflict', 'unusable', 'curved', 'non_simple', 'displaced_support', 'source_end'])
def test_unsupported_membership_abstains(defect):
    records, lines = _fixture()
    support = list(_support())
    if defect == 'ancestry':
        records[0].physical_identity.source_primitive_ids = ('unrelated',)
    elif defect == 'remote':
        records[0].wall_candidate.centerline_pts = ((20., 53.), (40., 53.))
    elif defect == 'outside':
        lines['raw:left'] = (20., 70., 100., 70.)
    elif defect == 'missing_end':
        support.pop(2)
    elif defect == 'end_conflict':
        support[2].geometry = (99., 50., 99., 60.)
    elif defect == 'unusable':
        records[0].physical_identity.usable = False
    elif defect == 'curved':
        records[0].wall_candidate.is_curved = True
    elif defect == 'non_simple':
        records[0].wall_candidate.reason_codes = ('non_simple_chain_topology_fallback_ordering',)
    elif defect == 'displaced_support':
        for item in support:
            x0,y0,x1,y1 = item.geometry
            item.geometry = (x0,y0+100.,x1,y1+100.)
    elif defect == 'source_end':
        lines['raw:left'] = (20.,53.,100.-host.DEFAULT_GAP_SNAP_TOLERANCE_PT-.01,53.)
    result = _resolve(records, lines, support)
    assert result.bands == ()


@pytest.mark.parametrize('classification', [Class.DISTINCT_PHYSICAL_WALLS, Class.AMBIGUOUS_PHYSICAL_EQUIVALENCE])
def test_two_competing_flank_owners_conflict_without_ranking(classification):
    records, lines = _fixture()
    extra = _record('other', start=20., end=100., offset=-1., source_ids=('raw:other',))
    lines['raw:other'] = (20., 54., 100., 54.)
    records = (*records, extra)
    result = _resolve(records, lines, pairs=(('left', 'other', classification.value),))
    assert result.status is Status.CONFLICT
    assert result.bands == ()


@pytest.mark.parametrize('scale,rotation,dx,dy', [(1.,0,333.,-120.), (1.,1,0.,0.), (2.,1,-100.,200.), (.5,0,5.,8.)])
def test_translation_rotation_scale_and_segment_split_invariance(scale, rotation, dx, dy):
    records, lines = _fixture()
    support = _support()
    def point(p):
        x,y=p
        if rotation: x,y=-y,x
        return (x*scale+dx,y*scale+dy)
    def line(values):
        return (*point(values[:2]),*point(values[2:]))
    for record in records:
        start,end=record.wall_candidate.centerline_pts
        midpoint=((start[0]+end[0])/2.,(start[1]+end[1])/2.)
        record.wall_candidate.centerline_pts=tuple(point(p) for p in (start,midpoint,end))
    for item in support: item.geometry=line(item.geometry)
    lines={k:line(v) for k,v in lines.items()}
    opening=host._OpeningGeometry(origin=point(OPENING.origin), axis=(0.,1.) if rotation else (1.,0.),
        normal=(-1.,0.) if rotation else (0.,1.), length=OPENING.length*scale, thickness=OPENING.thickness*scale)
    result=_resolve(records, lines, support, opening)
    assert result.status is Status.CORROBORATED
    assert result.bands[0].member_ids==('left','right')


def test_remote_fragment_with_shared_primitive_does_not_compete():
    records, lines = _fixture()
    remote = _record('remote', start=20., end=40., offset=-2., source_ids=('raw:left',))
    result = _resolve((*records, remote), lines)
    assert result.bands[0].member_ids == ('left','right')


def test_source_alias_order_cannot_change_proven_band_geometry():
    records, lines = _fixture()
    records[0].physical_identity.source_primitive_ids = ('raw:left', 'raw:alias')
    lines['raw:alias'] = (20., 54., 100., 54.)
    first = _resolve(records, lines)
    records[0].physical_identity.source_primitive_ids = ('raw:alias', 'raw:left')
    replay = _resolve(records, lines)
    assert first.status is Status.CORROBORATED
    assert replay == first
    assert first.bands[0].center_offset == 0.0  # midpoint of source faces 50/60
