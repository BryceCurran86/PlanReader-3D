"""Read-only GPT3 shadow: exact physical claims issued under different semantics.

The signed V1 exporter intentionally prevents partial physical-object overlap
within (family, semantic_key), not across semantic keys. Cross-key claims can
be a mutually exclusive reclassification *or* independently valid finish
layers. This module only identifies the source-owned object references
requiring human/source-issued semantic review. It never deduplicates, rejects
a commercial row, signs a new scope, or scores a benchmark.

Caller must supply an already source-closed run. V1 content fingerprints are
unkeyed digests, not proof of who issued the original construction claim.
Avoid publishing source-native identifiers from downstream private reviews.
"""
from __future__ import annotations

from collections import defaultdict
from hashlib import sha256
import json
from typing import Any

from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    sealed_source_closed_run_from_dict,
)

SHADOW_SCHEMA_VERSION = "gpt3.cross_semantic_physical_claims.shadow.v1"
_ELIGIBLE_STATUSES = frozenset({"firm", "corroborated"})


def audit_cross_semantic_physical_claims(run: SealedSourceClosedRun) -> dict[str, Any]:
    """Enumerate exact same-family/object, different-semantic-key conflicts.

    No fuzzy matching, area equality, project lookup, global family aliases,
    published customer output, or inferred room/finish type. An exact repeated
    physical reference across distinct source envelopes is *flagged for source
    review*; it is never asserted to prove the same physical object across
    drawings. An abstained, blocked or unverified row grants no FIRM claim.
    """
    if not isinstance(run, SealedSourceClosedRun):
        raise TypeError("verified SealedSourceClosedRun input required")
    checked = sealed_source_closed_run_from_dict(run.to_dict())
    indexed: dict[tuple[str, str], list[Any]] = defaultdict(list)
    withheld: list[str] = []
    considered = 0
    for row in checked.quantities:
        status = row.status.strip().lower()
        if row.abstained or not row.lineage_ok or status not in _ELIGIBLE_STATUSES:
            withheld.append(row.quantity_id)
            continue
        if not row.object_identity_refs:
            raise ValueError("FIRM source quantity has no exact physical object")
        considered += 1
        for physical_identity in row.object_identity_refs:
            indexed[(row.family, physical_identity)].append(row)

    flags: list[dict[str, Any]] = []
    for (family, physical_identity), rows in sorted(indexed.items()):
        keys = sorted({row.semantic_key for row in rows})
        if len(keys) <= 1:
            continue
        source_scopes = sorted({
            (row.source_sha256, row.document_id, row.revision_id) for row in rows
        })
        # A hash hides the original drawing's native object reference from a
        # routine diagnostic log. Exact original row IDs permit private review.
        identity_digest = sha256(json.dumps(
            [checked.project_id, family, physical_identity],
            ensure_ascii=False, separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        flags.append({
            "family": family,
            "physical_claim_sha256": identity_digest,
            "quantity_ids": sorted({row.quantity_id for row in rows}),
            "semantic_keys": keys,
            "source_envelope_count": len(source_scopes),
            "cross_source_envelope_review": len(source_scopes) > 1,
            "first_gate": "SOURCE_OWNED_SEMANTIC_CLAIM_EQUIVALENCE_UNPROVEN",
            "commercial_decision": "ABSTAIN_REVIEW_ONLY",
        })
    return {
        "schema_version": SHADOW_SCHEMA_VERSION,
        "source_run_id": checked.run_id,
        "source_run_fingerprint": checked.fingerprint,
        "project_id": checked.project_id,
        "considered_firm_or_corroborated_rows": considered,
        "excluded_unfirm_or_abstained_quantity_ids": sorted(withheld),
        "cross_semantic_overlap_groups": flags,
        "review_group_count": len(flags),
        "shadow_only": True,
        "source_issuer_equivalence_authenticated": False,
        "duplicate_claim_removed": False,
        "customer_output_approval_granted": False,
        "benchmark_score_granted": False,
    }
