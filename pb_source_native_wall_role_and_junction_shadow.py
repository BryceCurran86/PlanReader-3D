"""Shadow: source-role wall segments, junctions, and false-bridge negatives.

Cursor-owned original-app slice. Reuses the layered ring producer (filled
strips, paired faces, optional heavy strokes, existing 0.05 pt noise). Does
not edit GPT1's raster collector, does not inflate snap to 2.5 pt, and does
not mint walls from a morphological hull. Raster traces are a supporting cue
only.

Roles are unique-or-abstain. Unknown, competing, or missing evidence stays
UNKNOWN / ABSTAINED. Virtual closures remain topology-only.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from shapely.geometry import LineString

from pb_external_footprint_first_trace import ExternalFootprintTrace
from pb_layered_wall_doorway_room_ring_shadow import (
    NOISE_PT,
    _collect_source_heavy_stroke_strips,
    _collect_stroke_pair_strips,
    _collect_strips,
    _owner_excluded_green_ink,
    build_layered_wall_doorway_room_rings,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_native_exterior_edge_path_ownership import (
    enrich_open_to_exterior_span,
    own_exterior_contour_native_paths,
)
from pb_wall_layer_evidence_shadow import is_explicit_wall_layer_name

CONTACT_PT = 0.03  # representation contact only; not the 2.5 pt production snap
_AXIS_PT = 2.0
_EXCLUSION_LAYER_TOKENS = frozenset({
    "dim", "dimension", "hatch", "furniture", "furn", "roof", "eave", "eaves",
    "site", "title", "text", "grid", "viewport", "border", "frame", "hatching",
})


ROLE_EXTERIOR_OUTER_FACE = "exterior_outer_face_candidate"
ROLE_ATTACHED_STRUCTURE = "attached_porch_carport_candidate"
ROLE_INTERNAL_WALL = "internal_wall_candidate"
ROLE_OPENING_GAP = "opening_gap_unauthenticated"
ROLE_EXCLUSION = "exclusion_site_roof_hatch_title_green"
ROLE_DIAGONAL_BRIDGE = "rejected_diagonal_bridge"
ROLE_UNKNOWN = "unknown"


def _dashed(row: Mapping[str, Any]) -> bool:
    token = "".join(str(row.get("dashes") or "").split())
    return token not in {"", "[]0"}


def _xy(point: Any) -> tuple[float, float]:
    if hasattr(point, "x"):
        return float(point.x), float(point.y)
    return float(point[0]), float(point[1])


def _layer_tokens(row: Mapping[str, Any]) -> frozenset[str]:
    import re
    return frozenset(re.findall(r"[a-z0-9]+", str(row.get("layer") or "").lower()))


def _is_diagonal_row(row: Mapping[str, Any]) -> bool:
    items = list(row.get("items") or ())
    if not items:
        return False
    lines = [item for item in items if item and item[0] == "l" and len(item) >= 3]
    if not lines or any(item[0] not in {"l", "re", "qu"} for item in items if item):
        return False
    for item in lines:
        start, end = _xy(item[1]), _xy(item[2])
        if abs(start[0] - end[0]) > _AXIS_PT and abs(start[1] - end[1]) > _AXIS_PT:
            return True
    return False


def classify_native_path_role(
    row: Mapping[str, Any] | object,
    path_index: int,
    *,
    exterior_owner_indices: frozenset[int] = frozenset(),
    attached_indices: frozenset[int] = frozenset(),
    page_bounds: tuple[float, float, float, float] | None = None,
) -> str:
    """Typed source role for one original path. Unique-or-abstain; never size-only."""
    if not isinstance(row, Mapping):
        return ROLE_UNKNOWN
    fill, stroke = row.get("fill"), row.get("color")
    if _owner_excluded_green_ink(fill) or _owner_excluded_green_ink(stroke):
        return ROLE_EXCLUSION
    if _dashed(row):
        return ROLE_EXCLUSION
    tokens = _layer_tokens(row)
    if tokens & _EXCLUSION_LAYER_TOKENS or any(
        token.startswith("dim") for token in tokens
    ):
        return ROLE_EXCLUSION
    if page_bounds is not None:
        try:
            rect = row.get("rect")
            y1 = float(rect.y1) if rect is not None else None
        except (TypeError, ValueError, AttributeError):
            y1 = None
        if y1 is not None:
            _, y0_page, _, y1_page = page_bounds
            height = y1_page - y0_page
            if height > 0 and y1 >= y0_page + 0.82 * height:
                return ROLE_EXCLUSION
    if _is_diagonal_row(row):
        return ROLE_DIAGONAL_BRIDGE
    if path_index in exterior_owner_indices:
        return ROLE_EXTERIOR_OUTER_FACE
    if path_index in attached_indices:
        return ROLE_ATTACHED_STRUCTURE
    if is_explicit_wall_layer_name(str(row.get("layer") or "")):
        return ROLE_INTERNAL_WALL
    return ROLE_UNKNOWN


@dataclass(frozen=True)
class NativePathRoleRecord:
    path_index: int
    role: str
    status: EvidenceResolutionStatus
    topology_only: bool = True
    physical_wall_authenticated: bool = False
    can_issue_area: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "path_index": self.path_index,
            "role": self.role,
            "status": self.status.value,
            "topology_only": True,
            "physical_wall_authenticated": False,
            "can_issue_area": False,
        }


@dataclass(frozen=True)
class SourceWallJunctionReport:
    status: EvidenceResolutionStatus
    reason: str
    path_roles: tuple[NativePathRoleRecord, ...]
    wall_segment_native_path_indices: tuple[int, ...]
    heavy_stroke_band_count: int
    stroke_pair_band_count: int
    filled_strip_count: int
    junction_count: int
    open_endpoint_count: int
    unresolved_open_spans: tuple[dict[str, object], ...]
    rejected_diagonal_bridge_count: int
    invented_door_bridge_count: int
    commercial_publishable: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        role_counts: dict[str, int] = {}
        for record in self.path_roles:
            role_counts[record.role] = role_counts.get(record.role, 0) + 1
        return {
            "status": self.status.value,
            "reason": self.reason,
            "role_counts": role_counts,
            "wall_segment_native_path_indices": list(self.wall_segment_native_path_indices),
            "heavy_stroke_band_count": self.heavy_stroke_band_count,
            "stroke_pair_band_count": self.stroke_pair_band_count,
            "filled_strip_count": self.filled_strip_count,
            "junction_count": self.junction_count,
            "open_endpoint_count": self.open_endpoint_count,
            "unresolved_open_spans": list(self.unresolved_open_spans),
            "rejected_diagonal_bridge_count": self.rejected_diagonal_bridge_count,
            "invented_door_bridge_count": self.invented_door_bridge_count,
            "commercial_publishable": False,
            "measurement_authorized": False,
            "can_issue_area": False,
        }


def _strip_tips(strip: Any) -> tuple[tuple[float, float], tuple[float, float]]:
    x0, y0, x1, y1 = (float(v) for v in strip.polygon.bounds)
    if (x1 - x0) > (y1 - y0):
        return ((x0, (y0 + y1) / 2.0), (x1, (y0 + y1) / 2.0))
    return (((x0 + x1) / 2.0, y0), ((x0 + x1) / 2.0, y1))


def _count_junctions_and_open_ends(strips: Sequence[Any]) -> tuple[int, int]:
    """0.03 pt contact only. No 2.5 pt snap and no invented join."""
    valid = [s for s in strips if getattr(s, "polygon", None) is not None and not s.polygon.is_empty]
    junctions = 0
    open_ends = 0
    for i, strip in enumerate(valid):
        for tip in _strip_tips(strip):
            point = LineString((tip, tip))
            hit = 0
            for j, other in enumerate(valid):
                if i == j:
                    continue
                if other.polygon.distance(point) <= CONTACT_PT:
                    hit += 1
            if hit:
                junctions += 1
            else:
                open_ends += 1
    return junctions, open_ends


def identify_source_wall_junctions_and_roles(
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    source_sha256: str,
    page_index: int,
    trace: ExternalFootprintTrace | None = None,
    page_bounds: tuple[float, float, float, float] | None = None,
) -> SourceWallJunctionReport:
    """Wall/junction/opening identity on the original engine. Never a second footprint."""
    filled, _other = _collect_strips(drawings)
    pairs = _collect_stroke_pair_strips(drawings)
    heavy = _collect_source_heavy_stroke_strips(drawings)
    ring = build_layered_wall_doorway_room_rings(
        drawings,
        source_sha256=source_sha256,
        page_index=page_index,
        sliding_leaf_frame_closure=True,
        dark_painted_wall_source=True,
        wall_end_stroke_closures=False,
        source_heavy_stroke_wall_bands=True,
    )
    exterior_owners: set[int] = set()
    attached: set[int] = set()
    if trace is not None and trace.status == "CANDIDATE" and trace.bbox_pdf_pts:
        owned = own_exterior_contour_native_paths(
            drawings, trace, closures=ring.closures,
        )
        for edge in owned:
            if edge.classification == "source_native_wall_ink_candidate":
                exterior_owners.update(edge.native_path_indices)
        x0, y0, x1, y1 = trace.bbox_pdf_pts
        padx = min(24.0, max(3.0, (x1 - x0) * 0.02))
        pady = min(24.0, max(3.0, (y1 - y0) * 0.02))
        for index, raw in enumerate(drawings):
            if not isinstance(raw, Mapping) or not raw.get("items"):
                continue
            box = raw.get("rect")
            if box is None:
                continue
            try:
                a, b, c, d = map(float, (box.x0, box.y0, box.x1, box.y1))
            except (TypeError, ValueError, AttributeError):
                continue
            outside = c < x0 - padx or a > x1 + padx or d < y0 - pady or b > y1 + pady
            if outside and not _dashed(raw) and not _owner_excluded_green_ink(raw.get("color")):
                if is_explicit_wall_layer_name(str(raw.get("layer") or "")):
                    attached.add(index)
    roles: list[NativePathRoleRecord] = []
    rejected_diagonals = 0
    for index, raw in enumerate(drawings):
        if not isinstance(raw, Mapping) or not raw.get("items"):
            continue
        role = classify_native_path_role(
            raw, index,
            exterior_owner_indices=frozenset(exterior_owners),
            attached_indices=frozenset(attached),
            page_bounds=page_bounds,
        )
        if role == ROLE_DIAGONAL_BRIDGE:
            rejected_diagonals += 1
        status = (
            EvidenceResolutionStatus.ABSTAINED
            if role in {ROLE_UNKNOWN, ROLE_EXCLUSION, ROLE_DIAGONAL_BRIDGE, ROLE_OPENING_GAP}
            else EvidenceResolutionStatus.CANDIDATE
        )
        roles.append(NativePathRoleRecord(index, role, status))
    spans = []
    invented = 0
    for witness in ring.unresolved_gap_witnesses:
        receipt = enrich_open_to_exterior_span(
            drawings, witness, closures=ring.closures,
        )
        payload = receipt.to_dict()
        payload["role"] = ROLE_OPENING_GAP
        spans.append(payload)
        if receipt.missing_jamb_opening_evidence:
            invented += 1
    junctions, open_ends = _count_junctions_and_open_ends(
        list(filled) + list(pairs) + list(heavy),
    )
    wall_paths = tuple(sorted({
        *exterior_owners,
        *(index for strip in filled for index in strip.native_path_indices()),
        *(index for strip in pairs for index in strip.native_path_indices()),
        *(index for strip in heavy for index in strip.native_path_indices()),
    }))
    return SourceWallJunctionReport(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason="source_wall_roles_and_junctions_need_authenticated_exterior_cycle",
        path_roles=tuple(roles),
        wall_segment_native_path_indices=wall_paths,
        heavy_stroke_band_count=len(heavy),
        stroke_pair_band_count=len(pairs),
        filled_strip_count=len(filled),
        junction_count=junctions,
        open_endpoint_count=open_ends,
        unresolved_open_spans=tuple(spans),
        rejected_diagonal_bridge_count=rejected_diagonals,
        invented_door_bridge_count=invented,
    )
