"""Shadow-only positive physical wall-body evidence.

CRITICAL SHADOW BOUNDARY
========================
PhysicalWallBodyEvidence must never be consumed by any live opening,
host-binding, opening-deduction, gross/net-wall, finish, commercial-output,
or JobHub authority until a separate explicit authority-promotion design and
review approves that consumption.

This module is an evidence compiler, not a quantity producer. It may nominate
parallel-face wall-band candidates and may resolve a local physical-wall-body
proposition from independently supplied source/topology evidence. It does not
claim scope completeness and it does not prove an opening exists.

Segmentation support, when supplied by a future raster producer, is supporting
evidence only. It is never sufficient by itself. If segmentation is absent,
the resolver does not fall back to parallel-lines-equals-wall; a double-face
candidate must instead have independent topology plus source-supported
thickness-family evidence, otherwise it abstains.

The first implementation is intentionally shadow-only and has no live caller.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import re
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_vector_geometry_v130 import detect_wall_pairs
from pb_wall_room_topology_stage_a import is_structural_candidate_segment


PHYSICAL_WALL_BODY_EVIDENCE_SHADOW_SCHEMA_VERSION = "0.1.0"

PHYSICAL_WALL_BODY_SHADOW_ONLY = "physical_wall_body_shadow_only"
PHYSICAL_WALL_BODY_CORROBORATED_LOCAL = "physical_wall_body_corroborated_local"
PHYSICAL_WALL_BODY_EVIDENCE_INSUFFICIENT = "physical_wall_body_evidence_insufficient"
PHYSICAL_WALL_BODY_SOURCE_PROVENANCE_INCOMPLETE = (
    "physical_wall_body_source_provenance_incomplete"
)
PHYSICAL_WALL_BODY_GEOMETRY_UNAVAILABLE = "physical_wall_body_geometry_unavailable"
PHYSICAL_WALL_BODY_FACE_CARDINALITY_UNSUPPORTED = (
    "physical_wall_body_face_cardinality_unsupported"
)
PHYSICAL_WALL_BODY_PARALLEL_FACES_PRESENT = "physical_wall_body_parallel_faces_present"
PHYSICAL_WALL_BODY_SINGLE_FACE_CANDIDATE = "physical_wall_body_single_face_candidate"
PHYSICAL_WALL_BODY_LONGITUDINAL_OVERLAP_PRESENT = (
    "physical_wall_body_longitudinal_overlap_present"
)
PHYSICAL_WALL_BODY_TOPOLOGY_CONTINUITY_PRESENT = (
    "physical_wall_body_topology_continuity_present"
)
PHYSICAL_WALL_BODY_THICKNESS_FAMILY_PRESENT = (
    "physical_wall_body_thickness_family_present"
)
PHYSICAL_WALL_BODY_SEGMENTATION_SUPPORT_PRESENT = (
    "physical_wall_body_segmentation_support_present"
)
PHYSICAL_WALL_BODY_SEGMENTATION_SUPPORT_UNAVAILABLE = (
    "physical_wall_body_segmentation_support_unavailable"
)
PHYSICAL_WALL_BODY_PARALLEL_FACES_WITHOUT_STRONG_SUPPORT = (
    "physical_wall_body_parallel_faces_without_strong_support"
)
PHYSICAL_WALL_BODY_NEGATIVE_EVIDENCE_BLOCKED = (
    "physical_wall_body_negative_evidence_blocked"
)
NETWORK_INCOMPLETE_FOR_SCOPE = "network_incomplete_for_scope"
OPENING_LOCAL_TOPOLOGY_PRESENT = "opening_local_topology_present"

NEGATIVE_DIMENSION_PATTERN_DETECTED = "negative_dimension_pattern_detected"
NEGATIVE_STRUCTURAL_GRID_PATTERN_DETECTED = "negative_structural_grid_pattern_detected"
NEGATIVE_TABLE_OR_SCHEDULE_GRID_PATTERN_DETECTED = (
    "negative_table_or_schedule_grid_pattern_detected"
)
NEGATIVE_PAVING_GRID_PATTERN_DETECTED = "negative_paving_grid_pattern_detected"
NEGATIVE_GLAZING_PATTERN_DETECTED = "negative_glazing_pattern_detected"
NEGATIVE_LOCAL_FIXTURE_PATTERN_DETECTED = "negative_local_fixture_pattern_detected"
NEGATIVE_TITLE_BLOCK_OR_ANNOTATION_PATTERN_DETECTED = (
    "negative_title_block_or_annotation_pattern_detected"
)
NEGATIVE_FURNITURE_PATTERN_DETECTED = "negative_furniture_pattern_detected"
NEGATIVE_ROOF_OR_FINISH_HATCH_PATTERN_DETECTED = (
    "negative_roof_or_finish_hatch_pattern_detected"
)
NEGATIVE_AMBIGUOUS_DOUBLE_LINE_PATTERN_DETECTED = (
    "negative_ambiguous_double_line_pattern_detected"
)
NEGATIVE_EXPLICIT_NON_WALL_SOURCE_ROLE = "negative_explicit_non_wall_source_role"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
Point = tuple[float, float]


def _clean_required(value: str, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


def _clean_optional(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    clean = str(value).strip()
    return clean or None


def _sorted_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _finite_geometry(
    geometry: Optional[Sequence[Sequence[float]]],
) -> Optional[tuple[Point, ...]]:
    if geometry is None:
        return None
    points: list[Point] = []
    for point in geometry:
        if len(point) != 2:
            raise ValueError(
                "wall_band_geometry points must contain exactly two coordinates"
            )
        x, y = float(point[0]), float(point[1])
        if not math.isfinite(x) or not math.isfinite(y):
            raise ValueError("wall_band_geometry coordinates must be finite")
        points.append((x, y))
    if len(points) < 2:
        raise ValueError(
            "wall_band_geometry must contain at least two points when supplied"
        )
    return tuple(points)


@dataclass(frozen=True)
class WallBandCandidate:
    """Non-authoritative paired-face candidate emitted for shadow evaluation."""

    candidate_id: str
    candidate_face_ids: tuple[str, str]
    wall_band_geometry: tuple[Point, ...]
    separation_pt: float
    overlap_pt: float
    reason_codes: tuple[str, ...] = (
        PHYSICAL_WALL_BODY_PARALLEL_FACES_PRESENT,
        PHYSICAL_WALL_BODY_LONGITUDINAL_OVERLAP_PRESENT,
    )
    schema_version: str = PHYSICAL_WALL_BODY_EVIDENCE_SHADOW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _clean_required(self.candidate_id, "candidate_id")
        if len(set(self.candidate_face_ids)) != 2:
            raise ValueError(
                "candidate_face_ids must contain two distinct face ids"
            )
        if (
            not math.isfinite(float(self.separation_pt))
            or float(self.separation_pt) <= 0.0
        ):
            raise ValueError("separation_pt must be finite and positive")
        if (
            not math.isfinite(float(self.overlap_pt))
            or float(self.overlap_pt) <= 0.0
        ):
            raise ValueError("overlap_pt must be finite and positive")


@dataclass(frozen=True)
class PhysicalWallBodyEvidence:
    """Shadow evidence record for one local physical-wall-body proposition."""

    record_id: str

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    view_scope_id: Optional[str]

    physical_wall_body_id: Optional[str]

    candidate_face_ids: tuple[str, ...]
    source_observation_ids: tuple[str, ...]

    wall_band_geometry: Optional[tuple[Point, ...]]

    thickness_family_id: Optional[str]
    topology_evidence_ids: tuple[str, ...]
    negative_evidence_ids: tuple[str, ...]

    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]

    schema_version: str = PHYSICAL_WALL_BODY_EVIDENCE_SHADOW_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "record_id", _clean_required(self.record_id, "record_id")
        )
        object.__setattr__(
            self, "document_id", _clean_required(self.document_id, "document_id")
        )
        object.__setattr__(
            self, "revision_id", _clean_required(self.revision_id, "revision_id")
        )
        source_hash = str(self.source_sha256 or "").strip().lower()
        if not _SHA256_RE.fullmatch(source_hash):
            raise ValueError(
                "source_sha256 must be a 64-character lowercase SHA-256"
            )
        object.__setattr__(self, "source_sha256", source_hash)
        object.__setattr__(
            self, "snapshot_id", _clean_required(self.snapshot_id, "snapshot_id")
        )
        object.__setattr__(self, "page_id", _clean_required(self.page_id, "page_id"))
        object.__setattr__(self, "viewport_id", _clean_optional(self.viewport_id))
        object.__setattr__(self, "view_scope_id", _clean_optional(self.view_scope_id))
        object.__setattr__(
            self,
            "physical_wall_body_id",
            _clean_optional(self.physical_wall_body_id),
        )
        object.__setattr__(
            self, "candidate_face_ids", _sorted_unique(self.candidate_face_ids)
        )
        object.__setattr__(
            self, "source_observation_ids", _sorted_unique(self.source_observation_ids)
        )
        object.__setattr__(
            self, "topology_evidence_ids", _sorted_unique(self.topology_evidence_ids)
        )
        object.__setattr__(
            self, "negative_evidence_ids", _sorted_unique(self.negative_evidence_ids)
        )
        object.__setattr__(
            self, "reason_codes", _sorted_unique(self.reason_codes)
        )
        object.__setattr__(
            self, "thickness_family_id", _clean_optional(self.thickness_family_id)
        )
        object.__setattr__(
            self, "wall_band_geometry", _finite_geometry(self.wall_band_geometry)
        )


def _segment_line(
    segment: Mapping[str, object],
) -> tuple[float, float, float, float]:
    try:
        line = (
            float(segment["x1"]),
            float(segment["y1"]),
            float(segment["x2"]),
            float(segment["y2"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("candidate segment geometry is unavailable") from exc
    if not all(math.isfinite(value) for value in line):
        raise ValueError("candidate segment geometry must be finite")
    return line


def _aligned_band_polygon(
    first: Mapping[str, object],
    second: Mapping[str, object],
) -> tuple[Point, ...]:
    """Return a deterministic four-corner band polygon for two paired faces."""

    a = _segment_line(first)
    b = _segment_line(second)
    ax, ay = a[2] - a[0], a[3] - a[1]
    length = math.hypot(ax, ay)
    if length <= 1e-12:
        raise ValueError("candidate face is degenerate")
    ux, uy = ax / length, ay / length
    if ux < 0.0 or (abs(ux) <= 1e-12 and uy < 0.0):
        ux, uy = -ux, -uy

    def ordered(line: tuple[float, float, float, float]) -> tuple[Point, Point]:
        p1 = (line[0], line[1])
        p2 = (line[2], line[3])
        s1 = p1[0] * ux + p1[1] * uy
        s2 = p2[0] * ux + p2[1] * uy
        return (p1, p2) if s1 <= s2 else (p2, p1)

    a0, a1 = ordered(a)
    b0, b1 = ordered(b)
    return (a0, a1, b1, b0)


def generate_wall_band_candidates_shadow(
    segments: Sequence[Mapping[str, object]],
    *,
    points_per_m: float = 0.0,
) -> tuple[WallBandCandidate, ...]:
    """Nominate double-face wall bands without granting wall authority.

    This reuses detect_wall_pairs as candidate generation only. Its confidence
    score and its unscaled fallback band are never consumed as evidence of
    physical-wall truth.
    """

    copied = [dict(segment) for segment in segments]
    by_id = {
        str(segment.get("id")): segment
        for segment in copied
        if segment.get("id") not in (None, "")
    }
    rows = detect_wall_pairs(
        copied,
        px_per_m=float(points_per_m or 0.0),
    )
    candidates: list[WallBandCandidate] = []
    for row in rows:
        left_id = str(row.get("face_a") or "").strip()
        right_id = str(row.get("face_b") or "").strip()
        if not left_id or not right_id or left_id == right_id:
            continue
        face_ids = tuple(sorted((left_id, right_id)))
        first = by_id.get(face_ids[0])
        second = by_id.get(face_ids[1])
        if first is None or second is None:
            continue
        gap = float(row.get("gap_pt") or 0.0)
        overlap = float(row.get("overlap_pt") or 0.0)
        if gap <= 0.0 or overlap <= 0.0:
            continue
        candidate_id = stable_contract_id(
            "wall_band_candidate",
            {
                "candidate_face_ids": face_ids,
                "separation_pt": round(gap, 6),
                "overlap_pt": round(overlap, 6),
            },
        )
        candidates.append(
            WallBandCandidate(
                candidate_id=candidate_id,
                candidate_face_ids=(face_ids[0], face_ids[1]),
                wall_band_geometry=_aligned_band_polygon(first, second),
                separation_pt=gap,
                overlap_pt=overlap,
            )
        )
    return tuple(
        sorted(
            candidates,
            key=lambda candidate: (
                candidate.candidate_face_ids,
                candidate.candidate_id,
            ),
        )
    )


def source_negative_reason_codes(
    segments: Sequence[Mapping[str, object]],
) -> tuple[str, ...]:
    """Translate existing source-role exclusions into typed shadow negatives."""

    reasons: set[str] = set()
    for segment in segments:
        _, source_reasons = is_structural_candidate_segment(dict(segment))
        for reason in source_reasons:
            if reason == "dimension_layer_excluded":
                reasons.add(NEGATIVE_DIMENSION_PATTERN_DETECTED)
            elif reason == "structural_grid_source_layer_excluded":
                reasons.add(NEGATIVE_STRUCTURAL_GRID_PATTERN_DETECTED)
            elif reason == "text_frame_layer_excluded":
                reasons.add(NEGATIVE_TITLE_BLOCK_OR_ANNOTATION_PATTERN_DETECTED)
            elif reason == "hatch_layer_excluded":
                reasons.add(NEGATIVE_ROOF_OR_FINISH_HATCH_PATTERN_DETECTED)
            elif reason == "explicit_non_wall_source_layer_excluded":
                reasons.add(NEGATIVE_EXPLICIT_NON_WALL_SOURCE_ROLE)
    return tuple(sorted(reasons))


def _build_record_id(
    *,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    page_id: str,
    viewport_id: Optional[str],
    view_scope_id: Optional[str],
    physical_wall_body_id: Optional[str],
    candidate_face_ids: tuple[str, ...],
    source_observation_ids: tuple[str, ...],
    thickness_family_id: Optional[str],
    topology_evidence_ids: tuple[str, ...],
    negative_evidence_ids: tuple[str, ...],
    status: EvidenceResolutionStatus,
    reason_codes: tuple[str, ...],
) -> str:
    return stable_contract_id(
        "physical_wall_body_shadow",
        {
            "schema_version": PHYSICAL_WALL_BODY_EVIDENCE_SHADOW_SCHEMA_VERSION,
            "document_id": document_id,
            "revision_id": revision_id,
            "source_sha256": source_sha256,
            "snapshot_id": snapshot_id,
            "page_id": page_id,
            "viewport_id": viewport_id,
            "view_scope_id": view_scope_id,
            "physical_wall_body_id": physical_wall_body_id,
            "candidate_face_ids": candidate_face_ids,
            "source_observation_ids": source_observation_ids,
            "thickness_family_id": thickness_family_id,
            "topology_evidence_ids": topology_evidence_ids,
            "negative_evidence_ids": negative_evidence_ids,
            "status": status,
            "reason_codes": reason_codes,
        },
    )


def resolve_physical_wall_body_evidence_shadow(
    *,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    page_id: str,
    viewport_id: Optional[str] = None,
    view_scope_id: Optional[str] = None,
    physical_wall_body_id: Optional[str] = None,
    candidate_face_ids: Sequence[str],
    source_observation_ids: Sequence[str],
    wall_band_geometry: Optional[Sequence[Sequence[float]]],
    thickness_family_id: Optional[str] = None,
    topology_evidence_ids: Sequence[str] = (),
    negative_evidence_ids: Sequence[str] = (),
    negative_reason_codes: Sequence[str] = (),
    segmentation_support_observation_ids: Sequence[str] = (),
    network_complete_for_scope: Optional[bool] = None,
    opening_local_topology_present: bool = False,
) -> PhysicalWallBodyEvidence:
    """Resolve one local wall-body proposition in SHADOW only.

    One-face candidates require segmentation support, a source-supported
    thickness family, and at least two independent topology witnesses.
    Two-face candidates require independent topology and a source-supported
    thickness family; segmentation may strengthen that proof but can never
    substitute for thickness evidence. Parallel faces alone can never
    corroborate. Any typed negative evidence blocks corroboration. Scope
    completeness is never minted here.
    """

    document_id = _clean_required(document_id, "document_id")
    revision_id = _clean_required(revision_id, "revision_id")
    source_sha256 = str(source_sha256 or "").strip().lower()
    if not _SHA256_RE.fullmatch(source_sha256):
        raise ValueError(
            "source_sha256 must be a 64-character lowercase SHA-256"
        )
    snapshot_id = _clean_required(snapshot_id, "snapshot_id")
    page_id = _clean_required(page_id, "page_id")
    viewport_id = _clean_optional(viewport_id)
    view_scope_id = _clean_optional(view_scope_id)
    physical_wall_body_id = _clean_optional(physical_wall_body_id)

    faces = _sorted_unique(candidate_face_ids)
    base_observations = _sorted_unique(source_observation_ids)
    segmentation_observations = _sorted_unique(
        segmentation_support_observation_ids
    )
    observations = _sorted_unique(
        base_observations + segmentation_observations
    )
    topology = _sorted_unique(topology_evidence_ids)
    negatives = _sorted_unique(negative_evidence_ids)
    negative_reasons = _sorted_unique(negative_reason_codes)
    thickness_family_id = _clean_optional(thickness_family_id)
    geometry = _finite_geometry(wall_band_geometry)

    reasons: list[str] = [PHYSICAL_WALL_BODY_SHADOW_ONLY]

    if len(faces) == 1:
        reasons.append(PHYSICAL_WALL_BODY_SINGLE_FACE_CANDIDATE)
    elif len(faces) == 2:
        reasons.append(PHYSICAL_WALL_BODY_PARALLEL_FACES_PRESENT)
    else:
        reasons.append(PHYSICAL_WALL_BODY_FACE_CARDINALITY_UNSUPPORTED)

    if topology:
        reasons.append(PHYSICAL_WALL_BODY_TOPOLOGY_CONTINUITY_PRESENT)
    if thickness_family_id is not None:
        reasons.append(PHYSICAL_WALL_BODY_THICKNESS_FAMILY_PRESENT)
    if segmentation_observations:
        reasons.append(PHYSICAL_WALL_BODY_SEGMENTATION_SUPPORT_PRESENT)
    elif len(faces) == 1:
        reasons.append(PHYSICAL_WALL_BODY_SEGMENTATION_SUPPORT_UNAVAILABLE)

    if opening_local_topology_present:
        reasons.append(OPENING_LOCAL_TOPOLOGY_PRESENT)

    if network_complete_for_scope is False:
        reasons.append(NETWORK_INCOMPLETE_FOR_SCOPE)

    status = EvidenceResolutionStatus.ABSTAINED

    if len(faces) not in (1, 2):
        reasons.append(PHYSICAL_WALL_BODY_EVIDENCE_INSUFFICIENT)
    elif not observations:
        reasons.extend(
            (
                PHYSICAL_WALL_BODY_SOURCE_PROVENANCE_INCOMPLETE,
                PHYSICAL_WALL_BODY_EVIDENCE_INSUFFICIENT,
            )
        )
    elif geometry is None:
        reasons.extend(
            (
                PHYSICAL_WALL_BODY_GEOMETRY_UNAVAILABLE,
                PHYSICAL_WALL_BODY_EVIDENCE_INSUFFICIENT,
            )
        )
    elif negatives or negative_reasons:
        reasons.append(PHYSICAL_WALL_BODY_NEGATIVE_EVIDENCE_BLOCKED)
        reasons.extend(negative_reasons)
    elif len(faces) == 1:
        if (
            segmentation_observations
            and thickness_family_id is not None
            and len(topology) >= 2
        ):
            status = EvidenceResolutionStatus.CORROBORATED
            reasons.append(PHYSICAL_WALL_BODY_CORROBORATED_LOCAL)
        else:
            reasons.append(PHYSICAL_WALL_BODY_EVIDENCE_INSUFFICIENT)
    else:
        has_strong_wall_body_proof = (
            bool(topology) and thickness_family_id is not None
        )
        if has_strong_wall_body_proof:
            status = EvidenceResolutionStatus.CORROBORATED
            reasons.append(PHYSICAL_WALL_BODY_CORROBORATED_LOCAL)
        else:
            reasons.extend(
                (
                    PHYSICAL_WALL_BODY_PARALLEL_FACES_WITHOUT_STRONG_SUPPORT,
                    PHYSICAL_WALL_BODY_EVIDENCE_INSUFFICIENT,
                )
            )

    reasons_tuple = _sorted_unique(reasons)
    record_id = _build_record_id(
        document_id=document_id,
        revision_id=revision_id,
        source_sha256=source_sha256,
        snapshot_id=snapshot_id,
        page_id=page_id,
        viewport_id=viewport_id,
        view_scope_id=view_scope_id,
        physical_wall_body_id=physical_wall_body_id,
        candidate_face_ids=faces,
        source_observation_ids=observations,
        thickness_family_id=thickness_family_id,
        topology_evidence_ids=topology,
        negative_evidence_ids=negatives,
        status=status,
        reason_codes=reasons_tuple,
    )
    return PhysicalWallBodyEvidence(
        record_id=record_id,
        document_id=document_id,
        revision_id=revision_id,
        source_sha256=source_sha256,
        snapshot_id=snapshot_id,
        page_id=page_id,
        viewport_id=viewport_id,
        view_scope_id=view_scope_id,
        physical_wall_body_id=physical_wall_body_id,
        candidate_face_ids=faces,
        source_observation_ids=observations,
        wall_band_geometry=geometry,
        thickness_family_id=thickness_family_id,
        topology_evidence_ids=topology,
        negative_evidence_ids=negatives,
        status=status,
        reason_codes=reasons_tuple,
    )
