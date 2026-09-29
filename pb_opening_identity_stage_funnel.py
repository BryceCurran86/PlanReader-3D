"""Gold-free stage-wise diagnostics for the existing Item35 opening shadow.

This module does not execute opening authorities directly. It summarizes the
producer-owned output of collect_item35_authority_shadow so diagnostics use
one execution path and cannot silently diverge from the live shadow chain.

Important limitation: Item35 shadow schema v1 exposes visibility/enumeration,
semantic completeness and generic-count publication, but it does not expose
per-opening prove_existence(), compare_identity(), or host-binding decisions.
Those stages are therefore reported as unobserved, never inferred.
"""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id


OPENING_IDENTITY_STAGE_FUNNEL_SCHEMA_VERSION = "1.0.0"


def _int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _codes(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple, set, frozenset)):
        return ()
    return tuple(sorted({str(item) for item in value if str(item)}))


def _stage(
    name: str,
    *,
    observed: bool,
    status: str | None,
    input_count: int | None,
    output_count: int | None,
    reason_codes: tuple[str, ...] = (),
    metrics: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "stage": name,
        "observed": bool(observed),
        "status": status,
        "input_count": input_count,
        "output_count": output_count,
        "reason_codes": list(reason_codes),
        "item_status_counts": None,
        "metrics": dict(metrics or {}),
    }


def build_opening_identity_stage_funnel(
    item35_shadow: Mapping[str, Any],
) -> dict[str, Any]:
    """Summarize only facts exposed by one Item35 shadow execution.

    item_status_counts remains None because schema v1 does not expose a
    per-item status vector at any stage. A later diagnostic seam may populate
    that field only from producer-owned records; this function must not infer it.
    """
    if not isinstance(item35_shadow, Mapping):
        raise TypeError("item35_shadow must be a mapping")

    document_id = item35_shadow.get("document_id")
    revision_id = item35_shadow.get("revision_id")
    source_sha256 = item35_shadow.get("source_sha256")
    snapshot_id = item35_shadow.get("snapshot_id")

    visible = _int(item35_shadow.get("visible_observation_count"))
    semantic_openings = _int(item35_shadow.get("semantic_opening_count"))
    supports = _int(item35_shadow.get("support_observation_count"))
    residual = _int(item35_shadow.get("residual_visible_observation_count"))
    semantic_codes = _codes(item35_shadow.get("semantic_reason_codes"))
    generic_codes = _codes(item35_shadow.get("generic_count_reason_codes"))

    semantic_wrapper_status = str(item35_shadow.get("status") or "abstained")
    if semantic_wrapper_status == "conflict":
        semantic_status = EvidenceResolutionStatus.CONFLICT.value
    elif semantic_wrapper_status == "evidence_present":
        semantic_status = EvidenceResolutionStatus.CORROBORATED.value
    else:
        semantic_status = EvidenceResolutionStatus.ABSTAINED.value

    structural_complete = bool(
        item35_shadow.get("structural_enumeration_complete", False)
    )
    universe_complete = bool(
        item35_shadow.get("physical_opening_universe_complete", False)
    )

    generic_raw = str(
        item35_shadow.get("generic_count_status")
        or EvidenceResolutionStatus.ABSTAINED.value
    )
    allowed_statuses = {
        EvidenceResolutionStatus.CORROBORATED.value,
        EvidenceResolutionStatus.ABSTAINED.value,
        EvidenceResolutionStatus.CONFLICT.value,
    }
    generic_status = (
        generic_raw
        if generic_raw in allowed_statuses
        else EvidenceResolutionStatus.ABSTAINED.value
    )

    stages = [
        _stage(
            "source_visibility",
            observed=bool(snapshot_id),
            status=None,
            input_count=None,
            output_count=visible,
            metrics={"visible_observation_count": visible},
        ),
        _stage(
            "semantic_opening_enumeration",
            observed=True,
            status=semantic_status,
            input_count=visible,
            output_count=semantic_openings,
            reason_codes=semantic_codes,
            metrics={
                "support_observation_count": supports,
                "residual_visible_observation_count": residual,
                "semantic_record_id": item35_shadow.get("semantic_record_id"),
            },
        ),
        _stage(
            "physical_opening_existence",
            observed=False,
            status=None,
            input_count=semantic_openings,
            output_count=None,
        ),
        _stage(
            "same_scope_identity",
            observed=False,
            status=None,
            input_count=semantic_openings,
            output_count=None,
        ),
        _stage(
            "opening_host_binding",
            observed=False,
            status=None,
            input_count=semantic_openings,
            output_count=None,
        ),
        _stage(
            "structural_enumeration_completeness",
            observed=True,
            status=(
                EvidenceResolutionStatus.CORROBORATED.value
                if structural_complete
                else EvidenceResolutionStatus.ABSTAINED.value
            ),
            input_count=semantic_openings,
            output_count=semantic_openings if structural_complete else None,
            reason_codes=semantic_codes,
            metrics={"complete": structural_complete},
        ),
        _stage(
            "physical_opening_universe_completeness",
            observed=True,
            status=(
                EvidenceResolutionStatus.CORROBORATED.value
                if universe_complete
                else EvidenceResolutionStatus.ABSTAINED.value
            ),
            input_count=semantic_openings,
            output_count=semantic_openings if universe_complete else None,
            reason_codes=semantic_codes,
            metrics={"complete": universe_complete},
        ),
        _stage(
            "generic_count_publication",
            observed=True,
            status=generic_status,
            input_count=semantic_openings,
            output_count=(
                _int(item35_shadow.get("generic_count"))
                if item35_shadow.get("generic_count") is not None
                else None
            ),
            reason_codes=generic_codes,
            metrics={
                "generic_count": item35_shadow.get("generic_count"),
                "commercial_count_unlocked": bool(
                    item35_shadow.get("commercial_count_unlocked", False)
                ),
            },
        ),
    ]

    payload = {
        "schema_version": OPENING_IDENTITY_STAGE_FUNNEL_SCHEMA_VERSION,
        "document_id": document_id,
        "revision_id": revision_id,
        "source_sha256": source_sha256,
        "snapshot_id": snapshot_id,
        "stages": stages,
    }
    return {
        "record_id": stable_contract_id(
            "opening_identity_stage_funnel", payload, digest_chars=32
        ),
        **payload,
        "source_shadow_schema_version": item35_shadow.get("schema_version"),
        "gold_free": True,
        "commercial_output_mutated": False,
    }


__all__ = [
    "OPENING_IDENTITY_STAGE_FUNNEL_SCHEMA_VERSION",
    "build_opening_identity_stage_funnel",
]
