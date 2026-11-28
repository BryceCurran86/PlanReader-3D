"""Read-only GPT3 shadow: exact physical claims issued under different semantics.

The signed V1 exporter rejects conflicting commercial opening claims.
Independent receipts can still be compared here without sealing them together. Cross-key claims can
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


def audit_cross_semantic_physical_claims(run: SealedSourceClosedRun | tuple[SealedSourceClosedRun, ...] | list[SealedSourceClosedRun]) -> dict[str, Any]:
    """Enumerate exact same-family/object, different-semantic-key conflicts.

    No fuzzy matching, area equality, project lookup, global family aliases,
    published customer output, or inferred room/finish type. An exact repeated
    physical reference across distinct source envelopes is *flagged for source
    review*; it is never asserted to prove the same physical object across
    drawings. An abstained, blocked or unverified row grants no FIRM claim.
    """
    # Conflicting candidate batches must never be combined into a commercial
    # seal merely to inspect them. Validate each independent receipt, then
    # compare them in this read-only diagnostic without creating a new run.
    if isinstance(run, SealedSourceClosedRun):
        checked = sealed_source_closed_run_from_dict(run.to_dict())
        rows = checked.quantities
        project_id = checked.project_id
        run_id = checked.run_id
        fingerprint = checked.fingerprint
    elif type(run) in (tuple, list) and run and all(
        isinstance(item, SealedSourceClosedRun) for item in run
    ):
        receipts = sorted(
            (sealed_source_closed_run_from_dict(item.to_dict()) for item in run),
            key=lambda item: item.fingerprint,
        )
        project_id = receipts[0].project_id
        if any(item.project_id != project_id for item in receipts):
            raise ValueError("diagnostic receipts must belong to one project")
        rows = tuple(row for item in receipts for row in item.quantities)
        if len({row.quantity_id for row in rows}) != len(rows):
            raise ValueError("diagnostic receipts have duplicate quantity IDs")
        fingerprint = sha256(json.dumps(
            [item.fingerprint for item in receipts], separators=(",", ":"),
        ).encode("utf-8")).hexdigest()
        run_id = "diagnostic-only:" + fingerprint
    else:
        raise TypeError("verified SealedSourceClosedRun input required")
    indexed: dict[tuple[str, str], list[Any]] = defaultdict(list)
    withheld: list[str] = []
    considered = 0
    for row in rows:
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
            [project_id, family, physical_identity],
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
        "source_run_id": run_id,
        "source_run_fingerprint": fingerprint,
        "project_id": project_id,
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
