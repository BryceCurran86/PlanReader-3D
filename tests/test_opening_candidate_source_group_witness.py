"""Fail-closed original-source raw candidate grouping: never publish a count/host."""
from __future__ import annotations

from types import SimpleNamespace
import copy

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector


def _setup(*, raster=False, ids=("candidate-a", "candidate-b"),
           observed=("obs-a", "obs-b")):
    selector = ObservationSelector(
        document_id="document", revision_id="revision", source_sha256="1" * 64,
        snapshot_id="source_snapshot", observation_id="seed-observation")
    source = SimpleNamespace(
        document_id="document", revision_id="revision", source_sha256="1" * 64,
        snapshot_id="source_snapshot", page_id="3")
    result = SimpleNamespace(status=Status.CORROBORATED, observation=source)
    closure = SimpleNamespace(
        status=Status.CORROBORATED,
        unresolved_candidate_ids=ids,
        unresolved_observation_ids=observed)
    authority = object.__new__(PhysicalOpeningAuthority)
    key = PhysicalOpeningAuthority._visible_page_candidate_key(source)
    if raster:
        authority._source_visibility_authority = SimpleNamespace(
            resolve_raster_opening_primitive=lambda _: result)
        authority._raster_gap_candidate_audit_cache = {
            key: (
                ("candidate-b", frozenset(("obs-b",)), (10.0, 20.0, 30.0, 40.0)),
                ("candidate-a", frozenset(("obs-a",)), (1.0, 2.0, 3.0, 4.0)),
            )
        }
        authority.assess_raster_candidate_closure = lambda _: closure
    else:
        authority._native_raw_candidate_support_cache = {
            key: (("candidate-b", "window_jamb_pair_candidate", ("obs-b",)), ("candidate-a", "door_jamb_leaf_candidate", ("obs-a",)))
        }
        authority.assess_visible_candidate_closure = lambda _: closure
        authority._resolve_visible_cached = lambda _: result
    return authority, selector, key, closure


def test_native_group_witness_retains_exact_original_per_candidate_source_membership():
    authority, selector, key, closure = _setup()
    before = copy.deepcopy(authority._native_raw_candidate_support_cache)
    rows = authority.audited_unresolved_source_candidate_groups(
        selector, family="native")
    assert tuple(x["candidate_id"] for x in rows) == ("candidate-a", "candidate-b")
    assert tuple(x["source_observation_ids"] for x in rows) == (["obs-a"], ["obs-b"])
    assert all(x["aperture_bbox_pt"] is None for x in rows)
    assert [x["structural_pattern"] for x in rows] == ["door_jamb_leaf_candidate", "window_jamb_pair_candidate"]
    assert all(x["candidate_status"] == "unresolved_source_only" for x in rows)
    assert authority._native_raw_candidate_support_cache == before
    assert closure.unresolved_candidate_ids == ("candidate-a", "candidate-b")


def test_raster_group_witness_has_detector_owned_exact_aperture_and_source_groups():
    authority, selector, _, _ = _setup(raster=True)
    rows = authority.audited_unresolved_source_candidate_groups(
        selector, family="raster")
    assert tuple(x["source_observation_ids"] for x in rows) == (["obs-a"], ["obs-b"])
    assert rows[0]["aperture_bbox_pt"] == [1.0, 2.0, 3.0, 4.0]
    assert rows[1]["aperture_bbox_pt"] == [10.0, 20.0, 30.0, 40.0]
    assert all(row["structural_pattern"] == "raster_gap_candidate" for row in rows)


def test_missing_group_refuses_apparent_closure():
    authority, selector, key, _ = _setup()
    authority._native_raw_candidate_support_cache[key] = (
        ("candidate-a", "door_jamb_leaf_candidate", ("obs-a",)),)
    with pytest.raises(RuntimeError, match="group-to-source mapping incomplete"):
        authority.audited_unresolved_source_candidate_groups(selector, family="native")


def test_raw_group_extra_unverified_source_refused():
    authority, selector, key, _ = _setup(raster=True)
    authority._raster_gap_candidate_audit_cache[key] = (
        ("candidate-a", frozenset(("obs-a", "invented")), (1., 2., 3., 4.)),
        ("candidate-b", frozenset(("obs-b",)), (10., 20., 30., 40.)),
    )
    with pytest.raises(RuntimeError, match="outside authenticated closure"):
        authority.audited_unresolved_source_candidate_groups(selector, family="raster")


def test_abstained_source_fails_closed_without_emitting_group_proof():
    authority, selector, key, closure = _setup()
    closure.status = Status.ABSTAINED
    with pytest.raises(RuntimeError, match="original scope unavailable"):
        authority.audited_unresolved_source_candidate_groups(selector, family="native")


def test_input_type_and_family_guard_prevent_unscoped_provenance():
    authority, selector, _, _ = _setup()
    with pytest.raises(ValueError, match="family must be"):
        authority.audited_unresolved_source_candidate_groups(selector, family="unknown")
    with pytest.raises(TypeError, match="ObservationSelector"):
        authority.audited_unresolved_source_candidate_groups(object(), family="native")
