"""Shadow: unique-or-abstain exterior endpoint receipts on the #4347 native graph.

Compatibility bridge only. Reuses GPT1 near-miss diagnostics and heavy-stroke
collectors; does not copy them, does not join on 2.5 pt commercial snap, and
does not treat a raster hull as a wall. A near-miss, including 0.4252 pt, is
never an automatic junction.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from pb_layered_wall_doorway_room_ring_shadow import _owner_excluded_green_ink
from pb_migration_contracts import EvidenceResolutionStatus
from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
from pb_new_wall_graph_diagnostic import NativeWallEndpointNearMiss
from pb_wall_layer_evidence_shadow import is_explicit_wall_layer_name

CONTACT_PT = 0.03
_COMPETING_TOKENS = (
    "joinery", "slab", "anno", "annotation", "furniture", "furn",
    "hatch", "dim", "title", "site", "text", "grid", "border", "viewport",
)

REASON_NEAR_MISS = "near_miss_unauthenticated_no_elbow_jamb_or_opening"
REASON_COMPETING = "competing_non_wall_source_role"
REASON_CONTACT_CANDIDATE = "representation_contact_needs_physical_wall_proof"
REASON_OPENING_TOPOLOGY = "opening_chassis_topology_only_not_wall_join"
REASON_UNWITNESSED_GAP = "unwitnessed_collinear_span_not_a_door"
REASON_MISSING_NATIVE_PATH_OWNER = "native_source_path_owner_missing"
REASON_INVALID_SEPARATION = "negative_or_nonfinite_separation_not_contact"
REASON_FOREIGN_VIEW = "foreign_view_path_index_collision"
REASON_SELF_PATH_COLLISION = "native_path_owners_not_disjoint"

ROLE_EXTERIOR_OUTER_FACE = "exterior_outer_face_candidate"
ROLE_INTERNAL_WALL = "internal_wall_candidate"
ROLE_EXCLUSION = "exclusion_site_roof_hatch_title_green"
ROLE_DIAGONAL_BRIDGE = "rejected_diagonal_bridge"
ROLE_UNKNOWN = "unknown"
_AXIS_PT = 2.0


def _layer_compact(layer: str) -> str:
    return "".join(c for c in str(layer).lower() if c.isalnum())


def _competing_non_wall_layer(layer: str) -> bool:
    compact = _layer_compact(layer)
    return any(token in compact for token in _COMPETING_TOKENS)


def _is_painted_exterior_layer(row: Mapping[str, Any] | None) -> bool:
    if not isinstance(row, Mapping) or row.get("fill") is None:
        return False
    compact = _layer_compact(str(row.get("layer") or ""))
    return "wall" in compact and "external" in compact


def _dashed(row: Mapping[str, Any]) -> bool:
    token = "".join(str(row.get("dashes") or "").split())
    return token not in {"", "[]0"}


def _xy(point: Any) -> tuple[float, float]:
    if hasattr(point, "x"):
        return float(point.x), float(point.y)
    return float(point[0]), float(point[1])


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


def classify_source_native_path_role(row: Mapping[str, Any] | object) -> str:
    """Unique-or-abstain source role. Raster hulls and snap joins are not roles."""
    if not isinstance(row, Mapping):
        return ROLE_UNKNOWN
    if _owner_excluded_green_ink(row.get("fill")) or _owner_excluded_green_ink(row.get("color")):
        return ROLE_EXCLUSION
    if _dashed(row):
        return ROLE_EXCLUSION
    layer = str(row.get("layer") or "")
    if _competing_non_wall_layer(layer):
        return ROLE_EXCLUSION
    if _is_diagonal_row(row):
        return ROLE_DIAGONAL_BRIDGE
    compact = _layer_compact(layer)
    if "wall" in compact and "external" in compact:
        return ROLE_EXTERIOR_OUTER_FACE
    if is_explicit_wall_layer_name(layer):
        return ROLE_INTERNAL_WALL
    return ROLE_UNKNOWN


@dataclass(frozen=True)
class ExteriorEndpointReceipt:
    tip_pdf_pts: tuple[float, float]
    native_path_ids: tuple[int, ...]
    native_source_layers: tuple[str, ...]
    nearby_native_path_ids: tuple[int, ...]
    nearby_source_layers: tuple[str, ...]
    separation_pdf_pts: float
    status: EvidenceResolutionStatus
    reason: str
    physical_join_authenticated: bool = False
    opening_authenticated: bool = False
    can_issue_area: bool = False
    measurement_authorized: bool = False

    def to_dict(self) -> dict[str, object]:
        return {
            "tip_pdf_pts": list(self.tip_pdf_pts),
            "native_path_ids": list(self.native_path_ids),
            "native_source_layers": list(self.native_source_layers),
            "nearby_native_path_ids": list(self.nearby_native_path_ids),
            "nearby_source_layers": list(self.nearby_source_layers),
            "separation_pdf_pts": self.separation_pdf_pts,
            "status": self.status.value,
            "reason": self.reason,
            "physical_join_authenticated": False,
            "opening_authenticated": False,
            "can_issue_area": False,
            "measurement_authorized": False,
        }


def _is_path_index(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _rows_for_paths(
    drawings: Sequence[Mapping[str, Any] | object],
    paths: Sequence[int],
) -> tuple[Mapping[str, Any], ...] | None:
    if not paths:
        return None
    owned: list[Mapping[str, Any]] = []
    for index in paths:
        if not _is_path_index(index):
            return None
        if not (0 <= index < len(drawings)):
            return None
        row = drawings[index]
        if not isinstance(row, Mapping):
            return None
        owned.append(row)
    return tuple(owned)


def _viewport_identity(row: Mapping[str, Any]) -> str:
    for key in (
        "source_viewport_id",
        "source_viewport_ownership_id",
        "viewport_id",
    ):
        value = row.get(key)
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def authenticate_external_wall_junction(
    *,
    native_path_ids: Sequence[int],
    nearby_native_path_ids: Sequence[int],
    separation_pdf_pts: float,
    drawings: Sequence[Mapping[str, Any] | object],
    opening_chassis_witness: bool = False,
) -> tuple[EvidenceResolutionStatus, str]:
    """Unique-or-abstain join. Near-miss distance is never a wall."""
    left_rows = _rows_for_paths(drawings, native_path_ids)
    right_rows = _rows_for_paths(drawings, nearby_native_path_ids)
    if left_rows is None or right_rows is None:
        return EvidenceResolutionStatus.ABSTAINED, REASON_MISSING_NATIVE_PATH_OWNER
    left_ids = tuple(native_path_ids)
    right_ids = tuple(nearby_native_path_ids)
    if (
        len(left_ids) != len(set(left_ids))
        or len(right_ids) != len(set(right_ids))
        or not set(left_ids).isdisjoint(set(right_ids))
    ):
        return EvidenceResolutionStatus.ABSTAINED, REASON_SELF_PATH_COLLISION
    left_layers = tuple(str(row.get("layer") or "") for row in left_rows)
    right_layers = tuple(str(row.get("layer") or "") for row in right_rows)
    if any(_competing_non_wall_layer(layer) for layer in (*left_layers, *right_layers)):
        return EvidenceResolutionStatus.ABSTAINED, REASON_COMPETING
    viewports = tuple(_viewport_identity(row) for row in (*left_rows, *right_rows))
    if any(viewports) and (not all(viewports) or len(set(viewports)) != 1):
        return EvidenceResolutionStatus.ABSTAINED, REASON_FOREIGN_VIEW
    if opening_chassis_witness:
        return EvidenceResolutionStatus.ABSTAINED, REASON_OPENING_TOPOLOGY
    if not math.isfinite(separation_pdf_pts) or separation_pdf_pts < 0:
        return EvidenceResolutionStatus.ABSTAINED, REASON_INVALID_SEPARATION
    if separation_pdf_pts > CONTACT_PT:
        return EvidenceResolutionStatus.ABSTAINED, REASON_NEAR_MISS
    if not (
        all(_is_painted_exterior_layer(row) for row in left_rows)
        and all(_is_painted_exterior_layer(row) for row in right_rows)
    ):
        return EvidenceResolutionStatus.ABSTAINED, REASON_NEAR_MISS
    return EvidenceResolutionStatus.CANDIDATE, REASON_CONTACT_CANDIDATE


def receipt_from_near_miss(
    miss: NativeWallEndpointNearMiss,
    drawings: Sequence[Mapping[str, Any] | object],
    *,
    opening_chassis_witness: bool = False,
) -> ExteriorEndpointReceipt:
    status, reason = authenticate_external_wall_junction(
        native_path_ids=miss.native_path_ids,
        nearby_native_path_ids=miss.nearby_native_path_ids,
        separation_pdf_pts=float(miss.separation_pdf_pts),
        drawings=drawings,
        opening_chassis_witness=opening_chassis_witness,
    )
    return ExteriorEndpointReceipt(
        tip_pdf_pts=miss.tip_pdf_pts,
        native_path_ids=miss.native_path_ids,
        native_source_layers=miss.native_source_layers,
        nearby_native_path_ids=miss.nearby_native_path_ids,
        nearby_source_layers=miss.nearby_source_layers,
        separation_pdf_pts=float(miss.separation_pdf_pts),
        status=status,
        reason=reason,
    )


def audit_source_native_exterior_endpoints(
    drawings: Sequence[Mapping[str, Any] | object],
) -> dict[str, object]:
    """Per-page joined / outside / unresolved census. Zero quantities."""
    attempt = attempt_source_native_outer_wall_first(drawings)
    live_graph = attempt.graph
    receipts = tuple(
        receipt_from_near_miss(miss, drawings)
        for miss in live_graph.endpoint_near_misses
    )
    joined = sum(1 for item in receipts if item.status is EvidenceResolutionStatus.CANDIDATE)
    competing = sum(1 for item in receipts if item.reason == REASON_COMPETING)
    unresolved = sum(
        1
        for item in receipts
        if item.reason in (
            REASON_NEAR_MISS,
            REASON_MISSING_NATIVE_PATH_OWNER,
            REASON_INVALID_SEPARATION,
            REASON_FOREIGN_VIEW,
            REASON_SELF_PATH_COLLISION,
        )
    )
    role_counts: dict[str, int] = {}
    for raw in drawings:
        if not isinstance(raw, Mapping) or not raw.get("items"):
            continue
        role = classify_source_native_path_role(raw)
        role_counts[role] = role_counts.get(role, 0) + 1
    return {
        "exterior_preflight_status": attempt.status,
        "exterior_preflight_reason": attempt.reason,
        "source_wall_path_ids": list(attempt.source_wall_path_ids),
        "component_count": live_graph.component_count,
        "open_endpoint_count": len(live_graph.largest_component_open_endpoints_pdf_pts),
        "near_miss_total": live_graph.endpoint_near_miss_total,
        "endpoint_receipts": [item.to_dict() for item in receipts],
        "joined_candidate_count": joined,
        "competing_non_wall_count": competing,
        "unresolved_near_miss_count": unresolved,
        "path_role_counts": role_counts,
        "rejected_diagonal_bridge_count": role_counts.get(ROLE_DIAGONAL_BRIDGE, 0),
        "exclusion_count": role_counts.get(ROLE_EXCLUSION, 0),
        "physical_wall_authenticated": False,
        "measurement_authorized": False,
        "commercial_publishable": False,
        "can_issue_area": False,
        "official_frozen120_score_change": 0,
    }
