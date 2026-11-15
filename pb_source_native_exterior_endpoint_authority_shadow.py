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

from pb_migration_contracts import EvidenceResolutionStatus
from pb_new_exterior_wall_preflight import attempt_source_native_outer_wall_first
from pb_new_wall_graph_diagnostic import NativeWallEndpointNearMiss

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


def _rows_for_paths(
    drawings: Sequence[Mapping[str, Any] | object],
    paths: Sequence[int],
) -> tuple[Mapping[str, Any] | None, ...]:
    out = []
    for index in paths:
        if 0 <= index < len(drawings) and isinstance(drawings[index], Mapping):
            out.append(drawings[index])
        else:
            out.append(None)
    return tuple(out)


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
    left_layers = tuple(str(row.get("layer") or "") for row in left_rows if row)
    right_layers = tuple(str(row.get("layer") or "") for row in right_rows if row)
    if any(_competing_non_wall_layer(layer) for layer in (*left_layers, *right_layers)):
        return EvidenceResolutionStatus.ABSTAINED, REASON_COMPETING
    if opening_chassis_witness:
        return EvidenceResolutionStatus.ABSTAINED, REASON_OPENING_TOPOLOGY
    if not math.isfinite(separation_pdf_pts) or separation_pdf_pts > CONTACT_PT:
        return EvidenceResolutionStatus.ABSTAINED, REASON_NEAR_MISS
    if not (
        left_rows and right_rows
        and all(_is_painted_exterior_layer(row) for row in left_rows if row)
        and all(_is_painted_exterior_layer(row) for row in right_rows if row)
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
    unresolved = sum(1 for item in receipts if item.reason == REASON_NEAR_MISS)
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
        "physical_wall_authenticated": False,
        "measurement_authorized": False,
        "commercial_publishable": False,
        "can_issue_area": False,
        "official_frozen120_score_change": 0,
    }
