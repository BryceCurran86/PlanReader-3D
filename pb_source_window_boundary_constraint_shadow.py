"""Shadow: source-owned window boundary constraints & floor-closure authority.

AntiGravity P4 on GPT1's research->repo handoff.
Resolves:
1. External WINDOW versus full-height glazed door distinction.
   - Window: sill lines spanning terminal jambs, finished floor does not leak
     outside, closes 2D room boundary while remaining vertical wall void.
   - Door: threshold transition, walk-through opening, sill_height == 0.
2. Adversarial challenge gates:
   - Segmented glazing without terminal jambs -> ABSTAIN.
   - Removed jamb / gap tolerance exceeded -> ABSTAIN.
   - Foreign layer or competitor dimension ink claiming sill -> ABSTAIN.
   - One-end-short sill lines -> ABSTAIN.
   - Unhosted aperture without structural wall bodies on both ends -> ABSTAIN.

Zero customer quantities, zero FIRM, zero artificial wall area.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_native_wall_body_junction_graph_shadow import (
    CONTACT_PT,
    SourceWallBodyRecord,
)

REASON_WINDOW_VALID = "window_aperture_boundary_constraint_observed"
REASON_MISSING_JAMB = "window_terminal_jamb_missing_or_unresolved"
REASON_FOREIGN_LAYER = "window_candidate_foreign_layer_competitor"
REASON_ONE_END_SHORT = "window_sill_line_does_not_span_both_jambs"
REASON_UNHOSTED = "window_aperture_unhosted_by_structural_wall_bodies"
REASON_GLAZED_DOOR = "opening_classified_as_glazed_door_not_window"


@dataclass(frozen=True)
class WindowApertureConstraintRecord:
    aperture_id: str
    left_jamb_path_id: int
    right_jamb_path_id: int
    sill_path_ids: tuple[int, ...]
    wall_host_left_body_id: str
    wall_host_right_body_id: str
    sill_chord_pdf_pts: tuple[tuple[float, float], tuple[float, float]]
    clear_width_pts: float
    is_window_not_door: bool
    closes_2d_room_boundary: bool
    deducts_from_wall_surface: bool
    status: EvidenceResolutionStatus
    reason: str
    physical_opening_authenticated: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "aperture_id": self.aperture_id,
            "left_jamb_path_id": self.left_jamb_path_id,
            "right_jamb_path_id": self.right_jamb_path_id,
            "sill_path_ids": list(self.sill_path_ids),
            "wall_host_left_body_id": self.wall_host_left_body_id,
            "wall_host_right_body_id": self.wall_host_right_body_id,
            "sill_chord_pdf_pts": [list(pt) for pt in self.sill_chord_pdf_pts],
            "clear_width_pts": round(self.clear_width_pts, 3),
            "is_window_not_door": self.is_window_not_door,
            "closes_2d_room_boundary": self.closes_2d_room_boundary,
            "deducts_from_wall_surface": self.deducts_from_wall_surface,
            "status": self.status.value,
            "reason": self.reason,
            "physical_opening_authenticated": False,
            "measurement_authorized": False,
        }


def _pt_dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def authenticate_window_boundary_constraint(
    *,
    sill_drawings: Sequence[Mapping[str, Any]],
    left_jamb_drawing: Mapping[str, Any] | None,
    right_jamb_drawing: Mapping[str, Any] | None,
    left_wall_body: SourceWallBodyRecord | None,
    right_wall_body: SourceWallBodyRecord | None,
    callout_tag: str = "",
) -> WindowApertureConstraintRecord:
    """Validate that a window opening forms an authentic 2D room boundary."""
    # Gate 1: Both structural wall bodies must host the opening
    if left_wall_body is None or right_wall_body is None:
        left_bid = "" if left_wall_body is None else left_wall_body.body_id
        right_bid = "" if right_wall_body is None else right_wall_body.body_id
        return WindowApertureConstraintRecord(
            aperture_id="aperture:unhosted",
            left_jamb_path_id=-1,
            right_jamb_path_id=-1,
            sill_path_ids=(),
            wall_host_left_body_id=left_bid,
            wall_host_right_body_id=right_bid,
            sill_chord_pdf_pts=((0.0, 0.0), (0.0, 0.0)),
            clear_width_pts=0.0,
            is_window_not_door=False,
            closes_2d_room_boundary=False,
            deducts_from_wall_surface=False,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason=REASON_UNHOSTED,
        )

    # Gate 2: Terminal jambs must exist and belong to valid enclosure/wall layer
    lj_id = (
        -1 if left_jamb_drawing is None
        else int(left_jamb_drawing.get("path_index", 0))
    )
    rj_id = (
        -1 if right_jamb_drawing is None
        else int(right_jamb_drawing.get("path_index", 0))
    )

    if left_jamb_drawing is None or right_jamb_drawing is None:
        return WindowApertureConstraintRecord(
            aperture_id=f"aperture:{left_wall_body.body_id}:{right_wall_body.body_id}",
            left_jamb_path_id=lj_id,
            right_jamb_path_id=rj_id,
            sill_path_ids=(),
            wall_host_left_body_id=left_wall_body.body_id,
            wall_host_right_body_id=right_wall_body.body_id,
            sill_chord_pdf_pts=((0.0, 0.0), (0.0, 0.0)),
            clear_width_pts=0.0,
            is_window_not_door=False,
            closes_2d_room_boundary=False,
            deducts_from_wall_surface=False,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason=REASON_MISSING_JAMB,
        )

    left_jamb_id = lj_id
    right_jamb_id = rj_id

    # Gate 3: Check foreign layers on jambs and sills
    valid_layers = {
        "enclosure_wallexternal", "enclosure_wallinternal", "wall", "a-wall"
    }
    for d in (left_jamb_drawing, right_jamb_drawing, *sill_drawings):
        layer = str(d.get("layer") or "").strip().lower()
        if layer and not any(vl in layer for vl in valid_layers):
            return WindowApertureConstraintRecord(
                aperture_id=f"aperture:{left_jamb_id}:{right_jamb_id}",
                left_jamb_path_id=left_jamb_id,
                right_jamb_path_id=right_jamb_id,
                sill_path_ids=tuple(
                    int(s.get("path_index", 0)) for s in sill_drawings
                ),
                wall_host_left_body_id=left_wall_body.body_id,
                wall_host_right_body_id=right_wall_body.body_id,
                sill_chord_pdf_pts=((0.0, 0.0), (0.0, 0.0)),
                clear_width_pts=0.0,
                is_window_not_door=False,
                closes_2d_room_boundary=False,
                deducts_from_wall_surface=False,
                status=EvidenceResolutionStatus.ABSTAINED,
                reason=REASON_FOREIGN_LAYER,
            )

    # Gate 4: Sill lines must span between left and right jambs
    if not sill_drawings:
        return WindowApertureConstraintRecord(
            aperture_id=f"aperture:{left_jamb_id}:{right_jamb_id}",
            left_jamb_path_id=left_jamb_id,
            right_jamb_path_id=right_jamb_id,
            sill_path_ids=(),
            wall_host_left_body_id=left_wall_body.body_id,
            wall_host_right_body_id=right_wall_body.body_id,
            sill_chord_pdf_pts=((0.0, 0.0), (0.0, 0.0)),
            clear_width_pts=0.0,
            is_window_not_door=False,
            closes_2d_room_boundary=False,
            deducts_from_wall_surface=False,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason=REASON_ONE_END_SHORT,
        )

    # Extract bounds of jambs
    lj_rect = left_jamb_drawing.get("rect")
    rj_rect = right_jamb_drawing.get("rect")
    if lj_rect is None or rj_rect is None:
        return WindowApertureConstraintRecord(
            aperture_id=f"aperture:{left_jamb_id}:{right_jamb_id}",
            left_jamb_path_id=left_jamb_id,
            right_jamb_path_id=right_jamb_id,
            sill_path_ids=tuple(
                int(s.get("path_index", 0)) for s in sill_drawings
            ),
            wall_host_left_body_id=left_wall_body.body_id,
            wall_host_right_body_id=right_wall_body.body_id,
            sill_chord_pdf_pts=((0.0, 0.0), (0.0, 0.0)),
            clear_width_pts=0.0,
            is_window_not_door=False,
            closes_2d_room_boundary=False,
            deducts_from_wall_surface=False,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason=REASON_MISSING_JAMB,
        )

    # Jamb positions
    lj_pt = (
        (float(lj_rect.x0) + float(lj_rect.x1)) / 2.0,
        (float(lj_rect.y0) + float(lj_rect.y1)) / 2.0,
    )
    rj_pt = (
        (float(rj_rect.x0) + float(rj_rect.x1)) / 2.0,
        (float(rj_rect.y0) + float(rj_rect.y1)) / 2.0,
    )
    clear_width = _pt_dist(lj_pt, rj_pt)

    # Check that at least one continuous sill line reaches both jambs within tolerance
    sill_reaches_both = False
    for sd in sill_drawings:
        sr = sd.get("rect")
        if sr is not None:
            s_min_x, s_max_x = float(sr.x0), float(sr.x1)
            reaches_left = (
                abs(s_min_x - lj_pt[0]) <= CONTACT_PT or
                abs(s_max_x - lj_pt[0]) <= CONTACT_PT or
                (s_min_x <= lj_pt[0] <= s_max_x)
            )
            reaches_right = (
                abs(s_min_x - rj_pt[0]) <= CONTACT_PT or
                abs(s_max_x - rj_pt[0]) <= CONTACT_PT or
                (s_min_x <= rj_pt[0] <= s_max_x)
            )
            if reaches_left and reaches_right:
                sill_reaches_both = True
                break

    if not sill_reaches_both:
        return WindowApertureConstraintRecord(
            aperture_id=f"aperture:{left_jamb_id}:{right_jamb_id}",
            left_jamb_path_id=left_jamb_id,
            right_jamb_path_id=right_jamb_id,
            sill_path_ids=tuple(
                int(s.get("path_index", 0)) for s in sill_drawings
            ),
            wall_host_left_body_id=left_wall_body.body_id,
            wall_host_right_body_id=right_wall_body.body_id,
            sill_chord_pdf_pts=(lj_pt, rj_pt),
            clear_width_pts=clear_width,
            is_window_not_door=False,
            closes_2d_room_boundary=False,
            deducts_from_wall_surface=False,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason=REASON_ONE_END_SHORT,
        )

    # Gate 5: Distinguish Window vs Glazed Door
    tag_clean = callout_tag.strip().upper()
    is_door = False
    if tag_clean.startswith("D") or "DOOR" in tag_clean or "SGD" in tag_clean:
        is_door = True

    if is_door:
        return WindowApertureConstraintRecord(
            aperture_id=f"aperture:door:{left_jamb_id}:{right_jamb_id}",
            left_jamb_path_id=left_jamb_id,
            right_jamb_path_id=right_jamb_id,
            sill_path_ids=tuple(
                int(s.get("path_index", 0)) for s in sill_drawings
            ),
            wall_host_left_body_id=left_wall_body.body_id,
            wall_host_right_body_id=right_wall_body.body_id,
            sill_chord_pdf_pts=(lj_pt, rj_pt),
            clear_width_pts=clear_width,
            is_window_not_door=False,
            closes_2d_room_boundary=False,  # Door does NOT close floor boundary
            deducts_from_wall_surface=True,
            status=EvidenceResolutionStatus.CANDIDATE,
            reason=REASON_GLAZED_DOOR,
        )

    return WindowApertureConstraintRecord(
        aperture_id=f"aperture:window:{left_jamb_id}:{right_jamb_id}",
        left_jamb_path_id=left_jamb_id,
        right_jamb_path_id=right_jamb_id,
        sill_path_ids=tuple(
            int(s.get("path_index", 0)) for s in sill_drawings
        ),
        wall_host_left_body_id=left_wall_body.body_id,
        wall_host_right_body_id=right_wall_body.body_id,
        sill_chord_pdf_pts=(lj_pt, rj_pt),
        clear_width_pts=clear_width,
        is_window_not_door=True,
        closes_2d_room_boundary=True,   # Window sill closes 2D floor/room boundary
        deducts_from_wall_surface=True,  # Opening void deducted from wall surface
        status=EvidenceResolutionStatus.CANDIDATE,
        reason=REASON_WINDOW_VALID,
    )
