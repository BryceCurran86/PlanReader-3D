"""Source-proven split host may be used ONLY in opt-in nonpublishing frame shadow."""
from dataclasses import replace

import pytest

import pb_opening_host_binding_authority as host_geometry
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_opening_host_frame_authority import OpeningHostFrameProducer
from test_raster_connected_host_frame import _fixture, _publish, _scope


def _shadow(composition):
    return OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=composition.physical_opening_authority,
        host_binding_authority=composition.opening_host_binding_authority,
        physical_wall_candidate_authority=composition.physical_wall_candidate_authority,
        raster_split_frame_shadow=True,
    )


def _context(source, composition, producer, bound):
    scope=_scope(producer,bound)
    _, opening, _, binding=bound[0]
    geometry=host_geometry._opening_geometry(producer._opening,opening)
    return scope,opening,binding,geometry


def test_default_and_shadow_preserve_original_positive_connected_frames():
    source,composition,producer,bound=_fixture()
    expected=_publish(producer,bound)
    assert all(r.status is Status.CORROBORATED for r in expected)
    assert _publish(_shadow(composition),bound)==expected


def test_opt_in_source_split_edge_rechecks_own_exact_host_members(monkeypatch):
    source,composition,producer,bound=_fixture()
    scope,opening,binding,geometry=_context(source,composition,producer,bound)
    authentic=host_geometry._resolve_raster_source_band_host(
        producer._opening,opening,scope.records,geometry,
        scope.equivalence,scope.source_observation_ids)
    assert authentic.status is Status.CORROBORATED and len(authentic.bands)==1
    provenance=replace(binding,reason_codes=(
        *binding.reason_codes,host_geometry.RASTER_SPLIT_CENTERLINE_HOST_RESOLVED))
    monkeypatch.setattr(host_geometry,"_resolve_raster_source_band_host",
        lambda *args:host_geometry._HostBandResolution(Status.CORROBORATED,(),()))
    calls=[]
    def reprove_split(*args):
        calls.append(True)
        return authentic
    monkeypatch.setattr(host_geometry,"_resolve_raster_split_centerline_host",reprove_split)
    assert producer._raster_binding_nodes(
        opening=opening,binding=provenance,geometry=geometry,wall_scope=scope) is None
    assert not calls
    shadow=_shadow(composition)
    nodes=shadow._raster_binding_nodes(
        opening=opening,binding=provenance,geometry=geometry,wall_scope=scope)
    assert nodes is not None and nodes[0] != nodes[1] and calls==[True]
    wrong=replace(provenance,member_wall_candidate_ids=(
        "unsupported-original-wall","unowned-wall"))
    assert shadow._raster_binding_nodes(
        opening=opening,binding=wrong,geometry=geometry,wall_scope=scope) is None


@pytest.mark.parametrize("source_status,source_bands",[
    (Status.ABSTAINED,0),
    (Status.CONFLICT,0),
    (Status.CORROBORATED,1),
])
def test_no_source_integrity_or_competing_positive_witness_bypass(
        monkeypatch,source_status,source_bands):
    source,composition,producer,bound=_fixture()
    scope,opening,binding,geometry=_context(source,composition,producer,bound)
    authentic=host_geometry._resolve_raster_source_band_host(
        producer._opening,opening,scope.records,geometry,
        scope.equivalence,scope.source_observation_ids)
    source_proof=host_geometry._HostBandResolution(
        source_status, authentic.bands if source_bands else (), ())
    reasoned=replace(binding,reason_codes=(
        *binding.reason_codes,host_geometry.RASTER_SPLIT_CENTERLINE_HOST_RESOLVED))
    monkeypatch.setattr(host_geometry,"_resolve_raster_source_band_host",lambda *args:source_proof)
    def forbidden(*args):
        raise AssertionError("unearned alternate host proof")
    monkeypatch.setattr(host_geometry,"_resolve_raster_split_centerline_host",forbidden)
    result=_shadow(composition)._raster_binding_nodes(
        opening=opening,binding=reasoned,geometry=geometry,wall_scope=scope)
    if source_bands:
        assert result is not None
    else:
        assert result is None


def test_no_shadow_without_original_source_host_reason(monkeypatch):
    source,composition,producer,bound=_fixture()
    scope,opening,binding,geometry=_context(source,composition,producer,bound)
    monkeypatch.setattr(host_geometry,"_resolve_raster_source_band_host",lambda *args:
        host_geometry._HostBandResolution(Status.CORROBORATED,(),()))
    def forbidden(*args):
        raise AssertionError("missing producer-issued split-centerline host reason")
    monkeypatch.setattr(host_geometry,"_resolve_raster_split_centerline_host",forbidden)
    assert _shadow(composition)._raster_binding_nodes(
        opening=opening,binding=binding,geometry=geometry,wall_scope=scope) is None


def test_extra_unproven_real_source_wall_fragment_remains_a_whole_wall_abstain():
    _source,composition,producer,bound=_fixture(remote=True)
    results=_publish(_shadow(composition),bound)
    assert all(r.status is Status.ABSTAINED and
        "opening_host_frame_aligned_fragment_distinctness_unproven" in r.reason_codes
        for r in results)


@pytest.mark.parametrize("invalid",["yes",None,1])
def test_shadow_parameter_must_be_an_explicit_boolean(invalid):
    _source,composition,_producer,_bound=_fixture()
    with pytest.raises(TypeError):
        OpeningHostFrameProducer.from_authorities(
            physical_opening_authority=composition.physical_opening_authority,
            host_binding_authority=composition.opening_host_binding_authority,
            physical_wall_candidate_authority=composition.physical_wall_candidate_authority,
            raster_split_frame_shadow=invalid,
        )
