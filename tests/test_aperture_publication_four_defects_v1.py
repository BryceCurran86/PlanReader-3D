"""Regression tests for the four defects of PR #4282's quantity-level aperture collapse, which this change removes.

The merged collapse (``apply_aperture_equivalence_publication`` behind three keywords of ``publish_live_opening_area_quantities``) had:

1. the surviving row was the FIRST SORTED member's, not the member with the strongest source evidence (AGENTS: never first/smallest);
2. the surviving quantity's ``input_entity_ids`` became the whole member tuple (the seal refuses it: exactly one canonical opening per
   quantity, and a quantity must also equal the owner's own recomputed one, byte for byte);
3. every ambiguous, unproven or unclassified quantity vanished (a customer row disappeared with no proof of a duplicate);
4. caller-supplied records and pair verdicts were trusted.

It could not be repaired in place (it receives only quantities: it cannot authenticate a verdict, and it cannot keep the canonical
inventory, which other publishers re-derive from the composition, consistent), so the composition-level, authority-reproving
``pb_live_opening_aperture_consolidation`` replaces it. These tests pin that each defect is closed, end to end through the existing
seal and customer-row functions, on synthetic compositions (default off: none of this changes a live output).
"""
from __future__ import annotations

from dataclasses import replace
import importlib.util
import inspect
from pathlib import Path
from types import SimpleNamespace

import pytest

import pb_live_opening_aperture_consolidation as consolidation
from pb_live_opening_aperture_consolidation import (
    AuthorityEvidenceProvider, consolidate_live_opening_apertures, publish_live_opening_area_quantities_with_aperture_consolidation,
)
from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_aperture_equivalence_shadow import DISTINCT, OVERLAPPING, UNPROVEN
from pb_physical_opening_authority import _PARTITION_RECEIPT_SEAL, PhysicalOpeningPartitionReceipt
from pb_source_closed_run_export import SourceClosedRunConflictError
from tests.test_live_opening_aperture_consolidation_v1 import (
    FakeProvider, SHA, _claim, _customer_rows, _sealed, composition, opening, overlapping, run,
)

ROOT = Path(consolidation.__file__).parent


def _sealed_ids(comp):
    return sorted(q.object_identity_refs[0] for q in _sealed(comp).quantities)


def _customer_ids(comp):
    return sorted(r["canonical_entity_ids"][0] for r in _customer_rows(comp))


# --------------------------------------------------------------------------------------- the removed collapse stays removed
def test_the_quantity_level_collapse_and_its_caller_verdict_channel_are_gone():
    assert set(inspect.signature(publish_live_opening_area_quantities).parameters) == {"composition"}
    assert importlib.util.find_spec("pb_live_opening_aperture_equivalence_publication") is None
    forbidden = ("apply_aperture_equivalence_publication", "aperture_equivalence_publication_shadow", "aperture_verdicts")
    offenders = sorted(p.name for p in ROOT.glob("pb_*.py") if any(word in p.read_text(encoding="utf-8", errors="ignore") for word in forbidden))
    assert offenders == [], offenders


def test_the_public_api_accepts_no_verdict_record_receipt_or_provider():
    expected = {"source_visibility_producer", "wall_opening_composition", "composition", "enabled"}
    for function in (consolidate_live_opening_apertures, publish_live_opening_area_quantities_with_aperture_consolidation):
        assert set(inspect.signature(function).parameters) == expected
    with pytest.raises(TypeError):                              # a caller cannot smuggle one in by keyword either
        consolidate_live_opening_apertures(composition=composition(opening("a")), enabled=True, evidence_provider=FakeProvider())  # type: ignore[call-arg]
    with pytest.raises(TypeError):
        consolidate_live_opening_apertures(composition=composition(opening("a")), enabled=True, aperture_verdicts=())  # type: ignore[call-arg]


def test_only_the_shadow_and_the_consumer_name_the_pair_verdict_type():
    importers = sorted(p.name for p in ROOT.glob("pb_*.py") if "PairVerdict" in p.read_text(encoding="utf-8", errors="ignore"))
    assert importers == ["pb_live_opening_aperture_consolidation.py", "pb_opening_aperture_equivalence_shadow.py"], importers


# --------------------------------------------------------------------------------------- defect 1: survivor by evidence, not order
@pytest.mark.parametrize("owner_id, other_id", [("a", "z"), ("z", "a")])
def test_the_survivor_is_the_evidence_owner_never_the_first_sorted_member(owner_id, other_id):
    comp = composition(opening(owner_id, ("o1", "o2")), opening(other_id, ("o1",)))
    consolidated = run(comp, FakeProvider(overlapping(owner_id, other_id))).composition
    assert _sealed_ids(consolidated) == _customer_ids(consolidated) == [owner_id]


@pytest.mark.parametrize("sets", [(("o1", "o2"), ("o1", "o2")), (("o1", "o2"), ("o1", "o3")), (("o1",), ("o2",))])
def test_with_no_order_independent_owner_nothing_is_chosen_and_both_rows_publish(sets):
    comp = composition(opening("a", sets[0]), opening("b", sets[1]))
    result = run(comp, FakeProvider(overlapping("a", "b")))
    assert result.composition is comp and result.consolidated == ()
    assert _sealed_ids(result.composition) == _customer_ids(result.composition) == ["a", "b"]


# --------------------------------------------------------------------------------------- defect 2: exactly one physical opening id
def test_every_sealed_quantity_references_exactly_one_physical_opening_and_is_the_owners_own():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)), opening("c", ("p1", "p2"), figured="figured-2"),
                       opening("d", ("p1",), figured="figured-2"))
    provider = FakeProvider({**overlapping("a", "b"), **overlapping("c", "d")}, figures={"c": ("fig-2",), "d": ("fig-2",)},
                            hosts={"c": "host-B", "d": "host-B"})
    baseline = {q.input_entity_ids[0]: q for q in publish_live_opening_area_quantities(comp)}
    consolidated = run(comp, provider).composition
    published = publish_live_opening_area_quantities(consolidated)
    assert all(len(q.input_entity_ids) == 1 for q in published)
    assert all(q == baseline[q.input_entity_ids[0]] and q.to_dict() == baseline[q.input_entity_ids[0]].to_dict() for q in published)
    assert all(len(s.object_identity_refs) == 1 for s in _sealed(consolidated).quantities)
    assert _sealed_ids(consolidated) == _customer_ids(consolidated) == ["a", "c"]


def test_the_seal_refuses_what_the_removed_collapse_published():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    owner = publish_live_opening_area_quantities(comp)[0]
    from pb_live_opening_source_closed_export import seal_live_opening_area_claim_run

    def seal(quantity):
        claim = replace(_claim(comp), opening_quantity_evidence=(quantity,))
        return seal_live_opening_area_claim_run(claim, workspace_id=7, project_id="synthetic-project")

    with pytest.raises(SourceClosedRunConflictError, match="exactly one canonical opening"):
        seal(replace(owner, input_entity_ids=("a", "b")))                                       # the whole member tuple
    with pytest.raises(SourceClosedRunConflictError, match="does not match current physical source"):
        seal(replace(owner, metadata={**owner.metadata, "aperture_class_id": "x", "can_issue_firm_quantity": False}))   # rewritten metadata
    with pytest.raises(SourceClosedRunConflictError, match="does not match current physical source"):
        seal(replace(owner, evidence_ids=(*owner.evidence_ids, "receipt-x")))                    # merged evidence ids
    assert [s.object_identity_refs for s in seal(owner).quantities] == [("a",)]                  # the owner's own row seals


# --------------------------------------------------------------------------------------- defect 3: ambiguity preserves rows
@pytest.mark.parametrize("verdicts, figures, hosts", [
    (overlapping("a", "b"), {"a": ("fig-1",), "b": ("fig-2",)}, {}),                          # overlapping, different printed figure
    (overlapping("a", "b"), {"a": (), "b": ()}, {}),                                          # overlapping, no figure evidence
    (overlapping("a", "b"), {}, {"a": "host-A", "b": "host-B"}),                              # overlapping, different physical host
    (overlapping("a", "b"), {}, {"a": "host-A", "b": None}),                                  # overlapping, host unknown on a side
    ({("a", "b"): UNPROVEN}, {}, {}),                                                         # the authority cannot say
])
def test_an_ambiguous_pair_keeps_every_row_through_the_seal_and_the_customer_output(verdicts, figures, hosts):
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    result = run(comp, FakeProvider(verdicts, figures, hosts))
    assert result.composition is comp and result.consolidated == ()
    assert {m for r in result.unconsolidated for m in r.member_physical_opening_ids} == {"a", "b"}     # ambiguity is recorded
    assert _sealed_ids(result.composition) == _customer_ids(result.composition) == ["a", "b"]


def test_an_opening_outside_every_class_or_not_reproven_keeps_its_row():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)), opening("solo", ("q1",), figured="figured-3"),
                       opening("unseen", ("r1",), figured="figured-4"))
    provider = FakeProvider({**overlapping("a", "b")}, figures={"solo": ("fig-3",)}, hosts={"solo": "host-C"}, not_reproven={"unseen"})
    result = run(comp, provider)
    assert result.dropped_physical_opening_ids == ("b",) and result.not_reproven_physical_opening_ids == ("unseen",)
    assert _sealed_ids(result.composition) == _customer_ids(result.composition) == ["a", "solo", "unseen"]


def test_nothing_but_the_proven_duplicate_ever_disappears():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)), opening("solo", ("q1",), figured="figured-3"))
    published, result = consolidation._publish_with_provider(
        comp, FakeProvider(overlapping("a", "b"), figures={"solo": ("fig-3",)}, hosts={"solo": "host-C"}), True)
    before = {q.input_entity_ids[0] for q in publish_live_opening_area_quantities(comp)}
    assert {q.input_entity_ids[0] for q in published} == before - set(result.dropped_physical_opening_ids) == {"a", "solo"}


# --------------------------------------------------------------------------------------- defect 4: verdicts are authenticated
def _receipt(partition, *, status=EvidenceResolutionStatus.CORROBORATED, receipt_id="r-1"):
    return PhysicalOpeningPartitionReceipt(
        receipt_id=receipt_id, status=status, partition=partition, basis="native_aperture_extents", reason_codes=(),
        left_record_id="a", right_record_id="b", document_id="doc-1", revision_id="rev-1", source_sha256=SHA, snapshot_id="snap-1",
        page_id="3", left_viewport_id=None, right_viewport_id=None, left_source_observation_ids=("o1", "o2"),
        right_source_observation_ids=("o1",), shared_source_observation_ids=("o1",), left_extent=(0.0, 0.0, 1.0, 1.0),
        right_extent=(0.0, 0.0, 1.0, 1.0), producer_method="m", producer_version="1", producer_generation=1, _seal=_PARTITION_RECEIPT_SEAL)


class _Authority:
    """Looks like the authority's pair interface; each answer is controlled by the test."""

    def __init__(self, receipt, verifies=True, raises=False):
        self.receipt, self.verifies, self.raises, self.calls = receipt, verifies, raises, []

    def partition_receipt(self, left, right):
        if self.raises:
            raise RuntimeError("authority failure")
        self.calls.append(("partition_receipt", left, right))
        return self.receipt

    def verify_partition_receipt(self, receipt, left, right):
        self.calls.append(("verify_partition_receipt", receipt, left, right))
        return self.verifies


def _provider(authority, selectors=("sel-a", "sel-b")):
    provider = object.__new__(AuthorityEvidenceProvider)
    provider._authority = authority
    provider._selectors = {"a": selectors[0], "b": selectors[1]}
    return provider


def _verdict(authority, **kwargs):
    a, b = opening("a", ("o1", "o2")), opening("b", ("o1",))
    return _provider(authority, **kwargs).verdict(a, b)


@pytest.mark.parametrize("partition, status, expected", [
    ("overlapping_extent", EvidenceResolutionStatus.CONFLICT, OVERLAPPING),
    ("disjoint", EvidenceResolutionStatus.CORROBORATED, DISTINCT),
    ("partitioned", EvidenceResolutionStatus.CORROBORATED, DISTINCT),
    ("disjoint", EvidenceResolutionStatus.ABSTAINED, UNPROVEN),                                  # not corroborated: never distinct
    ("unproven", EvidenceResolutionStatus.ABSTAINED, UNPROVEN),
    ("same_record", EvidenceResolutionStatus.CORROBORATED, UNPROVEN),
    ("not_applicable", EvidenceResolutionStatus.ABSTAINED, UNPROVEN),
])
def test_a_verified_receipt_is_mapped_to_the_authoritys_own_verdict(partition, status, expected):
    assert _verdict(_Authority(_receipt(partition, status=status))) == (expected, "r-1")


def test_a_receipt_the_authority_does_not_verify_is_unproven_and_never_makes_anything_distinct():
    for partition in ("overlapping_extent", "disjoint", "partitioned"):
        authority = _Authority(_receipt(partition), verifies=False)
        assert _verdict(authority) == (UNPROVEN, "")
        assert [call[0] for call in authority.calls] == ["partition_receipt", "verify_partition_receipt"]    # it was asked, then refused


def test_a_forged_or_foreign_receipt_is_unproven():
    forged = SimpleNamespace(receipt_id="r-1", partition="disjoint", is_physically_distinct=True, grants_quantity=False,
                             grants_firm_authority=False)                                         # right shape, not an issued receipt
    assert _verdict(_Authority(forged, verifies=True)) == (UNPROVEN, "")
    assert _verdict(_Authority(None, verifies=True)) == (UNPROVEN, "")
    assert _verdict(_Authority(_receipt("disjoint"), raises=True)) == (UNPROVEN, "")              # an authority failure never becomes a verdict


def test_a_pair_without_a_reproven_selector_is_unproven():
    a, b = opening("a", ("o1", "o2")), opening("b", ("o1",))
    provider = _provider(_Authority(_receipt("overlapping_extent")))
    provider._selectors.pop("b")                                                                 # b was never re-proven
    assert provider.verdict(a, b) == (UNPROVEN, "")


def test_an_object_that_is_not_the_physical_authority_reproves_nothing():
    provider = _provider(_Authority(_receipt("overlapping_extent")))
    provider._traces, provider._labels = {}, SimpleNamespace()
    assert provider.reproven(opening("a", ("o1", "o2"))) is False


def test_the_record_comes_from_producer_evidence_never_from_the_caller():
    provider = _provider(_Authority(_receipt("disjoint")))
    provider._labels = SimpleNamespace(publish_scope=lambda selector: SimpleNamespace(
        evidence=SimpleNamespace(source_text_observation_ids=("w2", "w1"))))
    provider._traces = {"a": SimpleNamespace(member_wall_candidate_ids=("c2", "c1"))}
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    quantities = {q.input_entity_ids[0]: q for q in publish_live_opening_area_quantities(comp)}
    a, b = (o for o in comp.canonical_openings)
    record_a = provider.record(a, quantities["a"])
    assert (record_a.record_id, record_a.figure_key, record_a.host_key) == ("a", ("w1", "w2"), "c1|c2")
    assert record_a.area_m2 == float(quantities["a"].value) and record_a.receipt_ids == (quantities["a"].quantity_id,)
    assert record_a.scope_key == "doc-1|rev-1|snap-1|3"
    assert provider.record(b, quantities["b"]).host_key is None                                    # no host trace: unknown, never guessed
    provider._labels = SimpleNamespace(publish_scope=lambda selector: SimpleNamespace(evidence=None))
    assert provider.record(a, quantities["a"]).figure_key == ()                                    # no printed-figure evidence: empty key


def test_an_authority_that_fails_never_consolidates_through_the_whole_consumer():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))

    class Failing(FakeProvider):
        def verdict(self, left, right):
            return UNPROVEN, ""

    result = run(comp, Failing())
    assert result.consolidated == () and result.composition is comp
    assert _sealed_ids(result.composition) == _customer_ids(result.composition) == ["a", "b"]
