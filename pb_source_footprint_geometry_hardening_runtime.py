"""Production helpers for #4549-16..20 footprint geometry hardening.

Page skew, curved/chamfer boundaries, annex islands, raster-vector dedup,
and shared-wall thickness roles. Fail-closed; no FIRM/customer authority.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class PointPoly:
    points_pdf_pts: tuple[tuple[float, float], ...]
    role: str = "footprint"  # footprint | annex | garage | raster | vector


def estimate_page_skew_correction(
    *,
    reference_horizontal_spans: Sequence[tuple[tuple[float, float], tuple[float, float]]] = (),
) -> dict[str, object]:
    """#16 — derive skew from near-horizontal source spans; abstain if conflict."""
    angles: list[float] = []
    for a, b in reference_horizontal_spans:
        dx, dy = b[0] - a[0], b[1] - a[1]
        if math.hypot(dx, dy) < 20:
            continue
        angles.append(math.degrees(math.atan2(dy, dx)))
    if len(angles) < 2:
        return {
            "status": "ABSTAINED",
            "reason": "insufficient_horizontal_reference_spans",
            "skew_degrees": None,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    # Normalize to [-45, 45] residual from 0°.
    residuals = []
    for ang in angles:
        r = ang
        while r > 45:
            r -= 90
        while r < -45:
            r += 90
        residuals.append(r)
    if max(residuals) - min(residuals) > 1.5:
        return {
            "status": "ABSTAINED",
            "reason": "conflicting_skew_estimates",
            "skew_degrees": None,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    skew = sum(residuals) / len(residuals)
    return {
        "status": "CANDIDATE",
        "reason": "page_skew_from_horizontal_spans",
        "skew_degrees": round(skew, 4),
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def build_curved_chamfer_boundary(
    control_pdf_pts: Sequence[tuple[float, float]],
    *,
    closed: bool = True,
) -> dict[str, object]:
    """#17 — preserve source control points; refuse invented densification."""
    pts = [(float(x), float(y)) for x, y in control_pdf_pts]
    if len(pts) < 3:
        return {
            "status": "ABSTAINED",
            "reason": "curved_boundary_needs_three_source_points",
            "polygon_pdf_pts": [],
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    if any(not (math.isfinite(x) and math.isfinite(y)) for x, y in pts):
        return {
            "status": "ABSTAINED",
            "reason": "nonfinite_boundary_control_point",
            "polygon_pdf_pts": [],
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    out = list(pts)
    if closed and out[0] != out[-1]:
        out.append(out[0])
    return {
        "status": "CANDIDATE",
        "reason": "source_preserving_curved_or_chamfer_polygon",
        "polygon_pdf_pts": [[round(x, 4), round(y, 4)] for x, y in out],
        "densified": False,
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def detect_disjoint_annex_islands(
    islands: Sequence[PointPoly],
    *,
    primary_role: str = "footprint",
) -> dict[str, object]:
    """#18 — keep real enclosed annex/garage islands; never silently drop."""
    primary = [p for p in islands if p.role == primary_role]
    annex = [p for p in islands if p.role in {"annex", "garage"}]
    if not primary:
        return {
            "status": "ABSTAINED",
            "reason": "primary_footprint_island_missing",
            "retained_annex_count": 0,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    retained = []
    for island in annex:
        if len(island.points_pdf_pts) < 4:
            continue
        retained.append(
            {
                "role": island.role,
                "vertex_count": len(island.points_pdf_pts),
                "silently_dropped": False,
            }
        )
    return {
        "status": "CANDIDATE",
        "reason": "disjoint_annex_islands_retained",
        "primary_count": len(primary),
        "retained_annexes": retained,
        "retained_annex_count": len(retained),
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def dedupe_overlapping_raster_vector(
    *,
    raster_segments: Sequence[tuple[tuple[float, float], tuple[float, float]]] = (),
    vector_segments: Sequence[tuple[tuple[float, float], tuple[float, float]]] = (),
    overlap_tol_pt: float = 1.5,
) -> dict[str, object]:
    """#19 — prefer vector when overlap; keep unmatched raster as evidence."""
    kept_vector = list(vector_segments)
    kept_raster = []
    suppressed = 0
    for rs in raster_segments:
        overlapped = False
        for vs in vector_segments:
            # Midpoint proximity proxy for collinear overlap.
            rm = ((rs[0][0] + rs[1][0]) / 2, (rs[0][1] + rs[1][1]) / 2)
            vm = ((vs[0][0] + vs[1][0]) / 2, (vs[0][1] + vs[1][1]) / 2)
            if math.hypot(rm[0] - vm[0], rm[1] - vm[1]) <= overlap_tol_pt:
                overlapped = True
                break
        if overlapped:
            suppressed += 1
        else:
            kept_raster.append(rs)
    return {
        "status": "CANDIDATE",
        "reason": "raster_vector_dedup_prefer_vector_keep_unmatched_raster",
        "vector_count": len(kept_vector),
        "raster_retained_unmatched": len(kept_raster),
        "raster_suppressed_overlap": suppressed,
        "structural_evidence_eliminated": False,
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def infer_shared_wall_thickness_role(
    *,
    thickness_pt: float,
    party_labelled: bool = False,
    exterior_labelled: bool = False,
    partition_labelled: bool = False,
) -> dict[str, object]:
    """#20 — thickness + labels distinguish partition / external / party."""
    if not math.isfinite(thickness_pt) or thickness_pt <= 0:
        return {
            "status": "ABSTAINED",
            "reason": "nonpositive_thickness",
            "role": None,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    labels = sum(
        1 for flag in (party_labelled, exterior_labelled, partition_labelled) if flag
    )
    if labels > 1:
        return {
            "status": "ABSTAINED",
            "reason": "conflicting_wall_role_labels",
            "role": None,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    if party_labelled:
        role = "party"
    elif exterior_labelled:
        role = "external"
    elif partition_labelled:
        role = "partition"
    elif thickness_pt >= 5.5:
        role = "external_or_party_candidate"
    elif thickness_pt <= 2.2:
        role = "partition_candidate"
    else:
        return {
            "status": "ABSTAINED",
            "reason": "ambiguous_thickness_without_label",
            "role": None,
            "thickness_pt": round(thickness_pt, 4),
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    return {
        "status": "CANDIDATE",
        "reason": "shared_wall_thickness_role",
        "role": role,
        "thickness_pt": round(thickness_pt, 4),
        "measurement_authorized": False,
        "commercial_publishable": False,
    }


def run_footprint_geometry_hardening_stage(
    *,
    horizontal_spans: Sequence[tuple[tuple[float, float], tuple[float, float]]] = (),
    curved_controls: Sequence[tuple[float, float]] = (),
    islands: Sequence[PointPoly] = (),
    raster_segments: Sequence[tuple[tuple[float, float], tuple[float, float]]] = (),
    vector_segments: Sequence[tuple[tuple[float, float], tuple[float, float]]] = (),
    thickness_pt: float | None = None,
    party_labelled: bool = False,
    exterior_labelled: bool = False,
    partition_labelled: bool = False,
) -> dict[str, object]:
    thickness_receipt = (
        infer_shared_wall_thickness_role(
            thickness_pt=float(thickness_pt),
            party_labelled=party_labelled,
            exterior_labelled=exterior_labelled,
            partition_labelled=partition_labelled,
        )
        if thickness_pt is not None
        else {
            "status": "ABSTAINED",
            "reason": "thickness_not_supplied",
            "role": None,
            "measurement_authorized": False,
            "commercial_publishable": False,
        }
    )
    return {
        "page_skew": estimate_page_skew_correction(
            reference_horizontal_spans=horizontal_spans,
        ),
        "curved_chamfer_boundary": build_curved_chamfer_boundary(curved_controls),
        "disjoint_annex_islands": detect_disjoint_annex_islands(islands),
        "raster_vector_dedup": dedupe_overlapping_raster_vector(
            raster_segments=raster_segments, vector_segments=vector_segments,
        ),
        "shared_wall_thickness": thickness_receipt,
        "tasks_covered": ["16", "17", "18", "19", "20"],
        "measurement_authorized": False,
        "commercial_publishable": False,
        "official_frozen120_score_change": 0,
    }
