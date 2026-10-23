"""Producer-owned source wall-thickness and paired wall faces shadow authority (Item 6).

Proves the authentic 2D paired face geometry and physical thickness for wall candidates:
- Evaluates parallel, overlapping source vector segments with strict geometric gates.
- Rejects negative drafting motifs (dimension ticks, grid lines, hatching strokes, furniture contours).
- Computes canonical medial centerline with stable Left / Right face identities invariant to coordinate reversal.
- Derives physical thickness in meters via authenticated scale or documented/figured dimensions.
- Rejects zero, negative, or out-of-range thicknesses.
- Detects conflicts between figured thickness and scaled linework gap.
- Serializes genuine standard OGC Well-Known Binary (WKB) hex geometry.
- Operates strictly in shadow mode with CANDIDATE status and non-commercial flags.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SOURCE_WALL_THICKNESS_SCHEMA_VERSION = "1.0.0"

# Public Reason Codes
PAIRED_WALL_FACES_RESOLVED = "paired_wall_faces_resolved"
PAIRED_WALL_FACES_UNRESOLVED = "paired_wall_faces_unresolved"
PAIRED_FACES_NON_PARALLEL = "paired_faces_non_parallel"
PAIRED_FACES_OVERLAP_INSUFFICIENT = "paired_faces_overlap_insufficient"
PAIRED_FACES_GAP_OUT_OF_RANGE = "paired_faces_gap_out_of_range"
NEGATIVE_DRAFTING_MOTIF_REJECTED = "negative_drafting_motif_rejected"
WALL_THICKNESS_ZERO_REJECTED = "wall_thickness_zero_rejected"
WALL_THICKNESS_NEGATIVE_REJECTED = "wall_thickness_negative_rejected"
WALL_THICKNESS_SCALE_UNRESOLVED = "wall_thickness_scale_unresolved"
WALL_THICKNESS_LINEAGE_MISMATCH = "wall_thickness_lineage_mismatch"
WALL_THICKNESS_CONFLICT = "wall_thickness_conflict"
WALL_THICKNESS_RECORD_UNAVAILABLE = "wall_thickness_record_unavailable"
DEGENERATE_SEGMENT_GEOMETRY = "degenerate_segment_geometry"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str]  # doc/rev/sha/snap/page/scope/wall_id


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


# ── Genuine OGC WKB Serialization ──────────────────────────────────────────────


def _linestring_to_wkb_hex(pts: Sequence[Tuple[float, float]]) -> str:
    """Encode 2D LineString into genuine standard OGC Well-Known Binary hex."""
    header = struct.pack("<BII", 1, 2, len(pts))
    coords = b"".join(struct.pack("<dd", float(x), float(y)) for x, y in pts)
    return (header + coords).hex()


def _polygon_to_wkb_hex(ring: Sequence[Tuple[float, float]]) -> str:
    """Encode 2D single-ring Polygon into genuine standard OGC Well-Known Binary hex."""
    pts = list(ring)
    if pts and (pts[0][0] != pts[-1][0] or pts[0][1] != pts[-1][1]):
        pts.append(pts[0])
    header = struct.pack("<BII", 1, 3, 1)
    body = struct.pack("<I", len(pts)) + b"".join(
        struct.pack("<dd", float(x), float(y)) for x, y in pts
    )
    return (header + body).hex()


# ── Data Contracts ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourcePairedWallFacesSelector:
    """Selector identifying the exact wall and context for paired face resolution."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    wall_candidate_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "wall_candidate_id",
        ):
            _required(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.decision_scope_id,
            self.wall_candidate_id,
        )


@dataclass(frozen=True)
class SourcePairedFaceGeometryRecord:
    """Sealed, authentic record proving paired wall faces and verified thickness."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    wall_candidate_id: str
    face_a_primitive_id: str
    face_b_primitive_id: str
    gap_pt: float
    thickness_m: Optional[float]
    thickness_mm: Optional[float]
    thickness_authority: str  # "PDF_SCALED", "DOCUMENTED_DIMENSION", or "PROVISIONAL"
    overlap_pt: float
    centerline_pts: Tuple[Tuple[float, float], ...]
    face_left_pts: Tuple[Tuple[float, float], ...]
    face_right_pts: Tuple[Tuple[float, float], ...]
    centerline_wkb_hex: str
    face_left_wkb_hex: str
    face_right_wkb_hex: str
    polygon_wkb_hex: str
    corroborating_evidence_ids: Tuple[str, ...]
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    schema_version: str = SOURCE_WALL_THICKNESS_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourcePairedFaceGeometryRecord is producer-owned and cannot be constructed directly")


@dataclass(frozen=True)
class SourceWallThicknessPairedFacesResult:
    """Resolution result for source wall thickness and paired faces."""

    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[SourcePairedFaceGeometryRecord] = None
    schema_version: str = SOURCE_WALL_THICKNESS_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> SourceWallThicknessPairedFacesResult:
    return SourceWallThicknessPairedFacesResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


def _conflict(reason: str, *extras: str) -> SourceWallThicknessPairedFacesResult:
    return SourceWallThicknessPairedFacesResult(
        status=EvidenceResolutionStatus.CONFLICT,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


# ── Geometric Analysis ────────────────────────────────────────────────────────


def _extract_endpoints(seg: Mapping[str, Any]) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
    """Extract (x1, y1), (x2, y2) from segment mapping."""
    if "p1" in seg and "p2" in seg:
        p1, p2 = seg["p1"], seg["p2"]
        return ((float(p1[0]), float(p1[1])), (float(p2[0]), float(p2[1])))
    if "x1" in seg and "y1" in seg and "x2" in seg and "y2" in seg:
        return ((float(seg["x1"]), float(seg["y1"])), (float(seg["x2"]), float(seg["y2"])))
    if "points" in seg:
        pts = seg["points"]
        if len(pts) >= 2:
            return ((float(pts[0][0]), float(pts[0][1])), (float(pts[-1][0]), float(pts[-1][1])))
    return None


def _evaluate_paired_geometry(
    pts_a: Tuple[Tuple[float, float], Tuple[float, float]],
    pts_b: Tuple[Tuple[float, float], Tuple[float, float]],
) -> Tuple[Optional[float], Optional[float], Optional[Tuple[Tuple[float, float], ...]], Optional[str]]:
    """Evaluate parallelism, gap, overlap, and canonical centerline.

    Returns:
        (gap_pt, overlap_pt, canonical_centerline_pts, error_code)
    """
    (p1_x, p1_y), (p2_x, p2_y) = pts_a
    (q1_x, q1_y), (q2_x, q2_y) = pts_b

    dx_a = p2_x - p1_x
    dy_a = p2_y - p1_y
    len_a = math.hypot(dx_a, dy_a)

    dx_b = q2_x - q1_x
    dy_b = q2_y - q1_y
    len_b = math.hypot(dx_b, dy_b)

    if len_a < 1e-4 or len_b < 1e-4:
        return None, None, None, DEGENERATE_SEGMENT_GEOMETRY

    u_ax = dx_a / len_a
    u_ay = dy_a / len_a
    n_ax = -u_ay
    n_ay = u_ax

    u_bx = dx_b / len_b
    u_by = dy_b / len_b

    # Parallelism: normalized cross product
    cross = u_ax * u_by - u_ay * u_bx
    dot = u_ax * u_bx + u_ay * u_by

    if abs(cross) > 0.035:  # ~2.0 degrees
        return None, None, None, PAIRED_FACES_NON_PARALLEL

    # Align B's direction with A for projection
    if dot < 0:
        q1_x, q2_x = q2_x, q1_x
        q1_y, q2_y = q2_y, q1_y

    # Perpendicular gap
    d1 = (q1_x - p1_x) * n_ax + (q1_y - p1_y) * n_ay
    d2 = (q2_x - p1_x) * n_ax + (q2_y - p1_y) * n_ay

    if abs(abs(d1) - abs(d2)) > 2.0:  # non-uniform gap exceeding tolerance
        return None, None, None, PAIRED_FACES_NON_PARALLEL

    gap_pt = (abs(d1) + abs(d2)) / 2.0
    sign_gap = 1.0 if (d1 + d2) >= 0 else -1.0

    # Projection along A
    t_b1 = (q1_x - p1_x) * u_ax + (q1_y - p1_y) * u_ay
    t_b2 = (q2_x - p1_x) * u_ax + (q2_y - p1_y) * u_ay
    t_b_min = min(t_b1, t_b2)
    t_b_max = max(t_b1, t_b2)

    t_start = max(0.0, t_b_min)
    t_end = min(len_a, t_b_max)
    overlap_pt = max(0.0, t_end - t_start)

    min_required_overlap = min(len_a, len_b) * 0.45
    if overlap_pt < min_required_overlap or overlap_pt < 12.0:
        return None, None, None, PAIRED_FACES_OVERLAP_INSUFFICIENT

    # Centerline calculation
    offset_dist = sign_gap * (gap_pt / 2.0)
    c1_x = p1_x + t_start * u_ax + offset_dist * n_ax
    c1_y = p1_y + t_start * u_ay + offset_dist * n_ay
    c2_x = p1_x + t_end * u_ax + offset_dist * n_ax
    c2_y = p1_y + t_end * u_ay + offset_dist * n_ay

    # Canonical order: lexicographically ordered endpoints
    c1 = (c1_x, c1_y)
    c2 = (c2_x, c2_y)
    if c1 > c2:
        c1, c2 = c2, c1

    return gap_pt, overlap_pt, (c1, c2), None


# ── Authority & Producer ──────────────────────────────────────────────────────


class SourceWallThicknessPairedFacesAuthority:
    """Sealed lookup authority for published paired wall face records."""

    def __init__(
        self,
        records: Mapping[_Key, SourceWallThicknessPairedFacesResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("SourceWallThicknessPairedFacesAuthority is producer-owned and cannot be constructed directly")
        self._records = MappingProxyType(dict(records))

    def resolve(self, selector: SourcePairedWallFacesSelector) -> SourceWallThicknessPairedFacesResult:
        if type(selector) is not SourcePairedWallFacesSelector:
            raise TypeError("selector must be SourcePairedWallFacesSelector")
        return self._records.get(selector.key, _abstained(WALL_THICKNESS_RECORD_UNAVAILABLE))


class SourceWallThicknessPairedFacesProducer:
    """Producer for authenticating source wall thickness and paired faces."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("SourceWallThicknessPairedFacesProducer must be obtained via create()")
        self._results: Dict[_Key, SourceWallThicknessPairedFacesResult] = {}

    @classmethod
    def create(cls) -> SourceWallThicknessPairedFacesProducer:
        return cls(_seal=_PRODUCER_SEAL)

    def evaluate_and_publish(
        self,
        selector: SourcePairedWallFacesSelector,
        segment_a: Mapping[str, Any],
        segment_b: Mapping[str, Any],
        *,
        scale_px_per_m: Optional[float] = None,
        figured_thickness_m: Optional[float] = None,
        negative_motif_ids: Optional[Set[str]] = None,
    ) -> SourceWallThicknessPairedFacesResult:
        """Evaluate two source segments, verify gates, and publish authentic record."""
        if type(selector) is not SourcePairedWallFacesSelector:
            raise TypeError("selector must be SourcePairedWallFacesSelector")

        id_a = str(segment_a.get("id") or segment_a.get("source_primitive_id") or "")
        id_b = str(segment_b.get("id") or segment_b.get("source_primitive_id") or "")

        # 1. Negative drafting motif rejection
        neg_ids = set(negative_motif_ids or ())
        if (id_a and id_a in neg_ids) or (id_b and id_b in neg_ids):
            res = _abstained(NEGATIVE_DRAFTING_MOTIF_REJECTED)
            self._results[selector.key] = res
            return res

        # 2. Extract endpoints
        pts_a = _extract_endpoints(segment_a)
        pts_b = _extract_endpoints(segment_b)
        if not pts_a or not pts_b:
            res = _abstained(DEGENERATE_SEGMENT_GEOMETRY)
            self._results[selector.key] = res
            return res

        # 3. Geometric pairing evaluation
        gap_pt, overlap_pt, centerline_pts, err = _evaluate_paired_geometry(pts_a, pts_b)
        if err or gap_pt is None or overlap_pt is None or centerline_pts is None:
            res = _abstained(err or PAIRED_WALL_FACES_UNRESOLVED)
            self._results[selector.key] = res
            return res

        # 4. Gap bounds gate
        if scale_px_per_m is not None and scale_px_per_m > 0:
            calibrated_thickness_m = gap_pt / scale_px_per_m
            if calibrated_thickness_m <= 0:
                res = _abstained(WALL_THICKNESS_ZERO_REJECTED)
                self._results[selector.key] = res
                return res
            if not (0.04 <= calibrated_thickness_m <= 0.45):
                res = _abstained(PAIRED_FACES_GAP_OUT_OF_RANGE)
                self._results[selector.key] = res
                return res
        else:
            calibrated_thickness_m = None
            if not (0.8 <= gap_pt <= 18.0):
                res = _abstained(PAIRED_FACES_GAP_OUT_OF_RANGE)
                self._results[selector.key] = res
                return res

        # 5. Figured thickness evaluation and cross-check
        thickness_m: Optional[float] = None
        thickness_mm: Optional[float] = None
        thickness_auth = "PROVISIONAL"

        if figured_thickness_m is not None:
            if figured_thickness_m <= 0:
                res = _abstained(WALL_THICKNESS_ZERO_REJECTED)
                self._results[selector.key] = res
                return res
            if calibrated_thickness_m is not None:
                diff = abs(figured_thickness_m - calibrated_thickness_m)
                if diff > 0.02 and (diff / figured_thickness_m) > 0.15:
                    res = _conflict(WALL_THICKNESS_CONFLICT)
                    self._results[selector.key] = res
                    return res
            thickness_m = round(figured_thickness_m, 4)
            thickness_mm = round(figured_thickness_m * 1000.0, 1)
            thickness_auth = "DOCUMENTED_DIMENSION"
        elif calibrated_thickness_m is not None:
            thickness_m = round(calibrated_thickness_m, 4)
            thickness_mm = round(calibrated_thickness_m * 1000.0, 1)
            thickness_auth = "PDF_SCALED"

        # 6. Canonical Left & Right faces
        (c1_x, c1_y), (c2_x, c2_y) = centerline_pts
        cdx = c2_x - c1_x
        cdy = c2_y - c1_y
        clen = math.hypot(cdx, cdy)
        if clen < 1e-4:
            res = _abstained(DEGENERATE_SEGMENT_GEOMETRY)
            self._results[selector.key] = res
            return res

        cu_x = cdx / clen
        cu_y = cdy / clen
        cn_x = -cu_y
        cn_y = cu_x

        half_gap = gap_pt / 2.0
        # Left face: offset along +normal
        fl1 = (c1_x + half_gap * cn_x, c1_y + half_gap * cn_y)
        fl2 = (c2_x + half_gap * cn_x, c2_y + half_gap * cn_y)
        # Right face: offset along -normal
        fr1 = (c1_x - half_gap * cn_x, c1_y - half_gap * cn_y)
        fr2 = (c2_x - half_gap * cn_x, c2_y - half_gap * cn_y)

        face_left_pts = (fl1, fl2)
        face_right_pts = (fr1, fr2)
        polygon_pts = (fl1, fl2, fr2, fr1, fl1)

        # 7. Serialise to standard OGC WKB hex
        centerline_wkb = _linestring_to_wkb_hex(centerline_pts)
        face_left_wkb = _linestring_to_wkb_hex(face_left_pts)
        face_right_wkb = _linestring_to_wkb_hex(face_right_pts)
        poly_wkb = _polygon_to_wkb_hex(polygon_pts)

        # 8. Mint stable contract ID
        rec_id = stable_contract_id(
            "source_paired_face_record",
            {
                "document_id": selector.document_id,
                "revision_id": selector.revision_id,
                "source_sha256": selector.source_sha256,
                "snapshot_id": selector.snapshot_id,
                "page_id": selector.page_id,
                "wall_candidate_id": selector.wall_candidate_id,
                "face_a_primitive_id": id_a,
                "face_b_primitive_id": id_b,
            },
        )

        record = SourcePairedFaceGeometryRecord(
            record_id=rec_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            wall_candidate_id=selector.wall_candidate_id,
            face_a_primitive_id=id_a,
            face_b_primitive_id=id_b,
            gap_pt=round(gap_pt, 4),
            thickness_m=thickness_m,
            thickness_mm=thickness_mm,
            thickness_authority=thickness_auth,
            overlap_pt=round(overlap_pt, 4),
            centerline_pts=centerline_pts,
            face_left_pts=face_left_pts,
            face_right_pts=face_right_pts,
            centerline_wkb_hex=centerline_wkb,
            face_left_wkb_hex=face_left_wkb,
            face_right_wkb_hex=face_right_wkb,
            polygon_wkb_hex=poly_wkb,
            corroborating_evidence_ids=tuple(sorted([id_a, id_b])),
            status=EvidenceResolutionStatus.CANDIDATE,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_RECORD_SEAL,
        )

        res = SourceWallThicknessPairedFacesResult(
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=(PAIRED_WALL_FACES_RESOLVED,),
            record=record,
        )
        self._results[selector.key] = res
        return res

    def authority(self) -> SourceWallThicknessPairedFacesAuthority:
        return SourceWallThicknessPairedFacesAuthority(self._results, _seal=_AUTHORITY_SEAL)
