"""Cross-check exact original door schedule with a PAINTED wall-ink gap.

This preserves original page-local door words and four-wall native evidence.
A scheduled leaf width, callout or geometrical ink gap NEVER by itself
authenticates a finished floor threshold or a constructed opening.
"""
from __future__ import annotations

import hashlib
import math
import re

from tools.diag_original_room_four_edge_source_ink_shadow import (
    audit_source_painted_enclosure_correspondence_shadow,
)
from tools.diag_gpt2_original_door_schedule_native_words_shadow import (
    census_original_door_schedule_native_source,
)


def audit_original_room_ink_door_schedule_gap_candidate(
    original_pdf_bytes: bytes, *, expected_sha256: str,
    floor_page_1_based: int, finish_page_1_based: int,
    original_side_pairs: dict[str, tuple[str, str]],
    source_translation_pdf_pts: tuple[float, float],
    door_schedule_page_1_based: int, door_schedule_native_block: int,
    source_door_code: str,
) -> dict:
    # No trust in caller-copied structural room, printed mark or schedule.
    # Recompute both original source candidates from immutable PDF bytes.
    ink = audit_source_painted_enclosure_correspondence_shadow(
        original_pdf_bytes,expected_sha256=expected_sha256,
        floor_page_1_based=floor_page_1_based,
        finish_page_1_based=finish_page_1_based,
        original_side_pairs=original_side_pairs,
        expected_translation_pdf_pts=source_translation_pdf_pts,
    )
    schedule = census_original_door_schedule_native_source(
        original_pdf_bytes,expected_sha256=expected_sha256,
        schedule_page_1_based=door_schedule_page_1_based,
        plan_page_1_based=floor_page_1_based,
        requested_door_code=source_door_code,
        schedule_native_block=door_schedule_native_block,
    )
    if schedule["status"] != "native_original_door_schedule_and_plan_words_only":
        return {
            "status":"original_room_door_gap_schedule_source_abstained",
            "first_unclosed_gate":"original_source_plan_door_word_missing",
            "new_firm_quantities":0,
        }
    raw_gap=ink["source_floor_painted_corner_evidence"][
        "original_source_top_virtual_door_gap_pdf_pts"
    ]
    if len(raw_gap)!=2:
        raise ValueError("source_original_virtual_door_gap_invalid")
    (ax,ay),(bx,by)=raw_gap
    if (not all(math.isfinite(v) for v in (ax,ay,bx,by))
            or ay!=by or ax>=bx):
        raise ValueError("original_source_virtual_gap_invalid")
    at_gap=[]
    elsewhere=[]
    for entry in schedule["all_original_plan_same_door_code_words"]:
        r=entry["original_word_bbox_pdf_pts"]
        if (type(r) not in (tuple,list) or len(r)!=4
                or any(type(v) not in (float,int) or not math.isfinite(v)
                       for v in r)):
            raise ValueError("original_door_word_source_bbox_invalid")
        x0,y0,x1,y1=map(float,r)
        # The mark's own original PRINTED bbox must lie across the wall ink
        # gap: a nearby label on a different opening is never chosen.
        if ax<=x0 and x1<=bx and y0<=ay<=y1:
            at_gap.append(entry)
        else:
            elsewhere.append(entry)
    candidate=len(at_gap)==1
    return {
        "status":(
            "one_original_room_door_word_on_painted_gap_candidate"
            if candidate else
            "original_room_door_gap_schedule_source_abstained"
        ),
        "first_unclosed_gate":(
            "source_physical_door_host_threshold_and_width_unproven"
            if candidate else
            "original_door_word_not_unique_on_this_ink_gap"
        ),
        "original_source_sha256":expected_sha256,
        "original_door_code_untrusted":source_door_code,
        "original_painted_wall_source":ink,
        "original_door_schedule_source":schedule,
        "source_door_gap_original_pdf_pts":tuple(tuple(p) for p in raw_gap),
        "source_original_plan_door_word_candidates_crossing_gap":tuple(at_gap),
        "source_original_same_code_door_words_elsewhere":tuple(elsewhere),
        "source_door_schedule_leaf_width_not_floor_threshold_width":True,
        "source_door_leaf_to_wall_gap_metric_correspondence_proven":False,
        "source_physically_constructed_door_or_host_authenticated":False,
        "source_finished_door_threshold_authenticated":False,
        "source_original_finish_floor_area_issued":False,
        "new_firm_quantities":0,
    }
