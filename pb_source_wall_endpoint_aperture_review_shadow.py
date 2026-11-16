"""Read-only original wall-terminal review AFTER native aperture detection.

Wall ink is intentionally discontinuous at real windows/doors. The raw
largest-wall-component graph runs BEFORE source-hosted opening bridges
are applied and must not be mistaken for the final exterior trace. This
module tags original unconnected wall endpoints already covered by the
EXISTING verified window, garage, swing and sliding source receipts.
It NEVER draws a new wall, changes connectivity or approves quantities.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from shapely.geometry import Point, box

from pb_new_wall_graph_diagnostic import NativeWallGraphDiagnostic
from pb_source_window_footprint_continuity import WindowFootprintBridge
from pb_source_garage_door_footprint_continuity import GarageDoorFootprintBridge
from pb_source_swing_door_footprint_continuity import ExteriorSwingDoorFootprintBridge
from pb_source_sliding_door_footprint_continuity import (
    ExteriorSlidingDoorFootprintBridge,
)


@dataclass(frozen=True)
class OriginalSourceWallEndpointReview:
    endpoint_pdf_pts: tuple[float, float]
    status: str
    original_aperture_kind: str | None = None
    original_host_path_ids: tuple[int, int] = ()
    original_aperture_bounds_pdf_pts: tuple[float, float, float, float] | None = None
    physical_wall_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint_pdf_pts": list(self.endpoint_pdf_pts),
            "status": self.status,
            "original_aperture_kind": self.original_aperture_kind,
            "original_host_path_ids": list(self.original_host_path_ids),
            "original_aperture_bounds_pdf_pts": (
                list(self.original_aperture_bounds_pdf_pts)
                if self.original_aperture_bounds_pdf_pts
                else None
            ),
            "physical_wall_authenticated": False,
            "measurement_authorized": False,
        }


@dataclass(frozen=True)
class OriginalSourceWallEndpointAudit:
    endpoint_reviews: tuple[OriginalSourceWallEndpointReview, ...] = ()
    source_hosted_aperture_terminal_count: int = 0
    source_unmatched_wall_ink_terminal_count: int = 0
    source_ambiguous_aperture_terminal_count: int = 0
    source_closed_outer_footprint_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "endpoint_reviews": [x.to_dict() for x in self.endpoint_reviews],
            "source_hosted_aperture_terminal_count": self.source_hosted_aperture_terminal_count,
            "source_unmatched_wall_ink_terminal_count": self.source_unmatched_wall_ink_terminal_count,
            "source_ambiguous_aperture_terminal_count": self.source_ambiguous_aperture_terminal_count,
            "source_closed_outer_footprint_authenticated": False,
            "measurement_authorized": False,
        }


_TYPE_KIND_HOSTS = (
    (WindowFootprintBridge, "window", "left_host_path_id", "right_host_path_id"),
    (GarageDoorFootprintBridge, "garage", "start_host_path_id", "end_host_path_id"),
    (
        ExteriorSwingDoorFootprintBridge,
        "swing",
        "first_host_path_id",
        "second_host_path_id",
    ),
    (
        ExteriorSlidingDoorFootprintBridge,
        "sliding",
        "first_host_path_id",
        "second_host_path_id",
    ),
)
_SOURCE_WALL_LAYERS = frozenset(("Enclosure_WallExternal", "Enclosure_WallInternal"))


def _original_dark_wall_host(
    drawing: Mapping[str, Any] | object,
) -> tuple[tuple[float, float, float, float], str, str] | None:
    if (
        not isinstance(drawing, Mapping)
        or str(drawing.get("layer") or "") not in _SOURCE_WALL_LAYERS
    ):
        return None
    fill = drawing.get("fill")
    if not isinstance(fill, (tuple, list)) or len(fill) < 3:
        return None
    try:
        if not all(math.isfinite(float(v)) and 0 <= float(v) < 0.3 for v in fill[:3]):
            return None
        rect = tuple(float(v) for v in drawing.get("rect"))
        if len(rect) != 4 or not all(math.isfinite(v) for v in rect):
            return None
        if rect[2] <= rect[0] or rect[3] <= rect[1]:
            return None
    except (TypeError, ValueError, OverflowError):
        return None
    viewport = str(
        drawing.get("source_viewport_id") or drawing.get("viewport_id") or ""
    )
    return rect, str(drawing["layer"]), viewport


def _source_hosted_aperture(
    bridge: object,
    drawings: Sequence[Mapping[str, Any] | object],
    source_page_index: int,
):
    match = next(
        (
            (kind, left, right)
            for cls, kind, left, right in _TYPE_KIND_HOSTS
            if type(bridge) is cls
        ),
        None,
    )
    if match is None:
        return None
    kind, left_name, right_name = match
    try:
        if (
            type(getattr(bridge, "page_index")) is not int
            or bridge.page_index != source_page_index
        ):
            return None
        ids = (int(getattr(bridge, left_name)), int(getattr(bridge, right_name)))
        bounds = tuple(float(v) for v in bridge.bounds_pdf_pts)
        axis = str(bridge.axis)
        if (
            len(bounds) != 4
            or not all(math.isfinite(v) for v in bounds)
            or bounds[0] >= bounds[2]
            or bounds[1] >= bounds[3]
            or axis not in ("h", "v")
            or ids[0] == ids[1]
            or any(idx < 0 or idx >= len(drawings) for idx in ids)
        ):
            return None
        hosts = tuple(_original_dark_wall_host(drawings[idx]) for idx in ids)
        if any(host is None for host in hosts):
            return None
        layers = {h[1] for h in hosts}
        viewports = {h[2] for h in hosts if h[2]}
        if len(layers) != 1 or len(viewports) > 1:
            return None
    except (TypeError, ValueError, AttributeError, OverflowError):
        return None
    return kind, ids, bounds, hosts


def reconcile_original_wall_ink_endpoints_with_hosted_apertures(
    graph: NativeWallGraphDiagnostic,
    *,
    source_page_index: int,
    original_source_drawings: Sequence[Mapping[str, Any] | object],
    existing_native_aperture_bridges: Sequence[object],
    proximity_pdf_pt: float = 0.16,
) -> OriginalSourceWallEndpointAudit:
    """Post-opening endpoint triage; output cannot change raw graph status.

    Original dark host pair AND unique source hosted aperture receipt
    required to classify one gap as an existing aperture; source-only
    near-misses/annotations are NEVER new filled physical walls.
    """
    if not isinstance(graph, NativeWallGraphDiagnostic):
        return OriginalSourceWallEndpointAudit()
    if type(source_page_index) is not int or source_page_index < 0:
        return OriginalSourceWallEndpointAudit()
    if not math.isfinite(proximity_pdf_pt) or not 0 <= proximity_pdf_pt <= 0.5:
        return OriginalSourceWallEndpointAudit()
    candidates = [
        proof
        for bridge in existing_native_aperture_bridges
        if (
            proof := _source_hosted_aperture(
                bridge, original_source_drawings, source_page_index
            )
        )
        is not None
    ]
    reviews = []
    for raw in graph.largest_component_open_endpoints_pdf_pts:
        try:
            x, y = (float(raw[0]), float(raw[1]))
            if not (math.isfinite(x) and math.isfinite(y)):
                continue
        except (TypeError, ValueError, IndexError, OverflowError):
            continue
        pt = Point(x, y)
        found = {}
        for kind, ids, bounds, hosts in candidates:
            if pt.distance(box(*bounds)) > proximity_pdf_pt:
                continue
            # A graphical aperture vicinity alone is not enough; this
            # terminal must also touch an original SOURCE DARK physical
            # host, not a nearby floor-ink, furniture or roof bar.
            if min(pt.distance(box(*h[0])) for h in hosts) > proximity_pdf_pt:
                continue
            found[(kind, ids, bounds)] = (kind, ids, bounds)
        if len(found) == 1:
            kind, ids, bounds = next(iter(found.values()))
            reviews.append(
                OriginalSourceWallEndpointReview(
                    (x, y),
                    "source_hosted_aperture_terminal_candidate",
                    kind,
                    ids,
                    bounds,
                )
            )
        elif len(found) > 1:
            reviews.append(
                OriginalSourceWallEndpointReview(
                    (x, y),
                    "ambiguous_competing_hosted_apertures",
                )
            )
        else:
            reviews.append(
                OriginalSourceWallEndpointReview(
                    (x, y),
                    "unmatched_raw_wall_ink_terminal_needs_post_opening_review",
                )
            )
    rows = tuple(reviews)
    return OriginalSourceWallEndpointAudit(
        endpoint_reviews=rows,
        source_hosted_aperture_terminal_count=sum(
            x.status == "source_hosted_aperture_terminal_candidate" for x in rows
        ),
        source_unmatched_wall_ink_terminal_count=sum(
            x.status == "unmatched_raw_wall_ink_terminal_needs_post_opening_review"
            for x in rows
        ),
        source_ambiguous_aperture_terminal_count=sum(
            x.status == "ambiguous_competing_hosted_apertures" for x in rows
        ),
    )
