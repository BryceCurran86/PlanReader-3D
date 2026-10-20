"""Assert signed-eight quantity ID retention without reading BOQ values."""
from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any


def assert_signed_quantity_ids_retained(
    *,
    required_quantity_ids: Sequence[str],
    observed_quantity_ids: Iterable[str],
) -> dict[str, Any]:
    required = tuple(sorted({str(x).strip() for x in required_quantity_ids if str(x).strip()}))
    observed = {str(x).strip() for x in observed_quantity_ids if str(x).strip()}
    if not required:
        raise ValueError("required signed quantity ids needed")
    missing = [qid for qid in required if qid not in observed]
    return {
        "status": (
            "SIGNED_QUANTITY_IDS_RETAINED"
            if not missing
            else "SIGNED_QUANTITY_IDS_MISSING"
        ),
        "required_count": len(required),
        "observed_count": len(observed),
        "missing_quantity_ids": missing,
        "boq_values_read": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }


def signed_ids_from_customer_rows(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    return [str(r["quantity_id"]) for r in rows if str(r.get("quantity_id") or "").strip()]
