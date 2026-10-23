"""Producer-owned source drafting motif negative evidence shadow authority (Items 5 & 28).

Classifies non-wall drafting linework that contaminates wall topology networks:
- Dimension marks and ticks: short stubs (<= 15 pt) at 45 degrees or witness terminations.
- Grid lines: long thin strokes (length >= 200 pt, width < 0.6 pt) spanning without paired face partners.
- Hatch strokes: dense parallel stroke arrays (>= 4 strokes, pitch <= 15 pt).
- Furniture and fixtures: compact closed loops (perimeter < 250 pt, bbox area < 4000 sq pt).
- Strictly protects verified paired wall faces and structural wall runs from negative classification.
- Strictly non-publishing in shadow mode (status=CANDIDATE, commercial_projection_allowed=False,
  takeoff_eligible=False).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
import math
import re
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"

# Public Reason Codes
SOURCE_DRAFTING_MOTIF_RESOLVED = "source_drafting_motif_resolved"
SOURCE_DRAFTING_MOTIF_CANDIDATE = "source_drafting_motif_candidate"
SOURCE_DRAFTING_MOTIF_UNAVAILABLE = "source_drafting_motif_unavailable"
SOURCE_LINEAGE_MISMATCH = "source_lineage_mismatch"
EMPTY_CANDIDATE_SEGMENTS = "empty_candidate_segments"

# Subtype Constants
SUBTYPE_STRUCTURAL_WALL_RUN = "structural_wall_run"
SUBTYPE_DIMENSION_TICK = "dimension_tick"
SUBTYPE_GRID_LINE = "grid_line"
SUBTYPE_HATCH_STROKE = "hatch_stroke"
SUBTYPE_FURNITURE_FIXTURE = "furniture_fixture"
SUBTYPE_UNPROVEN_DRAFTING_INK = "unproven_drafting_ink"

_RECORD_SEAL = object()


def _clean(val: Any) -> str:
    return str(val or "").strip()


def _point(val: Any) -> tuple[float, float] | None:
    if type(val) not in (tuple, list) or len(val) != 2:
        return None
    try:
        x, y = float(val[0]), float(val[1])
    except (TypeError, ValueError, OverflowError):
        return None
    if not (math.isfinite(x) and math.isfinite(y)):
        return None
    return (x, y)


def _distance(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


@dataclass(frozen=True)
class SourceDraftingMotifSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
        ):
            val = getattr(self, name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"Selector field {name} must be non-empty string")
        sha = self.source_sha256.lower()
        if len(sha) != 64 or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("source_sha256 must be a 64-char lowercase hex string")


@dataclass(frozen=True)
class SourceDraftingSegment:
    primitive_id: str
    start_pt: tuple[float, float]
    end_pt: tuple[float, float]
    stroke_width: float = 1.0
    path_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.primitive_id, str) or not self.primitive_id.strip():
            raise ValueError("primitive_id must be non-empty string")
        p1 = _point(self.start_pt)
        p2 = _point(self.end_pt)
        if p1 is None or p2 is None:
            raise ValueError("start_pt and end_pt must be valid coordinates")
        if _distance(p1, p2) <= 1e-6:
            raise ValueError("Segment points must be distinct")


@dataclass(frozen=True)
class SourceDraftingMotifVerdict:
    primitive_id: str
    classification: str
    subtype: str
    reason: str


@dataclass(frozen=True)
class SourceDraftingMotifRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    verdicts: tuple[SourceDraftingMotifVerdict, ...]
    dimension_tick_count: int
    grid_line_count: int
    hatch_stroke_count: int
    furniture_fixture_count: int
    structural_wall_run_count: int
    unproven_count: int
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    reason_codes: tuple[str, ...] = (SOURCE_DRAFTING_MOTIF_CANDIDATE,)
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    diagnostic_only: bool = True
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourceDraftingMotifRecord is producer-owned")


@dataclass(frozen=True)
class SourceDraftingMotifResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: SourceDraftingMotifRecord | None = None
    selector: SourceDraftingMotifSelector | None = None
    schema_version: str = SCHEMA_VERSION


def _segment_length(seg: SourceDraftingSegment) -> float:
    return _distance(seg.start_pt, seg.end_pt)


def _segment_angle_deg(seg: SourceDraftingSegment) -> float:
    dx = seg.end_pt[0] - seg.start_pt[0]
    dy = seg.end_pt[1] - seg.start_pt[1]
    angle = math.degrees(math.atan2(abs(dy), abs(dx)))
    return angle


def _is_parallel_and_nearby(
    s1: SourceDraftingSegment,
    s2: SourceDraftingSegment,
    *,
    angle_tol_deg: float = 5.0,
    max_dist_pt: float = 30.0,
) -> bool:
    a1 = _segment_angle_deg(s1)
    a2 = _segment_angle_deg(s2)
    if abs(a1 - a2) > angle_tol_deg and abs(abs(a1 - a2) - 180.0) > angle_tol_deg:
        return False
    # Check perpendicular distance between midpoints
    m1 = ((s1.start_pt[0] + s1.end_pt[0]) * 0.5, (s1.start_pt[1] + s1.end_pt[1]) * 0.5)
    m2 = ((s2.start_pt[0] + s2.end_pt[0]) * 0.5, (s2.start_pt[1] + s2.end_pt[1]) * 0.5)
    return _distance(m1, m2) <= max_dist_pt


def evaluate_source_drafting_motif_negative_evidence_shadow(
    selector: SourceDraftingMotifSelector,
    *,
    candidate_segments: Sequence[SourceDraftingSegment],
    known_wall_primitive_ids: Sequence[str] = (),
) -> SourceDraftingMotifResult:
    """Classify candidate segments as structural wall linework vs negative drafting motifs."""
    if not isinstance(selector, SourceDraftingMotifSelector):
        return SourceDraftingMotifResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_LINEAGE_MISMATCH,),
        )

    if not candidate_segments:
        return SourceDraftingMotifResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(EMPTY_CANDIDATE_SEGMENTS,),
            selector=selector,
        )

    protected_wall_ids = frozenset(str(x).strip() for x in known_wall_primitive_ids if str(x).strip())

    # Pre-index paths for loop/fixture analysis
    segments_by_path: dict[str, list[SourceDraftingSegment]] = defaultdict(list)
    for seg in candidate_segments:
        if seg.path_id:
            segments_by_path[seg.path_id].append(seg)

    path_is_furniture_fixture: dict[str, bool] = {}
    for path_id, path_segs in segments_by_path.items():
        if len(path_segs) >= 3:
            # Check closed loop perimeter and bbox
            total_len = sum(_segment_length(s) for s in path_segs)
            all_x = [s.start_pt[0] for s in path_segs] + [s.end_pt[0] for s in path_segs]
            all_y = [s.start_pt[1] for s in path_segs] + [s.end_pt[1] for s in path_segs]
            bbox_w = max(all_x) - min(all_x)
            bbox_h = max(all_y) - min(all_y)
            bbox_area = bbox_w * bbox_h
            if total_len < 250.0 and bbox_area < 4000.0 and bbox_area > 1.0:
                # Small closed component characteristic of fixture or symbol
                path_is_furniture_fixture[path_id] = True

    # Check for hatch clusters: group segments by angle bucket and check pitch
    angle_buckets: dict[int, list[SourceDraftingSegment]] = defaultdict(list)
    for seg in candidate_segments:
        ang = int(round(_segment_angle_deg(seg)))
        angle_buckets[ang].append(seg)

    hatch_primitive_ids: set[str] = set()
    for ang, group in angle_buckets.items():
        if len(group) >= 4:
            # Check if lengths are similar and spacing is regular
            lens = [_segment_length(s) for s in group]
            avg_len = sum(lens) / len(lens)
            if all(abs(l - avg_len) < 0.35 * avg_len for l in lens):
                # Sort along perpendicular direction
                # Radian angle
                rad = math.radians(ang)
                perp_dx, perp_dy = -math.sin(rad), math.cos(rad)
                projections = [
                    (s.start_pt[0] * perp_dx + s.start_pt[1] * perp_dy, s)
                    for s in group
                ]
                projections.sort(key=lambda item: item[0])
                diffs = [
                    projections[i + 1][0] - projections[i][0]
                    for i in range(len(projections) - 1)
                ]
                if diffs and all(0.5 <= d <= 15.0 for d in diffs):
                    for _, s in projections:
                        hatch_primitive_ids.add(s.primitive_id)

    verdicts: list[SourceDraftingMotifVerdict] = []
    dim_tick_count = 0
    grid_count = 0
    hatch_count = 0
    fixture_count = 0
    wall_run_count = 0
    unproven_count = 0

    for seg in candidate_segments:
        pid = seg.primitive_id

        # 1. Protected wall primitive check
        if pid in protected_wall_ids:
            verdicts.append(
                SourceDraftingMotifVerdict(
                    primitive_id=pid,
                    classification="STRUCTURAL_WALL_CANDIDATE",
                    subtype=SUBTYPE_STRUCTURAL_WALL_RUN,
                    reason="protected_wall_face_or_boundary_edge",
                )
            )
            wall_run_count += 1
            continue

        length = _segment_length(seg)
        angle = _segment_angle_deg(seg)

        # 2. Dimension tick check (<= 15 pt, angled ~45 deg)
        if length <= 15.0 and (abs(angle - 45.0) <= 12.0 or abs(angle - 135.0) <= 12.0):
            verdicts.append(
                SourceDraftingMotifVerdict(
                    primitive_id=pid,
                    classification="NOT_WALL_DRAFTING_MOTIF",
                    subtype=SUBTYPE_DIMENSION_TICK,
                    reason="angled_short_dimension_tick_family",
                )
            )
            dim_tick_count += 1
            continue

        # 3. Hatch stroke check
        if pid in hatch_primitive_ids:
            verdicts.append(
                SourceDraftingMotifVerdict(
                    primitive_id=pid,
                    classification="NOT_WALL_DRAFTING_MOTIF",
                    subtype=SUBTYPE_HATCH_STROKE,
                    reason="repeated_parallel_hatch_array",
                )
            )
            hatch_count += 1
            continue

        # 4. Furniture and fixture loop check
        if seg.path_id and path_is_furniture_fixture.get(seg.path_id, False):
            verdicts.append(
                SourceDraftingMotifVerdict(
                    primitive_id=pid,
                    classification="NOT_WALL_DRAFTING_MOTIF",
                    subtype=SUBTYPE_FURNITURE_FIXTURE,
                    reason="compact_closed_fixture_or_symbol_loop",
                )
            )
            fixture_count += 1
            continue

        # 5. Grid line check: long thin line without parallel partner
        if length >= 200.0 and seg.stroke_width < 0.6:
            # Check if there is any parallel partner within 30 pt
            has_partner = any(
                other.primitive_id != pid and _is_parallel_and_nearby(seg, other, max_dist_pt=30.0)
                for other in candidate_segments
            )
            if not has_partner:
                verdicts.append(
                    SourceDraftingMotifVerdict(
                        primitive_id=pid,
                        classification="NOT_WALL_DRAFTING_MOTIF",
                        subtype=SUBTYPE_GRID_LINE,
                        reason="long_thin_isolated_grid_line",
                    )
                )
                grid_count += 1
                continue

        # 6. Unproven drafting ink (retained fail-closed)
        verdicts.append(
            SourceDraftingMotifVerdict(
                primitive_id=pid,
                classification="UNPROVEN",
                subtype=SUBTYPE_UNPROVEN_DRAFTING_INK,
                reason="unproven_drafting_ink_retained",
            )
        )
        unproven_count += 1

    verdict_tuple = tuple(verdicts)
    record_id = stable_contract_id(
        "source_drafting_motif_negative_evidence",
        {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "verdict_ids": [v.primitive_id for v in verdict_tuple],
            "subtypes": [v.subtype for v in verdict_tuple],
        },
        digest_chars=32,
    )

    record = SourceDraftingMotifRecord(
        record_id=record_id,
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        page_id=selector.page_id,
        verdicts=verdict_tuple,
        dimension_tick_count=dim_tick_count,
        grid_line_count=grid_count,
        hatch_stroke_count=hatch_count,
        furniture_fixture_count=fixture_count,
        structural_wall_run_count=wall_run_count,
        unproven_count=unproven_count,
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(
            SOURCE_DRAFTING_MOTIF_RESOLVED,
            SOURCE_DRAFTING_MOTIF_CANDIDATE,
        ),
        schema_version=SCHEMA_VERSION,
        commercial_projection_allowed=False,
        takeoff_eligible=False,
        diagnostic_only=True,
        _seal=_RECORD_SEAL,
    )

    return SourceDraftingMotifResult(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=(
            SOURCE_DRAFTING_MOTIF_RESOLVED,
            SOURCE_DRAFTING_MOTIF_CANDIDATE,
        ),
        record=record,
        selector=selector,
    )
