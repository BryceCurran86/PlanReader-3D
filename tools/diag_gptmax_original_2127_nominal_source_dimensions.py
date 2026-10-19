"""Independent original Lot16 2127 compact mark dimension *source*, no area grant.

The floor-plan HHWW compact callout can describe height and width.  A
source-native mark and its nominal product is never a physical opening,
canonical structural host, frame, deduction, signed quantity or V2 match.
"""
from __future__ import annotations

from hashlib import sha256
import math

import fitz

from pb_source_plan_opening_callout import (
    extract_source_plan_opening_callouts,
)
from tools.diag_gptmax_original_2127_crossview_native import (
    LOT16_ORIGINAL_SHA, original_2127_crossview_receipt,
)


def select_unpublished_stacker_2127_callout(
    callouts, *, source_sha256: str,
    source_plan_bbox_pdf_pt: tuple[float, float, float, float],
) -> dict:
    """Bind the exact native p3 *text* mark to one abstained source callout."""
    candidates = [
        row for row in callouts
        if row.compact_code == "2127"
        and row.descriptor == "STACKER"
    ]
    if len(candidates) != 1:
        raise ValueError("exact one original 2127 STACKER callout required")
    record = candidates[0]
    if (record.source_sha256 != source_sha256
            or type(record.source_page) is not int
            or record.source_page != 3
            or record.raw_callout != "2127 STACKER"
            or record.opening_kind != "door"
            or record.trade_category != "doors"
            or type(source_plan_bbox_pdf_pt) not in (tuple, list)
            or len(source_plan_bbox_pdf_pt) != 4
            or any(type(value) not in (int, float) or not math.isfinite(value)
                   for value in source_plan_bbox_pdf_pt)
            or tuple(record.bbox) != tuple(
                round(float(v), 6) for v in source_plan_bbox_pdf_pt
            )):
        raise ValueError("original compact callout/native text binding conflict")
    evidence = record.quantity_evidence
    if (evidence.status != "abstained"
            or evidence.value is not None
            or evidence.family != "opening_area"
            or evidence.unit != "m2"
            or len(record.evidence_ids) != 1
            or not record.evidence_ids[0]
            or record.width_mm <= 0
            or record.height_mm <= 0
            or not all(math.isfinite(x) for x in (
                record.width_mm, record.height_mm, record.area_m2))
            or not math.isclose(record.area_m2,
                                record.width_mm * record.height_mm / 1_000_000,
                                rel_tol=0, abs_tol=1e-9)):
        raise ValueError("source compact dimension evidence is not safely abstained")
    return {
        "status": "original_2127_compact_size_source_only",
        "source_sha256": source_sha256,
        "source_page_id": "3",
        "source_plan_callout_id": record.opening_id,
        "source_plan_evidence_ids": list(record.evidence_ids),
        "original_plan_mark_bbox_pdf_pt": list(record.bbox),
        "source_compact_code": record.compact_code,
        "source_descriptor": record.descriptor,
        "source_opening_kind_lexical_only": record.opening_kind,
        "source_nominal_width_mm": record.width_mm,
        "source_nominal_height_mm": record.height_mm,
        "source_arithmetic_area_candidate_m2": record.area_m2,
        "underlying_source_quantity_status": evidence.status,
        "underlying_source_quantity_value": evidence.value,
        "physical_cross_page_instance_binding_proven": False,
        "unique_structural_host_proven": False,
        "connected_whole_wall_frame_proven": False,
        "independent_measured_opening_area_proven": False,
        "source_quantity_publication_granted": False,
        "customer_or_frozen_score_granted": False,
        "new_firm_quantities": 0,
    }


def original_2127_stacker_nominal_dimension_receipt(original_pdf: bytes) -> dict:
    """Recompute both original text pages and page-3 callout from one SHA."""
    if type(original_pdf) is not bytes or sha256(original_pdf).hexdigest() != LOT16_ORIGINAL_SHA:
        raise ValueError("exact original Lot16 source required")
    crossview = original_2127_crossview_receipt(original_pdf)
    with fitz.open(stream=original_pdf, filetype="pdf") as pdf:
        plan_calls = extract_source_plan_opening_callouts(
            pdf[2], source_sha256=LOT16_ORIGINAL_SHA, source_page=3,
        )
    plan_marks = crossview["native_marks"]
    if (len(plan_marks) != 2
            or [item["page_number"] for item in plan_marks] != [3, 5]):
        raise ValueError("original 2127 plan/elevation source scope unavailable")
    result = select_unpublished_stacker_2127_callout(
        plan_calls, source_sha256=LOT16_ORIGINAL_SHA,
        source_plan_bbox_pdf_pt=tuple(plan_marks[0]["bbox_pdf_pt"]),
    )
    result["source_native_crossview_label_receipt"] = crossview
    return result
