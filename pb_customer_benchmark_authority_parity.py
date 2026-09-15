"""Shared SHADOW parity seam between benchmark extractor and customer projection.

Delegates publication gates to ``extracted_prediction_publication_blocked`` /
``publishable_prediction_quantity``. Never invents a numeric quantity to
satisfy ``TakeoffOutputRow.value``. Never promotes extractor confidence to FIRM.
Does not rewrite Streamlit or JobHub production publication.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

from pb_geometry_takeoff_model import AuthorityStatus
from pb_legacy_extractor_adapter import LegacyExtractorAdapter, LegacyPredictionSnapshot
from pb_migration_contracts import stable_contract_id
from pb_planreader_pdf_extractor import (
    ExtractedPrediction,
    extracted_prediction_publication_blocked,
    publishable_prediction_quantity,
)
from pb_takeoff_output_authority import (
    TakeoffOutputRow,
    TakeoffSourceType,
    create_takeoff_output_row,
)

SHADOW_AUTHORITY_BLOCKED = "BLOCKED"
SHADOW_AUTHORITY_PROVISIONAL_LIVE_ONLY = "PROVISIONAL_LIVE_ONLY"

_BLOCKING_RECONCILIATION = frozenset(
    {"conflict_manual_review", "ambiguous_unresolved", "extraction_failed"}
)


@dataclass(frozen=True)
class ParityClaim:
    """Diagnostic claim carrying optional quantity — never invents a numeric."""

    tag: str
    trade: str
    unit: str
    quantity: Optional[float]
    source_page: int
    sheet_number: Optional[str]
    description: str
    confidence: float
    dimensions: Optional[tuple[float, ...]]
    metadata: Mapping[str, Any]
    publication_blocked: bool
    publishable_quantity: Optional[float]
    reconciliation_status: Optional[str]
    extraction_status: Optional[str]
    blocking_reasons: tuple[str, ...]


@dataclass(frozen=True)
class ParityDecision:
    """Shared authority decision plus optional non-commercial takeoff projection."""

    claim: ParityClaim
    shadow_authority: str
    takeoff_row: Optional[TakeoffOutputRow]


def publication_decision_for_prediction(
    prediction: ExtractedPrediction,
) -> tuple[bool, Optional[float]]:
    """Delegate to extractor publication gates — do not reimplement them."""
    return (
        extracted_prediction_publication_blocked(prediction),
        publishable_prediction_quantity(prediction),
    )


def blocking_reasons_for_prediction(prediction: ExtractedPrediction) -> tuple[str, ...]:
    """Collect diagnostic blocking reasons without inventing quantities."""
    metadata = prediction.metadata or {}
    reasons: list[str] = []
    if metadata.get("publication_blocked"):
        reasons.append("publication_blocked")
    reconciliation = metadata.get("reconciliation_status")
    if reconciliation in _BLOCKING_RECONCILIATION:
        reasons.append(f"reconciliation_status:{reconciliation}")
    extraction_status = metadata.get("extraction_status")
    if extraction_status == "extraction_failed":
        reasons.append("extraction_status:extraction_failed")
    explicit = metadata.get("blocking_reason")
    if explicit:
        reasons.append(str(explicit))
    blocked, publishable = publication_decision_for_prediction(prediction)
    if blocked and prediction.quantity is None:
        reasons.append("quantity_unavailable")
    if blocked and publishable is None and "quantity_unavailable" not in reasons:
        if prediction.quantity is not None:
            reasons.append("publication_gate_blocked")
    # Deduplicate, preserve order
    seen: set[str] = set()
    out: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            out.append(reason)
    return tuple(out)


def parity_claim_from_prediction(prediction: ExtractedPrediction) -> ParityClaim:
    blocked, publishable = publication_decision_for_prediction(prediction)
    metadata = dict(prediction.metadata or {})
    dims = (
        tuple(float(v) for v in prediction.dimensions)
        if prediction.dimensions is not None
        else None
    )
    return ParityClaim(
        tag=prediction.tag,
        trade=prediction.trade_type,
        unit=prediction.unit,
        quantity=prediction.quantity,
        source_page=int(prediction.source_page),
        sheet_number=prediction.sheet_number,
        description=prediction.description,
        confidence=float(prediction.confidence),
        dimensions=dims,
        metadata=metadata,
        publication_blocked=blocked,
        publishable_quantity=publishable,
        reconciliation_status=metadata.get("reconciliation_status"),
        extraction_status=metadata.get("extraction_status"),
        blocking_reasons=blocking_reasons_for_prediction(prediction),
    )


def diagnostic_claim_quantity_id(prediction: ExtractedPrediction) -> str:
    """Deterministic diagnostic identity for a shadow takeoff projection.

    Same tag + page alone never collapses distinct claims. The payload mirrors
    extractor claim/evidence discriminators (quantity, dimensions, bbox,
    ``raw_evidence_ref``, scoped claims / provenance) and is hashed with
    ``stable_contract_id``. This is diagnostic shadow identity only — not
    physical-instance authority, commercial quantity authority, or PROVEN_SAME.
    Confidence is intentionally excluded (detection is not identity).
    """
    metadata = prediction.metadata or {}
    dimensions = (
        [float(v) for v in prediction.dimensions]
        if prediction.dimensions is not None
        else None
    )
    bounding_box = None
    if prediction.bounding_box is not None:
        bounding_box = [float(v) for v in prediction.bounding_box]
    payload = {
        "kind": "parity_shadow_claim",
        "tag": prediction.tag,
        "trade_type": prediction.trade_type,
        "unit": prediction.unit,
        "description": prediction.description,
        "source_page": int(prediction.source_page),
        "sheet_number": prediction.sheet_number,
        "quantity": prediction.quantity,
        "dimensions": dimensions,
        "bounding_box": bounding_box,
        "raw_evidence_ref": metadata.get("raw_evidence_ref") or "",
        "scoped_claims": metadata.get("scoped_claims"),
        "merge_source": metadata.get("merge_source") or "",
        "reconciliation_status": metadata.get("reconciliation_status") or "",
        "extraction_status": metadata.get("extraction_status") or "",
        "blocking_reason": metadata.get("blocking_reason") or "",
        "opening_instance_id": (
            metadata.get("opening_instance_id")
            or metadata.get("instance_id")
            or ""
        ),
    }
    return stable_contract_id("parity_shadow", payload)


def takeoff_row_candidate_from_prediction(
    prediction: ExtractedPrediction,
) -> Optional[TakeoffOutputRow]:
    """Optional customer-side projection. Never fabricates a numeric value.

    1. Blocked + quantity=None → no TakeoffOutputRow.
    2. Blocked + evidenced numeric → BLOCKED non-publishable shadow row.
    3. Publication gate allows quantity → still SHADOW / non-FIRM / non-publishable.
    """
    blocked, publishable = publication_decision_for_prediction(prediction)
    quantity_id = diagnostic_claim_quantity_id(prediction)
    reasons = list(blocking_reasons_for_prediction(prediction))

    if blocked:
        if prediction.quantity is None:
            return None
        return create_takeoff_output_row(
            quantity_id=quantity_id,
            description=prediction.description,
            value=float(prediction.quantity),
            unit=prediction.unit,
            trade=prediction.trade_type,
            source_type=TakeoffSourceType.BLOCKED,
            authority_status=AuthorityStatus.BLOCKED,
            confidence=float(prediction.confidence),
            source_page=int(prediction.source_page),
            source_sheet=prediction.sheet_number,
            warnings=["shadow parity projection; not a commercial authority route"],
            blocking_reasons=reasons
            or ["extractor publication gate blocked this prediction"],
        )

    if publishable is None:
        return None

    return create_takeoff_output_row(
        quantity_id=quantity_id,
        description=prediction.description,
        value=float(publishable),
        unit=prediction.unit,
        trade=prediction.trade_type,
        source_type=TakeoffSourceType.AI_DETECTED,
        authority_status=AuthorityStatus.PROVISIONAL,
        confidence=float(prediction.confidence),
        source_page=int(prediction.source_page),
        source_sheet=prediction.sheet_number,
        warnings=[
            "shadow parity projection; extractor publication gate is not FIRM authority",
            "extractor confidence is never measurement authority",
        ],
        blocking_reasons=[
            "C14 shadow seam does not promote live extractor quantities to commercial FIRM",
        ],
    )


def decide_parity(prediction: ExtractedPrediction) -> ParityDecision:
    """Build claim + optional projection for one ExtractedPrediction."""
    claim = parity_claim_from_prediction(prediction)
    row = takeoff_row_candidate_from_prediction(prediction)
    shadow = (
        SHADOW_AUTHORITY_BLOCKED
        if claim.publication_blocked
        else SHADOW_AUTHORITY_PROVISIONAL_LIVE_ONLY
    )
    if row is not None and row.authority_status == AuthorityStatus.FIRM.value:
        raise RuntimeError("parity seam must never emit FIRM takeoff authority")
    if row is not None and row.is_publishable:
        raise RuntimeError("parity seam must never emit publishable takeoff rows")
    return ParityDecision(claim=claim, shadow_authority=shadow, takeoff_row=row)


def _prediction_from_legacy_snapshot(snapshot: LegacyPredictionSnapshot) -> ExtractedPrediction:
    return ExtractedPrediction(
        tag=snapshot.tag,
        trade_type=snapshot.trade_type,
        description=snapshot.description,
        quantity=snapshot.quantity,
        unit=snapshot.unit,
        confidence=snapshot.confidence,
        source_page=snapshot.source_page,
        sheet_number=snapshot.sheet_number,
        dimensions=list(snapshot.dimensions) if snapshot.dimensions is not None else None,
        bounding_box=list(snapshot.bounding_box) if snapshot.bounding_box is not None else None,
        metadata=dict(snapshot.metadata),
    )


def collect_parity_shadow_for_pdf(
    pdf_path: Path | str,
    pages: Optional[Sequence[int]] = None,
    *,
    adapter: Optional[LegacyExtractorAdapter] = None,
) -> dict[str, Any]:
    """Run legacy extractor adapter and record shared parity decisions (shadow only)."""
    runner = adapter or LegacyExtractorAdapter()
    result = runner.extract(pdf_path, pages=pages)
    decisions = [
        decide_parity(_prediction_from_legacy_snapshot(snapshot))
        for snapshot in result.predictions
    ]
    blocked_count = sum(1 for d in decisions if d.claim.publication_blocked)
    row_count = sum(1 for d in decisions if d.takeoff_row is not None)
    return {
        "status": "collected",
        "result_id": result.result_id,
        "engine_id": result.engine_id,
        "adapter_version": result.adapter_version,
        "source_sha256": result.source_sha256,
        "prediction_count": len(decisions),
        "blocked_count": blocked_count,
        "provisional_live_count": len(decisions) - blocked_count,
        "takeoff_projection_count": row_count,
        "decisions": [
            {
                "tag": d.claim.tag,
                "trade": d.claim.trade,
                "quantity": d.claim.quantity,
                "publishable_quantity": d.claim.publishable_quantity,
                "publication_blocked": d.claim.publication_blocked,
                "shadow_authority": d.shadow_authority,
                "blocking_reasons": list(d.claim.blocking_reasons),
                "reconciliation_status": d.claim.reconciliation_status,
                "extraction_status": d.claim.extraction_status,
                "has_takeoff_row": d.takeoff_row is not None,
                "takeoff_authority_status": (
                    d.takeoff_row.authority_status if d.takeoff_row is not None else None
                ),
                "takeoff_is_publishable": (
                    d.takeoff_row.is_publishable if d.takeoff_row is not None else False
                ),
            }
            for d in decisions
        ],
        "note": (
            "Shadow-only customer/benchmark parity seam. "
            "Does not rewrite Streamlit or JobHub publication. "
            "Never promotes extractor confidence to FIRM."
        ),
    }
