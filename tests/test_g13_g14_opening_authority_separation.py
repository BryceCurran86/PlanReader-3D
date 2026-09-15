from __future__ import annotations

from pb_opening_authority import (
    AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE,
    AuthorityScope,
    HostBindingRelation,
    IdentityRelation,
    LocalCandidateQuery,
    OpeningObservation,
    assess_current_host_authority,
    assess_current_physical_void_authority,
)


def _scope() -> AuthorityScope:
    return AuthorityScope(
        source_sha256="b" * 64,
        source_revision_id="rev-1",
        evidence_snapshot_id="evsnap-1",
        canonical_graph_snapshot_id="graphsnap-1",
        page_index=0,
        viewport_id="vp-1",
    )


def _opening() -> OpeningObservation:
    return OpeningObservation(
        observation_id="opening-observation-1",
        scope=_scope(),
        evidence_ids=("ev-opening-1",),
        tag="D01",
        width_mm=900.0,
        height_mm=2100.0,
        caller_identity_proven=True,
        caller_self_hash="caller-self-hash",
    )


def test_g13_host_identity_is_explicitly_separate_from_binding() -> None:
    query = LocalCandidateQuery(
        scope=_scope(),
        candidate_ids=("wall-a", "wall-b"),
        caller_complete=True,
    )

    decision = assess_current_host_authority(_opening(), query)

    assert decision.host_identity is IdentityRelation.AMBIGUOUS
    assert decision.binding is HostBindingRelation.AMBIGUOUS
    assert decision.authoritative is False
    assert AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE in decision.blockers


def test_g14_caller_created_observation_does_not_prove_physical_existence() -> None:
    query = LocalCandidateQuery(
        scope=_scope(),
        candidate_ids=("wall-a",),
        caller_complete=True,
    )

    decision = assess_current_physical_void_authority(
        opening=_opening(),
        width_mm=900.0,
        height_mm=2100.0,
        host_query=query,
        commercial_applicability=None,
    )

    assert decision.firm is False
    assert decision.area_m2 is None
    assert "opening_existence_unproven" in decision.blockers
    assert "opening_physical_identity_unproven" in decision.blockers
    assert AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE in decision.blockers
    assert "opening_commercial_applicability_unproven" not in decision.blockers
