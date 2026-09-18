"""Producer-owned wall-thickness and authentic face-geometry authority (Item 27).

Proves the 2D physical face geometry and thickness for an exact physical wall:
- Thickness derives strictly from source-backed evidence (figured dimension,
  wall detail, section, or dimension-chain binding) bound to the exact wall.
- Prohibits treating candidate `thickness_m` or caller thickness as authority.
- Prohibits default thicknesses (90/110/150/200/230mm) without explicit source proof.
- Rejects zero or negative thickness.
- Multi-segment bent walls are correctly offset segment-by-segment with local
  junction miter orientation, not using the first segment's normal.
- Stable physical face identity: reversing coordinate ordering does not silently
  swap authoritative left and right face identities.
- Genuine binary OGC Well-Known Binary (WKB) serialization (not text-encoded WKT).
- Fails closed on stale lineage, scale uncorroborated, or conflicting dimensions.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from types import MappingProxyType
from typing import Dict, List, Mapping, Optional, Sequence, Set, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_physical_scale_authority import (
    PhysicalScaleAuthority,
    PhysicalScaleSelector,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)

WALL_THICKNESS_FACE_SCHEMA_VERSION = "1.0.0"

# Public reason codes
WALL_THICKNESS_FACE_RESOLVED = "wall_thickness_face_resolved"
WALL_THICKNESS_UNRESOLVED = "wall_thickness_unresolved"
WALL_THICKNESS_WALL_UNRESOLVED = "wall_thickness_wall_candidate_unresolved"
WALL_THICKNESS_SCALE_UNRESOLVED = "wall_thickness_scale_unresolved"
WALL_THICKNESS_LINEAGE_MISMATCH = "wall_thickness_lineage_mismatch"
WALL_THICKNESS_STALE_EVIDENCE = "wall_thickness_stale_evidence"
WALL_THICKNESS_GEOMETRY_UNAVAILABLE = "wall_thickness_geometry_unavailable"
WALL_THICKNESS_RECORD_UNAVAILABLE = "wall_thickness_record_unavailable"
WALL_THICKNESS_GEOMETRY_INVALID = "wall_thickness_geometry_invalid"
WALL_THICKNESS_CANDIDATE_REJECTED = "wall_thickness_candidate_thickness_rejected"
WALL_THICKNESS_DEFAULT_REJECTED = "wall_thickness_default_rejected"
WALL_THICKNESS_WRONG_WALL = "wall_thickness_wrong_wall"
WALL_THICKNESS_CONFLICT = "wall_thickness_conflict"
WALL_THICKNESS_ZERO_REJECTED = "wall_thickness_zero_rejected"
WALL_THICKNESS_NEGATIVE_REJECTED = "wall_thickness_negative_rejected"
WALL_THICKNESS_FACE_IDENTITY_UNSTABLE = "wall_thickness_face_identity_unstable"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str]  # doc/rev/sha/snap/page/scope/wall_id
_EvidenceKey = Tuple[str, str, str, str, str, str]  # doc/rev/sha/snap/page/wall_id


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _line_length(pts: Sequence[Tuple[float, float]]) -> float:
    total = 0.0
    for i in range(len(pts) - 1):
        x1, y1 = pts[i]
        x2, y2 = pts[i + 1]
        total += math.hypot(x2 - x1, y2 - y1)
    return total


# ── Genuine OGC WKB Serialization ──────────────────────────────────────────────


def _linestring_to_wkb_hex(pts: Sequence[Tuple[float, float]]) -> str:
    """Encode 2D LineString into genuine standard OGC Well-Known Binary hex."""
    # 1 byte byte-order (1 = little-endian)
    # uint32 geom-type (2 = LineString)
    # uint32 count
    # count * 2 doubles (x, y)
    header = struct.pack("<BII", 1, 2, len(pts))
    coords = b"".join(struct.pack("<dd", float(x), float(y)) for x, y in pts)
    return (header + coords).hex()


def _polygon_to_wkb_hex(ring: Sequence[Tuple[float, float]]) -> str:
    """Encode 2D single-ring Polygon into genuine standard OGC Well-Known Binary hex."""
    # 1 byte byte-order (1 = little-endian)
    # uint32 geom-type (3 = Polygon)
    # uint32 num_rings (1)
    # uint32 ring_count
    # ring_count * 2 doubles (x, y)
    pts = list(ring)
    if pts and (pts[0][0] != pts[-1][0] or pts[0][1] != pts[-1][1]):
        pts.append(pts[0])
    header = struct.pack("<BII", 1, 3, 1)
    body = struct.pack("<I", len(pts)) + b"".join(
        struct.pack("<dd", float(x), float(y)) for x, y in pts
    )
    return (header + body).hex()


# ── Multi-Segment Polyline Offset with Junction Mitering ───────────────────────


def _compute_multi_segment_offset(
    pts: Sequence[Tuple[float, float]],
    offset_dist: float,
) -> Tuple[Tuple[float, float], ...]:
    """Offset a multi-segment polyline with local segment orientation and junction mitering."""
    n = len(pts)
    if n < 2:
        return tuple(pts)

    tangents: List[Tuple[float, float]] = []
    normals: List[Tuple[float, float]] = []
    for i in range(n - 1):
        dx = pts[i + 1][0] - pts[i][0]
        dy = pts[i + 1][1] - pts[i][1]
        length = math.hypot(dx, dy)
        if length < 1e-12:
            continue
        tx = dx / length
        ty = dy / length
        tangents.append((tx, ty))
        normals.append((-ty, tx))

    if not tangents:
        return tuple(pts)

    num_segs = len(tangents)
    offset_pts: List[Tuple[float, float]] = []

    # Start point: offset along first segment normal
    offset_pts.append((
        pts[0][0] + offset_dist * normals[0][0],
        pts[0][1] + offset_dist * normals[0][1],
    ))

    # Intermediate junction vertices
    for i in range(1, num_segs):
        t_prev = tangents[i - 1]
        t_curr = tangents[i]
        n_prev = normals[i - 1]
        n_curr = normals[i]

        cross = t_prev[0] * t_curr[1] - t_prev[1] * t_curr[0]
        dot = t_prev[0] * t_curr[0] + t_prev[1] * t_curr[1]

        if abs(cross) < 1e-9 and dot > 0:
            # Collinear continuation in same direction
            offset_pts.append((
                pts[i][0] + offset_dist * n_curr[0],
                pts[i][1] + offset_dist * n_curr[1],
            ))
        elif abs(cross) > 1e-9:
            # Lines intersect at miter point
            diff_x = offset_dist * (n_curr[0] - n_prev[0])
            diff_y = offset_dist * (n_curr[1] - n_prev[1])
            diff_cross = diff_x * t_curr[1] - diff_y * t_curr[0]
            s = diff_cross / cross

            max_miter = 4.0 * abs(offset_dist)
            if abs(s) <= max_miter:
                ix = pts[i][0] + offset_dist * n_prev[0] + s * t_prev[0]
                iy = pts[i][1] + offset_dist * n_prev[1] + s * t_prev[1]
                offset_pts.append((ix, iy))
            else:
                # Clamp extreme miter spike
                avg_n_x = n_prev[0] + n_curr[0]
                avg_n_y = n_prev[1] + n_curr[1]
                avg_len = math.hypot(avg_n_x, avg_n_y)
                if avg_len > 1e-9:
                    offset_pts.append((
                        pts[i][0] + offset_dist * (avg_n_x / avg_len),
                        pts[i][1] + offset_dist * (avg_n_y / avg_len),
                    ))
                else:
                    offset_pts.append((
                        pts[i][0] + offset_dist * n_curr[0],
                        pts[i][1] + offset_dist * n_curr[1],
                    ))
        else:
            offset_pts.append((
                pts[i][0] + offset_dist * n_curr[0],
                pts[i][1] + offset_dist * n_curr[1],
            ))

    # End point: offset along last segment normal
    offset_pts.append((
        pts[-1][0] + offset_dist * normals[-1][0],
        pts[-1][1] + offset_dist * normals[-1][1],
    ))
    return tuple(offset_pts)


def _is_canonical_direction(pts: Sequence[Tuple[float, float]]) -> Optional[bool]:
    """Determine whether a polyline runs in canonical physical forward direction."""
    n = len(pts)
    for i in range(n):
        p_start = (pts[i][0], pts[i][1])
        p_end = (pts[n - 1 - i][0], pts[n - 1 - i][1])
        if p_start < p_end:
            return True
        if p_start > p_end:
            return False
    return None


# ── Selectors, Evidence, and Records ──────────────────────────────────────────


@dataclass(frozen=True)
class WallThicknessFaceSelector:
    """Sealed selector identifying the exact wall and context for thickness resolution."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "physical_wall_id",
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
            self.physical_wall_id,
        )


@dataclass(frozen=True)
class WallThicknessEvidence:
    """Producer-owned source-backed evidence of physical wall thickness.

    Derived only from source-backed dimension, wall detail, section,
    or exact dimension-chain binding.
    """

    evidence_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    physical_wall_id: str
    thickness_m: float
    source_kind: str  # "figured_dimension", "wall_detail", "section", "dimension_chain"
    is_default: bool = False
    schema_version: str = WALL_THICKNESS_FACE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "physical_wall_id",
            "source_kind",
        ):
            _required(getattr(self, name), name)


class WallThicknessAuthority:
    """Sealed lookup authority for wall thickness evidence."""

    def __init__(
        self,
        records: Mapping[_EvidenceKey, WallThicknessEvidence],
        conflicts: Optional[Set[_EvidenceKey]] = None,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallThicknessAuthority is producer-owned and cannot be constructed directly")
        self._records = MappingProxyType(dict(records))
        self._conflicts = frozenset(conflicts or ())

    def is_conflict(self, selector: WallThicknessFaceSelector) -> bool:
        key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
            selector.physical_wall_id,
        )
        return key in self._conflicts

    def get_evidence(self, selector: WallThicknessFaceSelector) -> Optional[WallThicknessEvidence]:
        key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
            selector.physical_wall_id,
        )
        return self._records.get(key)


class WallThicknessProducer:
    """Producer for authenticated wall thickness evidence."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("WallThicknessProducer must be obtained via create()")
        self._records: Dict[_EvidenceKey, WallThicknessEvidence] = {}
        self._conflicts: Set[_EvidenceKey] = set()

    @classmethod
    def create(cls) -> WallThicknessProducer:
        return cls(_seal=_PRODUCER_SEAL)

    def publish(self, evidence: WallThicknessEvidence) -> None:
        if type(evidence) is not WallThicknessEvidence:
            raise TypeError("evidence must be WallThicknessEvidence")
        key = (
            evidence.document_id,
            evidence.revision_id,
            evidence.source_sha256,
            evidence.snapshot_id,
            evidence.page_id,
            evidence.physical_wall_id,
        )
        if key in self._records:
            existing = self._records[key]
            if abs(existing.thickness_m - evidence.thickness_m) > 1e-4:
                self._conflicts.add(key)
        self._records[key] = evidence

    def authority(self) -> WallThicknessAuthority:
        return WallThicknessAuthority(self._records, self._conflicts, _seal=_AUTHORITY_SEAL)


@dataclass(frozen=True)
class WallFaceGeometryRecord:
    """Sealed, authenticated wall face geometry record."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_wall_id: str
    thickness_m: float
    thickness_mm: float
    length_m: float
    centerline_wkb_hex: str
    face_left_wkb_hex: str
    face_right_wkb_hex: str
    polygon_wkb_hex: str
    corroborating_evidence_ids: Tuple[str, ...]
    schema_version: str = WALL_THICKNESS_FACE_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("WallFaceGeometryRecord is producer-owned and cannot be constructed directly")


@dataclass(frozen=True)
class WallThicknessFaceResult:
    """Result of a wall thickness & face geometry resolution."""

    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[WallFaceGeometryRecord] = None
    schema_version: str = WALL_THICKNESS_FACE_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> WallThicknessFaceResult:
    return WallThicknessFaceResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


def _conflict(reason: str, *extras: str) -> WallThicknessFaceResult:
    return WallThicknessFaceResult(
        status=EvidenceResolutionStatus.CONFLICT,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


# ── Main Authority & Producer ─────────────────────────────────────────────────


class WallThicknessFaceAuthority:
    """Sealed selector-only lookup for published wall thickness and face geometry records."""

    def __init__(
        self,
        results: Mapping[_Key, WallThicknessFaceResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("WallThicknessFaceAuthority is producer-owned and cannot be constructed directly")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: WallThicknessFaceSelector) -> WallThicknessFaceResult:
        if type(selector) is not WallThicknessFaceSelector:
            raise TypeError("selector must be WallThicknessFaceSelector")
        return self._results.get(
            selector.key,
            _abstained(WALL_THICKNESS_RECORD_UNAVAILABLE),
        )


class WallThicknessFaceProducer:
    """Trusted writer boundary for authenticated wall thickness and authentic face geometry.

    Callers may NOT supply thickness, face coordinates, or use candidate thickness
    as authority. Genuine thickness must be proven by source-backed evidence.
    """

    def __init__(
        self,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        physical_scale_authority: PhysicalScaleAuthority,
        *,
        wall_thickness_authority: Optional[WallThicknessAuthority] = None,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("WallThicknessFaceProducer must be obtained via from_authorities()")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError(
                "physical_wall_candidate_authority must be a producer-owned PhysicalWallCandidateAuthority"
            )
        if type(physical_scale_authority) is not PhysicalScaleAuthority:
            raise TypeError(
                "physical_scale_authority must be a producer-owned PhysicalScaleAuthority"
            )
        if wall_thickness_authority is not None and type(wall_thickness_authority) is not WallThicknessAuthority:
            raise TypeError(
                "wall_thickness_authority must be a producer-owned WallThicknessAuthority"
            )

        self._wall_candidates = physical_wall_candidate_authority
        self._scale = physical_scale_authority
        self._thickness_auth = wall_thickness_authority
        self._results: Dict[_Key, WallThicknessFaceResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        physical_scale_authority: PhysicalScaleAuthority,
        wall_thickness_authority: Optional[WallThicknessAuthority] = None,
    ) -> WallThicknessFaceProducer:
        return cls(
            physical_wall_candidate_authority,
            physical_scale_authority,
            wall_thickness_authority=wall_thickness_authority,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> WallThicknessFaceAuthority:
        return WallThicknessFaceAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: WallThicknessFaceSelector,
        result: WallThicknessFaceResult,
    ) -> WallThicknessFaceResult:
        self._results[selector.key] = result
        return result

    def publish(
        self,
        selector: WallThicknessFaceSelector,
    ) -> WallThicknessFaceResult:
        """Publish authenticated wall thickness & face geometry for selector."""
        if type(selector) is not WallThicknessFaceSelector:
            raise TypeError("selector must be WallThicknessFaceSelector")

        # 1. Scale authority verification
        scale_sel = PhysicalScaleSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
        )
        scale_res = self._scale.resolve(scale_sel)
        if scale_res.status is not EvidenceResolutionStatus.CORROBORATED:
            return self._store(
                selector,
                _abstained(
                    WALL_THICKNESS_SCALE_UNRESOLVED,
                    *(getattr(scale_res, "reason_codes", ()) or ()),
                ),
            )

        # 2. Candidate wall existence verification
        cand_scope_id = f"wall-source:page-{selector.page_id}"
        cand_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=cand_scope_id,
        )
        cand_result = self._wall_candidates.resolve_scope(cand_sel)
        if cand_result.status is not EvidenceResolutionStatus.CORROBORATED:
            return self._store(
                selector,
                _abstained(
                    WALL_THICKNESS_WALL_UNRESOLVED,
                    *(getattr(cand_result, "reason_codes", ()) or ()),
                ),
            )

        matching_recs = [
            r for r in getattr(cand_result, "records", ())
            if getattr(r, "wall_candidate_id", None) == selector.physical_wall_id
            or getattr(getattr(r, "physical_identity", None), "physical_wall_id", None) == selector.physical_wall_id
        ]
        if not matching_recs:
            return self._store(selector, _abstained(WALL_THICKNESS_WALL_UNRESOLVED))

        rec = matching_recs[0]
        cand = rec.wall_candidate

        # 3. Diagnostic check of candidate thickness (never promoted to authority)
        diagnostic_reasons = []
        if getattr(cand, "thickness_m", None) is not None:
            diagnostic_reasons.append(WALL_THICKNESS_CANDIDATE_REJECTED)

        # Centerline validation
        centerline_raw = getattr(cand, "centerline_pts", None)
        if not centerline_raw or len(centerline_raw) < 2:
            return self._store(selector, _abstained(WALL_THICKNESS_GEOMETRY_UNAVAILABLE))

        # 4. Source-backed thickness evidence verification
        if self._thickness_auth is None:
            return self._store(
                selector,
                _abstained(WALL_THICKNESS_UNRESOLVED, *diagnostic_reasons),
            )

        # Conflict check
        if self._thickness_auth.is_conflict(selector):
            return self._store(
                selector,
                _conflict(WALL_THICKNESS_CONFLICT),
            )

        thick_ev = self._thickness_auth.get_evidence(selector)
        if thick_ev is None:
            return self._store(
                selector,
                _abstained(WALL_THICKNESS_UNRESOLVED, *diagnostic_reasons),
            )

        # Lineage check
        if (
            thick_ev.document_id != selector.document_id
            or thick_ev.revision_id != selector.revision_id
            or thick_ev.source_sha256 != selector.source_sha256
            or thick_ev.snapshot_id != selector.snapshot_id
            or thick_ev.page_id != selector.page_id
        ):
            return self._store(
                selector,
                _abstained(WALL_THICKNESS_STALE_EVIDENCE, WALL_THICKNESS_LINEAGE_MISMATCH),
            )

        if thick_ev.physical_wall_id != selector.physical_wall_id:
            return self._store(selector, _abstained(WALL_THICKNESS_WRONG_WALL))

        # Reject default / assumed thickness
        if thick_ev.is_default or thick_ev.source_kind in (
            "default",
            "model_default",
            "assumed",
            "typical",
            "project_constant",
        ):
            return self._store(selector, _abstained(WALL_THICKNESS_DEFAULT_REJECTED))

        # Reject zero or negative thickness
        if thick_ev.thickness_m == 0.0:
            return self._store(selector, _abstained(WALL_THICKNESS_ZERO_REJECTED))
        if thick_ev.thickness_m < 0.0:
            return self._store(selector, _abstained(WALL_THICKNESS_NEGATIVE_REJECTED))

        proven_thickness_m = float(thick_ev.thickness_m)
        proven_thickness_mm = proven_thickness_m * 1000.0

        # 5. Stable physical face geometry derivation
        # Check canonical physical direction
        canonical_flag = _is_canonical_direction(centerline_raw)
        if canonical_flag is None:
            return self._store(selector, _abstained(WALL_THICKNESS_FACE_IDENTITY_UNSTABLE))

        if not canonical_flag:
            canonical_centerline = tuple(reversed(centerline_raw))
        else:
            canonical_centerline = tuple(centerline_raw)

        half_thick = proven_thickness_m / 2.0
        # Left face: +half_thick in canonical physical orientation
        # Right face: -half_thick in canonical physical orientation
        left_face = _compute_multi_segment_offset(canonical_centerline, half_thick)
        right_face = _compute_multi_segment_offset(canonical_centerline, -half_thick)

        # Build bounding polygon: left face forward, right face in reverse, closed
        poly_pts = list(left_face) + list(reversed(right_face)) + [left_face[0]]

        # Serialize into genuine OGC WKB
        centerline_wkb = _linestring_to_wkb_hex(canonical_centerline)
        face_left_wkb = _linestring_to_wkb_hex(left_face)
        face_right_wkb = _linestring_to_wkb_hex(right_face)
        polygon_wkb = _polygon_to_wkb_hex(poly_pts)

        length_m = _line_length(canonical_centerline)
        corroborating_ids = (rec.wall_candidate_id, thick_ev.evidence_id)

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "physical_wall_id": selector.physical_wall_id,
            "thickness_m": proven_thickness_m,
            "length_m": length_m,
            "corroborating_evidence_ids": corroborating_ids,
        }
        record_id = stable_contract_id("wall_thickness_face", payload, digest_chars=32)
        record = WallFaceGeometryRecord(
            record_id=record_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            physical_wall_id=selector.physical_wall_id,
            thickness_m=proven_thickness_m,
            thickness_mm=proven_thickness_mm,
            length_m=length_m,
            centerline_wkb_hex=centerline_wkb,
            face_left_wkb_hex=face_left_wkb,
            face_right_wkb_hex=face_right_wkb,
            polygon_wkb_hex=polygon_wkb,
            corroborating_evidence_ids=corroborating_ids,
            _seal=_RECORD_SEAL,
        )

        return self._store(
            selector,
            WallThicknessFaceResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(WALL_THICKNESS_FACE_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "WALL_THICKNESS_CANDIDATE_REJECTED",
    "WALL_THICKNESS_CONFLICT",
    "WALL_THICKNESS_DEFAULT_REJECTED",
    "WALL_THICKNESS_FACE_IDENTITY_UNSTABLE",
    "WALL_THICKNESS_FACE_RESOLVED",
    "WALL_THICKNESS_GEOMETRY_INVALID",
    "WALL_THICKNESS_GEOMETRY_UNAVAILABLE",
    "WALL_THICKNESS_LINEAGE_MISMATCH",
    "WALL_THICKNESS_NEGATIVE_REJECTED",
    "WALL_THICKNESS_RECORD_UNAVAILABLE",
    "WALL_THICKNESS_SCALE_UNRESOLVED",
    "WALL_THICKNESS_SCHEMA_VERSION",
    "WALL_THICKNESS_STALE_EVIDENCE",
    "WALL_THICKNESS_UNRESOLVED",
    "WALL_THICKNESS_WALL_UNRESOLVED",
    "WALL_THICKNESS_WRONG_WALL",
    "WALL_THICKNESS_ZERO_REJECTED",
    "WallFaceGeometryRecord",
    "WallThicknessAuthority",
    "WallThicknessEvidence",
    "WallThicknessFaceAuthority",
    "WallThicknessFaceProducer",
    "WallThicknessFaceResult",
    "WallThicknessFaceSelector",
    "WallThicknessProducer",
]
