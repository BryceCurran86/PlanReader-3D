"""Compare segment-parent line keys to usable W4 source_primitive_ids (shadow)."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any


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
        "host_granted": False,
        "shadow_only": True,
    }
