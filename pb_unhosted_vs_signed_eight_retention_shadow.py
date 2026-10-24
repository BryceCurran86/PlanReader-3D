"""Prove unhosted opening retention does not drop signed-eight quantity IDs."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from pb_signed_eight_id_retention import assert_signed_quantity_ids_retained


def prove_unhosted_retention_vs_signed_eight(
    *,
    unhosted_physical_opening_ids: Sequence[str],
    all_physical_opening_ids: Sequence[str],
    required_signed_quantity_ids: Sequence[str],
    observed_signed_quantity_ids: Sequence[str],
) -> dict[str, Any]:
    unhosted = {str(x).strip() for x in unhosted_physical_opening_ids if str(x).strip()}
    all_ids = {str(x).strip() for x in all_physical_opening_ids if str(x).strip()}
    if not unhosted.issubset(all_ids):
        raise ValueError("unhosted IDs must be a subset of all opening IDs")
    retention = assert_signed_quantity_ids_retained(
        required_quantity_ids=required_signed_quantity_ids,
        observed_quantity_ids=observed_signed_quantity_ids,
    )
    return {
        "status": "UNPUBLISHED_UNHOSTED_VS_SIGNED_EIGHT_RETENTION",
        "unhosted_opening_count": len(unhosted),
        "all_opening_count": len(all_ids),
        "unhosted_subset_of_all": True,
        "signed_id_retention": retention["status"],
        "missing_quantity_ids": retention["missing_quantity_ids"],
        "host_granted_to_unhosted": False,
        "boq_values_read": False,
        "measurement_published": False,
        "benchmark_score_granted": False,
        "shadow_only": True,
    }
