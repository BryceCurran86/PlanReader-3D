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
