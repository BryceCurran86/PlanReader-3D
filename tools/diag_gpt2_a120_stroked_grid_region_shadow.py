"""Source-owned stroked ceiling grid enclosure shadow; no quantity authority.

White background fills and title/label proximity are never physical ring ink.
The shadow reports ALL source-line candidates and original word addresses.
No FIRM ceilings, new scale resolver or W2/W4 snap/graph modifications.
"""
from __future__ import annotations
from dataclasses import dataclass
import argparse
import hashlib
import json
import math
from pathlib import Path
import fitz


@dataclass(frozen=True)
class NativeLine:
    axis: str
    coordinate: float
    low: float
    high: float
    path_id: int
    item_id: int
    width_pt: float


def _stroked_lines(page, min_span_pt: float):
    result = []
    drawings = page.get_drawings()
    if len(drawings) > 120000:
        raise ValueError("source_drawing_universe_exceeds_shadow_bound")
    for i, drawing in enumerate(drawings):
        width = drawing.get("width")
        if (
            drawing.get("type") != "s"
            or drawing.get("color") != (0., 0., 0.)
            or type(width) not in (int, float)
            or not math.isfinite(width)
            or width <= 0
            or drawing.get("stroke_opacity") != 1
        ):
            continue
        for j, item in enumerate(drawing.get("items") or ()):
            if len(item) < 3 or item[0] != "l":
                continue
            p0, p1 = item[1:3]
            epsilon = min(width * 0.05, 0.03)
            if abs(p0.y - p1.y) <= epsilon and abs(p0.x - p1.x) >= min_span_pt:
                result.append(NativeLine(
                    "h", (p0.y + p1.y) / 2, min(p0.x, p1.x),
                    max(p0.x, p1.x), i, j, width,
                ))
            elif abs(p0.x - p1.x) <= epsilon and abs(p0.y - p1.y) >= min_span_pt:
                result.append(NativeLine(
                    "v", (p0.x + p1.x) / 2, min(p0.y, p1.y),
                    max(p0.y, p1.y), i, j, width,
                ))
    if len(result) > 10000:
        raise ValueError("source_long_line_universe_exceeds_shadow_bound")
    return result


def original_stroked_grid_rectangles_shadow(
    page, *, min_span_pt: float = 200.0, code: str = "GRID",
):
    """Enumerate all separate native source-line enclosures; never elect a winner."""
    if (
        type(min_span_pt) not in (int, float)
        or not math.isfinite(min_span_pt)
        or min_span_pt <= 0
    ):
        raise ValueError("finite_positive_min_span_required")
    if type(code) is not str or not code.isalpha() or code.upper() != code:
        raise ValueError("literal_material_code_required")
    words = tuple(page.get_text("words"))
    marks = tuple(w for w in words if str(w[4]).strip() == code)
    segments = _stroked_lines(page, float(min_span_pt))
    horizontal = [line for line in segments if line.axis == "h"]
    vertical = [line for line in segments if line.axis == "v"]
    candidates = []
    for i, top in enumerate(horizontal):
        for bottom in horizontal[i + 1:]:
            gap = max(top.width_pt, bottom.width_pt) * 1.05
            if (
                abs(top.low - bottom.low) > gap
                or abs(top.high - bottom.high) > gap
            ):
                continue
            height = abs(top.coordinate - bottom.coordinate)
            if height < min_span_pt:
                continue
            x0 = (top.low + bottom.low) / 2
            x1 = (top.high + bottom.high) / 2
            y0 = min(top.coordinate, bottom.coordinate)
            y1 = max(top.coordinate, bottom.coordinate)

            def matched(x):
                return [
                    line for line in vertical
                    if abs(line.coordinate - x) <= max(line.width_pt, gap) * 1.05
                    and abs(line.low - y0) <= max(line.width_pt, gap) * 1.05
                    and abs(line.high - y1) <= max(line.width_pt, gap) * 1.05
                ]

            left, right = matched(x0), matched(x1)
            if not left or not right:
                continue
            inside = [
                w for w in marks
                if x0 < (w[0] + w[2]) / 2 < x1
                and y0 < (w[1] + w[3]) / 2 < y1
            ]
            if len(inside) != 1:
                continue
            conflicting_marks = [
                w for w in words
                if w[4] in ("GRID", "IP", "IPF1", "FPB", "WFPB")
                and w[4] != code
                and x0 < (w[0] + w[2]) / 2 < x1
                and y0 < (w[1] + w[3]) / 2 < y1
            ]
            if conflicting_marks:
                continue
            for l in left:
                for r in right:
                    parents = (top.path_id, bottom.path_id, l.path_id, r.path_id)
                    if len(set(parents)) != 4:
                        continue
                    candidates.append({
                        "bbox_pdf_pts": [
                            round(n, 5) for n in (x0, y0, x1, y1)
                        ],
                        "source_path_ids": parents,
                        "source_mark_address": tuple(inside[0][5:8]),
                        "source_graphic_area_pt2": round((x1 - x0) * height, 5),
                        "source_stroked_perimeter_pt": round(2 * (x1 - x0 + height), 5),
                        "physical_room_source_authority": False,
                        "source_scale_authority": False,
                        "firm_quantity_m2": None,
                    })
    candidates.sort(key=lambda row: (
        row["bbox_pdf_pts"], row["source_path_ids"],
    ))
    return {
        "status": (
            "candidate_source_stroked_ceiling_region"
            if candidates else "unresolved"
        ),
        "material_code": code,
        "candidate_count": len(candidates),
        "candidates": candidates,
        "first_unclosed_gate": "source_producer_viewport_wall_and_material_ownership",
        "new_firm_quantities": 0,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdf", required=True)
    parser.add_argument("--sha256", required=True)
    parser.add_argument("--page", type=int, required=True)
    parser.add_argument("--min-span-pt", type=float, default=200.)
    args = parser.parse_args()
    original_bytes = Path(args.pdf).read_bytes()
    if hashlib.sha256(original_bytes).hexdigest() != args.sha256:
        raise SystemExit("private_source_sha_mismatch")
    with fitz.open(stream=original_bytes, filetype="pdf") as document:
        if args.page < 1 or args.page > len(document):
            raise SystemExit("source_page_range")
        result = original_stroked_grid_rectangles_shadow(
            document[args.page - 1], min_span_pt=args.min_span_pt,
        )
    result["original_source_sha256"] = args.sha256
    result["original_page_number"] = args.page
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
