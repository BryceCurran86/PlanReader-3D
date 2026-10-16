"""Original window elevation title-group source lineage (read-only).

A grouped original elevation for W03/W04/W05 is one drawing view, NOT three
separately authenticated frames or a physical count. This audit joins only
the original printed code/name universe across *different* source pages;
actual opening equivalence requires geometric host/frame, figured dimensions,
wall topology and source-issued visibility.

No nearest caption, numeric dimensions, inferred count=1, title-block scale,
or expected frozen holdout values grant quantity.
"""
from __future__ import annotations

from collections import defaultdict
import re

_CODE=re.compile(r"^W[0-9]{2}$")
_NUMBER=re.compile(r"^[1-9][0-9]{1,4}$")


def _native_word_rows(page):
    out=[]
    for w in page.get_text("words"):
        if len(w)<8:continue
        out.append({
            "original_native_word_address":[int(x) for x in w[5:8]],
            "source_pdf_literal_untrusted":str(w[4]),
            "original_bbox_pdf_pts":[float(x) for x in w[:4]],
            "source_glyph_clip_paint_issuer_authenticated":False,
        })
    return out


def audit_original_window_elevation_title_memberships(
    plan_page, elevation_page, *, expected_source_codes:tuple[str,...],
):
    if (type(expected_source_codes) is not tuple or not expected_source_codes
            or len(set(expected_source_codes))!=len(expected_source_codes)
            or any(type(x) is not str or not _CODE.fullmatch(x)
                   for x in expected_source_codes)):
        raise ValueError("source_window_code_universe_must_be_explicit_distinct")
    code_set=set(expected_source_codes)
    plan=_native_word_rows(plan_page)
    elevation=_native_word_rows(elevation_page)
    grouped=defaultdict(list)
    for row in elevation:
        grouped[row["original_native_word_address"][0]].append(row)
    titles=[]
    for block,words in sorted(grouped.items()):
        literal=[w["source_pdf_literal_untrusted"] for w in words]
        if "ELEVATION" not in literal:
            continue
        code_words=[
            w for w in words
            if _CODE.fullmatch(w["source_pdf_literal_untrusted"].rstrip(","))
            and w["source_pdf_literal_untrusted"].rstrip(",") in code_set
        ]
        if not code_words:
            continue
        codes=tuple(w["source_pdf_literal_untrusted"].rstrip(",")
                    for w in code_words)
        titles.append({
            "original_source_title_block_id":block,
            "original_source_title_words":words,
            "original_window_codes_in_same_title_block":list(codes),
            "all_window_codes_distinct_within_title":len(set(codes))==len(codes),
            "original_title_contains_elevation_role_word":True,
            "source_title_group_represents_one_elevation_view":True,
            "original_source_title_word_ids":[
                w["original_native_word_address"] for w in words
            ],
            "source_named_view_or_physical_window_authenticated":False,
        })

    plan_by_code=defaultdict(list)
    for row in plan:
        code=row["source_pdf_literal_untrusted"].rstrip(",")
        if code in code_set and _CODE.fullmatch(code):
            plan_by_code[code].append(row)
    title_by_code=defaultdict(list)
    for row in titles:
        for code in row["original_window_codes_in_same_title_block"]:
            title_by_code[code].append(row)

    memberships=[]
    for code in sorted(code_set):
        plans=plan_by_code.get(code,[])
        groups=title_by_code.get(code,[])
        structurally_unambiguous=(
            len(plans)==1 and len(groups)==1
            and groups[0]["all_window_codes_distinct_within_title"]
        )
        memberships.append({
            "original_window_code_literal_untrusted":code,
            "original_plan_tag_word_candidates":plans,
            "original_elevation_title_group_candidates":groups,
            "one_source_plan_label_and_one_elevation_group_candidate_only":
                structurally_unambiguous,
            "first_remaining_gate":(
                "trusted_text_source_then_frame_dims_and_original_host"
                if structurally_unambiguous
                else "source_plan_tag_or_elevation_title_conflicting"
            ),
            "physical_opening_identity_authenticated":False,
            "opening_count_complete":False,
            "figured_elevation_width_and_height_authenticated":False,
            "default_one_window_count_forbidden":True,
            "source_window_m2_granted":False,
        })
    source_numeric=[
        w for w in elevation
        if _NUMBER.fullmatch(w["source_pdf_literal_untrusted"])
    ]
    return {
        "status":"original_source_window_title_groups_candidate_only",
        "all_original_elevation_title_groups":titles,
        "source_plan_to_elevation_named_code_candidates":memberships,
        "original_elevation_numeric_words_not_dimensions":source_numeric,
        "native_source_title_or_count_issuer_authenticated":False,
        "new_authentic_window_frames":0,
        "new_eligible_window_counts":0,
        "new_window_areas_m2":0,
        "new_customer_quantities":0,
    }
