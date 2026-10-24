"""Shadow: commercial/JobHub paths may only see authorised publishable quantities.

Mission item 26. Reuses ``quantity_status_not_publishable`` — does not create a
second quantity vocabulary or bypass GPT3 sealing.
"""
from __future__ import annotations

from typing import Any, Mapping, Sequence

from pb_quantity_takeoff_adapter import quantity_status_not_publishable


def filter_authorised_quantity_rows_for_export(
    rows: Sequence[Mapping[str, Any]],
    *,
    status_field: str = "authority_status",
) -> dict[str, Any]:
    """Partition rows into exportable vs withheld without mutating inputs."""
    exportable: list[Mapping[str, Any]] = []
    withheld: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        status = row.get(status_field)
        if quantity_status_not_publishable(status):
            withheld.append({
                "index": index,
                "quantity_id": row.get("quantity_id"),
                "authority_status": status,
                "reason": "quantity_status_not_publishable",
            })
        else:
            exportable.append(row)
    return {
        "status": "UNPUBLISHED_AUTHORISED_QUANTITY_EXPORT_SHADOW",
        "exportable_count": len(exportable),
        "withheld_count": len(withheld),
        "exportable_rows": list(exportable),
        "withheld_rows": withheld,
        "jobhub_export_activated": False,
        "shadow_only": True,
    }
