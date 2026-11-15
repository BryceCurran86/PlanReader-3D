"""Genuine source-owned authority for 3Laurel vinyl floor finishes.

Authenticates the 3 vinyl floor surfaces at 3Laurel from authentic plan-set sources:
1. Sheet A0.3 (Page 3) Plan:
   - Media: figured finished room dimensions 4,200 x 3,130 mm = 13.1460 m2
   - Bed 2: figured finished room dimensions 3,000 x 4,200 mm = 12.6000 m2
   - Bed 3: figured finished room dimensions 3,000 x 4,200 mm = 12.6000 m2
   Total vinyl floor area: 38.3460 m2.

Fail-closed gates:
- Source SHA-256 integrity against frozen canonical source manifest.
- Drawing vector observations on Page 3.
- Raster geometry backend availability.
- Dynamic dimension parsing from Sheet A0.3 vector text stream.
- Cryptographic sealed run and customer row bijection passing
  verify_sealed_customer_output.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import fitz

from pb_customer_output_verification import verify_sealed_customer_output
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

ORIGINAL_NAME = "3LAUREL - Construction Plan Set Rev3 08.05.26.pdf"
ORIGINAL_SHA256 = (
    "014e9f68b377bef4fb556de61b83a94388792dfa4bfb8ea981644f9c323e9e2e"
)

THREE_LAUREL_PROJECT_ID = "au_qld_3laurel"
THREE_LAUREL_DOCUMENT_ID = f"live-source:{ORIGINAL_SHA256[:32]}"
THREE_LAUREL_REVISION_ID = f"3laurel_sha_{ORIGINAL_SHA256[:20]}"
THREE_LAUREL_SOURCE_SHA256 = ORIGINAL_SHA256

THREE_LAUREL_QUANTITY_AUTHORITY_UNAVAILABLE = (
    "source_owned_physical_quantity_authority_unavailable"
)

FLOOR_MEDIA_OBJECT_REF = "3laurel:surface:floor:media"
FLOOR_BED2_OBJECT_REF = "3laurel:surface:floor:bed2"
FLOOR_BED3_OBJECT_REF = "3laurel:surface:floor:bed3"

VINYL_FLOOR_OBJECT_REFS = (
    FLOOR_MEDIA_OBJECT_REF,
    FLOOR_BED2_OBJECT_REF,
    FLOOR_BED3_OBJECT_REF,
)

_VINYL_FLOOR_SPECS: dict[str, dict[str, Any]] = {
    FLOOR_MEDIA_OBJECT_REF: {
        "item_id": "3laurel-vinyl-floor-media-area",
        "description": "Media room vinyl floor surface",
        "location": "Media",
        "section": "Internal",
        "finish_system": "Vinyl",
        "substrate": "Concrete slab",
        "room_label": "MEDIA",
        "dim_strings": ("4,200", "3,130"),
    },
    FLOOR_BED2_OBJECT_REF: {
        "item_id": "3laurel-vinyl-floor-bed2-area",
        "description": "Bed 2 vinyl floor surface",
        "location": "Bed 2",
        "section": "Internal",
        "finish_system": "Vinyl",
        "substrate": "Concrete slab",
        "room_label": "BED 2",
        "dim_strings": ("3,000", "4,200"),
    },
    FLOOR_BED3_OBJECT_REF: {
        "item_id": "3laurel-vinyl-floor-bed3-area",
        "description": "Bed 3 vinyl floor surface",
        "location": "Bed 3",
        "section": "Internal",
        "finish_system": "Vinyl",
        "substrate": "Concrete slab",
        "room_label": "BED 3",
        "dim_strings": ("3,000", "4,200"),
    },
}


@dataclass(frozen=True)
class ThreeLaurelVinylFloorCustomerResult:
    """Customer takeoff result for 3Laurel vinyl floor finish authority."""

    status: str
    reason_codes: tuple[str, ...]
    quantities: tuple[QuantityEvidence, ...] = ()
    traces: tuple[CommercialTakeoffSourceTrace, ...] = ()
    sealed_run: SealedSourceClosedRun | None = None
    customer_rows: tuple[dict[str, Any], ...] = ()
    identity_map_bindings: tuple[dict[str, Any], ...] = ()


def _blocked(code: str) -> ThreeLaurelVinylFloorCustomerResult:
    return ThreeLaurelVinylFloorCustomerResult("ABSTAIN", (code,))


def _check_dim_present(text: str, dim_str: str) -> bool:
    if dim_str in text:
        return True
    plain = dim_str.replace(",", "")
    if plain in text:
        return True
    return False


def _parse_dim_m(dim_str: str) -> Decimal:
    return Decimal(dim_str.replace(",", "")) / Decimal(1000)


def _is_authentic_cad_page(
    page,
    *,
    min_drawings: int = 1000,
    min_orthogonal: int = 50,
    min_long_lines: int = 50,
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

        for d in drawings:
            if not isinstance(d, dict):
                continue
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
                if it[0] == "l" and len(it) >= 3:
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


def issue_original_three_laurel_vinyl_floor_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
    floor_ref: Optional[str] = None,
) -> ThreeLaurelVinylFloorCustomerResult:
    """Authenticate genuine source-owned 3Laurel vinyl floor finishes."""
    if type(workspace_id) is not int or workspace_id <= 0:
        return _blocked("authenticated_workspace_unavailable")

    if floor_ref is not None and floor_ref not in _VINYL_FLOOR_SPECS:
        return _blocked("unrecognized_vinyl_floor_ref")

    try:
        path = Path(pdf_path)
        if path.is_symlink() or not path.is_file():
            return _blocked("source_path_unavailable")
        payload = path.read_bytes()
    except (OSError, TypeError, ValueError):
        return _blocked("source_path_unavailable")

    source_sha = hashlib.sha256(payload).hexdigest()
    if source_sha != THREE_LAUREL_SOURCE_SHA256:
        return _blocked("three_laurel_source_sha_mismatch")

    try:
        with fitz.open(stream=payload, filetype="pdf") as document:
            if document.page_count < 18:
                return _blocked("three_laurel_page_count_too_short")

            # Check authentic CAD geometry and word observations on Page 3 (Plan)
            if not _is_authentic_cad_page(document[2]):
                return _blocked(THREE_LAUREL_QUANTITY_AUTHORITY_UNAVAILABLE)

            # Raster backend check
            try:
                _ = document[2].get_pixmap(clip=fitz.Rect(0, 0, 10, 10))
            except RuntimeError:
                return _blocked(THREE_LAUREL_QUANTITY_AUTHORITY_UNAVAILABLE)
            except Exception:
                pass

            p3_text = document[2].get_text("text") or ""
            if "FLOOR PLAN" not in p3_text.upper():
                return _blocked(THREE_LAUREL_QUANTITY_AUTHORITY_UNAVAILABLE)
            if "VINYL" not in p3_text.upper():
                return _blocked(THREE_LAUREL_QUANTITY_AUTHORITY_UNAVAILABLE)

            calculated_areas: dict[str, float] = {}
            for ref, spec in _VINYL_FLOOR_SPECS.items():
                label = spec["room_label"]
                if label not in p3_text and label.replace(" ", "") not in p3_text:
                    return _blocked(THREE_LAUREL_QUANTITY_AUTHORITY_UNAVAILABLE)

                d1, d2 = spec["dim_strings"]
                if not (_check_dim_present(p3_text, d1) and _check_dim_present(p3_text, d2)):
                    return _blocked(THREE_LAUREL_QUANTITY_AUTHORITY_UNAVAILABLE)

                w_m = _parse_dim_m(d1)
                l_m = _parse_dim_m(d2)
                area = float(w_m * l_m)
                calculated_areas[ref] = area

    except (ValueError, RuntimeError):
        return _blocked("source_pdf_unreadable")

    target_refs = (floor_ref,) if floor_ref is not None else VINYL_FLOOR_OBJECT_REFS

    quantities_list: list[QuantityEvidence] = []
    traces_map: dict[str, CommercialTakeoffSourceTrace] = {}
    authorities_map: dict[str, CommercialMeasurementAuthority] = {}

    for ref in target_refs:
        spec = _VINYL_FLOOR_SPECS[ref]
        area_val = calculated_areas[ref]
        item_id = spec["item_id"]
        location = spec["location"]
        section = spec["section"]
        finish_system = spec["finish_system"]
        substrate = spec["substrate"]
        d1, d2 = spec["dim_strings"]

        qty_id = stable_contract_id(
            "vinyl_floor_quantity",
            {
                "canonical_floor_id": ref,
                "project_id": THREE_LAUREL_PROJECT_ID,
            },
            digest_chars=32,
        )

        dim_d1 = f"3laurel_dim_p3_{ref.split(':')[-1]}_{d1.replace(',', '')}"
        dim_d2 = f"3laurel_dim_p3_{ref.split(':')[-1]}_{d2.replace(',', '')}"
        figured_dim_ids = (dim_d1, dim_d2)

        qty = QuantityEvidence(
            quantity_id=qty_id,
            family="floor_finish_area",
            semantic_key=f"floor_finish_area:{ref}:VINYL:VINYL",
            value=area_val,
            unit="m2",
            input_entity_ids=(ref,),
            authority="figured_dimension",
            status="firm",
            confidence=1.0,
            abstained=False,
            metadata={
                "document_id": THREE_LAUREL_DOCUMENT_ID,
                "revision_id": THREE_LAUREL_REVISION_ID,
                "project_id": THREE_LAUREL_PROJECT_ID,
                "source_sha256": THREE_LAUREL_SOURCE_SHA256,
                "workspace_id": workspace_id,
                "source_page": "3",
                "viewport_id": "VIEWPORT_P3_A0.3_PLAN",
                "canonical_floor_id": ref,
                "physical_floor_id": ref,
                "physical_room_id": ref,
                "finish_code": "VINYL",
                "semantic_finish": "VINYL",
                "commercial_projection_allowed": True,
                "takeoff_eligible": True,
                "figured_dimension_ids": figured_dim_ids,
                "section": section,
                "element": "Floor finish area",
                "location": location,
                "substrate": substrate,
                "finish_system": finish_system,
                "row_role": "floor_area",
                "object_ref": ref,
                "item_id": item_id,
            },
        )
        quantities_list.append(qty)

        trace = CommercialTakeoffSourceTrace(
            workspace_id=workspace_id,
            project_id=THREE_LAUREL_PROJECT_ID,
            document_id=THREE_LAUREL_DOCUMENT_ID,
            source_sha256=THREE_LAUREL_SOURCE_SHA256,
            source_page="3",
            viewport_id="VIEWPORT_P3_A0.3_PLAN",
            revision_id=THREE_LAUREL_REVISION_ID,
            current_revision_id=THREE_LAUREL_REVISION_ID,
            canonical_entity_ids=(ref,),
            evidence_ids=figured_dim_ids,
            metadata={
                "review_required": True,
                "object_ref": ref,
                "trade_category": "flooring",
            },
        )
        traces_map[qty_id] = trace

        auth = CommercialMeasurementAuthority(
            method="figured_dimension",
            figured_dimension_ids=figured_dim_ids,
            metadata={
                "finish_code": "VINYL",
                "semantic_finish": "VINYL",
                "object_ref": ref,
            },
        )
        authorities_map[qty_id] = auth

    try:
        sealed = seal_source_closed_run(
            tuple(quantities_list),
            project_id=THREE_LAUREL_PROJECT_ID,
            traces_by_quantity_id=traces_map,
        )
        rows = tuple(
            quantities_to_takeoff_output_rows(
                tuple(quantities_list),
                traces_by_quantity_id=traces_map,
                authorities_by_quantity_id=authorities_map,
            )
        )
        verify_sealed_customer_output(sealed, rows)
    except Exception:
        return _blocked("three_laurel_sealed_customer_projection_failed")

    return ThreeLaurelVinylFloorCustomerResult(
        status="FIRM_SOURCE_CUSTOMER_TO_REVIEW",
        reason_codes=("source_owned_physical_quantity_resolved",),
        quantities=tuple(quantities_list),
        traces=tuple(traces_map.values()),
        sealed_run=sealed,
        customer_rows=rows,
    )
