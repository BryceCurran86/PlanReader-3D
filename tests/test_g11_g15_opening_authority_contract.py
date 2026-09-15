from __future__ import annotations

from dataclasses import replace

from pb_opening_authority import (
    AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE,
    AuthorityScope,
    HostBindingRelation,
    IdentityRelation,
    LocalCandidateQuery,
    OpeningObservation,
    UpstreamUniverseState,
    assess_current_host_authority,
    assess_current_opening_universe,
    assess_current_physical_net_authority,
    assess_current_physical_void_authority,
    combine_identity_relations,
    resolve_current_opening_identity,
)


def _scope(*, page: int = 0, viewport: str = "vp-1") -> AuthorityScope:
    return AuthorityScope(
        source_sha256="a" * 64,
        source_revision_id="rev-1",
        evidence_snapshot_id="evsnap-1",
        canonical_graph_snapshot_id="graphsnap-1",
        page_index=page,
        viewport_id=viewport,
    )


def _obs(
    observation_id: str,
    *,
    scope: AuthorityScope | None = None,
    evidence_ids: tuple[str, ...] = ("ev-1",),
    tag: str | None = "D01",
    width_mm: float | None = 900.0,
    height_mm: float | None = 2100.0,
    x: float | None = 100.0,
    y: float | None = 200.0,
    caller_identity_proven: bool = False,
    caller_self_hash: str | None = None,
    caller_lineage_ids: tuple[str, ...] = (),
) -> OpeningObservation:
    return OpeningObservation(
        observation_id=observation_id,
        scope=scope or _scope(),
        evidence_ids=evidence_ids,
        tag=tag,
        width_mm=width_mm,
        height_mm=height_mm,
        x=x,
        y=y,
        caller_identity_proven=caller_identity_proven,
        caller_self_hash=caller_self_hash,
        caller_lineage_ids=caller_lineage_ids,
    )


# G11 — physical opening identity proof contract

def test_g11_same_tag_and_dimensions_distinct_plan_instances_are_not_proven_same() -> None:
    left = _obs("plan-door-1", evidence_ids=("plan-ev-1",))
    right = _obs("plan-door-2", evidence_ids=("plan-ev-2",))

    decision = resolve_current_opening_identity(left, right)

    assert decision.relation is IdentityRelation.AMBIGUOUS
    assert decision.authoritative is False


def test_g11_same_coordinates_in_different_scopes_are_not_automatically_same() -> None:
    left = _obs("door-1", scope=_scope(page=0, viewport="vp-a"))
    right = _obs("door-2", scope=_scope(page=1, viewport="vp-b"))

    assert resolve_current_opening_identity(left, right).relation is IdentityRelation.AMBIGUOUS


def test_g11_schedule_type_relation_does_not_establish_physical_identity() -> None:
    plan = _obs("plan-instance", evidence_ids=("plan-ev",))
    schedule = _obs(
        "schedule-type-row",
        scope=_scope(page=4, viewport="schedule-vp"),
        evidence_ids=("schedule-ev",),
    )

    assert resolve_current_opening_identity(plan, schedule).relation is IdentityRelation.AMBIGUOUS


def test_g11_caller_identity_flag_and_self_hash_cannot_mint_same() -> None:
    left = _obs(
        "fragment-a",
        caller_identity_proven=True,
        caller_self_hash="caller-hash",
        caller_lineage_ids=("same-parent",),
    )
    right = _obs(
        "fragment-b",
        caller_identity_proven=True,
        caller_self_hash="caller-hash",
        caller_lineage_ids=("same-parent",),
    )

    decision = resolve_current_opening_identity(left, right)

    assert decision.relation is IdentityRelation.AMBIGUOUS
    assert decision.authoritative is False


def test_g11_split_fragments_need_independently_inspectable_lineage() -> None:
    left = _obs("fragment-a", caller_lineage_ids=("lineage-1",))
    right = _obs("fragment-b", caller_lineage_ids=("lineage-1",))

    decision = resolve_current_opening_identity(left, right)

    assert decision.relation is IdentityRelation.AMBIGUOUS
    assert AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE in decision.blockers


def test_g11_adding_contradictory_evidence_cannot_strengthen_identity() -> None:
    assert combine_identity_relations((IdentityRelation.PROVEN_SAME,)) is IdentityRelation.PROVEN_SAME
    assert (
        combine_identity_relations(
            (IdentityRelation.PROVEN_SAME, IdentityRelation.PROVEN_DISTINCT)
        )
        is IdentityRelation.AMBIGUOUS
    )
    assert (
        combine_identity_relations(
            (IdentityRelation.AMBIGUOUS, IdentityRelation.PROVEN_SAME)
        )
        is IdentityRelation.AMBIGUOUS
    )


def test_g11_removal_of_provenance_cannot_strengthen_identity() -> None:
    complete = resolve_current_opening_identity(_obs("a"), _obs("b", evidence_ids=("ev-2",)))
    missing = resolve_current_opening_identity(
        replace(_obs("a"), evidence_ids=()),
        _obs("b", evidence_ids=("ev-2",)),
    )

    assert complete.relation is IdentityRelation.AMBIGUOUS
    assert missing.relation is IdentityRelation.AMBIGUOUS
    assert missing.authoritative is False
    assert "opening_identity_provenance_incomplete" in missing.blockers


# G12 — authoritative opening candidate universe

def _query(
    candidates: tuple[str, ...] = ("opening-a", "opening-b"),
    *,
    caller_complete: bool = False,
    radius_mm: float | None = None,
    filters: tuple[str, ...] = (),
) -> LocalCandidateQuery:
    return LocalCandidateQuery(
        scope=_scope(),
        candidate_ids=candidates,
        caller_complete=caller_complete,
        radius_mm=radius_mm,
        filters=filters,
    )


def _assert_unavailable(query: LocalCandidateQuery) -> None:
    decision = assess_current_opening_universe(query)
    assert decision.state is UpstreamUniverseState.AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE
    assert decision.complete is False
    assert decision.authoritative_candidate_ids == ()
    assert AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE in decision.blockers


def test_g12_truncated_candidate_list_cannot_certify_completeness() -> None:
    _assert_unavailable(_query(("opening-a",)))


def test_g12_filtering_away_inconvenient_opening_cannot_certify_completeness() -> None:
    _assert_unavailable(_query(("opening-a",), filters=("exclude:opening-b",)))


def test_g12_shrinking_radius_cannot_certify_completeness() -> None:
    _assert_unavailable(_query(("opening-a",), radius_mm=50.0))


def test_g12_omitting_unresolved_candidate_cannot_certify_completeness() -> None:
    _assert_unavailable(_query(("opening-resolved",)))


def test_g12_reordering_candidates_does_not_create_authority() -> None:
    _assert_unavailable(_query(("opening-b", "opening-a")))


def test_g12_duplicate_candidates_do_not_create_authority() -> None:
    _assert_unavailable(_query(("opening-a", "opening-a")))


def test_g12_self_declared_complete_true_is_ignored() -> None:
    _assert_unavailable(_query(caller_complete=True))


# G13 — host universe and binding stay separate from nomination

def _assert_host_blocked(host_ids: tuple[str, ...], **query_kwargs: object) -> None:
    query = LocalCandidateQuery(
        scope=_scope(),
        candidate_ids=host_ids,
        caller_complete=bool(query_kwargs.get("caller_complete", False)),
        radius_mm=query_kwargs.get("radius_mm"),
        filters=tuple(query_kwargs.get("filters", ())),
    )
    decision = assess_current_host_authority(_obs("opening-a"), query)
    assert decision.universe.state is UpstreamUniverseState.AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE
    assert decision.universe.complete is False
    assert decision.binding is HostBindingRelation.AMBIGUOUS
    assert decision.authoritative is False


def test_g13_corner_opening_with_two_plausible_hosts_is_blocked() -> None:
    _assert_host_blocked(("wall-a", "wall-b"))


def test_g13_cavity_double_wall_geometry_is_blocked() -> None:
    _assert_host_blocked(("wall-leaf-a", "wall-leaf-b"))


def test_g13_overlapping_wall_bboxes_are_only_nominations() -> None:
    _assert_host_blocked(("wall-a", "wall-b"))


def test_g13_nearest_wall_with_incomplete_universe_is_blocked() -> None:
    _assert_host_blocked(("nearest-wall",), radius_mm=100.0)


def test_g13_schedule_wall_type_does_not_bind_host() -> None:
    _assert_host_blocked(("wall-type-A",), filters=("schedule-wall-type",))


def test_g13_host_disappearing_under_filtering_is_blocked() -> None:
    _assert_host_blocked(("wall-a",), filters=("exclude:wall-b",))


def test_g13_proven_distinct_or_ambiguous_local_host_claims_do_not_bypass_universe() -> None:
    _assert_host_blocked(("wall-a:PROVEN_DISTINCT", "wall-b:PROVEN_DISTINCT"))
    _assert_host_blocked(("wall-a:AMBIGUOUS", "wall-b:AMBIGUOUS"))


# G14/G15 — dependent physical quantities stay fail-closed under stop condition B

def test_g14_current_physical_void_authority_blocks_without_identity_and_universe_producers() -> None:
    decision = assess_current_physical_void_authority(
        opening=_obs("opening-a"),
        width_mm=900.0,
        height_mm=2100.0,
        host_query=_query(("wall-a",), caller_complete=True),
        commercial_applicability=None,
    )

    assert decision.firm is False
    assert decision.area_m2 is None
    assert "opening_physical_identity_unproven" in decision.blockers
    assert AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE in decision.blockers
    assert "opening_commercial_applicability_unproven" not in decision.blockers


def test_g14_unknown_commercial_applicability_is_not_itself_a_physical_void_blocker() -> None:
    unknown = assess_current_physical_void_authority(
        opening=_obs("opening-a"),
        width_mm=900.0,
        height_mm=2100.0,
        host_query=_query(("wall-a",)),
        commercial_applicability=None,
    )
    known = assess_current_physical_void_authority(
        opening=_obs("opening-a"),
        width_mm=900.0,
        height_mm=2100.0,
        host_query=_query(("wall-a",)),
        commercial_applicability=True,
    )

    assert unknown.blockers == known.blockers
    assert "opening_commercial_applicability_unproven" not in unknown.blockers


def test_g15_unresolved_opening_keeps_firm_gross_but_blocks_net() -> None:
    decision = assess_current_physical_net_authority(
        gross_area_m2=25.0,
        gross_is_firm=True,
        opening_query=_query(("opening-a",)),
        resolved_void_areas_m2=(),
    )

    assert decision.gross_preserved is True
    assert decision.firm is False
    assert decision.net_area_m2 is None
    assert AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE in decision.blockers


def test_g15_missing_schedule_is_not_proof_of_no_opening() -> None:
    decision = assess_current_physical_net_authority(
        gross_area_m2=25.0,
        gross_is_firm=True,
        opening_query=_query((), filters=("no-schedule-rows",)),
        resolved_void_areas_m2=(),
    )

    assert decision.firm is False
    assert decision.net_area_m2 is None


def test_g15_zero_local_candidates_from_incomplete_producer_is_not_zero_deduction() -> None:
    decision = assess_current_physical_net_authority(
        gross_area_m2=25.0,
        gross_is_firm=True,
        opening_query=_query(()),
        resolved_void_areas_m2=(),
    )

    assert decision.gross_preserved is True
    assert decision.firm is False
    assert decision.net_area_m2 is None
    assert AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE in decision.blockers
