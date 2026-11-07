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
from pb_live_wall_finish_quantity_publication import publish_bound_wall_finish_quantity
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

    # Reprove the exact source record before customer rounding. A positive
    # original area smaller than the two-decimal display quantum must never
    # silently become a measured 0.00 m² row, nor be rounded UP to a
    # fabricated minimum. The batch caller fails closed on this error.
    quantity = publish_bound_wall_finish_quantity(record)
    qty = round(float(quantity.value), 2)
    if not math.isfinite(qty) or qty <= 0.0:
        raise ValueError(
            "positive source wall-finish area is unrepresentable in customer m²"
        )
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
    source_ref = (
        f"{source_prefix} · bound_wall_finish:{record.record_id}"
        f" · finish_quantity:{quantity.quantity_id}"
    )

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
    """Project a COMPLETE validated source-bound finish batch or none.

    Source producer records are individually authenticated, but a commercial
    batch must also reject a later invalid member, a replayed record, or the
    same original physical finish surface published twice. Do not expose rows
    accumulated before a failure; the auto-geometry caller treats an empty
    result as an explicit nonpublication.
    """
    rows: List[Tuple[Any, ...]] = []
    finish_records: List[Dict[str, Any]] = []
    seen_record_ids: set[tuple[str, str, str, str]] = set()
    seen_surfaces: set[tuple[str, str, str, str]] = set()
    seen_scopes: set[tuple[str, ...]] = set()

    def add_record(rec: SourceBoundWallFinishQuantityRecord) -> None:
        if type(rec) is not SourceBoundWallFinishQuantityRecord:
            raise ValueError("source-bound wall finish record required")
        # This real issuer re-proves the producer seal, source roots, physical
        # face identities, and positive metric quantity. No caller row can
        # supply or bypass the authority.
        quantity = publish_bound_wall_finish_quantity(rec)
        root = (rec.document_id, rec.revision_id, rec.source_sha256)
        record_key = (*root, rec.record_id)
        scope_key = (
            *root, rec.snapshot_id, rec.page_id, rec.viewport_id,
            rec.decision_scope_id, rec.trade_scope_id, rec.finish_material,
        )
        surfaces = {(*root, surface) for surface in rec.physical_surface_ids}
        if (
            record_key in seen_record_ids
            or scope_key in seen_scopes
            or not surfaces.isdisjoint(seen_surfaces)
        ):
            raise ValueError("duplicate original wall finish quantity or physical surface")
        row = bound_wall_finish_record_to_takeoff_row(workspace_id, rec)
        # Commit to local staging only after all source and customer checks.
        seen_record_ids.add(record_key)
        seen_scopes.add(scope_key)
        seen_surfaces.update(surfaces)
        rows.append(row)
        finish_records.append({
            "record_id": rec.record_id,
            "trade_scope_id": rec.trade_scope_id,
            "finish_material": rec.finish_material,
            "quantity_m2": float(rec.quantity_m2),
            "physical_wall_ids": list(rec.physical_wall_ids),
            "physical_face_ids": list(rec.physical_face_ids),
            "physical_surface_ids": list(rec.physical_surface_ids),
            "quantity_id": quantity.quantity_id,
            "page_id": rec.page_id,
        })

    def add_result(result: Any) -> None:
        rec = getattr(result, "record", result)
        if rec is None and getattr(result, "status", None) in (
            EvidenceResolutionStatus.ABSTAINED,
            EvidenceResolutionStatus.CONFLICT,
            EvidenceResolutionStatus.CANDIDATE,
        ):
            return
        if rec is None or (
            getattr(result, "record", result) is not result
            and getattr(result, "status", None) is not EvidenceResolutionStatus.CORROBORATED
        ):
            raise ValueError("contradictory original wall finish result")
        add_record(rec)

    try:
        resolver = getattr(app, "resolve_bound_wall_finishes", None)
        if callable(resolver):
            results = resolver(int(workspace_id))
            if results:
                saw_original_result = False
                for result in results:
                    saw_original_result = True
                    add_result(result)
                # A producer-owned ABSTAIN/CONFLICT is evidence against
                # publication, not permission to borrow a different source
                # authority. Only a genuinely empty resolver may fall back.
                if saw_original_result:
                    return rows, finish_records

        authority = getattr(app, "source_bound_wall_finish_authority", None)
        if type(authority) is SourceBoundWallFinishQuantityAuthority:
            for selector in getattr(app, "source_bound_wall_finish_selectors", ()):
                if type(selector) is not SourceBoundWallFinishQuantitySelector:
                    raise ValueError("original wall finish selector required")
                add_result(authority.resolve(selector))
    except Exception:
        # Deliberately discard ALL staged positive rows, not just the invalid
        # member. The upstream auto-geometry wrapper is likewise fail-closed.
        return [], []

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
