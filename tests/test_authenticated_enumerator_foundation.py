"""Adversarial tests for the post-#297 authenticated enumerator foundation.

These tests intentionally require an independent parent-snapshot content anchor.
A locally self-consistent universe / manifest / proof is not enough: the
verifier must reconstruct the scoped universe from immutable parent content.
"""
from __future__ import annotations

from dataclasses import replace

from pb_authority_completeness import (
    AuthorityBindingStatus,
    AuthorityScope,
    AuthorityUniverseMember,
    ExplicitExclusion,
    build_authority_universe,
    build_completeness_manifest,
    canonical_sha256,
)
from pb_authenticated_enumerator_foundation import (
    AuthenticatedEnumerationRecord,
    build_authenticated_parent_snapshot,
    build_enumeration_proof,
    verify_local_manifest_against_parent_snapshot,
)

SHA = "a" * 64


def _scope(*, viewport_id: str = "vp", graph_snapshot_id: str = "graph-1") -> AuthorityScope:
    return AuthorityScope(
        domain="wall_length.physical_candidates",
        document_id="doc",
        source_sha256=SHA,
        revision_id="R1",
        evidence_snapshot_id="ev-1",
        graph_snapshot_id=graph_snapshot_id,
        page_id="page-1",
        viewport_id=viewport_id,
    )


def _record(candidate_id: str, *, viewport_id: str = "vp", provenance: str | None = None) -> AuthenticatedEnumerationRecord:
    scope = _scope(viewport_id=viewport_id)
    return AuthenticatedEnumerationRecord(
        candidate_id=candidate_id,
        domain=scope.domain,
        document_id=scope.document_id,
        source_sha256=scope.source_sha256,
        revision_id=scope.revision_id,
        evidence_snapshot_id=scope.evidence_snapshot_id,
        graph_snapshot_id=scope.graph_snapshot_id,
        page_id=scope.page_id,
        viewport_id=scope.viewport_id,
        provenance_fingerprint=provenance or canonical_sha256({"candidate": candidate_id, "viewport": viewport_id}),
    )


def _snapshot(*records: AuthenticatedEnumerationRecord, snapshot_id: str = "canonical-graph-1"):
    return build_authenticated_parent_snapshot(
        snapshot_id=snapshot_id,
        producer_id="canonical-wall-graph",
        producer_version="1",
        records=records,
    )


def _local_universe(scope: AuthorityScope, *records: AuthenticatedEnumerationRecord):
    return build_authority_universe(
        scope,
        tuple(AuthorityUniverseMember(item.candidate_id, item.provenance_fingerprint) for item in records),
    )


def _manifest(universe, *, admitted: tuple[str, ...], unresolved: tuple[str, ...] = (), exclusions=()):
    return build_completeness_manifest(
        universe,
        admitted_candidate_ids=admitted,
        unresolved_candidate_ids=unresolved,
        explicit_exclusions=exclusions,
    )


def test_truncated_self_consistent_local_universe_is_rejected() -> None:
    w1, w2 = _record("W1"), _record("W2")
    parent = _snapshot(w1, w2)
    proof = build_enumeration_proof(parent, scope=_scope(), enumerator_id="physical-wall-enumerator", enumerator_version="1")

    truncated = _local_universe(_scope(), w1)
    manifest = _manifest(truncated, admitted=("W1",))
    result = verify_local_manifest_against_parent_snapshot(
        parent_snapshot=parent,
        proof=proof,
        local_universe=truncated,
        manifest=manifest,
        expected_scope=_scope(),
        supplied_admitted_ids=("W1",),
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "local_universe_does_not_match_authenticated_enumeration" in result.reasons


def test_fabricated_parent_snapshot_fingerprint_is_rejected() -> None:
    w1, w2 = _record("W1"), _record("W2")
    parent = _snapshot(w1, w2)
    proof = build_enumeration_proof(parent, scope=_scope(), enumerator_id="physical-wall-enumerator", enumerator_version="1")
    forged_parent = replace(parent, content_sha256=canonical_sha256({"records": ["W1"]}))
    universe = _local_universe(_scope(), w1, w2)
    manifest = _manifest(universe, admitted=("W1", "W2"))
    result = verify_local_manifest_against_parent_snapshot(
        parent_snapshot=forged_parent,
        proof=proof,
        local_universe=universe,
        manifest=manifest,
        expected_scope=_scope(),
        supplied_admitted_ids=("W1", "W2"),
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "parent_snapshot_content_fingerprint_mismatch" in result.reasons


def test_candidate_added_after_proof_is_stale() -> None:
    w1, w2 = _record("W1"), _record("W2")
    original = _snapshot(w1)
    proof = build_enumeration_proof(original, scope=_scope(), enumerator_id="physical-wall-enumerator", enumerator_version="1")
    current = _snapshot(w1, w2, snapshot_id=original.snapshot_id)
    universe = _local_universe(_scope(), w1, w2)
    manifest = _manifest(universe, admitted=("W1", "W2"))
    result = verify_local_manifest_against_parent_snapshot(
        parent_snapshot=current,
        proof=proof,
        local_universe=universe,
        manifest=manifest,
        expected_scope=_scope(),
        supplied_admitted_ids=("W1", "W2"),
    )
    assert result.status == AuthorityBindingStatus.STALE


def test_candidate_removed_after_proof_is_stale() -> None:
    w1, w2 = _record("W1"), _record("W2")
    original = _snapshot(w1, w2)
    proof = build_enumeration_proof(original, scope=_scope(), enumerator_id="physical-wall-enumerator", enumerator_version="1")
    current = _snapshot(w1, snapshot_id=original.snapshot_id)
    universe = _local_universe(_scope(), w1)
    manifest = _manifest(universe, admitted=("W1",))
    result = verify_local_manifest_against_parent_snapshot(
        parent_snapshot=current,
        proof=proof,
        local_universe=universe,
        manifest=manifest,
        expected_scope=_scope(),
        supplied_admitted_ids=("W1",),
    )
    assert result.status == AuthorityBindingStatus.STALE


def test_parent_and_proof_are_order_invariant() -> None:
    w1, w2 = _record("W1"), _record("W2")
    a = _snapshot(w1, w2)
    b = _snapshot(w2, w1)
    assert a.content_sha256 == b.content_sha256
    pa = build_enumeration_proof(a, scope=_scope(), enumerator_id="physical-wall-enumerator", enumerator_version="1")
    pb = build_enumeration_proof(b, scope=_scope(), enumerator_id="physical-wall-enumerator", enumerator_version="1")
    assert pa.proof_fingerprint == pb.proof_fingerprint
    assert pa.candidate_universe_fingerprint == pb.candidate_universe_fingerprint


def test_scope_isolation_ignores_unrelated_viewport_candidate() -> None:
    w1 = _record("W1")
    outside = _record("W-OUT", viewport_id="vp-other")
    parent = _snapshot(w1, outside)
    proof = build_enumeration_proof(parent, scope=_scope(), enumerator_id="physical-wall-enumerator", enumerator_version="1")
    universe = _local_universe(_scope(), w1)
    manifest = _manifest(universe, admitted=("W1",))
    result = verify_local_manifest_against_parent_snapshot(
        parent_snapshot=parent,
        proof=proof,
        local_universe=universe,
        manifest=manifest,
        expected_scope=_scope(),
        supplied_admitted_ids=("W1",),
    )
    assert result.status == AuthorityBindingStatus.AUTHENTIC


def test_self_fingerprinted_incomplete_query_proof_is_rejected() -> None:
    w1, w2 = _record("W1"), _record("W2")
    parent = _snapshot(w1, w2)
    genuine = build_enumeration_proof(parent, scope=_scope(), enumerator_id="physical-wall-enumerator", enumerator_version="1")
    truncated = _local_universe(_scope(), w1)
    fake = replace(
        genuine,
        matched_candidate_ids=("W1",),
        candidate_count=1,
        candidate_universe_fingerprint=truncated.fingerprint,
    )
    fake = replace(fake, proof_fingerprint=canonical_sha256(fake.payload(include_fingerprint=False)))
    manifest = _manifest(truncated, admitted=("W1",))
    result = verify_local_manifest_against_parent_snapshot(
        parent_snapshot=parent,
        proof=fake,
        local_universe=truncated,
        manifest=manifest,
        expected_scope=_scope(),
        supplied_admitted_ids=("W1",),
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "enumeration_proof_does_not_match_parent_snapshot" in result.reasons


def test_same_id_with_mutated_provenance_invalidates_old_proof() -> None:
    old = _record("W1", provenance=canonical_sha256({"source": "old"}))
    new = _record("W1", provenance=canonical_sha256({"source": "new"}))
    original = _snapshot(old)
    proof = build_enumeration_proof(original, scope=_scope(), enumerator_id="physical-wall-enumerator", enumerator_version="1")
    current = _snapshot(new, snapshot_id=original.snapshot_id)
    universe = _local_universe(_scope(), new)
    manifest = _manifest(universe, admitted=("W1",))
    result = verify_local_manifest_against_parent_snapshot(
        parent_snapshot=current,
        proof=proof,
        local_universe=universe,
        manifest=manifest,
        expected_scope=_scope(),
        supplied_admitted_ids=("W1",),
    )
    assert result.status == AuthorityBindingStatus.STALE


def test_proof_cannot_be_reused_across_viewports() -> None:
    w1 = _record("W1")
    outside = _record("W2", viewport_id="vp-other")
    parent = _snapshot(w1, outside)
    proof = build_enumeration_proof(parent, scope=_scope(), enumerator_id="physical-wall-enumerator", enumerator_version="1")
    other_scope = _scope(viewport_id="vp-other")
    universe = _local_universe(other_scope, outside)
    manifest = _manifest(universe, admitted=("W2",))
    result = verify_local_manifest_against_parent_snapshot(
        parent_snapshot=parent,
        proof=proof,
        local_universe=universe,
        manifest=manifest,
        expected_scope=other_scope,
        supplied_admitted_ids=("W2",),
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "enumeration_proof_scope_mismatch" in result.reasons


def test_valid_full_universe_can_feed_completeness_manifest_without_quantity_publication() -> None:
    w1, w2 = _record("W1"), _record("W2")
    parent = _snapshot(w1, w2)
    proof = build_enumeration_proof(parent, scope=_scope(), enumerator_id="physical-wall-enumerator", enumerator_version="1")
    universe = _local_universe(_scope(), w1, w2)
    manifest = _manifest(
        universe,
        admitted=("W1",),
        exclusions=(ExplicitExclusion("W2", "outside_declared_local_wall_set", ("scope-ev",)),),
    )
    result = verify_local_manifest_against_parent_snapshot(
        parent_snapshot=parent,
        proof=proof,
        local_universe=universe,
        manifest=manifest,
        expected_scope=_scope(),
        supplied_admitted_ids=("W1",),
    )
    assert result.status == AuthorityBindingStatus.AUTHENTIC
