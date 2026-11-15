"""Extra near-black vector source candidates for NEW tracing only.

A CAD export may render real walls in RGB .09-.10 gray instead of 0.0.
Original commercial wall authority remains unchanged; this source gate is
only a noncommercial tracing shadow. Never admit colored, faint, green, white,
transparent, or weakly described content as a source wall.
"""
from __future__ import annotations

import math
from typing import Any, Mapping, Sequence

_SOURCE_DARK_GREY_MAX = .12
_SOURCE_NEUTRAL_SPREAD = .015


def is_source_neutral_dark(color: Any) -> bool:
    return (
        isinstance(color,(tuple,list))
        and len(color)==3
        and all(
            type(v) in (float,int) and math.isfinite(v)
            and 0 <= v <= _SOURCE_DARK_GREY_MAX
            for v in color
        )
        and max(color)-min(color) <= _SOURCE_NEUTRAL_SPREAD
    )


def include_source_neutral_dark_strokes(
    original: Sequence[Mapping[str,Any]],
    strict_mask: Sequence[Mapping[str,Any]],
) -> tuple[tuple[Mapping[str,Any],...],int]:
    """Add only source-owned opaque neutral-dark strokes after strict original gate.

    No page offset, no path-ID renumber, no fallback to raster hull.
    """
    if len(original)!=len(strict_mask):
        raise ValueError("source_native_path_identity_length_mismatch")
    output=[]
    added=0
    for row, old in zip(original,strict_mask):
        if old.get("items"):
            output.append(old)
            continue
        opacity = row.get("stroke_opacity", 1.) if isinstance(row, Mapping) else None
        if (
            isinstance(row, Mapping)
            and row.get("fill") is None
            and is_source_neutral_dark(row.get("color"))
            and type(opacity) in (int, float)
            and math.isfinite(opacity)
            and opacity >= .95
            and row.get("items")
        ):
            output.append(row)
            added+=1
        else:
            output.append(old)
    return tuple(output),added
