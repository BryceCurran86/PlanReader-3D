"""Opening-local mixed source roles must remain producer-owned and fail closed.

These controls are supplemental to the unmodified original-source PDF test
in tests/test_raster_unchanged_band_segments.py. No fixture grants physical
wall authority or a metric quantity.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
import pb_opening_host_binding_authority as host


def _record(name: str, source: str = "verified"):
    return SimpleNamespace(
        wall_candidate_id=name,
        physical_identity=SimpleNamespace(candidate_identity_id=source + name),
    )


def _band(*members: str):
    return host._HostBandResolution(
        Status.CORROBORATED,
        (SimpleNamespace(member_ids=tuple(sorted(members))),),
    )


def test_one_old_and_one_new_source_flank_require_exact_joint_proof(monkeypatch):
    prior = _record("wall_canonical")
    new = _record("wall_supplemental")
    calls = {}

    def roles(record, opening):
        return ("right",) if record is prior else ("left",)

    def cross_source_equivalence(identities):
        calls["identities"] = tuple(x.candidate_identity_id for x in identities)
        return "authenticated-pair-evaluation"

    def source_band(auth, opening, records, geom, equivalence, source_ids):
        calls["records"] = tuple(row.wall_candidate_id for row in records)
        calls["equivalence"] = equivalence
        calls["source_ids"] = source_ids
        return _band(prior.wall_candidate_id, new.wall_candidate_id)

    monkeypatch.setattr(host, "_candidate_host_roles", roles)
    monkeypatch.setattr(host, "resolve_physical_wall_equivalence", cross_source_equivalence)
    monkeypatch.setattr(host, "_resolve_raster_source_band_host", source_band)

    resolution = host._resolve_opening_local_mixed_scope_source_band(
        None, None, None,
        (prior,), (new,),
        ("original-visible-receipt",),
        ("new-visible-receipt",),
    )
    assert resolution.status is Status.CORROBORATED
    assert len(resolution.bands) == 1
    assert set(resolution.bands[0].member_ids) == {
        "wall_canonical", "wall_supplemental"
    }
    assert calls["records"] == ("wall_canonical", "wall_supplemental")
    assert calls["source_ids"] == (
        "new-visible-receipt", "original-visible-receipt"
    )
    assert calls["equivalence"] == "authenticated-pair-evaluation"
    assert set(calls["identities"]) == {
        "verifiedwall_canonical", "verifiedwall_supplemental"
    }


def test_cross_scope_identity_collision_cannot_silently_choose_one(monkeypatch):
    ordinary = _record("wall_same_id", "old")
    supplemental = _record("wall_same_id", "new")
    monkeypatch.setattr(host, "_candidate_host_roles", lambda *_: ("left",))
    monkeypatch.setattr(host, "resolve_physical_wall_equivalence",
                        lambda *_: pytest.fail("identity collision elected equivalence"))
    resolution = host._resolve_opening_local_mixed_scope_source_band(
        None, None, None, (ordinary,), (supplemental,), (), (),
    )
    assert resolution.status is Status.CONFLICT
    assert not resolution.bands
    assert "opening_local_supplemental_wall_identity_collision" in resolution.reason_codes


def test_never_publish_if_unverified_additive_source_does_not_support_band(monkeypatch):
    old = _record("wall_canonical")
    new = _record("wall_supplemental")
    monkeypatch.setattr(host, "_candidate_host_roles", lambda *_: ("left",))
    monkeypatch.setattr(host, "resolve_physical_wall_equivalence", lambda *_: "verified")
    monkeypatch.setattr(
        host, "_resolve_raster_source_band_host",
        lambda *_: _band(old.wall_candidate_id),
    )
    resolution = host._resolve_opening_local_mixed_scope_source_band(
        None, None, None, (old,), (new,), ("o",), ("n",),
    )
    assert resolution.status is Status.ABSTAINED
    assert not resolution.bands
    assert resolution.reason_codes == ("opening_local_supplemental_source_not_used",)


def test_upstream_cross_scope_ambiguity_remains_abstained(monkeypatch):
    old = _record("wall_canonical")
    new = _record("wall_supplemental")
    monkeypatch.setattr(host, "_candidate_host_roles", lambda *_: ("left",))
    monkeypatch.setattr(host, "resolve_physical_wall_equivalence", lambda *_: "unresolved")
    monkeypatch.setattr(
        host, "_resolve_raster_source_band_host",
        lambda *_: host._HostBandResolution(
            Status.ABSTAINED, (), ("host_physical_equivalence_unavailable",),
        ),
    )
    resolution = host._resolve_opening_local_mixed_scope_source_band(
        None, None, None, (old,), (new,), (), (),
    )
    assert resolution.status is Status.ABSTAINED
    assert not resolution.bands
    assert resolution.reason_codes == ("host_physical_equivalence_unavailable",)


def test_without_supplemental_source_no_host_is_invented(monkeypatch):
    old = _record("wall_canonical")
    monkeypatch.setattr(host, "_candidate_host_roles", lambda *_: ("right",))
    monkeypatch.setattr(host, "resolve_physical_wall_equivalence",
                        lambda *_: pytest.fail("missing supplement elected host"))
    resolution = host._resolve_opening_local_mixed_scope_source_band(
        None, None, None, (old,), (), ("old",), (),
    )
    assert resolution.status is Status.CORROBORATED
    assert not resolution.bands


def test_identical_cross_scope_wall_address_cannot_count_as_supplemental(monkeypatch):
    same = _record("wall_same")
    monkeypatch.setattr(host, "_candidate_host_roles", lambda *_: ("left",))
    monkeypatch.setattr(
        host, "resolve_physical_wall_equivalence",
        lambda *_: pytest.fail("duplicate scope alias reached equivalence"),
    )
    resolution = host._resolve_opening_local_mixed_scope_source_band(
        None, None, None, (same,), (same,), ("old",), ("new",),
    )
    assert resolution.status is Status.CONFLICT
    assert not resolution.bands
    assert resolution.reason_codes == (
        "opening_local_supplemental_wall_identity_collision",
    )


def test_compose_and_mixed_scope_shadow_flags_default_off():
    import inspect
    from pb_live_wall_opening_authority_composition import (
        compose_live_wall_opening_authority,
    )
    from pb_opening_host_binding_authority import OpeningHostBindingProducer

    compose = inspect.signature(compose_live_wall_opening_authority)
    mixed = inspect.signature(host._resolve_opening_local_mixed_scope_source_band)
    producer = inspect.signature(OpeningHostBindingProducer.__init__)
    assert compose.parameters['include_unmeasured_ink_closed_flanks_shadow'].default is False
    assert compose.parameters['source_fragment_roles_shadow'].default is False
    assert mixed.parameters['source_fragment_roles_shadow'].default is False
    assert producer.parameters['source_fragment_roles_shadow'].default is False


def test_fragment_nominated_member_without_whole_candidate_role_is_not_a_host(monkeypatch):
    from test_raster_opening_split_centerline_host import OPENING, _record

    ordinary = _record('right', start=140., end=220., offset=1., source_ids=('raw:right',))
    parent = _record('parent', start=20., end=220., offset=-2., source_ids=('raw:parent',))
    parent.wall_candidate.centerline_pts = (
        (20., 53.), (100., 53.), (140., 53.), (220., 53.),
    )

    def source_band(auth, opening, records, geom, equivalence, source_ids):
        return host._HostBandResolution(
            Status.CORROBORATED,
            (host._HostBand(
                member_ids=('parent', 'right'),
                member_candidate_identity_ids=('parent', 'right'),
                member_equivalence_groups=(('parent',), ('right',)),
                center_offset=0.0,
            ),),
            (host.RASTER_SOURCE_BAND_HOST_RESOLVED,),
        )

    monkeypatch.setattr(host, 'resolve_physical_wall_equivalence', lambda identities: identities)
    monkeypatch.setattr(host, '_resolve_raster_source_band_host', source_band)
    resolution = host._resolve_opening_local_mixed_scope_source_band(
        None, None, OPENING, (ordinary,), (parent,), ('old',), ('new',),
        source_fragment_roles_shadow=True,
    )
    assert resolution.bands == ()
    assert resolution.reason_codes == (
        host.OPENING_LOCAL_SUPPLEMENTAL_WHOLE_CANDIDATE_ROLE_UNMAPPED,
    )


def test_mixed_scope_host_with_only_shared_members_is_demoted():
    from pb_opening_host_binding_authority import (
        OPENING_HOST_BINDING_RESOLVED,
        OPENING_LOCAL_SUPPLEMENTAL_SHARED_HOST_MEMBER,
        OPENING_LOCAL_SUPPLEMENTAL_SOURCE_BAND_HOST_RESOLVED,
        OpeningHostBindingRecord,
        OpeningHostBindingResult,
        _exclusive_mixed_scope_host_results,
    )

    def record(opening, members, mixed):
        payload = OpeningHostBindingRecord(
            record_id='rec-' + opening,
            document_id='d',
            revision_id='r',
            source_sha256='s',
            snapshot_id='n',
            page_id='3',
            decision_scope_id='wall-source:page-3',
            opening_identity_id=opening,
            host_wall_id='host-' + opening,
            member_wall_candidate_ids=members,
            member_candidate_identity_ids=members,
            member_equivalence_groups=tuple((member,) for member in members),
            source_observation_ids=('obs',),
        )
        reasons = (OPENING_HOST_BINDING_RESOLVED,)
        if mixed:
            reasons = reasons + (OPENING_LOCAL_SUPPLEMENTAL_SOURCE_BAND_HOST_RESOLVED,)
        return OpeningHostBindingResult(Status.CORROBORATED, reasons, payload)

    neighbour = record('opening-neighbour', ('wall_shared_a', 'wall_unique_n'), mixed=True)
    other = record('opening-other', ('wall_shared_b', 'wall_unique_o'), mixed=True)
    borrowed = record('opening-borrowed', ('wall_shared_a', 'wall_shared_b'), mixed=True)
    unique = record('opening-unique', ('wall_left', 'wall_right'), mixed=True)
    ordinary = record('opening-ordinary', ('wall_ordinary',), mixed=False)
    results = {
        ('d', 'r', 's', 'n', '3', 'scope', 'opening-neighbour'): neighbour,
        ('d', 'r', 's', 'n', '3', 'scope', 'opening-other'): other,
        ('d', 'r', 's', 'n', '3', 'scope', 'opening-borrowed'): borrowed,
        ('d', 'r', 's', 'n', '3', 'scope', 'opening-unique'): unique,
        ('d', 'r', 's', 'n', '3', 'scope', 'opening-ordinary'): ordinary,
    }
    exclusive = _exclusive_mixed_scope_host_results(results)
    assert exclusive[('d', 'r', 's', 'n', '3', 'scope', 'opening-neighbour')].record is neighbour.record
    assert exclusive[('d', 'r', 's', 'n', '3', 'scope', 'opening-other')].record is other.record
    assert exclusive[('d', 'r', 's', 'n', '3', 'scope', 'opening-unique')].record is unique.record
    assert exclusive[('d', 'r', 's', 'n', '3', 'scope', 'opening-ordinary')].record is ordinary.record
    demoted = exclusive[('d', 'r', 's', 'n', '3', 'scope', 'opening-borrowed')]
    assert demoted.record is None
    assert OPENING_LOCAL_SUPPLEMENTAL_SHARED_HOST_MEMBER in demoted.reason_codes


def _mixed_scope_record(opening, members, *, document='d', revision='r',
                        sha='s', snapshot='n', page='3'):
    from pb_opening_host_binding_authority import (
        OPENING_HOST_BINDING_RESOLVED,
        OPENING_LOCAL_SUPPLEMENTAL_SOURCE_BAND_HOST_RESOLVED,
        OpeningHostBindingRecord,
        OpeningHostBindingResult,
    )

    payload = OpeningHostBindingRecord(
        record_id='rec-' + opening,
        document_id=document,
        revision_id=revision,
        source_sha256=sha,
        snapshot_id=snapshot,
        page_id=page,
        decision_scope_id='wall-source:page-' + page,
        opening_identity_id=opening,
        host_wall_id='host-' + opening,
        member_wall_candidate_ids=members,
        member_candidate_identity_ids=members,
        member_equivalence_groups=tuple((member,) for member in members),
        source_observation_ids=('obs',),
    )
    return OpeningHostBindingResult(
        Status.CORROBORATED,
        (OPENING_HOST_BINDING_RESOLVED, OPENING_LOCAL_SUPPLEMENTAL_SOURCE_BAND_HOST_RESOLVED),
        payload,
    )


@pytest.mark.parametrize('first_foreign', (False, True))
@pytest.mark.parametrize('axis,foreign_value', (
    ('document', 'other-doc'),
    ('revision', 'other-rev'),
    ('sha', 'other-sha'),
    ('snapshot', 'other-snap'),
    ('page', '11'),
))
def test_mixed_scope_exclusivity_is_namespaced_by_physical_source_scope(
    first_foreign, axis, foreign_value,
):
    from pb_opening_host_binding_authority import (
        OPENING_LOCAL_SUPPLEMENTAL_SHARED_HOST_MEMBER,
        _exclusive_mixed_scope_host_results,
    )

    members = ('same-coordinate-left', 'same-coordinate-right')
    local = _mixed_scope_record('opening-local', members)
    foreign_kwargs = {axis: foreign_value}
    foreign = _mixed_scope_record('opening-foreign', members, **foreign_kwargs)
    local_key = (
        local.record.document_id, local.record.revision_id,
        local.record.source_sha256, local.record.snapshot_id,
        local.record.page_id, 'scope', 'opening-local',
    )
    foreign_key = (
        foreign.record.document_id, foreign.record.revision_id,
        foreign.record.source_sha256, foreign.record.snapshot_id,
        foreign.record.page_id, 'scope', 'opening-foreign',
    )
    alone = _exclusive_mixed_scope_host_results({local_key: local})
    assert alone[local_key].record is local.record
    ordered = (
        {foreign_key: foreign, local_key: local}
        if first_foreign else
        {local_key: local, foreign_key: foreign}
    )
    exclusive = _exclusive_mixed_scope_host_results(ordered)
    assert exclusive[local_key].record is local.record
    assert exclusive[foreign_key].record is foreign.record
    assert OPENING_LOCAL_SUPPLEMENTAL_SHARED_HOST_MEMBER not in exclusive[local_key].reason_codes
    assert OPENING_LOCAL_SUPPLEMENTAL_SHARED_HOST_MEMBER not in exclusive[foreign_key].reason_codes


def test_through_going_parent_is_not_a_left_owner_unless_fragment_flag(monkeypatch):
    from test_raster_opening_split_centerline_host import OPENING, _record

    ordinary = _record('right', start=140., end=220., offset=1., source_ids=('raw:right',))
    parent = _record('parent', start=20., end=220., offset=-2., source_ids=('raw:parent',))
    parent.wall_candidate.centerline_pts = (
        (20., 53.), (100., 53.), (140., 53.), (220., 53.),
    )
    selected = []

    def source_band(auth, opening, records, geom, equivalence, source_ids):
        selected.append(tuple(row.wall_candidate_id for row in records))
        return host._HostBandResolution(Status.CORROBORATED, ())

    monkeypatch.setattr(host, 'resolve_physical_wall_equivalence', lambda identities: identities)
    monkeypatch.setattr(host, '_resolve_raster_source_band_host', source_band)
    off = host._resolve_opening_local_mixed_scope_source_band(
        None, None, OPENING, (ordinary,), (parent,), ('old',), ('new',),
    )
    assert off.status is Status.CORROBORATED
    assert off.bands == ()
    assert selected == []

    on = host._resolve_opening_local_mixed_scope_source_band(
        None, None, OPENING, (ordinary,), (parent,), ('old',), ('new',),
        source_fragment_roles_shadow=True,
    )
    assert selected == [('parent', 'right')]
    assert on.status is Status.CORROBORATED
    assert on.bands == ()


def test_cross_scope_candidate_identity_alias_cannot_count_twice(monkeypatch):
    canonical = _record("wall_old", "shared")
    supplemental = _record("wall_new", "shared")
    # Force the two wall addresses to carry the same producer physical identity.
    supplemental.physical_identity.candidate_identity_id = (
        canonical.physical_identity.candidate_identity_id
    )
    monkeypatch.setattr(host, "_candidate_host_roles", lambda *_: ("left",))
    monkeypatch.setattr(
        host, "resolve_physical_wall_equivalence",
        lambda *_: pytest.fail("candidate alias reached equivalence"),
    )
    resolution = host._resolve_opening_local_mixed_scope_source_band(
        None, None, None, (canonical,), (supplemental,), ("old",), ("new",),
    )
    assert resolution.status is Status.CONFLICT
    assert not resolution.bands
    assert resolution.reason_codes == (
        "opening_local_supplemental_candidate_identity_collision",
    )
