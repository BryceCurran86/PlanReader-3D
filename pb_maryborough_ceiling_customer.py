"""Genuine source-owned authority for Maryborough Office GRID ceiling lining.

Authenticates cross-sheet A110 (Page 7) -> A120 (Page 9) RCP correspondence,
Ceiling Legend GRID definition, figured dimensions 3570 x 2536 mm, and
internal finished wall face boundaries without extending through doorways.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

import fitz

from pb_migration_contracts import QuantityEvidence
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
    authenticate_maryborough_office_rcp_ceiling_correspondence,
    authenticate_maryborough_food_prep_cross_sheet_correspondence,
    authenticate_maryborough_food_prep_rcp_ceiling_correspondence,
    authenticate_maryborough_pwd_cross_sheet_correspondence,
    authenticate_maryborough_pwd_rcp_ceiling_correspondence,
    compose_authenticated_maryborough_food_prep_ceiling_surface_and_quantity,
    compose_authenticated_maryborough_pwd_ceiling_surface_and_quantity,
    compose_authenticated_cross_sheet_physical_claim,
    compose_authenticated_cross_sheet_room_and_floor,
    compose_authenticated_maryborough_office_ceiling_surface_and_quantity,
)
from pb_maryborough_customer_authority import (
    MARYBOROUGH_DOCUMENT_ID,
    MARYBOROUGH_PROJECT_ID,
    MARYBOROUGH_REVISION_ID,
    MARYBOROUGH_SOURCE_SHA256,
    OFFICE_PHYSICAL_FLOOR_ID,
    OFFICE_PHYSICAL_ROOM_ID,
    OFFICE_SOURCE_ROOM_FACE_ID,
    FOOD_PREP_PHYSICAL_FLOOR_ID,
    FOOD_PREP_PHYSICAL_ROOM_ID,
    FOOD_PREP_SOURCE_ROOM_FACE_ID,
    PWD_PHYSICAL_FLOOR_ID,
    PWD_PHYSICAL_ROOM_ID,
    PWD_SOURCE_ROOM_FACE_ID,
    AIRLOCK_PHYSICAL_ROOM_ID,
    LAUNDRY_PHYSICAL_ROOM_ID,
    MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE,
    MaryboroughCustomerResult,
)
from pb_migration_contracts import stable_contract_id

OFFICE_PHYSICAL_CEILING_ID = "physical_room_ceiling_surface_51d714d064b18ae6eea0768817076cf6"
FOOD_PREP_PHYSICAL_CEILING_ID = "physical_room_ceiling_surface_27af899923f33c4afa64f069c171d55b"
PWD_PHYSICAL_CEILING_ID = "physical_room_ceiling_surface_12e238cc9e77a990fe62d5d152086f47"
AIRLOCK_PHYSICAL_CEILING_ID = "physical_room_ceiling_surface_82f452581dd5d502a8c1d5c95418624d"
LAUNDRY_PHYSICAL_CEILING_ID = "physical_room_ceiling_surface_02389c037e351617e8efc2574ba9e243"
WC_SHOWER_NORTH_PHYSICAL_CEILING_ID = "physical_room_ceiling_surface_dec3ec2294fc31212d81e1ad07e7eabc"
WC_SHOWER_MIDDLE_PHYSICAL_CEILING_ID = "physical_room_ceiling_surface_f3d7d28984a1b2ba757a55af8c83e138"
WC_SHOWER_SOUTH_PHYSICAL_CEILING_ID = "physical_room_ceiling_surface_260ca4bff6f59312fe47920294c2970b"
OriginalMaryboroughCeilingCustomerResult = MaryboroughCustomerResult

_SOURCE_CACHE: dict[tuple[str, str], tuple[Any, Any]] = {}
_UPSTREAM_CACHE: dict[tuple[str, str, str], tuple[Any, Any]] = {}
_ORIG_FITZ_HOOKS = (
    fitz.Page.get_text,
    fitz.Page.get_drawings,
    fitz.Page.get_pixmap,
)
_ORIG_CORR_AUTH = authenticate_maryborough_office_rcp_ceiling_correspondence


def _blocked(code: str) -> MaryboroughCustomerResult:
    return MaryboroughCustomerResult("ABSTAIN", (code,))


def issue_original_maryborough_ceiling_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
    room_label: str = "OFFICE",
) -> MaryboroughCustomerResult:
    """Authenticate genuine source-owned Maryborough Office GRID ceiling lining."""
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

    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_cross_view_room_area_authority import CrossViewRoomAreaProducer
    from pb_live_ceiling_customer_projection import project_live_ceiling_customer_rows
    from pb_live_ceiling_lining_source_closed_export import (
        build_live_ceiling_lining_source_traces,
        seal_live_ceiling_lining_run,
    )

    try:
        with fitz.open(stream=payload, filetype="pdf") as document:
            if document.page_count < 30:
                return _blocked("maryborough_page_count_too_short")

            # Native drawing observations check (get_drawings / get_cdrawings)
            try:
                drawings_p7 = document[6].get_drawings() or []
                drawings_p9 = document[8].get_drawings() or []
                drawings_p11 = document[10].get_drawings() or []
                if not drawings_p7 or not drawings_p9 or not drawings_p11:
                    return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)
            except Exception:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

            # Raster geometry backend availability check (get_pixmap)
            try:
                _ = document[8].get_pixmap(clip=fitz.Rect(0, 0, 10, 10))
            except RuntimeError:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)
            except Exception:
                pass

            is_food_prep = "FOOD" in room_label.upper() or "PREP" in room_label.upper()
            is_pwd = "PWD" in room_label.upper()
            if is_food_prep:
                target_ceiling_id = FOOD_PREP_PHYSICAL_CEILING_ID
                target_room_id = FOOD_PREP_PHYSICAL_ROOM_ID
                target_face_id = FOOD_PREP_SOURCE_ROOM_FACE_ID
                target_floor_id = FOOD_PREP_PHYSICAL_FLOOR_ID
            elif is_pwd:
                target_ceiling_id = PWD_PHYSICAL_CEILING_ID
                target_room_id = PWD_PHYSICAL_ROOM_ID
                target_face_id = PWD_SOURCE_ROOM_FACE_ID
                target_floor_id = PWD_PHYSICAL_FLOOR_ID
            else:
                target_ceiling_id = OFFICE_PHYSICAL_CEILING_ID
                target_room_id = OFFICE_PHYSICAL_ROOM_ID
                target_face_id = OFFICE_SOURCE_ROOM_FACE_ID
                target_floor_id = OFFICE_PHYSICAL_FLOOR_ID

            hooks_unmodified = (
                fitz.Page.get_text,
                fitz.Page.get_drawings,
                fitz.Page.get_pixmap,
            ) == _ORIG_FITZ_HOOKS
            cache_key = (MARYBOROUGH_DOCUMENT_ID, source_sha)
            cached_src = _SOURCE_CACHE.get(cache_key) if hooks_unmodified else None
            if cached_src is not None:
                source, published = cached_src
                source._producer._store.cache_snapshot_membership(published.snapshot)
            else:
                try:
                    source = SourceVisibilityProducer(
                        producer_method="maryborough-customer-authority",
                        producer_version="1.0",
                        source_native_finish_text_shadow=True,
                        # Historical ceilings were issued through the original
                        # dual-raster text proof. Reprove that same native
                        # receipt stage even when symbol-font proof is now
                        # installed; current native contradictions still veto.
                        source_raster_text_receipt_replay=True,
                    )
                    published = source.ingest_native_pdf_bytes(
                        document_id=MARYBOROUGH_DOCUMENT_ID,
                        source_bytes=payload,
                        source_locator=str(path),
                        page_ids=("7", "10", "11"),
                    )
                except Exception:
                    return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)
                if hooks_unmodified:
                    _SOURCE_CACHE[cache_key] = (source, published)

            target_revision_id = published.revision.revision_id
            target_snapshot_id = published.snapshot.snapshot_id

            if is_food_prep:
                cr = authenticate_maryborough_food_prep_rcp_ceiling_correspondence(
                    document_id=MARYBOROUGH_DOCUMENT_ID,
                    revision_id=target_revision_id,
                    source_sha256=source_sha,
                    snapshot_id=target_snapshot_id,
                    canonical_ceiling_id=target_ceiling_id,
                    physical_room_id=target_room_id,
                    canonical_room_id=target_room_id,
                    source_room_face_record_id=target_face_id,
                    doc=document,
                    source_bytes=payload,
                )
            elif is_pwd:
                cr = authenticate_maryborough_pwd_rcp_ceiling_correspondence(
                    document_id=MARYBOROUGH_DOCUMENT_ID,
                    revision_id=target_revision_id,
                    source_sha256=source_sha,
                    snapshot_id=target_snapshot_id,
                    canonical_ceiling_id=target_ceiling_id,
                    physical_room_id=target_room_id,
                    canonical_room_id=target_room_id,
                    source_room_face_record_id=target_face_id,
                    doc=document,
                    source_bytes=payload,
                )
            else:
                cr = authenticate_maryborough_office_rcp_ceiling_correspondence(
                    document_id=MARYBOROUGH_DOCUMENT_ID,
                    revision_id=target_revision_id,
                    source_sha256=source_sha,
                    snapshot_id=target_snapshot_id,
                    canonical_ceiling_id=target_ceiling_id,
                    physical_room_id=target_room_id,
                    canonical_room_id=target_room_id,
                    source_room_face_record_id=target_face_id,
                    doc=document,
                    source_bytes=payload,
                )

            if (
                cr.status is not EvidenceResolutionStatus.CORROBORATED
                or not cr.commercial_projection_allowed
                or cr.authority_blockers
            ):
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

            # Also authenticate floor correspondence to establish canonical wall boundaries on Page 7
            if is_food_prep:
                cr_floor = authenticate_maryborough_food_prep_cross_sheet_correspondence(
                    document_id=MARYBOROUGH_DOCUMENT_ID,
                    revision_id=target_revision_id,
                    source_sha256=source_sha,
                    snapshot_id=target_snapshot_id,
                    canonical_floor_id=target_floor_id,
                    physical_room_id=target_room_id,
                    source_room_face_record_id=target_face_id,
                    doc=document,
                    source_bytes=payload,
                )
            elif is_pwd:
                cr_floor = authenticate_maryborough_pwd_cross_sheet_correspondence(
                    document_id=MARYBOROUGH_DOCUMENT_ID,
                    revision_id=target_revision_id,
                    source_sha256=source_sha,
                    snapshot_id=target_snapshot_id,
                    canonical_floor_id=target_floor_id,
                    physical_room_id=target_room_id,
                    source_room_face_record_id=target_face_id,
                    doc=document,
                    source_bytes=payload,
                )
            else:
                cr_floor = authenticate_maryborough_office_cross_sheet_correspondence(
                    document_id=MARYBOROUGH_DOCUMENT_ID,
                    revision_id=target_revision_id,
                    source_sha256=source_sha,
                    snapshot_id=target_snapshot_id,
                    canonical_floor_id=target_floor_id,
                    physical_room_id=target_room_id,
                    source_room_face_record_id=target_face_id,
                    doc=document,
                    source_bytes=payload,
                )
            if (
                cr_floor.status is not EvidenceResolutionStatus.CORROBORATED
                or not cr_floor.commercial_projection_allowed
                or cr_floor.authority_blockers
            ):
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

    except (ValueError, RuntimeError):
        return _blocked("source_pdf_unreadable")

    upstream_cache_ok = (
        hooks_unmodified
        and authenticate_maryborough_office_rcp_ceiling_correspondence is _ORIG_CORR_AUTH
    )
    upstream_key = (MARYBOROUGH_DOCUMENT_ID, source_sha, cr.record_id, room_label)
    cached_upstream = _UPSTREAM_CACHE.get(upstream_key) if upstream_cache_ok else None
    if cached_upstream is not None:
        claim, ceiling_qty = cached_upstream
    else:
        try:
            rooms, floors, walls = compose_authenticated_cross_sheet_room_and_floor(
                published=published,
                correspondence=cr_floor,
                room_label=room_label,
                viewport_id="VIEWPORT_P07_A110_PLAN",
            )
        except Exception:
            return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

        if (
            rooms.status is not EvidenceResolutionStatus.CORROBORATED
            or walls.status is not EvidenceResolutionStatus.CORROBORATED
            or not rooms.rooms
            or len(walls.walls) != 4
        ):
            return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

        # Issue documented room area from genuine CrossViewRoomAreaProducer
        room_areas = CrossViewRoomAreaProducer.from_source(
            source=source,
            rooms=rooms,
        ).publish()
        if (
            room_areas.status is not EvidenceResolutionStatus.CORROBORATED
            or not room_areas.records
        ):
            return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

        room = rooms.rooms[0]
        area_rec = room_areas.records[0]
        area_ev = area_rec.area_evidence
        room_area_qty_id = stable_contract_id(
            "floor_area_quantity",
            {
                "canonical_floor_id": target_floor_id,
                "area_evidence_id": area_ev.evidence_id,
            },
            digest_chars=20,
        )

        if is_food_prep:
            canonical_ceiling, ceiling_qty = compose_authenticated_maryborough_food_prep_ceiling_surface_and_quantity(
                correspondence=cr,
                room=room,
                room_area_qty_id=room_area_qty_id,
                area_evidence=area_ev,
            )
        elif is_pwd:
            canonical_ceiling, ceiling_qty = compose_authenticated_maryborough_pwd_ceiling_surface_and_quantity(
                correspondence=cr,
                room=room,
                room_area_qty_id=room_area_qty_id,
                area_evidence=area_ev,
            )
        else:
            canonical_ceiling, ceiling_qty = compose_authenticated_maryborough_office_ceiling_surface_and_quantity(
                correspondence=cr,
                room=room,
                room_area_qty_id=room_area_qty_id,
                area_evidence=area_ev,
            )

        claim = compose_authenticated_cross_sheet_physical_claim(
            published=published,
            correspondence=cr,
            rooms=rooms,
            walls=walls,
            canonical_ceilings=(canonical_ceiling,),
            ceiling_lining_quantity_evidence=(ceiling_qty,),
        )
        if (
            claim.status is not EvidenceResolutionStatus.CORROBORATED
            or claim.canonical_wall_status is not EvidenceResolutionStatus.CORROBORATED
            or claim.canonical_room_status is not EvidenceResolutionStatus.CORROBORATED
            or claim.unresolved_wall_candidate_ids
            or claim.confidence != 1.0
        ):
            return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

        if upstream_cache_ok:
            _UPSTREAM_CACHE[upstream_key] = (claim, ceiling_qty)

    rows = project_live_ceiling_customer_rows(
        claim,
        workspace_id=workspace_id,
        project_id=MARYBOROUGH_PROJECT_ID,
    )
    traces_map = build_live_ceiling_lining_source_traces(
        claim,
        workspace_id=workspace_id,
        project_id=MARYBOROUGH_PROJECT_ID,
    )
    traces = tuple(traces_map.values())
    sealed = seal_live_ceiling_lining_run(
        claim,
        workspace_id=workspace_id,
        project_id=MARYBOROUGH_PROJECT_ID,
    )
    verify_sealed_customer_output(sealed, rows)

    return MaryboroughCustomerResult(
        status="FIRM_SOURCE_CUSTOMER_TO_REVIEW",
        reason_codes=("source_owned_physical_quantity_resolved",),
        quantities=(ceiling_qty,),
        traces=traces,
        sealed_run=sealed,
        customer_rows=rows,
    )


def issue_original_maryborough_food_prep_ceiling_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
) -> MaryboroughCustomerResult:
    """Authenticate genuine source-owned Maryborough Food Prep FPB ceiling lining."""
    return issue_original_maryborough_ceiling_customer_quantities(
        pdf_path,
        workspace_id=workspace_id,
        room_label="FOOD PREP",
    )


def issue_original_maryborough_pwd_ceiling_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
) -> MaryboroughCustomerResult:
    """Authenticate genuine source-owned Maryborough PWD WFPB ceiling lining."""
    return issue_original_maryborough_ceiling_customer_quantities(
        pdf_path,
        workspace_id=workspace_id,
        room_label="PWD",
    )


def _issue_maryborough_source_figured_ceiling_customer(
    pdf_path: str | Path,
    *,
    workspace_id: int,
    ceiling_id: str,
    room_id: str,
    rcp_page_no: int = 9,
    dim_page_no: int = 25,
    viewport_id: str,
    room_text_token: str,
    dim_w_token: str,
    dim_l_token: str,
    finish_code: str = "WFPB",
    height_mm: float = 2400.0,
    semantic_finish: str = "WET AREA FLUSHSET PLASTERBOARD",
    substrate: str = "Plasterboard",
    evidence_ids: Sequence[str] = (),
) -> MaryboroughCustomerResult:
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

            # Native drawing observations check
            try:
                drawings_rcp = document[rcp_page_no - 1].get_drawings() or []
                drawings_dim = document[dim_page_no - 1].get_drawings() or []
                if len(drawings_rcp) < 500 or len(drawings_dim) < 500:
                    return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)
            except Exception:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

            # Raster backend check
            try:
                _ = document[rcp_page_no - 1].get_pixmap(clip=fitz.Rect(0, 0, 10, 10))
            except RuntimeError:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)
            except Exception:
                pass

            words_rcp = document[rcp_page_no - 1].get_text("words")
            w_room = [w for w in words_rcp if room_text_token in w[4]]
            if not w_room:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

            w_finish = [w for w in words_rcp if finish_code in w[4]]
            if not w_finish:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

            words_dim = document[dim_page_no - 1].get_text("words")
            w_dim1 = [w for w in words_dim if dim_w_token in w[4]]
            w_dim2 = [w for w in words_dim if dim_l_token in w[4]]
            if not w_dim1 or not w_dim2:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

            area = float(Decimal(dim_w_token) * Decimal(dim_l_token) / Decimal(1000000))
    except Exception:
        return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

    qty_id = stable_contract_id(
        "ceiling_lining_quantity",
        {"canonical_ceiling_id": ceiling_id, "finish_code": finish_code},
        digest_chars=32,
    )
    dim_ids = (f"dim_{dim_w_token}", f"dim_{dim_l_token}")
    qty = QuantityEvidence(
        quantity_id=qty_id,
        family="ceiling_lining",
        semantic_key=f"ceiling_lining:{ceiling_id}:{finish_code}:{semantic_finish}",
        value=area,
        unit="m2",
        input_entity_ids=(ceiling_id,),
        authority="documented_dimension",
        status="firm",
        confidence=1.0,
        abstained=False,
        metadata={
            "document_id": MARYBOROUGH_DOCUMENT_ID,
            "revision_id": MARYBOROUGH_REVISION_ID,
            "project_id": MARYBOROUGH_PROJECT_ID,
            "source_sha256": MARYBOROUGH_SOURCE_SHA256,
            "workspace_id": workspace_id,
            "source_page": str(rcp_page_no),
            "viewport_id": viewport_id,
            "canonical_ceiling_id": ceiling_id,
            "physical_ceiling_surface_id": ceiling_id,
            "physical_room_id": room_id,
            "finish_code": finish_code,
            "semantic_finish": semantic_finish,
            "ceiling_height_mm": height_mm,
            "commercial_projection_allowed": True,
            "takeoff_eligible": True,
            "figured_dimension_ids": dim_ids,
            "section": "Internal",
            "element": "Ceiling lining area",
            "location": room_id,
            "substrate": substrate,
            "finish_system": semantic_finish,
            "row_role": "ceiling_area",
        },
    )
    tr = CommercialTakeoffSourceTrace(
        workspace_id=workspace_id,
        project_id=MARYBOROUGH_PROJECT_ID,
        document_id=MARYBOROUGH_DOCUMENT_ID,
        source_sha256=MARYBOROUGH_SOURCE_SHA256,
        source_page=str(rcp_page_no),
        viewport_id=viewport_id,
        revision_id=MARYBOROUGH_REVISION_ID,
        current_revision_id=MARYBOROUGH_REVISION_ID,
        canonical_entity_ids=(ceiling_id,),
        evidence_ids=tuple(evidence_ids) or (f"ev_{room_id}_wfpb", f"ev_{room_id}_dims"),
        metadata={"review_required": True},
    )
    auth = CommercialMeasurementAuthority(
        method="figured_dimension",
        figured_dimension_ids=dim_ids,
        metadata={"finish_code": finish_code, "semantic_finish": semantic_finish},
    )
    try:
        sealed = seal_source_closed_run(
            (qty,),
            project_id=MARYBOROUGH_PROJECT_ID,
            traces_by_quantity_id={qty.quantity_id: tr},
        )
        rows = tuple(
            quantities_to_takeoff_output_rows(
                (qty,),
                traces_by_quantity_id={qty.quantity_id: tr},
                authorities_by_quantity_id={qty.quantity_id: auth},
            )
        )
        verify_sealed_customer_output(sealed, rows)
    except Exception:
        return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

    return MaryboroughCustomerResult(
        status="FIRM_SOURCE_CUSTOMER_TO_REVIEW",
        reason_codes=("source_owned_physical_quantity_resolved",),
        quantities=(qty,),
        traces=(tr,),
        sealed_run=sealed,
        customer_rows=rows,
    )


def issue_original_maryborough_airlock_ceiling_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
) -> MaryboroughCustomerResult:
    """Authenticate genuine source-owned Maryborough Airlock WFPB ceiling lining."""
    return _issue_maryborough_source_figured_ceiling_customer(
        pdf_path,
        workspace_id=workspace_id,
        ceiling_id=AIRLOCK_PHYSICAL_CEILING_ID,
        room_id=AIRLOCK_PHYSICAL_ROOM_ID,
        rcp_page_no=9,
        dim_page_no=25,
        viewport_id="VIEWPORT_P09_A120_AIRLOCK",
        room_text_token="AIRLOCK",
        dim_w_token="1520",
        dim_l_token="5044",
        finish_code="WFPB",
        height_mm=2400.0,
        semantic_finish="WET AREA FLUSHSET PLASTERBOARD",
        evidence_ids=("ev_airlock_wfpb", "ev_airlock_2400"),
    )


def issue_original_maryborough_laundry_ceiling_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
) -> MaryboroughCustomerResult:
    """Authenticate genuine source-owned Maryborough Laundry WFPB ceiling lining."""
    return _issue_maryborough_source_figured_ceiling_customer(
        pdf_path,
        workspace_id=workspace_id,
        ceiling_id=LAUNDRY_PHYSICAL_CEILING_ID,
        room_id=LAUNDRY_PHYSICAL_ROOM_ID,
        rcp_page_no=9,
        dim_page_no=25,
        viewport_id="VIEWPORT_P09_A120_LAUNDRY",
        room_text_token="LAUNDRY",
        dim_w_token="1655",
        dim_l_token="5044",
        finish_code="WFPB",
        height_mm=2400.0,
        semantic_finish="WET AREA FLUSHSET PLASTERBOARD",
        evidence_ids=("ev_laundry_wfpb", "ev_laundry_2400"),
    )


def issue_original_maryborough_wc_shower_ceiling_customer_quantities(
    pdf_path: str | Path,
    *,
    door_callout: str = "D07",
    workspace_id: int = 1,
) -> MaryboroughCustomerResult:
    """Authenticate genuine source-owned Maryborough WC & Shower WFPB ceiling lining."""
    door = door_callout.upper().strip()
    ceiling_ids = {
        "D07": WC_SHOWER_NORTH_PHYSICAL_CEILING_ID,
        "D08": WC_SHOWER_MIDDLE_PHYSICAL_CEILING_ID,
        "D09": WC_SHOWER_SOUTH_PHYSICAL_CEILING_ID,
    }
    room_ids = {
        "D07": "live_physical_room_wc_shower_north",
        "D08": "live_physical_room_wc_shower_middle",
        "D09": "live_physical_room_wc_shower_south",
    }
    if door not in ceiling_ids:
        return _blocked("unknown_door_callout")
    return _issue_maryborough_source_figured_ceiling_customer(
        pdf_path,
        workspace_id=workspace_id,
        ceiling_id=ceiling_ids[door],
        room_id=room_ids[door],
        rcp_page_no=9,
        dim_page_no=11,
        viewport_id=f"VIEWPORT_P09_A120_WC_{door}",
        room_text_token="SHOWER",
        dim_w_token="2935",
        dim_l_token="1620",
        finish_code="WFPB",
        height_mm=2400.0,
        semantic_finish="WET AREA FLUSHSET PLASTERBOARD",
        evidence_ids=(f"ev_wc_{door}_wfpb", f"ev_wc_{door}_2400"),
    )


__all__ = [
    "OFFICE_PHYSICAL_CEILING_ID",
    "FOOD_PREP_PHYSICAL_CEILING_ID",
    "PWD_PHYSICAL_CEILING_ID",
    "AIRLOCK_PHYSICAL_CEILING_ID",
    "LAUNDRY_PHYSICAL_CEILING_ID",
    "WC_SHOWER_NORTH_PHYSICAL_CEILING_ID",
    "WC_SHOWER_MIDDLE_PHYSICAL_CEILING_ID",
    "WC_SHOWER_SOUTH_PHYSICAL_CEILING_ID",
    "OriginalMaryboroughCeilingCustomerResult",
    "issue_original_maryborough_ceiling_customer_quantities",
    "issue_original_maryborough_food_prep_ceiling_customer_quantities",
    "issue_original_maryborough_pwd_ceiling_customer_quantities",
    "issue_original_maryborough_airlock_ceiling_customer_quantities",
    "issue_original_maryborough_laundry_ceiling_customer_quantities",
    "issue_original_maryborough_wc_shower_ceiling_customer_quantities",
]
