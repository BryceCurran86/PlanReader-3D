"""A shadow host policy must be re-proved at the frame edge boundary.

Focused orchestration controls do not mint a producer or publish a frame.
Actual PDF-backed host/frame controls are in test_raster_connected_host_frame.
"""
from dataclasses import replace
from types import SimpleNamespace as Obj

import pytest

import pb_opening_host_binding_authority as host
from pb_opening_host_frame_authority import OpeningHostFrameProducer
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_physical_wall_candidate_authority import PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED
from test_raster_opening_whole_wall_frame import GEOMETRY, _binding, _opening, _record, _scope


def edge_fixture(monkeypatch, *, policy):
    binding = _binding('left')
    binding.member_wall_candidate_ids = ('left', 'right')
    left = _record('left'); right = _record('right')
    left.wall_candidate.centerline_pts = ((20.,55.),(100.,55.))
    right.wall_candidate.centerline_pts = ((140.,55.),(220.,55.))
    ordinary = _scope((left,)); ordinary.source_observation_ids = ('ordinary',)
    supplemental = _scope((right,), complete=False)
    supplemental.source_observation_ids = ('supplemental',)
    f = object.__new__(OpeningHostFrameProducer)
    f._opening = Obj(); f._walls = Obj()
    f._supplemental_walls = Obj(resolve_scope=lambda _: supplemental)
    f._raster_split_frame_shadow = False
    f._source_fragment_roles_shadow = policy
    monkeypatch.setattr(host, '_resolve_raster_source_band_host',
        lambda *_: host._HostBandResolution(Status.CORROBORATED, ()))
    return f, binding, ordinary, supplemental


@pytest.mark.parametrize('policy', (False, True))
def test_exact_fragment_policy_is_replayed_instead_of_trusting_old_host(monkeypatch, policy):
    f, binding, ordinary, _ = edge_fixture(monkeypatch, policy=policy)
    calls = []
    def reprove(*args, source_fragment_roles_shadow=False):
        calls.append((args[-2:], source_fragment_roles_shadow))
        return host._HostBandResolution(Status.CORROBORATED,
            (Obj(member_ids=('left','right')),))
    monkeypatch.setattr(host, '_resolve_opening_local_mixed_scope_source_band', reprove)
    result = f._raster_binding_nodes(opening=_opening(), binding=binding,
        geometry=GEOMETRY, wall_scope=ordinary)
    assert result is not None
    assert calls == [((('ordinary',), ('supplemental',)), policy)]


@pytest.mark.parametrize('status', (Status.ABSTAINED, Status.CONFLICT))
def test_fragment_policy_cannot_override_negative_source_reproof(monkeypatch, status):
    f,binding,ordinary,_ = edge_fixture(monkeypatch, policy=True)
    monkeypatch.setattr(host, '_resolve_opening_local_mixed_scope_source_band',
        lambda *args, **kwargs: host._HostBandResolution(status, ()))
    assert f._raster_binding_nodes(opening=_opening(),binding=binding,
        geometry=GEOMETRY,wall_scope=ordinary) is None


def test_fragment_reproof_cannot_substitute_different_host_members(monkeypatch):
    f,binding,ordinary,_ = edge_fixture(monkeypatch, policy=True)
    monkeypatch.setattr(host, '_resolve_opening_local_mixed_scope_source_band',
        lambda *args, **kwargs: host._HostBandResolution(Status.CORROBORATED,
            (Obj(member_ids=('left','foreign')),)))
    assert f._raster_binding_nodes(opening=_opening(),binding=binding,
        geometry=GEOMETRY,wall_scope=ordinary) is None


@pytest.mark.parametrize('field', ('document_id','revision_id','source_sha256',
    'snapshot_id','page_id','decision_scope_id'))
def test_foreign_supplemental_scope_cannot_enter_frame_reproof(monkeypatch, field):
    f,binding,ordinary,supplemental = edge_fixture(monkeypatch, policy=True)
    setattr(supplemental, field, 'foreign')
    monkeypatch.setattr(host, '_resolve_opening_local_mixed_scope_source_band',
        lambda *args, **kwargs: pytest.fail('foreign source scope reached role reproof'))
    assert f._raster_binding_nodes(opening=_opening(),binding=binding,
        geometry=GEOMETRY,wall_scope=ordinary) is None


@pytest.mark.parametrize('foreign', (None, 1, 'true', (), {}))
def test_frame_policy_requires_explicit_boolean(foreign):
    from test_raster_connected_host_frame import _fixture
    _, c, _, _ = _fixture()
    with pytest.raises(TypeError,match='source_fragment_roles_shadow must be a bool'):
        OpeningHostFrameProducer.from_authorities(
            physical_opening_authority=c.physical_opening_authority,
            host_binding_authority=c.opening_host_binding_authority,
            physical_wall_candidate_authority=c.physical_wall_candidate_authority,
            source_fragment_roles_shadow=foreign)


def test_fragment_policy_requires_real_supplemental_authority():
    from test_raster_connected_host_frame import _fixture
    _, c, _, _ = _fixture()
    with pytest.raises(ValueError,match='require a supplemental source authority'):
        OpeningHostFrameProducer.from_authorities(
            physical_opening_authority=c.physical_opening_authority,
            host_binding_authority=c.opening_host_binding_authority,
            physical_wall_candidate_authority=c.physical_wall_candidate_authority,
            source_fragment_roles_shadow=True)


def test_wrong_supplemental_proposition_cannot_reprove_a_host(monkeypatch):
    f,binding,ordinary,supplemental = edge_fixture(monkeypatch,policy=True)
    supplemental.proposition = 'unrelated_positive_proposition'
    monkeypatch.setattr(host,'_resolve_opening_local_mixed_scope_source_band',
        lambda *args,**kwargs: pytest.fail('unrelated proposition reached reproof'))
    assert f._raster_binding_nodes(opening=_opening(),binding=binding,
        geometry=GEOMETRY,wall_scope=ordinary) is None
