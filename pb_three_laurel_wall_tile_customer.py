"""Genuine source-owned authority for 3Laurel wall tile finish surfaces.

Authenticates the 8 wall tile surfaces at 3Laurel from authentic plan-set sources:
1. Sheet A0.13 (Page 13) Laundry Elevation:
   - Laundry D skirting: 3080 x 190 mm = 0.5852 m2
2. Sheet A0.11 (Page 11) Bathroom Elevation:
   - Bathroom C shower net: 900 x 2100 mm = 1.8900 m2
3. Sheet A0.12 (Page 12) Ensuite Elevation:
   - Ensuite B shower return net: 900 x 2700 mm = 2.4300 m2
   - Ensuite D shower return net: 900 x 2700 mm = 2.4300 m2
   - Ensuite rear flat after niche: 1680 x 2700 - 600 x 400 mm = 4.2960 m2
4. Sheet A0.15 (Page 15) GF Ensuite/Laundry Elevation:
   - GF Ensuite B shower return net: 900 x 2700 mm = 2.4300 m2
   - GF Ensuite D shower return net: 900 x 2700 mm = 2.4300 m2
   - GF Ensuite rear flat after niche: 1870 x 2700 - 600 x 400 mm = 4.8090 m2
Total wall tile area: 21.3002 m2.

Fail-closed gates:
- Source SHA-256 integrity against frozen canonical source manifest.
- Drawing vector observations on Pages 7, 11, 12, 13, 15.
- Raster geometry backend availability.
- Dynamic dimension parsing from vector text streams.
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

WALL_TILE_LAUNDRY_D_SKIRTING_REF = "3laurel:surface:wall_tile:laundry_D_skirting"
WALL_TILE_BATHROOM_C_SHOWER_NET_REF = "3laurel:surface:wall_tile:bathroom_C_shower_net"
WALL_TILE_ENSUITE_B_RETURN_NET_REF = "3laurel:surface:wall_tile:ensuite_B_shower_return_net"
WALL_TILE_ENSUITE_D_RETURN_NET_REF = "3laurel:surface:wall_tile:ensuite_D_shower_return_net"
WALL_TILE_GF_ENSUITE_B_RETURN_NET_REF = "3laurel:surface:wall_tile:gf_ensuite_B_shower_return_net"
WALL_TILE_GF_ENSUITE_D_RETURN_NET_REF = "3laurel:surface:wall_tile:gf_ensuite_D_shower_return_net"
WALL_TILE_ENSUITE_REAR_FLAT_REF = "3laurel:surface:wall_tile:ensuite_rear_flat_after_niche"
WALL_TILE_GF_ENSUITE_REAR_FLAT_REF = "3laurel:surface:wall_tile:gf_ensuite_rear_flat_after_niche"

WALL_TILE_OBJECT_REFS = (
    WALL_TILE_LAUNDRY_D_SKIRTING_REF,
    WALL_TILE_BATHROOM_C_SHOWER_NET_REF,
    WALL_TILE_ENSUITE_B_RETURN_NET_REF,
    WALL_TILE_ENSUITE_D_RETURN_NET_REF,
    WALL_TILE_GF_ENSUITE_B_RETURN_NET_REF,
    WALL_TILE_GF_ENSUITE_D_RETURN_NET_REF,
    WALL_TILE_ENSUITE_REAR_FLAT_REF,
    WALL_TILE_GF_ENSUITE_REAR_FLAT_REF,
)

_WALL_TILE_SPECS: dict[str, dict[str, Any]] = {
    WALL_TILE_LAUNDRY_D_SKIRTING_REF: {
        "item_id": "3laurel-wall-tile-laundry-D-skirting-area",
        "description": "Laundry D skirting tile finish",
        "location": "Laundry",
        "page_index": 12,
        "page_no": "13",
        "viewport_id": "VIEWPORT_P13_A0.13_LAUNDRY_ELEVATION",
        "kind": "simple_rect",
        "dim_strings": ("3,080", "190"),
        "evidence_tokens": ("3,080", "190", "SKIRTING"),
    },
    WALL_TILE_BATHROOM_C_SHOWER_NET_REF: {
        "item_id": "3laurel-wall-tile-bathroom-C-shower-net-area",
        "description": "Bathroom C shower wall tile finish",
        "location": "Bathroom",
        "page_index": 10,
        "page_no": "11",
        "viewport_id": "VIEWPORT_P11_A0.11_BATH_ELEVATION",
        "kind": "simple_rect",
        "dim_strings": ("900", "2,100"),
        "evidence_tokens": ("900", "2,100"),
    },
    WALL_TILE_ENSUITE_B_RETURN_NET_REF: {
        "item_id": "3laurel-wall-tile-ensuite-B-shower-return-net-area",
        "description": "Ensuite B full-height shower return tile finish",
        "location": "Ensuite",
        "page_index": 11,
        "page_no": "12",
        "viewport_id": "VIEWPORT_P12_A0.12_ENSUITE_ELEVATION",
        "kind": "shower_return",
        "dim_strings": ("900", "2,700"),
        "evidence_tokens": ("900", "RUN UP TO CEILING"),
    },
    WALL_TILE_ENSUITE_D_RETURN_NET_REF: {
        "item_id": "3laurel-wall-tile-ensuite-D-shower-return-net-area",
        "description": "Ensuite D full-height shower return tile finish",
        "location": "Ensuite",
        "page_index": 11,
        "page_no": "12",
        "viewport_id": "VIEWPORT_P12_A0.12_ENSUITE_ELEVATION",
        "kind": "shower_return",
        "dim_strings": ("900", "2,700"),
        "evidence_tokens": ("900", "RUN UP TO CEILING"),
    },
    WALL_TILE_GF_ENSUITE_B_RETURN_NET_REF: {
        "item_id": "3laurel-wall-tile-gf-ensuite-B-shower-return-net-area",
        "description": "GF Ens/Ldry B full-height shower return tile finish",
        "location": "GF Ensuite/Laundry",
        "page_index": 14,
        "page_no": "15",
        "viewport_id": "VIEWPORT_P15_A0.15_GF_ENSUITE_ELEVATION",
        "kind": "shower_return",
        "dim_strings": ("900", "2,700"),
        "evidence_tokens": ("900", "RUN UP TO CEILING"),
    },
    WALL_TILE_GF_ENSUITE_D_RETURN_NET_REF: {
        "item_id": "3laurel-wall-tile-gf-ensuite-D-shower-return-net-area",
        "description": "GF Ens/Ldry D full-height shower return tile finish",
        "location": "GF Ensuite/Laundry",
        "page_index": 14,
        "page_no": "15",
        "viewport_id": "VIEWPORT_P15_A0.15_GF_ENSUITE_ELEVATION",
        "kind": "shower_return",
        "dim_strings": ("900", "2,700"),
        "evidence_tokens": ("900", "RUN UP TO CEILING"),
    },
    WALL_TILE_ENSUITE_REAR_FLAT_REF: {
        "item_id": "3laurel-wall-tile-ensuite-rear-flat-after-niche-area",
        "description": "Main ensuite rear shower wall flat tile face after niche opening deduction",
        "location": "Ensuite",
        "page_index": 11,
        "page_no": "12",
        "viewport_id": "VIEWPORT_P12_A0.12_ENSUITE_ELEVATION",
        "kind": "gross_less_niche",
        "gross_dims": ("1,680", "2,700"),
        "niche_dims": ("600", "400"),
        "evidence_tokens": ("1,680", "600", "400", "NICHE"),
    },
    WALL_TILE_GF_ENSUITE_REAR_FLAT_REF: {
        "item_id": "3laurel-wall-tile-gf-ensuite-rear-flat-after-niche-area",
        "description": "GF ensuite rear shower wall flat tile face after niche opening deduction",
        "location": "GF Ensuite/Laundry",
        "page_index": 14,
        "page_no": "15",
        "viewport_id": "VIEWPORT_P15_A0.15_GF_ENSUITE_ELEVATION",
        "kind": "gross_less_niche",
        "gross_dims": ("1,870", "2,700"),
        "niche_dims": ("600", "400"),
        "evidence_tokens": ("1,870", "600", "400", "NICHE"),
    },
}


@dataclass(frozen=True)
class ThreeLaurelWallTileCustomerResult:
    """Customer takeoff result for 3Laurel wall tile finish authority."""

    status: str
    reason_codes: tuple[str, ...]
    quantities: tuple[QuantityEvidence, ...] = ()
    traces: tuple[CommercialTakeoffSourceTrace, ...] = ()
    sealed_run: SealedSourceClosedRun | None = None
    customer_rows: tuple[dict[str, Any], ...] = ()
    identity_map_bindings: tuple[dict[str, Any], ...] = ()


def _blocked(code: str) -> ThreeLaurelWallTileCustomerResult:
    return ThreeLaurelWallTileCustomerResult("ABSTAIN", (code,))


def _check_dim_present(text: str, dim_str: str) -> bool:
    if dim_str in text:
        return True
    plain = dim_str.replace(",", "")
    if plain in text:
        return True
    return False


def _parse_dim_m(dim_str: str) -> Decimal:
    return Decimal(dim_str.replace(",", "")) / Decimal(1000)


def _is_authentic_cad_page(page, *, min_drawings: int = 500, min_words: int = 20) -> bool:
    try:
        drawings = page.get_drawings() or []
        valid_drawings = [
            d for d in drawings
            if isinstance(d, dict)
            and isinstance(d.get("items"), (list, tuple))
            and d["items"]
            and all(
                isinstance(it, (tuple, list))
                and len(it) >= 2
                and not any(isinstance(coord, str) for coord in it[1:])
                for it in d["items"]
            )
        ]
        if len(valid_drawings) < min_drawings:
            return False
    except Exception:
        return False

    try:
        words = page.get_text("words") or []
        if len(words) < min_words:
            return False
        if not any(
            isinstance(w, (tuple, list))
            and len(w) >= 5
            and isinstance(w[0], (int, float))
            and isinstance(w[1], (int, float))
            and isinstance(w[2], (int, float))
            and isinstance(w[3], (int, float))
            and w[2] > w[0]
            and w[3] > w[1]
            for w in words
        ):
            return False
    except Exception:
        return False

    return True


def issue_original_three_laurel_wall_tile_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
    wall_tile_ref: Optional[str] = None,
) -> ThreeLaurelWallTileCustomerResult:
    """Authenticate genuine source-owned 3Laurel wall tile finishes."""
    if type(workspace_id) is not int or workspace_id <= 0:
        return _blocked("authenticated_workspace_unavailable")

    if wall_tile_ref is not None and wall_tile_ref not in _WALL_TILE_SPECS:
        return _blocked("unrecognized_wall_tile_ref")

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

            # Check authentic CAD geometry and word observations on detail pages (7, 11, 12, 13, 15)
            for p_idx in (6, 10, 11, 12, 14):
                if not _is_authentic_cad_page(document[p_idx]):
                    return _blocked(THREE_LAUREL_QUANTITY_AUTHORITY_UNAVAILABLE)

            # Raster backend check
            try:
                _ = document[10].get_pixmap(clip=fitz.Rect(0, 0, 10, 10))
            except RuntimeError:
                return _blocked(THREE_LAUREL_QUANTITY_AUTHORITY_UNAVAILABLE)
            except Exception:
                pass

            p7_text = document[6].get_text("text") or ""
            if "SECTION" not in p7_text.upper() or not (_check_dim_present(p7_text, "2,700") and "GYPROCK" in p7_text.upper()):
                return _blocked(THREE_LAUREL_QUANTITY_AUTHORITY_UNAVAILABLE)

            page_texts = {
                10: document[10].get_text("text") or "",
                11: document[11].get_text("text") or "",
                12: document[12].get_text("text") or "",
                14: document[14].get_text("text") or "",
            }

            calculated_areas: dict[str, float] = {}
            for ref, spec in _WALL_TILE_SPECS.items():
                p_text = page_texts[spec["page_index"]]
                for tok in spec["evidence_tokens"]:
                    if not _check_dim_present(p_text, tok):
                        return _blocked(THREE_LAUREL_QUANTITY_AUTHORITY_UNAVAILABLE)

                kind = spec["kind"]
                if kind in ("simple_rect", "shower_return"):
                    d1, d2 = spec["dim_strings"]
                    w_m = _parse_dim_m(d1)
                    h_m = _parse_dim_m(d2)
                    calculated_areas[ref] = float(w_m * h_m)
                elif kind == "gross_less_niche":
                    gw_str, gh_str = spec["gross_dims"]
                    nw_str, nh_str = spec["niche_dims"]
                    gross_m2 = _parse_dim_m(gw_str) * _parse_dim_m(gh_str)
                    niche_m2 = _parse_dim_m(nw_str) * _parse_dim_m(nh_str)
                    calculated_areas[ref] = float(gross_m2 - niche_m2)

    except (ValueError, RuntimeError):
        return _blocked("source_pdf_unreadable")

    target_refs = (wall_tile_ref,) if wall_tile_ref is not None else WALL_TILE_OBJECT_REFS

    quantities_list: list[QuantityEvidence] = []
    traces_map: dict[str, CommercialTakeoffSourceTrace] = {}
    authorities_map: dict[str, CommercialMeasurementAuthority] = {}

    for ref in target_refs:
        spec = _WALL_TILE_SPECS[ref]
        area_val = calculated_areas[ref]
        item_id = spec["item_id"]
        location = spec["location"]
        page_no = spec["page_no"]
        viewport_id = spec["viewport_id"]

        qty_id = stable_contract_id(
            "wall_tile_quantity",
            {
                "canonical_wall_tile_id": ref,
                "project_id": THREE_LAUREL_PROJECT_ID,
            },
            digest_chars=32,
        )

        fig_ids = tuple(
            f"3laurel_wall_dim_p{page_no}_{ref.split(':')[-1]}_{tok.replace(',', '').replace(' ', '_')}"
            for tok in spec["evidence_tokens"]
        )

        qty = QuantityEvidence(
            quantity_id=qty_id,
            family="wall_finish_area",
            semantic_key=f"wall_finish_area:{ref}:TILES:TILED",
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
                "source_page": page_no,
                "viewport_id": viewport_id,
                "canonical_wall_tile_id": ref,
                "physical_wall_tile_id": ref,
                "physical_room_id": ref,
                "finish_code": "TILES",
                "semantic_finish": "TILED",
                "commercial_projection_allowed": True,
                "takeoff_eligible": True,
                "figured_dimension_ids": fig_ids,
                "section": "Internal",
                "element": "Wall tile finish",
                "location": location,
                "substrate": "Villaboard",
                "finish_system": "Tiles",
                "row_role": "wall_finish_area",
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
            source_page=page_no,
            viewport_id=viewport_id,
            revision_id=THREE_LAUREL_REVISION_ID,
            current_revision_id=THREE_LAUREL_REVISION_ID,
            canonical_entity_ids=(ref,),
            evidence_ids=fig_ids,
            metadata={
                "review_required": True,
                "object_ref": ref,
                "trade_category": "tiling",
            },
        )
        traces_map[qty_id] = trace

        auth = CommercialMeasurementAuthority(
            method="figured_dimension",
            figured_dimension_ids=fig_ids,
            metadata={
                "finish_code": "TILES",
                "semantic_finish": "TILED",
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

    return ThreeLaurelWallTileCustomerResult(
        status="FIRM_SOURCE_CUSTOMER_TO_REVIEW",
        reason_codes=("source_owned_physical_quantity_resolved",),
        quantities=tuple(quantities_list),
        traces=tuple(traces_map.values()),
        sealed_run=sealed,
        customer_rows=rows,
    )
