"""Source-native OUTER painted wall preflight; no image hull or site rectangle.

This stage runs before doorway / internal-wall tracing. A source-painted
closed perimeter can be a *candidate*, not a physical building wall until
source role and opening ownership are independently verified. Nothing issues
quantities and no guessed envelope filters inner walls.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from shapely.geometry import Polygon, box
from shapely.ops import unary_union

from pb_layered_wall_doorway_room_ring_shadow import (
    _collect_dark_painted_source_wall_strips,
    _collect_strips,
    _source_wall_ink_candidate_drawings,
)
from pb_new_wall_graph_diagnostic import (
    NativeWallGraphDiagnostic,
    inspect_native_wall_graph,
)
from pb_next_wall_ring_preview import (
    _collect_cavity_multi_face_strips,
    _collect_monotonic_source_stroke_pairs,
    _collect_source_heavy_stroke_strips,
    _collect_source_wide_face_pairs,
)
from pb_source_garage_door_footprint_continuity import (
    GarageDoorFootprintBridge,
    detect_exterior_garage_door_footprint_bridges,
)
from pb_source_neutral_wall_seam_continuity import (
    SourceNeutralWallSeam,
    detect_source_neutral_wall_seams,
)
from pb_source_shared_dwelling_envelope_shadow import (
    CandidateSharedBuildingDivider,
    closed_loop_uses_interior_dwelling_divider,
    detect_native_shared_dwelling_dividers,
)
from pb_source_unbounded_building_face_walk_shadow import (
    OutsideFacingBuildingWalk,
    walk_source_unbounded_building_face,
)
from pb_source_sliding_door_footprint_continuity import (
    ExteriorSlidingDoorFootprintBridge,
    detect_exterior_sliding_door_footprint_bridges,
)
from pb_source_wall_endpoint_aperture_review_shadow import (
    OriginalSourceWallEndpointAudit,
    reconcile_original_wall_ink_endpoints_with_hosted_apertures,
)
from pb_source_swing_door_footprint_continuity import (
    ExteriorSwingDoorFootprintBridge,
    detect_exterior_swing_door_footprint_bridges,
)
from pb_source_window_footprint_continuity import (
    WindowFootprintBridge,
    detect_exterior_window_footprint_bridges,
)


@dataclass(frozen=True)
class SourceNativeOuterWallAttempt:
    status: str
    reason: str
    polygon_pdf_pts: tuple[tuple[float, float], ...] = ()
    source_wall_path_ids: tuple[int, ...] = ()
    physical_wall_authenticated: bool = False
    internal_wall_filter_authorized: bool = False
    measurement_authorized: bool = False
    source_wall_band_count: int = 0
    source_stroke_pair_band_count: int = 0
    source_heavy_stroke_band_count: int = 0
    source_cavity_multi_face_band_count: int = 0
    source_wide_face_pair_band_count: int = 0
    source_wall_path_count: int = 0
    graph: NativeWallGraphDiagnostic = field(default_factory=NativeWallGraphDiagnostic)
    window_footprint_bridges: tuple[WindowFootprintBridge, ...] = ()
    garage_door_footprint_bridges: tuple[GarageDoorFootprintBridge, ...] = ()
    swing_door_footprint_bridges: tuple[ExteriorSwingDoorFootprintBridge, ...] = ()
    sliding_door_footprint_bridges: tuple[ExteriorSlidingDoorFootprintBridge, ...] = ()
    rejected_candidate_bbox_pdf_pts: tuple[float, float, float, float] | None = None
    diagnostic_closed_wall_loop_count: int = 0
    diagnostic_rejected_loop_bbox_pdf_pts: tuple[float, float, float, float] | None = None
    diagnostic_wall_bands_outside_loop: int = 0
    diagnostic_outside_source_path_sample: tuple[int, ...] = ()
    neutral_wall_seams: tuple[SourceNeutralWallSeam, ...] = ()
    # One connected BUILDING may contain two (or more) DWELLINGS. Never
    # misclassify an annotated internal PARTY wall as outside envelope.
    shared_dwelling_divider_candidates: tuple[CandidateSharedBuildingDivider, ...] = ()
    diagnostic_party_wall_bounded_unit_loops: int = 0
    source_outside_face_walk: OutsideFacingBuildingWalk | None = None
    source_wall_endpoint_aperture_review: OriginalSourceWallEndpointAudit = field(
        default_factory=OriginalSourceWallEndpointAudit
    )


def attempt_source_native_outer_wall_first(
    drawings: Sequence[Mapping[str, Any]],
    *,
    baseline_source_drawings: Sequence[Mapping[str, Any]] | None = None,
    source_ink_already_scoped: bool = False,
    source_words: Sequence[Mapping[str, Any] | Sequence[Any]] = (),
    window_source_drawings: Sequence[Mapping[str, Any] | object] | None = None,
    source_page_index: int = -1,
) -> SourceNativeOuterWallAttempt:
    """Find one joined perimeter in *source wall fills*, NOT the sheet bbox.

    Only accepts a continuous source-painted wall band with an interior hole.
    Requires all other painted structural wall bands be contained inside the
    candidate. Ambiguous outer candidates and separate wings fail closed.
    This is deliberately stricter than a raster contour or concave hull.
    """
    if type(source_ink_already_scoped) is not bool:
        raise ValueError("source_ink_already_scoped_must_be_bool")
    if type(source_page_index) is not int or source_page_index < -1:
        raise ValueError("source_page_index_invalid")
    # The preview already applies original source-negative paint hygiene.
    # Reapplying its original black-only mask here would silently discard
    # the newly recovered neutral-grey paths.
    wall_ink = (
        tuple(drawings)
        if source_ink_already_scoped
        else _source_wall_ink_candidate_drawings(drawings)[0]
    )
    strict_ink = None
    if baseline_source_drawings is not None:
        if len(baseline_source_drawings) != len(drawings):
            raise ValueError("source_pair_baseline_path_identity_length_mismatch")
        strict_ink = (
            tuple(baseline_source_drawings)
            if source_ink_already_scoped
            else _source_wall_ink_candidate_drawings(baseline_source_drawings)[0]
        )
    named, _other = _collect_strips(wall_ink)
    dark = _collect_dark_painted_source_wall_strips(wall_ink)
    # Architectural walls can be two separate native ink strokes, not opaque
    # filled rectangles. The original preflight omitted them entirely.
    # Source paired faces are candidates, NEVER automatically physical walls.
    paired = _collect_monotonic_source_stroke_pairs(wall_ink, strict_ink)
    # Preserve native thick-line paint. Those source strokes are physical
    # wall candidates, not inferred or double-line approximations.
    thick = _collect_source_heavy_stroke_strips(wall_ink)
    cavity = _collect_cavity_multi_face_strips(wall_ink)
    wide_pairs = _collect_source_wide_face_pairs(wall_ink)
    bars = named + dark + paired + thick + cavity + wide_pairs
    unique_bars = {}
    for bar in bars:
        if bar.polygon is None or bar.polygon.is_empty or not bar.polygon.is_valid:
            continue
        key = (
            int(bar.path_index),
            *(round(float(v), 4) for v in bar.polygon.bounds),
        )
        unique_bars[key] = bar
    bars = list(unique_bars.values())
    graph = inspect_native_wall_graph(bars, source_drawings=wall_ink)
    # Windows are holes in wall paint but NOT holes in the exterior footprint.
    # The synthetic bridging solids below exist only in this topology union;
    # they are never emitted as wall, frame, length or customer quantities.
    opening_drawings = window_source_drawings if window_source_drawings is not None else wall_ink
    window_bridges = detect_exterior_window_footprint_bridges(
        opening_drawings, source_words, page_index=source_page_index, wall_bars=bars,
    ) if source_words else ()
    garage_bridges = detect_exterior_garage_door_footprint_bridges(
        opening_drawings, source_words, page_index=source_page_index,
    ) if source_words else ()
    swing_bridges = detect_exterior_swing_door_footprint_bridges(
        opening_drawings, source_words, page_index=source_page_index,
    )
    sliding_bridges = detect_exterior_sliding_door_footprint_bridges(
        opening_drawings, source_words, page_index=source_page_index, wall_bars=bars,
    ) if source_words else ()
    seam_candidates = detect_source_neutral_wall_seams(
        opening_drawings, page_index=source_page_index,
    )
    party_dividers = (
        detect_native_shared_dwelling_dividers(
            opening_drawings,
            source_words,
            source_page_index=source_page_index,
        )
        if source_words
        else ()
    )
    source_bar_paths = {path for bar in bars for path in bar.native_path_indices()}
    window_bridges = tuple(
        bridge for bridge in window_bridges
        if (
            (bridge.left_host_path_id in source_bar_paths and bridge.right_host_path_id in source_bar_paths)
            or (0 <= bridge.left_host_path_id < len(opening_drawings) and 0 <= bridge.right_host_path_id < len(opening_drawings))
        )
    )
    garage_bridges = tuple(
        bridge for bridge in garage_bridges
        if bridge.start_host_path_id in source_bar_paths
        and bridge.end_host_path_id in source_bar_paths
    )
    # The general wall-band collector can exclude legitimate short
    # jamb-side painted wall ends. A swing bridge already proves the two
    # native dark wall faces + their arc and separate caps. Require these
    # source faces to survive the wall-ink scope, but do NOT require a
    # commercial/measurement wall-strip issuer to have accepted them.
    swing_bridges = tuple(
        bridge for bridge in swing_bridges
        if all(
            0 <= idx < len(wall_ink)
            and isinstance(wall_ink[idx], Mapping)
            and wall_ink[idx].get("fill") is not None
            and max(wall_ink[idx]["fill"][:3]) < .3
            and wall_ink[idx].get("layer") == opening_drawings[idx].get("layer")
            for idx in (bridge.first_host_path_id, bridge.second_host_path_id)
        )
    )
    sliding_bridges = tuple(
        bridge for bridge in sliding_bridges
        if (
            (bridge.first_host_path_id in source_bar_paths and bridge.second_host_path_id in source_bar_paths)
            or all(
                0 <= idx < len(wall_ink)
                and isinstance(wall_ink[idx], Mapping)
                and wall_ink[idx].get("fill") is not None
                and max(wall_ink[idx]["fill"][:3]) < .3
                and wall_ink[idx].get("layer") == opening_drawings[idx].get("layer")
                for idx in (bridge.first_host_path_id, bridge.second_host_path_id)
            )
        )
    )
    # A native GREY wall infill is actual source paint, not a distance
    # snap. Preserve only when all its path owners survive the original
    # page source filter and remain on the same source wall layer.
    # Grey fills are not black wall bars; the source detector must prove
    # the independently hosted original black faces and same-layer grey seam.

    neutral_seams = tuple(
        seam for seam in seam_candidates
        if all(
            0 <= idx < len(wall_ink)
            and isinstance(wall_ink[idx], Mapping)
            and wall_ink[idx].get("fill") is not None
            and .3 < min(wall_ink[idx]["fill"][:3]) < .75
            and wall_ink[idx].get("layer") == opening_drawings[idx].get("layer")
            for idx in seam.neutral_fill_path_ids
        )
        # Short, source-painted black wall faces can be omitted by the
        # commercial wall-strip collector. The native seam detector has
        # already proved unique wall-layer/dark-host/full-grey-fill geometry;
        # require original source identity here, not a separate billable strip.
        and all(
            0 <= idx < len(wall_ink)
            and isinstance(wall_ink[idx], Mapping)
            and wall_ink[idx].get("fill") is not None
            and max(wall_ink[idx]["fill"][:3]) < .3
            and wall_ink[idx].get("layer") == opening_drawings[idx].get("layer")
            for idx in (seam.first_host_path_id, seam.second_host_path_id)
        )
    )
    # Only source-dark verified jamb-side bodies are included in this
    # TOPOLOGY union, never in customer wall area or published quantities.
    door_host_ink = tuple(
        box(*wall_ink[idx]["rect"])
        for idx in sorted({
            path
            for bridge in (*swing_bridges, *sliding_bridges)
            for path in (bridge.first_host_path_id, bridge.second_host_path_id)
            if path not in source_bar_paths
        })
    )
    counts = {
        "window_footprint_bridges": window_bridges,
        "garage_door_footprint_bridges": garage_bridges,
        "swing_door_footprint_bridges": swing_bridges,
        "sliding_door_footprint_bridges": sliding_bridges,
        "neutral_wall_seams": neutral_seams,
        "shared_dwelling_divider_candidates": party_dividers,
        "graph": graph,
        "source_wall_band_count": len(bars),
        "source_stroke_pair_band_count": len(paired),
        "source_heavy_stroke_band_count": len(thick),
        "source_cavity_multi_face_band_count": len(cavity),
        "source_wide_face_pair_band_count": len(wide_pairs),
        "source_wall_path_count": len({
            path for bar in bars for path in bar.native_path_indices()
        }),
    }

    def _review(source_wall_union=None):
        # The graph above runs BEFORE hosted openings. Its raw source-ink
        # tips are not automatically missing walls; classify terminals
        # covered by original SOURCE-DARK wall hosts, EXISTING native
        # aperture receipts, then the post-aperture union / unique owner
        # layer. Never modify the graph or add an aperture/wall.
        return reconcile_original_wall_ink_endpoints_with_hosted_apertures(
            graph,
            source_page_index=source_page_index,
            original_source_drawings=opening_drawings,
            existing_native_aperture_bridges=(
                *window_bridges, *garage_bridges, *swing_bridges, *sliding_bridges,
            ),
            source_wall_union=source_wall_union,
            wall_bars=bars,
        )

    if len(bars) < 4:
        counts["source_wall_endpoint_aperture_review"] = _review()
        return SourceNativeOuterWallAttempt(
            "ABSTAINED", "source_exterior_continuous_wall_band_not_found",
            **counts,
        )
    union = unary_union(
        [bar.polygon for bar in bars]
        + [box(*bridge.bounds_pdf_pts) for bridge in window_bridges]
        + [box(*bridge.bounds_pdf_pts) for bridge in garage_bridges]
        + [box(*bridge.bounds_pdf_pts) for bridge in swing_bridges]
        + [box(*bridge.bounds_pdf_pts) for bridge in sliding_bridges]
        + [box(*seam.bounds_pdf_pts) for seam in neutral_seams]
        + list(door_host_ink)
    )
    counts["source_wall_endpoint_aperture_review"] = _review(union)
    # No duplicate original-page decode/union. This outside-face walker
    # reuses the source-native wall-and-hosted-opening network computed above.
    # The outside is one building face, never a party-wall-bounded unit face.
    if party_dividers:
        counts["source_outside_face_walk"] = walk_source_unbounded_building_face(
            bars, source_words,
            shared_dividers=party_dividers,
            source_wall_union=union,
        )
    polygons = list(union.geoms) if hasattr(union, "geoms") else [union]
    # A true wall-band perimeter has an interior void. Open-ended lines,
    # dimension ticks and boxed landscape art cannot be promoted by hull.
    closed = [
        part for part in polygons
        if isinstance(part, Polygon)
        and part.is_valid
        and len(part.interiors) >= 1
        and len(part.exterior.coords) >= 5
    ]
    if len(closed) != 1:
        return SourceNativeOuterWallAttempt(
            "ABSTAINED", "source_exterior_perimeter_not_unique_and_closed",
            diagnostic_closed_wall_loop_count=len(closed),
            **counts,
        )
    outer = closed[0]
    # A building-wall union may have a fully closed VOID on either side
    # of an internal party wall. Such an interior ring is not the shared
    # outside footprint. Track this proof separately; NEVER promote the
    # first/leftmost closed room loop to a building envelope.
    divider_bounded_unit_loops = sum(
        closed_loop_uses_interior_dwelling_divider(
            Polygon(hole),
            party_dividers,
        )
        for hole in outer.interiors
    )
    party_wall_misused_as_outer_boundary = closed_loop_uses_interior_dwelling_divider(
        outer,
        party_dividers,
    )
    if outer.area <= 0 or not math.isfinite(outer.area):
        return SourceNativeOuterWallAttempt(
            "ABSTAINED", "source_exterior_perimeter_not_finite",
            **counts,
        )
    # A single ROOM perimeter with other walls beyond it is not the outer
    # building boundary. Proven ALFRESCO/PORCH/POST labels may leave the
    # envelope; Living/Bed/garage structure may not. Never x-crop leftovers.
    from pb_source_outer_house_continuity_shadow import bar_proven_outside_envelope

    expanded_outer = outer.buffer(.05)
    outside_bars = [
        bar for bar in bars if not expanded_outer.covers(bar.polygon)
    ]
    structural_outside = [
        bar for bar in outside_bars
        if not bar_proven_outside_envelope(bar, wall_ink, source_words)
    ]
    if structural_outside:
        # The short receipt contains actual original path_index owners for
        # rejected source wall BANDS; composite bars may reference many more
        # primitive paths. A bounded first-seen owner sample is readable on
        # the original drawing, and never authorizes any physical wall area.
        bbox = tuple(round(float(v), 3) for v in outer.bounds)
        outside_source_paths = tuple(
            dict.fromkeys(int(bar.path_index) for bar in structural_outside)
        )
        return SourceNativeOuterWallAttempt(
            "ABSTAINED",
            (
                "source_party_wall_is_internal_not_building_outer_boundary"
                if party_wall_misused_as_outer_boundary
                else "source_exterior_other_wall_ink_outside_candidate"
            ),
            rejected_candidate_bbox_pdf_pts=bbox,
            diagnostic_closed_wall_loop_count=len(closed),
            diagnostic_party_wall_bounded_unit_loops=divider_bounded_unit_loops,
            diagnostic_rejected_loop_bbox_pdf_pts=bbox,
            diagnostic_wall_bands_outside_loop=len(structural_outside),
            diagnostic_outside_source_path_sample=outside_source_paths[:32],
            **counts,
        )
    if party_wall_misused_as_outer_boundary:
        return SourceNativeOuterWallAttempt(
            "ABSTAINED",
            "source_party_wall_is_internal_not_building_outer_boundary",
            diagnostic_closed_wall_loop_count=len(closed),
            diagnostic_party_wall_bounded_unit_loops=divider_bounded_unit_loops,
            **counts,
        )
    # Party-wall adjacency must prove TWO enclosed dwelling domains before
    # the common building perimeter can be even a geometry CANDIDATE.
    # A left-hand unit loop returning home is NOT this outside face.
    if party_dividers and (
        counts["source_outside_face_walk"].status != "CANDIDATE"
    ):
        return SourceNativeOuterWallAttempt(
            "ABSTAINED",
            counts["source_outside_face_walk"].reason,
            diagnostic_closed_wall_loop_count=len(closed),
            diagnostic_party_wall_bounded_unit_loops=divider_bounded_unit_loops,
            **counts,
        )
    points = tuple(
        (round(float(x), 3), round(float(y), 3))
        for x, y in list(outer.exterior.coords)[:-1]
    )
    sources = tuple(sorted({
        int(bar.path_index) for bar in bars
        if outer.boundary.distance(bar.polygon) <= 0.05
    }))
    if len(points) < 4 or len(sources) < 4:
        return SourceNativeOuterWallAttempt(
            "ABSTAINED", "source_exterior_wall_path_owners_incomplete",
            **counts,
        )
    return SourceNativeOuterWallAttempt(
        "CANDIDATE", "source_closed_painted_wall_ring_needs_exterior_role_authentication",
        points, sources,
        source_wall_band_count=counts["source_wall_band_count"],
        source_stroke_pair_band_count=counts["source_stroke_pair_band_count"],
        source_heavy_stroke_band_count=counts["source_heavy_stroke_band_count"],
        source_cavity_multi_face_band_count=counts["source_cavity_multi_face_band_count"],
        source_wide_face_pair_band_count=counts["source_wide_face_pair_band_count"],
        source_wall_path_count=counts["source_wall_path_count"],
        graph=graph,
        window_footprint_bridges=window_bridges,
        garage_door_footprint_bridges=garage_bridges,
        swing_door_footprint_bridges=swing_bridges,
        sliding_door_footprint_bridges=sliding_bridges,
        neutral_wall_seams=neutral_seams,
        diagnostic_closed_wall_loop_count=len(closed),
        diagnostic_party_wall_bounded_unit_loops=divider_bounded_unit_loops,
        diagnostic_wall_bands_outside_loop=0,
    )
