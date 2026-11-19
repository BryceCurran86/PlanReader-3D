"""Production-reachable #4443 fabricated-box collapse + typed room closure.

Owner defect: two unsupported rectangular excursions on a straight exterior
wall must collapse to one continuous source-backed face; genuine alcoves with
paired wall ink stay; typed doorway/slider gaps close rooms for topology only.

Wires existing shadow collapse + structural room-region helpers into the
original footprint/extractor path. Never FIRM, never customer area.
"""
from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_source_unsupported_rectangular_detour_shadow import (
    collapse_unsupported_rectangular_detours,
    wall_ink_segments_from_drawings,
)
from pb_structural_room_region_shadow import derive_structural_room_regions
from pb_structural_wall_ink_shadow import (
    OpeningGapCandidate,
    StructuralInkDecision,
    StructuralWallInkReport,
    WALL_NETWORK_INK_CANDIDATE,
)


@dataclass(frozen=True)
class FabricatedBoxClosureReceipt:
    status: str
    reason: str
    collapsed_detour_count: int = 0
    polygon_pdf_pts: tuple[tuple[float, float], ...] = ()
    room_region_count: int = 0
    doorway_closure_count: int = 0
    suppressed_false_gap_count: int = 0
    unclosed_gap_diagnostics: tuple[dict[str, object], ...] = ()
    open_plan_merged: bool = False
    topology_only: bool = True
    measurement_authorized: bool = False
    commercial_publishable: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "reason": self.reason,
            "collapsed_detour_count": self.collapsed_detour_count,
            "polygon_pdf_pts": [list(p) for p in self.polygon_pdf_pts],
            "room_region_count": self.room_region_count,
            "doorway_closure_count": self.doorway_closure_count,
            "suppressed_false_gap_count": self.suppressed_false_gap_count,
            "unclosed_gap_diagnostics": [dict(d) for d in self.unclosed_gap_diagnostics],
            "open_plan_merged": self.open_plan_merged,
            "topology_only": True,
            "doorway_closure_is_not_physical_wall": True,
            "measurement_authorized": False,
            "commercial_publishable": False,
            "official_frozen120_score_change": 0,
            "owner_issue": 4443,
        }


def _ink_report_for_segments(
    segments: Sequence[Mapping[str, Any]],
    gaps: Sequence[OpeningGapCandidate],
) -> StructuralWallInkReport:
    decisions = tuple(
        StructuralInkDecision(
            str(seg["id"]),
            WALL_NETWORK_INK_CANDIDATE,
            ("source_positive_wall_network",),
            None,
            1,
        )
        for seg in segments
    )
    return StructuralWallInkReport(
        decisions=decisions,
        class_table=(),
        network_count=1,
        darkest_ink_color=(0.0, 0.0, 0.0),
        reason_codes=(),
        opening_gaps=tuple(gaps),
    )


def diagnose_unclosed_gaps(
    gaps: Sequence[OpeningGapCandidate],
    *,
    closed_chord_ids: Sequence[str],
    suppressed_chord_ids: Sequence[str],
) -> tuple[dict[str, object], ...]:
    """Emit explicit missing-host/gap diagnostics for overlay review."""
    closed = set(closed_chord_ids)
    suppressed = set(suppressed_chord_ids)
    out: list[dict[str, object]] = []
    for gap in gaps:
        from pb_structural_room_region_shadow import chord_id

        cid = chord_id(gap)
        if cid in closed or cid in suppressed:
            continue
        out.append(
            {
                "gap_type": "typed_opening_unclosed",
                "chord_id": cid,
                "a_pdf_pts": list(gap.end_a),
                "b_pdf_pts": list(gap.end_b),
                "width_pt": gap.gap_length_pt,
                "host_a": gap.source_primitive_id_a,
                "host_b": gap.source_primitive_id_b,
                "missing": "room_enclosure_not_formed",
            }
        )
    return tuple(out)


def run_fabricated_wall_box_closure_stage(
    *,
    exterior_polygon_pdf_pts: Sequence[tuple[float, float]],
    wall_ink_segments: Sequence[tuple[float, float, float, float]] = (),
    drawings: Sequence[Mapping[str, Any] | object] = (),
    wall_network_segments: Sequence[Mapping[str, Any]] = (),
    opening_gaps: Sequence[OpeningGapCandidate] = (),
    room_labels: Sequence[str] = (),
) -> FabricatedBoxClosureReceipt:
    """Collapse unsupported boxes then close rooms on typed doorway gaps."""
    if len(exterior_polygon_pdf_pts) < 4:
        return FabricatedBoxClosureReceipt(
            "ABSTAINED", "exterior_polygon_too_few_vertices",
        )

    ink = tuple(wall_ink_segments)
    if not ink and drawings:
        ink = wall_ink_segments_from_drawings(
            tuple(row for row in drawings if isinstance(row, Mapping))
        )

    detour = collapse_unsupported_rectangular_detours(
        tuple(exterior_polygon_pdf_pts), ink,
    )
    poly = detour.polygon_pdf_pts

    room_count = 0
    doorway_closures = 0
    suppressed = 0
    diagnostics: tuple[dict[str, object], ...] = ()
    if wall_network_segments:
        report = derive_structural_room_regions(
            wall_network_segments,
            _ink_report_for_segments(wall_network_segments, opening_gaps),
        )
        room_count = len(report.regions)
        doorway_closures = len(report.chord_ids)
        suppressed = len(report.suppressed_wall_covered_chord_ids)
        diagnostics = diagnose_unclosed_gaps(
            opening_gaps,
            closed_chord_ids=report.chord_ids,
            suppressed_chord_ids=report.suppressed_wall_covered_chord_ids,
        )

    labels = [str(x).upper() for x in room_labels]
    open_plan = (
        any(x.startswith("LIVING") for x in labels)
        and any(x.startswith("KITCHEN") for x in labels)
    )

    status = "CANDIDATE"
    reason = "fabricated_box_collapse_and_typed_room_closure"
    if detour.collapsed_detour_count == 0 and room_count == 0 and not opening_gaps:
        reason = detour.reason_codes[0] if detour.reason_codes else reason
        if "no_unsupported_rectangular_detour" in (detour.reason_codes or ()):
            status = "CANDIDATE"

    return FabricatedBoxClosureReceipt(
        status=status,
        reason=reason,
        collapsed_detour_count=detour.collapsed_detour_count,
        polygon_pdf_pts=poly,
        room_region_count=room_count,
        doorway_closure_count=doorway_closures,
        suppressed_false_gap_count=suppressed,
        unclosed_gap_diagnostics=diagnostics,
        open_plan_merged=open_plan,
    )


def run_fabricated_wall_box_closure_from_footprint_trace(
    *,
    footprint_polygon_pdf_pts: Sequence[tuple[float, float]],
    drawings: Sequence[Mapping[str, Any] | object],
    source_words: Sequence[Any] = (),
) -> dict[str, object]:
    """Extractor/runner entry: footprint polygon + native drawings → #4443 receipt."""
    labels: list[str] = []
    for word in source_words:
        try:
            text = str(
                word.get("text") if isinstance(word, Mapping) else word[4]
            )
        except (TypeError, IndexError, AttributeError):
            continue
        token = "".join(ch for ch in text.upper() if ch.isalnum())
        if token:
            labels.append(token)

    # Build simple wall-network segments from dark wall-layer strokes for room
    # preview; opening gaps are left empty unless a caller supplies typed ones.
    segments: list[dict[str, Any]] = []
    for index, row in enumerate(drawings):
        if not isinstance(row, Mapping):
            continue
        layer = str(row.get("layer") or "")
        if "Wall" not in layer and "WALL" not in layer:
            continue
        for item in row.get("items") or ():
            if not item or item[0] != "l" or len(item) < 3:
                continue
            try:
                a, b = item[1], item[2]
                x1, y1 = float(a.x), float(a.y)
                x2, y2 = float(b.x), float(b.y)
            except (AttributeError, TypeError, ValueError):
                continue
            if not all(math.isfinite(v) for v in (x1, y1, x2, y2)):
                continue
            segments.append(
                {"id": f"path:{index}", "x1": x1, "y1": y1, "x2": x2, "y2": y2}
            )
            break

    receipt = run_fabricated_wall_box_closure_stage(
        exterior_polygon_pdf_pts=footprint_polygon_pdf_pts,
        drawings=drawings,
        wall_network_segments=tuple(segments),
        room_labels=tuple(labels),
    )
    return receipt.to_dict()
