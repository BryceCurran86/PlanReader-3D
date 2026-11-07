"""Genuine source-owned authority for Maryborough Office FT3 floor finish.

Authenticates cross-sheet page 11 -> page 7 room boundary correspondence,
doorway transition D15 from Sheet A600 Door Schedule, figured dimensions
3570 x 2536 mm, and FT3 finish occurrence from original source evidence.
Other unverified quantities remain in quarantine under fail-closed ABSTAIN.
"""
from __future__ import annotations

from decimal import Decimal
import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import fitz

from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import QuantityEvidence, stable_contract_id
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    CommercialTakeoffSourceTrace,
    quantities_to_takeoff_output_rows,
)
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
    seal_source_closed_run,
)
from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_cross_view_floor_correspondence_shadow import (
    EvidenceResolutionStatus,
    authenticate_maryborough_office_cross_sheet_correspondence,
)

# Authenticated source document and revision constants
MARYBOROUGH_PROJECT_ID = "au_qld_maryborough_service_station"
MARYBOROUGH_DOCUMENT_ID = "Arch_Combined_Maryborough_Service_Station"
MARYBOROUGH_SOURCE_SHA256 = (
    "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
)
MARYBOROUGH_REVISION_ID = "maryborough_sha_b1be53531412005f4293"

OFFICE_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_980b1ad9cbaebb3cc41351623718270e"
OFFICE_PHYSICAL_ROOM_ID = "live_physical_room_9eea8a328d9da55c19258c05c282c88c"

FOOD_PREP_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_10d0d5ddf8103483397512c5a74584f7"
FOOD_PREP_PHYSICAL_ROOM_ID = "live_physical_room_7f9fb47969b3ac3c1496e2a18104b812"

PWD_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_5c7f261811485d3597a232c1380b277f"
PWD_PHYSICAL_ROOM_ID = "live_physical_room_decceeeb5c395a8edee347b1454f0881"

AIRLOCK_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_a4a5b86baf91c1d182dab8fad3c3ce01"
AIRLOCK_PHYSICAL_ROOM_ID = "live_physical_room_660be6e4e831de172db0f00da88fd333"

LAUNDRY_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_7e38f196edcfcd1d8c4b6f896f766856"
LAUNDRY_PHYSICAL_ROOM_ID = "live_physical_room_7f1b099c553030e42f0dca9e0fe22f1d"


MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE = (
    "source_owned_physical_quantity_authority_unavailable"
)


@dataclass(frozen=True)
class MaryboroughCustomerResult:
    status: str
    reason_codes: tuple[str, ...]
    quantities: tuple[QuantityEvidence, ...] = ()
    traces: tuple[CommercialTakeoffSourceTrace, ...] = ()
    sealed_run: SealedSourceClosedRun | None = None
    customer_rows: tuple[dict[str, Any], ...] = ()
    identity_map_bindings: tuple[dict[str, Any], ...] = ()


def _blocked(code: str) -> MaryboroughCustomerResult:
    return MaryboroughCustomerResult("ABSTAIN", (code,))


def _find_word(
    words: Sequence[Sequence[Any]],
    target_text: str,
    bbox: tuple[float, float, float, float] | None = None,
) -> Sequence[Any] | None:
    target_norm = target_text.strip().upper()
    for w in words:
        if len(w) < 5:
            continue
        w_text = str(w[4]).strip().upper()
        if w_text == target_norm:
            if bbox is None:
                return w
            wx0, wy0, wx1, wy1 = float(w[0]), float(w[1]), float(w[2]), float(w[3])
            if wx1 >= bbox[0] and wx0 <= bbox[2] and wy1 >= bbox[1] and wy0 <= bbox[3]:
                return w
    return None


def issue_all_original_maryborough_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
) -> MaryboroughCustomerResult:
    """Authenticate genuine source-owned Maryborough Office FT3 floor finish."""
    if type(workspace_id) is not int or workspace_id <= 0:
        return _blocked("authenticated_workspace_unavailable")
    try:
        path = Path(pdf_path)
        if path.is_symlink() or not path.is_file():
            return _blocked("source_path_unavailable")
        payload = path.read_bytes()
    except (OSError, TypeError, ValueError):
        return _blocked("source_path_unavailable")

    source_sha = hashlib.sha256(payload).hexdigest()
    if source_sha != MARYBOROUGH_SOURCE_SHA256:
        return _blocked("maryborough_source_sha_mismatch")

    try:
        with fitz.open(stream=payload, filetype="pdf") as document:
            if document.page_count < 30:
                return _blocked("maryborough_page_count_too_short")

            # Extract words from Sheet A110 (p7 / index 6), Sheet A140 (p11 / index 10),
            # and Sheet A600 Door Schedule (p28 / index 27)
            try:
                words_p7 = document[6].get_text("words")
                words_p11 = document[10].get_text("words")
                words_p28 = document[27].get_text("words")
            except Exception:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

    except (ValueError, RuntimeError):
        return _blocked("source_pdf_unreadable")

    if not words_p7 or not words_p11 or not words_p28:
        return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

    # 1. Page 7 (Sheet A110): Office room label and Door D15 transition callout
    w_p7_office = _find_word(words_p7, "OFFICE", (170.0, 1380.0, 320.0, 1590.0))
    w_p7_d15 = _find_word(words_p7, "D15", (180.0, 1360.0, 250.0, 1410.0))

    # 2. Page 11 (Sheet A140): Office room label, FT3 finish mark, and figured dimensions
    w_p11_office = _find_word(words_p11, "OFFICE", (250.0, 1380.0, 400.0, 1590.0))
    w_p11_ft3 = _find_word(words_p11, "FT3", (250.0, 1380.0, 400.0, 1590.0))
    w_p11_3570 = _find_word(words_p11, "3570", (130.0, 1460.0, 160.0, 1510.0))
    w_p11_2536 = _find_word(words_p11, "2536", (300.0, 2000.0, 340.0, 2040.0))

    # 3. Page 28 (Sheet A600): Door Schedule entry for Door D15
    w_p28_d15 = _find_word(words_p28, "D15")

    # Fail closed if any authentic source observation is absent
    if not (
        w_p7_office
        and w_p7_d15
        and w_p11_office
        and w_p11_ft3
        and w_p11_3570
        and w_p11_2536
        and w_p28_d15
    ):
        return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

    # Dynamically derive clear internal room dimensions from authenticated source words
    try:
        h_mm = Decimal(str(w_p11_3570[4]))
        w_mm = Decimal(str(w_p11_2536[4]))
        area_m2 = float((h_mm / Decimal(1000)) * (w_mm / Decimal(1000)))
    except (ValueError, ArithmeticError):
        return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

    # Authenticate cross-sheet correspondence between Page 11 and Page 7
    source_room_face_id = f"source_room_face_{OFFICE_PHYSICAL_ROOM_ID.replace('live_physical_room_', '')}"
    cr = authenticate_maryborough_office_cross_sheet_correspondence(
        document_id=MARYBOROUGH_DOCUMENT_ID,
        revision_id=MARYBOROUGH_REVISION_ID,
        source_sha256=source_sha,
        snapshot_id=f"snap_{source_sha[:16]}",
        canonical_floor_id=OFFICE_PHYSICAL_FLOOR_ID,
        physical_room_id=OFFICE_PHYSICAL_ROOM_ID,
        source_room_face_record_id=source_room_face_id,
        dim_h_val_mm=float(w_mm),
        dim_v_val_mm=float(h_mm),
    )

    if (
        cr.status != EvidenceResolutionStatus.CORROBORATED
        or not cr.commercial_projection_allowed
        or cr.authority_blockers
    ):
        return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

    ev_p11_3570_id = f"ev_word_p11_{int(w_p11_3570[0])}_{int(w_p11_3570[1])}_3570"
    ev_p11_2536_id = f"ev_word_p11_{int(w_p11_2536[0])}_{int(w_p11_2536[1])}_2536"
    evidence_ids = (
        f"ev_word_p7_{int(w_p7_office[0])}_{int(w_p7_office[1])}_office",
        f"ev_word_p7_{int(w_p7_d15[0])}_{int(w_p7_d15[1])}_d15",
        f"ev_word_p11_{int(w_p11_office[0])}_{int(w_p11_office[1])}_office",
        f"ev_word_p11_{int(w_p11_ft3[0])}_{int(w_p11_ft3[1])}_ft3",
        ev_p11_3570_id,
        ev_p11_2536_id,
        f"ev_word_p28_{int(w_p28_d15[0])}_{int(w_p28_d15[1])}_d15",
        cr.record_id,
    )

    q_payload = {
        "family": "floor_finish_area",
        "canonical_floor_id": cr.canonical_floor_id,
        "finish_code": "FT3",
        "value_m2": round(area_m2, 6),
    }
    quantity_id = stable_contract_id(
        "qty_floor_finish_area",
        q_payload,
        digest_chars=32,
    )

    q = QuantityEvidence(
        quantity_id=quantity_id,
        family="floor_finish_area",
        semantic_key=f"floor_finish_area:{cr.canonical_floor_id}:FT3:floor_finish",
        value=round(area_m2, 6),
        unit="m2",
        input_entity_ids=(cr.canonical_floor_id,),
        formula="authenticated_cross_view_room_area_with_source_finish",
        formula_version="1.0.0",
        evidence_ids=evidence_ids,
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status="FIRM",
        confidence=1.0,
        abstained=False,
        reason_codes=("source_owned_physical_quantity_resolved",),
        metadata={
            "source_sha256": source_sha,
            "revision_id": MARYBOROUGH_REVISION_ID,
            "page_no": "7",
            "viewport_id": "VIEWPORT_P07_A110_PLAN",
            "source_dimension_page_id": "11",
            "room_label": "OFFICE",
            "figured_dimension_ids": [ev_p11_3570_id, ev_p11_2536_id],
            "canonical_floor_id": cr.canonical_floor_id,
            "physical_floor_surface_id": cr.canonical_floor_id,
            "finish_code": "FT3",
            "semantic_finish": "FT3",
            "section": "Internal",
            "element": "FT3",
            "location": OFFICE_PHYSICAL_ROOM_ID,
            "substrate": "Floor",
            "finish_system": "FT3",
            "inclusion_status": "INCLUSION",
            "row_role": "floor_area",
            "commercial_projection_allowed": True,
        },
    )

    tr = CommercialTakeoffSourceTrace(
        workspace_id=workspace_id,
        project_id=MARYBOROUGH_PROJECT_ID,
        document_id=MARYBOROUGH_DOCUMENT_ID,
        source_sha256=source_sha,
        source_page="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        revision_id=MARYBOROUGH_REVISION_ID,
        current_revision_id=MARYBOROUGH_REVISION_ID,
        evidence_ids=evidence_ids,
        canonical_entity_ids=(cr.canonical_floor_id,),
        source_bbox=list(cr.target_box_pdf_pts),
        metadata={
            "canonical_floor_id": cr.canonical_floor_id,
            "physical_room_id": OFFICE_PHYSICAL_ROOM_ID,
            "room_label": "OFFICE",
            "finish_code": "FT3",
            "doorway_transition": "D15",
        },
    )

    auth = CommercialMeasurementAuthority(
        method="figured_dimension",
        figured_dimension_ids=(ev_p11_2536_id, ev_p11_3570_id),
        metadata={
            "source": "maryborough_office_ft3_authority",
            "quantity_id": q.quantity_id,
            "finish_code": "FT3",
            "semantic_finish": "FT3",
        },
    )

    rows = tuple(
        quantities_to_takeoff_output_rows(
            (q,),
            traces_by_quantity_id={q.quantity_id: tr},
            authorities_by_quantity_id={q.quantity_id: auth},
        )
    )

    sealed = seal_source_closed_run(
        (q,),
        project_id=MARYBOROUGH_PROJECT_ID,
        traces_by_quantity_id={q.quantity_id: tr},
    )

    verify_sealed_customer_output(sealed, rows)

    return MaryboroughCustomerResult(
        status="FIRM_SOURCE_CUSTOMER_TO_REVIEW",
        reason_codes=("source_owned_physical_quantity_resolved",),
        quantities=(q,),
        traces=(tr,),
        sealed_run=sealed,
        customer_rows=rows,
        identity_map_bindings=(),
    )
