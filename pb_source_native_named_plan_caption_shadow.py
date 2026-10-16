"""Source-native local named-plan caption *candidates* on mixed-view sheets.

The active F07 viewport title grammar is deliberately conservative, but does
not currently nominate local captions such as "PROP. PWD PLAN" on pages whose
sheet title is INTERNAL ELEVATIONS. This read-only census keeps the original
line/block/word addresses; it does not classify a complete physical viewport,
manufacture a frame, infer sheet identity or publish a quantity.

Text/spatial hints can only nominate an independently source-bounded view,
never prove one. The default production viewport reader is unchanged.
"""
from __future__ import annotations

import math
import re
from typing import Any

# Positive exact native local caption ONLY. Exclude mere substring matches,
# free-text discussion, and sheet title values that lack a specific room/name.
_LOCAL_NAMED_PLAN_CAPTION = re.compile(
    r"^(?:PROP(?:OSED)?\.)\s+"
    r"(?P<local_name>[A-Z][A-Z0-9&/' -]{1,54})\s+PLAN$",
    re.ASCII | re.IGNORECASE,
)


def _finite_bbox(raw):
    try:
        if isinstance(raw, (str, bytes)):
            return None
        values = tuple(float(v) for v in raw)
    except (ValueError, TypeError, OverflowError):
        return None
    return (
        values if len(values)==4
        and all(math.isfinite(v) for v in values)
        and values[2]>values[0] and values[3]>values[1]
        else None
    )


def find_native_named_plan_caption_candidates_shadow(page: Any, *, page_number: int):
    """Enumerate *all* exact native title lines, retaining competing captions."""
    data = page.get_text("dict") or {}
    original_words = page.get_text("words") or ()
    by_line = {}
    for raw in original_words:
        if len(raw) < 8:
            continue
        try:
            block,line,ordinal = (int(raw[i]) for i in (5,6,7))
        except (TypeError,ValueError,OverflowError):
            continue
        bbox = _finite_bbox(raw[:4])
        if block < 0 or line < 0 or ordinal < 0 or bbox is None:
            continue
        by_line.setdefault((block,line), []).append({
            "word_ordinal":ordinal,
            "source_literal_word":str(raw[4]),
            "native_source_bbox_pdf_pts":list(bbox),
        })
    rows = []
    for block_idx,block in enumerate(data.get("blocks", ())):
        if int(block.get("type",0) or 0) != 0:
            continue
        for line_idx,line in enumerate(block.get("lines", ())):
            content = " ".join(str(span.get("text","")) for span in line.get("spans", ()))
            content = " ".join(content.strip().split())
            found = _LOCAL_NAMED_PLAN_CAPTION.fullmatch(content)
            if found is None:
                continue
            box = _finite_bbox(line.get("bbox"))
            direction = line.get("dir")
            try:
                vector = tuple(float(x) for x in direction)
            except (ValueError,TypeError,OverflowError):
                vector = ()
            if box is None or len(vector)!=2 or not all(math.isfinite(v) for v in vector):
                continue
            name = " ".join(found.group("local_name").upper().split())
            if not name or not re.search(r"[A-Z]",name):
                continue
            source_words = sorted(by_line.get((block_idx,line_idx),[]),
                                  key=lambda word:(word["word_ordinal"],
                                                   word["native_source_bbox_pdf_pts"]))
            if not source_words:
                continue
            rows.append({
                "source_pdf_page_number":int(page_number),
                "original_native_block_index":block_idx,
                "original_native_line_index":line_idx,
                "native_caption_text":content,
                "native_named_plan_subject":name,
                "native_caption_bbox_pdf_pts":list(box),
                "native_text_direction":list(vector),
                "original_native_word_source_receipts":source_words,
                "source_local_plan_caption_candidate_only":True,
                "new_physical_plan_viewport_granted":False,
                "new_room_identity_or_metric_granted":False,
            })
    return sorted(rows,key=lambda a:(a["source_pdf_page_number"],
                                     a["native_caption_bbox_pdf_pts"],
                                     a["original_native_block_index"],
                                     a["original_native_line_index"]))


__all__=["find_native_named_plan_caption_candidates_shadow"]
