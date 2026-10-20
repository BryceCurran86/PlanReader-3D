"""Segment↔W4 ID namespace taxonomy + variant bridges (shadow, no host).

Diagnostic only. Never grants host from prefix strip, digit extract, or
geometric proximity. Retains all candidates; abstains on ambiguity.
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from typing import Any
import re


_DIGIT_TAIL = re.compile(r"(\d+)$")
_D_INDEX = re.compile(r"^d(\d+)i0$", re.IGNORECASE)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _prefix_bucket(raw_id: str) -> str:
    text = _clean(raw_id)
    if not text:
        return "empty"
    if text.startswith("raster_opening_primitive:"):
        return "raster_opening_primitive"
    if text.startswith("raster_segment:"):
        return "raster_segment"
    if text.startswith("visible:"):
        return "visible_prefixed"
    if _D_INDEX.match(text):
        return "w4_d_index"
    if ":" in text:
        return f"colon_namespace:{text.split(':', 1)[0]}"
    return "plain_token"


def _digit_tail(raw_id: str) -> str | None:
    text = _clean(raw_id)
    if text.startswith("raster_opening_primitive:") or text.startswith("raster_segment:"):
        # ...:raster_wall_band_face:1467 or raster_segment:sha:1.0.0:1585 → last digit token
        tail = text.rsplit(":", 1)[-1]
        return tail if tail.isdigit() else None
    m = _D_INDEX.match(text)
    if m:
        return m.group(1)
    m2 = _DIGIT_TAIL.search(text)
    return m2.group(1) if m2 else None


def _ids_by_digit_tail(ids: Sequence[str]) -> dict[str, list[str]]:
    by_tail: dict[str, list[str]] = {}
    for raw in ids:
        text = _clean(raw)
        tail = _digit_tail(text)
        if not tail:
            continue
        by_tail.setdefault(tail, []).append(text)
    for tail in by_tail:
        by_tail[tail] = sorted(set(by_tail[tail]))
    return by_tail


def classify_id_namespace_taxonomy(
    *,
    segment_line_ids: Sequence[str],
    w4_primitive_ids: Sequence[str],
) -> dict[str, Any]:
    seg = [_clean(x) for x in segment_line_ids if _clean(x)]
    w4 = [_clean(x) for x in w4_primitive_ids if _clean(x)]
    seg_prefix = Counter(_prefix_bucket(x) for x in seg)
    w4_prefix = Counter(_prefix_bucket(x) for x in w4)
    return {
        "status": "UNPUBLISHED_SEGMENT_W4_ID_NAMESPACE_TAXONOMY",
        "segment_id_count": len(seg),
        "w4_id_count": len(w4),
        "segment_prefix_counts": dict(sorted(seg_prefix.items())),
        "w4_prefix_counts": dict(sorted(w4_prefix.items())),
        "host_granted": False,
        "shadow_only": True,
    }


def assess_segment_w4_namespace_bridge_variants(
    *,
    physical_opening_id: str,
    segment_line_ids: Sequence[str],
    w4_primitive_ids: Sequence[str],
) -> dict[str, Any]:
    """Try exact / visible-strip / digit-tail bridges; never pick a nearest host."""
    oid = _clean(physical_opening_id)
    if not oid:
        raise ValueError("physical opening identity required")
    seg = tuple(sorted({_clean(x) for x in segment_line_ids if _clean(x)}))
    w4 = tuple(sorted({_clean(x) for x in w4_primitive_ids if _clean(x)}))
    exact = set(seg) & set(w4)
    seg_strip = {
        x[len("visible:"):] if x.startswith("visible:") else x for x in seg
    }
    w4_strip = {
        x[len("visible:"):] if x.startswith("visible:") else x for x in w4
    }
    stripped = seg_strip & w4_strip
    seg_by_tail = _ids_by_digit_tail(seg)
    w4_by_tail = _ids_by_digit_tail(w4)
    digit_hits = sorted(set(seg_by_tail) & set(w4_by_tail))
    # Retain both ID forms for every colliding digit — never pick one side.
    collision_pairs = []
    for tail in digit_hits:
        collision_pairs.append({
            "digit_tail": tail,
            "segment_ids": seg_by_tail[tail],
            "w4_ids": w4_by_tail[tail],
            "selected_id": None,
        })
    w4_raster_segment = [x for x in w4 if x.startswith("raster_segment:")]
    w4_d_index = [x for x in w4 if _D_INDEX.match(x)]
    seg_vs_raster_segment_tails = sorted(
        set(seg_by_tail) & set(_ids_by_digit_tail(w4_raster_segment))
    )
    seg_vs_d_index_tails = sorted(
        set(seg_by_tail) & set(_ids_by_digit_tail(w4_d_index))
    )

    if exact:
        gate = "exact_id_intersection_review_only"
    elif stripped:
        gate = "visible_strip_intersection_review_only"
    elif digit_hits:
        # Digit-tail collisions are ambiguous across namespaces — abstain.
        gate = "digit_tail_collision_ambiguous_abstain"
    else:
        gate = "all_namespace_bridge_variants_disjoint"

    taxonomy = classify_id_namespace_taxonomy(
        segment_line_ids=seg, w4_primitive_ids=w4,
    )
    return {
        "physical_opening_id": oid,
        "first_remaining_gate": gate,
        "exact_intersection_count": len(exact),
        "stripped_intersection_count": len(stripped),
        "digit_tail_collision_count": len(digit_hits),
        "digit_tail_collision_sample": digit_hits[:12],
        "digit_tail_collision_pairs_sample": collision_pairs[:8],
        "seg_vs_raster_segment_digit_tail_count": len(seg_vs_raster_segment_tails),
        "seg_vs_d_index_digit_tail_count": len(seg_vs_d_index_tails),
        "seg_vs_raster_segment_digit_tails_sample": seg_vs_raster_segment_tails[:12],
        "seg_vs_d_index_digit_tails_sample": seg_vs_d_index_tails[:12],
        "w4_raster_segment_id_count": len(w4_raster_segment),
        "w4_d_index_id_count": len(w4_d_index),
        "taxonomy": {
            "segment_prefix_counts": taxonomy["segment_prefix_counts"],
            "w4_prefix_counts": taxonomy["w4_prefix_counts"],
        },
        "host_granted": False,
        "nearest_wins_applied": False,
        "measurement_published": False,
        "shadow_only": True,
    }


def summarize_namespace_bridge_rows(
    rows: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    gates: Counter[str] = Counter()
    for row in rows:
        gates[str(row.get("first_remaining_gate") or "")] += 1
    return {
        "status": "UNPUBLISHED_SEGMENT_W4_NAMESPACE_BRIDGE_SUMMARY",
        "opening_count": len(rows),
        "gate_counts": dict(sorted(gates.items())),
        "host_granted": False,
        "shadow_only": True,
    }
