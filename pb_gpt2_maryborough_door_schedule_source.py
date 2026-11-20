"""Original Maryborough A110/A600 *source-word* door schedule correspondence.

This is an upstream source-attestation reader, not an opening/threshold/metric
issuer. No schedule row or plan callout alone establishes installed door kind,
host, frame, opening area, threshold or any commercial quantity.

A600's 'WC & SHOWER SINGLE SWING' native text shares one line: the native
' SHOWER' word straddles the existing room/type Y separator by 0.1 PDF pt.
Resolve the printed room and leaf-type suffix by source token sequence inside
one uniquely anchored schedule row rather than by splitting that native word.
"""
from __future__ import annotations

import hashlib
import math
import re
from collections.abc import Sequence
from typing import Any

import fitz

from pb_source_cross_view_floor_correspondence_shadow import (
    _authenticate_d15_door_schedule_row,
)
from pb_maryborough_customer_authority import MARYBOROUGH_SOURCE_SHA256

_CODE = re.compile(r"D[0-9]{2}")
_SOURCE_ONLY = "source_schedule_and_plan_words_only"


def _word(word: Sequence[Any]) -> dict[str, Any] | None:
    """Require a distinct PDF-native address, valid box and textual token."""
    try:
        if len(word) < 8 or any(type(x) is not int or x < 0 for x in word[5:8]):
            return None
        box = tuple(float(v) for v in word[:4])
        token = str(word[4]).strip().upper()
        if (not token or len(token) > 128 or not all(math.isfinite(v) for v in box)
                or box[2] <= box[0] or box[3] <= box[1]):
            return None
        return {"bbox": box, "text": token, "address": tuple(word[5:8])}
    except (TypeError, ValueError, OverflowError):
        return None


def census_native_a600_door_words(
    schedule_words: Sequence[Sequence[Any]],
    plan_words: Sequence[Sequence[Any]],
    requested_codes: tuple[str, ...],
) -> dict[str, dict[str, Any]]:
    """Read exact source rows and plan marks, without physical-door promotion.

    The caller must independently authenticate PDF SHA and page identity.
    All returned fields are noncommercial review witnesses, not FIRM facts.
    """
    if (type(requested_codes) is not tuple or not requested_codes
            or len(requested_codes) > 24
            or any(type(c) is not str or not _CODE.fullmatch(c) for c in requested_codes)
            or len(set(requested_codes)) != len(requested_codes)):
        raise ValueError("unique_requested_door_codes_required")
    if len(schedule_words) > 100000 or len(plan_words) > 100000:
        raise ValueError("source_word_bound_exceeded")
    schedules = [_word(w) for w in schedule_words]
    plans = [_word(w) for w in plan_words]
    if any(w is None for w in schedules) or any(w is None for w in plans):
        raise ValueError("malformed_native_source_word_universe")
    if len({w["address"] for w in schedules}) != len(schedules):
        raise ValueError("duplicate_native_schedule_word_address")
    if len({w["address"] for w in plans}) != len(plans):
        raise ValueError("duplicate_native_plan_word_address")

    def abstain(reason: str) -> dict[str, Any]:
        return {
            "status": "ABSTAIN", "first_failure": reason,
            "source_physical_door_authenticated": False,
            "source_doorway_threshold_authenticated": False,
            "measurement_authorized": False, "new_firm_quantities": 0,
        }

    by_block: dict[int, list[dict[str, Any]]] = {}
    for row in schedules:
        by_block.setdefault(row["address"][0], []).append(row)
    out: dict[str, dict[str, Any]] = {}
    for code in requested_codes:
        occurrences = [w for w in schedules if w["text"] == code
                       and w["bbox"][0] >= 970.0
                       and 2270.0 <= w["bbox"][1] <= 2305.0]
        if len(occurrences) != 1:
            out[code] = abstain("original_a600_unique_structured_row_missing")
            continue
        leader = occurrences[0]
        block = sorted(by_block[leader["address"][0]],
                       key=lambda r: (-r["bbox"][1], r["address"]))
        col_no = [w for w in block if 2270.0 <= w["bbox"][1] <= 2305.0]
        if (len(col_no) != 1 or col_no[0]["text"] != code
                or col_no[0]["address"][1:] != (0, 0)
                or max(w["bbox"][2] for w in block) - min(w["bbox"][0] for w in block) > 25.0):
            out[code] = abstain("original_a600_native_row_topology_conflict")
            continue
        # The original print layout may put the final room word across the
        # hardcoded 2200pt boundary. The source words themselves remain intact.
        room_and_kind = [w["text"] for w in block
                         if 2120.0 <= w["bbox"][1] < 2270.0]
        if (len(room_and_kind) < 3 or room_and_kind[-2:] != ["SINGLE", "SWING"]
                or any(token in ("SINGLE", "SWING") for token in room_and_kind[:-2])):
            out[code] = abstain("original_a600_room_or_leaf_kind_ambiguous")
            continue
        room_tokens = room_and_kind[:-2]
        if any(not re.fullmatch(r"[A-Z0-9&'()/.-]+", tok) for tok in room_tokens):
            out[code] = abstain("original_a600_room_label_malformed")
            continue
        numbers = []
        for lo, hi in ((2035.0, 2080.0), (1990.0, 2035.0), (1930.0, 1990.0)):
            columns = [w for w in block if lo <= w["bbox"][1] < hi]
            if len(columns) != 1 or not re.fullmatch(r"[0-9]{2,4}", columns[0]["text"]):
                break
            numbers.append(int(columns[0]["text"]))
        if (len(numbers) != 3 or not 100 <= numbers[0] <= 3000
                or not 100 <= numbers[1] <= 5000 or not 1 <= numbers[2] <= 250):
            out[code] = abstain("original_a600_numeric_columns_unproven")
            continue
        marked = [w for w in plans if w["text"] == code]
        if len(marked) != 1:
            out[code] = abstain("original_a110_door_callout_missing_or_ambiguous")
            continue
        out[code] = {
            "status": _SOURCE_ONLY,
            "source_schedule_word_address": leader["address"],
            "source_plan_word_address": marked[0]["address"],
            "source_schedule_native_block": leader["address"][0],
            "source_room_name_printed": " ".join(room_tokens),
            "source_leaf_type_printed": "SINGLE SWING",
            "source_scheduled_width_mm_printed": numbers[0],
            "source_scheduled_height_mm_printed": numbers[1],
            "source_scheduled_thickness_mm_printed": numbers[2],
            "source_physical_door_authenticated": False,
            "source_doorway_threshold_authenticated": False,
            "measurement_authorized": False,
            "new_firm_quantities": 0,
        }
    return out


def audit_original_maryborough_door_schedule(
    original_pdf_bytes: bytes,
    *,
    expected_sha256: str,
    plan_page_1_based: int = 7,
    schedule_page_1_based: int = 28,
    requested_codes: tuple[str, ...] = ("D07", "D08", "D13", "D14", "D15"),
) -> dict[str, Any]:
    """SHA-verify the original PDF, then inspect both actual source pages."""
    if (type(original_pdf_bytes) is not bytes or type(expected_sha256) is not str
            or not re.fullmatch(r"[0-9a-f]{64}", expected_sha256)
            or expected_sha256 != MARYBOROUGH_SOURCE_SHA256
            or hashlib.sha256(original_pdf_bytes).hexdigest() != expected_sha256):
        raise ValueError("original_maryborough_source_sha256_required")
    if (type(plan_page_1_based) is not int or plan_page_1_based != 7
            or type(schedule_page_1_based) is not int or schedule_page_1_based != 28):
        raise ValueError("original_a110_a600_page_scope_required")
    with fitz.open(stream=original_pdf_bytes, filetype="pdf") as pdf:
        if pdf.page_count != 31:
            raise ValueError("original_maryborough_31_page_revision_required")
        sched = pdf[27].get_text("words", sort=False)
        plan = pdf[6].get_text("words", sort=False)
        # Existing physical/floor authority's independent positive D13
        # source-table gate authenticates the A600 header and column scope.
        if _authenticate_d15_door_schedule_row(sched, "D13", "PWD") is None:
            return {
                "status": "ABSTAIN", "first_failure": "a600_schedule_identity_not_authenticated",
                "source_sha256": expected_sha256, "source_door_receipts": {},
                "new_firm_quantities": 0,
            }
        rows = census_native_a600_door_words(sched, plan, requested_codes)
    return {
        "status": "source_only_original_schedule_review",
        "source_sha256": expected_sha256,
        "source_plan_page_1_based": plan_page_1_based,
        "source_schedule_page_1_based": schedule_page_1_based,
        "source_door_receipts": rows,
        "source_physical_door_authenticated": False,
        "measurement_authorized": False,
        "new_firm_quantities": 0,
    }
