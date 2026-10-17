"""Read-only original PDF native stroke correspondence census (GPT1 shadow).

A caller provides *two page-local source windows* and an existing candidate
(dx,dy). The census never guesses the alignment, elects an authoritative wall,
or emits a customer quantity. Every matching stroke and every unmatched dark
source candidate is preserved, including duplicate/competing native paths.

This is a development diagnostic for the source-authority owner. Native
stroke IDs mean path/item indices scoped to the exact original PDF SHA.
They are not portable between different original source files or revisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any


def _rect(window: object) -> tuple[float, float, float, float]:
    if type(window) not in (list, tuple) or len(window) != 4:
        raise ValueError("window must contain exactly four finite original PDF coordinates")
    if any(type(v) not in (int, float) for v in window):
        raise ValueError("window must contain exact numeric PDF coordinates")
    try:
        x0, y0, x1, y1 = (float(x) for x in window)
    except (TypeError, ValueError, OverflowError) as exc:
        raise ValueError("window values cannot be represented") from exc
    if not all(math.isfinite(v) for v in (x0, y0, x1, y1)) or x0 >= x1 or y0 >= y1:
        raise ValueError("window is not a finite nonempty rectangle")
    return x0, y0, x1, y1


def _strokes(
    page: Any,
    window: tuple[float, float, float, float],
    *,
    min_source_length_pt: float,
    min_source_width_pt: float,
    dark_ink_max_channel: float,
) -> tuple[dict[str, Any], ...]:
    """Read each native linear item, not shape bounds or raster approximations."""
    output: list[dict[str, Any]] = []
    for path_id, drawing in enumerate(page.get_drawings()):
        raw_color = drawing.get("color")
        raw_width = drawing.get("width")
        if (
            type(raw_color) not in (tuple, list) or len(raw_color) != 3
            or any(type(v) not in (int, float) for v in raw_color)
            or any(not math.isfinite(float(v)) for v in raw_color)
            or max(raw_color) > dark_ink_max_channel
            or type(raw_width) not in (int, float)
            or not math.isfinite(float(raw_width))
            or raw_width < min_source_width_pt
        ):
            continue
        for item_id, item in enumerate(drawing["items"]):
            if item[0] != "l":
                continue
            a, b = item[1], item[2]
            geometry = (float(a.x), float(a.y), float(b.x), float(b.y))
            if not all(math.isfinite(v) for v in geometry):
                continue
            length = math.hypot(geometry[0] - geometry[2], geometry[1] - geometry[3])
            if length < min_source_length_pt:
                continue
            if (
                min(geometry[0], geometry[2]) < window[0]
                or max(geometry[0], geometry[2]) > window[2]
                or min(geometry[1], geometry[3]) < window[1]
                or max(geometry[1], geometry[3]) > window[3]
            ):
                continue
            output.append({
                "native_source_path_id": f"d{path_id}i{item_id}",
                "source_endpoints_pdf_pt": tuple(round(v, 6) for v in geometry),
                "source_stroke_width_pt": round(float(raw_width), 6),
                "native_source_color": tuple(round(float(v), 6) for v in raw_color),
            })
    return tuple(output)


def _exact_translated(
    left: dict[str, Any],
    right: dict[str, Any],
    *,
    dx: float,
    dy: float,
    tolerance_pt: float,
) -> bool:
    """Width and native RGB plus both endpoints must agree; no nearest rank."""
    if abs(left["source_stroke_width_pt"] - right["source_stroke_width_pt"]) > 1e-6:
        return False
    if left["native_source_color"] != right["native_source_color"]:
        return False
    a = left["source_endpoints_pdf_pt"]
    b = right["source_endpoints_pdf_pt"]
    for i, j in ((0, 2), (2, 0)):
        first = math.dist((a[0] + dx, a[1] + dy), (b[i], b[i + 1]))
        second = math.dist((a[2] + dx, a[3] + dy), (b[j], b[j + 1]))
        if first <= tolerance_pt and second <= tolerance_pt:
            return True
    return False


def native_stroke_correspondence_census(
    original_pdf_path: str | Path,
    *,
    room_page_number: int,
    finish_page_number: int,
    room_window_pdf_pt: tuple[float, float, float, float],
    finish_window_pdf_pt: tuple[float, float, float, float],
    candidate_dx_pt: float,
    candidate_dy_pt: float,
    min_source_length_pt: float = 28.0,
    min_source_width_pt: float = 0.46,
    dark_ink_max_channel: float = 0.1,
    endpoint_tolerance_pt: float = 0.02,
) -> dict[str, Any]:
    """Retain all matching, rival and unmatched original paths at one hypothesis."""
    import fitz

    values = (
        candidate_dx_pt, candidate_dy_pt, min_source_length_pt,
        min_source_width_pt, dark_ink_max_channel, endpoint_tolerance_pt,
    )
    if any(type(v) not in (int, float) for v in values):
        raise ValueError("source census parameters must be numeric")
    numbers = tuple(float(v) for v in values)
    if (
        not all(math.isfinite(v) for v in numbers)
        or min_source_length_pt <= 0
        or min_source_width_pt <= 0
        or not 0 <= dark_ink_max_channel <= 1
        or not 0 <= endpoint_tolerance_pt <= 0.1
    ):
        raise ValueError("source census thresholds must be finite and safe")
    if (
        type(room_page_number) is not int or type(finish_page_number) is not int
        or room_page_number < 1 or finish_page_number < 1
        or room_page_number == finish_page_number
    ):
        raise ValueError("source pages must be different positive exact integer IDs")
    room_window, finish_window = _rect(room_window_pdf_pt), _rect(finish_window_pdf_pt)
    path = Path(original_pdf_path)
    payload = path.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    pdf = fitz.open(stream=payload, filetype="pdf")
    try:
        if max(room_page_number, finish_page_number) > pdf.page_count:
            raise ValueError("source page is outside the original PDF")
        room = _strokes(
            pdf[room_page_number - 1],room_window,
            min_source_length_pt=min_source_length_pt,
            min_source_width_pt=min_source_width_pt,
            dark_ink_max_channel=dark_ink_max_channel,
        )
        finish = _strokes(
            pdf[finish_page_number - 1],finish_window,
            min_source_length_pt=min_source_length_pt,
            min_source_width_pt=min_source_width_pt,
            dark_ink_max_channel=dark_ink_max_channel,
        )
    finally:
        pdf.close()
    matched_right: set[str] = set()
    left_rows = []
    for stroke in room:
        matched = tuple(sorted(
            candidate["native_source_path_id"] for candidate in finish
            if _exact_translated(
                stroke,candidate,dx=candidate_dx_pt,dy=candidate_dy_pt,
                tolerance_pt=endpoint_tolerance_pt,
            )
        ))
        matched_right.update(matched)
        left_rows.append({
            **stroke,
            "finish_source_path_matches": matched,
            "match_status": (
                "NO_MATCH" if not matched else
                "UNIQUE_CANDIDATE" if len(matched) == 1 else
                "COMPETING_SOURCE_STROKES"
            ),
        })
    no_match = tuple(sorted(
        v["native_source_path_id"] for v in finish
        if v["native_source_path_id"] not in matched_right
    ))
    counts = {
        k: sum(item["match_status"] == k for item in left_rows)
        for k in ("UNIQUE_CANDIDATE","COMPETING_SOURCE_STROKES","NO_MATCH")
    }
    return {
        "kind": "gpt1_original_native_stroke_correspondence_shadow",
        "diagnostic_only": True,
        "commercial_quantity_authority": False,
        "original_pdf_sha256": digest,
        "original_room_page_id": str(room_page_number),
        "original_finish_page_id": str(finish_page_number),
        "original_room_window_pdf_pt": room_window,
        "original_finish_window_pdf_pt": finish_window,
        "provided_candidate_translation_pdf_pt": (candidate_dx_pt,candidate_dy_pt),
        "match_type": "same_native_line_geometry_color_width_at_hypothesis",
        "physical_wall_semantic_authority": "UNPROVEN",
        "room_native_stroke_count": len(room),
        "finish_native_stroke_count": len(finish),
        "counts": counts,
        "room_original_source_strokes": tuple(left_rows),
        "unmatched_finish_source_path_ids": no_match,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("original_pdf",help="private original PDF; never upload into public git")
    parser.add_argument("--room-page",type=int,required=True)
    parser.add_argument("--finish-page",type=int,required=True)
    parser.add_argument("--room-window",type=float,nargs=4,required=True)
    parser.add_argument("--finish-window",type=float,nargs=4,required=True)
    parser.add_argument("--dx",type=float,required=True,help="prior W4 source frame candidate")
    parser.add_argument("--dy",type=float,required=True)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    result=native_stroke_correspondence_census(
        args.original_pdf,
        room_page_number=args.room_page,
        finish_page_number=args.finish_page,
        room_window_pdf_pt=tuple(args.room_window),
        finish_window_pdf_pt=tuple(args.finish_window),
        candidate_dx_pt=args.dx,candidate_dy_pt=args.dy,
    )
    serialized=json.dumps(result,indent=2,sort_keys=True)+"\n"
    if args.output:
        args.output.write_text(serialized,encoding="utf-8")
    else:
        print(serialized,end="")


if __name__=="__main__":
    main()
