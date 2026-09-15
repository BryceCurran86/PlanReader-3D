"""Shadow-only authority parity for live extractor opening predictions.

Compares live ``ExtractedPrediction`` rows against publication gates without
mutating ``pred_dict`` or introducing new FIRM routes.
"""
from __future__ import annotations

from typing import Any, Dict, List, Sequence

from pb_planreader_pdf_extractor import (
    ExtractedPrediction,
    extracted_prediction_publication_blocked,
    publishable_prediction_quantity,
)


def collect_opening_authority_shadow(
    predictions: Sequence[ExtractedPrediction],
) -> Dict[str, Any]:
    """Record publishability vs blocked opening predictions for shadow review."""
    opening_rows: List[Dict[str, Any]] = []
    for pred in predictions:
        if pred.trade_type not in ("windows", "doors"):
            continue
        blocked = extracted_prediction_publication_blocked(pred)
        publishable_qty = publishable_prediction_quantity(pred)
        opening_rows.append(
            {
                "tag": pred.tag,
                "source_page": pred.source_page,
                "live_quantity": pred.quantity,
                "publishable_quantity": publishable_qty,
                "dimensions": pred.dimensions,
                "publication_blocked": blocked,
                "reconciliation_status": (pred.metadata or {}).get("reconciliation_status"),
                "extraction_status": (pred.metadata or {}).get("extraction_status"),
                "scoped_claim_count": len((pred.metadata or {}).get("scoped_claims") or []),
                "shadow_authority": "BLOCKED" if blocked else "PROVISIONAL_LIVE_ONLY",
            }
        )

    blocked_count = sum(1 for row in opening_rows if row["publication_blocked"])
    return {
        "status": "collected",
        "opening_count": len(opening_rows),
        "blocked_count": blocked_count,
        "publishable_count": len(opening_rows) - blocked_count,
        "openings": opening_rows,
        "note": (
            "Shadow-only: canonical firm authority is not wired to live pred_dict; "
            "BLOCKED rows must not feed deductions or commercial publish."
        ),
    }
