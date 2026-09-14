"""Independent upstream-enumerator commitments for authority completeness.

A CompletenessManifest proves accounting *within* a universe; it does not prove
that the universe itself was complete.  This module binds an enumerated
universe to the immutable upstream snapshot from which the authoritative
enumerator produced it.

There is deliberately no secret constructor, nonce, trust boolean, Python
identity check, or signing key.  Authenticity is architectural: verification
requires the actual immutable upstream snapshot payload so its content digest
can be recomputed independently.  A caller-echoed snapshot id/fingerprint,
caller-curated candidate list, or self-consistent manifest cannot stand in for
that upstream content.

The current wall-length publication boundary intentionally does *not* expose an
upstream-snapshot-payload argument.  Until the canonical graph / viewport
producers supply their content-addressed snapshots directly, C1/C5 therefore
fail closed instead of pretending that a caller-provided digest is an
independent completeness proof.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional, Sequence

from pb_authority_completeness import (
    AuthorityBindingStatus,
    AuthorityScope,
    AuthorityUniverseFingerprint,
    AuthorityVerification,
    CompletenessManifest,
    canonical_sha256,
    verify_completeness_manifest,
)

ENUMERATOR_SNAPSHOT_COMMITMENT_SCHEMA_VERSION = "1.0.1"


@dataclass(frozen=True)
class EnumeratorSnapshotCommitment:
    scope: AuthorityScope
    enumerator_id: str
    enumerator_version: str
    upstream_snapshot_id: str
    upstream_snapshot_fingerprint: str
    candidate_universe_fingerprint: str
    candidate_count: int
    commitment_fingerprint: str
    schema_version: str = ENUMERATOR_SNAPSHOT_COMMITMENT_SCHEMA_VERSION


def immutable_snapshot_fingerprint(payload: object) -> str:
    """Content-address an immutable upstream snapshot payload deterministically."""
    return canonical_sha256(
        {
            "schema_version": ENUMERATOR_SNAPSHOT_COMMITMENT_SCHEMA_VERSION,
            "kind": "immutable_upstream_snapshot",
            "payload": payload,
        }
    )


def _payload(
    *,
    scope: AuthorityScope,
    enumerator_id: str,
    enumerator_version: str,
    upstream_snapshot_id: str,
    upstream_snapshot_fingerprint: str,
    candidate_universe_fingerprint: str,
    candidate_count: int,
) -> dict[str, object]:
    return {
        "schema_version": ENUMERATOR_SNAPSHOT_COMMITMENT_SCHEMA_VERSION,
        "scope": scope.payload(),
        "enumerator_id": enumerator_id,
        "enumerator_version": enumerator_version,
        "upstream_snapshot_id": upstream_snapshot_id,
        "upstream_snapshot_fingerprint": upstream_snapshot_fingerprint,
        "candidate_universe_fingerprint": candidate_universe_fingerprint,
        "candidate_count": candidate_count,
    }


def build_enumerator_snapshot_commitment(
    *,
    scope: AuthorityScope,
    enumerator_id: str,
    enumerator_version: str,
    upstream_snapshot_id: str,
    upstream_snapshot_fingerprint: str,
    candidate_universe: AuthorityUniverseFingerprint,
) -> EnumeratorSnapshotCommitment:
    if candidate_universe.scope != scope:
        raise ValueError("enumerator_commitment_scope_universe_mismatch")
    if not enumerator_id or not enumerator_version:
        raise ValueError("enumerator_identity_unbound")
    if not upstream_snapshot_id:
        raise ValueError("enumerator_upstream_snapshot_id_unbound")
    if not upstream_snapshot_fingerprint:
        raise ValueError("enumerator_upstream_snapshot_fingerprint_unbound")
    payload = _payload(
        scope=scope,
        enumerator_id=enumerator_id,
        enumerator_version=enumerator_version,
        upstream_snapshot_id=upstream_snapshot_id,
        upstream_snapshot_fingerprint=upstream_snapshot_fingerprint,
        candidate_universe_fingerprint=candidate_universe.fingerprint,
        candidate_count=len(candidate_universe.members),
    )
    return EnumeratorSnapshotCommitment(
        scope=scope,
        enumerator_id=enumerator_id,
        enumerator_version=enumerator_version,
        upstream_snapshot_id=upstream_snapshot_id,
        upstream_snapshot_fingerprint=upstream_snapshot_fingerprint,
        candidate_universe_fingerprint=candidate_universe.fingerprint,
        candidate_count=len(candidate_universe.members),
        commitment_fingerprint=canonical_sha256(payload),
    )


def verify_enumerator_snapshot_commitment(
    commitment: Optional[EnumeratorSnapshotCommitment],
    *,
    expected_scope: AuthorityScope,
    current_upstream_snapshot_id: Optional[str],
    current_upstream_snapshot_fingerprint: Optional[str],
    current_enumerated_universe: Optional[AuthorityUniverseFingerprint],
    manifest: Optional[CompletenessManifest],
    supplied_admitted_ids: Sequence[str],
    current_upstream_snapshot_payload: Optional[object] = None,
    require_resolved: bool = True,
) -> AuthorityVerification:
    """Verify snapshot content -> enumerator -> universe -> manifest provenance.

    ``current_upstream_snapshot_payload`` is the independent anchor.  A caller
    echoing a digest into ``current_upstream_snapshot_fingerprint`` cannot make
    a commitment authentic: without the actual immutable snapshot content the
    result is UNBOUND.  Publication code must obtain that payload from the
    upstream canonical producer, not from the quantity caller.
    """
    if commitment is None:
        return AuthorityVerification(
            AuthorityBindingStatus.UNBOUND,
            ("enumerator_snapshot_commitment_unbound",),
        )
    if (
        not current_upstream_snapshot_id
        or not current_upstream_snapshot_fingerprint
        or current_enumerated_universe is None
    ):
        return AuthorityVerification(
            AuthorityBindingStatus.UNBOUND,
            ("current_enumerator_snapshot_verification_unavailable",),
        )
    if current_upstream_snapshot_payload is None:
        return AuthorityVerification(
            AuthorityBindingStatus.UNBOUND,
            ("authoritative_upstream_snapshot_content_unavailable",),
        )

    recomputed_snapshot_fingerprint = immutable_snapshot_fingerprint(
        current_upstream_snapshot_payload
    )
    if recomputed_snapshot_fingerprint != current_upstream_snapshot_fingerprint:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("current_upstream_snapshot_content_fingerprint_mismatch",),
        )

    if commitment.scope != expected_scope:
        stale_fields = (
            commitment.scope.source_sha256 != expected_scope.source_sha256
            or commitment.scope.revision_id != expected_scope.revision_id
            or commitment.scope.evidence_snapshot_id != expected_scope.evidence_snapshot_id
            or commitment.scope.graph_snapshot_id != expected_scope.graph_snapshot_id
        )
        return AuthorityVerification(
            AuthorityBindingStatus.STALE if stale_fields else AuthorityBindingStatus.MISMATCH,
            ("enumerator_commitment_scope_mismatch",),
        )

    rebuilt_fingerprint = canonical_sha256(
        _payload(
            scope=commitment.scope,
            enumerator_id=commitment.enumerator_id,
            enumerator_version=commitment.enumerator_version,
            upstream_snapshot_id=commitment.upstream_snapshot_id,
            upstream_snapshot_fingerprint=commitment.upstream_snapshot_fingerprint,
            candidate_universe_fingerprint=commitment.candidate_universe_fingerprint,
            candidate_count=commitment.candidate_count,
        )
    )
    if rebuilt_fingerprint != commitment.commitment_fingerprint:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("enumerator_commitment_fingerprint_mismatch",),
        )
    if commitment.schema_version != ENUMERATOR_SNAPSHOT_COMMITMENT_SCHEMA_VERSION:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("enumerator_commitment_schema_mismatch",),
        )
    if commitment.upstream_snapshot_id != current_upstream_snapshot_id:
        return AuthorityVerification(
            AuthorityBindingStatus.STALE,
            ("enumerator_upstream_snapshot_id_stale",),
        )
    if commitment.upstream_snapshot_fingerprint != current_upstream_snapshot_fingerprint:
        return AuthorityVerification(
            AuthorityBindingStatus.STALE,
            ("enumerator_upstream_snapshot_fingerprint_stale",),
        )
    if current_enumerated_universe.scope != expected_scope:
        return AuthorityVerification(
            AuthorityBindingStatus.STALE,
            ("current_enumerated_universe_scope_stale",),
        )
    if commitment.candidate_count != len(current_enumerated_universe.members):
        return AuthorityVerification(
            AuthorityBindingStatus.STALE,
            ("enumerator_candidate_count_stale",),
        )
    if commitment.candidate_universe_fingerprint != current_enumerated_universe.fingerprint:
        return AuthorityVerification(
            AuthorityBindingStatus.STALE,
            ("enumerator_candidate_universe_stale",),
        )
    if manifest is None:
        return AuthorityVerification(
            AuthorityBindingStatus.UNBOUND,
            ("enumerator_completeness_manifest_unbound",),
        )
    if manifest.authority_universe_fingerprint != commitment.candidate_universe_fingerprint:
        return AuthorityVerification(
            AuthorityBindingStatus.MISMATCH,
            ("manifest_not_bound_to_enumerator_commitment",),
        )

    manifest_verification = verify_completeness_manifest(
        manifest,
        current_universe=current_enumerated_universe,
        expected_scope=expected_scope,
        supplied_admitted_ids=supplied_admitted_ids,
        require_resolved=require_resolved,
    )
    if not manifest_verification.authentic:
        return manifest_verification
    return AuthorityVerification(AuthorityBindingStatus.AUTHENTIC)


__all__ = [
    "ENUMERATOR_SNAPSHOT_COMMITMENT_SCHEMA_VERSION",
    "EnumeratorSnapshotCommitment",
    "build_enumerator_snapshot_commitment",
    "immutable_snapshot_fingerprint",
    "verify_enumerator_snapshot_commitment",
]
