"""Generic zero-physical-wall-support veto for floor-surface room bindings (MAX #7235431173).

Consumes an injected physical wall-support predicate compatible with Claude's
``pb_finish_face_wall_support_shadow.face_wall_support(polygon_pdf_pts, drawings, closures=())``
without duplicating wall/ring geometry:

- **Safe negative rule (per Claude #7235439333)**:
  Veto a candidate floor surface ONLY when **every** edge has zero physical
  wall support (``supported_length <= 0.0`` / every edge ``unsupported == length``),
  emitting typed abstention ``FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT`` even
  if independent figured dimensions exist.
- **Preserves partial paired-wall support**:
  A surface with positive paired-wall support (e.g., 28% paired-wall support
  alongside white-filled panel walls) is NOT vetoed by this safe negative.
- **Fail-closed on malformed/missing polygons or cross-revision mismatches**.

Default-off / report-only contract (``shadow_only=True``,
``commercial_authority_granted=False``).
"""
from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import math
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus


SCHEMA_VERSION = "1.0.0"

FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT = "floor_surface_zero_physical_wall_support"
FLOOR_SURFACE_POLYGON_UNAVAILABLE = "floor_surface_polygon_unavailable"
FLOOR_SURFACE_POSITIVE_WALL_SUPPORT = "floor_surface_positive_wall_support"


@dataclass(frozen=True)
class FloorSurfaceWallSupportInput:
    """One candidate floor surface with its unrotated PDF polygon."""

    surface_entity_id: str
    quantity_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    polygon_pdf_pts: tuple[tuple[float, float], ...]


@dataclass(frozen=True)
class FloorSurfaceWallSupportVerdict:
    """Typed veto/retain verdict for one floor surface."""

    surface_entity_id: str
    quantity_id: str
    status: EvidenceResolutionStatus
    vetoed: bool
    supported_edge_count: int
    total_edge_count: int
    supported_length_pt: float
    total_length_pt: float
    supported_fraction: float
    reason_codes: tuple[str, ...]
    shadow_only: bool = True
    commercial_authority_granted: bool = False
    schema_version: str = SCHEMA_VERSION


def _extract_edge_support_totals(predicate_result: Any) -> tuple[int, int, float, float]:
    """Extract (supported_edges, total_edges, supported_len, total_len) from predicate output.

    Supports both dataclass/attribute objects and dict-based reports returning
    ``edges`` where each edge carries ``length`` and ``unsupported`` (matching
    ``pb_finish_face_wall_support_shadow.face_wall_support``).
    """
    edges = (
        predicate_result.get("edges")
        if isinstance(predicate_result, Mapping)
        else getattr(predicate_result, "edges", None)
    )
    if edges is None:
        raise ValueError("wall support predicate result missing 'edges'")
    edge_seq = tuple(edges)
    if not edge_seq:
        return 0, 0, 0.0, 0.0

    supported_edges = 0
    supported_len = 0.0
    total_len = 0.0
    for edge in edge_seq:
        length = float(
            edge.get("length", 0.0) if isinstance(edge, Mapping) else getattr(edge, "length", 0.0)
        )
        unsupported = float(
            edge.get("unsupported", length)
            if isinstance(edge, Mapping)
            else getattr(edge, "unsupported", length)
        )
        if not (math.isfinite(length) and math.isfinite(unsupported)) or length < 0.0:
            raise ValueError("non-finite or negative edge length from wall support predicate")
        supported = max(0.0, length - max(0.0, unsupported))
        total_len += length
        supported_len += supported
        if supported > 1e-6:
            supported_edges += 1
    return supported_edges, len(edge_seq), supported_len, total_len


def evaluate_floor_surface_zero_wall_support_veto(
    *,
    surfaces: Sequence[FloorSurfaceWallSupportInput],
    drawings: Sequence[Any],
    wall_support_predicate: Callable[..., Any],
    expected_document_id: str,
    expected_revision_id: str,
    expected_source_sha256: str,
    closures: Sequence[Any] = (),
) -> tuple[FloorSurfaceWallSupportVerdict, ...]:
    """Veto any floor surface whose polygon has 0% physical wall edge support.

    Never duplicates wall/ring geometry: delegates strictly to
    ``wall_support_predicate(polygon_pdf_pts, drawings, closures=closures)``.
    """
    verdicts: list[FloorSurfaceWallSupportVerdict] = []
    for surf in surfaces:
        if (
            surf.document_id != expected_document_id
            or surf.revision_id != expected_revision_id
            or surf.source_sha256 != expected_source_sha256
        ):
            verdicts.append(
                FloorSurfaceWallSupportVerdict(
                    surface_entity_id=surf.surface_entity_id,
                    quantity_id=surf.quantity_id,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    vetoed=True,
                    supported_edge_count=0,
                    total_edge_count=0,
                    supported_length_pt=0.0,
                    total_length_pt=0.0,
                    supported_fraction=0.0,
                    reason_codes=("floor_surface_provenance_scope_mismatch",),
                )
            )
            continue

        poly = tuple(surf.polygon_pdf_pts or ())
        if len(poly) < 3 or any(
            len(pt) != 2 or not (math.isfinite(pt[0]) and math.isfinite(pt[1]))
            for pt in poly
        ):
            verdicts.append(
                FloorSurfaceWallSupportVerdict(
                    surface_entity_id=surf.surface_entity_id,
                    quantity_id=surf.quantity_id,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    vetoed=True,
                    supported_edge_count=0,
                    total_edge_count=0,
                    supported_length_pt=0.0,
                    total_length_pt=0.0,
                    supported_fraction=0.0,
                    reason_codes=(FLOOR_SURFACE_POLYGON_UNAVAILABLE,),
                )
            )
            continue

        pred_result = wall_support_predicate(poly, drawings, closures=closures)
        supp_edges, total_edges, supp_len, total_len = _extract_edge_support_totals(pred_result)
        frac = (supp_len / total_len) if total_len > 1e-9 else 0.0

        # Safe negative rule: veto ONLY when every edge has zero wall support.
        if total_edges == 0 or total_len <= 1e-9 or supp_len <= 1e-6:
            verdicts.append(
                FloorSurfaceWallSupportVerdict(
                    surface_entity_id=surf.surface_entity_id,
                    quantity_id=surf.quantity_id,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    vetoed=True,
                    supported_edge_count=0,
                    total_edge_count=total_edges,
                    supported_length_pt=0.0,
                    total_length_pt=round(total_len, 4),
                    supported_fraction=0.0,
                    reason_codes=(FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT,),
                )
            )
        else:
            verdicts.append(
                FloorSurfaceWallSupportVerdict(
                    surface_entity_id=surf.surface_entity_id,
                    quantity_id=surf.quantity_id,
                    status=EvidenceResolutionStatus.CORROBORATED,
                    vetoed=False,
                    supported_edge_count=supp_edges,
                    total_edge_count=total_edges,
                    supported_length_pt=round(supp_len, 4),
                    total_length_pt=round(total_len, 4),
                    supported_fraction=round(frac, 4),
                    reason_codes=(FLOOR_SURFACE_POSITIVE_WALL_SUPPORT,),
                )
            )
    return tuple(verdicts)


__all__ = [
    "FLOOR_SURFACE_POLYGON_UNAVAILABLE",
    "FLOOR_SURFACE_POSITIVE_WALL_SUPPORT",
    "FLOOR_SURFACE_ZERO_PHYSICAL_WALL_SUPPORT",
    "FloorSurfaceWallSupportInput",
    "FloorSurfaceWallSupportVerdict",
    "SCHEMA_VERSION",
    "evaluate_floor_surface_zero_wall_support_veto",
]
