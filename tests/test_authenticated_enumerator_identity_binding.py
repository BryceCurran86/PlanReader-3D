"""Expected producer/enumerator identities are part of the verifier trust boundary."""
from __future__ import annotations

import pytest

from pb_authority_completeness import AuthorityBindingStatus, AuthorityScope, AuthorityUniverseMember, build_authority_universe, build_completeness_manifest, canonical_sha256
from pb_authenticated_enumerator_foundation import AuthenticatedEnumerationRecord, build_authenticated_parent_snapshot, build_enumeration_proof, verify_local_manifest_against_parent_snapshot


def _fixture():
    scope = AuthorityScope(
        domain="wall_length.physical_candidates",
        document_id="doc",
        source_sha256="a" * 64,
        revision_id="R1",
        evidence_snapshot_id="ev-1",
        graph_snapshot_id="graph-1",
        page_id="page-1",
        viewport_id="vp",
    )
    record = AuthenticatedEnumerationRecord(
        candidate_id="W1",
        domain=scope.domain,
        document_id=scope.document_id,
        source_sha256=scope.source_sha256,
        revision_id=scope.revision_id,
        evidence_snapshot_id=scope.evidence_snapshot_id,
        graph_snapshot_id=scope.graph_snapshot_id,
        page_id=scope.page_id,
        viewport_id=scope.viewport_id,
        provenance_fingerprint=canonical_sha256({"wall": "W1"}),
    )
    parent = build_authenticated_parent_snapshot(
        snapshot_id="parent-1",
        producer_id="canonical-wall-graph",
        producer_version="1",
        records=(record,),
    )
    proof = build_enumeration_proof(
        parent,
        scope=scope,
        enumerator_id="physical-wall-enumerator",
        enumerator_version="1",
    )
    universe = build_authority_universe(
        scope,
        (AuthorityUniverseMember(record.candidate_id, record.provenance_fingerprint),),
    )
    manifest = build_completeness_manifest(universe, admitted_candidate_ids=("W1",))
    return scope, parent, proof, universe, manifest


@pytest.mark.parametrize(
    "identity_overrides",
    [
        {"expected_parent_producer_id": ""},
        {"expected_parent_producer_version": ""},
        {"expected_enumerator_id": ""},
        {"expected_enumerator_version": ""},
    ],
)
def test_unbound_expected_authority_identity_fails_closed(identity_overrides) -> None:
    scope, parent, proof, universe, manifest = _fixture()
    kwargs = dict(
        parent_snapshot=parent,
        proof=proof,
        local_universe=universe,
        manifest=manifest,
        expected_scope=scope,
        supplied_admitted_ids=("W1",),
        expected_parent_producer_id="canonical-wall-graph",
        expected_parent_producer_version="1",
        expected_enumerator_id="physical-wall-enumerator",
        expected_enumerator_version="1",
    )
    kwargs.update(identity_overrides)
    result = verify_local_manifest_against_parent_snapshot(**kwargs)
    assert result.status == AuthorityBindingStatus.UNBOUND
    assert "expected_authority_identity_unbound" in result.reasons
