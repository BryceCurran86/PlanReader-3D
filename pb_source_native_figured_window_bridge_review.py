"""Source-native figured window ↔ individually hosted footprint bridge review.

Printed two-axis window text and uniquely painted wall/window marker geometry
can be compared without consulting a frozen benchmark. This is still a
SOURCE REVIEW, not certified physical wall or customer measurement authority.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
import hashlib
import math
import re

import fitz

from pb_migration_contracts import stable_contract_id
from pb_opening_label_dimension_authority import parse_opening_label_dimensions
from pb_source_window_footprint_continuity import (
    detect_exterior_window_footprint_bridges,
)

_SHA = re.compile(r"^[0-9a-f]{64}$")
_WINDOW_KIND = re.compile(
    r"\b(?:ASW|AAW|ADH|ADHW|ASHW|AFW|ALW|AW|WIN|WINDOW)\b",
    re.IGNORECASE,
)
_DOOR_KIND = re.compile(r"\b(?:ASD|ASSD|VSD|CS|DOORS?)\b",re.IGNORECASE)
_BRIDGE_WINDOW = re.compile(
    r"^(?:ASW|AAW|ADH|ADHW|ASHW|AFW|ALW|AW|WINDOW|WIN|FGW|SGW|W[- ]?\d+[A-Z]*)$",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class NativeFiguredWindowBridgeReview:
    receipt_id: str
    source_sha256: str
    page_index: int
    native_host_path_ids: tuple[int, int]
    native_window_marker_path_ids: tuple[int, ...]
    figured_word_indices: tuple[int, ...]
    unordered_figured_axes_mm: tuple[float, float]
    provisional_product_m2: float
    status: str = "FIGURED_SOURCE_WINDOW_TOPOLOGY_REVIEW_ONLY"
    physical_wall_authenticated: bool = False
    metric_authorized: bool = False
    customer_quantity_authorized: bool = False
    frozen_benchmark_scored: bool = False


@dataclass(frozen=True)
class NativeFiguredWindowBridgeReviewResult:
    source_sha256: str
    page_index: int
    native_window_bridge_count: int
    source_figured_two_axis_window_line_count: int
    unique_source_figured_window_bridges: tuple[NativeFiguredWindowBridgeReview, ...]
    ambiguous_lines_or_bridges: int
    physical_wall_authenticated: bool = False
    customer_quantity_authorized: bool = False
    frozen_benchmark_scored: bool = False


def _visible_window_figure_lines(words):
    groups = defaultdict(list)
    for i, word in enumerate(words):
        if (
            not isinstance(word,(tuple,list)) or len(word)<8
            or any(type(word[j]) is not int for j in (5,6,7))
        ):
            continue
        try:
            bbox=tuple(float(word[j]) for j in range(4))
        except (TypeError,ValueError,OverflowError):
            continue
        if (
            not all(math.isfinite(v) for v in bbox)
            or bbox[2]<=bbox[0] or bbox[3]<=bbox[1]
            or type(word[4]) is not str
        ):
            continue
        groups[word[5],word[6]].append((word[7],i,word[4],bbox))
    out=[]
    for rows in groups.values():
        rows.sort(key=lambda row:(row[0],row[1]))
        text=" ".join(x[2] for x in rows).strip()
        if not _WINDOW_KIND.search(text) or _DOOR_KIND.search(text):
            continue
        parsed=parse_opening_label_dimensions(text)
        if parsed is None or len(parsed.dimension_values_mm)!=2:
            continue
        axes=tuple(float(x) for x in parsed.dimension_values_mm)
        if not all(math.isfinite(x) and 400.0<=x<=6000.0 for x in axes):
            continue
        bboxes=[x[3] for x in rows]
        bbox=(min(x[0] for x in bboxes),min(x[1] for x in bboxes),
              max(x[2] for x in bboxes),max(x[3] for x in bboxes))
        out.append((tuple(x[1] for x in rows),bbox,axes))
    return tuple(out)


def _same_owned_aperture_band(bridge, bbox) -> bool:
    b=bridge.bounds_pdf_pts
    if (
        len(b)!=4 or len(bbox)!=4
        or any(not math.isfinite(v) for v in (*b,*bbox))
        or bridge.axis not in ("h","v")
    ):
        return False
    if bridge.axis=="h":
        bridge_lo,bridge_hi=b[0],b[2]
        text_lo,text_hi=bbox[0],bbox[2]
        normal=abs((b[1]+b[3]-bbox[1]-bbox[3])/2.0)
        text_thickness=bbox[3]-bbox[1]
    else:
        bridge_lo,bridge_hi=b[1],b[3]
        text_lo,text_hi=bbox[1],bbox[3]
        normal=abs((b[0]+b[2]-bbox[0]-bbox[2])/2.0)
        text_thickness=bbox[2]-bbox[0]
    span=bridge_hi-bridge_lo
    text_span=text_hi-text_lo
    if span<=1.0 or text_span<=1.0 or text_thickness<=0:
        return False
    overlap=max(0.0,min(bridge_hi,text_hi)-max(bridge_lo,text_lo))
    center_delta=abs((bridge_hi+bridge_lo-text_hi-text_lo)/2.0)
    return (
        overlap/min(span,text_span)>=0.75
        and normal<=max(3.0,min(15.0,1.75*text_thickness))
        and center_delta<=max(4.0,0.25*span)
    )


def inspect_original_window_figured_bridge_review(
    original_pdf_bytes: bytes,
    *, page_index: int, expected_source_sha256: str,
) -> NativeFiguredWindowBridgeReviewResult:
    """Verify exact PDF SHA and bind *unique source callouts* for review only."""
    if type(original_pdf_bytes) is not bytes or not original_pdf_bytes:
        raise ValueError("immutable_original_pdf_bytes_required")
    if type(expected_source_sha256) is not str or _SHA.fullmatch(expected_source_sha256) is None:
        raise ValueError("full_original_pdf_sha256_required")
    source_sha256=hashlib.sha256(original_pdf_bytes).hexdigest()
    if source_sha256!=expected_source_sha256:
        raise ValueError("original_pdf_sha256_mismatch")
    if type(page_index) is not int or page_index<0:
        raise ValueError("original_page_index_invalid")
    try:
        with fitz.open(stream=original_pdf_bytes,filetype="pdf") as doc:
            if doc.is_encrypted or page_index>=doc.page_count:
                raise ValueError("original_page_not_available")
            page=doc[page_index]
            drawings=page.get_drawings()
            words=page.get_text("words")
    except (fitz.FileDataError,fitz.FileNotFoundError) as exc:
        raise ValueError("original_pdf_unreadable") from exc
    bridges=tuple(b for b in detect_exterior_window_footprint_bridges(
        drawings,words,page_index=page_index,
    ) if _BRIDGE_WINDOW.fullmatch(str(b.label_text or "").strip()))
    lines=_visible_window_figure_lines(words)
    by_bridge=defaultdict(list)
    ambiguous=0
    for ids,bbox,axes in lines:
        matches=[i for i,bridge in enumerate(bridges)
                 if _same_owned_aperture_band(bridge,bbox)]
        if len(matches)!=1:
            if matches:ambiguous+=1
            continue
        by_bridge[matches[0]].append((ids,axes))
    candidates=[]
    for index,rows in sorted(by_bridge.items()):
        if len(rows)!=1:
            ambiguous+=len(rows)
            continue
        bridge=bridges[index]
        ids,axes=rows[0]
        hosts=(bridge.left_host_path_id,bridge.right_host_path_id)
        area=axes[0]*axes[1]/1_000_000.0
        if not math.isfinite(area) or area<=0:
            continue
        receipt_id=stable_contract_id(
            "source_figured_window_bridge_review",
            {
                "source_sha256":source_sha256,
                "page_index":page_index,
                "host_path_ids":hosts,
                "marker_path_ids":tuple(bridge.marker_path_ids),
                "word_indices":ids,
                "two_axes_mm":axes,
            },digest_chars=32,
        )
        candidates.append(NativeFiguredWindowBridgeReview(
            receipt_id=receipt_id,source_sha256=source_sha256,
            page_index=page_index,native_host_path_ids=hosts,
            native_window_marker_path_ids=tuple(bridge.marker_path_ids),
            figured_word_indices=ids,unordered_figured_axes_mm=axes,
            provisional_product_m2=area,
        ))
    return NativeFiguredWindowBridgeReviewResult(
        source_sha256=source_sha256,page_index=page_index,
        native_window_bridge_count=len(bridges),
        source_figured_two_axis_window_line_count=len(lines),
        unique_source_figured_window_bridges=tuple(candidates),
        ambiguous_lines_or_bridges=ambiguous,
    )
