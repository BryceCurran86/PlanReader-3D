"""Producer-owned F.07 SegmentedViewport -> migration ViewportEvidence adapter.

This module is the only authority-bearing bridge for DERIVED F.07 viewport
ownership.  It never trusts ViewportEvidence.metadata as certification.

The adapter requires the complete page-level F.07 output, verifies that every
record is an unmodified product of segment_page_viewports, checks sibling
non-overlap and provider ownership, and then preserves F.07 provenance into
ViewportEvidence metadata for observability.

DERIVED authority is granted only when the unchanged existing
is_authoritative_derived_viewport predicate succeeds.  A separate sealed proof
object is returned so downstream consumers can distinguish producer-owned
lineage from caller-populated metadata.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Any, Mapping, Optional, Sequence

from pb_migration_contracts import (
    ViewportEvidence,
    ViewportResolutionStatus,
    stable_contract_id,
)
from pb_migration_provider_envelope import ProviderContext
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    is_segment_page_viewports_product,
    segmented_viewport_producer_fingerprint,
    validate_non_overlapping_viewports,
)

F07_VIEWPORT_MIGRATION_SCHEMA_VERSION = "1.0.0"
F07_VIEWPORT_PRODUCER = "pb_viewport_segmentation.segment_page_viewports"

F07_VIEWPORT_ADAPTER_OK = "f07_viewport_adapter_ok"
F07_VIEWPORT_ADAPTER_UNAVAILABLE = "f07_viewport_adapter_unavailable"
F07_VIEWPORT_PRODUCER_LINEAGE_INVALID = "f07_viewport_producer_lineage_invalid"
F07_VIEWPORT_SIBLING_OVERLAP = "f07_viewport_sibling_overlap"
F07_VIEWPORT_NOT_AUTHORITATIVE = "f07_viewport_not_authoritative"
F07_VIEWPORT_TITLE_OWNERSHIP_CHANGED = "f07_viewport_title_ownership_changed"
F07_VIEWPORT_SCOPE_MISMATCH = "f07_viewport_scope_mismatch"

_PROOF_SEAL = object()

_PROVENANCE_KEYS = (
    "partition_mode",
    "grid_validated",
    "column_index",
    "column_count",
    "row_index",
    "row_count",
    "title_bbox",
    "duplicate_title_bboxes",
)


@dataclass(frozen=True)
class F07ViewportOwnershipProof:
    ownership_id: str
    document_id: str
    source_sha256: str
    revision_id: str
    page_no: int
    viewport_id: str
    view_type: str
    status: str
    bbox: tuple[float, float, float, float]
    title_bbox: tuple[float, float, float, float]
    boundary_source: str
    producer_fingerprint: str
    sibling_set_fingerprint: str
    authoritative_derived: bool
    schema_version: str = F07_VIEWPORT_MIGRATION_SCHEMA_VERSION
    _seal: Any = field(default=None, repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._seal is not _PROOF_SEAL:
            raise ValueError(
                "F07ViewportOwnershipProof may only be created by the F.07 migration adapter"
            )


@dataclass(frozen=True)
class F07ViewportMigrationResult:
    viewport: Optional[ViewportEvidence]
    ownership_proof: Optional[F07ViewportOwnershipProof]
    blocking_reasons: tuple[str, ...]
    schema_version: str = F07_VIEWPORT_MIGRATION_SCHEMA_VERSION

    @property
    def abstained(self) -> bool:
        return self.viewport is None or self.ownership_proof is None


def _bbox_tuple(value: Sequence[float]) -> tuple[float, float, float, float]:
    if len(value) != 4:
        raise ValueError("bbox must contain four coordinates")
    bbox = tuple(float(v) for v in value)
    if not all(math.isfinite(v) for v in bbox):
        raise ValueError("bbox coordinates must be finite")
    return bbox  # type: ignore[return-value]


def _normalise_metadata_value(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {
            str(key): _normalise_metadata_value(value[key])
            for key in sorted(value, key=lambda item: str(item))
        }
    if isinstance(value, (list, tuple)):
        return tuple(_normalise_metadata_value(item) for item in value)
    return value


def _visible_provenance(viewport: SegmentedViewport) -> dict[str, Any]:
    provenance = viewport.provenance or {}
    copied = {
        key: _normalise_metadata_value(provenance.get(key))
        for key in _PROVENANCE_KEYS
        if key in provenance
    }
    copied["boundary_source"] = str(viewport.boundary_source)
    copied["producer"] = F07_VIEWPORT_PRODUCER
    copied["producer_fingerprint"] = segmented_viewport_producer_fingerprint(viewport)
    return copied


def _sibling_set_fingerprint(viewports: Sequence[SegmentedViewport]) -> str:
    payload = [
        {
            "view_id": viewport.view_id,
            "producer_fingerprint": segmented_viewport_producer_fingerprint(viewport),
        }
        for viewport in sorted(viewports, key=lambda item: item.view_id)
    ]
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _context_reasons(
    *,
    context: ProviderContext,
    page_no: int,
    viewport_id: str,
) -> list[str]:
    reasons: list[str] = []
    if not context.document_id:
        reasons.append("document_id_missing")
    if not context.source_sha256:
        reasons.append("source_sha256_missing")
    if not context.revision_id or not context.current_revision_id:
        reasons.append("revision_unbound")
    elif context.revision_id != context.current_revision_id:
        reasons.append("stale_revision")
    if int(page_no) not in context.trusted_page_numbers():
        reasons.append("page_not_owned")
    if viewport_id not in context.trusted_viewport_ids():
        reasons.append("viewport_not_owned")
    mapped = context.page_for_viewport(viewport_id)
    if mapped is None or int(mapped) != int(page_no):
        reasons.append("viewport_page_ownership_missing")
    return reasons


def _title_ownership_unchanged(viewport: SegmentedViewport) -> bool:
    provenance = viewport.provenance or {}
    producer_title_bbox = provenance.get("title_bbox")
    if producer_title_bbox is None:
        # RESOLVED F.07 records carry title_bbox in provenance; authoritative
        # derived records do too. Missing lineage must fail closed.
        return False
    try:
        return _bbox_tuple(producer_title_bbox) == _bbox_tuple(viewport.title_bbox)
    except (TypeError, ValueError):
        return False


def adapt_f07_viewport_to_migration(
    viewports: Sequence[SegmentedViewport],
    *,
    viewport_id: str,
    context: ProviderContext,
    page_no: int,
) -> F07ViewportMigrationResult:
    """Preserve authentic F.07 ownership at the migration ViewportEvidence boundary."""
    if not isinstance(context, ProviderContext):
        raise TypeError("context must be ProviderContext")
    rows = tuple(viewports)
    reasons = _context_reasons(
        context=context,
        page_no=page_no,
        viewport_id=viewport_id,
    )

    matches = [viewport for viewport in rows if viewport.view_id == viewport_id]
    if len(matches) != 1:
        reasons.append("viewport_identity_not_unique")
        return F07ViewportMigrationResult(
            viewport=None,
            ownership_proof=None,
            blocking_reasons=tuple(dict.fromkeys((F07_VIEWPORT_ADAPTER_UNAVAILABLE, *reasons))),
        )
    target = matches[0]

    for viewport in rows:
        if int(viewport.page_number) != int(page_no):
            reasons.append(f"sibling_page_mismatch:{viewport.view_id}")
        if not is_segment_page_viewports_product(viewport):
            reasons.append(f"{F07_VIEWPORT_PRODUCER_LINEAGE_INVALID}:{viewport.view_id}")

    if not validate_non_overlapping_viewports(rows):
        reasons.append(F07_VIEWPORT_SIBLING_OVERLAP)

    if target.bounding_box is None:
        reasons.append("viewport_bbox_missing")
    if target.status == ViewportSegmentationStatus.RESOLVED.value:
        pass
    elif target.status == ViewportSegmentationStatus.DERIVED.value:
        if not is_authoritative_derived_viewport(target):
            reasons.append(F07_VIEWPORT_NOT_AUTHORITATIVE)
    else:
        reasons.append(F07_VIEWPORT_NOT_AUTHORITATIVE)

    if not _title_ownership_unchanged(target):
        reasons.append(F07_VIEWPORT_TITLE_OWNERSHIP_CHANGED)

    if reasons:
        return F07ViewportMigrationResult(
            viewport=None,
            ownership_proof=None,
            blocking_reasons=tuple(dict.fromkeys((F07_VIEWPORT_ADAPTER_UNAVAILABLE, *reasons))),
        )

    assert target.bounding_box is not None
    status = (
        ViewportResolutionStatus.RESOLVED
        if target.status == ViewportSegmentationStatus.RESOLVED.value
        else ViewportResolutionStatus.DERIVED
    )
    metadata = _visible_provenance(target)
    evidence = ViewportEvidence(
        viewport_id=target.view_id,
        document_id=context.document_id,
        page_id=str(int(page_no)),
        bbox=_bbox_tuple(target.bounding_box),
        view_type=target.view_type,
        status=status,
        confidence=float(target.confidence),
        reason_codes=(F07_VIEWPORT_ADAPTER_OK,),
        metadata=metadata,
    )
    producer_fingerprint = segmented_viewport_producer_fingerprint(target)
    sibling_fingerprint = _sibling_set_fingerprint(rows)
    proof_payload = {
        "document_id": context.document_id,
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "page_no": int(page_no),
        "viewport_id": target.view_id,
        "view_type": target.view_type,
        "status": target.status,
        "bbox": evidence.bbox,
        "title_bbox": _bbox_tuple(target.title_bbox),
        "boundary_source": target.boundary_source,
        "producer_fingerprint": producer_fingerprint,
        "sibling_set_fingerprint": sibling_fingerprint,
        "authoritative_derived": is_authoritative_derived_viewport(target),
    }
    proof = F07ViewportOwnershipProof(
        ownership_id=stable_contract_id(
            "f07_viewport_ownership",
            proof_payload,
            digest_chars=32,
        ),
        document_id=context.document_id,
        source_sha256=context.source_sha256,
        revision_id=str(context.current_revision_id),
        page_no=int(page_no),
        viewport_id=target.view_id,
        view_type=target.view_type,
        status=target.status,
        bbox=evidence.bbox,
        title_bbox=_bbox_tuple(target.title_bbox),
        boundary_source=target.boundary_source,
        producer_fingerprint=producer_fingerprint,
        sibling_set_fingerprint=sibling_fingerprint,
        authoritative_derived=is_authoritative_derived_viewport(target),
        _seal=_PROOF_SEAL,
    )
    return F07ViewportMigrationResult(
        viewport=evidence,
        ownership_proof=proof,
        blocking_reasons=(),
    )


def verify_f07_viewport_ownership_proof(
    proof: Optional[F07ViewportOwnershipProof],
    *,
    viewport: ViewportEvidence,
    context: ProviderContext,
    page_no: int,
) -> tuple[str, ...]:
    """Verify a sealed F.07 proof without trusting ViewportEvidence.metadata."""
    if proof is None or not isinstance(proof, F07ViewportOwnershipProof):
        return ("authoritative_derived_ownership_missing",)
    if proof._seal is not _PROOF_SEAL:
        return ("authoritative_derived_ownership_unsealed",)

    reasons: list[str] = []
    if proof.document_id != context.document_id or viewport.document_id != proof.document_id:
        reasons.append("authoritative_derived_document_mismatch")
    if proof.source_sha256 != context.source_sha256:
        reasons.append("authoritative_derived_source_sha_mismatch")
    if not context.current_revision_id or proof.revision_id != context.current_revision_id:
        reasons.append("authoritative_derived_revision_mismatch")
    if int(proof.page_no) != int(page_no):
        reasons.append("authoritative_derived_page_mismatch")
    try:
        viewport_page = int(viewport.page_id)
    except (TypeError, ValueError):
        viewport_page = -1
    if viewport_page != int(proof.page_no):
        reasons.append("authoritative_derived_viewport_page_mismatch")
    if viewport.viewport_id != proof.viewport_id:
        reasons.append("authoritative_derived_viewport_id_mismatch")
    if viewport.view_type != proof.view_type:
        reasons.append("authoritative_derived_view_type_mismatch")
    if viewport.status is not ViewportResolutionStatus.DERIVED:
        reasons.append("authoritative_derived_status_mismatch")
    if tuple(float(v) for v in viewport.bbox) != proof.bbox:
        reasons.append("authoritative_derived_bbox_mismatch")
    if not proof.authoritative_derived:
        reasons.append("authoritative_derived_predicate_failed")
    if proof.status != ViewportSegmentationStatus.DERIVED.value:
        reasons.append("authoritative_derived_proof_status_invalid")
    if proof.boundary_source != "title_partition":
        reasons.append("authoritative_derived_boundary_source_invalid")
    return tuple(dict.fromkeys(reasons))


__all__ = [
    "F07_VIEWPORT_ADAPTER_OK",
    "F07_VIEWPORT_ADAPTER_UNAVAILABLE",
    "F07_VIEWPORT_MIGRATION_SCHEMA_VERSION",
    "F07_VIEWPORT_NOT_AUTHORITATIVE",
    "F07_VIEWPORT_PRODUCER",
    "F07_VIEWPORT_PRODUCER_LINEAGE_INVALID",
    "F07_VIEWPORT_SCOPE_MISMATCH",
    "F07_VIEWPORT_SIBLING_OVERLAP",
    "F07_VIEWPORT_TITLE_OWNERSHIP_CHANGED",
    "F07ViewportMigrationResult",
    "F07ViewportOwnershipProof",
    "adapt_f07_viewport_to_migration",
    "verify_f07_viewport_ownership_proof",
]
