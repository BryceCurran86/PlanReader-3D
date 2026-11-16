"""Read-only: attach painted physical wall ends to existing CS/robe closures.

A sliding-door leaf and pocket are not a deleted wall. Source-painted dark
structural wall *ends* can corroborate an existing candidate opening; they
never authenticate a room, wall height, opening area or customer quantity.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from pb_next_wall_ring_preview import (
    KIND_CAVITY_SLIDER,
    KIND_SLIDING_LEAF,
    LayeredDoorwayClosure,
)

_WALL_LAYERS = frozenset({"Enclosure_WallInternal", "Enclosure_WallExternal"})


@dataclass(frozen=True)
class NativeWallHostsBesideSlidingClosure:
    closure_id: str
    kind: str
    page_index: int
    source_sha256: str
    wall_host_path_ids: tuple[int, int]
    wall_source_layer: str
    gap_interval_pdf_pts: tuple[float, float]
    band_pdf_pts: tuple[float, float]
    wall_role: str = "source_painted_wall_ends"
    sliding_role: str = "pocket_and_aperture_not_opaque_wall"
    physical_room_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "closure_id": self.closure_id,
            "kind": self.kind,
            "page_index": self.page_index,
            "source_sha256": self.source_sha256,
            "wall_host_path_ids": list(self.wall_host_path_ids),
            "wall_source_layer": self.wall_source_layer,
            "gap_interval_pdf_pts": list(self.gap_interval_pdf_pts),
            "band_pdf_pts": list(self.band_pdf_pts),
            "wall_role": self.wall_role,
            "sliding_role": self.sliding_role,
            "physical_room_authenticated": False,
            "measurement_authorized": False,
        }


def _rect(row: Mapping[str, Any]) -> tuple[float, float, float, float] | None:
    v = row.get("rect")
    if v is None:
        return None
    try:
        x0, y0, x1, y1 = [float(t) for t in v]
    except (TypeError, ValueError, OverflowError):
        return None
    if not all(map(math.isfinite, (x0, y0, x1, y1))) or x0 >= x1 or y0 >= y1:
        return None
    return x0, y0, x1, y1


def _dark_source_fill(row: Mapping[str, Any]) -> bool:
    if str(row.get("layer") or "") not in _WALL_LAYERS:
        return False
    if row.get("type") != "f":
        return False
    rgb = row.get("fill")
    try:
        return (
            isinstance(rgb, (tuple, list))
            and len(rgb) >= 3
            and all(math.isfinite(float(c)) and 0 <= float(c) < 0.3 for c in rgb[:3])
        )
    except (ValueError, TypeError, OverflowError):
        return False


def corroborate_native_wall_ends_at_existing_slider(
    closure: LayeredDoorwayClosure,
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    source_sha256: str,
    page_index: int,
    endpoint_tolerance_pdf_pt: float = 0.15,
) -> NativeWallHostsBesideSlidingClosure | None:
    """Require two UNIQUE original dark physical wall owners at slider ends.

    Retains semantic separation: physical wall outside the clear aperture,
    door leaf/pocket inside assembly; NEVER converts a door span to opaque
    material, infers wall above the frame, closes a metric room or publishes.
    """
    if not isinstance(closure, LayeredDoorwayClosure):
        return None
    if closure.kind not in (KIND_CAVITY_SLIDER, KIND_SLIDING_LEAF):
        return None
    if not (
        type(source_sha256) is str
        and len(source_sha256) == 64
        and all(x in "0123456789abcdef" for x in source_sha256)
        and type(page_index) is int
        and page_index >= 0
    ):
        return None
    # Printed CS word, or two separately native-drawn sliding frame paths.
    if closure.kind == KIND_CAVITY_SLIDER and not closure.native_word_refs:
        return None
    if closure.kind == KIND_SLIDING_LEAF and len(set(closure.native_path_indices)) < 2:
        return None
    if len(closure.band) != 2 or len(closure.gap_interval) != 2:
        return None
    low, high = closure.gap_interval
    norm0, norm1 = closure.band
    if not all(math.isfinite(x) for x in (low, high, norm0, norm1)):
        return None
    if low >= high or norm0 >= norm1 or not 0.7 < norm1 - norm0 < 8:
        return None

    first: list[tuple[int, str, str]] = []
    second: list[tuple[int, str, str]] = []
    middle = []
    for idx, raw in enumerate(drawings):
        if not isinstance(raw, Mapping) or not _dark_source_fill(raw):
            continue
        rect = _rect(raw)
        if rect is None:
            continue
        x0, y0, x1, y1 = rect
        a0, a1, b0, b1 = (x0, x1, y0, y1) if closure.horizontal else (y0, y1, x0, x1)
        thickness = b1 - b0
        length = a1 - a0
        if not 0.7 <= thickness <= 8 or length < max(0.6, 0.5 * thickness):
            continue
        overlap = min(b1, norm1) - max(b0, norm0)
        if overlap < 0.8 * min(thickness, norm1 - norm0):
            continue
        layer = str(raw.get("layer"))
        scope = str(
            raw.get("source_viewport_id") or raw.get("viewport_id") or ""
        ).strip()
        if abs(a1 - low) <= endpoint_tolerance_pdf_pt and a0 < low - 0.5:
            first.append((idx, layer, scope))
        if abs(a0 - high) <= endpoint_tolerance_pdf_pt and a1 > high + 0.5:
            second.append((idx, layer, scope))
        # Full-width or middle wall ink cannot be relabelled a doorway.
        if a0 <= low + 1 and a1 >= high - 1:
            middle.append(idx)
    if middle or len(first) != 1 or len(second) != 1:
        return None
    l, r = first[0], second[0]
    if l[0] == r[0] or l[1] != r[1]:
        return None
    if l[2] and r[2] and l[2] != r[2]:
        return None
    return NativeWallHostsBesideSlidingClosure(
        closure_id=closure.closure_id,
        kind=closure.kind,
        page_index=page_index,
        source_sha256=source_sha256,
        wall_host_path_ids=(l[0], r[0]),
        wall_source_layer=l[1],
        gap_interval_pdf_pts=tuple(float(z) for z in closure.gap_interval),
        band_pdf_pts=tuple(float(z) for z in closure.band),
    )
