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


def apply_finish_callout_bindings_to_walls(
    walls: Sequence[Dict[str, Any]],
    callout_bindings: Sequence[Any],
) -> List[Dict[str, Any]]:
    """Bind authenticated finish callouts to candidate walls deterministically (AG-05).

    Invariants:
    1. Deterministic wall binding: matches host wall ID or equivalence group.
    2. Local scope: does not apply a local callout note globally to other walls.
    3. Provenance preservation: records callout_binding_id, finish_material,
       trade_scope_id, and source_evidence_ids on the matched wall object.
    4. Ambiguity abstention: if a callout was ambiguous across multiple distinct
       walls, the upstream authority abstained and produced no binding; this function
       never guesses or proximity-assigns.
    5. Walls with no callout maintain their unconfirmed/gross status.
    """
    from pb_wall_finish_callout_wall_authority import WallFinishCalloutWallBindingRecord

    updated_walls: List[Dict[str, Any]] = [dict(w) for w in walls]

    for binding in callout_bindings:
        if not isinstance(binding, WallFinishCalloutWallBindingRecord):
            continue
        if binding.status is not EvidenceResolutionStatus.CORROBORATED:
            continue

        target_ids = set(binding.equivalence_group_wall_ids) if binding.equivalence_group_wall_ids else {binding.physical_wall_id}
        target_ids.add(binding.physical_wall_id)

        for wall in updated_walls:
            wid = str(wall.get("id") or wall.get("wall_id") or wall.get("wall_ref") or "")
            if wid in target_ids:
                wall["finish_material"] = binding.finish_material
                wall["trade_scope_id"] = binding.trade_scope_id
                wall["finish_callout_binding_id"] = binding.binding_id
                wall["finish_source_evidence_ids"] = list(binding.source_evidence_ids)
                wall["finish_semantic_direction"] = binding.semantic_direction
                # Update substrate if default
                current_sub = str(wall.get("substrate") or "")
                if not current_sub or current_sub in {"Other", "External walling", "Internal walling"}:
                    wall["substrate"] = binding.finish_material
                wall["callout_bound"] = True

    return updated_walls


def resolve_pdf_finish_callouts(
    pdf_path: Any,
    page_ids: Optional[Sequence[str]] = None,
) -> List[Any]:
    """Extract authenticated finish callouts from a PDF using WallFinishCalloutWallProducer."""
    try:
        from pathlib import Path
        from pb_source_visibility_authority import SourceVisibilityProducer
        from pb_wall_finish_callout_wall_authority import WallFinishCalloutWallProducer

        p = Path(pdf_path)
        if not p.is_file():
            return []

        source = SourceVisibilityProducer(
            producer_method="customer-runtime-callout-wall",
            producer_version="1.0",
        )
        source.ingest_native_pdf_bytes(
            document_id=f"doc:{p.name}",
            source_bytes=p.read_bytes(),
            source_locator=str(p),
        )
        producer = WallFinishCalloutWallProducer.from_source_visibility_producer(
            source,
            page_ids=page_ids,
        )
        bindings: List[Any] = []
        for result in producer.published_results():
            if result.status is EvidenceResolutionStatus.CORROBORATED:
                for b in result.bindings:
                    if b.status is EvidenceResolutionStatus.CORROBORATED:
                        bindings.append(b)
        return bindings
    except Exception:
        return []


__all__ = [
    "SOURCE_PREFIX",
    "apply_finish_callout_bindings_to_walls",
    "bound_wall_finish_record_to_takeoff_row",
    "build_bound_wall_finish_rows",
    "resolve_pdf_finish_callouts",
]
