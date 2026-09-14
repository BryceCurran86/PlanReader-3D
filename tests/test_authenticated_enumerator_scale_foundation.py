"""Scale-domain controls for the generic authenticated enumerator foundation."""
from __future__ import annotations

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

DOMAIN = "wall_length.scale"
SHA = "a" * 64


def _scope() -> AuthorityScope:
    return AuthorityScope(
        domain=DOMAIN,
        document_id="doc",
        source_sha256=SHA,
        revision_id="R1",
        evidence_snapshot_id="ev-1",
        graph_snapshot_id="viewport-catalog-1",
        page_id="page-1",
        viewport_id="vp",
    )


def _record(candidate_id: str) -> AuthenticatedEnumerationRecord:
    scope = _scope()
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
        provenance_fingerprint=canonical_sha256({"scale": candidate_id}),
    )


def _universe(*records: AuthenticatedEnumerationRecord):
    return build_authority_universe(
        _scope(),
        tuple(AuthorityUniverseMember(record.candidate_id, record.provenance_fingerprint) for record in records),
    )


def test_full_scale_catalog_can_prove_one_admitted_scale_and_evidenced_exclusion() -> None:
    s1, s2 = _record("S1"), _record("S2")
    parent = build_authenticated_parent_snapshot(
        snapshot_id="scale-parent-1",
        producer_id="viewport-scale-catalog",
        producer_version="1",
        records=(s1, s2),
    )
    proof = build_enumeration_proof(
        parent,
        scope=_scope(),
        enumerator_id="viewport-scale-enumerator",
        enumerator_version="1",
    )
    universe = _universe(s1, s2)
    manifest = build_completeness_manifest(
        universe,
        admitted_candidate_ids=("S1",),
        explicit_exclusions=(ExplicitExclusion("S2", "non_authoritative_scale_source", ("scale-exclusion-ev",)),),
    )
    result = verify_local_manifest_against_parent_snapshot(
        parent_snapshot=parent,
        proof=proof,
        local_universe=universe,
        manifest=manifest,
        expected_scope=_scope(),
        supplied_admitted_ids=("S1",),
        expected_parent_producer_id="viewport-scale-catalog",
        expected_parent_producer_version="1",
        expected_enumerator_id="viewport-scale-enumerator",
        expected_enumerator_version="1",
    )
    assert result.status == AuthorityBindingStatus.AUTHENTIC


def test_truncated_scale_catalog_is_rejected_even_when_local_manifest_is_self_consistent() -> None:
    s1, s2 = _record("S1"), _record("S2")
    parent = build_authenticated_parent_snapshot(
        snapshot_id="scale-parent-1",
        producer_id="viewport-scale-catalog",
        producer_version="1",
        records=(s1, s2),
    )
    proof = build_enumeration_proof(
        parent,
        scope=_scope(),
        enumerator_id="viewport-scale-enumerator",
        enumerator_version="1",
    )
    truncated = _universe(s1)
    manifest = build_completeness_manifest(truncated, admitted_candidate_ids=("S1",))
    result = verify_local_manifest_against_parent_snapshot(
        parent_snapshot=parent,
        proof=proof,
        local_universe=truncated,
        manifest=manifest,
        expected_scope=_scope(),
        supplied_admitted_ids=("S1",),
        expected_parent_producer_id="viewport-scale-catalog",
        expected_parent_producer_version="1",
        expected_enumerator_id="viewport-scale-enumerator",
        expected_enumerator_version="1",
    )
    assert result.status == AuthorityBindingStatus.MISMATCH
    assert "local_universe_does_not_match_authenticated_enumeration" in result.reasons
