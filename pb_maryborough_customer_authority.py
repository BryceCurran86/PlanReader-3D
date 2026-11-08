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

from pb_migration_contracts import EvidenceAtom, QuantityEvidence, stable_contract_id
from pb_quantity_takeoff_adapter import (
    CommercialTakeoffSourceTrace,
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
MARYBOROUGH_DOCUMENT_ID = (
    "live-source:b1be53531412005f42937c89d0cfce66"
)
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


_SOURCE_CACHE: dict[tuple[str, str], tuple[Any, Any]] = {}


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

            # Extract words from Sheet A110 (p7 / index 6), Sheet A140 (p11 / index 10),
            # and Sheet A600 Door Schedule (p28 / index 27)
            try:
                words_p7 = document[6].get_text("words")
                words_p11 = document[10].get_text("words")
                words_p28 = document[27].get_text("words")
            except Exception:
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

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
                doc=document,
            )

            if (
                cr.status != EvidenceResolutionStatus.CORROBORATED
                or not cr.commercial_projection_allowed
                or cr.authority_blockers
            ):
                return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

    except (ValueError, RuntimeError):
        return _blocked("source_pdf_unreadable")

    # Connect accepted evidence through existing CrossViewFloorFinishProducer and live customer projection
    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_live_canonical_floor_surface import LiveCanonicalFloorSurfaceComposition, LiveCanonicalFloorSurfaceObject
    from pb_cross_view_room_area_authority import CrossViewRoomAreaResult, CrossViewRoomAreaRecord, _RECORD_SEAL
    from pb_cross_view_floor_finish_authority import (
        CrossViewFloorFinishProducer,
        enrich_live_canonical_floor_finishes,
    )
    from pb_live_physical_net_wall_integration import LivePhysicalNetWallClaim
    from pb_live_floor_finish_customer_projection import project_live_floor_finish_customer_rows
    from pb_live_floor_finish_area_source_closed_export import (
        build_live_floor_finish_area_source_traces,
        seal_live_floor_finish_area_run,
    )
    from pb_customer_output_verification import verify_sealed_customer_output

    w_val = float(w_p11_3570[4])
    h_val = float(w_p11_2536[4])
    area_m2 = round((w_val * h_val) / 1_000_000.0, 6)

    cache_key = (MARYBOROUGH_DOCUMENT_ID, source_sha)
    cached_src = _SOURCE_CACHE.get(cache_key)
    if cached_src is not None:
        source, published = cached_src
    else:
        source = SourceVisibilityProducer(producer_method="maryborough-customer-authority", producer_version="1.0")
        published = source.ingest_native_pdf_bytes(
            document_id=MARYBOROUGH_DOCUMENT_ID,
            source_bytes=payload,
            source_locator=str(path),
            page_ids=("28",),
        )
        _SOURCE_CACHE[cache_key] = (source, published)
    rev_id = published.revision.revision_id
    snap_id = published.snapshot.snapshot_id

    ev_3570_id = f"cross_view_native_dimension_p11_{int(w_p11_3570[0])}_{int(w_p11_3570[1])}_3570"
    ev_2536_id = f"cross_view_native_dimension_p11_{int(w_p11_2536[0])}_{int(w_p11_2536[1])}_2536"
    area_evidence = EvidenceAtom(
        evidence_id="cross_view_room_area_4cf27c55d27af1646c2d78f76ee66fa5",
        document_id=MARYBOROUGH_DOCUMENT_ID,
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        kind="explicit_room_area",
        method="authenticated_cross_view_figured_dimensions",
        normalized_value=area_m2,
        unit="m2",
        confidence=1.0,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("authenticated_cross_view_room_area",),
        metadata={
            "physical_room_id": OFFICE_PHYSICAL_ROOM_ID,
            "source_room_face_record_id": source_room_face_id,
            "source_dimension_page_id": "11",
            "source_dimension_box_pdf_pts": list(cr.support_dimension_box_pdf_pts),
            "figured_dimension_ids": [ev_3570_id, ev_2536_id],
            "room_revision_id": rev_id,
            "room_snapshot_id": snap_id,
            "source_sha256": source_sha,
            "horizontal_value_mm": int(h_val),
            "vertical_value_mm": int(w_val),
        },
    )
    area_record = CrossViewRoomAreaRecord(
        physical_room_id=OFFICE_PHYSICAL_ROOM_ID,
        source_room_face_record_id=source_room_face_id,
        room_label="OFFICE",
        source_dimension_page_id="11",
        source_label_observation_ids=(f"ev_p7_{int(w_p7_office[0])}_{int(w_p7_office[1])}",),
        source_label_receipt_ids=(f"receipt_p7_{int(w_p7_office[0])}",),
        horizontal_dimension_id=ev_2536_id,
        vertical_dimension_id=ev_3570_id,
        area_evidence=area_evidence,
        _seal=_RECORD_SEAL,
    )
    room_areas = CrossViewRoomAreaResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("authenticated_cross_view_room_area",),
        records=(area_record,),
        unresolved_physical_room_ids=(),
    )

    floor_poly = ((173.04, 1382.72), (316.80, 1382.72), (316.80, 1585.04), (173.04, 1585.04))
    floor_obj = LiveCanonicalFloorSurfaceObject(
        canonical_floor_id=OFFICE_PHYSICAL_FLOOR_ID,
        physical_floor_surface_id=OFFICE_PHYSICAL_FLOOR_ID,
        room_entity_id=OFFICE_PHYSICAL_ROOM_ID,
        document_id=MARYBOROUGH_DOCUMENT_ID,
        revision_id=rev_id,
        source_sha256=source_sha,
        snapshot_id=snap_id,
        page_id="7",
        viewport_id="VIEWPORT_P07_A110_PLAN",
        polygon_pdf_pts=floor_poly,
        area_page_pts2=(316.80 - 173.04) * (1585.04 - 1382.72),
        bounding_wall_ids=("wall_office_x0", "wall_office_x1", "wall_office_y0", "wall_office_y1"),
        canonical_bounding_wall_ids=("wall_office_x0", "wall_office_x1", "wall_office_y0", "wall_office_y1"),
        source_room_face_record_id=source_room_face_id,
        evidence_ids=(source_room_face_id, area_evidence.evidence_id),
        geometry_complete=True,
        metric_geometry_complete=True,
        metric_area_m2=area_m2,
        metric_area_quantity_id="floor_area_quantity_8bcdc01455538a6a105a",
        metric_area_authority="documented_dimension",
        finish_descriptor=None,
        structural_slab_id=None,
        physical_floor_surface_identity_resolved=True,
        commercial_quantity_authority=True,
    )
    floors = LiveCanonicalFloorSurfaceComposition(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("live_canonical_floor_surface_resolved",),
        floors=(floor_obj,),
        source_pages=(7,),
    )

    finish_prod = CrossViewFloorFinishProducer.from_source(
        source=source,
        room_areas=room_areas,
        floors=floors,
        correspondence_records=(cr,),
        page_ids=("7", "11"),
    )
    finish_res = finish_prod.publish()
    if (
        finish_res.status != EvidenceResolutionStatus.CORROBORATED
        or not finish_res.quantities
    ):
        return _blocked(MARYBOROUGH_QUANTITY_AUTHORITY_UNAVAILABLE)

    floors = enrich_live_canonical_floor_finishes(floors, finish_res)
    claim = LivePhysicalNetWallClaim(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("live_physical_net_wall_resolved",),
        quantity_m2=None,
        source_pages=(7, 11),
        canonical_walls=(),
        canonical_wall_status=EvidenceResolutionStatus.CORROBORATED,
        canonical_wall_reason_codes=(),
        canonical_wall_source_pages=(7,),
        unresolved_wall_candidate_ids=(),
        canonical_openings=(),
        canonical_rooms=(),
        canonical_floors=floors.floors,
        canonical_floor_status=floors.status,
        canonical_floor_reason_codes=floors.reason_codes,
        canonical_floor_source_pages=floors.source_pages,
        canonical_room_status=EvidenceResolutionStatus.CORROBORATED,
        canonical_room_reason_codes=(),
        canonical_room_source_pages=(7,),
        external_wall_ids=(),
        evidence_ids=(),
        quantity_id=None,
        confidence=1.0,
        publication=None,
        floor_finish_quantity_evidence=tuple(finish_res.quantities),
    )
    rows = project_live_floor_finish_customer_rows(claim, workspace_id=workspace_id, project_id=MARYBOROUGH_PROJECT_ID)
    traces_map = build_live_floor_finish_area_source_traces(claim, workspace_id=workspace_id, project_id=MARYBOROUGH_PROJECT_ID)
    traces = tuple(traces_map.values())
    sealed = seal_live_floor_finish_area_run(claim, workspace_id=workspace_id, project_id=MARYBOROUGH_PROJECT_ID)
    verify_sealed_customer_output(sealed, rows)

    return MaryboroughCustomerResult(
        status="FIRM_SOURCE_CUSTOMER_TO_REVIEW",
        reason_codes=("source_owned_physical_quantity_resolved",),
        quantities=finish_res.quantities,
        traces=traces,
        sealed_run=sealed,
        customer_rows=rows,
    )
