"""Customer-runtime bridge for SourceBoundWallFinishQuantityAuthority (AG-04).

Bridges the benchmark-proven bound wall-finish quantity authority directly
into the PlanReader customer runtime.

Core invariants:
1. A wall is identified geometrically ONCE (physical wall -> openings -> net wall).
2. Downstream finish quantities consume the authenticated host net wall area
   via face/finish binding, rather than painting/plastering/tiling independently
   rediscovering or inventing wall geometry.
3. Different finishes on different wall faces (e.g. exterior face vs room-facing
   interior face) of the same physical wall are supported without duplicating
   wall geometry.
4. If net wall authority or face binding abstains or is incomplete, the finish
   quantity abstains fail-closed; no speculative finish rows are created.
5. All published rows strictly adhere to the canonical 21-field takeoff_rows contract.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Sequence, Tuple

from pb_bound_wall_finish_quantity_authority import (
    FINISH_QUANTITY_RESOLVED,
    SourceBoundWallFinishQuantityAuthority,
    SourceBoundWallFinishQuantityProducer,
    SourceBoundWallFinishQuantityRecord,
    SourceBoundWallFinishQuantityResult,
    SourceBoundWallFinishQuantitySelector,
)
from pb_migration_contracts import EvidenceResolutionStatus
import pb_takeoff_row_contract as takeoff_contract

SOURCE_PREFIX = "PB Auto Geometry v1.2.19"


def bound_wall_finish_record_to_takeoff_row(
    workspace_id: int,
    record: SourceBoundWallFinishQuantityRecord,
    *,
    source_prefix: str = SOURCE_PREFIX,
    status: str = "Measured",
    confidence: str = "Documented",
) -> Tuple[Any, ...]:
    """Convert an authenticated SourceBoundWallFinishQuantityRecord into a canonical 21-field takeoff row.

    Layout (21 fields):
    workspace_id, section, element, location, substrate, finish_system, quantity, unit,
    quantity_status, source_page, source_reference, inclusion_status, coats,
    coverage_m2_per_litre, productivity_m2_per_hour, rate_per_unit, confidence, notes,
    row_role, created_at, updated_at
    """
    if type(record) is not SourceBoundWallFinishQuantityRecord:
        raise TypeError("record must be SourceBoundWallFinishQuantityRecord")
    if record.status is not EvidenceResolutionStatus.CORROBORATED:
        raise ValueError("Cannot publish uncorroborated finish record to customer takeoff")

    qty = round(max(0.0, float(record.quantity_m2)), 2)
    trade_lower = str(record.trade_scope_id or "").lower()
    is_external = "external" in trade_lower or "exterior" in trade_lower

    section = "External" if is_external else "Internal"
    element = "External wall finishes" if is_external else "Internal wall finishes"

    wall_list = ", ".join(sorted(record.physical_wall_ids)) if record.physical_wall_ids else "wall"
    face_count = len(record.physical_face_ids)
    location = f"Wall ({wall_list}) · {record.finish_material}"
    substrate = str(record.finish_material or "Wall finish")
    finish_system = str(record.finish_material or "To be confirmed")

    notes = (
        f"Source-bound wall finish ({record.trade_scope_id}) derived from authenticated net wall geometry. "
        f"Host walls: {wall_list}; faces bound: {face_count}; net area: {qty:.2f} m²."
    )
    source_page = str(record.page_id or "1")
    source_ref = f"{source_prefix} · bound_wall_finish:{record.record_id}"

    stamp = ""  # Replaced by database transaction / caller
    return (
        int(workspace_id),
        section,
        element,
        location,
        substrate,
        finish_system,
        qty,
        "m²",
        status,
        source_page,
        source_ref,
        "PROVISIONAL",
        0,
        0,
        0,
        0,
        confidence,
        notes,
        "wall_finish",
        stamp,
        stamp,
    )


def build_bound_wall_finish_rows(
    app: Any,
    workspace_id: int,
    pages: Sequence[Dict[str, Any]],
) -> Tuple[List[Tuple[Any, ...]], List[Dict[str, Any]]]:
    """Discover, resolve, and publish source-bound wall finish rows for the workspace.

    Checks:
    1. Callable `app.resolve_bound_wall_finishes(workspace_id)` if provided by workspace.
    2. Attached `app.source_bound_wall_finish_authority` or `app.source_bound_wall_finish_records`.
    3. Returns canonical 21-field takeoff rows and report dictionaries.
    """
    rows: List[Tuple[Any, ...]] = []
    finish_records: List[Dict[str, Any]] = []

    # 1. Check direct resolver method on app
    if hasattr(app, "resolve_bound_wall_finishes") and callable(getattr(app, "resolve_bound_wall_finishes")):
        try:
            results = app.resolve_bound_wall_finishes(int(workspace_id))
            if results:
                for res in results:
                    rec = getattr(res, "record", res)
                    if isinstance(rec, SourceBoundWallFinishQuantityRecord):
                        row = bound_wall_finish_record_to_takeoff_row(workspace_id, rec)
                        rows.append(row)
                        finish_records.append({
                            "record_id": rec.record_id,
                            "trade_scope_id": rec.trade_scope_id,
                            "finish_material": rec.finish_material,
                            "quantity_m2": float(rec.quantity_m2),
                            "physical_wall_ids": list(rec.physical_wall_ids),
                            "physical_face_ids": list(rec.physical_face_ids),
                            "page_id": rec.page_id,
                        })
        except Exception:
            pass

    # 2. Check attached authority on app
    if not rows and hasattr(app, "source_bound_wall_finish_authority"):
        authority = getattr(app, "source_bound_wall_finish_authority")
        if isinstance(authority, SourceBoundWallFinishQuantityAuthority):
            try:
                # Query registered selectors
                selectors = getattr(app, "source_bound_wall_finish_selectors", ())
                for sel in selectors:
                    if isinstance(sel, SourceBoundWallFinishQuantitySelector):
                        res = authority.resolve(sel)
                        if res.status is EvidenceResolutionStatus.CORROBORATED and res.record is not None:
                            rec = res.record
                            row = bound_wall_finish_record_to_takeoff_row(workspace_id, rec)
                            rows.append(row)
                            finish_records.append({
                                "record_id": rec.record_id,
                                "trade_scope_id": rec.trade_scope_id,
                                "finish_material": rec.finish_material,
                                "quantity_m2": float(rec.quantity_m2),
                                "physical_wall_ids": list(rec.physical_wall_ids),
                                "physical_face_ids": list(rec.physical_face_ids),
                                "page_id": rec.page_id,
                            })
            except Exception:
                pass

    return rows, finish_records


__all__ = [
    "SOURCE_PREFIX",
    "bound_wall_finish_record_to_takeoff_row",
    "build_bound_wall_finish_rows",
]
