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
    return base


__all__ = ["source_grid_registration_shadow"]
