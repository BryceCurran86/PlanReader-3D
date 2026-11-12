"""Default-off consumer: one published opening-area quantity per source-proven physical aperture (option A).

The consumer takes every verdict from the producer-owned physical-opening authority; here a fake provider supplies those verdicts so the
rules can be proven on synthetic compositions. It is not a geometric hypothesis (the geometry lives in the authority), so there is no
translation/rotation/scale case; input-order, split, replay and no-mutation invariance are tested instead.
"""
from __future__ import annotations

from dataclasses import fields, replace
import itertools
from pathlib import Path
from types import MappingProxyType
import random

import pytest

import pb_live_opening_aperture_consolidation as consolidation
from pb_live_opening_aperture_consolidation import (
    AMBIGUOUS, CONSOLIDATED, DISABLED, NOT_REPROVEN, NO_OWNER, QUANTITIES_DIFFER, ApertureConsolidationInvariantError,
    consolidate_live_opening_apertures, derive_composition, evidence_owner, plan_consolidation,
    publish_live_opening_area_quantities_with_aperture_consolidation,
)
from pb_live_opening_area_quantity_publication import publish_live_opening_area_quantities
from pb_live_physical_opening_void_composition import LiveCanonicalOpeningObject, LivePhysicalOpeningVoidComposition
from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_aperture_equivalence_shadow import DISTINCT, OVERLAPPING, UNPROVEN

SHA = "a" * 64


def opening(canonical_id, obs=("o1",), *, kind="window", area_m2=2.172, page="3", figured="figured-1", basis="figured_opening_label"):
    evidence_ids = tuple(v for v in (canonical_id, *obs, "host-binding-1", "host-frame-1", figured) if v)
    return LiveCanonicalOpeningObject(
        canonical_opening_id=canonical_id, physical_opening_id=canonical_id, document_id="doc-1", revision_id="rev-1", source_sha256=SHA,
        snapshot_id="snap-1", page_id=page, viewport_id="vp-floor-1", semantic_class="physical_opening",
        structural_pattern="gap_corroborated_window_jamb_pair", representative_observation_id=obs[0], source_observation_ids=tuple(obs),
        source_lineage_root_ids=("root-1",), source_geometries=((0.0, 0.0, 1.0, 0.0),), host_wall_id="wall-1",
        host_binding_record_id="host-binding-1", host_frame_record_id="host-frame-1", wall_local_frame_id=None, profile_kind=None,
        coordinate_unit=None, u0=None, u1=None, z0=None, z1=None, width_m=None, height_m=None, area_m2=area_m2, area_basis=basis,
        figured_area_record_id=figured, opening_void_record_id=None, opening_universe_record_id=None, width_record_id=None,
        height_record_id=None, vertical_placement_record_id=None, scale_record_id=None, schedule_binding_record_id=None,
        opening_kind=kind, type_mark=None, schedule_page_id=None, schedule_declared_width_mm=None, schedule_declared_height_mm=None,
        schedule_declared_count=None, schedule_count_explicit=False, schedule_row_observation_ids=(), tag_observation_id=None,
        evidence_ids=evidence_ids, geometry_complete=False)


def composition(*openings):
    return LivePhysicalOpeningVoidComposition(
        revision_id="rev-1", status=EvidenceResolutionStatus.ABSTAINED, reason_codes=("partial",), traces=(),
        physical_opening_void_authorities=MappingProxyType({}), void_selectors=MappingProxyType({}), canonical_openings=tuple(openings))


class FakeProvider:
    """The physical authority's answers: pair verdicts, printed figure and physical host per opening."""

    def __init__(self, verdicts=None, figures=None, hosts=None, not_reproven=(), default=DISTINCT):
        self.verdicts = {frozenset(k): v for k, v in (verdicts or {}).items()}
        self.figures, self.hosts, self.not_reproven, self.default = figures or {}, hosts or {}, set(not_reproven), default
        self.asked = []

    def reproven(self, o):
        return o.physical_opening_id not in self.not_reproven

    def record(self, o, q):
        from pb_opening_aperture_equivalence_shadow import ApertureRecord
        i = o.physical_opening_id
        return ApertureRecord(i, f"{o.document_id}|{o.revision_id}|{o.snapshot_id}|{o.page_id}", self.figures.get(i, ("fig-1",)),
                              float(q.value), self.hosts.get(i, "host-A"), (q.quantity_id,))

    def verdict(self, left, right):
        key = frozenset((left.physical_opening_id, right.physical_opening_id))
        self.asked.append(key)
        return self.verdicts.get(key, self.default), "receipt:" + "|".join(sorted(key))


def overlapping(*ids):
    return {pair: OVERLAPPING for pair in itertools.combinations(sorted(ids), 2)}


def run(comp, provider, enabled=True):
    # the PRIVATE core: the public entry points accept no provider, so tests substitute the authority's answers here
    return consolidation._consolidate_with_provider(comp, provider, enabled)


def run_publish(comp, provider, enabled=True):
    return consolidation._publish_with_provider(comp, provider, enabled)


def ids_of(quantities):
    return sorted(q.input_entity_ids[0] for q in quantities)


# ------------------------------------------------------------------------------------------------ off / strictness
def test_disabled_by_default_returns_the_same_composition_and_asks_nothing():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    provider = FakeProvider(overlapping("a", "b"))
    result = consolidate_live_opening_apertures(composition=comp)             # the PUBLIC API, default off: no provider is even built
    assert result.enabled is False and result.composition is comp and result.consolidated == () and result.reason_codes == (DISABLED,)
    assert run(comp, provider, enabled=False).composition is comp and provider.asked == []
    quantities, record = publish_live_opening_area_quantities_with_aperture_consolidation(composition=comp)
    assert quantities == publish_live_opening_area_quantities(comp) and record.composition is comp


@pytest.mark.parametrize("bad", [1, 0, "yes", None, 1.0])
def test_enabled_must_be_a_strict_bool(bad):
    with pytest.raises(ValueError):
        consolidate_live_opening_apertures(composition=composition(opening("a")), enabled=bad)
    with pytest.raises(ValueError):
        run(composition(opening("a")), FakeProvider(), enabled=bad)


def test_a_non_composition_is_refused():
    with pytest.raises(TypeError):
        consolidate_live_opening_apertures(composition=object())
    with pytest.raises(TypeError):
        run(object(), FakeProvider())


def test_an_enabled_call_without_the_producer_owned_objects_fails_closed():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    with pytest.raises(TypeError):                                              # no source producer, no wall-opening composition
        consolidate_live_opening_apertures(composition=comp, enabled=True)
    with pytest.raises(TypeError):                                              # stand-ins are refused by exact type
        consolidate_live_opening_apertures(
            source_visibility_producer=object(), wall_opening_composition=object(), composition=comp, enabled=True)
    with pytest.raises(TypeError):
        run(comp, None)                                                         # the private core also refuses a missing provider


def test_the_result_grants_no_authority():
    result = run(composition(opening("a", ("o1", "o2")), opening("b", ("o1",))), FakeProvider(overlapping("a", "b")))
    assert result.grants_quantity is False and result.grants_firm_authority is False


# ------------------------------------------------------------------------------------------------ positives
def test_an_equivalent_pair_with_an_evidence_owner_publishes_one_quantity_and_keeps_both_members():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    baseline = publish_live_opening_area_quantities(comp)
    assert ids_of(baseline) == ["a", "b"]
    quantities, result = run_publish(comp, FakeProvider(overlapping("a", "b")))
    assert ids_of(quantities) == ["a"]
    assert quantities == tuple(q for q in baseline if q.input_entity_ids[0] == "a")           # the owner's own row, byte for byte
    (aperture,) = result.consolidated
    assert aperture.owner_physical_opening_id == "a" and aperture.dropped_physical_opening_ids == ("b",)
    assert [m.physical_opening_id for m in aperture.members] == ["a", "b"]                       # every member retained
    assert {m.physical_opening_id: m.source_observation_ids for m in aperture.members} == {"a": ("o1", "o2"), "b": ("o1",)}
    assert {m.quantity_id for m in aperture.members} == {q.quantity_id for q in baseline}
    assert all(m.partition_receipt_ids == ("receipt:a|b",) for m in aperture.members)
    assert result.reason_codes == (CONSOLIDATED,) and aperture.area_m2 == pytest.approx(2.172)
    assert [o.physical_opening_id for o in result.composition.canonical_openings] == ["a"]


@pytest.mark.parametrize("owner_id, other_id", [("a", "z"), ("z", "a")])
def test_the_owner_never_depends_on_id_order(owner_id, other_id):
    comp = composition(opening(owner_id, ("o1", "o2")), opening(other_id, ("o1",)))
    result = run(comp, FakeProvider(overlapping(owner_id, other_id)))
    assert result.consolidated[0].owner_physical_opening_id == owner_id


def test_a_three_member_class_with_one_strict_superset_keeps_only_that_member():
    comp = composition(opening("a", ("o1", "o2", "o3")), opening("b", ("o1", "o2")), opening("c", ("o1", "o3")))
    result = run(comp, FakeProvider(overlapping("a", "b", "c")))
    (aperture,) = result.consolidated
    assert aperture.owner_physical_opening_id == "a" and aperture.dropped_physical_opening_ids == ("b", "c")
    assert [o.physical_opening_id for o in result.composition.canonical_openings] == ["a"]
    assert all(len(m.partition_receipt_ids) == 2 for m in aperture.members)                       # each member took part in two pairs


def test_two_independent_classes_are_each_reduced():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)), opening("c", ("p1", "p2"), figured="figured-2"),
                       opening("d", ("p1",), figured="figured-2"))
    provider = FakeProvider({**overlapping("a", "b"), **overlapping("c", "d")}, figures={"c": ("fig-2",), "d": ("fig-2",)}, hosts={"c": "host-B", "d": "host-B"})
    result = run(comp, provider)
    assert sorted(a.owner_physical_opening_id for a in result.consolidated) == ["a", "c"]
    assert result.dropped_physical_opening_ids == ("b", "d")
    assert ids_of(publish_live_opening_area_quantities(result.composition)) == ["a", "c"]


# ------------------------------------------------------------------------------------------------ negatives and abstentions
def test_symmetric_members_are_not_consolidated_and_every_member_still_publishes():
    for sets in ((("o1", "o2"), ("o1", "o2")), (("o1", "o2"), ("o1", "o3")), (("o1",), ("o2",))):
        comp = composition(opening("a", sets[0]), opening("b", sets[1]))
        result = run(comp, FakeProvider(overlapping("a", "b")))
        assert result.composition is comp and result.consolidated == ()
        (rest,) = result.unconsolidated
        assert rest.member_physical_opening_ids == ("a", "b") and rest.reason_codes == (NO_OWNER,)
        assert ids_of(publish_live_opening_area_quantities(result.composition)) == ["a", "b"]


def test_a_three_member_tie_for_the_largest_set_has_no_owner():
    comp = composition(opening("a", ("o1", "o2", "o3")), opening("b", ("o1", "o2", "o4")), opening("c", ("o1",)))
    result = run(comp, FakeProvider(overlapping("a", "b", "c")))
    assert result.consolidated == () and result.unconsolidated[0].reason_codes == (NO_OWNER,) and result.composition is comp


def test_a_separate_aperture_with_the_same_figure_area_and_host_is_never_merged():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    result = run(comp, FakeProvider({("a", "b"): DISTINCT}))                                       # the authority proves them apart
    assert result.consolidated == () and result.unconsolidated == () and result.composition is comp


@pytest.mark.parametrize("verdicts, figures, hosts", [
    (overlapping("a", "b"), {"a": ("fig-1",), "b": ("fig-2",)}, {}),                                # overlapping, different printed figure
    (overlapping("a", "b"), {"a": (), "b": ()}, {}),                                                # overlapping, no figure evidence
    (overlapping("a", "b"), {}, {"a": "host-A", "b": "host-B"}),                                    # overlapping, different physical host
    (overlapping("a", "b"), {}, {"a": "host-A", "b": None}),                                        # overlapping, host unknown on a side
    ({("a", "b"): UNPROVEN}, {}, {}),                                                               # the authority cannot say
])
def test_ambiguous_equivalence_never_consolidates_and_is_recorded(verdicts, figures, hosts):
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    result = run(comp, FakeProvider(verdicts, figures, hosts))
    assert result.consolidated == () and result.composition is comp
    assert result.unconsolidated and all(r.reason_codes[0] == AMBIGUOUS for r in result.unconsolidated)
    assert {m for r in result.unconsolidated for m in r.member_physical_opening_ids} == {"a", "b"}          # ambiguity never disappears
    assert ids_of(publish_live_opening_area_quantities(result.composition)) == ["a", "b"]                   # and both rows still publish


def test_overlapping_apertures_with_different_areas_are_never_merged():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",), area_m2=2.5))
    result = run(comp, FakeProvider(overlapping("a", "b")))
    assert result.consolidated == () and result.composition is comp
    assert result.unconsolidated and all(r.reason_codes[0] == AMBIGUOUS for r in result.unconsolidated)


def test_members_whose_quantities_differ_are_not_consolidated():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",), kind="door"))                # same area, different opening kind
    assert len({q.metadata["opening_kind"] for q in publish_live_opening_area_quantities(comp)}) == 2
    result = run(comp, FakeProvider(overlapping("a", "b")))
    assert result.consolidated == () and result.unconsolidated[0].reason_codes == (QUANTITIES_DIFFER,) and result.composition is comp


def test_an_opening_the_authority_does_not_reprove_is_left_alone_and_recorded():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    result = run(comp, FakeProvider(overlapping("a", "b"), not_reproven={"b"}))
    assert result.consolidated == () and result.composition is comp
    assert result.not_reproven_physical_opening_ids == ("b",) and NOT_REPROVEN in result.reason_codes


def test_an_unmeasured_opening_is_not_part_of_any_class():
    unmeasured = opening("b", ("o1",), kind=None, area_m2=None, figured=None)
    comp = composition(opening("a", ("o1", "o2")), unmeasured)
    assert ids_of(publish_live_opening_area_quantities(comp)) == ["a"]
    provider = FakeProvider(overlapping("a", "b"))
    result = run(comp, provider)
    assert result.consolidated == () and result.composition is comp and provider.asked == []


def test_openings_on_different_pages_are_never_related_or_compared():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",), page="5"))
    provider = FakeProvider(overlapping("a", "b"))
    result = run(comp, provider)
    assert result.consolidated == () and result.composition is comp and provider.asked == []


# ------------------------------------------------------------------------------------------------ invariance
def test_input_order_and_replay_do_not_change_the_result():
    members = [opening("a", ("o1", "o2", "o3")), opening("b", ("o1", "o2")), opening("c", ("o1",)),
               opening("x", ("p1", "p2"), figured="figured-2"), opening("y", ("p1",), figured="figured-2"), opening("lone", ("q1",), figured="figured-3")]
    provider = lambda: FakeProvider({**overlapping("a", "b", "c"), **overlapping("x", "y")},
                                    figures={"x": ("fig-2",), "y": ("fig-2",), "lone": ("fig-3",)}, hosts={"x": "host-B", "y": "host-B", "lone": "host-C"})
    reference = run(composition(*members), provider())
    assert run(composition(*members), provider()) == reference                                      # deterministic replay
    rng = random.Random(7)
    for _ in range(15):
        shuffled = members[:]
        rng.shuffle(shuffled)
        again = run(composition(*shuffled), provider())
        assert (again.consolidated, again.unconsolidated, again.dropped_physical_opening_ids) == (
            reference.consolidated, reference.unconsolidated, reference.dropped_physical_opening_ids)
        assert sorted(o.physical_opening_id for o in again.composition.canonical_openings) == ["a", "lone", "x"]


def test_the_input_composition_is_never_mutated():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    before = (comp.canonical_openings, comp.reason_codes, comp.status)
    result = run(comp, FakeProvider(overlapping("a", "b")))
    assert (comp.canonical_openings, comp.reason_codes, comp.status) == before and len(comp.canonical_openings) == 2
    assert result.composition is not comp and result.composition.reason_codes == comp.reason_codes and result.composition.status == comp.status


def test_derive_composition_drops_only_the_named_openings_and_returns_the_same_object_for_none():
    comp = composition(opening("a"), opening("b", ("o1", "o9")), opening("c", ("o7",)))
    assert derive_composition(comp, ()) is comp
    assert [o.physical_opening_id for o in derive_composition(comp, ("b",)).canonical_openings] == ["a", "c"]
    assert derive_composition(comp, ("nope",)).canonical_openings == comp.canonical_openings


# ------------------------------------------------------------------------------------------------ publication invariant
def test_the_publication_invariant_fails_closed_if_anything_else_would_disappear(monkeypatch):
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)), opening("c", ("z1",), figured="figured-3"))
    provider = FakeProvider({**overlapping("a", "b"), ("a", "c"): DISTINCT, ("b", "c"): DISTINCT}, figures={"c": ("fig-3",)}, hosts={"c": "host-C"})
    real = consolidation.derive_composition
    monkeypatch.setattr(consolidation, "derive_composition", lambda c, dropped: real(c, (*dropped, "c")))      # an extra member vanishes
    with pytest.raises(ApertureConsolidationInvariantError):
        run_publish(comp, provider)


# ------------------------------------------------------------------------------------------------ pure rules
def test_evidence_owner_is_a_unique_strict_superset_and_never_a_tie_break():
    assert evidence_owner({"a": ("1", "2"), "b": ("1",)}) == "a"
    assert evidence_owner({"b": ("1",), "a": ("1", "2")}) == "a"                                    # order-independent
    assert evidence_owner({"a": ("1", "2", "3"), "b": ("1", "2"), "c": ("1", "3")}) == "a"            # b and c incomparable is fine
    assert evidence_owner({"a": ("1", "2"), "b": ("1", "2")}) is None                               # equal sets
    assert evidence_owner({"a": ("1", "2"), "b": ("1", "3")}) is None                               # partial overlap
    assert evidence_owner({"a": ("1", "2", "3"), "b": ("1", "2", "4"), "c": ("1",)}) is None          # two largest, neither contains the other
    assert evidence_owner({"a": ("1",)}) is None                                                    # one member has nothing to own
    assert evidence_owner({}) is None
    assert evidence_owner({"a": (), "b": ("1",)}) == "b" and evidence_owner({"a": (), "b": ()}) is None


def test_plan_consolidation_ignores_single_member_classes():
    from pb_opening_aperture_equivalence_shadow import ApertureRecord, resolve_aperture_equivalence
    comp = composition(opening("a"), opening("b", ("p1",), figured="figured-2"))
    quantities = {q.input_entity_ids[0]: q for q in publish_live_opening_area_quantities(comp)}
    records = [ApertureRecord(i, "s", ("f-" + i,), float(quantities[i].value), "h", (quantities[i].quantity_id,)) for i in ("a", "b")]
    classes = resolve_aperture_equivalence(records, [consolidation.PairVerdict("a", "b", DISTINCT)], enabled=True)
    assert plan_consolidation(classes, {o.physical_opening_id: o for o in comp.canonical_openings}, quantities, {}) == ((), ())


# ------------------------------------------------------------------------------------------------ isolation
def test_nothing_in_production_imports_the_consumer():
    import ast
    root = Path(consolidation.__file__).parent
    me = Path(consolidation.__file__).name

    def imports_it(path):
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        names = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
        names |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
        return "pb_live_opening_aperture_consolidation" in names

    importers = sorted(p.name for p in root.glob("pb_*.py") if p.name != me and imports_it(p))
    assert importers == [], importers                                                               # wiring is a separate, reviewed step


def _quantity():
    return publish_live_opening_area_quantities(composition(opening("a")))[0]


@pytest.mark.parametrize("change", [
    {"authority": "another_authority"}, {"status": "another_status"}, {"family": "another_family"}, {"unit": "another_unit"}, {"value": 9.99},
])
def test_every_quantity_field_the_signature_names_decides_whether_two_quantities_agree(change):
    quantity = _quantity()
    assert consolidation._quantity_signature(replace(quantity, **change)) != consolidation._quantity_signature(quantity)


@pytest.mark.parametrize("key", ["area_basis", "opening_kind"])
def test_the_signature_reads_the_basis_and_kind_metadata(key):
    quantity = _quantity()
    other = replace(quantity, metadata={**quantity.metadata, key: "another"})
    assert consolidation._quantity_signature(other) != consolidation._quantity_signature(quantity)
    assert consolidation._quantity_signature(replace(quantity)) == consolidation._quantity_signature(quantity)


def test_a_members_receipts_are_only_those_of_pairs_inside_its_own_class():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)), opening("c", ("z1",), figured="figured-3"))
    provider = FakeProvider({**overlapping("a", "b"), ("a", "c"): DISTINCT, ("b", "c"): DISTINCT}, figures={"c": ("fig-3",)}, hosts={"c": "host-C"})
    (aperture,) = run(comp, provider).consolidated
    assert [m.partition_receipt_ids for m in aperture.members] == [("receipt:a|b",), ("receipt:a|b",)]       # a|c and b|c belong to no class
    receipts = {frozenset(("a", "b")): "r-ab", frozenset(("a", "c")): "r-ac"}
    from pb_opening_aperture_equivalence_shadow import ApertureRecord, PairVerdict, resolve_aperture_equivalence
    quantities = {q.input_entity_ids[0]: q for q in publish_live_opening_area_quantities(comp)}
    records = [ApertureRecord(i, "s", ("f1",) if i != "c" else ("f3",), float(quantities[i].value), "h" if i != "c" else "hc", ()) for i in ("a", "b", "c")]
    classes = resolve_aperture_equivalence(records, [PairVerdict("a", "b", OVERLAPPING), PairVerdict("a", "c", DISTINCT), PairVerdict("b", "c", DISTINCT)], enabled=True)
    planned, _ = plan_consolidation(classes, {o.physical_opening_id: o for o in comp.canonical_openings}, quantities, receipts)
    assert [m.partition_receipt_ids for m in planned[0].members] == [("r-ab",), ("r-ab",)]


# ------------------------------------------------------------------------------------------------ sealed / customer bijection
def _claim(comp):
    from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
    return LivePhysicalNetWallClaim(
        status=EvidenceResolutionStatus.ABSTAINED, reason_codes=(), quantity_m2=None, source_pages=(), canonical_walls=(),
        canonical_wall_status=EvidenceResolutionStatus.ABSTAINED, canonical_wall_reason_codes=(), canonical_wall_source_pages=(),
        unresolved_wall_candidate_ids=(), canonical_openings=comp.canonical_openings, canonical_rooms=(), canonical_floors=(),
        canonical_floor_status=EvidenceResolutionStatus.ABSTAINED, canonical_floor_reason_codes=(), canonical_floor_source_pages=(),
        canonical_room_status=EvidenceResolutionStatus.ABSTAINED, canonical_room_reason_codes=(), canonical_room_source_pages=(),
        external_wall_ids=(), evidence_ids=(), quantity_id=None, confidence=0.0, publication=None,
        opening_quantity_evidence=publish_live_opening_area_quantities(comp),
        opening_dimension_quantity_evidence=comp.physical_opening_dimension_quantities)


def _sealed(comp):
    from pb_live_opening_source_closed_export import seal_live_opening_area_claim_run
    return seal_live_opening_area_claim_run(_claim(comp), workspace_id=7, project_id="synthetic-project")


def _customer_rows(comp):
    from pb_live_opening_customer_projection import project_live_opening_customer_rows
    return project_live_opening_customer_rows(_claim(comp), workspace_id=7, project_id="synthetic-project")


def test_off_leaves_the_sealed_run_and_the_customer_rows_byte_identical():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    baseline_run, baseline_rows = _sealed(comp), _customer_rows(comp)
    result = run(comp, FakeProvider(overlapping("a", "b")), enabled=False)
    assert result.composition is comp
    assert _sealed(result.composition).fingerprint == baseline_run.fingerprint
    assert _customer_rows(result.composition) == baseline_rows
    assert len(baseline_run.quantities) == 2                                                          # the duplicate sale OFF still has


def test_on_seals_and_projects_exactly_one_row_for_the_one_aperture_and_it_is_the_owners_own_row():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    baseline_run, baseline_rows = _sealed(comp), _customer_rows(comp)
    consolidated = run(comp, FakeProvider(overlapping("a", "b"))).composition
    sealed, rows = _sealed(consolidated), _customer_rows(consolidated)
    assert [q.object_identity_refs for q in sealed.quantities] == [("a",)] and all(q.lineage_ok for q in sealed.quantities)
    owner_before = next(q for q in baseline_run.quantities if q.object_identity_refs == ("a",))
    assert sealed.quantities[0] == owner_before and sealed.quantities[0].to_dict() == owner_before.to_dict()          # the owner's sealed row, unchanged
    assert [r["canonical_entity_ids"] for r in rows] == [["a"]]
    assert tuple(rows) == tuple(r for r in baseline_rows if r["canonical_entity_ids"] == ["a"])                      # the owner's customer row, unchanged
    assert {r["quantity_id"] for r in rows} == {q.quantity_id for q in sealed.quantities} == {q.quantity_id for q in publish_live_opening_area_quantities(consolidated)}


def test_the_sealed_run_and_customer_rows_stay_one_to_one_with_the_published_quantities_after_consolidation():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)), opening("c", ("p1", "p2"), figured="figured-2"),
                       opening("d", ("p1",), figured="figured-2"), opening("lone", ("q1",), figured="figured-3"))
    provider = FakeProvider({**overlapping("a", "b"), **overlapping("c", "d")}, figures={"c": ("fig-2",), "d": ("fig-2",), "lone": ("fig-3",)},
                            hosts={"c": "host-B", "d": "host-B", "lone": "host-C"})
    consolidated = run(comp, provider).composition
    published = publish_live_opening_area_quantities(consolidated)
    sealed, rows = _sealed(consolidated), _customer_rows(consolidated)
    assert sorted(q.object_identity_refs[0] for q in sealed.quantities) == sorted(r["canonical_entity_ids"][0] for r in rows) == ["a", "c", "lone"]
    assert {q.quantity_id for q in published} == {q.quantity_id for q in sealed.quantities} == {r["quantity_id"] for r in rows}
    assert all(q.lineage_ok and not q.abstained for q in sealed.quantities)


def test_a_distinct_aperture_keeps_its_own_sealed_row_and_customer_row():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    consolidated = run(comp, FakeProvider({("a", "b"): DISTINCT})).composition                          # the authority proves them apart
    assert consolidated is comp
    assert sorted(q.object_identity_refs[0] for q in _sealed(consolidated).quantities) == ["a", "b"]
    assert sorted(r["canonical_entity_ids"][0] for r in _customer_rows(consolidated)) == ["a", "b"]


def test_a_conflicting_physical_host_keeps_both_rows():
    comp = composition(opening("a", ("o1", "o2")), opening("b", ("o1",)))
    result = run(comp, FakeProvider(overlapping("a", "b"), hosts={"a": "host-A", "b": "host-B"}))          # overlapping, but resting on different walls
    assert result.consolidated == () and result.composition is comp
    assert sorted(q.object_identity_refs[0] for q in _sealed(result.composition).quantities) == ["a", "b"]
