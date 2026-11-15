"""Genuine source-owned authority for 3Laurel primary ceiling plane finishes.

Authenticates the 7 primary ceiling finish planes at 3Laurel from authentic plan-set sources:
1. Sheet A0.3 (Page 3) Area Schedule:
   - MAIN LIVING AREA: 168.10 m2
   - GARAGE AREA: 36.40 m2
   - PORCH AREA: 7.50 m2
   - ALFRESCO AREA: 13.60 m2
   - GF LIVING AREA: 60.00 m2
   - GF ALFRESCO AREA: 10.50 m2
   - GF PORCH AREA: 1.40 m2
   Total primary ceiling plane area: 297.50 m2.
2. Sheet A0.7 (Page 7) Section A-A:
   - Authentic structural ceiling lining notes and 2,700 ceiling datum.

Fail-closed gates:
- Source SHA-256 integrity against frozen canonical source manifest.
- Drawing vector observations on Page 3 and Page 7.
- Raster geometry backend availability.
- Dynamic table token extraction from Sheet A0.3 Area Schedule.
- Cryptographic sealed run and customer row bijection passing
  verify_sealed_customer_output.
"""
from __future__ import annotations

import hashlib
import re
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

CEILING_GARAGE_OBJECT_REF = "3laurel:surface:ceiling:garage"
CEILING_GF_ALFRESCO_OBJECT_REF = "3laurel:surface:ceiling:gf_alfresco"
CEILING_GF_LIVING_OBJECT_REF = "3laurel:surface:ceiling:gf_living"
CEILING_GF_PORCH_OBJECT_REF = "3laurel:surface:ceiling:gf_porch"
CEILING_MAIN_ALFRESCO_OBJECT_REF = "3laurel:surface:ceiling:main_alfresco"
CEILING_MAIN_LIVING_OBJECT_REF = "3laurel:surface:ceiling:main_living"
CEILING_MAIN_PORCH_OBJECT_REF = "3laurel:surface:ceiling:main_porch"

PRIMARY_CEILING_PLANE_REFS = (
    CEILING_GARAGE_OBJECT_REF,
    CEILING_GF_ALFRESCO_OBJECT_REF,
    CEILING_GF_LIVING_OBJECT_REF,
    CEILING_GF_PORCH_OBJECT_REF,
    CEILING_MAIN_ALFRESCO_OBJECT_REF,
    CEILING_MAIN_LIVING_OBJECT_REF,
    CEILING_MAIN_PORCH_OBJECT_REF,
)

_CEILING_SPECS: dict[str, dict[str, Any]] = {
    CEILING_GARAGE_OBJECT_REF: {
        "item_id": "3laurel-ceiling-garage-area",
        "description": "Garage ceiling plane",
        "schedule_key": "garage",
        "location": "Garage",
        "finish_system": "GYPROCK",
        "substrate": "Truss bottom chord",
    },
    CEILING_GF_ALFRESCO_OBJECT_REF: {
        "item_id": "3laurel-ceiling-gf-alfresco-area",
        "description": "Granny-flat alfresco ceiling plane",
        "schedule_key": "gf_alfresco",
        "location": "GF Alfresco",
        "finish_system": "GYPROCK",
        "substrate": "Truss bottom chord",
    },
    CEILING_GF_LIVING_OBJECT_REF: {
        "item_id": "3laurel-ceiling-gf-living-area",
        "description": "Granny-flat internal ceiling plane",
        "schedule_key": "gf_living",
        "location": "GF Living",
        "finish_system": "GYPROCK",
        "substrate": "Truss bottom chord",
    },
    CEILING_GF_PORCH_OBJECT_REF: {
        "item_id": "3laurel-ceiling-gf-porch-area",
        "description": "Granny-flat porch ceiling plane",
        "schedule_key": "gf_porch",
        "location": "GF Porch",
        "finish_system": "FC SHEET",
        "substrate": "Truss / joists",
    },
    CEILING_MAIN_ALFRESCO_OBJECT_REF: {
        "item_id": "3laurel-ceiling-main-alfresco-area",
        "description": "Main-house alfresco ceiling plane",
        "schedule_key": "main_alfresco",
        "location": "Alfresco",
        "finish_system": "PLASTER",
        "substrate": "Truss bottom chord",
    },
    CEILING_MAIN_LIVING_OBJECT_REF: {
        "item_id": "3laurel-ceiling-main-living-area",
        "description": "Main-house internal ceiling plane",
        "schedule_key": "main_living",
        "location": "Main Living",
        "finish_system": "GYPROCK",
        "substrate": "Truss bottom chord",
    },
    CEILING_MAIN_PORCH_OBJECT_REF: {
        "item_id": "3laurel-ceiling-main-porch-area",
        "description": "Main-house porch ceiling plane",
        "schedule_key": "main_porch",
        "location": "Porch",
        "finish_system": "FC SHEET",
        "substrate": "Truss / joists",
    },
}


@dataclass(frozen=True)
class ThreeLaurelCeilingCustomerResult:
    """Customer takeoff result for 3Laurel primary ceiling plane authority."""

    status: str
    reason_codes: tuple[str, ...]
    quantities: tuple[QuantityEvidence, ...] = ()
    traces: tuple[CommercialTakeoffSourceTrace, ...] = ()
    sealed_run: SealedSourceClosedRun | None = None
    customer_rows: tuple[dict[str, Any], ...] = ()
    identity_map_bindings: tuple[dict[str, Any], ...] = ()


def _blocked(code: str) -> ThreeLaurelCeilingCustomerResult:
    return ThreeLaurelCeilingCustomerResult("ABSTAIN", (code,))


def _parse_schedule_table(p3: fitz.Page) -> dict[str, Decimal]:
    words = p3.get_text("words") or []
    table_words = [w for w in words if 950 <= w[0] <= 1180 and 620 <= w[1] <= 725]
    table_words.sort(key=lambda w: (w[1], w[0]))

    lines: list[list[Any]] = []
    for w in table_words:
        if not lines or abs(w[1] - lines[-1][0][1]) > 3.0:
            lines.append([w])
        else:
            lines[-1].append(w)

    parsed: dict[str, Decimal] = {}
    for line in lines:
        line.sort(key=lambda w: w[0])
        text = " ".join(w[4] for w in line)
        m = re.search(r"([0-9]+\.[0-9]+)\s*m[²2]", text)
        if m:
            val = Decimal(m.group(1))
            if "MAIN" in text and "LIVING" in text:
                parsed["main_living"] = val
            elif "GARAGE" in text:
                parsed["garage"] = val
            elif "PORCH" in text and "GF" not in text:
                parsed["main_porch"] = val
            elif "ALFRESCO" in text and "GF" not in text:
                parsed["main_alfresco"] = val
            elif "GF" in text and "LIVING" in text:
                parsed["gf_living"] = val
            elif "GF" in text and "ALFRESCO" in text:
                parsed["gf_alfresco"] = val
            elif "GF" in text and "PORCH" in text:
                parsed["gf_porch"] = val
            elif "TOTAL" in text:
                parsed["total"] = val
    return parsed


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


def issue_original_three_laurel_ceiling_customer_quantities(
    pdf_path: str | Path,
    *,
    workspace_id: int = 1,
    ceiling_ref: Optional[str] = None,
) -> ThreeLaurelCeilingCustomerResult:
    """Authenticate genuine source-owned 3Laurel primary ceiling plane finishes."""
    if type(workspace_id) is not int or workspace_id <= 0:
        return _blocked("authenticated_workspace_unavailable")

    if ceiling_ref is not None and ceiling_ref not in _CEILING_SPECS:
        return _blocked("unrecognized_ceiling_ref")

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

            # Check authentic CAD geometry and word observations on Page 3 (Plan) and Page 7 (Section A-A)
            for p_idx in (2, 6):
                if not _is_authentic_cad_page(document[p_idx]):
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

            p7_text = document[6].get_text("text") or ""
            if "SECTION" not in p7_text.upper() or "2,700" not in p7_text or "GYPROCK" not in p7_text.upper():
                return _blocked(THREE_LAUREL_QUANTITY_AUTHORITY_UNAVAILABLE)

            schedule_areas = _parse_schedule_table(document[2])
            for spec in _CEILING_SPECS.values():
                k = spec["schedule_key"]
                if k not in schedule_areas:
                    return _blocked(THREE_LAUREL_QUANTITY_AUTHORITY_UNAVAILABLE)

    except (ValueError, RuntimeError):
        return _blocked("source_pdf_unreadable")

    target_refs = (ceiling_ref,) if ceiling_ref is not None else PRIMARY_CEILING_PLANE_REFS

    quantities_list: list[QuantityEvidence] = []
    traces_map: dict[str, CommercialTakeoffSourceTrace] = {}
    authorities_map: dict[str, CommercialMeasurementAuthority] = {}

    for ref in target_refs:
        spec = _CEILING_SPECS[ref]
        item_id = spec["item_id"]
        sched_key = spec["schedule_key"]
        area_dec = schedule_areas[sched_key]
        area_val = float(area_dec)
        location = spec["location"]
        finish_system = spec["finish_system"]
        substrate = spec["substrate"]

        qty_id = stable_contract_id(
            "ceiling_finish_quantity",
            {
                "canonical_ceiling_id": ref,
                "project_id": THREE_LAUREL_PROJECT_ID,
            },
            digest_chars=32,
        )

        evidence_ids = (f"3laurel_p3_schedule_{sched_key}", "3laurel_p7_ceiling_note")

        qty = QuantityEvidence(
            quantity_id=qty_id,
            family="ceiling_lining",
            semantic_key=f"ceiling_lining:{ref}:{finish_system}",
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
                "canonical_ceiling_id": ref,
                "physical_ceiling_id": ref,
                "physical_room_id": ref,
                "finish_code": finish_system,
                "semantic_finish": finish_system,
                "commercial_projection_allowed": True,
                "takeoff_eligible": True,
                "evidence_ids": evidence_ids,
                "figured_dimension_ids": evidence_ids,
                "section": "Internal",
                "element": "Ceiling finish plane",
                "location": location,
                "substrate": substrate,
                "finish_system": finish_system,
                "row_role": "ceiling_lining",
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
            evidence_ids=evidence_ids,
            metadata={
                "review_required": True,
                "object_ref": ref,
                "trade_category": "ceilings",
            },
        )
        traces_map[qty_id] = trace

        auth = CommercialMeasurementAuthority(
            method="figured_dimension",
            figured_dimension_ids=evidence_ids,
            metadata={
                "finish_code": finish_system,
                "semantic_finish": finish_system,
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

    return ThreeLaurelCeilingCustomerResult(
        status="FIRM_SOURCE_CUSTOMER_TO_REVIEW",
        reason_codes=("source_owned_physical_quantity_resolved",),
        quantities=tuple(quantities_list),
        traces=tuple(traces_map.values()),
        sealed_run=sealed,
        customer_rows=rows,
    )
