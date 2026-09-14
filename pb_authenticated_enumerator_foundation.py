"""Content-addressed parent snapshots and independently recomputable enumeration proofs.

This module is the first post-#297 upstream trust layer.  It deliberately does
*not* reopen quantity publication and it does not claim that hashing by itself
proves completeness.  The architectural invariant is:

    independently obtained immutable parent snapshot content
        -> deterministic declarative scope enumeration
        -> recomputable enumeration proof
        -> local AuthorityUniverseFingerprint
        -> CompletenessManifest

The verifier must receive the complete parent snapshot from an upstream
producer channel, not from the quantity caller's selected candidate list.  A
self-consistent local universe, manifest, or self-fingerprinted proof cannot
substitute for recomputation from that parent content.

This is intentionally not a Merkle tree, JCS implementation, authenticated
spatial index, or succinct range proof.  The first foundation verifies a local
query by recomputing it against the complete parent snapshot payload.  A later
optimization branch may make that proof smaller/faster without changing the
authority semantics established here.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from pb_authority_completeness import (
    AuthorityBindingStatus,
    AuthorityScope,
    AuthorityUniverseFingerprint,
    AuthorityUniverseMember,
    AuthorityVerification,
    CompletenessManifest,
    build_authority_universe,
    canonical_sha256,
    verify_completeness_manifest,
)

AUTHENTICATED_ENUMERATOR_FOUNDATION_SCHEMA_VERSION = "1.0.0"


@dataclass(frozen=True)
class AuthenticatedEnumerationRecord:
    """One enumeratable record materialized in the immutable parent snapshot.

    ``provenance_fingerprint`` must bind the candidate's authority-relevant
    payload/provenance before it enters this layer.  This layer additionally
    binds the candidate to its exact architectural scope.
    """

    candidate_id: str
    domain: str
    document_id: str
    source_sha256: str
    revision_id: str
    evidence_snapshot_id: str
    graph_snapshot_id: str
    page_id: str
    viewport_id: str
    provenance_fingerprint: str
    schema_version: str = AUTHENTICATED_ENUMERATOR_FOUNDATION_SCHEMA_VERSION

    def payload(self) -> dict[str, str]:
        return {
            "schema_version": self.schema_version,
            "candidate_id": self.candidate_id,
            "domain": self.domain,
            "document_id": self.document_id,
            "source_sha256": self.source_sha256,
            "revision_id": self.revision_id,
            "evidence_snapshot_id": self.evidence_snapshot_id,
            "graph_snapshot_id": self.graph_snapshot_id,
            "page_id": self.page_id,
            "viewport_id": self.viewport_id,
            "provenance_fingerprint": self.provenance_fingerprint,
        }

    def scope_key(self) -> tuple[str, ...]:
        return (
            self.domain,
            self.document_id,
            self.source_sha256,
            self.revision_id,
            self.evidence_snapshot_id,
            self.graph_snapshot_id,
            self.page_id,
            self.viewport_id,
            self.candidate_id,
        )


@dataclass(frozen=True)
class AuthenticatedParentSnapshot:
    """Immutable content-addressed materialization produced upstream.

    ``snapshot_id`` is a human/system identity label. ``content_sha256`` is
    independently recomputable from producer identity and the complete sorted
    record content.  Neither field alone establishes provenance; integration
    must obtain this object from the upstream producer rather than the quantity
    caller.
    """

    snapshot_id: str
    producer_id: str
    producer_version: str
    records: tuple[AuthenticatedEnumerationRecord, ...]
    content_sha256: str
    schema_version: str = AUTHENTICATED_ENUMERATOR_FOUNDATION_SCHEMA_VERSION

    def content_payload(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "kind": "authenticated_parent_snapshot",
            "producer_id": self.producer_id,
            "producer_version": self.producer_version,
            "records": [item.payload() for item in self.records],
        }


@dataclass(frozen=True)
class AuthenticatedEnumerationProof:
    """Deterministic proof of one exact-scope enumeration over a parent.

    This proof is independently verifiable only together with the immutable
    parent snapshot content.  It is intentionally not a cryptographic range
    proof: the verifier recomputes the exact-scope query from the parent.
    """

    parent_snapshot_id: str
    parent_snapshot_content_sha256: str
    scope: AuthorityScope
    enumerator_id: str
    enumerator_version: str
    matched_candidate_ids: tuple[str, ...]
    candidate_universe_fingerprint: str
    candidate_count: int
    proof_fingerprint: str
    schema_version: str = AUTHENTICATED_ENUMERATOR_FOUNDATION_SCHEMA_VERSION

    def payload(self, *, include_fingerprint: bool = True) -> dict[str, object]:
        payload: dict[str, object] = {
            "schema_version": self.schema_version,
            "kind": "authenticated_enumeration_proof",
            "parent_snapshot_id": self.parent_snapshot_id,
            "parent_snapshot_content_sha256": self.parent_snapshot_content_sha256,
            "scope": self.scope.payload(),
            "enumerator_id": self.enumerator_id,
            "enumerator_version": self.enumerator_version,
            "matched_candidate_ids": list(self.matched_candidate_ids),
            "candidate_universe_fingerprint": self.candidate_universe_fingerprint,
            "candidate_count": self.candidate_count,
        }
        if include_fingerprint:
            payload["proof_fingerprint"] = self.proof_fingerprint
        return payload


def _validate_record(record: AuthenticatedEnumerationRecord) -> None:
    values = (
        record.candidate_id,
        record.domain,
        record.document_id,
        record.source_sha256,
        record.revision_id,
        record.evidence_snapshot_id,
        record.graph_snapshot_id,
        record.page_id,
        record.viewport_id,
        record.provenance_fingerprint,
    )
    if any(not value for value in values):
        raise ValueError("authenticated_enumeration_record_unbound")
    if record.schema_version != AUTHENTICATED_ENUMERATOR_FOUNDATION_SCHEMA_VERSION:
        raise ValueError("authenticated_enumeration_record_schema_mismatch")


def _ordered_records(
    records: Sequence[AuthenticatedEnumerationRecord],
) -> tuple[AuthenticatedEnumerationRecord, ...]:
    for item in records:
        _validate_record(item)
    ordered = tuple(
        sorted(
            records,
            key=lambda item: (*item.scope_key(), item.provenance_fingerprint),
        )
    )
    keys = [item.scope_key() for item in ordered]
    if len(keys) != len(set(keys)):
        raise ValueError("duplicate_authenticated_enumeration_record")
    return ordered


def build_authenticated_parent_snapshot(
    *,
    snapshot_id: str,
    producer_id: str,
    producer_version: str,
    records: Sequence[AuthenticatedEnumerationRecord],
) -> AuthenticatedParentSnapshot:
    """Content-address a complete upstream materialization.

    This function does not claim the caller supplied a complete producer
    snapshot.  Completeness authority comes only when integration obtains the
    returned snapshot from the designated upstream producer channel.  The
    contract makes later truncation/mutation detectable.
    """
    if not snapshot_id:
        raise ValueError("parent_snapshot_id_unbound")
    if not producer_id or not producer_version:
        raise ValueError("parent_snapshot_producer_unbound")
    ordered = _ordered_records(records)
    provisional = AuthenticatedParentSnapshot(
        snapshot_id=snapshot_id,
        producer_id=producer_id,
        producer_version=producer_version,
        records=ordered,
        content_sha256="",
    )
    digest = canonical_sha256(provisional.content_payload())
    return AuthenticatedParentSnapshot(
        snapshot_id=snapshot_id,
        producer_id=producer_id,
        producer_version=producer_version,
        records=ordered,
        content_sha256=digest,
    )


def _verify_parent_snapshot(
    snapshot: AuthenticatedParentSnapshot,
    *,
    expected_producer_id: str,
    expected_producer_version: str,
) -> AuthorityVerification:
    if snapshot.schema_version != AUTHENTICATED_ENUMERATOR_FOUNDATION_SCHEMA_VERSION:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("parent_snapshot_schema_mismatch",),
        )
    if snapshot.producer_id != expected_producer_id or snapshot.producer_version != expected_producer_version:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("parent_snapshot_producer_mismatch",),
        )
    try:
        ordered = _ordered_records(snapshot.records)
    except (TypeError, ValueError) as exc:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            (f"parent_snapshot_records_invalid:{exc}",),
        )
    if ordered != snapshot.records:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("parent_snapshot_record_order_noncanonical",),
        )
    recomputed = canonical_sha256(snapshot.content_payload())
    if recomputed != snapshot.content_sha256:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("parent_snapshot_content_fingerprint_mismatch",),
        )
    return AuthorityVerification(AuthorityBindingStatus.AUTHENTIC)


def _matches_scope(record: AuthenticatedEnumerationRecord, scope: AuthorityScope) -> bool:
    return (
        record.domain == scope.domain
        and record.document_id == scope.document_id
        and record.source_sha256 == scope.source_sha256
        and record.revision_id == scope.revision_id
        and record.evidence_snapshot_id == scope.evidence_snapshot_id
        and record.graph_snapshot_id == scope.graph_snapshot_id
        and record.page_id == scope.page_id
        and record.viewport_id == scope.viewport_id
    )


def reconstruct_scoped_universe(
    parent_snapshot: AuthenticatedParentSnapshot,
    *,
    scope: AuthorityScope,
) -> AuthorityUniverseFingerprint:
    """Recompute the complete exact-scope universe from parent content."""
    members = tuple(
        AuthorityUniverseMember(item.candidate_id, item.provenance_fingerprint)
        for item in parent_snapshot.records
        if _matches_scope(item, scope)
    )
    return build_authority_universe(scope, members)


def build_enumeration_proof(
    parent_snapshot: AuthenticatedParentSnapshot,
    *,
    scope: AuthorityScope,
    enumerator_id: str,
    enumerator_version: str,
) -> AuthenticatedEnumerationProof:
    if not enumerator_id or not enumerator_version:
        raise ValueError("authenticated_enumerator_identity_unbound")
    # Building a proof from corrupted snapshot content is never permitted.
    recomputed_parent = canonical_sha256(parent_snapshot.content_payload())
    if recomputed_parent != parent_snapshot.content_sha256:
        raise ValueError("parent_snapshot_content_fingerprint_mismatch")
    universe = reconstruct_scoped_universe(parent_snapshot, scope=scope)
    candidate_ids = tuple(item.candidate_id for item in universe.members)
    provisional = AuthenticatedEnumerationProof(
        parent_snapshot_id=parent_snapshot.snapshot_id,
        parent_snapshot_content_sha256=parent_snapshot.content_sha256,
        scope=scope,
        enumerator_id=enumerator_id,
        enumerator_version=enumerator_version,
        matched_candidate_ids=candidate_ids,
        candidate_universe_fingerprint=universe.fingerprint,
        candidate_count=len(universe.members),
        proof_fingerprint="",
    )
    digest = canonical_sha256(provisional.payload(include_fingerprint=False))
    return AuthenticatedEnumerationProof(
        parent_snapshot_id=provisional.parent_snapshot_id,
        parent_snapshot_content_sha256=provisional.parent_snapshot_content_sha256,
        scope=provisional.scope,
        enumerator_id=provisional.enumerator_id,
        enumerator_version=provisional.enumerator_version,
        matched_candidate_ids=provisional.matched_candidate_ids,
        candidate_universe_fingerprint=provisional.candidate_universe_fingerprint,
        candidate_count=provisional.candidate_count,
        proof_fingerprint=digest,
    )


def verify_local_manifest_against_parent_snapshot(
    *,
    parent_snapshot: AuthenticatedParentSnapshot,
    proof: Optional[AuthenticatedEnumerationProof],
    local_universe: Optional[AuthorityUniverseFingerprint],
    manifest: Optional[CompletenessManifest],
    expected_scope: AuthorityScope,
    supplied_admitted_ids: Sequence[str],
    expected_parent_producer_id: str = "canonical-wall-graph",
    expected_parent_producer_version: str = "1",
    expected_enumerator_id: str = "physical-wall-enumerator",
    expected_enumerator_version: str = "1",
    require_resolved: bool = True,
) -> AuthorityVerification:
    """Verify parent -> enumerator -> local universe -> manifest.

    The verifier identity is itself part of the trust boundary.  An integration
    that cannot name the producer and enumerator/version it expects is UNBOUND;
    an empty expectation must never be satisfiable by caller-controlled data.
    The quantity publication boundary is deliberately not wired to this
    function in this branch.
    """
    expected_identity = (
        expected_parent_producer_id,
        expected_parent_producer_version,
        expected_enumerator_id,
        expected_enumerator_version,
    )
    if any(not str(value or "").strip() for value in expected_identity):
        return AuthorityVerification(
            AuthorityBindingStatus.UNBOUND,
            ("expected_authority_identity_unbound",),
        )

    parent_verification = _verify_parent_snapshot(
        parent_snapshot,
        expected_producer_id=expected_parent_producer_id,
        expected_producer_version=expected_parent_producer_version,
    )
    if not parent_verification.authentic:
        return parent_verification
    if proof is None:
        return AuthorityVerification(
            AuthorityBindingStatus.UNBOUND,
            ("authenticated_enumeration_proof_unbound",),
        )
    if proof.scope != expected_scope:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("enumeration_proof_scope_mismatch",),
        )
    if (
        proof.enumerator_id != expected_enumerator_id
        or proof.enumerator_version != expected_enumerator_version
    ):
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("enumeration_proof_enumerator_identity_mismatch",),
        )
    if proof.parent_snapshot_id != parent_snapshot.snapshot_id:
        return AuthorityVerification(
            AuthorityBindingStatus.STALE,
            ("enumeration_proof_parent_snapshot_id_stale",),
        )
    if proof.parent_snapshot_content_sha256 != parent_snapshot.content_sha256:
        return AuthorityVerification(
            AuthorityBindingStatus.STALE,
            ("enumeration_proof_parent_snapshot_content_stale",),
        )

    recomputed_proof = build_enumeration_proof(
        parent_snapshot,
        scope=expected_scope,
        enumerator_id=expected_enumerator_id,
        enumerator_version=expected_enumerator_version,
    )
    if proof != recomputed_proof:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("enumeration_proof_does_not_match_parent_snapshot",),
        )

    if local_universe is None:
        return AuthorityVerification(
            AuthorityBindingStatus.UNBOUND,
            ("local_authority_universe_unbound",),
        )
    reconstructed_universe = reconstruct_scoped_universe(
        parent_snapshot,
        scope=expected_scope,
    )
    if (
        local_universe.scope != expected_scope
        or local_universe.fingerprint != reconstructed_universe.fingerprint
        or local_universe.members != reconstructed_universe.members
        or local_universe.fingerprint != proof.candidate_universe_fingerprint
    ):
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("local_universe_does_not_match_authenticated_enumeration",),
        )

    return verify_completeness_manifest(
        manifest,
        current_universe=reconstructed_universe,
        expected_scope=expected_scope,
        supplied_admitted_ids=supplied_admitted_ids,
        require_resolved=require_resolved,
    )


__all__ = [
    "AUTHENTICATED_ENUMERATOR_FOUNDATION_SCHEMA_VERSION",
    "AuthenticatedEnumerationProof",
    "AuthenticatedEnumerationRecord",
    "AuthenticatedParentSnapshot",
    "build_authenticated_parent_snapshot",
    "build_enumeration_proof",
    "reconstruct_scoped_universe",
    "verify_local_manifest_against_parent_snapshot",
]
