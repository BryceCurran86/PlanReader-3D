"""Q5446-class vector outlined lettering: reuse original typed-negative ink filter.

Source-generic diagnostic only. Refuses to treat noisy font/dimension strokes as
physical walls. It does not modify the original PDF, invent an outline, renumber
any native path, or enable a commercial quantity.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from pb_physical_wall_candidate_authority import (
    _filter_repeated_non_physical_drafting_primitives,
)
from pb_vector_geometry_v130 import extract_native_page


@dataclass(frozen=True)
class VectorInkScope:
    drawings: tuple[Mapping[str, Any], ...]
    applied: bool
    reason: str
    original_paths: int
    discarded_simple_stroke_paths: int
    native_line_segments: int
    kept_line_segments: int


def scope_outlined_vector_lettering(
    page: Any,
    original_drawings: Sequence[Mapping[str, Any]],
) -> VectorInkScope:
    """Keep every source path ID, including excluded paths as inert rows.

    Only the GENERIC outlined-lettering signature enables this prefilter:
    nearly no native words AND a dense native vector sheet. It never touches
    any filled, curved, non-stroked or composite path. Thus door arcs, solid
    wall bars and native page path IDs are all retained. The existing original
    typed-negative producer classifies the discarded stroke-only paths.
    """
    original_count = len(original_drawings)
    try:
        words = page.get_text("words")
    except Exception:
        words = []
    if len(words) > 20 or original_count < 5000:
        return VectorInkScope(tuple(original_drawings), False,
            "outlined_text_signature_not_present", original_count, 0, 0, 0)
    native = extract_native_page(page)
    segments = native.get("segments", ())
    if len(segments) < 10000:
        return VectorInkScope(tuple(original_drawings), False,
            "too_few_native_line_segments_for_outlined_filter", original_count, 0,
            len(segments), len(segments))
    kept = _filter_repeated_non_physical_drafting_primitives(
        segments,
        page_width=float(page.rect.width),
        page_height=float(page.rect.height),
        filter_typed_negative_non_wall_ink_shadow=True,
    )
    source_ids = {
        s.get("path_index") for s in segments
        if type(s.get("path_index")) is int
    }
    kept_ids = {
        s.get("path_index") for s in kept
        if type(s.get("path_index")) is int
    }
    blank = {"layer": "", "fill": None, "color": None, "items": ()}
    selected: list[Mapping[str, Any]] = []
    removed = 0
    for index, row in enumerate(original_drawings):
        items = row.get("items", ())
        simple_stroke_only = (
            row.get("type") == "s"
            and row.get("fill") is None
            and len(items) > 0
            and all(item[0] == "l" for item in items)
        )
        if simple_stroke_only and index in source_ids and index not in kept_ids:
            selected.append(blank)
            removed += 1
        else:
            selected.append(row)
    return VectorInkScope(tuple(selected), True,
        "typed_negative_vector_ink_source_path_scope_candidate_only",
        original_count, removed, len(segments), len(kept))
