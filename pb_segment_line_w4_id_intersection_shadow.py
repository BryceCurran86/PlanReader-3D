"""Compare segment-parent line keys to usable W4 source_primitive_ids (shadow)."""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any
import re

from pb_segment_w4_id_namespace_bridge_shadow import (
    assess_segment_w4_namespace_bridge_variants,
)


_DIGIT_TAIL = re.compile(r"(\d+)$")
_D_INDEX = re.compile(r"^d(\d+)i0$", re.IGNORECASE)


def _digit_tail(raw_id: str) -> str | None:
    text = str(raw_id or "").strip()
    if text.startswith("raster_opening_primitive:"):
        tail = text.rsplit(":", 1)[-1]
        return tail if tail.isdigit() else None
    m = _D_INDEX.match(text)
    if m:
        return m.group(1)
    m2 = _DIGIT_TAIL.search(text)
    return m2.group(1) if m2 else None


def assess_segment_line_w4_id_intersection_shadow(
    *,
    physical_opening_id: str,
    segment_line_raw_ids: Sequence[str],
    usable_w4_source_primitive_ids: Sequence[str],
) -> dict[str, Any]:
    oid = str(physical_opening_id or "").strip()
    if not oid:
        raise ValueError("physical opening identity required")
    lines = tuple(sorted({str(x).strip() for x in segment_line_raw_ids if str(x).strip()}))
    w4 = tuple(sorted({str(x).strip() for x in usable_w4_source_primitive_ids if str(x).strip()}))
    inter = tuple(sorted(set(lines) & set(w4)))
    # Prefix-normalized variants (visible: / raw) without inventing new owners.
    w4_stripped = {x[len("visible:"):] if x.startswith("visible:") else x for x in w4}
    lines_stripped = {x[len("visible:"):] if x.startswith("visible:") else x for x in lines}
    stripped_inter = tuple(sorted(lines_stripped & w4_stripped))
    if not lines:
        gate = "segment_lines_empty"
    elif not inter and not stripped_inter:
        gate = "segment_line_ids_disjoint_from_w4_primitives"
    elif inter:
        gate = "segment_line_ids_intersect_w4_primitives"
    else:
        gate = "segment_line_ids_intersect_w4_after_visible_strip_only"
    bridge = assess_segment_w4_namespace_bridge_variants(
        physical_opening_id=oid,
        segment_line_ids=lines,
        w4_primitive_ids=w4,
    )
    return {
        "physical_opening_id": oid,
        "first_remaining_gate": gate,
        "segment_line_id_count": len(lines),
        "usable_w4_primitive_id_count": len(w4),
        "exact_intersection_count": len(inter),
        "stripped_intersection_count": len(stripped_inter),
        "exact_intersection_ids": list(inter)[:32],
        "sample_segment_line_ids": list(lines)[:8],
        "sample_w4_primitive_ids": list(w4)[:8],
        "namespace_bridge_gate": bridge["first_remaining_gate"],
        "digit_tail_collision_count": bridge["digit_tail_collision_count"],
        "digit_tail_collision_sample": bridge["digit_tail_collision_sample"],
        "digit_tail_collision_pairs_sample": bridge["digit_tail_collision_pairs_sample"],
        "seg_vs_raster_segment_digit_tail_count": bridge[
            "seg_vs_raster_segment_digit_tail_count"],
        "seg_vs_d_index_digit_tail_count": bridge["seg_vs_d_index_digit_tail_count"],
        "w4_raster_segment_id_count": bridge["w4_raster_segment_id_count"],
        "w4_d_index_id_count": bridge["w4_d_index_id_count"],
        "namespace_taxonomy": bridge["taxonomy"],
        "host_granted": False,
        "nearest_wins_applied": False,
        "shadow_only": True,
    }
