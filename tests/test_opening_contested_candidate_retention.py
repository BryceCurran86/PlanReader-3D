"""Candidates whose every support is contested are retained for audit (report only). Synthetic stubs only."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector

SELECTOR = ObservationSelector(document_id="document", revision_id="revision", source_sha256="1" * 64,
                               snapshot_id="source_snapshot", observation_id="seed-observation")
SOURCE = SimpleNamespace(document_id="document", revision_id="revision", source_sha256="1" * 64,
                         snapshot_id="source_snapshot", page_id="3")


def candidate(name, *supports):
    return SimpleNamespace(candidate_id=name, source_observation_ids=supports, structural_pattern=f"pattern-{name}")


def build(promotable, lookups):
    """``lookups``: observation id -> existence stub; anything else is ambiguous (no candidate)."""
    authority = object.__new__(PhysicalOpeningAuthority)
    authority._source_visibility_authority = SimpleNamespace()
    result = SimpleNamespace(status=Status.CORROBORATED, observation=SOURCE, reason_codes=())
    authority._resolve_visible_cached = lambda _selector: result
    authority._visible_snapshot_records = lambda _result: ((), ())
    authority._visible_candidates_for = lambda _seed, _records: ()
    authority._viewport_scoped_visible_candidates_for = lambda _seed, _records: (tuple(promotable), {}, ())
    ambiguous = SimpleNamespace(status=Status.CONFLICT, existence_record=None, candidate=None)
    authority.prove_existence = lambda selector: lookups.get(selector.observation_id, ambiguous)
    authority._native_raw_candidate_support_cache = {}
    authority._native_contested_candidate_cache = {}
    return authority


def proven(*supports):
    return SimpleNamespace(status=Status.CORROBORATED, candidate=None,
                           existence_record=SimpleNamespace(source_observation_ids=supports))


def pointing_at(item):
    return SimpleNamespace(status=Status.CANDIDATE, existence_record=None, candidate=item)


def test_a_candidate_contested_on_every_support_is_listed_and_changes_nothing_else():
    lost, kept, real = candidate("lost", "a", "b"), candidate("kept", "c", "d"), candidate("real", "e", "f")
    authority = build([lost, kept, real], {"d": pointing_at(kept), "e": proven("e", "f")})
    closure = authority.assess_visible_candidate_closure(SELECTOR)
    assert closure.raw_candidate_count == 1 and closure.unresolved_candidate_ids == ("kept",)
    rows = authority.visible_contested_candidate_groups(SELECTOR)
    assert [(r["candidate_id"], r["source_observation_ids"], r["candidate_status"]) for r in rows] == [
        ("lost", ["a", "b"], "contested_every_support")]
    assert rows[0]["structural_pattern"] == "pattern-lost"


@pytest.mark.parametrize("order", [(0, 1), (1, 0)])
def test_the_list_does_not_depend_on_candidate_order(order):
    items = [candidate("y", "c", "d"), candidate("x", "a", "b")]
    authority = build([items[i] for i in order], {})
    assert [r["candidate_id"] for r in authority.visible_contested_candidate_groups(SELECTOR)] == ["x", "y"]


def test_nothing_contested_gives_an_empty_list():
    item = candidate("kept", "a", "b")
    authority = build([item], {"a": pointing_at(item)})
    assert authority.visible_contested_candidate_groups(SELECTOR) == ()


def test_an_unavailable_scope_is_refused():
    authority = build([], {})
    authority._source_visibility_authority = None
    with pytest.raises(RuntimeError):
        authority.visible_contested_candidate_groups(SELECTOR)
    with pytest.raises(TypeError):
        authority.visible_contested_candidate_groups("selector")
