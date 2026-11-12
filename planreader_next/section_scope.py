"""Original plan section-cut chain to source FFL/FCL height; shadow evidence.

A section that passes through a region does NOT establish a finished ceiling
height for that region or authorise a wall-surface/customer quantity.
"""
from __future__ import annotations

from collections import defaultdict
import math
import re
from typing import Any, Mapping, Sequence

from .engine import NativePage, NativeWord, SourceConflict
from .height_evidence import section_ffl_fcl_heights

_SOURCE_BLOCK = re.compile(r"^word:(b[0-9]+):l[0-9]+:w[0-9]+:i[0-9]+$")
_AXIS_TOL_PT = .45
_MAX_DASH_LENGTH_PT = 22
_MAX_DASH_GAP_PT = 13
_MIN_DASH_COUNT = 8


def _block(word: NativeWord) -> str | None:
    match = _SOURCE_BLOCK.fullmatch(word.ref)
    return match.group(1) if match else None


def _mid(word: NativeWord) -> tuple[float, float]:
    return (word.bbox[0] + word.bbox[2]) / 2, (word.bbox[1] + word.bbox[3]) / 2


def source_section_cut(
    plan_page: NativePage,
    section_page: NativePage,
    *,
    section_letter: str = "A",
    sheet_code: str = "A0.7",
) -> dict[str, Any]:
    """Locate the authentic dashed A?A cut from paired source marker ink."""
    if (
        plan_page.source_sha256 != section_page.source_sha256
        or plan_page.page_index == section_page.page_index
    ):
        raise SourceConflict("section_cut_cross_page_source_mismatch")
    if not re.fullmatch(r"[A-Z]", section_letter) or not re.fullmatch(
        r"A[0-9]+[.][0-9]+", sheet_code
    ):
        raise SourceConflict("section_cut_reference_invalid")
    title_groups: dict[str, set[str]] = defaultdict(set)
    title_refs: list[str] = []
    for word in section_page.words:
        block = _block(word)
        if block and word.text.upper() in ("SECTION", section_letter + "-" + section_letter):
            title_groups[block].add(word.text.upper())
            title_refs.append(word.ref)
    if not any(
        {"SECTION", section_letter + "-" + section_letter} <= tokens
        for tokens in title_groups.values()
    ):
        raise SourceConflict("section_title_source_not_authenticated")

    marker_groups: dict[str, dict[str, list[NativeWord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for word in plan_page.words:
        block = _block(word)
        if block and word.text.strip().upper() in (section_letter, sheet_code):
            marker_groups[block][word.text.strip().upper()].append(word)
    markers: list[tuple[NativeWord, NativeWord]] = []
    for group in marker_groups.values():
        letters, sheets = group.get(section_letter, []), group.get(sheet_code, [])
        if len(letters) == len(sheets) == 1:
            letter, sheet = letters[0], sheets[0]
            if abs(_mid(letter)[0] - _mid(sheet)[0]) <= 8 and (
                abs(_mid(letter)[1] - _mid(sheet)[1]) <= 22
            ):
                markers.append((letter, sheet))
    markers.sort(key=lambda pair: _mid(pair[1])[1])
    if len(markers) != 2:
        raise SourceConflict("section_cut_markers_not_unique")
    first, second = markers
    x_top, y_top = _mid(first[1])
    x_end, y_end = _mid(second[1])
    if abs(x_top - x_end) > _AXIS_TOL_PT or y_end - y_top < 120:
        raise SourceConflict("section_cut_marker_alignment_invalid")

    # Dashed plan ink is a set of source-native segments, NOT a fabricated
    # infinite line between two labels. Require a nearly complete chain with
    # a strict maximum gap, unique source ref and source actual stations.
    cut_x = (x_top + x_end) / 2
    chain: list[tuple[float, float, str]] = []
    for seg in plan_page.segments:
        if seg.kind not in ("line", "rect_edge"):
            continue
        if abs(seg.x1 - seg.x2) > .2 or abs(seg.x1 - cut_x) > _AXIS_TOL_PT:
            continue
        lo, hi = sorted((seg.y1, seg.y2))
        if not (6 <= hi - lo <= _MAX_DASH_LENGTH_PT):
            continue
        if lo < first[1].bbox[3] - 5 or hi > second[0].bbox[1] + 5:
            continue
        chain.append((lo, hi, seg.ref))
    chain.sort()
    unique_refs = {ref for _, _, ref in chain}
    if len(chain) < _MIN_DASH_COUNT or len(unique_refs) != len(chain):
        raise SourceConflict("section_cut_source_dashes_incomplete")
    if chain[0][0] - first[1].bbox[3] > 20 or (
        second[0].bbox[1] - chain[-1][1] > 20
    ):
        raise SourceConflict("section_cut_dashes_do_not_reach_markers")
    if any(a > b + _MAX_DASH_GAP_PT for (_, b, _), (a, _, _) in zip(chain, chain[1:])):
        raise SourceConflict("section_cut_dashes_disconnected")
    if sum(hi - lo for lo, hi, _ in chain) < .38 * (y_end - y_top):
        raise SourceConflict("section_cut_source_ink_too_sparse")
    if any(not math.isfinite(n) for n in (cut_x, y_top, y_end)):
        raise SourceConflict("section_cut_source_geometry_invalid")
    return {
        "source_sha256": plan_page.source_sha256,
        "plan_page_index": plan_page.page_index,
        "section_page_index": section_page.page_index,
        "section_reference": section_letter + "-" + section_letter,
        "section_sheet_code": sheet_code,
        "plan_marker_word_refs": [first[0].ref, first[1].ref, second[0].ref, second[1].ref],
        "section_title_word_refs": sorted(title_refs),
        "plan_dashed_source_segment_refs": [ref for _, _, ref in chain],
        "cut_axis_pdf_pts": [cut_x, chain[0][0], cut_x, chain[-1][1]],
        "source_cut_line_authenticated": True,
        "physical_room_scope_authenticated": False,
        "applies_to_all_rooms": False,
        "commercial_publishable": False,
        "benchmark_credit": False,
    }


def section_cut_region_height_candidates(
    plan_page: NativePage,
    section_page: NativePage,
    regions: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Shadow-only room-region intersects original section-cut SOURCE ink."""
    cut = source_section_cut(plan_page, section_page)
    heights = section_ffl_fcl_heights(section_page)
    # Equal text values on different height scopes are NOT necessarily the
    # same physical ceiling level; demand a unique original section receipt.
    if len(heights) != 1:
        raise SourceConflict("section_cut_ffl_fcl_height_not_unique")
    from shapely.geometry import LineString, Polygon

    x, y1, _, y2 = cut["cut_axis_pdf_pts"]
    line = LineString([(x, y1), (x, y2)])
    candidates: list[dict[str, Any]] = []
    region_ids: set[str] = set()
    for region in regions:
        region_id = region.get("region_id")
        if type(region_id) is not str or not region_id.strip():
            raise SourceConflict("section_region_identity_missing")
        if region_id in region_ids:
            raise SourceConflict("section_region_identity_duplicate")
        region_ids.add(region_id)
        points = region.get("boundary_polygon_pdf_pts")
        if not isinstance(points, list) or len(points) < 3:
            raise SourceConflict("section_region_boundary_invalid")
        try:
            poly = Polygon(points)
        except (ValueError, TypeError) as exc:
            raise SourceConflict("section_region_boundary_invalid") from exc
        if not poly.is_valid or poly.is_empty or poly.area <= 0:
            raise SourceConflict("section_region_boundary_invalid")
        overlap = poly.intersection(line).length
        if overlap < 5:
            continue
        labels = region.get("room_label_words", [])
        candidates.append({
            "region_id": region_id,
            "room_label_word_refs": sorted(
                word.get("native_word_ref", word.get("ref"))
                for word in labels if isinstance(word, dict)
                and type(word.get("native_word_ref", word.get("ref"))) is str
            ),
            "room_label_words": [word.get("text") for word in labels
                                 if isinstance(word, dict)],
            "region_topology_status": region.get("status"),
            "source_cut_intersection_pdf_pts_not_metric": round(overlap, 4),
            "height_source_page_index": section_page.page_index,
            "height_mm_source_candidate": heights[0]["height_mm"],
            "height_source_receipt": heights[0],
            "section_crosses_candidate_region": True,
            "room_identity_authenticated": False,
            "ceiling_zone_scope_authenticated": False,
            "wall_finish_to_fcl_authenticated": False,
            "height_applied_to_room": False,
            "commercial_publishable": False,
            "benchmark_credit": False,
        })
    return {
        "source_sha256": plan_page.source_sha256,
        "plan_page_index": plan_page.page_index,
        "section_page_index": section_page.page_index,
        "source_plan_section_cut": cut,
        "height_mm_source_candidate": heights[0]["height_mm"],
        "source_height_receipt": heights[0],
        "cut_intersecting_region_candidates": candidates,
        "region_count_checked": len(regions),
        "physical_room_height_authenticated": False,
        "height_applied_to_any_room": False,
        "commercial_publishable": False,
        "benchmark_credit": False,
        "official_score": None,
    }
