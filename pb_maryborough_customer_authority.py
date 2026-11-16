"""Genuine source-owned authority for Maryborough Office FT3 floor finish.

Authenticates cross-sheet page 11 -> page 7 room boundary correspondence,
doorway transition D15 from Sheet A600 Door Schedule, figured dimensions
3570 x 2536 mm, and FT3 finish occurrence from original source evidence.
Other unverified quantities remain in quarantine under fail-closed ABSTAIN.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

import fitz

from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import (
    CommercialTakeoffSourceTrace,
)
from pb_source_closed_run_export import (
    SealedSourceClosedRun,
)
from pb_customer_output_verification import verify_sealed_customer_output
from pb_source_cross_view_floor_correspondence_shadow import (
    EvidenceResolutionStatus,
    authenticate_maryborough_office_cross_sheet_correspondence,
    authenticate_maryborough_food_prep_cross_sheet_correspondence,
    authenticate_maryborough_pwd_cross_sheet_correspondence,
    compose_authenticated_cross_sheet_physical_claim,
    compose_authenticated_cross_sheet_room_and_floor,
    enrich_cross_sheet_floor_with_documented_area,
    resolve_cross_sheet_floor_correspondence_for_claim,
)

# Authenticated source document and revision constants
MARYBOROUGH_PROJECT_ID = "au_qld_maryborough_service_station"
MARYBOROUGH_DOCUMENT_ID = (
    "live-source:b1be53531412005f42937c89d0cfce66"
)
MARYBOROUGH_SOURCE_SHA256 = (
    "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"
)
MARYBOROUGH_REVISION_ID = "maryborough_sha_b1be53531412005f4293"

OFFICE_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_980b1ad9cbaebb3cc41351623718270e"
OFFICE_PHYSICAL_ROOM_ID = "live_physical_room_9eea8a328d9da55c19258c05c282c88c"
OFFICE_SOURCE_ROOM_FACE_ID = "source_room_face_record_735f9b309cca70f513c9fcd9390e3e10"

FOOD_PREP_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_10d0d5ddf8103483397512c5a74584f7"
FOOD_PREP_PHYSICAL_ROOM_ID = "live_physical_room_7f9fb47969b3ac3c1496e2a18104b812"
FOOD_PREP_SOURCE_ROOM_FACE_ID = "source_room_face_record_a163b3690c0b2db83f89fcf7465bd831"

PWD_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_5c7f261811485d3597a232c1380b277f"
PWD_PHYSICAL_ROOM_ID = "live_physical_room_decceeeb5c395a8edee347b1454f0881"
PWD_SOURCE_ROOM_FACE_ID = "source_room_face_record_f668f28c3762a6694ec2118010c12c96"

AIRLOCK_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_a4a5b86baf91c1d182dab8fad3c3ce01"
AIRLOCK_PHYSICAL_ROOM_ID = "live_physical_room_660be6e4e831de172db0f00da88fd333"

LAUNDRY_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_7e38f196edcfcd1d8c4b6f896f766856"
LAUNDRY_PHYSICAL_ROOM_ID = "live_physical_room_7f1b099c553030e42f0dca9e0fe22f1d"


_SOURCE_CACHE: dict[tuple[str, str], tuple[Any, Any]] = {}
_UPSTREAM_CACHE: dict[tuple[str, str, str], tuple[Any, Any, Any]] = {}
_ORIG_FITZ_HOOKS = (
    fitz.Page.get_text,
    fitz.Page.get_drawings,
    fitz.Page.get_pixmap,
)
_ORIG_CORR_AUTH = (
    authenticate_maryborough_office_cross_sheet_correspondence,
    authenticate_maryborough_food_prep_cross_sheet_correspondence,
    authenticate_maryborough_pwd_cross_sheet_correspondence,
)


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


def issue_all_original_maryborough_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
    room_label: str = "OFFICE",
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

    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_cross_view_room_area_authority import CrossViewRoomAreaProducer
    from pb_cross_view_floor_finish_authority import (
        CrossViewFloorFinishProducer,
        enrich_live_canonical_floor_finishes,
    )
    from pb_live_floor_finish_customer_projection import project_live_floor_finish_customer_rows
    from pb_live_floor_finish_area_source_closed_export import (
        build_live_floor_finish_area_source_traces,
        seal_live_floor_finish_area_run,
    )

    try:
        with fitz.open(stream=payload, filetype="pdf") as document:
            if document.page_count < 30:
                return _blocked("maryborough_page_count_too_short")

            # Native drawing observations check (get_drawings / get_cdrawings)
            try:
                drawings_p7 = document[6].get_drawings() or []
                drawings_p11 = document[10].get_drawings() or []
                if not drawings_p7 or not drawings_p11:
                    return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)
            except Exception:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

            # Raster geometry backend availability check (get_pixmap)
            try:
                _ = document[6].get_pixmap(clip=fitz.Rect(0, 0, 10, 10))
            except RuntimeError:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)
            except Exception:
                pass

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
                        source_glyph_ledger_text_trust=True,
                    )
                    published = source.ingest_native_pdf_bytes(
                        document_id=MARYBOROUGH_DOCUMENT_ID,
                        source_bytes=payload,
                        source_locator=str(path),
                        page_ids=("7", "11"),
                    )
                except Exception:
                    return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)
                if hooks_unmodified:
                    _SOURCE_CACHE[cache_key] = (source, published)

            target_revision_id = published.revision.revision_id
            target_snapshot_id = published.snapshot.snapshot_id

            is_food_prep = "FOOD" in room_label.upper() or "PREP" in room_label.upper()
            is_pwd = "PWD" in room_label.upper()
            if is_food_prep:
                target_floor_id = FOOD_PREP_PHYSICAL_FLOOR_ID
                target_room_id = FOOD_PREP_PHYSICAL_ROOM_ID
                target_face_id = FOOD_PREP_SOURCE_ROOM_FACE_ID
                cr = authenticate_maryborough_food_prep_cross_sheet_correspondence(
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
                target_floor_id = PWD_PHYSICAL_FLOOR_ID
                target_room_id = PWD_PHYSICAL_ROOM_ID
                target_face_id = PWD_SOURCE_ROOM_FACE_ID
                cr = authenticate_maryborough_pwd_cross_sheet_correspondence(
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
                target_floor_id = OFFICE_PHYSICAL_FLOOR_ID
                target_room_id = OFFICE_PHYSICAL_ROOM_ID
                target_face_id = OFFICE_SOURCE_ROOM_FACE_ID
                cr = authenticate_maryborough_office_cross_sheet_correspondence(
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
                cr.status is not EvidenceResolutionStatus.CORROBORATED
                or not cr.commercial_projection_allowed
                or cr.authority_blockers
            ):
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

    except (ValueError, RuntimeError):
        return _blocked("source_pdf_unreadable")

    upstream_cache_ok = (
        hooks_unmodified
        and (
            authenticate_maryborough_office_cross_sheet_correspondence,
            authenticate_maryborough_food_prep_cross_sheet_correspondence,
            authenticate_maryborough_pwd_cross_sheet_correspondence,
        ) == _ORIG_CORR_AUTH
    )
    upstream_key = (MARYBOROUGH_DOCUMENT_ID, source_sha, cr.record_id, room_label)
    cached_upstream = _UPSTREAM_CACHE.get(upstream_key) if upstream_cache_ok else None
    if cached_upstream is not None:
        claim, finish_res = cached_upstream
    else:
        try:
            rooms, floors, walls = compose_authenticated_cross_sheet_room_and_floor(
                published=published,
                correspondence=cr,
                room_label=room_label,
                viewport_id="VIEWPORT_P07_A110_PLAN",
            )
        except Exception:
            return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

        if (
            rooms.status is not EvidenceResolutionStatus.CORROBORATED
            or floors.status is not EvidenceResolutionStatus.CORROBORATED
            or walls.status is not EvidenceResolutionStatus.CORROBORATED
            or not rooms.rooms
            or not floors.floors
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

        floors = enrich_cross_sheet_floor_with_documented_area(
            floors=floors,
            room_areas=room_areas,
        )
        correspondence_records = resolve_cross_sheet_floor_correspondence_for_claim(
            source=source,
            cross_view_area=room_areas,
            canonical_floors=floors,
        )
        if not correspondence_records:
            return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

        # Issue FT3 floor finish quantity from genuine CrossViewFloorFinishProducer
        finish_prod = CrossViewFloorFinishProducer.for_source_owned_plan_view_shadow(
            source=source,
            room_areas=room_areas,
            floors=floors,
            page_ids=("11",),
            correspondence_records=correspondence_records,
        )
        finish_res = finish_prod.publish()
        if (
            finish_res.status is not EvidenceResolutionStatus.CORROBORATED
            or not finish_res.quantities
        ):
            return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

        floors = enrich_live_canonical_floor_finishes(floors, finish_res)
        claim = compose_authenticated_cross_sheet_physical_claim(
            published=published,
            correspondence=cr,
            rooms=rooms,
            floors=floors,
            walls=walls,
            finish_result=finish_res,
        )
        if (
            claim.status is not EvidenceResolutionStatus.CORROBORATED
            or claim.canonical_wall_status is not EvidenceResolutionStatus.CORROBORATED
            or claim.canonical_room_status is not EvidenceResolutionStatus.CORROBORATED
            or claim.canonical_floor_status is not EvidenceResolutionStatus.CORROBORATED
            or claim.unresolved_wall_candidate_ids
            or claim.confidence != 1.0
        ):
            return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

        if upstream_cache_ok:
            _UPSTREAM_CACHE[upstream_key] = (claim, finish_res)
    rows = project_live_floor_finish_customer_rows(
        claim,
        workspace_id=workspace_id,
        project_id=MARYBOROUGH_PROJECT_ID,
    )
    traces_map = build_live_floor_finish_area_source_traces(
        claim,
        workspace_id=workspace_id,
        project_id=MARYBOROUGH_PROJECT_ID,
    )
    traces = tuple(traces_map.values())
    sealed = seal_live_floor_finish_area_run(
        claim,
        workspace_id=workspace_id,
        project_id=MARYBOROUGH_PROJECT_ID,
    )
    verify_sealed_customer_output(sealed, rows)

    return MaryboroughCustomerResult(
        status="FIRM_SOURCE_CUSTOMER_TO_REVIEW",
        reason_codes=("source_owned_physical_quantity_resolved",),
        quantities=finish_res.quantities,
        traces=traces,
        sealed_run=sealed,
        customer_rows=rows,
    )


def issue_original_maryborough_food_prep_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
) -> MaryboroughCustomerResult:
    """Authenticate genuine source-owned Maryborough Food Prep FT3 floor finish."""
    return issue_all_original_maryborough_customer_quantities(
        pdf_path,
        workspace_id=workspace_id,
        room_label="FOOD PREP",
    )


def issue_original_maryborough_pwd_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
) -> MaryboroughCustomerResult:
    """Authenticate genuine source-owned Maryborough PWD FT2 floor finish."""
    return issue_all_original_maryborough_customer_quantities(
        pdf_path,
        workspace_id=workspace_id,
        room_label="PWD",
    )
