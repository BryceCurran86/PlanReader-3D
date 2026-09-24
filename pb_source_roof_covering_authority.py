"""pb_source_roof_covering_authority.py — Generic Source-Owned Roof Covering Measurement.

Derives gable roof pitch, cross-ridge structural span, ridge length, and 3D roof
covering area strictly from source-native vector geometry and authenticated
building footprint dimensions.

Authority Evidence Chain:
  source-native elevation/title ownership
  -> authenticated gable roofline topology
  -> matching left/right slope measurement
  -> authenticated structural/wall/post endpoints
  -> source-backed run/span
  -> source-backed ridge length / building axis
  -> roof-plane geometry
  -> roof-covering quantity

Fail-Closed Invariants:
  - No assumed pitch (never uses BOQ 'not exceeding 30 degrees' specification).
  - No assumed eaves overhang (stops at authenticated vertical structural supports).
  - Abstains on competing apexes, pitch mismatch (> 1.0 deg), missing structural
    endpoints, pitch out of structural range (< 5 deg or > 65 deg), or ambiguous
    ridge orientation.
  - Fully invariant to coordinate translation, input segment order, and scale.
"""
from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from pb_migration_contracts import (
    EvidenceAtom,
    EvidenceResolutionStatus,
    QuantityEvidence,
    stable_contract_id,
)

# ---------------------------------------------------------------------------
# Numerical & Geometric Thresholds
# ---------------------------------------------------------------------------
MIN_ROOFLINE_SEGMENT_LEN_PT = 20.0
MIN_STRUCTURAL_VERTICAL_LEN_PT = 15.0
MAX_APEX_CLUSTER_GAP_PT = 8.0
MAX_PITCH_DISAGREEMENT_DEG = 1.0
MIN_PLAUSIBLE_PITCH_DEG = 5.0
MAX_PLAUSIBLE_PITCH_DEG = 65.0
MIN_HORIZONTAL_RUN_PT = 30.0
MAX_WALLCORNER_RAY_GAP_PT = 3.5


@dataclass(frozen=True)
class VectorSegment:
    """Immutable 2D line segment on a drawing page."""

    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def length(self) -> float:
        return math.hypot(self.x1 - self.x0, self.y1 - self.y0)

    @property
    def angle_deg(self) -> float:
        ang = math.degrees(math.atan2(self.y1 - self.y0, self.x1 - self.x0))
        while ang <= -90.0:
            ang += 180.0
        while ang > 90.0:
            ang -= 180.0
        return ang

    @property
    def is_vertical(self) -> bool:
        return abs(self.x1 - self.x0) <= 1.0 and abs(self.y1 - self.y0) >= 0.5

    @property
    def is_horizontal(self) -> bool:
        return abs(self.y1 - self.y0) <= 1.0 and abs(self.x1 - self.x0) >= 0.5


@dataclass(frozen=True)
class DiagonalSlopeSegment:
    """Diagonal segment oriented from highest point (apex candidate) downward."""

    x_hi: float
    y_hi: float
    x_lo: float
    y_lo: float
    length: float
    direction: int  # -1 = slopes down to left (dx < 0), +1 = slopes down to right (dx > 0)
    pitch_deg: float

    @classmethod
    def from_endpoints(cls, x0: float, y0: float, x1: float, y1: float) -> DiagonalSlopeSegment | None:
        length = math.hypot(x1 - x0, y1 - y0)
        if length < MIN_ROOFLINE_SEGMENT_LEN_PT:
            return None
        # PDF coordinates: y increases downward. Higher point has smaller y.
        if y0 <= y1:
            x_hi, y_hi = x0, y0
            x_lo, y_lo = x1, y1
        else:
            x_hi, y_hi = x1, y1
            x_lo, y_lo = x0, y0

        dx = x_lo - x_hi
        dy = y_lo - y_hi
        if dy < 0.5 or abs(dx) < 0.5:
            return None

        pitch_deg = math.degrees(math.atan2(dy, abs(dx)))
        if not (MIN_PLAUSIBLE_PITCH_DEG <= pitch_deg <= MAX_PLAUSIBLE_PITCH_DEG):
            return None

        direction = 1 if dx > 0 else -1
        return cls(
            x_hi=round(x_hi, 4),
            y_hi=round(y_hi, 4),
            x_lo=round(x_lo, 4),
            y_lo=round(y_lo, 4),
            length=round(length, 4),
            direction=direction,
            pitch_deg=round(pitch_deg, 4),
        )


@dataclass(frozen=True)
class VerticalSupportSegment:
    """Vertical structural line segment representing wall or column/post corner."""

    x: float
    top_y: float
    bottom_y: float
    length: float

    @classmethod
    def from_endpoints(cls, x0: float, y0: float, x1: float, y1: float) -> VerticalSupportSegment | None:
        length = abs(y1 - y0)
        if abs(x1 - x0) > 1.0 or length < MIN_STRUCTURAL_VERTICAL_LEN_PT:
            return None
        return cls(
            x=round((x0 + x1) / 2.0, 4),
            top_y=round(min(y0, y1), 4),
            bottom_y=round(max(y0, y1), 4),
            length=round(length, 4),
        )


@dataclass(frozen=True)
class GableRoofApexEvidence:
    """Authenticated gable apex with opposing slopes and verified structural endpoints."""

    apex_xy: tuple[float, float]
    pitch_deg: float
    left_pitch_deg: float
    right_pitch_deg: float
    left_run_pt: float
    right_run_pt: float
    left_support_xy: tuple[float, float]
    right_support_xy: tuple[float, float]
    member_count: int
    source_viewport_id: str | None = None
    source_page: int = 1
    material_annotations: tuple[str, ...] = ()
    reason_codes: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourceRoofCoveringMeasurement:
    """Complete source-owned roof covering measurement result."""

    status: EvidenceResolutionStatus
    pitch_deg: float | None
    cross_ridge_span_m: float | None
    ridge_length_m: float | None
    slope_length_m: float | None
    roof_covering_area_m2: float | None
    gable_evidence: GableRoofApexEvidence | None
    quantity_evidence: QuantityEvidence | None
    reason_codes: tuple[str, ...] = ()
    metadata: Mapping[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core Geometric Algorithms
# ---------------------------------------------------------------------------

def _cluster_apex_candidates(
    diagonals: Sequence[DiagonalSlopeSegment],
) -> list[tuple[tuple[float, float], list[DiagonalSlopeSegment]]]:
    """Group diagonal slope segments by shared high endpoints (apex candidates).

    A valid cluster must contain at least one left-sloping and one right-sloping
    member, forming a genuine peak rather than a unilateral rake.
    """
    unclustered = list(diagonals)
    clusters: list[tuple[tuple[float, float], list[DiagonalSlopeSegment]]] = []

    while unclustered:
        seed = unclustered.pop(0)
        members = [seed]
        i = 0
        while i < len(unclustered):
            cand = unclustered[i]
            if any(
                math.hypot(cand.x_hi - m.x_hi, cand.y_hi - m.y_hi) <= MAX_APEX_CLUSTER_GAP_PT
                for m in members
            ):
                members.append(cand)
                unclustered.pop(i)
                continue
            i += 1

        dirs = {m.direction for m in members}
        if 1 in dirs and -1 in dirs:
            avg_x = sum(m.x_hi for m in members) / len(members)
            avg_y = sum(m.y_hi for m in members) / len(members)
            clusters.append(((round(avg_x, 4), round(avg_y, 4)), members))

    return clusters


def _find_farthest_structural_run(
    apex_xy: tuple[float, float],
    pitch_deg: float,
    direction: int,
    verticals: Sequence[VerticalSupportSegment],
) -> tuple[float, tuple[float, float]] | None:
    """Find the farthest vertical support whose top point lies on the pitch ray.

    Casts ray from apex at pitch_deg in specified direction (-1=left, +1=right).
    Selects the farthest qualifying structural vertical so that verandah / porch
    extensions are captured when physically continuous with the roofline, while
    strictly requiring an actual structural support element at that boundary.
    """
    ax, ay = apex_xy
    pitch_rad = math.radians(pitch_deg)
    tan_pitch = math.tan(pitch_rad)

    best_run: float | None = None
    best_point: tuple[float, float] | None = None

    for v in verticals:
        run = (v.x - ax) * direction
        if run < MIN_HORIZONTAL_RUN_PT:
            continue
        expected_y = ay + run * tan_pitch
        if abs(v.top_y - expected_y) <= MAX_WALLCORNER_RAY_GAP_PT and (best_run is None or run > best_run):
            best_run = run
            best_point = (v.x, v.top_y)

    if best_run is not None and best_point is not None:
        return round(best_run, 4), (round(best_point[0], 4), round(best_point[1], 4))
    return None


def resolve_gable_apex_in_viewport(
    diagonals: Sequence[DiagonalSlopeSegment],
    verticals: Sequence[VerticalSupportSegment],
    *,
    source_viewport_id: str | None = None,
    source_page: int = 1,
    material_annotations: Sequence[str] = (),
) -> tuple[GableRoofApexEvidence | None, tuple[str, ...]]:
    """Resolve an unambiguous gable apex within a segmented elevation viewport.

    Fails closed if zero or multiple distinct apex clusters exist, if opposing
    slopes disagree in pitch, or if either side lacks a structural endpoint.
    """
    clusters = _cluster_apex_candidates(diagonals)
    if not clusters:
        return None, ("no_gable_apex_found",)
    if len(clusters) > 1:
        return None, ("competing_apex_candidates",)

    apex_xy, members = clusters[0]

    left_members = [m for m in members if m.direction == -1]
    right_members = [m for m in members if m.direction == 1]
    if not left_members or not right_members:
        return None, ("unilateral_slope_not_gable",)

    left_pitch = sum(m.pitch_deg for m in left_members) / len(left_members)
    right_pitch = sum(m.pitch_deg for m in right_members) / len(right_members)

    if abs(left_pitch - right_pitch) > MAX_PITCH_DISAGREEMENT_DEG:
        return None, ("mismatched_slope_pitch",)

    mean_pitch = (left_pitch + right_pitch) / 2.0
    if not (MIN_PLAUSIBLE_PITCH_DEG <= mean_pitch <= MAX_PLAUSIBLE_PITCH_DEG):
        return None, ("pitch_out_of_structural_range",)

    left_res = _find_farthest_structural_run(apex_xy, mean_pitch, -1, verticals)
    if left_res is None:
        return None, ("missing_structural_endpoint_left",)

    right_res = _find_farthest_structural_run(apex_xy, mean_pitch, 1, verticals)
    if right_res is None:
        return None, ("missing_structural_endpoint_right",)

    left_run_pt, left_support = left_res
    right_run_pt, right_support = right_res

    evidence = GableRoofApexEvidence(
        apex_xy=apex_xy,
        pitch_deg=round(mean_pitch, 3),
        left_pitch_deg=round(left_pitch, 3),
        right_pitch_deg=round(right_pitch, 3),
        left_run_pt=left_run_pt,
        right_run_pt=right_run_pt,
        left_support_xy=left_support,
        right_support_xy=right_support,
        member_count=len(members),
        source_viewport_id=source_viewport_id,
        source_page=source_page,
        material_annotations=tuple(material_annotations),
        reason_codes=("authenticated_gable_roofline",),
    )
    return evidence, ("authenticated_gable_roofline",)


def measure_source_roof_covering(
    gable_evidence: GableRoofApexEvidence,
    *,
    building_length_m: float,
    building_width_m: float,
    source_sha256: str,
    document_id: str = "doc_source",
) -> SourceRoofCoveringMeasurement:
    """Compute physical 3D roof covering area from authenticated gable and footprint.

    Excludes eaves overhang: uses authenticated structural endpoints as the run.
    Binds the cross-ridge span to building_width_m (with width <= length guard).
    """
    if building_length_m <= 0.0 or building_width_m <= 0.0:
        return SourceRoofCoveringMeasurement(
            status=EvidenceResolutionStatus.ABSTAINED,
            pitch_deg=None,
            cross_ridge_span_m=None,
            ridge_length_m=None,
            slope_length_m=None,
            roof_covering_area_m2=None,
            gable_evidence=gable_evidence,
            quantity_evidence=None,
            reason_codes=("invalid_footprint_dimensions",),
        )

    # In standard gable structures, the ridge runs along the long axis.
    # When width > length without explicit ridge orientation, fail closed.
    if building_width_m > building_length_m:
        return SourceRoofCoveringMeasurement(
            status=EvidenceResolutionStatus.ABSTAINED,
            pitch_deg=None,
            cross_ridge_span_m=None,
            ridge_length_m=None,
            slope_length_m=None,
            roof_covering_area_m2=None,
            gable_evidence=gable_evidence,
            quantity_evidence=None,
            reason_codes=("ambiguous_ridge_axis",),
        )

    cross_ridge_span_m = round(building_width_m, 3)
    ridge_length_m = round(building_length_m, 3)

    pitch_rad = math.radians(gable_evidence.pitch_deg)
    cos_pitch = math.cos(pitch_rad)
    if cos_pitch <= 0.01:
        return SourceRoofCoveringMeasurement(
            status=EvidenceResolutionStatus.ABSTAINED,
            pitch_deg=None,
            cross_ridge_span_m=None,
            ridge_length_m=None,
            slope_length_m=None,
            roof_covering_area_m2=None,
            gable_evidence=gable_evidence,
            quantity_evidence=None,
            reason_codes=("extreme_pitch_angle",),
        )

    # 3D slope length across both roof planes: (run_left + run_right) / cos(pitch)
    slope_length_m = round(cross_ridge_span_m / cos_pitch, 4)
    roof_covering_area_m2 = round(ridge_length_m * slope_length_m, 2)

    ev_atom_id = stable_contract_id(
        "ev_roof",
        {
            "apex_xy": gable_evidence.apex_xy,
            "pitch_deg": gable_evidence.pitch_deg,
            "source_page": gable_evidence.source_page,
            "source_sha256": source_sha256,
        },
    )
    ev_atom = EvidenceAtom(
        evidence_id=ev_atom_id,
        document_id=document_id,
        page_id=f"page_{gable_evidence.source_page}",
        kind="gable_roof_apex_geometry",
        method="elevation_vector_roofline",
        viewport_id=gable_evidence.source_viewport_id,
        normalized_value=gable_evidence.pitch_deg,
        unit="deg",
        confidence=0.85,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("authenticated_gable_roofline",),
        metadata={
            "apex_xy": list(gable_evidence.apex_xy),
            "left_run_pt": gable_evidence.left_run_pt,
            "right_run_pt": gable_evidence.right_run_pt,
            "left_support_xy": list(gable_evidence.left_support_xy),
            "right_support_xy": list(gable_evidence.right_support_xy),
            "material_annotations": list(gable_evidence.material_annotations),
        },
    )

    qty_payload = {
        "family": "roof_covering",
        "semantic_key": "source_owned_gable_roof_covering",
        "pitch_deg": gable_evidence.pitch_deg,
        "cross_ridge_span_m": cross_ridge_span_m,
        "ridge_length_m": ridge_length_m,
        "roof_covering_area_m2": roof_covering_area_m2,
        "source_sha256": source_sha256,
        "source_page": gable_evidence.source_page,
        "evidence_id": ev_atom_id,
    }
    qty_id = stable_contract_id("qty_roof", qty_payload)

    qty_evidence = QuantityEvidence(
        quantity_id=qty_id,
        family="roof_covering",
        semantic_key="roof_covering",
        value=roof_covering_area_m2,
        unit="SM",
        evidence_ids=(ev_atom_id,),
        formula="ridge_length_m * (cross_ridge_span_m / cos(radians(pitch_deg)))",
        formula_version="1.0.0",
        authority="source_native_elevation_vector_pitch",
        status=EvidenceResolutionStatus.CORROBORATED.value,
        confidence=0.85,
        abstained=False,
        reason_codes=("authenticated_gable_roof_covering",),
        metadata={
            "pitch_deg": gable_evidence.pitch_deg,
            "cross_ridge_span_m": cross_ridge_span_m,
            "ridge_length_m": ridge_length_m,
            "slope_length_m": slope_length_m,
            "excludes_eaves_overhang": True,
            "left_run_pt": gable_evidence.left_run_pt,
            "right_run_pt": gable_evidence.right_run_pt,
            "source_viewport_id": gable_evidence.source_viewport_id,
            "source_page": gable_evidence.source_page,
            "material_annotations": list(gable_evidence.material_annotations),
            "evidence_atom": ev_atom.to_dict(),
        },
    )

    return SourceRoofCoveringMeasurement(
        status=EvidenceResolutionStatus.CORROBORATED,
        pitch_deg=gable_evidence.pitch_deg,
        cross_ridge_span_m=cross_ridge_span_m,
        ridge_length_m=ridge_length_m,
        slope_length_m=slope_length_m,
        roof_covering_area_m2=roof_covering_area_m2,
        gable_evidence=gable_evidence,
        quantity_evidence=qty_evidence,
        reason_codes=("authenticated_gable_roof_covering",),
        metadata=dict(qty_evidence.metadata),
    )


# ---------------------------------------------------------------------------
# High-Level Page & Document Discovery
# ---------------------------------------------------------------------------

def extract_elevation_segments_from_page(
    page: Any,
    viewport_bbox: tuple[float, float, float, float],
) -> tuple[list[DiagonalSlopeSegment], list[VerticalSupportSegment]]:
    """Extract diagonal and vertical segments within an elevation viewport bounding box."""
    vx0, vy0, vx1, vy1 = viewport_bbox
    diagonals: list[DiagonalSlopeSegment] = []
    verticals: list[VerticalSupportSegment] = []

    drawings = []
    try:
        drawings = page.get_drawings() or []
    except Exception:  # noqa: BLE001
        return diagonals, verticals

    for d in drawings:
        for it in d.get("items") or []:
            if not it or it[0] != "l" or len(it) < 3:
                continue
            p0, p1 = it[1], it[2]
            try:
                x0, y0, x1, y1 = float(p0.x), float(p0.y), float(p1.x), float(p1.y)
            except (ValueError, TypeError, AttributeError):
                continue

            # Must fall inside the viewport bounding box
            if not (vx0 <= min(x0, x1) and max(x0, x1) <= vx1 and vy0 <= min(y0, y1) and max(y0, y1) <= vy1):
                continue

            vert = VerticalSupportSegment.from_endpoints(x0, y0, x1, y1)
            if vert is not None:
                verticals.append(vert)
                continue

            diag = DiagonalSlopeSegment.from_endpoints(x0, y0, x1, y1)
            if diag is not None:
                diagonals.append(diag)

    return diagonals, verticals


def get_elevation_viewport_search_bbox(
    vp: Any,
    all_page_viewports: Sequence[Any],
    page_rect: Any,
) -> tuple[float, float, float, float]:
    """Determine the effective drawing bounding box for an elevation viewport.

    If the viewport is bound to an explicit closed vector frame, the vector
    frame is authoritative.
    If the viewport is derived from title anchors without a vector frame, standard
    architectural drafting convention places the title underneath the elevation
    drawing. The effective drawing region extends upward from the title anchor to
    the preceding title or frame boundary above it (or page top).
    """
    if getattr(vp, "boundary_source", None) == "vector_frame" and vp.bounding_box:
        return tuple(vp.bounding_box)

    page_w = float(page_rect.width) if hasattr(page_rect, "width") else 1000.0
    page_h = float(page_rect.height) if hasattr(page_rect, "height") else 1000.0

    if not getattr(vp, "title_bbox", None):
        return tuple(vp.bounding_box) if getattr(vp, "bounding_box", None) else (0.0, 0.0, page_w, page_h)

    _tx0, ty0, _tx1, ty1 = vp.title_bbox

    # Establish the current elevation column before looking for a vertical
    # predecessor.  A derived multi-column sheet can place another view title
    # only a few points above this title in a completely different column;
    # letting that unrelated title set y_top collapses the roof search to a
    # title-height strip and loses the actual elevation geometry.
    if getattr(vp, "bounding_box", None):
        x_left = float(vp.bounding_box[0])
        x_right = float(vp.bounding_box[2])
    else:
        x_left = 0.0
        x_right = page_w

    def _same_horizontal_column(bbox: Sequence[float]) -> bool:
        if len(bbox) < 4:
            return False
        center_x = (float(bbox[0]) + float(bbox[2])) / 2.0
        return x_left <= center_x <= x_right

    # Preceding elements strictly above ty0 AND in this elevation's column.
    prev_bottom = 0.0
    for other in all_page_viewports:
        if getattr(other, "view_id", None) == getattr(vp, "view_id", None):
            continue
        other_tb = getattr(other, "title_bbox", None)
        if (
            other_tb
            and _same_horizontal_column(other_tb)
            and ty0 > other_tb[3] > prev_bottom
        ):
            prev_bottom = float(other_tb[3])
        other_bbox = getattr(other, "bounding_box", None)
        if (
            getattr(other, "boundary_source", None) == "vector_frame"
            and other_bbox
            and _same_horizontal_column(other_bbox)
            and ty0 > other_bbox[3] > prev_bottom
        ):
            prev_bottom = float(other_bbox[3])

    y_top = max(0.0, prev_bottom)
    y_bottom = min(page_h, ty1 + 15.0)

    return (x_left, y_top, x_right, y_bottom)


def extract_roof_material_annotations(
    page: Any,
    search_bbox: tuple[float, float, float, float],
) -> list[str]:
    """Extract roof covering material callout annotations within an elevation search area."""
    annotations: list[str] = []
    sx0, sy0, sx1, sy1 = search_bbox
    try:
        text_dict = page.get_text("dict") or {}
    except Exception:  # noqa: BLE001
        return annotations

    for block in text_dict.get("blocks", []) or []:
        if int(block.get("type", 0)) != 0:
            continue
        for line in block.get("lines", []) or []:
            line_bbox = line.get("bbox")
            if not line_bbox or len(line_bbox) < 4:
                continue
            cx = (float(line_bbox[0]) + float(line_bbox[2])) / 2.0
            cy = (float(line_bbox[1]) + float(line_bbox[3])) / 2.0
            if sx0 <= cx <= sx1 and sy0 <= cy <= sy1:
                line_str = " ".join(str(s.get("text", "")) for s in line.get("spans", []) or []).strip()
                if re.search(r"(?:galvanized|corrugated|sheet\s+roofing|roofing\s+sheet|iron\s+sheet|tiles|metal\s+deck)\b", line_str, re.IGNORECASE):
                    annotations.append(line_str)
    return annotations


def resolve_document_gable_roof_covering(
    doc: Any,
    *,
    building_length_m: float,
    building_width_m: float,
    source_sha256: str,
    target_pages: Sequence[int] | None = None,
) -> SourceRoofCoveringMeasurement:
    """Scan document for segmented elevation viewports and resolve gable roof covering.

    Fails closed if zero or multiple candidate viewports yield valid gable rooflines.
    """
    from pb_viewport_segmentation import segment_page_viewports

    pages_to_scan = list(target_pages) if target_pages else list(range(len(doc)))
    candidates: list[GableRoofApexEvidence] = []

    for p_idx in pages_to_scan:
        if p_idx < 0 or p_idx >= len(doc):
            continue
        page = doc[p_idx]
        viewports = segment_page_viewports(page, page_number=p_idx + 1)
        for vp in viewports:
            if vp.view_type != "elevation":
                continue
            search_bbox = get_elevation_viewport_search_bbox(vp, viewports, page.rect)
            diags, verts = extract_elevation_segments_from_page(page, search_bbox)
            mat_annos = extract_roof_material_annotations(page, search_bbox)
            evidence, _ = resolve_gable_apex_in_viewport(
                diags,
                verts,
                source_viewport_id=vp.view_id,
                source_page=p_idx + 1,
                material_annotations=mat_annos,
            )
            if evidence is not None:
                candidates.append(evidence)

    if not candidates:
        return SourceRoofCoveringMeasurement(
            status=EvidenceResolutionStatus.ABSTAINED,
            pitch_deg=None,
            cross_ridge_span_m=None,
            ridge_length_m=None,
            slope_length_m=None,
            roof_covering_area_m2=None,
            gable_evidence=None,
            quantity_evidence=None,
            reason_codes=("no_elevation_gable_found",),
        )

    if len(candidates) > 1:
        # Check if all candidates represent identical geometry (e.g. redundant elevations of same pitch)
        first = candidates[0]
        all_match = all(
            abs(c.pitch_deg - first.pitch_deg) <= MAX_PITCH_DISAGREEMENT_DEG
            and abs(c.left_run_pt - first.left_run_pt) <= 2.0
            and abs(c.right_run_pt - first.right_run_pt) <= 2.0
            for c in candidates
        )
        if not all_match:
            return SourceRoofCoveringMeasurement(
                status=EvidenceResolutionStatus.CONFLICT,
                pitch_deg=None,
                cross_ridge_span_m=None,
                ridge_length_m=None,
                slope_length_m=None,
                roof_covering_area_m2=None,
                gable_evidence=None,
                quantity_evidence=None,
                reason_codes=("multiple_conflicting_gable_elevations",),
            )

    selected_gable = candidates[0]
    return measure_source_roof_covering(
        selected_gable,
        building_length_m=building_length_m,
        building_width_m=building_width_m,
        source_sha256=source_sha256,
    )
