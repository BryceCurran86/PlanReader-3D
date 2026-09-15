from __future__ import annotations

from pb_opening_authority import (
    AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE,
    AuthorityScope,
    LocalCandidateQuery,
    OpeningObservation,
    assess_current_physical_void_authority,
)


def test_g14_positive_caller_dimensions_are_not_independent_dimension_authority() -> None:
    scope = AuthorityScope(
        source_sha256="c" * 64,
        source_revision_id="rev-1",
        evidence_snapshot_id="evsnap-1",
        canonical_graph_snapshot_id="graphsnap-1",
        page_index=0,
        viewport_id="vp-1",
    )
    opening = OpeningObservation(
        observation_id="opening-1",
        scope=scope,
        evidence_ids=("opening-evidence-1",),
        tag="D01",
        width_mm=900.0,
        height_mm=2100.0,
    )
    host_query = LocalCandidateQuery(
        scope=scope,
        candidate_ids=("wall-1",),
        caller_complete=True,
    )

    decision = assess_current_physical_void_authority(
        opening=opening,
        width_mm=900.0,
        height_mm=2100.0,
        host_query=host_query,
        commercial_applicability=None,
    )

    assert decision.firm is False
    assert decision.area_m2 is None
    assert "opening_dimensions_unproven" in decision.blockers
    assert "relevant_opening_universe_incomplete" in decision.blockers
    assert AUTHORITATIVE_UPSTREAM_UNIVERSE_UNAVAILABLE in decision.blockers
    assert "opening_commercial_applicability_unproven" not in decision.blockers
