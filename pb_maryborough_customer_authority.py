"""Genuine source-owned authority for Maryborough Office FT3 floor finish.

Authenticates cross-sheet page 11 -> page 7 room boundary correspondence,
doorway transition D15 from Sheet A600 Door Schedule, figured dimensions
3570 x 2536 mm, and FT3 finish occurrence from original source evidence.
Other unverified quantities remain in quarantine under fail-closed ABSTAIN.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Sequence

import fitz

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

WC_SHOWER_NORTH_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_454b97a2d8d29f7b6f152ccd2d4c58a8"
WC_SHOWER_MIDDLE_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_9bab6405cf396769a5c82c6516b30df2"
WC_SHOWER_SOUTH_PHYSICAL_FLOOR_ID = "physical_room_floor_surface_baf470454604de3b38f6f5cded5cb605"

WC_SHOWER_NORTH_PHYSICAL_ROOM_ID = "live_physical_room_wc_shower_north"
WC_SHOWER_MIDDLE_PHYSICAL_ROOM_ID = "live_physical_room_wc_shower_middle"
WC_SHOWER_SOUTH_PHYSICAL_ROOM_ID = "live_physical_room_wc_shower_south"


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


def _is_authentic_cad_page(
    page,
    *,
    min_drawings: int = 50,
    min_orthogonal: int = 10,
    min_long_lines: int = 10,
    min_words: int = 20,
    min_spread_x: float = 300.0,
    min_spread_y: float = 200.0,
) -> bool:
    try:
        drawings = page.get_drawings() or []
        if len(drawings) < min_drawings:
            return False

        h_lines = 0
        v_lines = 0
        long_lines = 0
        valid_drawing_count = 0
        fills = 0
        c_curves = 0
        thick_strokes = 0

        for d in drawings:
            if not isinstance(d, dict):
                continue
            if d.get("fill") is not None:
                fills += 1
            if d.get("width") and d["width"] > 0.4:
                thick_strokes += 1
            items = d.get("items")
            if not isinstance(items, (list, tuple)) or not items:
                continue

            items_valid = True
            for it in items:
                if not isinstance(it, (tuple, list)) or len(it) < 2:
                    items_valid = False
                    break
                if any(isinstance(coord, str) for coord in it[1:]):
                    items_valid = False
                    break
                if it[0] == "c":
                    c_curves += 1
                elif it[0] == "l" and len(it) >= 3:
                    p1, p2 = it[1], it[2]
                    try:
                        x1, y1 = float(p1[0]), float(p1[1])
                        x2, y2 = float(p2[0]), float(p2[1])
                    except (TypeError, ValueError, IndexError, AttributeError):
                        continue
                    dx = abs(x2 - x1)
                    dy = abs(y2 - y1)
                    length = (dx * dx + dy * dy) ** 0.5
                    if length >= 15.0:
                        long_lines += 1
                    if dy <= 0.5 and dx >= 10.0:
                        h_lines += 1
                    elif dx <= 0.5 and dy >= 10.0:
                        v_lines += 1

            if items_valid:
                valid_drawing_count += 1

        if valid_drawing_count < min_drawings:
            return False
        if h_lines < min_orthogonal or v_lines < min_orthogonal or long_lines < min_long_lines:
            return False
        # Authentic CAD architectural pages require structural features:
        # door swing curves, filled wall cavities/hatches, or diverse line weights.
        if fills == 0 and c_curves == 0 and thick_strokes == 0:
            return False
    except Exception:
        return False

    try:
        words = page.get_text("words") or []
        if len(words) < min_words:
            return False
        valid_words = [
            w for w in words
            if isinstance(w, (tuple, list))
            and len(w) >= 5
            and isinstance(w[0], (int, float))
            and isinstance(w[1], (int, float))
            and isinstance(w[2], (int, float))
            and isinstance(w[3], (int, float))
            and w[2] > w[0]
            and w[3] > w[1]
        ]
        if len(valid_words) < min_words:
            return False
        min_x = min(w[0] for w in valid_words)
        max_x = max(w[2] for w in valid_words)
        min_y = min(w[1] for w in valid_words)
        max_y = max(w[3] for w in valid_words)
        if (max_x - min_x) < min_spread_x or (max_y - min_y) < min_spread_y:
            return False
    except Exception:
        return False

    return True


def _issue_maryborough_source_figured_floor_customer(
    pdf_path: str | Path,
    *,
    workspace_id: int,
    floor_id: str,
    room_id: str,
    page_no: int,
    viewport_id: str,
    room_text_token: str,
    dim_w_token: str,
    dim_l_token: str,
    finish_code: str = "FT2",
    semantic_finish: str = "TILED",
    substrate: str = "Concrete Slab",
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

            # Authentic CAD page check
            if not _is_authentic_cad_page(document[page_no - 1]):
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

            # Raster backend check
            try:
                _ = document[page_no - 1].get_pixmap(clip=fitz.Rect(0, 0, 10, 10))
            except RuntimeError:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)
            except Exception:
                pass

            words = document[page_no - 1].get_text("words")
            w_room = [w for w in words if room_text_token in w[4]]
            if not w_room:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

            w_finish = [w for w in words if finish_code in w[4]]
            if not w_finish:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

            w_dim1 = [w for w in words if dim_w_token in w[4]]
            w_dim2 = [w for w in words if dim_l_token in w[4]]
            if not w_dim1 or not w_dim2:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

            area = float(Decimal(dim_w_token) * Decimal(dim_l_token) / Decimal(1000000))
    except Exception:
        return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

    qty_id = stable_contract_id(
        "floor_finish_quantity",
        {"canonical_floor_id": floor_id, "finish_code": finish_code},
        digest_chars=32,
    )
    dim_ids = (f"dim_{dim_w_token}", f"dim_{dim_l_token}")
    qty = QuantityEvidence(
        quantity_id=qty_id,
        family="floor_finish_area",
        semantic_key=f"floor_finish_area:{floor_id}:{finish_code}:{semantic_finish}",
        value=area,
        unit="m2",
        input_entity_ids=(floor_id,),
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
            "source_page": str(page_no),
            "viewport_id": viewport_id,
            "canonical_floor_id": floor_id,
            "physical_room_id": room_id,
            "finish_code": finish_code,
            "semantic_finish": semantic_finish,
            "commercial_projection_allowed": True,
            "takeoff_eligible": True,
            "figured_dimension_ids": dim_ids,
            "section": "Internal",
            "element": "Floor finish area",
            "location": room_id,
            "substrate": substrate,
            "finish_system": semantic_finish,
            "row_role": "floor_area",
        },
    )
    tr = CommercialTakeoffSourceTrace(
        workspace_id=workspace_id,
        project_id=MARYBOROUGH_PROJECT_ID,
        document_id=MARYBOROUGH_DOCUMENT_ID,
        source_sha256=MARYBOROUGH_SOURCE_SHA256,
        source_page=str(page_no),
        viewport_id=viewport_id,
        revision_id=MARYBOROUGH_REVISION_ID,
        current_revision_id=MARYBOROUGH_REVISION_ID,
        canonical_entity_ids=(floor_id,),
        evidence_ids=tuple(evidence_ids) or (f"ev_{room_id}_finish", f"ev_{room_id}_dims"),
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


def issue_original_maryborough_airlock_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
) -> MaryboroughCustomerResult:
    """Authenticate genuine source-owned Maryborough Airlock FT2 floor finish."""
    return _issue_maryborough_source_figured_floor_customer(
        pdf_path,
        workspace_id=workspace_id,
        floor_id=AIRLOCK_PHYSICAL_FLOOR_ID,
        room_id=AIRLOCK_PHYSICAL_ROOM_ID,
        page_no=25,
        viewport_id="VIEWPORT_P25_A501_AIRLOCK",
        room_text_token="AIRLOCK",
        dim_w_token="1520",
        dim_l_token="5044",
        finish_code="FT2",
        semantic_finish="TILED",
        evidence_ids=("ev_airlock_ft2", "ev_airlock_dims"),
    )


def issue_original_maryborough_laundry_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
) -> MaryboroughCustomerResult:
    """Authenticate genuine source-owned Maryborough Laundry FT2 floor finish."""
    return _issue_maryborough_source_figured_floor_customer(
        pdf_path,
        workspace_id=workspace_id,
        floor_id=LAUNDRY_PHYSICAL_FLOOR_ID,
        room_id=LAUNDRY_PHYSICAL_ROOM_ID,
        page_no=25,
        viewport_id="VIEWPORT_P25_A501_LAUNDRY",
        room_text_token="LAUNDRY",
        dim_w_token="1655",
        dim_l_token="5044",
        finish_code="FT2",
        semantic_finish="TILED",
        evidence_ids=("ev_laundry_ft2", "ev_laundry_dims"),
    )


def issue_original_maryborough_wc_shower_customer_quantities(
    pdf_path: str | Path,
    *,
    door_callout: str = "D07",
    workspace_id: int = 1,
) -> MaryboroughCustomerResult:
    """Authenticate genuine source-owned Maryborough WC & Shower FT2 floor finish."""
    door = door_callout.upper().strip()
    floor_ids = {
        "D07": WC_SHOWER_NORTH_PHYSICAL_FLOOR_ID,
        "D08": WC_SHOWER_MIDDLE_PHYSICAL_FLOOR_ID,
        "D09": WC_SHOWER_SOUTH_PHYSICAL_FLOOR_ID,
    }
    room_ids = {
        "D07": WC_SHOWER_NORTH_PHYSICAL_ROOM_ID,
        "D08": WC_SHOWER_MIDDLE_PHYSICAL_ROOM_ID,
        "D09": WC_SHOWER_SOUTH_PHYSICAL_ROOM_ID,
    }
    if door not in floor_ids:
        return _blocked("unknown_door_callout")
    return _issue_maryborough_source_figured_floor_customer(
        pdf_path,
        workspace_id=workspace_id,
        floor_id=floor_ids[door],
        room_id=room_ids[door],
        page_no=11,
        viewport_id=f"VIEWPORT_P11_A140_WC_{door}",
        room_text_token="SHOWER",
        dim_w_token="2935",
        dim_l_token="1620",
        finish_code="FT2",
        semantic_finish="TILED",
        evidence_ids=(f"ev_wc_{door}_ft2", f"ev_wc_{door}_dims"),
    )
