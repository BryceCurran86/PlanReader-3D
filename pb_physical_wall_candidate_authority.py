"""Producer-owned source-backed physical-wall candidate authority.

This module proves one narrow proposition only: the physical wall candidates
produced by the existing W2/W3/W4 wall pipeline for a complete exact
producer-owned visible PDF page scope.

Physical equivalence is also producer-owned here. The generic wall-identity
classifier stays fail-closed for independent provenance; this producer may
strengthen otherwise-AMBIGUOUS pair relations only when the already-reviewed
G17 source authority independently re-proves a jamb-bounded two-face opening
from the exact same immutable visible source snapshot and the six proven source
primitives map bijectively back to six W4 wall candidates. No caller-supplied
wall list, equivalence flag, completeness flag, confidence, nearest/first rule,
or geometry body can enter that proof path.

It does NOT prove opening host binding, wall role, wall height, wall thickness,
opening deductions, net wall area, FIRM/commercial publication or JobHub data.
Ordinary callers can address a scope only by lineage; they cannot supply walls,
segments, graphs, candidate lists/counts or completeness flags.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_physical_wall_identity import (
    PhysicalEquivalenceClass,
    PhysicalWallEquivalenceResolution,
    PhysicalWallIdentity,
    collect_physical_wall_identities,
    resolve_physical_wall_equivalence,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    NATIVE_PDF_VISIBLE_SEGMENT,
    RASTER_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
    classify_native_segment_visibility,
)
from pb_vector_geometry_v130 import extract_native_page
from pb_viewport_segmentation import (
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    is_segment_page_viewports_product,
    segmented_viewport_producer_fingerprint,
    segment_page_viewports,
    validate_non_overlapping_viewports,
)
from pb_wall_room_topology_contracts import JunctionType, WallCandidate
from pb_wall_room_topology_junction_classifier import classify_junctions
from pb_wall_room_topology_stage_a import (
    build_wall_graph_for_viewport,
    is_structural_candidate_segment,
)
from pb_wall_room_topology_wall_assembly import assemble_wall_topology


PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION = "1.2.0"
PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED = "physical_wall_candidate_scope_resolved"
PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE = "physical_wall_candidate_scope_unavailable"
PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE = (
    "physical_wall_candidate_source_integrity_failure"
)
PHYSICAL_WALL_CANDIDATE_IDENTITY_UNRESOLVED = (
    "physical_wall_candidate_identity_unresolved"
)
PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY = (
    "physical_wall_candidate_scope_cropped_at_page_boundary"
)
PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY = (
    "physical_wall_candidate_scope_cropped_at_viewport_boundary"
)
PHYSICAL_WALL_CANDIDATE_SCOPE_BOUNDS_UNRESOLVED = (
    "physical_wall_candidate_scope_bounds_unresolved"
)
PHYSICAL_WALL_CANDIDATE_VIEWPORT_AUTHORITY_INVALID = (
    "physical_wall_candidate_viewport_authority_invalid"
)
PHYSICAL_WALL_CANDIDATE_VIEWPORT_LINEAGE_MISMATCH = (
    "physical_wall_candidate_viewport_lineage_mismatch"
)
PHYSICAL_WALL_CANDIDATE_SOURCE_PRIMITIVE_OWNERSHIP_AMBIGUOUS = (
    "physical_wall_candidate_source_primitive_ownership_ambiguous"
)

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_VIEWPORT_SELECTOR_SEAL = object()
_COORD_TOL = 1e-6
_PARALLEL_REL_TOL = 1e-9
Point = tuple[float, float]
Line = tuple[float, float, float, float]

# Exact-coincidence tolerance for "this coordinate is the same point as that
# boundary coordinate". This is the same tolerance this module already uses
# everywhere else for point/line exactness (_line, _canonical_direction,
# _trusted_face_break, _same_gap, _segment_matches, etc.) -- not a new
# constant invented for boundary checking. A native PDF coordinate that was
# actually drawn at a page or viewport edge decodes back to that exact
# value (verified: a segment endpoint drawn at x=0.0 on an unrotated,
# unscaled page reads back as exactly 0.0), so no larger, hand-picked
# proximity tolerance is needed or used.
_BOUNDARY_COORD_TOL = _COORD_TOL


@dataclass(frozen=True)
class PhysicalWallCandidateSelector:
    """Consumer address.

    Legacy page-scope selectors remain public for compatibility. Viewport
    selectors are producer-sealed and can only be obtained from an authority
    that already materialized the authenticated viewport scope.
    """

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    _viewport_selector_fingerprint: str = ""
    _viewport_selector_seal: object = None


@dataclass(frozen=True)
class PhysicalWallCandidateRecord:
    wall_candidate_id: str
    wall_candidate: WallCandidate
    physical_identity: PhysicalWallIdentity
    schema_version: str = PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION


@dataclass(frozen=True)
class PhysicalWallCandidateScopeResult:
    status: EvidenceResolutionStatus
    scope_complete: bool
    records: tuple[PhysicalWallCandidateRecord, ...]
    source_observation_ids: tuple[str, ...]
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    reason_codes: tuple[str, ...]
    equivalence: Optional[PhysicalWallEquivalenceResolution] = None
    proposition: Optional[str] = None
    scope_kind: str = "page"
    viewport_id: Optional[str] = None
    viewport_bbox: Optional[tuple[float, float, float, float]] = None
    viewport_view_type: Optional[str] = None
    viewport_status: Optional[str] = None
    viewport_boundary_source: Optional[str] = None
    viewport_producer_fingerprint: Optional[str] = None
    viewport_sibling_set_fingerprint: Optional[str] = None
    scope_boundary_observation_ids: tuple[str, ...] = ()
    ambiguous_source_observation_ids: tuple[str, ...] = ()
    schema_version: str = PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION


@dataclass(frozen=True)
class _ScopeKey:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str


@dataclass(frozen=True)
class _TrustedFaceBreak:
    first_raw_id: str
    second_raw_id: str
    gap_start: float
    gap_end: float
    start_point: Point
    end_point: Point
    direction: Point


def _decision_scope_id(page_id: str) -> str:
    return f"wall-source:page-{str(page_id)}"


def _viewport_selector_payload_fingerprint(
    *,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    page_id: str,
    decision_scope_id: str,
) -> str:
    payload = "|".join(
        (
            PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION,
            str(document_id),
            str(revision_id),
            str(source_sha256),
            str(snapshot_id),
            str(page_id),
            str(decision_scope_id),
        )
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _viewport_sibling_set_fingerprint(viewports: Sequence[object]) -> str:
    rows = []
    for viewport in sorted(viewports, key=lambda item: str(getattr(item, "view_id", ""))):
        rows.append(
            f"{getattr(viewport, 'view_id', '')}:"
            f"{segmented_viewport_producer_fingerprint(viewport)}"
        )
    return hashlib.sha256("|".join(rows).encode("utf-8")).hexdigest()


def _viewport_decision_scope_id(
    *,
    published,
    page_id: str,
    viewport,
    sibling_set_fingerprint: str,
) -> str:
    payload = "|".join(
        (
            PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION,
            str(published.revision.document_id),
            str(published.revision.revision_id),
            str(published.revision.source_sha256),
            str(published.snapshot.snapshot_id),
            str(page_id),
            str(viewport.view_id),
            segmented_viewport_producer_fingerprint(viewport),
            str(sibling_set_fingerprint),
        )
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]
    return f"wall-source:viewport:{page_id}:{viewport.view_id}:{digest}"


def _authenticated_viewports(page: fitz.Page, *, page_number: int) -> Optional[tuple[tuple, tuple]]:
    all_viewports = _all_viewports(page, page_number=page_number)
    if all_viewports is None:
        return None
    rows = tuple(all_viewports)
    if any(not is_segment_page_viewports_product(viewport) for viewport in rows):
        return None
    # Preserve F.07's authority distinction exactly:
    # - RESOLVED vector-frame ownership remains independently authoritative;
    # - DERIVED ownership is authoritative only when the complete usable
    #   sibling set is non-overlapping, matching the migration adapter gate.
    sibling_non_overlapping = validate_non_overlapping_viewports(rows)
    eligible = tuple(
        viewport
        for viewport in rows
        if viewport.bounding_box is not None
        and (
            viewport.status == ViewportSegmentationStatus.RESOLVED.value
            or (
                sibling_non_overlapping
                and is_authoritative_derived_viewport(viewport)
            )
        )
    )
    return rows, eligible


def _segment_geometry(segment: Mapping[str, object]) -> Line:
    return (
        float(segment["x1"]),
        float(segment["y1"]),
        float(segment["x2"]),
        float(segment["y2"]),
    )


def _segment_fully_inside_bbox(segment: Mapping[str, object], bbox: Sequence[float]) -> bool:
    x1, y1, x2, y2 = _segment_geometry(segment)
    return _inside_rect((x1, y1), x0=float(bbox[0]), y0=float(bbox[1]), x1=float(bbox[2]), y1=float(bbox[3])) and _inside_rect(
        (x2, y2), x0=float(bbox[0]), y0=float(bbox[1]), x1=float(bbox[2]), y1=float(bbox[3])
    )


def _segment_intersects_bbox(segment: Mapping[str, object], bbox: Sequence[float]) -> bool:
    x1, y1, x2, y2 = _segment_geometry(segment)
    xmin, ymin, xmax, ymax = (float(value) for value in bbox)
    if _inside_rect((x1, y1), x0=xmin, y0=ymin, x1=xmax, y1=ymax) or _inside_rect(
        (x2, y2), x0=xmin, y0=ymin, x1=xmax, y1=ymax
    ):
        return True
    dx, dy = x2 - x1, y2 - y1
    lower, upper = 0.0, 1.0
    for p, q in (
        (-dx, x1 - xmin),
        (dx, xmax - x1),
        (-dy, y1 - ymin),
        (dy, ymax - y1),
    ):
        if p == 0.0:
            if q < 0.0:
                return False
            continue
        ratio = q / p
        if p < 0.0:
            if ratio > upper:
                return False
            lower = max(lower, ratio)
        else:
            if ratio < lower:
                return False
            upper = min(upper, ratio)
    return lower <= upper


def _segment_lies_on_bbox_edge(segment: Mapping[str, object], bbox: Sequence[float]) -> bool:
    x1, y1, x2, y2 = _segment_geometry(segment)
    xmin, ymin, xmax, ymax = (float(value) for value in bbox)
    return (
        (abs(x1 - xmin) <= _BOUNDARY_COORD_TOL and abs(x2 - xmin) <= _BOUNDARY_COORD_TOL)
        or (abs(x1 - xmax) <= _BOUNDARY_COORD_TOL and abs(x2 - xmax) <= _BOUNDARY_COORD_TOL)
        or (abs(y1 - ymin) <= _BOUNDARY_COORD_TOL and abs(y2 - ymin) <= _BOUNDARY_COORD_TOL)
        or (abs(y1 - ymax) <= _BOUNDARY_COORD_TOL and abs(y2 - ymax) <= _BOUNDARY_COORD_TOL)
    )


def _segment_is_authenticated_vector_frame_edge(
    segment: Mapping[str, object],
    *,
    viewport,
) -> bool:
    """Recognize only a whole edge of F.07's authenticated vector frame.

    This is not a semantic wall exclusion. It is the exact producer-owned
    boundary primitive already used to establish the RESOLVED viewport. A
    partial line merely lying on that boundary remains ambiguous.
    """
    if (
        viewport.bounding_box is None
        or viewport.status != ViewportSegmentationStatus.RESOLVED.value
        or str(viewport.boundary_source) != "vector_frame"
    ):
        return False
    x1, y1, x2, y2 = _segment_geometry(segment)
    xmin, ymin, xmax, ymax = (float(value) for value in viewport.bounding_box)

    def same_point(left: Point, right: Point) -> bool:
        return (
            abs(left[0] - right[0]) <= _BOUNDARY_COORD_TOL
            and abs(left[1] - right[1]) <= _BOUNDARY_COORD_TOL
        )

    segment_ends = ((x1, y1), (x2, y2))
    frame_edges = (
        ((xmin, ymin), (xmax, ymin)),
        ((xmax, ymin), (xmax, ymax)),
        ((xmax, ymax), (xmin, ymax)),
        ((xmin, ymax), (xmin, ymin)),
    )
    return any(
        (
            same_point(segment_ends[0], edge[0])
            and same_point(segment_ends[1], edge[1])
        )
        or (
            same_point(segment_ends[0], edge[1])
            and same_point(segment_ends[1], edge[0])
        )
        for edge in frame_edges
    )


def _blocked(selector: PhysicalWallCandidateSelector, reason: str) -> PhysicalWallCandidateScopeResult:
    return PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        scope_complete=False,
        records=(),
        source_observation_ids=(),
        document_id=str(selector.document_id),
        revision_id=str(selector.revision_id),
        source_sha256=str(selector.source_sha256),
        snapshot_id=str(selector.snapshot_id),
        page_id=str(selector.page_id),
        decision_scope_id=str(selector.decision_scope_id),
        reason_codes=(reason,),
    )


def _source_page_segments(
    *,
    source_producer: SourceVisibilityProducer,
    published,
    source_bytes: bytes,
    page_id: str,
    decision_scope_id: str,
) -> tuple[list[dict], tuple[str, ...], float, float]:
    """Rebuild W2 inputs from exact bytes and exact receipted visible membership.

    Also returns the page's own (width, height) in points, so callers can
    determine whether a wall's dangling end actually terminates inside the
    drawing (a real wall end) or merely at the page edge (the wall's true
    continuation is unknown -- it may simply be cropped by this sheet).
    """

    visibility = source_producer.authority()
    native_visible_by_raw_id: dict[str, tuple[str, tuple[float, ...]]] = {}
    raster_visible: list[tuple[str, str, tuple[float, ...]]] = []
    page_visible_ids: list[str] = []

    for observation_id in published.visible_observation_ids:
        result = visibility.resolve_visible(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        observation = result.observation
        if (
            result.status is not EvidenceResolutionStatus.CORROBORATED
            or observation is None
        ):
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        if observation.page_id != page_id:
            continue

        geometry = tuple(float(value) for value in observation.geometry)
        if len(geometry) != 4:
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)

        if observation.observation_kind == NATIVE_PDF_VISIBLE_SEGMENT:
            prefix = "visible:segment:"
            if not observation.source_primitive_ref.startswith(prefix):
                raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
            raw_id = observation.source_primitive_ref[len(prefix) :]
            if not raw_id or raw_id in native_visible_by_raw_id:
                raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
            native_visible_by_raw_id[raw_id] = (observation_id, geometry)
        elif observation.observation_kind == RASTER_PDF_VISIBLE_SEGMENT:
            prefix = "visible:raster_segment:"
            if not observation.source_primitive_ref.startswith(prefix):
                raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
            raster_ref = observation.source_primitive_ref[len("visible:") :]
            if not raster_ref:
                raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
            raster_visible.append((observation_id, raster_ref, geometry))
        else:
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)

        page_visible_ids.append(observation_id)

    try:
        page_number = int(page_id)
    except (TypeError, ValueError) as exc:
        raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE) from exc
    if page_number < 1:
        raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)

    pdf = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        if page_number > int(pdf.page_count):
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        native = extract_native_page(pdf.load_page(page_number - 1))
    finally:
        pdf.close()

    segments: list[dict] = []
    native_visible_ids: set[str] = set()
    for source_segment in native.get("segments") or ():
        decision = classify_native_segment_visibility(source_segment)
        if not decision.visible:
            continue
        raw_id = str(source_segment.get("id") or "").strip()
        if not raw_id:
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        expected = native_visible_by_raw_id.get(raw_id)
        if expected is None:
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        observation_id, observation_geometry = expected
        geometry = (
            float(source_segment["x1"]),
            float(source_segment["y1"]),
            float(source_segment["x2"]),
            float(source_segment["y2"]),
        )
        if tuple(geometry) != tuple(observation_geometry):
            raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
        native_visible_ids.add(observation_id)
        segment = dict(source_segment)
        segment["document_id"] = published.revision.document_id
        segment["page_id"] = page_id
        segment["viewport_id"] = decision_scope_id
        segment["source_observation_id"] = observation_id
        segments.append(segment)

    if native_visible_ids != {
        observation_id
        for observation_id, _geometry in native_visible_by_raw_id.values()
    }:
        raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)

    # Raster-visible observations have already passed the producer-owned
    # visibility authority, including page-render provenance, image hash, DPI,
    # pixel geometry and parent-lineage checks.  Feed their exact page-point
    # geometry into the same W2-W5 topology pipeline as native segments while
    # leaving graphic attributes explicitly unknown.  No caller-supplied
    # pixels, segments, transforms or wall classifications enter this path.
    for observation_id, raster_ref, geometry in sorted(raster_visible):
        x1, y1, x2, y2 = geometry
        segments.append(
            {
                "id": raster_ref,
                "x1": x1,
                "y1": y1,
                "x2": x2,
                "y2": y2,
                "kind": "line",
                "kind_present": True,
                "width": 0.0,
                "width_present": False,
                "stroke": None,
                "stroke_present": False,
                "fill": None,
                "fill_present": False,
                "layer": "",
                "layer_present": False,
                "dashes": "",
                "dashes_present": False,
                "clip": None,
                "clip_present": False,
                "clip_known": True,
                "document_id": published.revision.document_id,
                "page_id": page_id,
                "viewport_id": decision_scope_id,
                "source_observation_id": observation_id,
                "source_kind": RASTER_PDF_VISIBLE_SEGMENT,
            }
        )

    if native_visible_ids | {item[0] for item in raster_visible} != set(page_visible_ids):
        raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)

    return (
        segments,
        tuple(sorted(page_visible_ids)),
        float(native["width"]),
        float(native["height"]),
    )


def _dangling_ends(wall: WallCandidate) -> list[Point]:
    """Return the coordinates of this wall's ends that are genuinely
    dangling (``JunctionType.ENDPOINT`` -- not connected to any other wall).

    An end that meets another wall (any other junction type) is a real,
    resolved terminus regardless of where it happens to sit; it is never a
    candidate for "cropped" classification.
    """
    if not wall.centerline_pts or len(wall.centerline_pts) < 2:
        return []
    if len(wall.junction_types) != 2:
        return []
    ends = (
        (wall.centerline_pts[0], wall.junction_types[0]),
        (wall.centerline_pts[-1], wall.junction_types[1]),
    )
    return [point for point, junction_type in ends if junction_type == JunctionType.ENDPOINT]


def _on_rect_boundary(
    point: Point, *, x0: float, y0: float, x1: float, y1: float, tol: float = _BOUNDARY_COORD_TOL
) -> bool:
    x, y = point
    return (
        abs(x - x0) <= tol
        or abs(x - x1) <= tol
        or abs(y - y0) <= tol
        or abs(y - y1) <= tol
    )


def _inside_rect(
    point: Point, *, x0: float, y0: float, x1: float, y1: float, tol: float = _BOUNDARY_COORD_TOL
) -> bool:
    x, y = point
    return (x0 - tol) <= x <= (x1 + tol) and (y0 - tol) <= y <= (y1 + tol)


def _resolved_viewports(page: fitz.Page, *, page_number: int) -> Optional[list]:
    """Return this page's RESOLVED-status segmented viewports, or ``None``
    if segmentation itself could not be run at all (a hard failure, not
    "no viewport structure exists").

    Only ``RESOLVED`` viewports (a real drawn vector frame) are treated as
    an authenticated boundary. ``DERIVED`` viewports are page-space
    partitions inferred from title placement alone with no real drawn
    boundary primitive -- exactly the case already established elsewhere in
    this codebase as insufficient proof of a physical boundary -- and
    ``AMBIGUOUS``/``UNSUPPORTED`` viewports carry no usable geometry at all.
    """
    all_viewports = _all_viewports(page, page_number=page_number)
    if all_viewports is None:
        return None
    return [v for v in all_viewports if v.status == ViewportSegmentationStatus.RESOLVED.value and v.bounding_box]


def _all_viewports(page: fitz.Page, *, page_number: int) -> Optional[list]:
    """Return every segmented viewport regardless of status, or ``None`` if
    segmentation itself raised. An empty list here means genuinely no
    sub-viewport structure was attempted (no title anchors at all) -- a
    non-empty list with no RESOLVED entries means structure was attempted
    but could not be authenticated, which is a different, stricter state.
    """
    try:
        return segment_page_viewports(page, page_number=page_number)
    except Exception:
        return None


def _scope_boundary_reason(
    wall: WallCandidate,
    *,
    page: fitz.Page,
    page_number: int,
    page_width: float,
    page_height: float,
) -> Optional[str]:
    """Classify this wall's scope-completeness boundary state.

    Returns ``None`` when every dangling end is a RESOLVED_INTERIOR_TERMINUS
    (either no dangling end exists at all, or every dangling end sits
    strictly inside both the page and any containing RESOLVED viewport).
    Otherwise returns the specific reason code for the first problem found:
    PAGE boundary, VIEWPORT boundary, or unresolved scope bounds.
    """
    dangling = _dangling_ends(wall)
    if not dangling:
        return None

    all_viewports = _all_viewports(page, page_number=page_number)

    for point in dangling:
        if _on_rect_boundary(point, x0=0.0, y0=0.0, x1=page_width, y1=page_height):
            return PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY

        if all_viewports is None:
            # Viewport segmentation itself failed outright: whether this
            # sheet has real sub-viewport structure this end might be
            # cropped against is genuinely unknown.
            return PHYSICAL_WALL_CANDIDATE_SCOPE_BOUNDS_UNRESOLVED

        if not all_viewports:
            # No viewport structure was found on this page at all (no title
            # anchors) -- the drawing genuinely occupies the whole page as
            # one undivided scope, and the page-boundary check above is the
            # only applicable one.
            continue

        resolved_viewports = [
            v for v in all_viewports if v.status == ViewportSegmentationStatus.RESOLVED.value and v.bounding_box
        ]

        containing = [
            vp
            for vp in resolved_viewports
            if _inside_rect(point, x0=vp.bounding_box[0], y0=vp.bounding_box[1], x1=vp.bounding_box[2], y1=vp.bounding_box[3])
        ]
        if not containing:
            # This page has authenticated viewport structure, but this
            # dangling end falls outside every RESOLVED viewport's bounds
            # (e.g. only DERIVED/AMBIGUOUS regions cover it) -- its true
            # scope cannot be authenticated from this page alone.
            return PHYSICAL_WALL_CANDIDATE_SCOPE_BOUNDS_UNRESOLVED
        if any(
            _on_rect_boundary(point, x0=vp.bounding_box[0], y0=vp.bounding_box[1], x1=vp.bounding_box[2], y1=vp.bounding_box[3])
            for vp in containing
        ):
            return PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY

    return None


def _viewport_scope_boundary_reason(
    wall: WallCandidate,
    *,
    bbox: Sequence[float],
    page_width: float,
    page_height: float,
) -> Optional[str]:
    dangling = _dangling_ends(wall)
    for point in dangling:
        if _on_rect_boundary(
            point,
            x0=0.0,
            y0=0.0,
            x1=page_width,
            y1=page_height,
        ):
            return PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY
        if _on_rect_boundary(
            point,
            x0=float(bbox[0]),
            y0=float(bbox[1]),
            x1=float(bbox[2]),
            y1=float(bbox[3]),
        ):
            return PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY
    return None


def _line(values: Sequence[float]) -> Optional[Line]:
    if len(values) != 4:
        return None
    try:
        line = tuple(float(value) for value in values)
    except (TypeError, ValueError):
        return None
    if not all(math.isfinite(value) for value in line):
        return None
    if math.hypot(line[2] - line[0], line[3] - line[1]) <= _COORD_TOL:
        return None
    return line  # type: ignore[return-value]


def _canonical_direction(line: Line) -> Point:
    dx, dy = line[2] - line[0], line[3] - line[1]
    length = math.hypot(dx, dy)
    ux, uy = dx / length, dy / length
    if ux < -_COORD_TOL or (abs(ux) <= _COORD_TOL and uy < 0.0):
        ux, uy = -ux, -uy
    return (ux, uy)


def _projection(point: Point, direction: Point) -> float:
    return point[0] * direction[0] + point[1] * direction[1]


def _cross(left: Point, right: Point) -> float:
    return left[0] * right[1] - left[1] * right[0]


def _parallel(left: Line, right: Line) -> bool:
    ldx, ldy = left[2] - left[0], left[3] - left[1]
    rdx, rdy = right[2] - right[0], right[3] - right[1]
    llen = math.hypot(ldx, ldy)
    rlen = math.hypot(rdx, rdy)
    return abs(ldx * rdy - ldy * rdx) <= _PARALLEL_REL_TOL * llen * rlen


def _collinear(left: Line, right: Line) -> bool:
    if not _parallel(left, right):
        return False
    direction = _canonical_direction(left)
    return abs(
        _cross(direction, (right[0] - left[0], right[1] - left[1]))
    ) <= _COORD_TOL


def _endpoint_at_projection(line: Line, direction: Point, target: float) -> Optional[Point]:
    for point in ((line[0], line[1]), (line[2], line[3])):
        if abs(_projection(point, direction) - target) <= _COORD_TOL:
            return point
    return None


def _trusted_face_break(
    first_raw_id: str,
    first_line: Line,
    second_raw_id: str,
    second_line: Line,
) -> Optional[_TrustedFaceBreak]:
    if not _collinear(first_line, second_line):
        return None
    direction = _canonical_direction(first_line)
    first_values = sorted(
        (_projection((first_line[0], first_line[1]), direction),
         _projection((first_line[2], first_line[3]), direction))
    )
    second_values = sorted(
        (_projection((second_line[0], second_line[1]), direction),
         _projection((second_line[2], second_line[3]), direction))
    )
    if first_values[0] <= second_values[0]:
        left_id, left_line, left_values = first_raw_id, first_line, first_values
        right_id, right_line, right_values = second_raw_id, second_line, second_values
    else:
        left_id, left_line, left_values = second_raw_id, second_line, second_values
        right_id, right_line, right_values = first_raw_id, first_line, first_values
    gap_start, gap_end = left_values[1], right_values[0]
    if gap_end - gap_start <= _COORD_TOL:
        return None
    start_point = _endpoint_at_projection(left_line, direction, gap_start)
    end_point = _endpoint_at_projection(right_line, direction, gap_end)
    if start_point is None or end_point is None:
        return None
    return _TrustedFaceBreak(
        first_raw_id=left_id,
        second_raw_id=right_id,
        gap_start=gap_start,
        gap_end=gap_end,
        start_point=start_point,
        end_point=end_point,
        direction=direction,
    )


def _same_gap(left: _TrustedFaceBreak, right: _TrustedFaceBreak) -> bool:
    if abs(left.gap_start - right.gap_start) > _COORD_TOL:
        return False
    if abs(left.gap_end - right.gap_end) > _COORD_TOL:
        return False
    dot = left.direction[0] * right.direction[0] + left.direction[1] * right.direction[1]
    return abs(abs(dot) - 1.0) <= _PARALLEL_REL_TOL


def _distinct_parallel_axes(left: _TrustedFaceBreak, right: _TrustedFaceBreak) -> bool:
    delta = (
        right.start_point[0] - left.start_point[0],
        right.start_point[1] - left.start_point[1],
    )
    return abs(_cross(left.direction, delta)) > _COORD_TOL


def _segment_matches(line: Line, first: Point, second: Point) -> bool:
    start = (line[0], line[1])
    end = (line[2], line[3])
    direct = (
        abs(start[0] - first[0]) <= _COORD_TOL
        and abs(start[1] - first[1]) <= _COORD_TOL
        and abs(end[0] - second[0]) <= _COORD_TOL
        and abs(end[1] - second[1]) <= _COORD_TOL
    )
    reverse = (
        abs(start[0] - second[0]) <= _COORD_TOL
        and abs(start[1] - second[1]) <= _COORD_TOL
        and abs(end[0] - first[0]) <= _COORD_TOL
        and abs(end[1] - first[1]) <= _COORD_TOL
    )
    return direct or reverse


def _opening_raw_relation_sets(
    raw_lines: Mapping[str, Line],
) -> dict[tuple[str, str], set[PhysicalEquivalenceClass]]:
    """Derive relations only for a complete six-primitive G17 opening pattern."""
    if len(raw_lines) != 6:
        return {}
    items = sorted(raw_lines.items())
    breaks: list[_TrustedFaceBreak] = []
    for index, (left_id, left_line) in enumerate(items):
        for right_id, right_line in items[index + 1 :]:
            candidate = _trusted_face_break(left_id, left_line, right_id, right_line)
            if candidate is not None:
                breaks.append(candidate)

    relation_sets: dict[tuple[str, str], set[PhysicalEquivalenceClass]] = {}
    all_ids = set(raw_lines)
    for index, first in enumerate(breaks):
        for second in breaks[index + 1 :]:
            if not _same_gap(first, second) or not _distinct_parallel_axes(first, second):
                continue
            face_ids = {
                first.first_raw_id,
                first.second_raw_id,
                second.first_raw_id,
                second.second_raw_id,
            }
            if len(face_ids) != 4:
                continue
            remaining = sorted(all_ids - face_ids)
            if len(remaining) != 2:
                continue
            start_matches = [
                raw_id
                for raw_id in remaining
                if _segment_matches(
                    raw_lines[raw_id], first.start_point, second.start_point
                )
            ]
            end_matches = [
                raw_id
                for raw_id in remaining
                if _segment_matches(
                    raw_lines[raw_id], first.end_point, second.end_point
                )
            ]
            if len(start_matches) != 1 or len(end_matches) != 1:
                continue
            if start_matches[0] == end_matches[0]:
                continue

            same_pairs = {
                tuple(sorted((first.first_raw_id, second.first_raw_id))),
                tuple(sorted((first.second_raw_id, second.second_raw_id))),
            }
            pattern_ids = sorted(face_ids | {start_matches[0], end_matches[0]})
            if len(pattern_ids) != 6:
                continue
            for left_index, left_id in enumerate(pattern_ids):
                for right_id in pattern_ids[left_index + 1 :]:
                    pair = tuple(sorted((left_id, right_id)))
                    classification = (
                        PhysicalEquivalenceClass.SAME_PHYSICAL_WALL
                        if pair in same_pairs
                        else PhysicalEquivalenceClass.DISTINCT_PHYSICAL_WALLS
                    )
                    relation_sets.setdefault(pair, set()).add(classification)
    return relation_sets


def _producer_opening_relation_overrides(
    *,
    source_producer: SourceVisibilityProducer,
    published,
    page_id: str,
    records: Sequence[PhysicalWallCandidateRecord],
) -> dict[tuple[str, str], PhysicalEquivalenceClass]:
    """Re-prove G17 source openings and map their exact primitives to W4 candidates."""
    visibility = source_producer.authority()
    opening_authority = PhysicalOpeningAuthority(visibility)
    proven_records: dict[str, object] = {}

    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = opening_authority.prove_existence(selector)
        existence = result.existence_record
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and existence is not None
            and existence.page_id == page_id
        ):
            proven_records[existence.record_id] = existence

    by_raw_id: dict[str, list[PhysicalWallCandidateRecord]] = {}
    for record in records:
        for raw_id in record.physical_identity.source_primitive_ids:
            by_raw_id.setdefault(str(raw_id), []).append(record)

    candidate_relation_sets: dict[
        tuple[str, str], set[PhysicalEquivalenceClass]
    ] = {}
    prefix = "visible:segment:"

    for existence in proven_records.values():
        raw_lines: dict[str, Line] = {}
        valid = True
        for observation_id in existence.source_observation_ids:  # type: ignore[attr-defined]
            resolved = visibility.resolve_visible(
                ObservationSelector(
                    document_id=existence.document_id,  # type: ignore[attr-defined]
                    revision_id=existence.revision_id,  # type: ignore[attr-defined]
                    source_sha256=existence.source_sha256,  # type: ignore[attr-defined]
                    snapshot_id=existence.snapshot_id,  # type: ignore[attr-defined]
                    observation_id=observation_id,
                )
            )
            observation = resolved.observation
            if (
                resolved.status is not EvidenceResolutionStatus.CORROBORATED
                or observation is None
                or not observation.source_primitive_ref.startswith(prefix)
            ):
                valid = False
                break
            raw_id = observation.source_primitive_ref[len(prefix) :]
            geometry = _line(observation.geometry)
            if not raw_id or geometry is None or raw_id in raw_lines:
                valid = False
                break
            raw_lines[raw_id] = geometry
        if not valid or len(raw_lines) != 6:
            continue

        raw_relations = _opening_raw_relation_sets(raw_lines)
        if not raw_relations:
            continue

        candidate_for_raw: dict[str, str] = {}
        for raw_id in raw_lines:
            matches = by_raw_id.get(raw_id, [])
            if len(matches) != 1:
                valid = False
                break
            candidate_for_raw[raw_id] = matches[0].wall_candidate_id
        if not valid or len(set(candidate_for_raw.values())) != 6:
            continue

        for (left_raw, right_raw), classifications in raw_relations.items():
            left_id = candidate_for_raw[left_raw]
            right_id = candidate_for_raw[right_raw]
            if left_id == right_id:
                valid = False
                break
            pair = tuple(sorted((left_id, right_id)))
            candidate_relation_sets.setdefault(pair, set()).update(classifications)
        if not valid:
            continue

    return {
        pair: next(iter(classifications))
        for pair, classifications in candidate_relation_sets.items()
        if len(classifications) == 1
    }


def _union_find_groups(
    pairs: Sequence[tuple[str, str]], members: Sequence[str]
) -> list[list[str]]:
    parent = {member: member for member in members}

    def find(item: str) -> str:
        while parent[item] != item:
            parent[item] = parent[parent[item]]
            item = parent[item]
        return item

    def union(left: str, right: str) -> None:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[root_right] = root_left

    for left, right in pairs:
        if left in parent and right in parent:
            union(left, right)
    groups: dict[str, list[str]] = {}
    for member in members:
        groups.setdefault(find(member), []).append(member)
    return [sorted(group) for group in groups.values()]


def _apply_trusted_relation_overrides(
    identities: Sequence[PhysicalWallIdentity],
    baseline: PhysicalWallEquivalenceResolution,
    overrides: Mapping[tuple[str, str], PhysicalEquivalenceClass],
) -> PhysicalWallEquivalenceResolution:
    """Reconcile source-proven relations without changing generic classifier semantics."""
    usable = [identity for identity in identities if identity.usable]
    if len(usable) != len(identities) or not overrides:
        return baseline

    pair_map = {
        tuple(sorted((left, right))): classification
        for left, right, classification in baseline.pair_classifications
    }
    for pair, classification in overrides.items():
        current = pair_map.get(tuple(sorted(pair)))
        if current == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value:
            pair_map[tuple(sorted(pair))] = classification.value

    member_ids = [identity.wall_candidate_id for identity in usable]
    same_links: list[tuple[str, str]] = []
    ambiguous_links: list[tuple[str, str]] = []
    for pair, classification in pair_map.items():
        if classification == PhysicalEquivalenceClass.SAME_PHYSICAL_WALL.value:
            same_links.append(pair)
        elif classification == PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE.value:
            ambiguous_links.append(pair)

    related_links = same_links + ambiguous_links
    components = _union_find_groups(related_links, member_ids) if member_ids else []
    ambiguous_edges = {frozenset(pair) for pair in ambiguous_links}
    same_edges = {frozenset(pair) for pair in same_links}
    blockers: dict[str, list[str]] = {}
    ambiguous_walls: set[str] = set()
    same_groups: list[tuple[str, ...]] = []
    representatives: list[str] = []

    for component in components:
        has_ambiguous = any(
            frozenset((left, right)) in ambiguous_edges
            for index, left in enumerate(component)
            for right in component[index + 1 :]
        )
        has_same = any(
            frozenset((left, right)) in same_edges
            for index, left in enumerate(component)
            for right in component[index + 1 :]
        )
        if has_ambiguous:
            ambiguous_walls.update(component)
            for wall_id in component:
                blockers.setdefault(wall_id, []).append(
                    "ambiguous_physical_wall_equivalence"
                )
            continue
        if has_same and len(component) > 1:
            group = tuple(sorted(component))
            same_groups.append(group)
            representative = sorted(group)[0]
            representatives.append(representative)
            for wall_id in group:
                if wall_id != representative:
                    blockers.setdefault(wall_id, []).append(
                        f"equivalent_physical_wall_represented_by:{representative}"
                    )
            continue
        representatives.extend(
            wall_id for wall_id in component if wall_id not in blockers
        )

    linked = {wall_id for component in components for wall_id in component}
    for wall_id in member_ids:
        if wall_id not in linked and wall_id not in blockers:
            representatives.append(wall_id)

    representatives = list(dict.fromkeys(representatives))
    abstained = [wall_id for wall_id in member_ids if wall_id in blockers]
    return PhysicalWallEquivalenceResolution(
        scope_viewport_id=baseline.scope_viewport_id,
        representative_wall_ids=tuple(representatives),
        abstained_wall_ids=tuple(dict.fromkeys(abstained)),
        equivalence_groups=tuple(same_groups),
        ambiguous_wall_ids=tuple(sorted(ambiguous_walls)),
        same_wall_ids=tuple(
            sorted({wall_id for group in same_groups for wall_id in group})
        ),
        pair_classifications=tuple(
            sorted((left, right, classification) for (left, right), classification in pair_map.items())
        ),
        blocking_reasons_by_wall_id={
            wall_id: tuple(dict.fromkeys(reasons))
            for wall_id, reasons in blockers.items()
            if reasons
        },
    )


def _assemble_scope_result(
    *,
    source_producer: SourceVisibilityProducer,
    published,
    page_id: str,
    selector: PhysicalWallCandidateSelector,
    segments: Sequence[dict],
    source_observation_ids: Sequence[str],
    page_width: float,
    page_height: float,
    source_bytes: bytes,
    viewport=None,
    sibling_set_fingerprint: Optional[str] = None,
    pre_boundary_reasons: Sequence[str] = (),
    scope_boundary_observation_ids: Sequence[str] = (),
    ambiguous_source_observation_ids: Sequence[str] = (),
) -> PhysicalWallCandidateScopeResult:
    scope_id = selector.decision_scope_id
    graph = build_wall_graph_for_viewport(tuple(segments))
    junctions, relationships = classify_junctions(
        graph,
        document_id=published.revision.document_id,
        page_id=page_id,
        viewport_id=scope_id,
    )
    walls, _rekeyed_junctions = assemble_wall_topology(
        graph,
        junctions,
        relationships,
        viewport_id=scope_id,
    )
    identities = collect_physical_wall_identities(walls, graph)

    ordered_walls = sorted(walls, key=lambda item: item.candidate_id)
    records: list[PhysicalWallCandidateRecord] = []
    ordered_identities: list[PhysicalWallIdentity] = []
    for wall in ordered_walls:
        identity = identities.get(wall.candidate_id)
        if identity is None or not identity.usable:
            return _blocked(selector, PHYSICAL_WALL_CANDIDATE_IDENTITY_UNRESOLVED)
        records.append(
            PhysicalWallCandidateRecord(
                wall_candidate_id=wall.candidate_id,
                wall_candidate=wall,
                physical_identity=identity,
            )
        )
        ordered_identities.append(identity)

    baseline_equivalence = resolve_physical_wall_equivalence(
        tuple(ordered_identities),
        walls_by_id={wall.candidate_id: wall for wall in ordered_walls},
    )
    trusted_overrides = _producer_opening_relation_overrides(
        source_producer=source_producer,
        published=published,
        page_id=page_id,
        records=tuple(records),
    )
    equivalence = _apply_trusted_relation_overrides(
        tuple(ordered_identities),
        baseline_equivalence,
        trusted_overrides,
    )

    boundary_reasons: list[str] = list(pre_boundary_reasons)
    boundary_pdf = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        boundary_page = boundary_pdf.load_page(int(page_id) - 1)
        for wall in ordered_walls:
            if viewport is None:
                reason = _scope_boundary_reason(
                    wall,
                    page=boundary_page,
                    page_number=int(page_id),
                    page_width=page_width,
                    page_height=page_height,
                )
            else:
                reason = _viewport_scope_boundary_reason(
                    wall,
                    bbox=viewport.bounding_box,
                    page_width=page_width,
                    page_height=page_height,
                )
            if reason is not None:
                boundary_reasons.append(reason)
    finally:
        boundary_pdf.close()

    cropped = bool(boundary_reasons)
    reason_codes = (
        (PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED, *dict.fromkeys(boundary_reasons))
        if cropped
        else (PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,)
    )
    viewport_bbox = (
        None
        if viewport is None or viewport.bounding_box is None
        else tuple(float(value) for value in viewport.bounding_box)
    )
    return PhysicalWallCandidateScopeResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        scope_complete=not cropped,
        records=tuple(records),
        source_observation_ids=tuple(sorted(dict.fromkeys(source_observation_ids))),
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=scope_id,
        reason_codes=reason_codes,
        equivalence=equivalence,
        proposition=PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED,
        scope_kind="page" if viewport is None else "viewport",
        viewport_id=None if viewport is None else str(viewport.view_id),
        viewport_bbox=viewport_bbox,
        viewport_view_type=None if viewport is None else str(viewport.view_type),
        viewport_status=None if viewport is None else str(viewport.status),
        viewport_boundary_source=None if viewport is None else str(viewport.boundary_source),
        viewport_producer_fingerprint=(
            None if viewport is None else segmented_viewport_producer_fingerprint(viewport)
        ),
        viewport_sibling_set_fingerprint=sibling_set_fingerprint,
        scope_boundary_observation_ids=tuple(
            sorted(dict.fromkeys(scope_boundary_observation_ids))
        ),
        ambiguous_source_observation_ids=tuple(
            sorted(dict.fromkeys(ambiguous_source_observation_ids))
        ),
    )


def _build_scope_result(
    *,
    source_producer: SourceVisibilityProducer,
    published,
    source_bytes: bytes,
    page_id: str,
) -> PhysicalWallCandidateScopeResult:
    scope_id = _decision_scope_id(page_id)
    selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id=page_id,
        decision_scope_id=scope_id,
    )
    page_number = int(page_id)
    if (
        published.coverage.state != "complete"
        or published.coverage.failed_pages
        or page_number not in published.coverage.decoded_pages
    ):
        return _blocked(selector, PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE)

    segments, source_observation_ids, page_width, page_height = _source_page_segments(
        source_producer=source_producer,
        published=published,
        source_bytes=source_bytes,
        page_id=page_id,
        decision_scope_id=scope_id,
    )
    return _assemble_scope_result(
        source_producer=source_producer,
        published=published,
        page_id=page_id,
        selector=selector,
        segments=segments,
        source_observation_ids=source_observation_ids,
        page_width=page_width,
        page_height=page_height,
        source_bytes=source_bytes,
    )


def _build_authenticated_viewport_scope_results(
    *,
    source_producer: SourceVisibilityProducer,
    published,
    source_bytes: bytes,
    page_id: str,
) -> tuple[PhysicalWallCandidateScopeResult, ...]:
    page_number = int(page_id)
    if (
        published.coverage.state != "complete"
        or published.coverage.failed_pages
        or page_number not in published.coverage.decoded_pages
    ):
        return ()

    page_scope_id = _decision_scope_id(page_id)
    page_segments, _page_observation_ids, page_width, page_height = _source_page_segments(
        source_producer=source_producer,
        published=published,
        source_bytes=source_bytes,
        page_id=page_id,
        decision_scope_id=page_scope_id,
    )
    pdf = fitz.open(stream=source_bytes, filetype="pdf")
    try:
        page = pdf.load_page(page_number - 1)
        authenticated = _authenticated_viewports(page, page_number=page_number)
    finally:
        pdf.close()
    if authenticated is None:
        return ()
    all_viewports, eligible = authenticated
    if not eligible:
        return ()
    sibling_fingerprint = _viewport_sibling_set_fingerprint(all_viewports)

    results: list[PhysicalWallCandidateScopeResult] = []
    for viewport in eligible:
        assert viewport.bounding_box is not None
        scope_id = _viewport_decision_scope_id(
            published=published,
            page_id=page_id,
            viewport=viewport,
            sibling_set_fingerprint=sibling_fingerprint,
        )
        selector = PhysicalWallCandidateSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            page_id=page_id,
            decision_scope_id=scope_id,
        )
        owned: list[dict] = []
        owned_observation_ids: list[str] = []
        boundary_observation_ids: list[str] = []
        ambiguous_observation_ids: list[str] = []
        pre_boundary_reasons: list[str] = []

        for segment in page_segments:
            observation_id = str(segment.get("source_observation_id") or "")
            owners = [
                other
                for other in eligible
                if other.bounding_box is not None
                and _segment_fully_inside_bbox(segment, other.bounding_box)
            ]
            target_owned = any(other.view_id == viewport.view_id for other in owners)
            structural, _exclude_reasons = is_structural_candidate_segment(segment)

            if target_owned and len(owners) == 1 and not _segment_lies_on_bbox_edge(
                segment, viewport.bounding_box
            ):
                scoped = dict(segment)
                scoped["viewport_id"] = scope_id
                owned.append(scoped)
                if observation_id:
                    owned_observation_ids.append(observation_id)
                continue

            if target_owned and _segment_is_authenticated_vector_frame_edge(
                segment, viewport=viewport
            ):
                # Exact F.07 vector-frame boundary evidence is not drawing
                # content. It is excluded by ownership provenance, not by
                # proximity to text or a project-specific semantic rule.
                continue

            if target_owned and (
                len(owners) > 1
                or _segment_lies_on_bbox_edge(segment, viewport.bounding_box)
            ):
                if structural:
                    pre_boundary_reasons.append(
                        PHYSICAL_WALL_CANDIDATE_SOURCE_PRIMITIVE_OWNERSHIP_AMBIGUOUS
                    )
                    if observation_id:
                        ambiguous_observation_ids.append(observation_id)
                continue

            if _segment_intersects_bbox(segment, viewport.bounding_box) and structural:
                pre_boundary_reasons.append(
                    PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY
                )
                if observation_id:
                    boundary_observation_ids.append(observation_id)

        results.append(
            _assemble_scope_result(
                source_producer=source_producer,
                published=published,
                page_id=page_id,
                selector=selector,
                segments=owned,
                source_observation_ids=owned_observation_ids,
                page_width=page_width,
                page_height=page_height,
                source_bytes=source_bytes,
                viewport=viewport,
                sibling_set_fingerprint=sibling_fingerprint,
                pre_boundary_reasons=pre_boundary_reasons,
                scope_boundary_observation_ids=boundary_observation_ids,
                ambiguous_source_observation_ids=ambiguous_observation_ids,
            )
        )
    return tuple(results)


class PhysicalWallCandidateProducer:
    """Trusted writer derived only from an already-ingested visibility producer."""

    def __init__(self, scopes: Mapping[_ScopeKey, PhysicalWallCandidateScopeResult], *, _seal=None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "PhysicalWallCandidateProducer must be obtained from "
                "from_source_visibility_producer()"
            )
        self._scopes = MappingProxyType(dict(scopes))

    @classmethod
    def from_authenticated_viewports(
        cls,
        source_visibility_producer,
        *,
        page_ids: Optional[Sequence[str]] = None,
    ):
        """Build legacy page scopes plus authenticated F.07 viewport scopes.

        Callers may address source pages only. Viewport geometry, membership,
        completeness, source primitives and wall candidates are resolved from
        the immutable source by this producer.
        """
        return cls._from_source_visibility_producer(
            source_visibility_producer,
            page_ids=page_ids,
            include_authenticated_viewports=True,
        )

    @classmethod
    def from_source_visibility_producer(
        cls,
        source_visibility_producer,
        *,
        page_ids: Optional[Sequence[str]] = None,
    ):
        return cls._from_source_visibility_producer(
            source_visibility_producer,
            page_ids=page_ids,
            include_authenticated_viewports=False,
        )

    @classmethod
    def _from_source_visibility_producer(
        cls,
        source_visibility_producer,
        *,
        page_ids: Optional[Sequence[str]],
        include_authenticated_viewports: bool,
    ):
        """Build wall scopes, optionally narrowed by source page address.

        page_ids is addressing only: it can select which already-decoded source
        pages are materialized, but it cannot inject geometry, candidates,
        completeness, roles, quantities, or any other evidence-shaped input.
        The legacy no-argument behavior remains the complete decoded-page build.
        """
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError(
                "source_visibility_producer must be an actual SourceVisibilityProducer"
            )

        selected_page_ids: Optional[set[str]] = None
        if page_ids is not None:
            selected_page_ids = {
                str(page_id).strip()
                for page_id in page_ids
                if str(page_id).strip()
            }
            if not selected_page_ids:
                raise ValueError("page_ids must contain at least one source page")

        # Preserve the current mainline raster-wall path while keeping page
        # addressing operationally narrow. Validate the requested source pages
        # against producer-owned decode coverage first, then render raster
        # fallback only for those pages. No caller pixels, segments, DPI,
        # thresholds, labels, or quantities enter this path.
        for revision_id in tuple(
            sorted(source_visibility_producer._published_by_revision)
        ):
            pre_augmented = source_visibility_producer._published_by_revision[
                revision_id
            ]
            decoded_page_ids = {
                str(int(page_number))
                for page_number in pre_augmented.coverage.decoded_pages
            }
            if (
                selected_page_ids is not None
                and not selected_page_ids <= decoded_page_ids
            ):
                raise ValueError(PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE)
            source_visibility_producer.augment_with_raster_visible_segments(
                revision_id,
                page_ids=(
                    tuple(
                        sorted(
                            selected_page_ids,
                            key=lambda value: int(value),
                        )
                    )
                    if selected_page_ids is not None
                    else None
                ),
            )

        published_by_revision = dict(source_visibility_producer._published_by_revision)
        store = source_visibility_producer._producer._store
        scopes: dict[_ScopeKey, PhysicalWallCandidateScopeResult] = {}

        for revision_id, published in sorted(published_by_revision.items()):
            if source_visibility_producer._producer.current_revision_id(
                published.revision.document_id
            ) != revision_id:
                continue
            source_bytes = store.source_bytes_by_revision.get(revision_id)
            if source_bytes is None:
                raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)
            digest = hashlib.sha256(source_bytes).hexdigest()
            if digest != published.revision.source_sha256:
                raise RuntimeError(PHYSICAL_WALL_CANDIDATE_SOURCE_INTEGRITY_FAILURE)

            decoded_page_ids = {
                str(int(page_number))
                for page_number in published.coverage.decoded_pages
            }
            if selected_page_ids is not None and not selected_page_ids <= decoded_page_ids:
                raise ValueError(PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE)
            materialized_page_ids = (
                sorted(selected_page_ids, key=lambda value: int(value))
                if selected_page_ids is not None
                else sorted(decoded_page_ids, key=lambda value: int(value))
            )

            for page_id in materialized_page_ids:
                result = _build_scope_result(
                    source_producer=source_visibility_producer,
                    published=published,
                    source_bytes=source_bytes,
                    page_id=page_id,
                )
                key = _ScopeKey(
                    document_id=result.document_id,
                    revision_id=result.revision_id,
                    source_sha256=result.source_sha256,
                    snapshot_id=result.snapshot_id,
                    page_id=result.page_id,
                    decision_scope_id=result.decision_scope_id,
                )
                scopes[key] = result

                if include_authenticated_viewports:
                    for viewport_result in _build_authenticated_viewport_scope_results(
                        source_producer=source_visibility_producer,
                        published=published,
                        source_bytes=source_bytes,
                        page_id=page_id,
                    ):
                        viewport_key = _ScopeKey(
                            document_id=viewport_result.document_id,
                            revision_id=viewport_result.revision_id,
                            source_sha256=viewport_result.source_sha256,
                            snapshot_id=viewport_result.snapshot_id,
                            page_id=viewport_result.page_id,
                            decision_scope_id=viewport_result.decision_scope_id,
                        )
                        scopes[viewport_key] = viewport_result

        return cls(scopes, _seal=_PRODUCER_SEAL)

    def authority(self):
        return PhysicalWallCandidateAuthority(self._scopes, _seal=_AUTHORITY_SEAL)


class PhysicalWallCandidateAuthority:
    """Read-only exact-scope resolver. Construction is producer-sealed."""

    def __init__(self, scopes: Mapping[_ScopeKey, PhysicalWallCandidateScopeResult], *, _seal=None) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError(
                "PhysicalWallCandidateAuthority must be obtained from "
                "PhysicalWallCandidateProducer.authority()"
            )
        self._scopes = MappingProxyType(dict(scopes))

    def resolve_scope(self, selector):
        if not isinstance(selector, PhysicalWallCandidateSelector):
            raise TypeError("selector must be PhysicalWallCandidateSelector")

        scope_id = str(selector.decision_scope_id)
        is_page_scope = scope_id == _decision_scope_id(selector.page_id)
        is_viewport_scope = scope_id.startswith(
            f"wall-source:viewport:{selector.page_id}:"
        )
        if not is_page_scope and not is_viewport_scope:
            return _blocked(selector, PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE)
        if is_viewport_scope:
            expected_fingerprint = _viewport_selector_payload_fingerprint(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=selector.decision_scope_id,
            )
            seal = selector._viewport_selector_seal
            if (
                not isinstance(seal, tuple)
                or len(seal) != 2
                or seal[0] is not _VIEWPORT_SELECTOR_SEAL
                or seal[1] != expected_fingerprint
                or selector._viewport_selector_fingerprint != expected_fingerprint
            ):
                return _blocked(
                    selector,
                    PHYSICAL_WALL_CANDIDATE_VIEWPORT_AUTHORITY_INVALID,
                )

        key = _ScopeKey(
            document_id=str(selector.document_id),
            revision_id=str(selector.revision_id),
            source_sha256=str(selector.source_sha256),
            snapshot_id=str(selector.snapshot_id),
            page_id=str(selector.page_id),
            decision_scope_id=str(selector.decision_scope_id),
        )
        result = self._scopes.get(key)
        if result is None:
            return _blocked(selector, PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE)
        return result

    @staticmethod
    def _selector_for_result(
        result: PhysicalWallCandidateScopeResult,
    ) -> PhysicalWallCandidateSelector:
        if result.scope_kind != "viewport":
            return PhysicalWallCandidateSelector(
                document_id=result.document_id,
                revision_id=result.revision_id,
                source_sha256=result.source_sha256,
                snapshot_id=result.snapshot_id,
                page_id=result.page_id,
                decision_scope_id=result.decision_scope_id,
            )
        fingerprint = _viewport_selector_payload_fingerprint(
            document_id=result.document_id,
            revision_id=result.revision_id,
            source_sha256=result.source_sha256,
            snapshot_id=result.snapshot_id,
            page_id=result.page_id,
            decision_scope_id=result.decision_scope_id,
        )
        return PhysicalWallCandidateSelector(
            document_id=result.document_id,
            revision_id=result.revision_id,
            source_sha256=result.source_sha256,
            snapshot_id=result.snapshot_id,
            page_id=result.page_id,
            decision_scope_id=result.decision_scope_id,
            _viewport_selector_fingerprint=fingerprint,
            _viewport_selector_seal=(_VIEWPORT_SELECTOR_SEAL, fingerprint),
        )

    def selector_for_viewport(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
        viewport_id: str,
    ) -> Optional[PhysicalWallCandidateSelector]:
        """Return a sealed address only for a materialized authenticated viewport."""
        matches = [
            result
            for result in self._scopes.values()
            if result.scope_kind == "viewport"
            and result.document_id == str(document_id)
            and result.revision_id == str(revision_id)
            and result.source_sha256 == str(source_sha256)
            and result.snapshot_id == str(snapshot_id)
            and result.page_id == str(page_id)
            and result.viewport_id == str(viewport_id)
        ]
        if len(matches) != 1:
            return None
        return self._selector_for_result(matches[0])

    def selector_for_decision_scope(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
        decision_scope_id: str,
    ) -> Optional[PhysicalWallCandidateSelector]:
        """Reissue a valid selector only for an exact producer-owned scope."""
        key = _ScopeKey(
            document_id=str(document_id),
            revision_id=str(revision_id),
            source_sha256=str(source_sha256),
            snapshot_id=str(snapshot_id),
            page_id=str(page_id),
            decision_scope_id=str(decision_scope_id),
        )
        result = self._scopes.get(key)
        if result is None:
            return None
        return self._selector_for_result(result)


__all__ = [
    "PHYSICAL_WALL_CANDIDATE_AUTHORITY_SCHEMA_VERSION",
    "PHYSICAL_WALL_CANDIDATE_SCOPE_BOUNDS_UNRESOLVED",
    "PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_PAGE_BOUNDARY",
    "PHYSICAL_WALL_CANDIDATE_SCOPE_CROPPED_AT_VIEWPORT_BOUNDARY",
    "PHYSICAL_WALL_CANDIDATE_SCOPE_RESOLVED",
    "PHYSICAL_WALL_CANDIDATE_SCOPE_UNAVAILABLE",
    "PHYSICAL_WALL_CANDIDATE_SOURCE_PRIMITIVE_OWNERSHIP_AMBIGUOUS",
    "PHYSICAL_WALL_CANDIDATE_VIEWPORT_AUTHORITY_INVALID",
    "PHYSICAL_WALL_CANDIDATE_VIEWPORT_LINEAGE_MISMATCH",
    "PhysicalWallCandidateAuthority",
    "PhysicalWallCandidateProducer",
    "PhysicalWallCandidateRecord",
    "PhysicalWallCandidateScopeResult",
    "PhysicalWallCandidateSelector",
]
