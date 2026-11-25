"""Item 26: RCP ceiling material/height bubble association shadow.

Associates source-owned Reflected Ceiling Plan (RCP) material and ceiling-height
bubbles to verified physical ceiling zones/polygons while strictly preserving
explicitly different heights across rooms, bulkheads, and stepped ceiling zones.

Key invariants:
- Ownership requires either interior containment inside a unique zone polygon OR
  an explicit verified leader targeting that zone (no proximity-only guesses).
- Explicitly different heights in distinct zones or bulkhead sub-zones are NEVER
  averaged, flattened, or overwritten (`explicit_distinct_heights_preserved=True`).
- Raked/sloped height ranges (e.g., `2700-3400` or `RAKED 2700 TO 3600`) are
  preserved as explicit min/max ranges instead of being collapsed to a single height.
- Two conflicting flat heights inside the SAME undivided zone without a bulkhead
  boundary fail closed (`conflicting_heights_same_undivided_zone`).
- Legend/schedule bubbles are excluded from floor ceiling zones.
- Cross-viewport/cross-revision bubbles are rejected.

Shadow-only; never publishes ceiling area, wall height, or commercial quantities
and contains zero job-specific rules.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Sequence


_MIN_CEILING_HEIGHT_MM = 1500
_MAX_CEILING_HEIGHT_MM = 8000

_RAKED_RANGE_RE = re.compile(
    r"\b(?:raked|sloped|pitched)?\s*(?P<lo>[1-7]\d{3}|8000)\s*(?:mm)?\s*(?:-|–|to)\s*(?P<hi>[1-7]\d{3}|8000)\s*(?:mm)?\b",
    re.IGNORECASE,
)
_SINGLE_HEIGHT_MM_RE = re.compile(
    r"(?:(?:ch|clg|ceiling\s*(?:ht|height)?|affl|fcl|ht|h|@)\s*[:=]?\s*)?(?P<mm>[1-7]\d{3}|8000)\s*(?:mm|affl|fcl)?\b",
    re.IGNORECASE,
)
_MATERIAL_CODE_RE = re.compile(
    r"\b(?P<code>(?:CL|CEIL|C|IPF|FPB|WFPB|WPB|CLD|AC|PB|FC|GYP|MRC|TIM|BHK)[A-Z0-9\-]{0,5}|GRID|BULKHEAD|SOFFIT|EXPOSED)\b",
    re.IGNORECASE,
)


def _clean(value: object) -> str:
    return str(value or "").strip()


def _canonical_sha(payload: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _point_in_polygon(pt: tuple[float, float], polygon: Sequence[tuple[float, float]]) -> bool:
    """Ray-casting point-in-polygon test (coordinate-frame invariant)."""
    if len(polygon) < 3:
        return False
    x, y = pt
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]
        if ((yi > y) != (yj > y)) and (x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-12) + xi):
            inside = not inside
        j = i
    return inside


def _polygon_area_abs(polygon: Sequence[tuple[float, float]]) -> float:
    if len(polygon) < 3:
        return 0.0
    total = 0.0
    n = len(polygon)
    for i in range(n):
        x0, y0 = polygon[i]
        x1, y1 = polygon[(i + 1) % n]
        total += x0 * y1 - x1 * y0
    return abs(total) * 0.5


@dataclass(frozen=True)
class RcpLineageRef:
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str

    def normalized(self) -> tuple[str, str, str, str, str]:
        return (
            _clean(self.document_id),
            _clean(self.revision_id),
            _clean(self.source_sha256).lower(),
            _clean(self.page_id),
            _clean(self.viewport_id),
        )

    def is_valid(self) -> bool:
        return all(bool(v) for v in self.normalized())


@dataclass(frozen=True)
class RcpCeilingZonePolygon:
    """Verified physical ceiling zone or bulkhead sub-zone polygon."""

    zone_id: str
    lineage: RcpLineageRef
    polygon_pdf_pts: tuple[tuple[float, float], ...]
    parent_zone_id: str | None = None
    is_bulkhead_subzone: bool = False


@dataclass(frozen=True)
class RcpMaterialHeightBubble:
    """Source-owned RCP callout bubble/pill/text group."""

    bubble_id: str
    lineage: RcpLineageRef
    anchor_pt: tuple[float, float]
    lines: tuple[str, ...]
    leader_target_pt: tuple[float, float] | None = None
    in_legend_region: bool = False
    text_integrity_trusted: bool = True


@dataclass(frozen=True)
class RcpZoneHeightMaterialAssociation:
    zone_id: str
    parent_zone_id: str | None
    is_bulkhead_subzone: bool
    resolved: bool
    abstained: bool
    material_code: str | None
    height_mm: int | None
    raked_height_range_mm: tuple[int, int] | None
    ownership_mode: str | None  # "interior_containment" | "explicit_leader"
    supporting_bubble_ids: tuple[str, ...]
    blocking_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "zone_id": self.zone_id,
            "parent_zone_id": self.parent_zone_id,
            "is_bulkhead_subzone": self.is_bulkhead_subzone,
            "resolved": self.resolved,
            "abstained": self.abstained,
            "material_code": self.material_code,
            "height_mm": self.height_mm,
            "raked_height_range_mm": list(self.raked_height_range_mm) if self.raked_height_range_mm else None,
            "ownership_mode": self.ownership_mode,
            "supporting_bubble_ids": list(self.supporting_bubble_ids),
            "blocking_reasons": list(self.blocking_reasons),
        }


@dataclass(frozen=True)
class RcpBubbleAssociationReport:
    report_id: str
    associations: tuple[RcpZoneHeightMaterialAssociation, ...]
    distinct_heights_preserved_mm: tuple[int, ...]
    rejected_bubble_ids: tuple[str, ...]
    rejection_reasons_by_bubble: dict[str, str]
    explicit_distinct_heights_preserved: bool = True
    cross_zone_height_flattening_forbidden: bool = True
    commercial_authority_granted: bool = False
    shadow_only: bool = True
    digest_sha256: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_id": self.report_id,
            "associations": [a.to_dict() for a in self.associations],
            "distinct_heights_preserved_mm": list(self.distinct_heights_preserved_mm),
            "rejected_bubble_ids": list(self.rejected_bubble_ids),
            "rejection_reasons_by_bubble": dict(self.rejection_reasons_by_bubble),
            "explicit_distinct_heights_preserved": True,
            "cross_zone_height_flattening_forbidden": True,
            "commercial_authority_granted": False,
            "shadow_only": True,
            "digest_sha256": self.digest_sha256,
        }


def parse_rcp_bubble_material_and_height(
    lines: Sequence[str],
) -> tuple[str | None, int | None, tuple[int, int] | None]:
    """Extract material code and flat or raked height (mm) from an RCP bubble."""
    joined = " ".join(_clean(line) for line in lines if _clean(line))
    if not joined:
        return (None, None, None)

    raked_range: tuple[int, int] | None = None
    flat_height: int | None = None

    m_raked = _RAKED_RANGE_RE.search(joined)
    if m_raked:
        lo, hi = int(m_raked.group("lo")), int(m_raked.group("hi"))
        if _MIN_CEILING_HEIGHT_MM <= min(lo, hi) and max(lo, hi) <= _MAX_CEILING_HEIGHT_MM and lo != hi:
            raked_range = (min(lo, hi), max(lo, hi))
    else:
        heights_found: list[int] = []
        for m_h in _SINGLE_HEIGHT_MM_RE.finditer(joined):
            val = int(m_h.group("mm"))
            if _MIN_CEILING_HEIGHT_MM <= val <= _MAX_CEILING_HEIGHT_MM:
                heights_found.append(val)
        unique_h = sorted(set(heights_found))
        if len(unique_h) == 1:
            flat_height = unique_h[0]

    # Strip recognized numeric heights before scanning material codes so digits don't collide
    cleaned_for_mat = _RAKED_RANGE_RE.sub(" ", joined)
    cleaned_for_mat = re.sub(r"\b[1-7]\d{3}\s*(?:mm|affl|fcl)?\b", " ", cleaned_for_mat, flags=re.IGNORECASE)
    mat_code: str | None = None
    for m_mat in _MATERIAL_CODE_RE.finditer(cleaned_for_mat):
        token = m_mat.group("code").upper()
        if token in {"CH", "CLG", "HT", "H", "AFFL", "FCL", "MM"}:
            continue
        mat_code = token
        break

    return (mat_code, flat_height, raked_range)


def associate_rcp_bubbles_to_ceiling_zones_shadow(
    zones: Sequence[RcpCeilingZonePolygon],
    bubbles: Sequence[RcpMaterialHeightBubble],
) -> RcpBubbleAssociationReport:
    """Associate RCP bubbles to ceiling zones while preserving distinct explicit heights."""
    valid_zones: list[RcpCeilingZonePolygon] = [
        z for z in zones if _clean(z.zone_id) and z.lineage.is_valid() and _polygon_area_abs(z.polygon_pdf_pts) > 1e-6
    ]
    zone_areas = {z.zone_id: _polygon_area_abs(z.polygon_pdf_pts) for z in valid_zones}
    zone_lineages = {z.zone_id: z.lineage.normalized() for z in valid_zones}

    bubbles_by_zone: dict[str, list[tuple[RcpMaterialHeightBubble, str]]] = {z.zone_id: [] for z in valid_zones}
    rejected_bubbles: list[str] = []
    rejection_reasons: dict[str, str] = {}

    for bubble in bubbles:
        bid = _clean(bubble.bubble_id) or "<bubble>"
        if bubble.in_legend_region:
            rejected_bubbles.append(bid)
            rejection_reasons[bid] = "legend_bubble_excluded_from_plan_zones"
            continue
        if not bubble.text_integrity_trusted:
            rejected_bubbles.append(bid)
            rejection_reasons[bid] = "untrusted_rcp_bubble_text_rejected"
            continue
        if not bubble.lineage.is_valid():
            rejected_bubbles.append(bid)
            rejection_reasons[bid] = "invalid_bubble_lineage"
            continue

        b_lin = bubble.lineage.normalized()
        same_lin_zones = [z for z in valid_zones if zone_lineages[z.zone_id] == b_lin]
        if not same_lin_zones:
            rejected_bubbles.append(bid)
            rejection_reasons[bid] = "cross_viewport_or_lineage_bubble_rejected"
            continue

        target_pt = bubble.leader_target_pt if bubble.leader_target_pt is not None else bubble.anchor_pt
        mode = "explicit_leader" if bubble.leader_target_pt is not None else "interior_containment"
        containing = [z for z in same_lin_zones if _point_in_polygon(target_pt, z.polygon_pdf_pts)]

        if not containing:
            rejected_bubbles.append(bid)
            rejection_reasons[bid] = "unowned_outside_zone_proximity_forbidden"
            continue

        # If a bubble sits inside a bulkhead subzone AND its explicit parent zone,
        # the child bulkhead subzone owns it (strictly preserving distinct bulkhead height!).
        if len(containing) > 1:
            children = [
                z for z in containing
                if z.is_bulkhead_subzone and z.parent_zone_id in {p.zone_id for p in containing}
            ]
            if len(children) == 1:
                owner_zone = children[0]
            else:
                rejected_bubbles.append(bid)
                rejection_reasons[bid] = "ambiguous_overlapping_ceiling_zones"
                continue
        else:
            owner_zone = containing[0]

        bubbles_by_zone[owner_zone.zone_id].append((bubble, mode))

    associations: list[RcpZoneHeightMaterialAssociation] = []
    distinct_heights: set[int] = set()

    for zone in sorted(valid_zones, key=lambda z: z.zone_id):
        assigned = bubbles_by_zone[zone.zone_id]
        z_reasons: list[str] = []
        mat_codes: set[str] = set()
        flat_heights: set[int] = set()
        raked_ranges: set[tuple[int, int]] = set()
        modes: set[str] = set()
        b_ids: list[str] = []

        for bubble, mode in assigned:
            b_ids.append(bubble.bubble_id)
            modes.add(mode)
            mat, h_mm, r_range = parse_rcp_bubble_material_and_height(bubble.lines)
            if mat is not None:
                mat_codes.add(mat)
            if h_mm is not None:
                flat_heights.add(h_mm)
            if r_range is not None:
                raked_ranges.add(r_range)

        if not assigned:
            z_reasons.append("no_owned_rcp_bubble_for_zone")
        if len(flat_heights) > 1:
            z_reasons.append("conflicting_heights_same_undivided_zone")
        if flat_heights and raked_ranges:
            z_reasons.append("conflicting_flat_and_raked_height_same_zone")
        if len(raked_ranges) > 1:
            z_reasons.append("conflicting_raked_height_ranges_same_zone")
        if len(mat_codes) > 1:
            z_reasons.append("conflicting_ceiling_materials_same_zone")
        if assigned and not flat_heights and not raked_ranges:
            z_reasons.append("rcp_bubble_missing_explicit_ceiling_height")

        resolved = not z_reasons and (len(flat_heights) == 1 or len(raked_ranges) == 1)
        out_height = next(iter(flat_heights)) if (resolved and len(flat_heights) == 1) else None
        out_raked = next(iter(raked_ranges)) if (resolved and len(raked_ranges) == 1) else None
        out_mat = next(iter(mat_codes)) if (resolved and len(mat_codes) == 1) else None
        out_mode = (
            next(iter(modes)) if len(modes) == 1 else ("mixed_interior_and_leader" if modes else None)
        )

        if out_height is not None:
            distinct_heights.add(out_height)

        associations.append(
            RcpZoneHeightMaterialAssociation(
                zone_id=zone.zone_id,
                parent_zone_id=zone.parent_zone_id,
                is_bulkhead_subzone=zone.is_bulkhead_subzone,
                resolved=resolved,
                abstained=not resolved,
                material_code=out_mat,
                height_mm=out_height,
                raked_height_range_mm=out_raked,
                ownership_mode=out_mode if resolved else None,
                supporting_bubble_ids=tuple(sorted(b_ids)),
                blocking_reasons=tuple(dict.fromkeys(z_reasons)),
            )
        )

    payload = {
        "associations": [a.to_dict() for a in associations],
        "distinct_heights_preserved_mm": sorted(distinct_heights),
        "rejected_bubble_ids": sorted(rejected_bubbles),
        "rejection_reasons_by_bubble": dict(sorted(rejection_reasons.items())),
    }
    digest = _canonical_sha(payload)
    return RcpBubbleAssociationReport(
        report_id=f"rcp_bubble_assoc_{digest[:16]}",
        associations=tuple(associations),
        distinct_heights_preserved_mm=tuple(sorted(distinct_heights)),
        rejected_bubble_ids=tuple(sorted(rejected_bubbles)),
        rejection_reasons_by_bubble=dict(sorted(rejection_reasons.items())),
        explicit_distinct_heights_preserved=True,
        cross_zone_height_flattening_forbidden=True,
        commercial_authority_granted=False,
        shadow_only=True,
        digest_sha256=digest,
    )
