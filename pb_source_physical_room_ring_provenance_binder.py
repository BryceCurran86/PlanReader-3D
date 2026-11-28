"""Generic physical room-ring provenance binder (MAX #7236315096, Claude #7236464810).

When a candidate floor-surface cell fails the zero-physical-wall-support veto
(``FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT`` — e.g., a drafting/floor-grid cell),
this module checks whether a **unique**, producer-owned physical room ring
(``LayeredRoomRingRecord`` or compatible ring object) on the exact same
``source_sha256`` and ``page_index``:

1. Strictly contains the room's label anchor point,
2. Carries positive wall enclosure (``wall_edge_count > 0`` and
   ``len(bounding_wall_path_indices) > 0``), and
3. Passes the exact same injected ``wall_support_predicate`` (non-vetoed).

If exactly one qualifying physical ring exists, the room's independent
figured-dimension / explicit-area, floor-finish, and RCP ceiling provenance
are bound to that physical ring record (preserving the original explicit area
value and dimension anchors untouched — never forcing or inventing an area).

If zero qualifying rings exist (e.g., an unenclosed open-plan zone), the room
stays strictly **withheld** under the false-cell veto. If more than one
qualifying ring contains the anchor, the binder fails closed with ``CONFLICT``.

Default-off / shadow-only contract (``shadow_only=True``,
``commercial_authority_granted=False``). Zero job-specific rules.
"""
from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
import math
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_floor_surface_wall_support_veto import (
    FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT,
    FloorSurfaceWallSupportInput,
    evaluate_floor_surface_zero_wall_support_veto,
)

SCHEMA_VERSION = "1.0.0"

ORIGINAL_SURFACE_WALL_SUPPORTED_RETAINED = "original_surface_wall_supported_retained"
PHYSICAL_ROOM_RING_PROVENANCE_REBOUND = "physical_room_ring_provenance_rebound"
NO_QUALIFYING_PHYSICAL_ROOM_RING_FOR_LABEL = "no_qualifying_physical_room_ring_for_label"
AMBIGUOUS_MULTIPLE_PHYSICAL_ROOM_RINGS_FOR_LABEL = (
    "ambiguous_multiple_physical_room_rings_for_label"
)
INVALID_ROOM_LABEL_ANCHOR = "invalid_room_label_anchor"


@dataclass(frozen=True)
class RoomProvenanceBindingCandidate:
    """One candidate floor surface + its room label anchor and independent provenance."""

    surface: FloorSurfaceWallSupportInput
    page_index: int
    room_label_anchor_pdf_pt: tuple[float, float]
    explicit_area_m2: float | None = None
    explicit_area_authority: str | None = None
    explicit_area_evidence_ids: tuple[str, ...] = ()
    floor_finish_code: str | None = None
    floor_finish_evidence_ids: tuple[str, ...] = ()
    rcp_ceiling_material: str | None = None
    rcp_ceiling_height_mm: int | None = None
    rcp_ceiling_evidence_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PhysicalRoomRingProvenanceBinding:
    """Typed provenance binding verdict for one room candidate."""

    original_surface_entity_id: str
    quantity_id: str
    status: EvidenceResolutionStatus
    withheld: bool
    bound_surface_entity_id: str | None
    bound_ring_record_id: str | None
    bound_ring_area_pt2: float | None
    bound_ring_closure_ids: tuple[str, ...]
    wall_support_fraction: float
    explicit_area_m2: float | None
    explicit_area_authority: str | None
    explicit_area_evidence_ids: tuple[str, ...]
    floor_finish_code: str | None
    floor_finish_evidence_ids: tuple[str, ...]
    rcp_ceiling_material: str | None
    rcp_ceiling_height_mm: int | None
    rcp_ceiling_evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    shadow_only: bool = True
    commercial_authority_granted: bool = False
    schema_version: str = SCHEMA_VERSION


def _point_in_polygon(
    pt: tuple[float, float],
    polygon: Sequence[tuple[float, float]],
) -> bool:
    """Ray-casting point-in-polygon test in unrotated PDF page coordinates."""
    if len(polygon) < 3:
        return False
    px, py = float(pt[0]), float(pt[1])
    if not (math.isfinite(px) and math.isfinite(py)):
        return False
    inside = False
    n = len(polygon)
    j = n - 1
    for i in range(n):
        xi, yi = float(polygon[i][0]), float(polygon[i][1])
        xj, yj = float(polygon[j][0]), float(polygon[j][1])
        if not (
            math.isfinite(xi) and math.isfinite(yi)
            and math.isfinite(xj) and math.isfinite(yj)
        ):
            return False
        intersects = ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / ((yj - yi) + 1e-30) + xi
        )
        if intersects:
            inside = not inside
        j = i
    return inside


def _ring_attr(ring: Any, name: str, default: Any = None) -> Any:
    if isinstance(ring, dict):
        return ring.get(name, default)
    return getattr(ring, name, default)


def bind_room_provenance_to_physical_rings_shadow(
    *,
    candidates: Sequence[RoomProvenanceBindingCandidate],
    physical_rings: Sequence[Any],
    drawings: Sequence[Any],
    wall_support_predicate: Callable[..., Any],
    expected_document_id: str,
    expected_revision_id: str,
    expected_source_sha256: str,
    closures: Sequence[Any] = (),
) -> tuple[PhysicalRoomRingProvenanceBinding, ...]:
    """Bind explicit-area, floor-finish, and RCP provenance to wall-supported physical rings.

    - Retains candidate surfaces that already pass ``evaluate_floor_surface_zero_wall_support_veto``.
    - For false cells vetoed with ``FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT``,
      attempts unique physical-ring rebinding via room-label anchor containment
      and the exact same ``wall_support_predicate``.
    - Keeps unenclosed zones (0 qualifying rings) strictly withheld.
    """
    if not candidates:
        return ()

    base_verdicts = evaluate_floor_surface_zero_wall_support_veto(
        surfaces=tuple(c.surface for c in candidates),
        drawings=drawings,
        wall_support_predicate=wall_support_predicate,
        expected_document_id=expected_document_id,
        expected_revision_id=expected_revision_id,
        expected_source_sha256=expected_source_sha256,
        closures=closures,
    )

    # Pre-validate candidate rings for scope & positive wall enclosure.
    scoped_rings: list[tuple[Any, tuple[tuple[float, float], ...]]] = []
    for ring in physical_rings:
        ring_sha = str(_ring_attr(ring, "source_sha256", "") or "").strip()
        if ring_sha != expected_source_sha256:
            continue
        wall_edges = int(_ring_attr(ring, "wall_edge_count", 0) or 0)
        wall_paths = tuple(_ring_attr(ring, "bounding_wall_path_indices", ()) or ())
        poly = tuple(_ring_attr(ring, "polygon_pdf_pts", ()) or ())
        if wall_edges <= 0 or not wall_paths or len(poly) < 3:
            continue
        scoped_rings.append((ring, poly))

    results: list[PhysicalRoomRingProvenanceBinding] = []
    for cand, base in zip(candidates, base_verdicts):
        surf = cand.surface
        # Case 1: Original surface already has positive physical wall / candidate support.
        if not base.vetoed:
            results.append(
                PhysicalRoomRingProvenanceBinding(
                    original_surface_entity_id=surf.surface_entity_id,
                    quantity_id=surf.quantity_id,
                    status=EvidenceResolutionStatus.CORROBORATED,
                    withheld=False,
                    bound_surface_entity_id=surf.surface_entity_id,
                    bound_ring_record_id=None,
                    bound_ring_area_pt2=None,
                    bound_ring_closure_ids=(),
                    wall_support_fraction=base.supported_fraction,
                    explicit_area_m2=cand.explicit_area_m2,
                    explicit_area_authority=cand.explicit_area_authority,
                    explicit_area_evidence_ids=cand.explicit_area_evidence_ids,
                    floor_finish_code=cand.floor_finish_code,
                    floor_finish_evidence_ids=cand.floor_finish_evidence_ids,
                    rcp_ceiling_material=cand.rcp_ceiling_material,
                    rcp_ceiling_height_mm=cand.rcp_ceiling_height_mm,
                    rcp_ceiling_evidence_ids=cand.rcp_ceiling_evidence_ids,
                    reason_codes=(
                        ORIGINAL_SURFACE_WALL_SUPPORTED_RETAINED,
                        *base.reason_codes,
                    ),
                )
            )
            continue

        # Case 2: Vetoed for non-zero-support reasons (scope mismatch / invalid polygon) -> fail closed.
        if FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT not in base.reason_codes:
            results.append(
                PhysicalRoomRingProvenanceBinding(
                    original_surface_entity_id=surf.surface_entity_id,
                    quantity_id=surf.quantity_id,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    withheld=True,
                    bound_surface_entity_id=None,
                    bound_ring_record_id=None,
                    bound_ring_area_pt2=None,
                    bound_ring_closure_ids=(),
                    wall_support_fraction=0.0,
                    explicit_area_m2=None,
                    explicit_area_authority=None,
                    explicit_area_evidence_ids=(),
                    floor_finish_code=None,
                    floor_finish_evidence_ids=(),
                    rcp_ceiling_material=None,
                    rcp_ceiling_height_mm=None,
                    rcp_ceiling_evidence_ids=(),
                    reason_codes=base.reason_codes,
                )
            )
            continue

        # Case 3: False cell (0% wall support) -> check for unique wall-supported physical ring.
        anchor = cand.room_label_anchor_pdf_pt
        if (
            len(anchor) != 2
            or not (math.isfinite(anchor[0]) and math.isfinite(anchor[1]))
        ):
            results.append(
                PhysicalRoomRingProvenanceBinding(
                    original_surface_entity_id=surf.surface_entity_id,
                    quantity_id=surf.quantity_id,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    withheld=True,
                    bound_surface_entity_id=None,
                    bound_ring_record_id=None,
                    bound_ring_area_pt2=None,
                    bound_ring_closure_ids=(),
                    wall_support_fraction=0.0,
                    explicit_area_m2=None,
                    explicit_area_authority=None,
                    explicit_area_evidence_ids=(),
                    floor_finish_code=None,
                    floor_finish_evidence_ids=(),
                    rcp_ceiling_material=None,
                    rcp_ceiling_height_mm=None,
                    rcp_ceiling_evidence_ids=(),
                    reason_codes=(
                        FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT,
                        INVALID_ROOM_LABEL_ANCHOR,
                    ),
                )
            )
            continue

        matching_rings: list[tuple[Any, float]] = []
        for ring, ring_poly in scoped_rings:
            ring_page = _ring_attr(ring, "page_index", None)
            if ring_page != cand.page_index:
                continue
            if not _point_in_polygon(anchor, ring_poly):
                continue
            # Verify the candidate ring itself passes the exact same wall_support_predicate!
            ring_surface = FloorSurfaceWallSupportInput(
                surface_entity_id=str(_ring_attr(ring, "record_id", "")),
                quantity_id=surf.quantity_id,
                document_id=surf.document_id,
                revision_id=surf.revision_id,
                source_sha256=surf.source_sha256,
                page_id=surf.page_id,
                viewport_id=surf.viewport_id,
                polygon_pdf_pts=ring_poly,
            )
            ring_verdict = evaluate_floor_surface_zero_wall_support_veto(
                surfaces=(ring_surface,),
                drawings=drawings,
                wall_support_predicate=wall_support_predicate,
                expected_document_id=expected_document_id,
                expected_revision_id=expected_revision_id,
                expected_source_sha256=expected_source_sha256,
                closures=closures,
            )[0]
            if not ring_verdict.vetoed:
                matching_rings.append((ring, ring_verdict.supported_fraction))

        if not matching_rings:
            # Open-plan / unenclosed zone (e.g., Food Prep): keep strictly withheld.
            results.append(
                PhysicalRoomRingProvenanceBinding(
                    original_surface_entity_id=surf.surface_entity_id,
                    quantity_id=surf.quantity_id,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    withheld=True,
                    bound_surface_entity_id=None,
                    bound_ring_record_id=None,
                    bound_ring_area_pt2=None,
                    bound_ring_closure_ids=(),
                    wall_support_fraction=0.0,
                    explicit_area_m2=None,
                    explicit_area_authority=None,
                    explicit_area_evidence_ids=(),
                    floor_finish_code=None,
                    floor_finish_evidence_ids=(),
                    rcp_ceiling_material=None,
                    rcp_ceiling_height_mm=None,
                    rcp_ceiling_evidence_ids=(),
                    reason_codes=(
                        FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT,
                        NO_QUALIFYING_PHYSICAL_ROOM_RING_FOR_LABEL,
                    ),
                )
            )
            continue

        if len(matching_rings) > 1:
            results.append(
                PhysicalRoomRingProvenanceBinding(
                    original_surface_entity_id=surf.surface_entity_id,
                    quantity_id=surf.quantity_id,
                    status=EvidenceResolutionStatus.CONFLICT,
                    withheld=True,
                    bound_surface_entity_id=None,
                    bound_ring_record_id=None,
                    bound_ring_area_pt2=None,
                    bound_ring_closure_ids=(),
                    wall_support_fraction=0.0,
                    explicit_area_m2=None,
                    explicit_area_authority=None,
                    explicit_area_evidence_ids=(),
                    floor_finish_code=None,
                    floor_finish_evidence_ids=(),
                    rcp_ceiling_material=None,
                    rcp_ceiling_height_mm=None,
                    rcp_ceiling_evidence_ids=(),
                    reason_codes=(
                        FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT,
                        AMBIGUOUS_MULTIPLE_PHYSICAL_ROOM_RINGS_FOR_LABEL,
                    ),
                )
            )
            continue

        ring, ring_support_frac = matching_rings[0]
        ring_id = str(_ring_attr(ring, "record_id", ""))
        ring_area = float(_ring_attr(ring, "area_pt2", 0.0) or 0.0)
        ring_closures = tuple(str(c) for c in (_ring_attr(ring, "bounding_closure_ids", ()) or ()))
        results.append(
            PhysicalRoomRingProvenanceBinding(
                original_surface_entity_id=surf.surface_entity_id,
                quantity_id=surf.quantity_id,
                status=EvidenceResolutionStatus.CORROBORATED,
                withheld=False,
                bound_surface_entity_id=ring_id,
                bound_ring_record_id=ring_id,
                bound_ring_area_pt2=round(ring_area, 4),
                bound_ring_closure_ids=ring_closures,
                wall_support_fraction=ring_support_frac,
                explicit_area_m2=cand.explicit_area_m2,
                explicit_area_authority=cand.explicit_area_authority,
                explicit_area_evidence_ids=cand.explicit_area_evidence_ids,
                floor_finish_code=cand.floor_finish_code,
                floor_finish_evidence_ids=cand.floor_finish_evidence_ids,
                rcp_ceiling_material=cand.rcp_ceiling_material,
                rcp_ceiling_height_mm=cand.rcp_ceiling_height_mm,
                rcp_ceiling_evidence_ids=cand.rcp_ceiling_evidence_ids,
                reason_codes=(PHYSICAL_ROOM_RING_PROVENANCE_REBOUND,),
            )
        )

    return tuple(results)


__all__ = [
    "AMBIGUOUS_MULTIPLE_PHYSICAL_ROOM_RINGS_FOR_LABEL",
    "INVALID_ROOM_LABEL_ANCHOR",
    "NO_QUALIFYING_PHYSICAL_ROOM_RING_FOR_LABEL",
    "ORIGINAL_SURFACE_WALL_SUPPORTED_RETAINED",
    "PHYSICAL_ROOM_RING_PROVENANCE_REBOUND",
    "PhysicalRoomRingProvenanceBinding",
    "RoomProvenanceBindingCandidate",
    "SCHEMA_VERSION",
    "bind_room_provenance_to_physical_rings_shadow",
]
