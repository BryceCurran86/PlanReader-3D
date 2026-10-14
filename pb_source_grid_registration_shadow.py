"""Two-view *candidate* construction-grid registration from immutable PDF.

This is an evidence CENSUS only.  The native text glyph positions on two
source pages can suggest a common construction grid, but text matching alone
NEVER proves an authentic drawn grid line, same physical room, material
occurrence, figured dimensions, scale, or metric quantity.

Inputs are original PDF bytes; outputs remain in native unrotated PDF points.
The algorithm abstains if two competing letter rows or numeric columns have
equally credible matches. A separate SourceVisibility/raster and W2/W3/W4
physical-grid receipt must corroborate this candidate before production use.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import math
from statistics import median
from typing import Any

import fitz


def _native_words(page: Any) -> tuple[dict, ...]:
    items = []
    for word in page.get_text("words"):
        if len(word) < 8:
            continue
        x0, y0, x1, y1, text, block, line, offset = word[:8]
        if not all(math.isfinite(float(x)) for x in (x0, y0, x1, y1)):
            continue
        if x1 <= x0 or y1 <= y0:
            continue
        token = str(text).strip()
        if len(token) != 1 or not (token.isascii() and token.isalnum()):
            continue
        items.append({
            "token": token, "x": (x0 + x1) / 2.0, "y": (y0 + y1) / 2.0,
            "bbox": (x0, y0, x1, y1),
            "native_source_address": (int(block), int(line), int(offset)),
        })
    return tuple(items)


def _rows(words: tuple[dict, ...], *, axis: str, tolerance: float,
          valid: str, min_distinct: int, span_required: float) -> tuple[dict, ...]:
    """Find source-collinear controls; never choose a nearest arbitrary word."""
    selected = [w for w in words if w["token"] in valid]
    coordinate = "y" if axis == "letters" else "x"
    transverse = "x" if axis == "letters" else "y"
    selected.sort(key=lambda w: (w[coordinate], w[transverse], w["token"]))
    groups: list[list[dict]] = []
    for w in selected:
        matching = [
            i for i, group in enumerate(groups)
            if abs(w[coordinate] - median(v[coordinate] for v in group)) <= tolerance
        ]
        if len(matching) == 1:
            groups[matching[0]].append(w)
        elif not matching:
            groups.append([w])
        # Ambiguous placement relative to multiple lines cannot create an
        # authoritative candidate: the shared point is discarded.
    results: list[dict] = []
    for group in groups:
        tokens = Counter(w["token"] for w in group)
        unique = {w["token"]: w for w in group if tokens[w["token"]] == 1}
        if len(unique) < min_distinct:
            continue
        span = max(w[transverse] for w in unique.values()) - min(
            w[transverse] for w in unique.values()
        )
        if span < span_required:
            continue
        results.append({
            "controls": unique,
            "row_coordinate": median(w[coordinate] for w in unique.values()),
        })
    return tuple(results)



def _native_vector_grid_axes(page: Any) -> dict[str, tuple[dict, ...]]:
    """Candidate long collinear segmented source STROKES, not W4 wall roles.

    Return original PDF path/index/coordinates.  No OCR, inferred vector,
    reconstructed raster line or invented source primitive enters this
    diagnostic. Drawing colors are not hard-coded to a project's grid color.
    """
    groups: dict[tuple, list[tuple]] = {}
    for path_index, drawing in enumerate(page.get_drawings()):
        color = drawing.get("color")
        width = drawing.get("width")
        if (
            type(color) not in (tuple, list)
            or len(color) != 3
            or not all(math.isfinite(float(c)) for c in color)
            or type(width) not in (float, int)
            or not math.isfinite(float(width))
            or float(width) <= 0
        ):
            continue
        style = (
            *(round(float(c), 4) for c in color),
            round(float(width), 4),
        )
        for item_index, item in enumerate(drawing.get("items") or ()):
            if not item or item[0] != "l" or len(item) < 3:
                continue
            a, b = item[1], item[2]
            x1, y1, x2, y2 = float(a.x), float(a.y), float(b.x), float(b.y)
            if not all(math.isfinite(v) for v in (x1,y1,x2,y2)):
                continue
            if abs(x1-x2) <= 0.05 and abs(y1-y2) > 1.0:
                key=("x",round((x1+x2)/2.0,1),style)
                low,high=sorted((y1,y2))
            elif abs(y1-y2) <= 0.05 and abs(x1-x2) > 1.0:
                key=("y",round((y1+y2)/2.0,1),style)
                low,high=sorted((x1,x2))
            else:
                continue
            groups.setdefault(key,[]).append(
                (low,high,int(path_index),int(item_index))
            )
    result: dict[str,list[dict]]={"x":[],"y":[]}
    for (orientation,coordinate,style),segments in groups.items():
        if len(segments) < 12:
            continue
        source_span=max(row[1] for row in segments)-min(
            row[0] for row in segments
        )
        needed=(
            float(page.cropbox.height)*0.35
            if orientation=="x" else float(page.cropbox.width)*0.35
        )
        if source_span < needed:
            continue
        result[orientation].append({
            "native_constant_coordinate": coordinate,
            "source_style": style,
            "segment_count": len(segments),
            "native_source_span_pdf_pts": round(source_span,3),
            "original_path_item_addresses": tuple(
                (s[2],s[3]) for s in segments
            ),
        })
    return {axis:tuple(rows) for axis,rows in result.items()}


def _grid_vector_witness_for_page(
    axes: dict[str,tuple[dict,...]],
    letters: dict, numbers: dict,
) -> dict | None:
    # Each source grid marker must have a uniquely associated original long
    # stroke on *both* source axes. A label without a line remains unproven.
    matches=[]
    for orientation,controls,coordinate in (
        ("x",letters,"x"),("y",numbers,"y")
    ):
        owned={}
        for key,word in controls.items():
            candidates=[
                axis for axis in axes[orientation]
                if abs(axis["native_constant_coordinate"]-word[coordinate]) <= 4.5
            ]
            if not candidates:
                return None
            owned[key]=candidates
        matches.append(owned)
    # A real drawn construction grid is a single original vector stroke style
    # across all independent lettered and numbered axes on the one page.
    styles=None
    for group in matches:
        for options in group.values():
            group_styles={tuple(axis["source_style"]) for axis in options}
            styles = group_styles if styles is None else styles & group_styles
    if not styles or len(styles)!=1:
        return None
    style=next(iter(styles))
    outputs=[]
    for group in matches:
        selected={}
        for token,options in group.items():
            same=[o for o in options if tuple(o["source_style"])==style]
            if len(same)!=1:
                return None
            selected[token]=same[0]
        outputs.append(selected)
    return {"letters":outputs[0],"numbers":outputs[1],"style":style}


def _native_cross_view_vector_registration(
    source_bytes: bytes, pages: tuple[int,int],
    text_hypothesis: tuple,
) -> dict:
    """Cross-check text control candidate against ORIGINAL, independent ink."""
    letters,numbers,_,_,la,lb,na,nb=text_hypothesis
    with fitz.open(stream=source_bytes,filetype="pdf") as doc:
        geometries=[
            _native_vector_grid_axes(doc[p]) for p in pages
        ]
    source_controls=[
        _grid_vector_witness_for_page(
            geometry, row["controls"], column["controls"]
        )
        for geometry,row,column in zip(
            geometries,(la,lb),(na,nb)
        )
    ]
    if any(value is None for value in source_controls):
        return {"source_native_vector_grid_candidate":False,
                "first_grid_vector_gate":"native_grid_marker_drawn_vector_ancestry_unavailable"}
    a,b=source_controls
    if a["style"]!=b["style"]:
        return {"source_native_vector_grid_candidate":False,
                "first_grid_vector_gate":"cross_view_grid_source_style_conflict"}
    offsets_x=[
        b["letters"][name]["native_constant_coordinate"]
        -a["letters"][name]["native_constant_coordinate"]
        for name in letters
    ]
    offsets_y=[
        b["numbers"][name]["native_constant_coordinate"]
        -a["numbers"][name]["native_constant_coordinate"]
        for name in numbers
    ]
    if (
        max(offsets_x)-min(offsets_x)>0.5
        or max(offsets_y)-min(offsets_y)>0.5
    ):
        return {"source_native_vector_grid_candidate":False,
                "first_grid_vector_gate":"drawn_gridline_cross_view_axis_conflict"}
    return {
        "source_native_vector_grid_candidate":True,
        "first_grid_vector_gate":"producer_owned_grid_source_and_room_equivalence_unverified",
        "native_vector_grid_translation_candidate_pdf_pts":[
            round(median(offsets_x),6),round(median(offsets_y),6),
        ],
        "native_vector_grid_letter_lineage":[
            {"grid_token":name,
             "first_line_coordinate":a["letters"][name]["native_constant_coordinate"],
             "second_line_coordinate":b["letters"][name]["native_constant_coordinate"],
             "first_original_segment_count":a["letters"][name]["segment_count"],
             "second_original_segment_count":b["letters"][name]["segment_count"],
             "first_original_path_item_addresses":a["letters"][name]["original_path_item_addresses"],
             "second_original_path_item_addresses":b["letters"][name]["original_path_item_addresses"],
            } for name in letters
        ],
        "native_vector_grid_number_lineage":[
            {"grid_token":name,
             "first_line_coordinate":a["numbers"][name]["native_constant_coordinate"],
             "second_line_coordinate":b["numbers"][name]["native_constant_coordinate"],
             "first_original_segment_count":a["numbers"][name]["segment_count"],
             "second_original_segment_count":b["numbers"][name]["segment_count"],
             "first_original_path_item_addresses":a["numbers"][name]["original_path_item_addresses"],
             "second_original_path_item_addresses":b["numbers"][name]["original_path_item_addresses"],
            } for name in numbers
        ],
    }


def source_grid_registration_shadow(
    source_pdf_bytes: bytes,
    *,
    expected_sha256: str,
    first_page_index: int,
    second_page_index: int,
) -> dict:
    if type(source_pdf_bytes) is not bytes:
        raise TypeError("source must be immutable PDF bytes")
    sha = hashlib.sha256(source_pdf_bytes).hexdigest()
    if sha != expected_sha256:
        raise ValueError("original source SHA differs")
    if (
        type(first_page_index) is not int
        or type(second_page_index) is not int
        or first_page_index < 0
        or second_page_index < 0
        or first_page_index == second_page_index
    ):
        raise ValueError("source pages must be distinct nonnegative indices")

    base = {
        "original_source_sha256": sha,
        "source_pages_1_based": [first_page_index + 1, second_page_index + 1],
        "diagnostic_only": True,
        "source_native_text_grid_candidate": False,
        "native_grid_translation_candidate_pdf_pts": None,
        "source_grid_line_witness_verified": False,
        "source_word_raster_corroborated": False,
        "source_plan_viewport_owned": False,
        "cross_view_physical_room_equivalence_verified": False,
        "source_finish_occurrence_owned": False,
        "source_floor_area_quantity_created": False,
        "commercial_projection_allowed": False,
        "first_unclosed_gate": "source_native_grid_controls_unavailable",
        "letter_controls": [],
        "number_controls": [],
    }
    with fitz.open(stream=source_pdf_bytes, filetype="pdf") as doc:
        if max(first_page_index, second_page_index) >= len(doc):
            raise ValueError("source page out of bounds")
        words, sizes = [], []
        for index in (first_page_index, second_page_index):
            p = doc[index]
            words.append(_native_words(p))
            sizes.append((float(p.cropbox.width), float(p.cropbox.height)))

    if any(x <= 0 or y <= 0 for x, y in sizes):
        return base
    # Both independent control systems must be composed of source-native
    # single-character tokens. String coincidence is insufficient to publish.
    a_rows = [_rows(ws, axis="letters", tolerance=1.5,
                     valid="ABCDEFGHIJKLMNOPQRSTUVWXYZ", min_distinct=3,
                     span_required=size[0] * 0.30)
              for ws, size in zip(words, sizes)]
    n_columns = [_rows(ws, axis="numbers", tolerance=2.5,
                       valid="123456789", min_distinct=4,
                       span_required=size[1] * 0.30)
                 for ws, size in zip(words, sizes)]

    hypotheses = []
    for letters_a in a_rows[0]:
        for letters_b in a_rows[1]:
            common_l = sorted(set(letters_a["controls"]) & set(letters_b["controls"]))
            if len(common_l) < 3:
                continue
            letter_deltas = [
                letters_b["controls"][name]["x"] - letters_a["controls"][name]["x"]
                for name in common_l
            ]
            if max(letter_deltas) - min(letter_deltas) > 0.5:
                continue
            if any(
                (letters_a["controls"][x]["x"] - letters_a["controls"][y]["x"])
                * (letters_b["controls"][x]["x"] - letters_b["controls"][y]["x"]) <= 0
                for x in common_l for y in common_l if x != y
            ):
                continue
            for numbers_a in n_columns[0]:
                for numbers_b in n_columns[1]:
                    common_n = sorted(set(numbers_a["controls"]) & set(numbers_b["controls"]))
                    if len(common_n) < 4:
                        continue
                    number_deltas = [
                        numbers_b["controls"][name]["y"] - numbers_a["controls"][name]["y"]
                        for name in common_n
                    ]
                    if max(number_deltas) - min(number_deltas) > 0.5:
                        continue
                    if any(
                        (numbers_a["controls"][x]["y"] - numbers_a["controls"][y]["y"])
                        * (numbers_b["controls"][x]["y"] - numbers_b["controls"][y]["y"]) <= 0
                        for x in common_n for y in common_n if x != y
                    ):
                        continue
                    hypotheses.append((common_l, common_n, letter_deltas,
                                       number_deltas, letters_a, letters_b,
                                       numbers_a, numbers_b))
    if len(hypotheses) != 1:
        base["first_unclosed_gate"] = (
            "competing_source_grid_control_registrations"
            if hypotheses else "independent_grid_control_registration_unavailable"
        )
        base["candidate_registration_count"] = len(hypotheses)
        return base

    letters, numbers, dxs, dys, la, lb, na, nb = hypotheses[0]
    base.update({
        "source_native_text_grid_candidate": True,
        "native_grid_translation_candidate_pdf_pts": [
            round(median(dxs), 6), round(median(dys), 6),
        ],
        "letter_grid_control_count": len(letters),
        "number_grid_control_count": len(numbers),
        "letter_delta_span_pdf_pts": round(max(dxs) - min(dxs), 6),
        "number_delta_span_pdf_pts": round(max(dys) - min(dys), 6),
        "letter_controls": [
            {"token": name,
             "first_native_source_address": la["controls"][name]["native_source_address"],
             "second_native_source_address": lb["controls"][name]["native_source_address"],
             "first_bbox_pdf_pts": la["controls"][name]["bbox"],
             "second_bbox_pdf_pts": lb["controls"][name]["bbox"]}
            for name in letters
        ],
        "number_controls": [
            {"token": name,
             "first_native_source_address": na["controls"][name]["native_source_address"],
             "second_native_source_address": nb["controls"][name]["native_source_address"],
             "first_bbox_pdf_pts": na["controls"][name]["bbox"],
             "second_bbox_pdf_pts": nb["controls"][name]["bbox"]}
            for name in numbers
        ],
        "first_unclosed_gate": "source_grid_drawn_line_and_raster_receipts_unverified",
    })
    vector=_native_cross_view_vector_registration(
        source_pdf_bytes,(first_page_index,second_page_index),hypotheses[0]
    )
    base.update(vector)
    # Raw native-vector path receipts are stronger source evidence than word
    # coordinates alone. They still cannot grant producer-owned W2/W3/W4
    # physical grid, room, finish or commercial authority.
    if vector.get("source_native_vector_grid_candidate") is True:
        base["first_unclosed_gate"]=(
            "source_grid_producer_and_room_physical_equivalence_unverified"
        )
    return base


__all__ = ["source_grid_registration_shadow"]
