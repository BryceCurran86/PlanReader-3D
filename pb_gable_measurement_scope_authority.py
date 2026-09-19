"""pb_gable_measurement_scope_authority.py — Measurement-scope authority for
the commercial term "gable walling" (KSTVET BOQ-C36-B and generically any
"ditto gable walling"-style residual wall item).

This module answers a DIFFERENT question than ``pb_gable_polygon_geometry``.
That module proves the physical roofline (ridge/eaves/slopes) — a pure
geometry proposition. This module proves WHICH region of wall, bounded
below by what datum, the commercial BOQ term actually measures. The two
must never be conflated:

- ``GableRooflineGeometry`` (physical): the roof boundary only. Never
  reasons about BOQ wording, adjacent items, or measurement convention.
- ``GableMeasurementScope`` (commercial): the lower measurement datum,
  upper roofline boundary, and the resulting polygon. Never re-derives or
  adjusts the roofline geometry itself — it only decides where to CUT the
  wall from below, using independent datum evidence.

A resolved scope is only ever produced from real, checkable evidence:

- BOQ wording/context (is this item a residual/"ditto" item relative to a
  named base walling item, or an independent scope?),
- an independently-evidenced lower datum (a ring/bond beam whose own
  cross-section is uniquely determined from source quantities, a drawn
  wall-plate/parapet line distinct from the roofline, an explicit ceiling
  line, or explicit level annotations),
- consistency with the drawing's own depiction (e.g. a continuous,
  undifferentiated masonry hatch from ground to roofline is itself
  evidence AGAINST an intermediate datum, not merely an absence of proof).

If the lower datum cannot be uniquely determined (underdetermined BOQ
quantities, no distinguishing drawn feature, conflicting evidence), the
scope is UNRESOLVED. The bare roofline-above-eaves region is used only
when that specific proposition is itself evidenced (BOQ residual wording
+ no distinguishing intermediate feature drawn) — never as a silent
default when evidence is simply absent.

Nothing here reads or depends on any benchmark/expected quantity.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Tuple

from pb_gable_polygon_geometry import GablePolygon


class GableMeasurementScopeStatus(str, Enum):
    """Real, evidenced propositions only -- never a placeholder state
    invented to make a number reachable."""

    # The residual region above the eaves/wall-plate line where the
    # adjoining walls' own roofline seats -- evidenced by (a) BOQ wording
    # naming this item as a "ditto"/residual relative to a named base
    # walling item, and (b) the drawing showing no distinguishing
    # intermediate feature (band, beam, parapet, ceiling line) between
    # that eaves line and the roofline.
    ABOVE_EAVES = "above_eaves"
    # A wall-plate level independently evidenced as sitting at a DIFFERENT
    # height than the bare roofline intersection (e.g. a raised parapet
    # with the roof set back/down from the wall top).
    ABOVE_WALL_PLATE = "above_wall_plate"
    # A ceiling line independently evidenced (drawn, dimensioned) as the
    # commercial lower boundary, distinct from the eaves.
    ABOVE_CEILING_DATUM = "above_ceiling_datum"
    # An independently, uniquely dimensioned ring/bond beam (from a
    # structural detail or a fully-determined BOQ quantity set -- not an
    # underdetermined volume+formwork pair with an assumed width) proves a
    # datum different from the bare roofline.
    ABOVE_STRUCTURAL_BEAM = "above_structural_beam"
    # A fully custom polygon (stepped or sloping lower boundary) proven
    # directly from source geometry rather than any of the named cases.
    EXPLICIT_POLYGON = "explicit_polygon"
    # Evidence is missing, underdetermined, or conflicting.
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class LowerDatumEvidence:
    """One candidate lower-datum proposition and why it was accepted or
    rejected. Kept even when rejected, for provenance/audit."""

    datum_kind: str  # matches a GableMeasurementScopeStatus value
    accepted: bool
    reason: str
    source_observation_ids: Tuple[str, ...] = field(default_factory=tuple)
    # When accepted with real, independently-measured boundary vertices
    # (e.g. a beam soffit line, a ceiling line, a stepped/sloping datum
    # line) -- left-to-right, matching the roofline's own boundary
    # x-positions. None means "accepted in principle but no boundary
    # geometry supplied yet" (stays incomplete rather than defaulting to
    # eaves).
    lower_boundary_vertices: Optional[Tuple[Tuple[float, float], ...]] = None


@dataclass(frozen=True)
class GableMeasurementScope:
    """A fully authenticated commercial measurement-scope result. Never
    directly constructed by a caller with an invented status -- only via
    ``resolve_gable_measurement_scope``."""

    status: str
    wall_identity: str
    elevation_identity: str
    document_id: str
    revision_id: str
    page_id: str
    lower_boundary_vertices: Optional[Tuple[Tuple[float, float], ...]]
    upper_roofline_vertices: Optional[Tuple[Tuple[float, float], ...]]
    scope_polygon: Optional[GablePolygon]
    datum_evidence: Tuple[LowerDatumEvidence, ...]
    completeness: str
    notes: Tuple[str, ...] = field(default_factory=tuple)


def resolve_gable_measurement_scope(
    *,
    wall_identity: str,
    elevation_identity: str,
    document_id: str,
    revision_id: str,
    page_id: str,
    roofline_polygon: GablePolygon,
    boq_item_is_residual_of: Optional[str],
    boq_item_wording: str,
    distinguishing_intermediate_feature_found: bool,
    candidate_lower_datums: Tuple[LowerDatumEvidence, ...] = (),
) -> GableMeasurementScope:
    """Resolve the commercial measurement scope for one gable-end wall.

    ``roofline_polygon`` is consumed read-only -- this function never
    mutates or re-derives its vertices/ridge/eaves. ``boq_item_is_residual_of``
    should be the base walling item id this gable item is worded as
    "ditto"/residual to, or None if the BOQ item stands alone.
    ``distinguishing_intermediate_feature_found`` must come from an actual
    check of the drawing (a drawn band/beam/parapet/ceiling line between
    the wall's eaves and its roofline) -- True only when one is genuinely
    present.
    """
    evidence: list[LowerDatumEvidence] = list(candidate_lower_datums)

    accepted_non_default = [e for e in evidence if e.accepted and e.datum_kind != GableMeasurementScopeStatus.ABOVE_EAVES.value]
    conflicting_accepted = {e.datum_kind for e in evidence if e.accepted}

    if len(conflicting_accepted) > 1:
        return GableMeasurementScope(
            status=GableMeasurementScopeStatus.UNRESOLVED.value,
            wall_identity=wall_identity,
            elevation_identity=elevation_identity,
            document_id=document_id,
            revision_id=revision_id,
            page_id=page_id,
            lower_boundary_vertices=None,
            upper_roofline_vertices=roofline_polygon.vertices,
            scope_polygon=None,
            datum_evidence=tuple(evidence),
            completeness="incomplete",
            notes=("multiple conflicting accepted lower-datum candidates",),
        )

    if accepted_non_default:
        winner = accepted_non_default[0]
        if winner.lower_boundary_vertices is None:
            return GableMeasurementScope(
                status=winner.datum_kind,
                wall_identity=wall_identity,
                elevation_identity=elevation_identity,
                document_id=document_id,
                revision_id=revision_id,
                page_id=page_id,
                lower_boundary_vertices=None,
                upper_roofline_vertices=roofline_polygon.vertices,
                scope_polygon=None,
                datum_evidence=tuple(evidence),
                completeness="incomplete",
                notes=(
                    f"datum {winner.datum_kind!r} accepted in principle but no lower "
                    "boundary geometry was supplied -- a polygon cannot be resolved "
                    "from a named datum alone",
                ),
            )
        # Build the real scope polygon: the roofline's own vertices
        # (unmodified) closed by the independently-measured lower boundary,
        # reversed so the polygon winds consistently.
        scope_vertices = tuple(roofline_polygon.vertices) + tuple(reversed(winner.lower_boundary_vertices))
        scope_polygon = GablePolygon(
            vertices=scope_vertices,
            source_segment_ids=roofline_polygon.source_segment_ids,
            status="resolved",
        )
        return GableMeasurementScope(
            status=winner.datum_kind,
            wall_identity=wall_identity,
            elevation_identity=elevation_identity,
            document_id=document_id,
            revision_id=revision_id,
            page_id=page_id,
            lower_boundary_vertices=winner.lower_boundary_vertices,
            upper_roofline_vertices=roofline_polygon.vertices,
            scope_polygon=scope_polygon,
            datum_evidence=tuple(evidence),
            completeness="complete",
            notes=(),
        )

    # No non-default datum was proven. ABOVE_EAVES is only itself a
    # resolved proposition -- not a silent fallback -- when BOTH:
    # (a) the BOQ item is worded as a residual/"ditto" of a named base
    #     walling item (proving it measures a REMAINDER, not a
    #     stand-alone region), and
    # (b) the drawing shows no distinguishing intermediate feature between
    #     the wall's eaves and its roofline (a continuous, undifferentiated
    #     surface is itself evidence against an intermediate datum).
    if boq_item_is_residual_of and not distinguishing_intermediate_feature_found:
        return GableMeasurementScope(
            status=GableMeasurementScopeStatus.ABOVE_EAVES.value,
            wall_identity=wall_identity,
            elevation_identity=elevation_identity,
            document_id=document_id,
            revision_id=revision_id,
            page_id=page_id,
            lower_boundary_vertices=(roofline_polygon.vertices[0], roofline_polygon.vertices[-1]),
            upper_roofline_vertices=roofline_polygon.vertices,
            scope_polygon=roofline_polygon,
            datum_evidence=tuple(evidence) + (
                LowerDatumEvidence(
                    datum_kind=GableMeasurementScopeStatus.ABOVE_EAVES.value,
                    accepted=True,
                    reason=(
                        f"BOQ item worded as residual of {boq_item_is_residual_of!r} "
                        f"({boq_item_wording!r}); no distinguishing intermediate "
                        "feature found between eaves and roofline"
                    ),
                ),
            ),
            completeness="complete",
            notes=(),
        )

    return GableMeasurementScope(
        status=GableMeasurementScopeStatus.UNRESOLVED.value,
        wall_identity=wall_identity,
        elevation_identity=elevation_identity,
        document_id=document_id,
        revision_id=revision_id,
        page_id=page_id,
        lower_boundary_vertices=None,
        upper_roofline_vertices=roofline_polygon.vertices,
        scope_polygon=None,
        datum_evidence=tuple(evidence),
        completeness="incomplete",
        notes=("no accepted lower-datum proposition and residual/BOQ-context proof insufficient",),
    )
