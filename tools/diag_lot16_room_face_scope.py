"""Diagnostic-only Lot16 room-face source geometry trace (no authority changes).

Run: PYTHONPATH=. python tools/diag_lot16_room_face_scope.py --pdf "documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf" --page-index 2 --diagnostic-label WC --diagnostic-label LINEN --diagnostic-label BROOM --output lot16-room-face-scope.json
The PDF path must be an actual source file; no benchmark gold is loaded.
Exact native word occurrence coordinates are diagnostic candidates only; they
must not be counted as source-authenticated room faces or metric quantities.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

import pb_source_room_face_authority as face_authority
import pb_source_room_label_authority as label_authority
import pb_same_view_room_area_authority as same_view_authority
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_opening_area_quantity_publication import _opening_quantity
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim



def _has_firm_metric_floor_receipt(floor) -> bool:
    """Count only unchanged typed source area receipts; never infer m².

    This is a diagnostic eligibility counter, not an independent metric
    measuring authority. The source quantity producer still governs FIRM.
    """
    area_value = getattr(floor, "metric_area_m2", None)
    if type(area_value) not in (int, float):
        return False
    try:
        area = float(area_value)
    except (TypeError, ValueError, OverflowError):
        return False
    source_id = getattr(floor, "metric_area_quantity_id", None)
    face_id = getattr(floor, "source_room_face_record_id", None)
    authority = getattr(floor, "metric_area_authority", None)
    receipts = getattr(floor, "evidence_ids", None)
    return (
        math.isfinite(area) and area > 0.0
        and type(source_id) is str and bool(source_id)
        and source_id == source_id.strip()
        and type(face_id) is str and bool(face_id)
        and face_id == face_id.strip()
        and type(authority) is str and authority in {
            MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
            MeasurementAuthorityType.PDF_SCALED.value,
        }
        and type(receipts) in (tuple, list) and bool(receipts)
        and all(type(r) is str and r and r == r.strip() for r in receipts)
        and len(set(receipts)) == len(receipts)
    )


def _floor_quantity_first_failure(
    floor, room, area_quantity_ids: set[str], *, duplicate_room_owner: bool = False
) -> str:
    """Identify the earliest unresolved floor-to-measurement stage.

    A PDF polygon area is never a physical m² measurement. A correctly
    corroborated source room label does not by itself authenticate scale.
    """
    if not floor.physical_floor_surface_identity_resolved or not floor.physical_floor_surface_id:
        return "physical_floor_identity_unresolved"
    if not floor.source_room_face_record_id or not floor.evidence_ids:
        return "source_room_face_evidence_unavailable"
    if duplicate_room_owner:
        return "duplicate_canonical_room_source_owner_conflict"
    if room is None:
        return "canonical_room_owner_unavailable"
    # A separately source-authenticated physical scale can close metric area
    # without an identifiable room-text label. Check an actual measurement
    # receipt first; the label branch diagnoses only the unmeasured path.
    if _has_firm_metric_floor_receipt(floor):
        if floor.metric_area_quantity_id not in area_quantity_ids:
            return "metric_floor_area_quantity_evidence_unavailable"
        return "floor_area_quantity_prerequisites_resolved"
    if (
        not room.room_label
        or not room.room_label_binding_record_id
        or not room.room_label_evidence_ids
    ):
        return "authenticated_room_label_ownership_unavailable"
    return "documented_dimension_or_physical_scale_measurement_unavailable"


def _floor_quantity_diagnostic(claim) -> dict:
    rooms_by_id = {
        str(room.canonical_room_id): room
        for room in claim.canonical_rooms
    }
    # Do not let a dict's last-writer-wins normalization conceal duplicate
    # authenticated canonical rooms in a diagnostic claiming a floor is ready.
    room_owner_counts = Counter(str(room.canonical_room_id) for room in claim.canonical_rooms)
    # The raw room-area source universe is NOT proof of a publishable floor
    # quantity. Reuse the exact production floor publisher, which validates
    # physical face, canonical/physical floor uniqueness, area, units, source
    # SHA/revision, room snapshot and evidence lineage. This read-only
    # diagnostic can only mark a floor as ready when that gate really passes.
    try:
        approved_floor_quantities = publish_live_floor_area_quantities(claim)
    except (TypeError, ValueError):
        approved_floor_quantities = ()
    areas = {
        str(quantity.metadata.get("upstream_room_area_quantity_id"))
        for quantity in approved_floor_quantities
        if quantity.metadata.get("upstream_room_area_quantity_id")
    }
    # Report asserted source-finish evidence separately from source-trace-
    # validated finish evidence. Raw claims are not sealed customer quantities.
    # This diagnostic executes no side-effecting export or benchmark scoring.
    from pb_live_floor_finish_area_source_closed_export import (
        build_live_floor_finish_area_source_traces,
    )
    from pb_source_closed_run_export import SourceClosedRunExportError
    try:
        finish_source_traces = build_live_floor_finish_area_source_traces(
            claim, workspace_id=1, project_id="gpt1-lot16-source-diagnostic",
        )
        finish_source_trace_failure = None
    except (TypeError, ValueError, SourceClosedRunExportError) as error:
        finish_source_traces = {}
        finish_source_trace_failure = str(error)
    finishes: dict[str, list[str]] = {}
    for quantity in claim.floor_finish_quantity_evidence:
        for entity_id in quantity.input_entity_ids:
            finishes.setdefault(str(entity_id), []).append(quantity.quantity_id)
    rows = []
    for floor in claim.canonical_floors:
        reason = _floor_quantity_first_failure(
            floor, rooms_by_id.get(str(floor.room_entity_id)), areas,
            duplicate_room_owner=room_owner_counts[str(floor.room_entity_id)] > 1,
        )
        rows.append({
            "canonical_floor_id": floor.canonical_floor_id,
            "physical_floor_surface_id": floor.physical_floor_surface_id,
            "room_entity_id": floor.room_entity_id,
            "source_room_face_record_id": floor.source_room_face_record_id,
            "source_receipt_count": len(floor.evidence_ids),
            "geometry_area_page_pts2": floor.area_page_pts2,
            "metric_area_m2": floor.metric_area_m2,
            "metric_area_authority": floor.metric_area_authority,
            "metric_area_quantity_id": floor.metric_area_quantity_id,
            "finish_descriptor": floor.finish_descriptor,
            "published_finish_quantity_ids": sorted(
                finishes.get(str(floor.canonical_floor_id), [])
            ),
            "source_trace_validated_finish_quantity_ids": sorted(
                qid for qid in finishes.get(str(floor.canonical_floor_id), [])
                if qid in finish_source_traces
            ),
            "first_missing_prerequisite": reason,
        })
    return {
        "canonical_floor_count": len(rows),
        "first_failure_frequency": dict(Counter(
            row["first_missing_prerequisite"] for row in rows
        )),
        "area_quantity_count": len(claim.room_area_quantity_evidence),
        "source_closed_floor_quantity_count": len(approved_floor_quantities),
        "finish_quantity_count": len(claim.floor_finish_quantity_evidence),
        "source_trace_validated_finish_quantity_count": len(finish_source_traces),
        "finish_source_trace_failure": finish_source_trace_failure,
        "per_floor": rows,
    }


def _wall_metric_first_failure(wall) -> str:
    """Classify the first absent producer-owned wall quantity prerequisite.

    This is a diagnostic ledger, not a new measurement or a claim that the
    source supports a physical wall, a height or a finish.
    """
    if not wall.physical_identity_resolved or not wall.physical_wall_id:
        return "physical_wall_identity_unresolved"
    if not wall.evidence_ids or not wall.plan_members:
        return "canonical_wall_source_receipts_unavailable"
    # The ledger must not call a wall metric-ready from a nonempty source
    # field when its actual value is Boolean, nonfinite or physically invalid.
    for attr, reason, strictly_positive in (
        ("length_m", "metric_wall_length_unavailable", True),
        ("height_m", "authenticated_wall_height_unavailable", True),
        ("gross_area_m2", "gross_wall_area_unavailable", True),
    ):
        measurement = getattr(wall, attr, None)
        if type(measurement) not in (int, float):
            return reason
        try:
            real_measurement = float(measurement)
        except (OverflowError, TypeError, ValueError):
            return reason
        if (not math.isfinite(real_measurement) or
                (real_measurement <= 0.0 if strictly_positive else real_measurement < 0.0)):
            return reason
    if not wall.gross_polygon_wkb_hex:
        return "gross_wall_area_unavailable"
    if not wall.role or not wall.whole_wall_role_record_id:
        return "authenticated_whole_wall_role_unavailable"
    net_value = getattr(wall, "net_area_m2", None)
    if type(net_value) not in (int, float):
        return "net_wall_area_or_deduction_unavailable"
    try:
        net_number = float(net_value)
    except (OverflowError, TypeError, ValueError):
        return "net_wall_area_or_deduction_unavailable"
    if not math.isfinite(net_number) or net_number < 0.0 or not wall.net_polygon_wkb_hex:
        return "net_wall_area_or_deduction_unavailable"
    if net_value > wall.gross_area_m2 + 1e-6:
        return "net_wall_greater_than_authenticated_gross_area"
    return "canonical_net_wall_area_available"


def _wall_metric_diagnostic(claim) -> dict:
    ledger = []
    for wall in claim.canonical_walls:
        ledger.append({
            "canonical_wall_id": wall.canonical_wall_id,
            "physical_wall_id": wall.physical_wall_id,
            "page_id": wall.page_id,
            "physical_identity_resolved": bool(wall.physical_identity_resolved),
            "identity_status": wall.identity_status,
            "plan_member_count": len(wall.plan_members),
            "evidence_receipt_count": len(wall.evidence_ids),
            "role": wall.role,
            "length_m": wall.length_m,
            "height_m": wall.height_m,
            "gross_area_m2": wall.gross_area_m2,
            "net_area_m2": wall.net_area_m2,
            "opening_void_count": len(wall.opening_voids),
            "first_missing_prerequisite": _wall_metric_first_failure(wall),
        })
    return {
        "canonical_wall_count": len(claim.canonical_walls),
        "wall_authority_status": str(getattr(claim.canonical_wall_status, "value", claim.canonical_wall_status)),
        "wall_authority_reasons": list(claim.canonical_wall_reason_codes),
        "first_failure_frequency": dict(Counter(
            entry["first_missing_prerequisite"] for entry in ledger
        )),
        "source_proven_net_wall_publication_status": str(
            getattr(claim.publication.status, "value", claim.publication.status)
        ),
        "external_wall_quantity_published": claim.publication.quantity_evidence is not None,
        "external_wall_ids_count": len(claim.external_wall_ids),
        "per_wall": ledger,
    }



def _opening_quantity_first_failure(opening) -> str:
    """Mirror the existing area publisher's ordered admissibility gates.

    This is source-diagnostic only. Unknown opening labels, counts and geometry
    remain unavailable rather than zero.
    """
    canonical_id = str(opening.canonical_opening_id or "").strip()
    physical_id = str(opening.physical_opening_id or "").strip()
    if not canonical_id or canonical_id != physical_id:
        return "canonical_physical_opening_identity_unresolved"
    if not str(opening.viewport_id or "").strip():
        return "authenticated_opening_viewport_unavailable"
    if not str(opening.host_wall_id or "").strip():
        return "opening_host_wall_unresolved"
    if not (
        str(opening.host_binding_record_id or "").strip()
        or str(opening.host_frame_record_id or "").strip()
    ):
        return "opening_host_source_receipt_unavailable"
    if str(opening.opening_kind or "").strip().lower() not in {"door", "window"}:
        return "authenticated_door_window_semantics_unavailable"
    basis = str(opening.area_basis or "").strip()
    bases = {
        "figured_opening_label": "figured_area_record_id",
        "resolved_opening_geometry": "opening_void_record_id",
        "authenticated_elevation_frame": "figured_area_record_id",
        "authenticated_frame_schedule": "schedule_binding_record_id",
    }
    if basis not in bases:
        return "authenticated_opening_area_basis_unavailable"
    if type(opening.area_m2) not in (int, float):
        return "metric_opening_area_unavailable"
    try:
        area = float(opening.area_m2)
    except (TypeError, ValueError, OverflowError):
        return "metric_opening_area_unavailable"
    if not math.isfinite(area) or area <= 0.0:
        return "metric_opening_area_unavailable"
    original_receipts = opening.evidence_ids
    if (
        not isinstance(original_receipts, (tuple, list))
        or not original_receipts
        or any(type(value) is not str or not value.strip() for value in original_receipts)
        or len(set(original_receipts)) != len(original_receipts)
    ):
        return "opening_source_evidence_unavailable"
    evidence = set(original_receipts)
    authority_record_id = str(getattr(opening, bases[basis]) or "").strip()
    if not authority_record_id or authority_record_id not in evidence:
        return "opening_area_measurement_source_receipt_unavailable"
    if (
        basis == "authenticated_frame_schedule"
        and str(opening.schedule_row_dimension_basis or "").strip().lower() != "frame"
    ):
        return "authenticated_frame_schedule_basis_unavailable"
    # A diagnostic heuristic is never authoritative over the actual
    # canonical→quantity publisher. Report the exact first failed publication
    # gate rather than falsely declaring an opening ready to improve recall.
    if _opening_quantity(opening) is None:
        return "production_opening_area_quantity_gate_unresolved"
    return "opening_area_quantity_prerequisites_resolved"


def _opening_quantity_diagnostic(claim) -> dict:
    published_by_opening = {}
    for quantity in claim.opening_quantity_evidence:
        for identity in quantity.input_entity_ids:
            published_by_opening.setdefault(str(identity), []).append(quantity)
    ledger = []
    for opening in claim.canonical_openings:
        published = published_by_opening.get(str(opening.canonical_opening_id), ())
        readiness = _opening_quantity_first_failure(opening)
        authentic = _opening_quantity(opening)
        signed_publication_matches = tuple(
            candidate for candidate in published
            if authentic is not None
            and candidate.quantity_id == authentic.quantity_id
            and type(candidate.value) in (int, float)
            and candidate.value == authentic.value
            and candidate.authority == authentic.authority
            and candidate.unit == authentic.unit
            and candidate.status == authentic.status
            and candidate.semantic_key == authentic.semantic_key
            and candidate.input_entity_ids == authentic.input_entity_ids
            and candidate.evidence_ids == authentic.evidence_ids
            and candidate.formula == authentic.formula
            and candidate.formula_version == authentic.formula_version
            and candidate.confidence == authentic.confidence
            and candidate.abstained == authentic.abstained
            and candidate.blocking_reasons == authentic.blocking_reasons
            and candidate.reason_codes == authentic.reason_codes
            and candidate.metadata == authentic.metadata
        )
        if readiness == "opening_area_quantity_prerequisites_resolved" and published and (
            len(signed_publication_matches) != 1 or len(published) != 1
        ):
            readiness = "opening_area_published_claim_drift"
        ledger.append({
            "canonical_opening_id": opening.canonical_opening_id,
            "physical_opening_id": opening.physical_opening_id,
            "page_id": opening.page_id,
            "opening_kind": opening.opening_kind,
            "semantic_class": opening.semantic_class,
            "viewport_id": opening.viewport_id,
            "host_wall_id": opening.host_wall_id,
            "host_receipt_available": bool(
                opening.host_binding_record_id or opening.host_frame_record_id
            ),
            "area_basis": opening.area_basis,
            "area_m2": opening.area_m2,
            "source_evidence_count": len(opening.evidence_ids),
            "schedule_explicit_count": bool(opening.schedule_count_explicit),
            "first_missing_prerequisite": readiness,
            "published_area_quantity_ids": [quantity.quantity_id for quantity in published],
            "production_matched_area_quantity_ids": [
                quantity.quantity_id for quantity in signed_publication_matches
            ],
        })
    return {
        "canonical_opening_count": len(claim.canonical_openings),
        "published_area_quantity_count": len(claim.opening_quantity_evidence),
        "production_matched_area_quantity_count": sum(
            len(row["production_matched_area_quantity_ids"]) for row in ledger
        ),
        "published_area_claim_drift_count": sum(
            row["first_missing_prerequisite"] == "opening_area_published_claim_drift"
            for row in ledger
        ),
        "published_explicit_count_quantity_count": len(
            claim.opening_count_quantity_evidence
        ),
        "first_failure_frequency": dict(Counter(
            row["first_missing_prerequisite"] for row in ledger
        )),
        "producer_ready_but_no_area_quantity_count": sum(
            row["first_missing_prerequisite"] == "opening_area_quantity_prerequisites_resolved"
            and not row["published_area_quantity_ids"]
            for row in ledger
        ),
        "per_opening": ledger,
    }




def _ceiling_quantity_diagnostic(claim) -> dict:
    """Shadow-only canonical ceiling -> typed quantity -> source-trace ledger.

    This is not a ceiling/finish detector, measurement publisher, seal or
    benchmark adapter. A missing RCP/room/receipt remains UNAVAILABLE.
    """
    from pb_geometry_takeoff_model import AuthorityStatus
    from pb_live_ceiling_lining_source_closed_export import (
        build_live_ceiling_lining_source_traces,
    )
    from pb_migration_contracts import QuantityEvidence

    ceilings = tuple(claim.canonical_ceilings)
    quantities = tuple(claim.ceiling_lining_quantity_evidence)
    ceiling_ids = Counter(
        ceiling.canonical_ceiling_id
        for ceiling in ceilings
        if type(ceiling.canonical_ceiling_id) is str
        and ceiling.canonical_ceiling_id
    )
    quantity_ids = Counter(
        quantity.quantity_id for quantity in quantities
        if isinstance(quantity, QuantityEvidence)
        and type(quantity.quantity_id) is str and quantity.quantity_id
    )
    room_ids = Counter(
        room.canonical_room_id for room in claim.canonical_rooms
        if type(room.canonical_room_id) is str and room.canonical_room_id
    )
    rooms = {
        room.canonical_room_id: room for room in claim.canonical_rooms
        if type(room.canonical_room_id) is str and room.canonical_room_id
    }
    # This is the actual production source trace gate, never a claim of a
    # source-authenticated quantity made by this diagnostic.
    traced = {}
    trace_error = None
    if quantities:
        try:
            traced = build_live_ceiling_lining_source_traces(
                claim, workspace_id=1, project_id="source-diagnostic:lot16"
            )
        except Exception as error:
            trace_error = type(error).__name__
    by_ceiling = {}
    for quantity in quantities:
        if isinstance(quantity, QuantityEvidence):
            for cid in (quantity.input_entity_ids
                        if type(quantity.input_entity_ids) in (tuple, list) else ()):
                by_ceiling.setdefault(cid, []).append(quantity)

    def first_failure(ceiling):
        cid = ceiling.canonical_ceiling_id
        if (type(cid) is not str or not cid or cid != cid.strip()
                or ceiling_ids[cid] != 1):
            return "canonical_ceiling_identity_unresolved"
        rid = ceiling.room_entity_id
        room = rooms.get(rid) if type(rid) is str else None
        if (room is None or room_ids[rid] != 1
                or not room.physical_room_id
                or not room.source_room_face_record_id
                or room.source_sha256 != ceiling.source_sha256
                or room.revision_id != ceiling.revision_id
                or room.snapshot_id != ceiling.snapshot_id):
            return "physical_ceiling_room_source_ownership_unavailable"
        if (not ceiling.document_id or not ceiling.source_sha256
                or not ceiling.revision_id or not ceiling.snapshot_id
                or type(ceiling.source_page) is not int or ceiling.source_page <= 0
                or not ceiling.viewport_id):
            return "authenticated_ceiling_source_view_unavailable"
        if (not ceiling.geometry_complete
                or type(ceiling.polygon_pdf_pts) not in (tuple, list)
                or len(ceiling.polygon_pdf_pts) < 3):
            return "source_ceiling_geometry_incomplete"
        if (not ceiling.metric_area_complete
                or type(ceiling.area_m2) not in (int, float)
                or not math.isfinite(ceiling.area_m2)
                or ceiling.area_m2 <= 0.0):
            return "firm_ceiling_metric_area_unavailable"
        if (ceiling.measurement_authority
                != MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
                or len(ceiling.figured_dimension_ids) != 2
                or any(type(v) is not str or not v or v != v.strip()
                       for v in ceiling.figured_dimension_ids)
                or len(set(ceiling.figured_dimension_ids)) != 2):
            return "source_documented_ceiling_dimension_pair_unavailable"
        if not ceiling.finish_descriptor:
            return "authenticated_ceiling_finish_semantic_unavailable"
        owned = by_ceiling.get(cid, ())
        if len(owned) != 1:
            return "ceiling_lining_quantity_evidence_unavailable_or_ambiguous"
        quantity = owned[0]
        qid = quantity.quantity_id
        if (type(qid) is not str or not qid or quantity_ids[qid] != 1):
            return "duplicate_or_invalid_ceiling_quantity_identity"
        if (qid != ceiling.ceiling_quantity_id
                or quantity.family != "ceiling_lining"
                or quantity.status != AuthorityStatus.FIRM.value
                or quantity.abstained
                or type(quantity.value) not in (int, float)
                or quantity.unit not in ("m2", "m²")
                or quantity.value != ceiling.area_m2):
            return "firm_ceiling_lining_quantity_unavailable"
        metadata = quantity.metadata
        if (not isinstance(metadata, Mapping)
                or not metadata.get("support_page_id")
                or not metadata.get("support_viewport_id")
                or not metadata.get("support_snapshot_id")):
            return "authenticated_ceiling_rcp_support_unavailable"
        if (not metadata.get("finish_occurrence_record_id")
                or not metadata.get("finish_definition_record_id")):
            return "authenticated_ceiling_finish_occurrence_unavailable"
        if qid not in traced:
            return "source_closed_ceiling_lineage_unresolved"
        return "ceiling_lining_source_trace_resolved"

    ledger = []
    for ceiling in ceilings:
        first = first_failure(ceiling)
        owned_ids = [
            quantity.quantity_id for quantity in
            by_ceiling.get(ceiling.canonical_ceiling_id, ())
        ]
        ledger.append({
            "canonical_ceiling_id": ceiling.canonical_ceiling_id,
            "canonical_room_id": ceiling.room_entity_id,
            "source_page": ceiling.source_page,
            "viewport_id": ceiling.viewport_id,
            "source_sha256": ceiling.source_sha256,
            "area_m2_source_record": (
                ceiling.area_m2 if type(ceiling.area_m2) in (int, float)
                and math.isfinite(ceiling.area_m2) else None
            ),
            "measurement_authority": ceiling.measurement_authority,
            "figured_dimension_receipt_count": len(ceiling.figured_dimension_ids),
            "finish_semantic": ceiling.finish_descriptor,
            "published_quantity_ids": owned_ids,
            "source_trace_quantity_ids": [
                qid for qid in owned_ids if qid in traced
            ],
            "first_missing_prerequisite": first,
        })
    return {
        "diagnostic_only": True,
        "canonical_ceiling_count": len(ceilings),
        "source_ceiling_quantity_count": len(quantities),
        "source_closed_trace_count": len(traced),
        "source_closed_trace_error_type": trace_error,
        "unresolved_universe_reason": (
            "canonical_ceiling_unavailable" if not ceilings else None
        ),
        "duplicate_source_ceiling_quantity_ids": sorted(
            qid for qid, count in quantity_ids.items() if count > 1
        ),
        "first_failure_frequency": dict(Counter(
            row["first_missing_prerequisite"] for row in ledger
        )),
        "per_ceiling": ledger,
    }


def _opening_sealing_diagnostic(claim) -> dict:
    """Exercise existing source-closed sealing and draft customer verification.

    The synthetic workspace ID is diagnostic only; no persistence or scoring.
    """
    from pb_live_opening_source_closed_export import seal_live_opening_area_claim_run
    from pb_live_opening_customer_projection import project_live_opening_customer_rows
    from pb_customer_output_verification import verify_sealed_customer_output

    upstream_ids = sorted(
        quantity.quantity_id for quantity in claim.opening_quantity_evidence
    )
    report = {
        "diagnostic_workspace_only": True,
        "input_opening_area_quantity_count": len(upstream_ids),
        "upstream_quantity_ids": upstream_ids,
    }
    try:
        sealed = seal_live_opening_area_claim_run(
            claim, workspace_id=1, project_id="source-diagnostic:lot16"
        )
        sealed_ids = sorted(quantity.quantity_id for quantity in sealed.quantities)
        report["sealed_opening_area_quantity_count"] = len(sealed_ids)
        report["sealed_quantity_ids"] = sealed_ids
        report["unsealed_upstream_ids"] = sorted(set(upstream_ids) - set(sealed_ids))
        rows = project_live_opening_customer_rows(
            claim, workspace_id=1, project_id="source-diagnostic:lot16"
        )
        verified = verify_sealed_customer_output(sealed, rows)
        report["customer_draft_row_count"] = len(rows)
        report["verified_quantity_ids"] = sorted(verified.verified_quantity_ids)
        report["verified_quantity_count"] = verified.valid_quantity_count
        report["status"] = (
            "source_sealed_and_customer_rows_verified"
            if sealed_ids == upstream_ids
            and len(rows) == len(sealed_ids)
            and sorted(verified.verified_quantity_ids) == sealed_ids
            else "source_to_customer_quantity_mismatch"
        )
    except Exception as error:
        report["status"] = "source_to_customer_exception"
        report["error_type"] = type(error).__name__
        report["error"] = str(error)[:1000]
    return report


def _native_word_label_census(
    pdf_bytes: bytes,
    page_index: int,
    *,
    labels: tuple[str, ...] = (),
) -> dict:
    """Read-only original PDF word inventory; never grants room/metric authority.

    This contrasts native word existence with later producer-owned label/room
    face proof. Every distinct original occurrence retains its own bbox and
    source-native block/line identity; equal label text is never one room ID.
    """
    if not labels:
        return {"diagnostic_only": True, "requested_labels": [], "occurrences": [],
                "count_by_label": {}}
    import fitz

    allowed = {value.casefold() for value in labels
               if type(value) is str and value and value == value.strip()}
    if not allowed:
        return {"diagnostic_only": True, "requested_labels": [], "occurrences": [],
                "count_by_label": {}}
    occurrences = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        if page_index >= len(doc) or page_index < 0:
            raise ValueError("native label census page index out of source bounds")
        source_page = doc[page_index]
        # A drawing can carry true source text above rasterized wall geometry.
        # Tile placement is useful for first-failure attribution, but NEVER
        # authorizes a wall, closed room face or metric quantity.
        tile_bounds = set()
        for image in source_page.get_images(full=True):
            for rect in source_page.get_image_rects(image[0]):
                tile_bounds.add(tuple(round(float(v), 6) for v in (rect.x0, rect.y0, rect.x1, rect.y1)))
        tile_bounds = tuple(sorted(tile_bounds))
        source_words = tuple(word for word in source_page.get_text("words") if len(word) >= 8)
        native_line_words: dict[tuple[int, int], list[tuple[int, str]]] = {}
        for word in source_words:
            native_line_words.setdefault((int(word[5]), int(word[6])), []).append(
                (int(word[7]), str(word[4]))
            )
        for word in source_words:
            if str(word[4]).casefold() not in allowed:
                continue
            native_line_key = (int(word[5]), int(word[6]))
            native_line_text = " ".join(
                item[1] for item in sorted(native_line_words[native_line_key])
            )
            word_bbox = tuple(float(v) for v in word[:4])
            tile_matches = tuple(
                list(tile) for tile in tile_bounds
                if not (
                    tile[2] <= word_bbox[0] or tile[0] >= word_bbox[2]
                    or tile[3] <= word_bbox[1] or tile[1] >= word_bbox[3]
                )
            )
            occurrences.append({
                "original_raster_tile_overlaps_not_geometry": list(tile_matches),
                "original_raster_tile_overlap_count": len(tile_matches),
                "raw_native_text": str(word[4]),
                "same_original_native_line_text_not_authority": native_line_text,
                "source_page_index_zero_based": page_index,
                "bbox_pt": [float(value) for value in word[:4]],
                "block_no": int(word[5]),
                "line_no": int(word[6]),
                "word_no": int(word[7]),
                # Untrusted display-only native words are never substitutes
                # for PdfTextIntegrity or source-room face ownership.
                "room_face_or_measurement_authority_granted": False,
            })
    counts = Counter(row["raw_native_text"].casefold() for row in occurrences)
    return {
        "diagnostic_only": True,
        "requested_labels": sorted(allowed),
        "original_source_image_tile_placement_count": len(tile_bounds),
        "occurrences": occurrences,
        "count_by_label": dict(sorted(counts.items())),
    }


def _raw_face_bbox_label_candidate_ledger(faces, native_census: dict) -> dict:
    """Diagnostic bbox intersections only; never prove room face ownership.

    Original native label text and independently unvalidated planarizer walks
    remain two distinct candidate streams. In particular, a label inside a
    face's BOUNDING RECTANGLE does not prove point-in-face or authenticated
    wall continuity. This helper only localizes the earliest failed gate.
    """
    # For crowded architectural sheets prefer label-adjacent candidate faces,
    # not arbitrary first-N planarizer ordering. Still strictly bounded.
    matching_rows = []
    matching_count = 0
    sample_unmatched = []
    labels = tuple(native_census.get("occurrences", ()) or ())
    count = 0
    for candidate in faces:
        polygon = face_authority._canonical_polygon(candidate)
        if not polygon:
            continue
        count += 1
        # Every candidate contributes to total count. Candidate geometry is
        # not a source-room face, even when text happens to be inside its bbox.
        xs, ys = (point[0] for point in polygon), (point[1] for point in polygon)
        x_coordinates = tuple(xs)
        y_coordinates = tuple(ys)
        bbox = (min(x_coordinates), min(y_coordinates), max(x_coordinates), max(y_coordinates))
        hits = []
        for index, label in enumerate(labels):
            label_bbox = label.get("bbox_pt", ())
            if len(label_bbox) != 4:
                continue
            cx = (label_bbox[0] + label_bbox[2]) * 0.5
            cy = (label_bbox[1] + label_bbox[3]) * 0.5
            if bbox[0] <= cx <= bbox[2] and bbox[1] <= cy <= bbox[3]:
                hits.append(index)
        row = {
            "raw_planar_candidate_bbox_pt": list(bbox),
            "raw_planar_candidate_area_pt2": face_authority._polygon_area(polygon),
            "native_label_occurrence_indices_inside_bbox_only": hits,
            "room_face_or_measurement_authority_granted": False,
        }
        if hits:
            matching_count += 1
            if len(matching_rows) < 150:
                matching_rows.append(row)
        elif len(sample_unmatched) < 20:
            sample_unmatched.append(row)
    rows = matching_rows[:150]
    rows.extend(sample_unmatched[:max(0, 150 - len(rows))])
    return {
        "diagnostic_only": True,
        "raw_candidate_count": count,
        "bbox_candidate_label_intersection_count": matching_count,
        "bbox_rows": rows,
        "truncated": count > len(rows),
        "bbox_overlap_is_not_physical_ownership": True,
    }


def inspect_source(pdf: Path, page_index: int, *, diagnostic_labels: tuple[str, ...] = (),
                   on_original_claim=None) -> dict:
    payload = pdf.read_bytes()
    original_native_label_census = _native_word_label_census(
        payload, page_index, labels=diagnostic_labels,
    )
    observations = []
    original_derive = face_authority._derive_scope_outcome
    original_extract = face_authority.extract_planar_faces
    original_label_resolve = label_authority.SourceRoomLabelAuthority.resolve_scope
    original_witness_intersect = same_view_authority._witness_systems_intersect
    original_trusted_lines = same_view_authority._trusted_lines_for_page
    active_label = {"value": "", "bbox": None}
    def traced_trusted_lines(*args, **kwargs):
        lines = original_trusted_lines(*args, **kwargs)
        candidate_labels = tuple(kwargs.get("candidate_labels") or ())
        active_label["value"] = str(candidate_labels[0]) if len(candidate_labels) == 1 else ""
        active_label["bbox"] = [
            list(line.bbox) for line in lines
        ]
        return lines
    label_scopes = []
    witness_audit = {
        "attempted_pairs": 0,
        "intersecting_pairs": 0,
        "nonintersecting_pairs": 0,
        "failed_pair_samples": [],
    }

    def traced_label_resolve(authority, selector):
        result = original_label_resolve(authority, selector)
        label_scopes.append({
            "page_id": str(selector.page_id),
            "decision_scope_id": str(selector.decision_scope_id),
            "status": str(getattr(result.status, "value", result.status)),
            "reasons": list(result.reason_codes),
            "bound_label_count": len(result.records),
            "split_face_candidate_count": len(result.split_face_candidates),
            "bound_labels": [
                {
                    "label": record.label,
                    "face_id": record.face_id,
                    "source_room_face_record_id": record.source_room_face_record_id,
                }
                for record in result.records
            ],
        })
        return result

    def traced_witness_intersect(horizontal, vertical):
        proven = original_witness_intersect(horizontal, vertical)
        witness_audit["attempted_pairs"] += 1
        witness_audit[
            "intersecting_pairs" if proven else "nonintersecting_pairs"
        ] += 1
        if not proven and len(witness_audit["failed_pair_samples"]) < 300:
            witness_audit["failed_pair_samples"].append({
                "room_label": active_label["value"],
                "trusted_label_bboxes": active_label["bbox"],
                "horizontal_dimension_id": str(horizontal.dimension_id),
                "vertical_dimension_id": str(vertical.dimension_id),
                "horizontal_value_mm": float(horizontal.value_mm),
                "vertical_value_mm": float(vertical.value_mm),
                "horizontal_endpoints_pt": horizontal.endpoints_pt,
                "vertical_endpoints_pt": vertical.endpoints_pt,
                "horizontal_witness_count": len(horizontal.witness_geometries),
                "vertical_witness_count": len(vertical.witness_geometries),
                "horizontal_witness_segments": horizontal.witness_geometries,
                "vertical_witness_segments": vertical.witness_geometries,
                "horizontal_source_witness_ids": list(horizontal.witness_observation_ids),
                "vertical_source_witness_ids": list(vertical.witness_observation_ids),
            })
        return proven

    def traced_extract(segments, *args, **kwargs):
        faces = original_extract(segments, *args, **kwargs)
        areas = sorted(
            (round(face_authority._polygon_area(face_authority._canonical_polygon(face)), 6)
             for face in faces if face_authority._canonical_polygon(face))
        )
        observations[-1]["raw_face_label_bbox_candidate_ledger"] = (
            _raw_face_bbox_label_candidate_ledger(
                faces, original_native_label_census,
            )
        )
        observations[-1]["planar_faces"] = {
            "count": len(faces),
            "canonical_count": len(areas),
            "areas_pt2_sorted": areas[:1000],
            "areas_truncated": len(areas) > 1000,
            "under_absolute_threshold": sum(
                area < face_authority._ABSOLUTE_DEGENERATE_AREA_PT2 for area in areas
            ),
            "under_relative_threshold": sum(
                area < (areas[-1] * face_authority._TINY_RELATIVE_THRESHOLD)
                for area in areas
            ) if areas else 0,
        }
        return faces

    def traced_derive(scope):
        records = tuple(getattr(scope, "records", ()) or ())
        edges_by_wall = {}
        for record in records:
            wall_id = str(getattr(record, "wall_candidate_id", "") or "")
            if wall_id:
                edges_by_wall[wall_id] = face_authority._wall_edges(record)
        observation = {
            "page_id": str(getattr(scope, "page_id", "") or ""),
            "decision_scope_id": str(getattr(scope, "decision_scope_id", "") or ""),
            "scope_status": str(getattr(getattr(scope, "status", None), "value", getattr(scope, "status", None))),
            "scope_complete": bool(getattr(scope, "scope_complete", False)),
            "source_wall_record_count": len(records),
            "source_wall_identity_count": len(edges_by_wall),
            "source_wall_edge_count": sum(map(len, edges_by_wall.values())),
            "source_wall_zero_edge_count": sum(not edges for edges in edges_by_wall.values()),
        }
        observations.append(observation)
        outcome = original_derive(scope)
        observation["outcome_status"] = str(getattr(getattr(outcome, "status", None), "value", getattr(outcome, "status", None)))
        observation["outcome_reasons"] = list(getattr(outcome, "reason_codes", ()) or ())
        observation["published_face_count"] = len(getattr(outcome, "records", ()) or ())
        return outcome

    try:
        face_authority._derive_scope_outcome = traced_derive
        face_authority.extract_planar_faces = traced_extract
        label_authority.SourceRoomLabelAuthority.resolve_scope = traced_label_resolve
        same_view_authority._witness_systems_intersect = traced_witness_intersect
        same_view_authority._trusted_lines_for_page = traced_trusted_lines
        claim = collect_live_physical_net_wall_claim(
            pdf, pages=(page_index,), topology_pages=(page_index,),
            room_area_support_pages=None,
        )
        # Exact source-owned claim is handed once to a trusted read-only
        # source-sealed export caller; no benchmark/truth/identity map input.
        if on_original_claim is not None:
            on_original_claim(claim)
        return {
            "diagnostic_only": True, "pdf_sha256": hashlib.sha256(payload).hexdigest(),
            "source_page_index_zero_based": page_index,
            "native_word_label_census_not_authority": original_native_label_census,
            "scope_outcomes": observations,
            "claim_type": type(claim).__name__,
            "floor_quantity_diagnostic": _floor_quantity_diagnostic(claim),
            "wall_metric_diagnostic": _wall_metric_diagnostic(claim),
            "opening_quantity_diagnostic": _opening_quantity_diagnostic(claim),
            "ceiling_quantity_diagnostic": _ceiling_quantity_diagnostic(claim),
            "opening_sealing_diagnostic": _opening_sealing_diagnostic(claim),
            "source_label_scope_diagnostic": label_scopes,
            "same_view_witness_intersection_audit": witness_audit,
            "label_ownership_diagnostic": {
                "labelled_room_count": sum(bool(room.room_label) for room in claim.canonical_rooms),
                "unlabelled_room_count": sum(not bool(room.room_label) for room in claim.canonical_rooms),
                "label_reason_frequency": dict(Counter(
                    code for room in claim.canonical_rooms
                    for code in (room.room_label_reason_codes or ())
                )),
                "labelled_rooms": [
                    {
                        "physical_room_id": room.physical_room_id,
                        "room_label": room.room_label,
                        "source_face_id": room.source_room_face_record_id,
                        "label_binding_id": room.room_label_binding_record_id,
                        "label_evidence_count": len(room.room_label_evidence_ids),
                        "label_reason_codes": list(room.room_label_reason_codes),
                        "polygon_pdf_pts": [list(point) for point in room.polygon_pdf_pts],
                        "bounding_wall_ids": list(room.bounding_wall_ids),
                        "polygon_area_page_pts2": float(room.area_page_pts2),
                    }
                    for room in claim.canonical_rooms if room.room_label
                ],
            },
            "same_view_prerequisite_breakdown": {
                "room_count": len(claim.canonical_rooms),
                "geometry_incomplete": sum(not room.geometry_complete for room in claim.canonical_rooms),
                "physical_room_id_missing": sum(not str(room.physical_room_id or "").strip() for room in claim.canonical_rooms),
                "source_face_id_missing": sum(not str(room.source_room_face_record_id or "").strip() for room in claim.canonical_rooms),
                "room_label_missing": sum(not str(room.room_label or "").strip() for room in claim.canonical_rooms),
                "room_label_binding_missing": sum(not str(room.room_label_binding_record_id or "").strip() for room in claim.canonical_rooms),
                "room_label_evidence_missing": sum(not bool(room.room_label_evidence_ids) for room in claim.canonical_rooms),
            },
            "downstream": {
                "canonical_room_count": len(claim.canonical_rooms),
                "canonical_room_status": str(getattr(claim.canonical_room_status, "value", claim.canonical_room_status)),
                "canonical_room_reasons": list(claim.canonical_room_reason_codes),
                "canonical_floor_count": len(claim.canonical_floors),
                "canonical_floor_status": str(getattr(claim.canonical_floor_status, "value", claim.canonical_floor_status)),
                "canonical_floor_reasons": list(claim.canonical_floor_reason_codes),
                "metric_floor_count": sum(_has_firm_metric_floor_receipt(floor) for floor in claim.canonical_floors),
                "room_area_quantity_count": len(claim.room_area_quantity_evidence),
                "floor_finish_quantity_count": len(claim.floor_finish_quantity_evidence),
                "same_view_first_failures": list(claim.same_view_room_area_first_failure_codes),
                "cross_view_first_failures": list(claim.cross_view_room_area_first_failure_codes),
                "physical_scale_first_failures": list(claim.physical_scale_first_failure_codes),
            },
            "scope_reason_frequency": dict(Counter(
                reason for item in observations for reason in item["outcome_reasons"]
            )),
        }
    finally:
        face_authority._derive_scope_outcome = original_derive
        face_authority.extract_planar_faces = original_extract
        label_authority.SourceRoomLabelAuthority.resolve_scope = original_label_resolve
        same_view_authority._witness_systems_intersect = original_witness_intersect
        same_view_authority._trusted_lines_for_page = original_trusted_lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--page-index", type=int, default=2)
    parser.add_argument("--diagnostic-label", action="append", default=[],
                        help="exact source word to locate without granting room identity")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.page_index < 0:
        parser.error("--page-index must be >= 0")
    if not args.pdf.is_file():
        parser.error(f"source PDF unavailable: {args.pdf}")
    report = inspect_source(
        args.pdf, args.page_index,
        diagnostic_labels=tuple(args.diagnostic_label),
    )
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "pdf_sha256": report["pdf_sha256"],
        "scope_count": len(report["scope_outcomes"]),
        "scope_reason_frequency": report["scope_reason_frequency"],
        "opening_seal_status": report["opening_sealing_diagnostic"]["status"],
        "output": str(args.output),
    }, sort_keys=True))
    # The artifact is written even on failure so source/quantity first gates
    # remain inspectable. Do not quietly pass source-to-customer mismatches.
    if report["opening_sealing_diagnostic"]["status"] != "source_sealed_and_customer_rows_verified":
        raise SystemExit("source-to-sealed opening/customer row validation failed")


if __name__ == "__main__":
    main()
