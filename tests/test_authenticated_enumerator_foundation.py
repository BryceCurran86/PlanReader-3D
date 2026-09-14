"""Adversarial tests for the post-#297 authenticated enumerator foundation.

These tests intentionally require an independent parent-snapshot content anchor.
A locally self-consistent universe / manifest / proof is not enough: the
verifier must reconstruct the scoped universe from immutable parent content.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

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
WALL_DOMAIN = "wall_length.physical_candidates"
SCALE_DOMAIN = "wall_length.scale_candidates"
WALL_PRODUCER = "canonical-wall-graph"
WALL_ENUMERATOR = "physical-wall-enumerator"
SCALE_PRODUCER = "viewport-scale-catalog"
SCALE_ENUMERATOR = "viewport-scale-enumerator"


def _scope(
    *,
    viewport_id: str = "vp",
    graph_snapshot_id: str = "graph-1",
    domain: str = WALL_DOMAIN,
    source_sha256: str = SHA,
    revision_id: str = "R1",
    evidence_snapshot_id: str = "ev-1",
) -> AuthorityScope:
    return AuthorityScope(
        domain=domain,
        document_id="doc",
        source_sha256=source_sha256,
        revision_id=revision_id,
        evidence_snapshot_id=evidence_snapshot_id,
        graph_snapshot_id=graph_snapshot_id,
        page_id="page-1",
        viewport_id=viewport_id,
    )


def _record(
    candidate_id: str,
    *,
    viewport_id: str = "vp",
    provenance: str | None = None,
    domain: str = WALL_DOMAIN,
    source_sha256: str = SHA,
    revision_id: str = "R1",
    evidence_snapshot_id: str = "ev-1",
    graph_snapshot_id: str = "graph-1",
) -> AuthenticatedEnumerationRecord:
    scope = _scope(
        viewport_id=viewport_id,
        domain=domain,
        source_sha256=source_sha256,
        revision_id=revision_id,
        evidence_snapshot_id=evidence_snapshot_id,
        graph_snapshot_id=graph_snapshot_id,
    )
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
        provenance_fingerprint=provenance
        or canonical_sha256({"candidate": candidate_id, "viewport": viewport_id, "domain": domain}),
    )


def _snapshot(
    *records: AuthenticatedEnumerationRecord,
    snapshot_id: str = "canonical-graph-1",
    producer_id: str = WALL_PRODUCER,
    producer_version: str = "1",
):
    return build_authenticated_parent_snapshot(
        snapshot_id=snapshot_id,
        producer_id=producer_id,
        producer_version=producer_version,
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


def _verify(
    *,
    parent,
    proof,
    universe,
    manifest,
    scope: AuthorityScope,
    admitted: tuple[str, ...],
    producer_id: str = WALL_PRODUCER,
    producer_version: str = "1",
    enumerator_id: str = WALL_ENUMERATOR,
    enumerator_version: str = "1",
):
    return verify_local_manifest_against_parent_snapshot(
        parent_snapshot=parent,
        proof=proof,
        local_universe=universe,
        manifest=manifest,
        expected_scope=scope,
        supplied_admitted_ids=admitted,
        expected_parent_producer_id=producer_id,
        expected_parent_producer_version=producer_version,
        expected_enumerator_id=enumerator_id,
        expected_enumerator_version=enumerator_version,
    )


def _wall_proof(parent, *, scope: AuthorityScope | None = None):
    return build_enumeration_proof(
        parent,
        scope=scope or _scope(),
        enumerator_id=WALL_ENUMERATOR,
        enumerator_version="1",
    )


def test_truncated_self_consistent_local_universe_is_rejected() -> None:
    w1, w2 = _record("W1"), _record("W2")
    parent = _snapshot(w1, w2)
    proof = _wall_proof(parent)

    truncated = _local_universe(_scope(), w1)
    manifest = _manifest(truncated, admitted=("W1",))
    result = _verify(parent=parent, proof=proof, universe=truncated, manifest=manifest, scope=_scope(), admitted=("W1",))
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "local_universe_does_not_match_authenticated_enumeration" in result.reasons


def test_fabricated_parent_snapshot_fingerprint_is_rejected() -> None:
    w1, w2 = _record("W1"), _record("W2")
    parent = _snapshot(w1, w2)
    proof = _wall_proof(parent)
    forged_parent = replace(parent, content_sha256=canonical_sha256({"records": ["W1"]}))
    universe = _local_universe(_scope(), w1, w2)
    manifest = _manifest(universe, admitted=("W1", "W2"))
    result = _verify(parent=forged_parent, proof=proof, universe=universe, manifest=manifest, scope=_scope(), admitted=("W1", "W2"))
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "parent_snapshot_content_fingerprint_mismatch" in result.reasons


def test_candidate_added_after_proof_is_stale() -> None:
    w1, w2 = _record("W1"), _record("W2")
    original = _snapshot(w1)
    proof = _wall_proof(original)
    current = _snapshot(w1, w2, snapshot_id=original.snapshot_id)
    universe = _local_universe(_scope(), w1, w2)
    manifest = _manifest(universe, admitted=("W1", "W2"))
    result = _verify(parent=current, proof=proof, universe=universe, manifest=manifest, scope=_scope(), admitted=("W1", "W2"))
    assert result.status == AuthorityBindingStatus.STALE


def test_candidate_removed_after_proof_is_stale() -> None:
    w1, w2 = _record("W1"), _record("W2")
    original = _snapshot(w1, w2)
    proof = _wall_proof(original)
    current = _snapshot(w1, snapshot_id=original.snapshot_id)
    universe = _local_universe(_scope(), w1)
    manifest = _manifest(universe, admitted=("W1",))
    result = _verify(parent=current, proof=proof, universe=universe, manifest=manifest, scope=_scope(), admitted=("W1",))
    assert result.status == AuthorityBindingStatus.STALE


def test_parent_and_proof_are_order_invariant() -> None:
    w1, w2 = _record("W1"), _record("W2")
    a = _snapshot(w1, w2)
    b = _snapshot(w2, w1)
    assert a.content_sha256 == b.content_sha256
    pa = _wall_proof(a)
    pb = _wall_proof(b)
    assert pa.proof_fingerprint == pb.proof_fingerprint
    assert pa.candidate_universe_fingerprint == pb.candidate_universe_fingerprint


def test_scope_isolation_ignores_unrelated_viewport_candidate() -> None:
    w1 = _record("W1")
    outside = _record("W-OUT", viewport_id="vp-other")
    parent = _snapshot(w1, outside)
    proof = _wall_proof(parent)
    universe = _local_universe(_scope(), w1)
    manifest = _manifest(universe, admitted=("W1",))
    result = _verify(parent=parent, proof=proof, universe=universe, manifest=manifest, scope=_scope(), admitted=("W1",))
    assert result.status == AuthorityBindingStatus.AUTHENTIC


def test_self_fingerprinted_incomplete_query_proof_is_rejected() -> None:
    w1, w2 = _record("W1"), _record("W2")
    parent = _snapshot(w1, w2)
    genuine = _wall_proof(parent)
    truncated = _local_universe(_scope(), w1)
    fake = replace(
        genuine,
        matched_candidate_ids=("W1",),
        candidate_count=1,
        candidate_universe_fingerprint=truncated.fingerprint,
    )
    fake = replace(fake, proof_fingerprint=canonical_sha256(fake.payload(include_fingerprint=False)))
    manifest = _manifest(truncated, admitted=("W1",))
    result = _verify(parent=parent, proof=fake, universe=truncated, manifest=manifest, scope=_scope(), admitted=("W1",))
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "enumeration_proof_does_not_match_parent_snapshot" in result.reasons


def test_same_id_with_mutated_provenance_invalidates_old_proof() -> None:
    old = _record("W1", provenance=canonical_sha256({"source": "old"}))
    new = _record("W1", provenance=canonical_sha256({"source": "new"}))
    original = _snapshot(old)
    proof = _wall_proof(original)
    current = _snapshot(new, snapshot_id=original.snapshot_id)
    universe = _local_universe(_scope(), new)
    manifest = _manifest(universe, admitted=("W1",))
    result = _verify(parent=current, proof=proof, universe=universe, manifest=manifest, scope=_scope(), admitted=("W1",))
    assert result.status == AuthorityBindingStatus.STALE


def test_proof_cannot_be_reused_across_viewports() -> None:
    w1 = _record("W1")
    outside = _record("W2", viewport_id="vp-other")
    parent = _snapshot(w1, outside)
    proof = _wall_proof(parent)
    other_scope = _scope(viewport_id="vp-other")
    universe = _local_universe(other_scope, outside)
    manifest = _manifest(universe, admitted=("W2",))
    result = _verify(parent=parent, proof=proof, universe=universe, manifest=manifest, scope=other_scope, admitted=("W2",))
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "enumeration_proof_scope_mismatch" in result.reasons


def test_valid_full_universe_can_feed_completeness_manifest_without_quantity_publication() -> None:
    w1, w2 = _record("W1"), _record("W2")
    parent = _snapshot(w1, w2)
    proof = _wall_proof(parent)
    universe = _local_universe(_scope(), w1, w2)
    manifest = _manifest(
        universe,
        admitted=("W1",),
        exclusions=(ExplicitExclusion("W2", "outside_declared_local_wall_set", ("scope-ev",)),),
    )
    result = _verify(parent=parent, proof=proof, universe=universe, manifest=manifest, scope=_scope(), admitted=("W1",))
    assert result.status == AuthorityBindingStatus.AUTHENTIC


def test_wrong_parent_producer_identity_is_rejected_even_with_valid_hash() -> None:
    w1 = _record("W1")
    parent = _snapshot(w1, producer_id="forged-wall-graph")
    proof = _wall_proof(parent)
    universe = _local_universe(_scope(), w1)
    manifest = _manifest(universe, admitted=("W1",))
    result = _verify(parent=parent, proof=proof, universe=universe, manifest=manifest, scope=_scope(), admitted=("W1",))
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "parent_snapshot_producer_mismatch" in result.reasons


def test_wrong_enumerator_identity_is_rejected_even_with_self_consistent_proof() -> None:
    w1 = _record("W1")
    parent = _snapshot(w1)
    proof = build_enumeration_proof(parent, scope=_scope(), enumerator_id="caller-enumerator", enumerator_version="1")
    universe = _local_universe(_scope(), w1)
    manifest = _manifest(universe, admitted=("W1",))
    result = _verify(parent=parent, proof=proof, universe=universe, manifest=manifest, scope=_scope(), admitted=("W1",))
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "enumeration_proof_enumerator_identity_mismatch" in result.reasons


def test_duplicate_candidate_id_in_same_scope_is_rejected_at_snapshot_build() -> None:
    first = _record("W1", provenance=canonical_sha256({"version": 1}))
    second = _record("W1", provenance=canonical_sha256({"version": 2}))
    with pytest.raises(ValueError, match="duplicate_authenticated_enumeration_record"):
        _snapshot(first, second)


def test_same_candidate_id_in_different_scope_is_allowed_and_isolated() -> None:
    local = _record("W1")
    remote = _record("W1", viewport_id="vp-other")
    parent = _snapshot(local, remote)
    proof = _wall_proof(parent)
    universe = _local_universe(_scope(), local)
    manifest = _manifest(universe, admitted=("W1",))
    result = _verify(parent=parent, proof=proof, universe=universe, manifest=manifest, scope=_scope(), admitted=("W1",))
    assert result.status == AuthorityBindingStatus.AUTHENTIC


def test_empty_scope_is_authentic_only_when_parent_proves_no_matching_records() -> None:
    outside = _record("W-OUT", viewport_id="vp-other")
    parent = _snapshot(outside)
    proof = _wall_proof(parent)
    universe = _local_universe(_scope())
    manifest = _manifest(universe, admitted=())
    result = _verify(parent=parent, proof=proof, universe=universe, manifest=manifest, scope=_scope(), admitted=())
    assert result.status == AuthorityBindingStatus.AUTHENTIC


def test_noncanonical_parent_order_is_rejected_even_if_attacker_rehashes_it() -> None:
    w1, w2 = _record("W1"), _record("W2")
    parent = _snapshot(w1, w2)
    reversed_parent = replace(parent, records=tuple(reversed(parent.records)), content_sha256="")
    reversed_parent = replace(reversed_parent, content_sha256=canonical_sha256(reversed_parent.content_payload()))
    proof = _wall_proof(parent)
    universe = _local_universe(_scope(), w1, w2)
    manifest = _manifest(universe, admitted=("W1", "W2"))
    result = _verify(parent=reversed_parent, proof=proof, universe=universe, manifest=manifest, scope=_scope(), admitted=("W1", "W2"))
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "parent_snapshot_record_order_noncanonical" in result.reasons


def test_upstream_source_revision_evidence_or_graph_mutation_invalidates_old_proof() -> None:
    original_record = _record("W1")
    original = _snapshot(original_record)
    proof = _wall_proof(original)
    mutations = (
        _record("W1", source_sha256="b" * 64),
        _record("W1", revision_id="R2"),
        _record("W1", evidence_snapshot_id="ev-2"),
        _record("W1", graph_snapshot_id="graph-2"),
    )
    for mutated in mutations:
        current = _snapshot(mutated, snapshot_id=original.snapshot_id)
        universe = _local_universe(_scope())
        manifest = _manifest(universe, admitted=())
        result = _verify(parent=current, proof=proof, universe=universe, manifest=manifest, scope=_scope(), admitted=())
        assert result.status == AuthorityBindingStatus.STALE


def test_same_contract_is_reusable_for_scale_domain_without_wall_specific_logic() -> None:
    scope = _scope(domain=SCALE_DOMAIN)
    s1 = _record("S1", domain=SCALE_DOMAIN)
    s2 = _record("S2", domain=SCALE_DOMAIN)
    parent = _snapshot(s1, s2, snapshot_id="viewport-scale-snapshot-1", producer_id=SCALE_PRODUCER)
    proof = build_enumeration_proof(
        parent,
        scope=scope,
        enumerator_id=SCALE_ENUMERATOR,
        enumerator_version="1",
    )
    universe = _local_universe(scope, s1, s2)
    manifest = _manifest(universe, admitted=("S1", "S2"))
    result = _verify(
        parent=parent,
        proof=proof,
        universe=universe,
        manifest=manifest,
        scope=scope,
        admitted=("S1", "S2"),
        producer_id=SCALE_PRODUCER,
        enumerator_id=SCALE_ENUMERATOR,
    )
    assert result.status == AuthorityBindingStatus.AUTHENTIC

    truncated = _local_universe(scope, s1)
    truncated_manifest = _manifest(truncated, admitted=("S1",))
    blocked = _verify(
        parent=parent,
        proof=proof,
        universe=truncated,
        manifest=truncated_manifest,
        scope=scope,
        admitted=("S1",),
        producer_id=SCALE_PRODUCER,
        enumerator_id=SCALE_ENUMERATOR,
    )
    assert blocked.status == AuthorityBindingStatus.MISMATCH
    assert "local_universe_does_not_match_authenticated_enumeration" in blocked.reasons
