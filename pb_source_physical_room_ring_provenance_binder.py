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

from collections.abc import Callable, Mapping, Sequence
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
RING_STATUS_NOT_CANDIDATE = "ring_status_not_candidate"
RING_INSUFFICIENT_POSITIVE_WALL_SUPPORT = "ring_insufficient_positive_wall_support"
RING_CONTAINS_MULTIPLE_DISTINCT_ROOM_LABELS = "ring_contains_multiple_distinct_room_labels"
OPEN_PLAN_FINISH_ZONE_WITNESS_ONLY_NO_PHYSICAL_RING = (
    "open_plan_finish_zone_witness_only_no_physical_ring"
)
AMBIGUOUS_MULTIPLE_PHYSICAL_ROOM_RINGS_FOR_LABEL = (
    "ambiguous_multiple_physical_room_rings_for_label"
)
INVALID_ROOM_LABEL_ANCHOR = "invalid_room_label_anchor"
DEFAULT_MIN_RING_WALL_SUPPORT_FRACTION = 0.50


@dataclass(frozen=True)
class SourceProvenFinishZoneWitness:
    """Source-proven open-plan finish zone witness (never invents walls or room rings)."""

    witness_id: str
    surface_entity_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    finish_code: str
    evidence_ids: tuple[str, ...]
    invented_wall_count: int = 0
    shadow_only: bool = True
    commercial_authority_granted: bool = False


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
    bound_finish_zone_witness_id: str | None = None
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


def _ring_status_is_admissible(ring: Any) -> bool:
    """Require explicit CANDIDATE (or CORROBORATED) status; reject ABSTAINED/CONFLICT/missing."""
    raw = _ring_attr(ring, "status", None)
    if raw in (EvidenceResolutionStatus.CANDIDATE, EvidenceResolutionStatus.CORROBORATED):
        return True
    if isinstance(raw, str) and raw.strip().lower() in ("candidate", "corroborated"):
        return True
    return False


def _closures_for_ring(ring: Any, all_closures: Sequence[Any]) -> tuple[Any, ...]:
    """Scope closures passed to wall_support_predicate strictly to the ring's own closure IDs."""
    if not all_closures:
        return ()
    ring_cids = frozenset(
        str(c) for c in (_ring_attr(ring, "bounding_closure_ids", ()) or ()) if str(c)
    )
    if not ring_cids:
        return ()
    matched: list[Any] = []
    any_has_id = False
    for cl in all_closures:
        cid = _ring_attr(cl, "closure_id", None) or _ring_attr(cl, "record_id", None)
        if cid is not None:
            any_has_id = True
            if str(cid) in ring_cids:
                matched.append(cl)
    return tuple(matched) if any_has_id else tuple(all_closures)


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
    page_room_label_anchors: Sequence[tuple[int, str, tuple[float, float]]] = (),
    min_ring_wall_support_fraction: float = DEFAULT_MIN_RING_WALL_SUPPORT_FRACTION,
    finish_zone_witnesses_by_surface_id: Mapping[str, SourceProvenFinishZoneWitness] | None = None,
) -> tuple[PhysicalRoomRingProvenanceBinding, ...]:
    """Bind explicit-area, floor-finish, and RCP provenance to wall-supported physical rings.

    - Retains candidate surfaces that already pass ``evaluate_floor_surface_zero_wall_support_veto``.
    - For false cells vetoed with ``FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT``,
      attempts unique physical-ring rebinding via room-label anchor containment
      and the exact same ``wall_support_predicate``.
    - Keeps unenclosed zones (0 qualifying rings) strictly withheld.
    """
    if not (
        math.isfinite(min_ring_wall_support_fraction)
        and 0.0 < float(min_ring_wall_support_fraction) <= 1.0
    ):
        raise ValueError("min_ring_wall_support_fraction must be in (0.0, 1.0]")
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
    # Keep status flag so rings containing a room label with non-CANDIDATE status
    # (e.g., ABSTAINED open_wall_gap_unresolved) are explicitly rejected with
    # RING_STATUS_NOT_CANDIDATE rather than silently bound.
    scoped_rings: list[tuple[Any, tuple[tuple[float, float], ...], bool]] = []
    for ring in physical_rings:
        ring_sha = str(_ring_attr(ring, "source_sha256", "") or "").strip()
        if ring_sha != expected_source_sha256:
            continue
        wall_edges = int(_ring_attr(ring, "wall_edge_count", 0) or 0)
        wall_paths = tuple(_ring_attr(ring, "bounding_wall_path_indices", ()) or ())
        poly = tuple(_ring_attr(ring, "polygon_pdf_pts", ()) or ())
        if wall_edges <= 0 or not wall_paths or len(poly) < 3:
            continue
        scoped_rings.append((ring, poly, _ring_status_is_admissible(ring)))

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
        multi_label_shell_rejected = False
        non_candidate_status_rejected = False
        insufficient_positive_support_rejected = False
        # Build all OTHER room-label anchors on the same page so a giant multi-room
        # open-plan shell ring enclosing >=2 distinct room labels cannot be mistaken
        # for a single room's physical boundary.
        other_anchors: list[tuple[float, float]] = [
            other.room_label_anchor_pdf_pt
            for other in candidates
            if other.page_index == cand.page_index
            and other.surface.surface_entity_id != surf.surface_entity_id
            and len(other.room_label_anchor_pdf_pt) == 2
        ]
        for lbl_page, _lbl_id, lbl_pt in page_room_label_anchors:
            if lbl_page != cand.page_index or len(lbl_pt) != 2:
                continue
            if math.hypot(lbl_pt[0] - anchor[0], lbl_pt[1] - anchor[1]) <= 1.0:
                continue
            other_anchors.append(lbl_pt)

        for ring, ring_poly, ring_status_ok in scoped_rings:
            ring_page = _ring_attr(ring, "page_index", None)
            if ring_page != cand.page_index:
                continue
            if not _point_in_polygon(anchor, ring_poly):
                continue
            if not ring_status_ok:
                non_candidate_status_rejected = True
                continue
            if any(_point_in_polygon(other_pt, ring_poly) for other_pt in other_anchors):
                multi_label_shell_rejected = True
                continue
            # Verify the candidate ring itself passes the exact same wall_support_predicate
            # using strictly that ring's own doorway closures.
            ring_closures_for_check = _closures_for_ring(ring, closures)
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
                closures=ring_closures_for_check,
            )[0]
            if not ring_verdict.vetoed:
                if ring_verdict.supported_fraction + 1e-9 >= float(min_ring_wall_support_fraction):
                    matching_rings.append((ring, ring_verdict.supported_fraction))
                else:
                    insufficient_positive_support_rejected = True

        if not matching_rings:
            # Open-plan / unenclosed zone (e.g., Food Prep): keep strictly withheld
            # from physical room publication. If a source-proven finish-zone witness
            # exists for the exact same scope, record it strictly as witness-only
            # (withheld=True, zero invented walls).
            extra_reasons: list[str] = [FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT]
            if non_candidate_status_rejected:
                extra_reasons.append(RING_STATUS_NOT_CANDIDATE)
            if multi_label_shell_rejected:
                extra_reasons.append(RING_CONTAINS_MULTIPLE_DISTINCT_ROOM_LABELS)
            if insufficient_positive_support_rejected:
                extra_reasons.append(RING_INSUFFICIENT_POSITIVE_WALL_SUPPORT)
            if len(extra_reasons) == 1:
                extra_reasons.append(NO_QUALIFYING_PHYSICAL_ROOM_RING_FOR_LABEL)

            fz_witness = (
                finish_zone_witnesses_by_surface_id.get(surf.surface_entity_id)
                if finish_zone_witnesses_by_surface_id
                else None
            )
            fz_valid = (
                isinstance(fz_witness, SourceProvenFinishZoneWitness)
                and fz_witness.surface_entity_id == surf.surface_entity_id
                and fz_witness.document_id == expected_document_id
                and fz_witness.revision_id == expected_revision_id
                and fz_witness.source_sha256 == expected_source_sha256
                and fz_witness.invented_wall_count == 0
                and bool(fz_witness.finish_code.strip())
                and bool(fz_witness.evidence_ids)
            )
            if fz_valid and fz_witness is not None:
                extra_reasons.append(OPEN_PLAN_FINISH_ZONE_WITNESS_ONLY_NO_PHYSICAL_RING)
            abstain_reasons = tuple(extra_reasons)
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
                    floor_finish_code=fz_witness.finish_code if (fz_valid and fz_witness) else None,
                    floor_finish_evidence_ids=(
                        fz_witness.evidence_ids if (fz_valid and fz_witness) else ()
                    ),
                    rcp_ceiling_material=None,
                    rcp_ceiling_height_mm=None,
                    rcp_ceiling_evidence_ids=(),
                    reason_codes=abstain_reasons,
                    bound_finish_zone_witness_id=(
                        fz_witness.witness_id if (fz_valid and fz_witness) else None
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
    "DEFAULT_MIN_RING_WALL_SUPPORT_FRACTION",
    "INVALID_ROOM_LABEL_ANCHOR",
    "NO_QUALIFYING_PHYSICAL_ROOM_RING_FOR_LABEL",
    "OPEN_PLAN_FINISH_ZONE_WITNESS_ONLY_NO_PHYSICAL_RING",
    "ORIGINAL_SURFACE_WALL_SUPPORTED_RETAINED",
    "PHYSICAL_ROOM_RING_PROVENANCE_REBOUND",
    "RING_CONTAINS_MULTIPLE_DISTINCT_ROOM_LABELS",
    "RING_INSUFFICIENT_POSITIVE_WALL_SUPPORT",
    "RING_STATUS_NOT_CANDIDATE",
    "PhysicalRoomRingProvenanceBinding",
    "RoomProvenanceBindingCandidate",
    "SCHEMA_VERSION",
    "SourceProvenFinishZoneWitness",
    "bind_room_provenance_to_physical_rings_shadow",
]
