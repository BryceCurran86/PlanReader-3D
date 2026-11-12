"""Counterexamples for the merged default-off collapse inside ``publish_live_opening_area_quantities`` (#4282), and what the authority-reproving
consolidation does instead.

The collapse is default off, so none of this changes a live output today. These tests pin what would happen the moment it is switched on, using
only synthetic compositions and the existing seal/customer functions:

* the surviving row is the FIRST SORTED member's row, not the member with the strongest source evidence (AGENTS: never first/smallest);
* the surviving quantity's ``input_entity_ids`` becomes the whole member tuple, which the existing seal refuses (one physical opening per row);
* an ambiguous record publishes NOTHING, so a customer row can disappear without any proof the opening is a duplicate.
"""
from __future__ import annotations

import pytest

from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_opening_aperture_equivalence_shadow import ApertureRecord, DISTINCT, OVERLAPPING, PairVerdict
from tests.test_live_opening_aperture_consolidation_v1 import (
    FakeProvider, _claim, _sealed, composition, opening, overlapping, run,
)


def _records(comp, *, figure=("fig-1",), host="host-A"):
    quantities = {q.input_entity_ids[0]: q for q in publish_live_opening_area_quantities(comp)}
    return tuple(ApertureRecord(i, "doc|rev|snap|3", figure, float(q.value), host, (q.quantity_id,)) for i, q in sorted(quantities.items()))


def test_the_collapse_keeps_the_first_sorted_member_even_when_another_member_owns_the_evidence():
    # "z" holds the richer source evidence (a strict superset); "a" sorts first
    comp = composition(opening("a", ("o1",)), opening("z", ("o1", "o2")))
    collapsed = publish_live_opening_area_quantities(
        comp, aperture_equivalence_publication_shadow=True, aperture_records=_records(comp),
        aperture_verdicts=(PairVerdict("a", "z", OVERLAPPING),))
    assert len(collapsed) == 1
    assert collapsed[0].quantity_id == next(q for q in publish_live_opening_area_quantities(comp) if q.input_entity_ids == ("a",)).quantity_id
    # the authority-reproving consumer chooses by evidence, independent of ids
    consolidated = run(comp, FakeProvider(overlapping("a", "z"))).consolidated
    assert [c.owner_physical_opening_id for c in consolidated] == ["z"]


def test_the_collapsed_quantity_names_every_member_and_the_existing_seal_refuses_it():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    collapsed = publish_live_opening_area_quantities(
        comp, aperture_equivalence_publication_shadow=True, aperture_records=_records(comp),
        aperture_verdicts=(PairVerdict("a", "b", OVERLAPPING),))
    assert [q.input_entity_ids for q in collapsed] == [("a", "b")]                  # one row, two physical identities
    from dataclasses import replace
    from pb_live_opening_source_closed_export import seal_live_opening_area_claim_run
    claim = replace(_claim(comp), opening_quantity_evidence=collapsed)
    from pb_source_closed_run_export import SourceClosedRunConflictError
    with pytest.raises(SourceClosedRunConflictError, match="exactly one canonical opening"):                         # one owned opening per row
        seal_live_opening_area_claim_run(claim, workspace_id=7, project_id="synthetic-project")
    # the consolidation's output seals, and keeps exactly the owner's own row
    consolidated = run(comp, FakeProvider(overlapping("a", "b"))).composition
    assert [q.object_identity_refs for q in _sealed(consolidated).quantities] == [("a",)]


def test_an_ambiguous_record_vanishes_from_the_collapse_but_keeps_its_row_in_the_consolidation():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    ambiguous = (PairVerdict("a", "b", OVERLAPPING),)
    no_figure = tuple(ApertureRecord(r.record_id, r.scope_key, (), r.area_m2, r.host_key, r.receipt_ids) for r in _records(comp))
    collapsed = publish_live_opening_area_quantities(
        comp, aperture_equivalence_publication_shadow=True, aperture_records=no_figure, aperture_verdicts=ambiguous)
    assert collapsed == ()                                                           # both rows gone with no proof of a duplicate
    kept = run(comp, FakeProvider(overlapping("a", "b"), figures={"a": (), "b": ()}))
    assert kept.consolidated == () and [o.physical_opening_id for o in kept.composition.canonical_openings] == ["a", "b"]


def test_the_collapse_trusts_caller_verdicts_the_consolidation_reproves_them():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    forged = (PairVerdict("a", "b", OVERLAPPING),)                                   # nothing checks that the authority said so
    assert len(publish_live_opening_area_quantities(
        comp, aperture_equivalence_publication_shadow=True, aperture_records=_records(comp), aperture_verdicts=forged)) == 1
    # the consolidation only acts on what the authority's re-proven verdict says: here the authority proves them apart
    assert run(comp, FakeProvider({("a", "b"): DISTINCT})).consolidated == ()
