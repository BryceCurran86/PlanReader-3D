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


def _tag_existing_host_result(monkeypatch, host_authority, binding, *, split=True):
    """Mock source-produced classification, never an invented binding field."""
    actual_resolve=host_authority.resolve
    def resolved(selector):
        result=actual_resolve(selector)
        if (result.record is None or result.record.record_id != binding.record_id):
            return result
        code=host_geometry.RASTER_SPLIT_CENTERLINE_HOST_RESOLVED
        reasons=tuple(x for x in result.reason_codes if x != code)
        return replace(result,reason_codes=(
            (*reasons,code) if split else reasons))
    monkeypatch.setattr(host_authority,"resolve",resolved)


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
    _tag_existing_host_result(monkeypatch,producer._host,binding)
    provenance=binding
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
    _tag_existing_host_result(monkeypatch,producer._host,binding)
    reasoned=binding
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
    _tag_existing_host_result(monkeypatch,producer._host,binding,split=False)
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


def _aligned_tick_records(base, center, count):
    extra=[]
    for index in range(count):
        start=(10.0 + index * 20.0, center)
        end=(14.5 + index * 20.0, center)
        extra.append(replace(base, wall_candidate_id=f"tick-{index}",
            physical_identity=replace(base.physical_identity,
                candidate_identity_id=f"wall2-tick-{index}",
                source_primitive_ids=(f"raster_segment:tick:1.0.0:{index}",),
                edge_ids=(f"tick-edge-{index}",),
                path_fingerprint=(start, end)),
            wall_candidate=replace(base.wall_candidate, centerline_pts=(start, end))))
    return tuple(extra)


def test_seven_aligned_raster_ticks_remain_unproven_in_shadow(monkeypatch):
    _source,composition,producer,bound=_fixture()
    scope=_scope(producer,bound)
    center=_publish(producer,bound)[0].evidence.origin_pt[1]
    extra=_aligned_tick_records(scope.records[0], center, 7)
    monkeypatch.setattr(producer._walls,"resolve_scope",
        lambda _s: replace(scope,records=(*scope.records, *extra)))
    shadow=_shadow(composition)
    monkeypatch.setattr(shadow._walls,"resolve_scope",
        lambda _s: replace(scope,records=(*scope.records, *extra)))
    results=_publish(shadow,bound)
    assert all(r.status is Status.ABSTAINED and
        "opening_host_frame_aligned_fragment_distinctness_unproven" in r.reason_codes
        for r in results)


def test_repeated_raster_dimension_ticks_do_not_block_opt_in_shadow_frame(monkeypatch):
    source,composition,producer,bound=_fixture()
    expected=_publish(producer,bound)
    assert all(r.status is Status.CORROBORATED for r in expected)
    scope=_scope(producer,bound)
    center=expected[0].evidence.origin_pt[1]
    extra=_aligned_tick_records(scope.records[0], center, 8)
    monkeypatch.setattr(producer._walls,"resolve_scope",
        lambda _s: replace(scope,records=(*scope.records, *extra)))
    default_results=_publish(producer,bound)
    assert all(r.status is Status.ABSTAINED and
        "opening_host_frame_aligned_fragment_distinctness_unproven" in r.reason_codes
        for r in default_results)
    shadow=_shadow(composition)
    monkeypatch.setattr(shadow._walls,"resolve_scope",
        lambda _s: replace(scope,records=(*scope.records, *extra)))
    results=_publish(shadow,bound)
    assert all(r.status is Status.CORROBORATED for r in results)
    assert {r.evidence.whole_wall_frame_id for r in results}=={
        r.evidence.whole_wall_frame_id for r in expected}
    assert _publish(shadow,tuple(reversed(bound)))==tuple(reversed(results))
    from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
    from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
    voids=compose_live_physical_opening_voids(source_visibility_producer=source,
        wall_opening_composition=composition)
    assert publish_live_opening_area_quantities(voids)==()


def test_source_corrupted_tick_geometry_cannot_mint_a_shadow_frame(monkeypatch):
    _source,composition,producer,bound=_fixture()
    scope=_scope(producer,bound)
    center=_publish(producer,bound)[0].evidence.origin_pt[1]
    extra=_aligned_tick_records(scope.records[0], center, 8)
    corrupted=tuple(replace(record, physical_identity=replace(
        record.physical_identity, source_primitive_ids=("d-tick",)))
        for record in extra)
    shadow=_shadow(composition)
    monkeypatch.setattr(shadow._walls,"resolve_scope",
        lambda _s: replace(scope,records=(*scope.records, *corrupted)))
    results=_publish(shadow,bound)
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
