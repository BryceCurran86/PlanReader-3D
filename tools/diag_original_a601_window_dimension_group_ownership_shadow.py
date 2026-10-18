"""Original A601 grouped-window source dimension candidates, never size authority.

One printed elevation caption may name multiple window codes. A printed
dimension in the common drawn area is not automatically the width or height
of every named frame. The original numeric text owners and all competitors
remain available for later source stroke/extension-line/frame host proofs.
"""
from __future__ import annotations
import math
import re
from collections import defaultdict
from tools.diag_original_window_elevation_title_lineage_shadow import (
    audit_original_window_elevation_title_memberships,
)

_NUM=re.compile(r"^[1-9][0-9]{1,4}$")


def _box(value):
    if (type(value) is not tuple or len(value)!=4
            or any(type(x) not in (float,int) or not math.isfinite(x) for x in value)
            or value[0]>=value[2] or value[1]>=value[3]):
        raise ValueError("original_independent_elevation_dimension_scope_required")
    return value


def audit_source_window_figure_competitors(
    plan_page, elevation_page, *,
    original_window_codes:tuple[str,...],
    group_scopes:dict[tuple[str,...],tuple[float,float,float,float]],
    max_numeric_tokens=5000,
):
    if type(group_scopes) is not dict or not group_scopes:
        raise ValueError("explicit_title_group_scopes_required")
    original=audit_original_window_elevation_title_memberships(
        plan_page,elevation_page,expected_source_codes=original_window_codes)
    titles=original["all_original_elevation_title_groups"]
    keys={tuple(t["original_window_codes_in_same_title_block"]) for t in titles}
    if keys != set(group_scopes):
        raise ValueError("all_printed_original_title_groups_must_be_scoped")
    bounds={k:_box(v) for k,v in group_scopes.items()}
    for a in bounds:
        for b in bounds:
            if a>=b:continue
            v,w=bounds[a],bounds[b]
            if max(v[0],w[0])<min(v[2],w[2]) and max(v[1],w[1])<min(v[3],w[3]):
                raise ValueError("overlapping_independent_elevation_dimension_scopes")
    number_rows=[]
    for token in elevation_page.get_text("words"):
        if len(token)<8 or not _NUM.fullmatch(str(token[4])):
            continue
        x0,y0,x1,y1=(float(z) for z in token[:4])
        owners=[name for name,(l,t,r,b) in bounds.items()
                if l<=x0 and y0>=t and x1<=r and y1<=b]
        if len(number_rows)>=max_numeric_tokens:
            return {"status":"number_universe_cap_exceeded",
                    "source_numeric_universe_complete":False,
                    "new_firm_quantities":0}
        number_rows.append({
            "original_numeric_literal_untrusted":str(token[4]),
            "original_source_word_address":[int(z) for z in token[5:8]],
            "original_source_bbox_pdf_pts":[x0,y0,x1,y1],
            "possible_caption_groups":[list(x) for x in owners],
            "figured_dimension_terminal_witness_proven":False,
            "frame_axis_or_unique_window_owner_proven":False,
        })
    # Retain every possible source number and every group independently.
    # Do not let a common W03,W04,W05 title mint three frame dimensions.
    return {
        "status":"original_grouped_window_numeric_evidence_only",
        "original_grouped_elevation_title_receipts":titles,
        "numeric_original_source_candidates":number_rows,
        "source_window_code_candidates":original["source_plan_to_elevation_named_code_candidates"],
        "all_caption_groups_explicitly_scoped":True,
        "physical_window_frame_universe_complete":False,
        "source_frame_width_height_axes_proven":False,
        "independent_original_door_window_host_bindings":0,
        "new_window_counts":0,
        "new_window_metric_areas":0,
        "new_firm_quantities":0,
    }
