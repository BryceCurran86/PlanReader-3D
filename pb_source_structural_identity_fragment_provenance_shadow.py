"""Producer-owned source structural identity and fragment provenance shadow authority (Items 9 & 25).

Implements deterministic structural identity across fragmented linework and preserves
complete primitive provenance through splitting, clipping, and snapping:
- Aggregates child edge fragments sharing a parent primitive ID from W2/W3 stages.
- Validates collinear parameterization of fragments along the parent primitive vector.
- Merges child intervals along the parent axis and identifies opening/junction void gaps.
- Computes complete vs partial coverage ratio.
- Mints immutable, stable structural_identity_id across all sibling fragments.
- Serializes reconstructed structural run geometry to standard OGC WKB hex.
- Operates strictly in shadow mode with CANDIDATE status and non-commercial flags.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
import struct
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SOURCE_STRUCTURAL_IDENTITY_SCHEMA_VERSION = "1.0.0"

# Public Reason Codes
STRUCTURAL_RUN_RESOLVED = "structural_run_resolved"
STRUCTURAL_RUN_UNRESOLVED = "structural_run_unresolved"
FRAGMENT_NON_COLLINEAR = "fragment_non_collinear"
FRAGMENT_LINEAGE_UNMAPPED = "fragment_lineage_unmapped"
DEGENERATE_FRAGMENT_GEOMETRY = "degenerate_fragment_geometry"
AMBIGUOUS_PARENT_PRIMITIVE = "ambiguous_parent_primitive"
STRUCTURAL_IDENTITY_RECORD_UNAVAILABLE = "structural_identity_record_unavailable"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str]  # doc/rev/sha/snap/page/scope/parent_id


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


def _multilinestring_to_wkb_hex(lines: Sequence[Sequence[Tuple[float, float]]]) -> str:
    """Encode 2D MultiLineString into genuine standard OGC Well-Known Binary hex."""
    header = struct.pack("<BII", 1, 5, len(lines))
    sub_lines = []
    for pts in lines:
        sub_header = struct.pack("<BII", 1, 2, len(pts))
        sub_coords = b"".join(struct.pack("<dd", float(x), float(y)) for x, y in pts)
        sub_lines.append(sub_header + sub_coords)
    return (header + b"".join(sub_lines)).hex()


# ── Contracts ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourceStructuralIdentitySelector:
    """Selector identifying the parent primitive context for structural run resolution."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    parent_primitive_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "parent_primitive_id",
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
            self.parent_primitive_id,
        )


@dataclass(frozen=True)
class SourceStructuralRunRecord:
    """Sealed record proving authentic continuous structural run identity."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    parent_primitive_id: str
    structural_identity_id: str
    parent_extent_pts: Tuple[Tuple[float, float], Tuple[float, float]]
    parent_length_pt: float
    child_edge_ids: Tuple[str, ...]
    coverage_ratio: float
    is_complete_extent: bool
    covered_intervals: Tuple[Tuple[float, float], ...]
    gap_intervals: Tuple[Tuple[float, float], ...]
    reconstructed_run_wkb_hex: str
    corroborating_evidence_ids: Tuple[str, ...]
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    schema_version: str = SOURCE_STRUCTURAL_IDENTITY_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourceStructuralRunRecord is producer-owned and cannot be constructed directly")


@dataclass(frozen=True)
class SourceStructuralIdentityResult:
    """Result of structural run identity and fragment provenance resolution."""

    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[SourceStructuralRunRecord] = None
    schema_version: str = SOURCE_STRUCTURAL_IDENTITY_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> SourceStructuralIdentityResult:
    return SourceStructuralIdentityResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


# ── Geometric Collinear Analysis ───────────────────────────────────────────────


def _extract_endpoints(seg: Mapping[str, Any]) -> Optional[Tuple[Tuple[float, float], Tuple[float, float]]]:
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


def _merge_intervals(intervals: Iterable[Tuple[float, float]]) -> List[Tuple[float, float]]:
    out: List[List[float]] = []
    for lo, hi in sorted((min(float(a), float(b)), max(float(a), float(b))) for a, b in intervals):
        if out and lo <= out[-1][1] + 1e-4:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return [(round(a, 4), round(b, 4)) for a, b in out]


def _compute_gaps(covered: Sequence[Tuple[float, float]], total_len: float) -> List[Tuple[float, float]]:
    gaps: List[Tuple[float, float]] = []
    curr = 0.0
    for a, b in covered:
        if a > curr + 1e-4:
            gaps.append((round(curr, 4), round(a, 4)))
        curr = max(curr, b)
    if curr + 1e-4 < total_len:
        gaps.append((round(curr, 4), round(total_len, 4)))
    return gaps


# ── Producer & Authority ───────────────────────────────────────────────────────


class SourceStructuralIdentityAuthority:
    """Sealed lookup authority for published structural run identity records."""

    def __init__(
        self,
        records: Mapping[_Key, SourceStructuralIdentityResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("SourceStructuralIdentityAuthority is producer-owned and cannot be constructed directly")
        self._records = MappingProxyType(dict(records))

    def resolve(self, selector: SourceStructuralIdentitySelector) -> SourceStructuralIdentityResult:
        if type(selector) is not SourceStructuralIdentitySelector:
            raise TypeError("selector must be SourceStructuralIdentitySelector")
        return self._records.get(selector.key, _abstained(STRUCTURAL_IDENTITY_RECORD_UNAVAILABLE))


class SourceStructuralIdentityProducer:
    """Producer for authenticating continuous structural run identities from fragmented linework."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("SourceStructuralIdentityProducer must be obtained via create()")
        self._results: Dict[_Key, SourceStructuralIdentityResult] = {}

    @classmethod
    def create(cls) -> SourceStructuralIdentityProducer:
        return cls(_seal=_PRODUCER_SEAL)

    def evaluate_and_publish(
        self,
        selector: SourceStructuralIdentitySelector,
        *,
        parent_primitive: Mapping[str, Any],
        child_fragments: Iterable[Mapping[str, Any]],
        collinear_tolerance_pt: float = 0.5,
    ) -> SourceStructuralIdentityResult:
        """Evaluate child edge fragments sharing parent primitive and publish authentic structural run."""
        if type(selector) is not SourceStructuralIdentitySelector:
            raise TypeError("selector must be SourceStructuralIdentitySelector")

        # 1. Validate parent primitive geometry
        parent_pts = _extract_endpoints(parent_primitive)
        if not parent_pts:
            res = _abstained(DEGENERATE_FRAGMENT_GEOMETRY)
            self._results[selector.key] = res
            return res

        (px1, py1), (px2, py2) = parent_pts
        pdx = px2 - px1
        pdy = py2 - py1
        parent_len = math.hypot(pdx, pdy)
        if parent_len < 1e-4:
            res = _abstained(DEGENERATE_FRAGMENT_GEOMETRY)
            self._results[selector.key] = res
            return res

        pu_x = pdx / parent_len
        pu_y = pdy / parent_len
        pn_x = -pu_y
        pn_y = pu_x

        # 2. Evaluate child fragments
        raw_intervals: List[Tuple[float, float]] = []
        child_ids: List[str] = []

        for frag in child_fragments:
            frag_id = str(frag.get("id") or frag.get("edge_id") or "")
            if not frag_id:
                res = _abstained(FRAGMENT_LINEAGE_UNMAPPED)
                self._results[selector.key] = res
                return res

            frag_pts = _extract_endpoints(frag)
            if not frag_pts:
                res = _abstained(DEGENERATE_FRAGMENT_GEOMETRY)
                self._results[selector.key] = res
                return res

            (qx1, qy1), (qx2, qy2) = frag_pts
            qdx = qx2 - qx1
            qdy = qy2 - qy1
            frag_len = math.hypot(qdx, qdy)
            if frag_len < 1e-4:
                continue

            # Check normal distance to parent line
            d1 = abs((qx1 - px1) * pn_x + (qy1 - py1) * pn_y)
            d2 = abs((qx2 - px1) * pn_x + (qy2 - py1) * pn_y)
            if d1 > collinear_tolerance_pt or d2 > collinear_tolerance_pt:
                res = _abstained(FRAGMENT_NON_COLLINEAR)
                self._results[selector.key] = res
                return res

            # Check parallel orientation
            qu_x = qdx / frag_len
            qu_y = qdy / frag_len
            dot = abs(pu_x * qu_x + pu_y * qu_y)
            if dot < 0.999:  # > 2.5 degrees difference
                res = _abstained(FRAGMENT_NON_COLLINEAR)
                self._results[selector.key] = res
                return res

            # Project endpoints along parent vector
            t1 = (qx1 - px1) * pu_x + (qy1 - py1) * pu_y
            t2 = (qx2 - px1) * pu_x + (qy2 - py1) * pu_y
            lo = min(t1, t2)
            hi = max(t1, t2)

            # Clamp to parent range with small tolerance
            lo_clamped = max(0.0, lo)
            hi_clamped = min(parent_len, hi)
            if hi_clamped > lo_clamped + 1e-4:
                raw_intervals.append((lo_clamped, hi_clamped))
                child_ids.append(frag_id)

        if not raw_intervals:
            res = _abstained(STRUCTURAL_RUN_UNRESOLVED)
            self._results[selector.key] = res
            return res

        # 3. Merge intervals and compute coverage
        merged_ivs = _merge_intervals(raw_intervals)
        covered_len = sum(b - a for a, b in merged_ivs)
        coverage_ratio = round(min(1.0, covered_len / parent_len), 4)
        is_complete = coverage_ratio >= 0.99
        gaps = _compute_gaps(merged_ivs, parent_len)

        # 4. Generate reconstructed run geometry
        run_lines: List[List[Tuple[float, float]]] = []
        for a, b in merged_ivs:
            p_start = (round(px1 + a * pu_x, 3), round(py1 + a * pu_y, 3))
            p_end = (round(px1 + b * pu_x, 3), round(py1 + b * pu_y, 3))
            run_lines.append([p_start, p_end])

        if len(run_lines) == 1:
            wkb_hex = _linestring_to_wkb_hex(run_lines[0])
        else:
            wkb_hex = _multilinestring_to_wkb_hex(run_lines)

        # 5. Mint stable structural identity
        structural_ident = stable_contract_id(
            "source_structural_identity",
            {
                "document_id": selector.document_id,
                "revision_id": selector.revision_id,
                "source_sha256": selector.source_sha256,
                "page_id": selector.page_id,
                "parent_primitive_id": selector.parent_primitive_id,
            },
        )

        rec_id = stable_contract_id(
            "source_structural_run_record",
            {
                "document_id": selector.document_id,
                "revision_id": selector.revision_id,
                "source_sha256": selector.source_sha256,
                "snapshot_id": selector.snapshot_id,
                "page_id": selector.page_id,
                "parent_primitive_id": selector.parent_primitive_id,
            },
        )

        record = SourceStructuralRunRecord(
            record_id=rec_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            parent_primitive_id=selector.parent_primitive_id,
            structural_identity_id=structural_ident,
            parent_extent_pts=((round(px1, 3), round(py1, 3)), (round(px2, 3), round(py2, 3))),
            parent_length_pt=round(parent_len, 4),
            child_edge_ids=tuple(sorted(set(child_ids))),
            coverage_ratio=coverage_ratio,
            is_complete_extent=is_complete,
            covered_intervals=tuple(merged_ivs),
            gap_intervals=tuple(gaps),
            reconstructed_run_wkb_hex=wkb_hex,
            corroborating_evidence_ids=tuple(sorted(set([selector.parent_primitive_id, *child_ids]))),
            status=EvidenceResolutionStatus.CANDIDATE,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_RECORD_SEAL,
        )

        res = SourceStructuralIdentityResult(
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=(STRUCTURAL_RUN_RESOLVED,),
            record=record,
        )
        self._results[selector.key] = res
        return res

    def authority(self) -> SourceStructuralIdentityAuthority:
        return SourceStructuralIdentityAuthority(self._results, _seal=_AUTHORITY_SEAL)
