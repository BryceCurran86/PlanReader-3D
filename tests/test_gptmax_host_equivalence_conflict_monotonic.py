"""Source-closed G17 host membership cannot recover a wall-pair contradiction."""
from __future__ import annotations

from itertools import permutations
from types import SimpleNamespace

import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_opening_host_binding_authority import (
    HOST_EQUIVALENCE_AMBIGUOUS,
    _normalize_role_candidates,
    _pair_lookup,
    _unsafe_original_lineage_group_members,
)
from pb_physical_wall_identity import PhysicalEquivalenceClass as Class
from test_raster_opening_split_centerline_host import _record

SAME = Class.SAME_PHYSICAL_WALL
DISTINCT = Class.DISTINCT_PHYSICAL_WALLS
UNKNOWN = Class.AMBIGUOUS_PHYSICAL_EQUIVALENCE


def _source_equivalence(rows, groups=()):
    return SimpleNamespace(
        pair_classifications=tuple(rows),
        equivalence_groups=groups,
        ambiguous_wall_ids=(),
    )


@pytest.mark.parametrize("classes", [
    (SAME.value, DISTINCT.value, SAME.value),
    (DISTINCT.value, SAME.value, DISTINCT.value),
    (UNKNOWN.value, DISTINCT.value, DISTINCT.value),
    (SAME.value, "malformed_producer_class", SAME.value),
    (DISTINCT.value, None, DISTINCT.value),
])
def test_conflicting_original_pair_issuer_order_cannot_restore_host_class(classes):
    for order in set(permutations(classes)):
        original = tuple(("left", "right", label) for label in order)
        first = _pair_lookup(_source_equivalence(original))
        reverse = _pair_lookup(_source_equivalence(tuple(reversed(original))))
        assert first == reverse == {("left", "right"): UNKNOWN}


@pytest.mark.parametrize("positive", (SAME, DISTINCT, UNKNOWN))
def test_identical_issuer_replays_remain_unchanged(positive):
    rows = (("left", "right", positive.value),
            ("right", "left", positive.value))
    assert _pair_lookup(_source_equivalence(rows)) == {
        ("left", "right"): positive
    }


def test_unrelated_wall_pairs_preserve_independent_distinctness():
    rows = (
        ("left", "right", SAME.value),
        ("other_a", "other_b", DISTINCT.value),
        ("right", "left", DISTINCT.value),
        ("left", "right", SAME.value),
    )
    snapshot = tuple(rows)
    actual = _pair_lookup(_source_equivalence(rows))
    assert actual == {
        ("left", "right"): UNKNOWN,
        ("other_a", "other_b"): DISTINCT,
    }
    assert rows == snapshot


@pytest.mark.parametrize("order", [
    (SAME.value, DISTINCT.value, SAME.value),
    (DISTINCT.value, SAME.value, DISTINCT.value),
])
def test_real_host_role_normalizer_abstains_on_conflicted_pair(order):
    """Full consumer must block; unit lookup alone isn't a host safety gate."""
    left = _record("left", start=10.0, end=40.0)
    right = _record("right", start=10.0, end=40.0)
    source = _source_equivalence(
        [("left", "right", c) for c in order],
        groups=(),
    )
    status, selected, reasons = _normalize_role_candidates(
        ((0.0, left), (0.0, right)), source, axis_tol=0.8
    )
    assert status is Status.CONFLICT
    assert selected == ()
    assert HOST_EQUIVALENCE_AMBIGUOUS in reasons


@pytest.mark.parametrize("issued", [
    (DISTINCT.value,),
    (DISTINCT.value, DISTINCT.value),
    (DISTINCT.value, SAME.value, DISTINCT.value),
])
def test_explicit_distinct_against_same_group_never_recovers_a_host(issued):
    left = _record("wall_left", start=10.0, end=40.0)
    right = _record("wall_right", start=10.0, end=40.0)
    for order in set(permutations(issued)):
        source = _source_equivalence(
            tuple(("wall_left", "wall_right", cls) for cls in order),
            groups=(("wall_left", "wall_right"),),
        )
        assert _pair_lookup(source) == {
            ("wall_left", "wall_right"): UNKNOWN,
        }
        status, selected, reasons = _normalize_role_candidates(
            ((0.0, left), (0.0, right)), source, axis_tol=0.8,
        )
        assert status is Status.CONFLICT
        assert selected == ()
        assert HOST_EQUIVALENCE_AMBIGUOUS in reasons


@pytest.mark.parametrize("unproved_class", (
    UNKNOWN.value, "malformed_source_class", None, [],
))
def test_same_source_group_with_ambiguous_or_malformed_pair_blocks_host(
    unproved_class,
):
    left = _record("wall:left", start=10.0, end=40.0)
    right = _record("wall:right", start=10.0, end=40.0)
    source = _source_equivalence(
        (("wall:left", "wall:right", unproved_class),),
        groups=(("wall:left", "wall:right"),),
    )
    assert _pair_lookup(source) == {("wall:left", "wall:right"): UNKNOWN}
    status, normalized, reasons = _normalize_role_candidates(
        ((0.0, left), (5.0, right)), source, axis_tol=0.8,
    )
    assert status is Status.CONFLICT
    assert normalized == ()
    assert HOST_EQUIVALENCE_AMBIGUOUS in reasons


def test_same_group_needs_positive_same_class_to_collapse_local_role():
    left = _record("wall_left", start=10.0, end=40.0)
    right = _record("wall_right", start=10.0, end=40.0)
    source = _source_equivalence(
        (("wall_left", "wall_right", SAME.value),),
        groups=(("wall_left", "wall_right"),),
    )
    status, selected, reasons = _normalize_role_candidates(
        ((0.0, left), (0.0, right)), source, axis_tol=0.8,
    )
    assert status is Status.CORROBORATED
    assert len(selected) == 1
    assert selected[0].candidate_group == ("wall_left", "wall_right")
    assert reasons == ()


def test_distinct_wall_groups_remain_two_local_host_candidates():
    left = _record("wall_left", start=10.0, end=40.0)
    right = _record("wall_right", start=10.0, end=40.0)
    source = _source_equivalence(
        (("wall_left", "wall_right", DISTINCT.value),),
        groups=(("wall_left",), ("wall_right",)),
    )
    status, selected, reasons = _normalize_role_candidates(
        ((0.0, left), (0.0, right)), source, axis_tol=0.8,
    )
    assert status is Status.CORROBORATED
    assert len(selected) == 2
    assert reasons == ()


@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize("left_offset,right_offset", [
    (0.0, 5.0), (5.0, 0.0), (-2.0, 2.0),
])
def test_same_group_distinct_pair_veto_spans_separate_role_offset_clusters(
    reverse, left_offset, right_offset,
):
    left = _record("wall:left", start=10.0, end=40.0)
    right = _record("wall:right", start=10.0, end=40.0)
    issued = (("wall:left", "wall:right", DISTINCT.value),)
    if reverse:
        issued = tuple((right_id, left_id, role)
                       for left_id, right_id, role in issued)
    source = _source_equivalence(
        issued, groups=(("wall:left", "wall:right"),),
    )
    candidates = ((left_offset, left), (right_offset, right))
    if reverse:
        candidates = tuple(reversed(candidates))
    status, normalized, reasons = _normalize_role_candidates(
        candidates, source, axis_tol=0.8,
    )
    assert status is Status.CONFLICT
    assert normalized == ()
    assert HOST_EQUIVALENCE_AMBIGUOUS in reasons


def test_source_cross_offset_conflict_not_global_to_unrelated_wall():
    record = _record("wall:unrelated", start=10.0, end=40.0)
    source = _source_equivalence(
        (("wall:left", "wall:right", DISTINCT.value),),
        groups=(("wall:left", "wall:right"),),
    )
    status, normalized, reasons = _normalize_role_candidates(
        ((0.0, record),), source, axis_tol=0.8,
    )
    assert status is Status.CORROBORATED
    assert len(normalized) == 1
    assert normalized[0].record.wall_candidate_id == "wall:unrelated"
    assert reasons == ()


@pytest.mark.parametrize("issued", (
    DISTINCT.value, UNKNOWN.value, "malformed_source_class", None,
))
@pytest.mark.parametrize("reverse", (False, True))
def test_three_member_source_group_conflict_taints_unselected_sibling(
    issued, reverse,
):
    group = ("wall:A", "wall:B", "wall:C")
    pair = ("wall:A", "wall:B", issued)
    if reverse:
        group = tuple(reversed(group))
        pair = (pair[1], pair[0], pair[2])
    source = _source_equivalence((pair,), groups=(group,))
    assert _unsafe_original_lineage_group_members(source) == frozenset(group)
    assert _pair_lookup(source) == {("wall:A", "wall:B"): UNKNOWN}
    only_c = _record("wall:C", start=10.0, end=40.0)
    status, selected, reasons = _normalize_role_candidates(
        ((0.0, only_c),), source, axis_tol=0.8,
        pair_lookup={}, group_lookup={"wall:C": tuple(sorted(group))},
    )
    assert status is Status.CONFLICT
    assert selected == ()
    assert HOST_EQUIVALENCE_AMBIGUOUS in reasons


def test_three_member_conflict_keeps_independent_group_and_valid_same():
    source = _source_equivalence(
        (("A", "B", DISTINCT.value), ("X", "Y", SAME.value)),
        groups=(("A", "B", "C"), ("X", "Y")),
    )
    assert _unsafe_original_lineage_group_members(source) == frozenset({"A", "B", "C"})
    for wall_id in ("X", "Y", "outside"):
        record = _record(wall_id, start=10.0, end=40.0)
        status, selected, reasons = _normalize_role_candidates(
            ((0.0, record),), source, axis_tol=0.8,
        )
        assert status is Status.CORROBORATED
        assert len(selected) == 1
        assert reasons == ()


def test_three_member_repeated_issuer_receipt_order_cannot_restore_c():
    c = _record("C", start=10.0, end=40.0)
    for order in set(permutations((SAME.value, DISTINCT.value, SAME.value))):
        source = _source_equivalence(
            tuple(("A", "B", cls) for cls in order),
            groups=(("A", "B", "C"),),
        )
        status, selected, reasons = _normalize_role_candidates(
            ((0.0, c),), source, axis_tol=0.8,
        )
        assert status is Status.CONFLICT
        assert selected == ()
        assert HOST_EQUIVALENCE_AMBIGUOUS in reasons

    valid = _source_equivalence(
        (("A", "B", SAME.value), ("B", "C", SAME.value)),
        groups=(("A", "B", "C"),),
    )
    status, selected, reasons = _normalize_role_candidates(
        ((0.0, c),), valid, axis_tol=0.8,
    )
    assert status is Status.CORROBORATED
    assert len(selected) == 1
    assert selected[0].candidate_group == ("A", "B", "C")
    assert reasons == ()


@pytest.mark.parametrize("mode", ("gap", "two_face"))
@pytest.mark.parametrize("issued", (DISTINCT.value, UNKNOWN.value, "bad_class"))
def test_three_member_contradiction_blocks_c_only_source_lineage(mode, issued):
    observations, records, _ = _original_lineage_test_case(mode)
    first = records[0]
    c = _record("wall:C", start=0.0, end=30.0,
                source_ids=first.physical_identity.source_primitive_ids)
    records = (c, *records[1:])
    valid = _original_lineage_resolve(
        observations, records, mode, _source_equivalence(()),
    )
    assert valid.status is Status.CORROBORATED
    source = _source_equivalence(
        (("wall:A", "wall:B", issued),),
        groups=(("wall:A", "wall:B", "wall:C"),),
    )
    blocked = _original_lineage_resolve(observations, records, mode, source)
    assert blocked.status is Status.CONFLICT
    assert blocked.bands == ()
    assert HOST_EQUIVALENCE_AMBIGUOUS in blocked.reason_codes


def test_three_member_contradiction_blocks_actual_raster_host_consumer():
    import pb_opening_host_binding_authority as host
    from test_raster_opening_split_centerline_host import OPENING

    c = _record("wall:C", start=20.0, end=220.0)
    clean = host._resolve_raster_whole_wall_host(
        (c,), OPENING, _source_equivalence(()),
    )
    assert clean.status is Status.CORROBORATED and len(clean.bands) == 1
    blocked = host._resolve_raster_whole_wall_host(
        (c,), OPENING,
        _source_equivalence(
            (("wall:A", "wall:B", DISTINCT.value),),
            groups=(("wall:A", "wall:B", "wall:C"),),
        ),
    )
    assert blocked.status is Status.CONFLICT
    assert blocked.bands == ()
    assert HOST_EQUIVALENCE_AMBIGUOUS in blocked.reason_codes


def test_injected_distinct_lookup_cannot_bypass_same_source_group_veto():
    left = _record("wall_left", start=10.0, end=40.0)
    right = _record("wall_right", start=10.0, end=40.0)
    source = _source_equivalence(
        (("wall_left", "wall_right", DISTINCT.value),),
        groups=(("wall_left", "wall_right"),),
    )
    status, selected, reasons = _normalize_role_candidates(
        ((0.0, left), (0.0, right)), source, axis_tol=0.8,
        pair_lookup={("wall_left", "wall_right"): DISTINCT},
    )
    assert status is Status.CONFLICT
    assert selected == ()
    assert HOST_EQUIVALENCE_AMBIGUOUS in reasons


@pytest.mark.parametrize("reverse", (False, True))
@pytest.mark.parametrize("selected", ("left", "right", "third"))
def test_overlapping_original_same_groups_fail_closed_on_all_affected_members(
    reverse, selected,
):
    groups = (("left", "right"), ("left", "third"))
    if reverse:
        groups = tuple(reversed(groups))
    equivalence = _source_equivalence((), groups=groups)
    record = _record(selected, start=10.0, end=40.0)
    status, normalized, reasons = _normalize_role_candidates(
        ((0.0, record),), equivalence, axis_tol=0.8,
    )
    assert status is Status.CONFLICT
    assert normalized == ()
    assert HOST_EQUIVALENCE_AMBIGUOUS in reasons


def test_repeated_identical_source_group_is_not_an_original_contradiction():
    left = _record("left", start=10.0, end=40.0)
    right = _record("right", start=10.0, end=40.0)
    equiv = _source_equivalence(
        (("left", "right", SAME.value),),
        groups=(("left", "right"), ("left", "right")),
    )
    status, normalized, reasons = _normalize_role_candidates(
        ((0.0, left), (0.0, right)), equiv, axis_tol=0.8,
    )
    assert status is Status.CORROBORATED
    assert len(normalized) == 1
    assert reasons == ()


def test_unrelated_wall_group_overlap_does_not_remove_independent_host():
    host = _record("host", start=10.0, end=40.0)
    equiv = _source_equivalence(
        (), groups=(("left", "right"), ("left", "third")),
    )
    status, normalized, reasons = _normalize_role_candidates(
        ((0.0, host),), equiv, axis_tol=0.8,
    )
    assert status is Status.CORROBORATED
    assert len(normalized) == 1
    assert normalized[0].record.wall_candidate_id == "host"
    assert reasons == ()


def _original_lineage_test_case(kind):
    # Source-neutral two-collinear-gap/four-wall-face observation receipts.
    if kind == "gap":
        paths = [
            ("left", (0.0, 50.0, 10.0, 50.0)),
            ("right", (20.0, 50.0, 30.0, 50.0)),
        ]
        resolve = "gap"
    else:
        paths = [
            ("left-top", (0.0, 50.0, 10.0, 50.0)),
            ("right-top", (20.0, 50.0, 30.0, 50.0)),
            ("left-bottom", (0.0, 60.0, 10.0, 60.0)),
            ("right-bottom", (20.0, 60.0, 30.0, 60.0)),
        ]
        resolve = "two_face"
    observations = tuple(
        SimpleNamespace(
            observation_id=f"source-obs:{name}",
            source_primitive_ref=f"visible:segment:primitive:{name}",
            geometry=coords,
        )
        for name, coords in paths
    )
    records = tuple(
        _record(f"wall:{name}", start=0.0, end=30.0,
                source_ids=(f"primitive:{name}",))
        for name, _coords in paths
    )
    return observations, records, resolve


def _original_lineage_resolve(observations, records, kind, equivalence):
    import pb_opening_host_binding_authority as host
    if kind == "gap":
        return host._resolve_gap_lineage_host_from_records(
            observations, records, equivalence,
        )
    return host._resolve_two_face_lineage_host_from_records(
        observations, records, equivalence,
    )


@pytest.mark.parametrize("kind", ("gap", "two_face"))
@pytest.mark.parametrize("unproved_class", (
    DISTINCT.value, UNKNOWN.value, "malformed_source_class",
))
def test_actual_source_lineage_hosts_reject_group_pair_contradiction(
    kind, unproved_class,
):
    observations, records, mode = _original_lineage_test_case(kind)
    left, right = records[:2]
    valid = _source_equivalence(())
    first = _original_lineage_resolve(observations, records, mode, valid)
    assert first.status is Status.CORROBORATED and len(first.bands) == 1
    relation = (
        (left.wall_candidate_id, right.wall_candidate_id, unproved_class),
    )
    contradictory = _source_equivalence(
        relation,
        groups=((left.wall_candidate_id, right.wall_candidate_id),),
    )
    blocked = _original_lineage_resolve(
        observations, records, mode, contradictory,
    )
    assert blocked.status is Status.CONFLICT
    assert blocked.bands == ()
    assert HOST_EQUIVALENCE_AMBIGUOUS in blocked.reason_codes


@pytest.mark.parametrize("kind", ("gap", "two_face"))
def test_source_lineage_hosts_reject_overlap_group_first_wins(kind):
    observations, records, mode = _original_lineage_test_case(kind)
    left, right = records[:2]
    for groups in (
        ((left.wall_candidate_id, "other-source-wall"),
         (left.wall_candidate_id, right.wall_candidate_id)),
        ((left.wall_candidate_id, right.wall_candidate_id),
         (left.wall_candidate_id, "other-source-wall")),
    ):
        blocked = _original_lineage_resolve(
            observations, records, mode,
            _source_equivalence((), groups=groups),
        )
        assert blocked.status is Status.CONFLICT
        assert blocked.bands == ()
        assert HOST_EQUIVALENCE_AMBIGUOUS in blocked.reason_codes


@pytest.mark.parametrize("kind", ("gap", "two_face"))
def test_unrelated_lineage_w4_group_contradiction_does_not_erase_host(kind):
    observations, records, mode = _original_lineage_test_case(kind)
    unrelated = _source_equivalence(
        (("unrelated:a", "unrelated:b", DISTINCT.value),),
        groups=(("unrelated:a", "unrelated:b"),),
    )
    accepted = _original_lineage_resolve(
        observations, records, mode, unrelated,
    )
    assert accepted.status is Status.CORROBORATED
    assert len(accepted.bands) == 1


def test_malformed_single_source_relation_fails_closed_in_host_admission():
    source = _source_equivalence((("left", "right", "untrusted_value"),))
    assert _pair_lookup(source) == {("left", "right"): UNKNOWN}
    left = _record("left", start=10.0, end=40.0)
    right = _record("right", start=10.0, end=40.0)
    status, rows, reasons = _normalize_role_candidates(
        ((0.0, left), (0.0, right)), source, axis_tol=0.8
    )
    assert status is Status.CONFLICT
    assert rows == ()
    assert HOST_EQUIVALENCE_AMBIGUOUS in reasons


def test_exact_original_host_producer_equivocation_revokes_cached_authority(
    monkeypatch,
):
    """A second different positive is an error AND revokes fresh host access."""
    import pb_opening_host_binding_authority as host
    from pb_source_observation_authority import ObservationSelector

    opening = SimpleNamespace(
        record_id="original:opening:A", document_id="doc",
        revision_id="rev", source_sha256="a" * 64,
        snapshot_id="snapshot", page_id="3", structural_pattern="fixture",
    )
    positive = SimpleNamespace(
        status=Status.CORROBORATED,
        proposition=host.PHYSICAL_OPENING_EXISTS,
        existence_record=opening,
    )
    same_identity = SimpleNamespace(
        status=Status.CORROBORATED,
        proven_same=True,
        reason_codes=(host.PHYSICAL_OPENING_IDENTITY_RESOLVED,),
    )
    original = ObservationSelector(
        document_id=opening.document_id, revision_id=opening.revision_id,
        source_sha256=opening.source_sha256, snapshot_id=opening.snapshot_id,
        observation_id="source:original:opening:A",
    )
    universe_selector = host.OpeningHostWallUniverseSelector(
        document_id=opening.document_id, revision_id=opening.revision_id,
        source_sha256=opening.source_sha256, snapshot_id=opening.snapshot_id,
        page_id=opening.page_id, decision_scope_id="wall-source:page-3",
    )
    producer = object.__new__(host.OpeningHostBindingProducer)
    producer._opening = SimpleNamespace(
        prove_existence=lambda _selector: positive,
        compare_identity=lambda _left, _right: same_identity,
    )
    producer._universe = SimpleNamespace(
        resolve_scope=lambda _selector: SimpleNamespace(
            status=Status.CORROBORATED, scope_complete=True,
            equivalence=SimpleNamespace(equivalence_groups=()),
            records=(), source_observation_ids=(),
        ),
    )
    producer._results = {}
    active = {"member": "wall:host:A", "blocked": False}

    def issue_band(*_args, **_kwargs):
        if active["blocked"]:
            return host._HostBandResolution(
                Status.ABSTAINED, (), ("original_w4_host_no_longer_owned",),
            )
        wall_id = active["member"]
        return host._HostBandResolution(
            Status.CORROBORATED,
            (host._HostBand(
                member_ids=(wall_id,),
                member_candidate_identity_ids=(f"physical:{wall_id}",),
                member_equivalence_groups=((wall_id,),),
                center_offset=0.0,
            ),),
            (),
        )

    monkeypatch.setattr(host, "_opening_geometry",
                        lambda *_args: host._OpeningGeometry(
                            origin=(100.0, 50.0), axis=(1.0, 0.0),
                            normal=(0.0, 1.0), length=40.0, thickness=10.0,
                        ))
    monkeypatch.setattr(host, "_resolve_generic_gap_lineage_host",
                        lambda *_args: None)
    monkeypatch.setattr(host, "_resolve_two_face_lineage_host",
                        lambda *_args: None)
    monkeypatch.setattr(host, "_resolve_host_bands", issue_band)
    first = producer.publish(
        opening_left_selector=original, opening_right_selector=original,
        host_universe_selector=universe_selector,
    )
    assert first.status is Status.CORROBORATED
    assert first.record is not None
    selector = host.OpeningHostBindingSelector(
        document_id=opening.document_id, revision_id=opening.revision_id,
        source_sha256=opening.source_sha256, snapshot_id=opening.snapshot_id,
        page_id=opening.page_id, decision_scope_id="wall-source:page-3",
        opening_identity_id=opening.record_id,
    )
    old_authority = producer.authority()
    assert old_authority.resolve(selector) == first

    # Current original wall/source support can become unproved before the
    # issuer constructs a replacement positive result. It must revoke a
    # stale positive from NEW authorities on this exact scoped opening.
    active["blocked"] = True
    withheld = producer.publish(
        opening_left_selector=original, opening_right_selector=original,
        host_universe_selector=universe_selector,
    )
    assert withheld.status is Status.ABSTAINED
    assert "original_w4_host_no_longer_owned" in withheld.reason_codes
    assert producer.authority().resolve(selector).status is Status.ABSTAINED
    assert old_authority.resolve(selector) == first

    active["blocked"] = False
    assert producer.publish(
        opening_left_selector=original, opening_right_selector=original,
        host_universe_selector=universe_selector,
    ) == first

    active["member"] = "wall:host:B"
    with pytest.raises(RuntimeError, match="host-binding producer equivocation"):
        producer.publish(
            opening_left_selector=original, opening_right_selector=original,
            host_universe_selector=universe_selector,
        )
    assert producer.authority().resolve(selector).status is Status.ABSTAINED
    assert old_authority.resolve(selector) == first

    active["member"] = "wall:host:A"
    assert producer.publish(
        opening_left_selector=original, opening_right_selector=original,
        host_universe_selector=universe_selector,
    ) == first
