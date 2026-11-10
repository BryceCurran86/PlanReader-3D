"""Synthetic proof for the shadow-only aperture equivalence of sealed opening records."""
from __future__ import annotations

import copy
import itertools
import random

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
import pb_opening_aperture_equivalence_shadow as ae
from pb_opening_aperture_equivalence_shadow import ApertureRecord, PairVerdict, classes_by_record, resolve_aperture_equivalence

CAND = EvidenceResolutionStatus.CANDIDATE
ABST = EvidenceResolutionStatus.ABSTAINED


def rec(rid, figure=("lbl-a",), area=1.5, host="wall-1", scope="doc|rev|snap|p3", receipts=None):
    return ApertureRecord(rid, scope, tuple(figure), area, host, tuple(receipts if receipts is not None else (f"r-{rid}",)))


def verdict(a, b, v):
    return PairVerdict(a, b, v)


def run(records, verdicts, enabled=True):
    return resolve_aperture_equivalence(records, verdicts, enabled=enabled)


def partition(classes):
    return sorted(c.member_ids for c in classes)


# ------------------------------------------------------------------------------------------------ positives
def test_two_overlapping_records_with_one_figure_one_area_one_host_are_one_aperture():
    classes = run([rec("a"), rec("b")], [verdict("a", "b", "overlapping")])
    (c,) = classes
    assert c.status is CAND and c.reason_codes == (ae.CONSOLIDATED,) and c.member_ids == ("a", "b") and c.is_consolidated
    assert c.area_m2 == 1.5 and set(c.receipt_ids) == {"r-a", "r-b"}
    assert c.status is not EvidenceResolutionStatus.CORROBORATED


def test_a_pair_the_authority_proves_apart_stays_two_records_even_with_one_printed_figure():
    classes = run([rec("a"), rec("b")], [verdict("a", "b", "distinct")])
    assert partition(classes) == [("a",), ("b",)] and all(c.reason_codes == (ae.SINGLE,) for c in classes)


def test_three_mutually_overlapping_records_are_one_class():
    v = [verdict("a", "b", "overlapping"), verdict("b", "c", "overlapping"), verdict("a", "c", "overlapping")]
    (c,) = run([rec("a"), rec("b"), rec("c")], v)
    assert c.member_ids == ("a", "b", "c") and c.is_consolidated


def test_a_record_with_no_relation_is_a_single_class():
    classes = run([rec("a"), rec("b"), rec("solo", figure=("lbl-z",))], [verdict("a", "b", "overlapping")])
    assert partition(classes) == [("a", "b"), ("solo",)]
    assert classes_by_record(classes)["solo"].reason_codes == (ae.SINGLE,)


def test_every_record_is_covered_exactly_once():
    records = [rec(f"r{i}", figure=(f"l{i // 2}",)) for i in range(8)]
    v = [verdict(f"r{i}", f"r{i + 1}", "overlapping") for i in range(0, 8, 2)]
    classes = run(records, v)
    members = [m for c in classes for m in c.member_ids]
    assert sorted(members) == sorted(r.record_id for r in records) and len(members) == len(set(members))
    assert partition(classes) == [("r0", "r1"), ("r2", "r3"), ("r4", "r5"), ("r6", "r7")]


# ------------------------------------------------------------------------------------------------ nothing else makes records one aperture
@pytest.mark.parametrize("other", [
    dict(area=1.6),                                   # a different area
    dict(figure=("lbl-b",)),                          # a different printed figure
    dict(host="wall-2"),                              # a different host
    dict(host=None),                                  # no host at all
])
def test_overlap_with_different_evidence_is_ambiguous_for_both_records(other):
    classes = run([rec("a"), rec("b", **other)], [verdict("a", "b", "overlapping")])
    assert partition(classes) == [("a",), ("b",)] and all(c.status is ABST for c in classes)
    assert all(ae.AMBIGUOUS_EVIDENCE in c.reason_codes for c in classes)


def test_an_unproven_pair_is_ambiguous_never_consolidated_and_never_dropped():
    classes = run([rec("a"), rec("b")], [verdict("a", "b", "unproven")])
    assert partition(classes) == [("a",), ("b",)] and all(c.reason_codes == (ae.AMBIGUOUS_UNPROVEN,) for c in classes)


def test_overlap_without_printed_figure_evidence_is_ambiguous():
    classes = run([rec("a", figure=()), rec("b", figure=())], [verdict("a", "b", "overlapping")])
    assert all(ae.AMBIGUOUS_NO_FIGURE in c.reason_codes for c in classes) and len(classes) == 2


def test_similar_size_or_closeness_alone_never_consolidates():
    # no verdict at all, different figures, equal areas: two separate records
    classes = run([rec("a", figure=("x",)), rec("b", figure=("y",))], [])
    assert partition(classes) == [("a",), ("b",)] and all(c.reason_codes == (ae.SINGLE,) for c in classes)


def test_records_sharing_a_printed_figure_must_have_been_compared():
    classes = run([rec("a"), rec("b")], [])                       # one figure, never compared
    assert all(ae.AMBIGUOUS_SHARED_FIGURE in c.reason_codes for c in classes) and len(classes) == 2


def test_one_figure_on_several_proven_distinct_apertures_is_fine():
    records = [rec("a"), rec("b"), rec("c")]
    v = [verdict("a", "b", "distinct"), verdict("a", "c", "distinct"), verdict("b", "c", "distinct")]
    assert partition(run(records, v)) == [("a",), ("b",), ("c",)]


def test_a_chain_without_the_closing_pair_is_ambiguous():
    records = [rec("a"), rec("b"), rec("c")]
    v = [verdict("a", "b", "overlapping"), verdict("b", "c", "overlapping"), verdict("a", "c", "distinct")]
    classes = run(records, v)
    assert partition(classes) == [("a", "b", "c")] and classes[0].reason_codes == (ae.AMBIGUOUS_NOT_CLIQUE,) and classes[0].is_ambiguous


def test_ambiguity_taints_the_whole_equivalence_component():
    records = [rec("a"), rec("b"), rec("c", area=9.0)]
    v = [verdict("a", "b", "overlapping"), verdict("b", "c", "overlapping"), verdict("a", "c", "distinct")]
    classes = run(records, v)
    assert partition(classes) == [("a", "b"), ("c",)]
    assert all(c.status is ABST and ae.AMBIGUOUS_EVIDENCE in c.reason_codes for c in classes)       # b is ambiguous, so is its whole class


def test_ambiguity_elsewhere_leaves_an_unrelated_consolidation_alone():
    records = [rec("a"), rec("b"), rec("p", figure=("q",)), rec("r", figure=("q",), area=2.0)]
    v = [verdict("a", "b", "overlapping"), verdict("p", "r", "overlapping")]
    classes = classes_by_record(run(records, v))
    assert classes["a"].is_consolidated and classes["b"].is_consolidated
    assert classes["p"].is_ambiguous and classes["r"].is_ambiguous


def test_records_in_different_scopes_are_never_related():
    a, b = rec("a", scope="doc|rev|snap|p3"), rec("b", scope="doc|rev|snap|p4")
    classes = run([a, b], [verdict("a", "b", "overlapping")])
    assert partition(classes) == [("a",), ("b",)] and all(c.reason_codes == (ae.SINGLE,) for c in classes)


def test_two_records_with_no_host_at_all_are_not_the_same_host():
    classes = run([rec("a", host=None), rec("b", host=None)], [verdict("a", "b", "overlapping")])
    assert partition(classes) == [("a",), ("b",)] and all(c.status is ABST and ae.AMBIGUOUS_EVIDENCE in c.reason_codes for c in classes)


def test_one_figure_in_two_scopes_needs_no_comparison_across_them():
    a, b = rec("a", scope="doc|rev|snap|p3"), rec("b", scope="doc|rev|snap|p4")
    classes = run([a, b], [])
    assert partition(classes) == [("a",), ("b",)] and all(c.reason_codes == (ae.SINGLE,) for c in classes)


# ------------------------------------------------------------------------------------------------ metamorphic
def _structure():
    records = [rec("a"), rec("b"), rec("c", figure=("lbl-b",), area=2.0), rec("d", figure=("lbl-b",), area=2.0), rec("e", figure=("lbl-b",), area=2.0)]
    v = [verdict("a", "b", "overlapping"), verdict("c", "d", "overlapping"), verdict("c", "e", "distinct"), verdict("d", "e", "distinct")]
    return records, v


def test_record_pair_and_side_order_do_not_change_the_result():
    records, v = _structure()
    ref = run(records, v)
    rng = random.Random(13)
    for _ in range(30):
        rr, vv = records[:], [PairVerdict(x.right_id, x.left_id, x.verdict) if rng.random() < 0.5 else x for x in v]
        rng.shuffle(rr), rng.shuffle(vv)
        assert run(rr, vv) == ref


def test_renaming_ids_gives_the_same_partition():
    records, v = _structure()
    mapping = {r.record_id: f"zz-{i}" for i, r in enumerate(reversed(records))}
    renamed_records = [ApertureRecord(mapping[r.record_id], r.scope_key, r.figure_key, r.area_m2, r.host_key, r.receipt_ids) for r in records]
    renamed_v = [PairVerdict(mapping[x.left_id], mapping[x.right_id], x.verdict) for x in v]
    expected = sorted(tuple(sorted(mapping[m] for m in c.member_ids)) for c in run(records, v))
    assert partition(run(renamed_records, renamed_v)) == expected


def test_unrelated_records_and_pairs_do_not_change_the_classes_of_others():
    records, v = _structure()
    ref = {c.member_ids: (c.status, c.reason_codes) for c in run(records, v)}
    extra = [rec(f"x{i}", figure=(f"far{i}",), area=3.0 + i, host=f"wall-{i}") for i in range(5)]
    got = {c.member_ids: (c.status, c.reason_codes) for c in run(records + extra, v)}
    assert all(got[k] == val for k, val in ref.items())


def test_replay_is_deterministic_and_inputs_are_not_mutated():
    records, v = _structure()
    snap = copy.deepcopy((records, v))
    r1, r2 = run(records, v), run(records, v)
    assert r1 == r2 and [c.class_id for c in r1] == [c.class_id for c in r2] and (records, v) == snap
    assert [c.class_id for c in r1] == sorted(c.class_id for c in r1)


def test_class_identity_changes_with_members_area_and_receipts():
    a = run([rec("a"), rec("b")], [verdict("a", "b", "overlapping")])[0].class_id
    b = run([rec("a"), rec("c")], [verdict("a", "c", "overlapping")])[0].class_id
    c = run([rec("a", area=2.0), rec("b", area=2.0)], [verdict("a", "b", "overlapping")])[0].class_id
    d = run([rec("a", receipts=("other",)), rec("b")], [verdict("a", "b", "overlapping")])[0].class_id
    assert len({a, b, c, d}) == 4


# ------------------------------------------------------------------------------------------------ switches and input safety
def test_default_off_and_strict_enabled_flag():
    assert resolve_aperture_equivalence([rec("a")], []) == ()
    assert resolve_aperture_equivalence([rec("a")], [], enabled=False) == ()
    for bad in (1, "yes", None):
        with pytest.raises(ValueError):
            resolve_aperture_equivalence([rec("a")], [], enabled=bad)


@pytest.mark.parametrize("records,verdicts", [
    ([rec("a"), rec("a")], []),                                                           # duplicate ids
    ([rec("a"), rec("b")], [verdict("a", "zzz", "distinct")]),                           # unknown id
    ([rec("a")], [verdict("a", "a", "distinct")]),                                        # self pair
    ([rec("a"), rec("b")], [verdict("a", "b", "same")]),                                  # unknown verdict word
    ([rec("a"), rec("b")], [verdict("a", "b", "distinct"), verdict("b", "a", "overlapping")]),   # the two sides disagree
    ([rec("a", area=float("nan"))], []),
    ([rec("a", area=-1.0)], []),
    ([rec("a", area=0.0)], []),
    ([rec("a", scope="")], []),
])
def test_invalid_input_abstains_as_one_invalid_class(records, verdicts):
    (c,) = run(records, verdicts)
    assert c.status is ABST and c.reason_codes == (ae.INVALID_INPUT,) and c.member_ids == ()


def test_a_record_without_an_area_is_never_consolidated():
    classes = run([rec("a", area=None), rec("b", area=None)], [verdict("a", "b", "overlapping")])
    assert all(c.status is ABST for c in classes)


def test_module_is_isolated_from_authority_modules():
    import ast
    import pathlib
    text = pathlib.Path(ae.__file__).read_text(encoding="utf-8")
    tree = ast.parse(text)
    imported = {n.module for n in ast.walk(tree) if isinstance(n, ast.ImportFrom) and n.module}
    imported |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert imported <= {"__future__", "dataclasses", "math", "typing", "pb_migration_contracts"}
    root = pathlib.Path(ae.__file__).parent
    importers = sorted(p.name for p in root.glob("pb_*.py") if p.name != pathlib.Path(ae.__file__).name
                       and "pb_opening_aperture_equivalence_shadow" in p.read_text(encoding="utf-8", errors="ignore"))
    # the default-off, authority-reproving consumer is the ONLY module that reads it; nothing in the live path imports either (pinned in the consumer's tests)
    assert importers == ["pb_live_opening_aperture_consolidation.py"], importers
