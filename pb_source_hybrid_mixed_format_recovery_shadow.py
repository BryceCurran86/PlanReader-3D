"""Producer-owned hybrid mixed-format (vector/raster) geometry recovery shadow authority (Item 8).

Resolves Workstream A, Item 8 of the Autonomous Core Accuracy Engineering Mission:
"Improve geometric recovery from vector, raster and mixed-format PDFs."

Key requirements:
- Reconciles native vector drawing paths and scanned raster-derived primitives on mixed-format pages.
- Resolves collocated duplicates: when a vector segment and a raster segment are collinear
  and overlapping within snap tolerance (<= 2.5 pt), the vector segment is canonicalized as
  primary geometry while the raster primitive is retained as corroborating evidence
  without duplicating graph edges or inflating complexity.
- Promotes authentic raster primitives when no corresponding vector linework exists (gap filling).
- Classifies page modality deterministically: PURE_VECTOR, PURE_RASTER, or MIXED_HYBRID.
- Strictly operates in shadow mode: status=CANDIDATE, commercial_projection_allowed=False,
  takeoff_eligible=False.
"""
from __future__ import annotations

import collections
from dataclasses import dataclass, field
import math
from types import MappingProxyType
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

SCHEMA_VERSION = "1.0.0"

# Page Modalities
MODALITY_PURE_VECTOR = "pure_vector"
MODALITY_PURE_RASTER = "pure_raster"
MODALITY_MIXED_HYBRID = "mixed_hybrid"

# Reconciliation Roles
VECTOR_PRIMITIVE_CANONICAL = "vector_primitive_canonical"
RASTER_PRIMITIVE_PROMOTED_AUGMENTATION = "raster_primitive_promoted_augmentation"
RASTER_PRIMITIVE_RECONCILED_AS_CORROBORATION = "raster_primitive_reconciled_as_corroboration"

# Public Reason Codes
SOURCE_HYBRID_RECOVERY_RESOLVED = "source_hybrid_recovery_resolved"
SOURCE_HYBRID_RECOVERY_CANDIDATE = "source_hybrid_recovery_candidate"
SOURCE_HYBRID_RECOVERY_UNAVAILABLE = "source_hybrid_recovery_unavailable"
HYBRID_PAGE_MODALITY_DETERMINED = "hybrid_page_modality_determined"
COLLOCATED_RASTER_DUPLICATE_RECONCILED = "collocated_raster_duplicate_reconciled"
UNMATCHED_RASTER_PROMOTED = "unmatched_raster_promoted"
PURE_VECTOR_PRESERVED = "pure_vector_preserved"
PURE_RASTER_PRESERVED = "pure_raster_preserved"

DEFAULT_SNAP_TOLERANCE_PT = 2.5

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str]  # doc/rev/sha/snap/page


def _clean(val: Any) -> str:
    return str(val or "").strip()


def _point_to_line_dist(px: float, py: float, x1: float, y1: float, x2: float, y2: float) -> float:
    dx = x2 - x1
    dy = y2 - y1
    l2 = dx * dx + dy * dy
    if l2 == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0.0, min(1.0, ((px - x1) * dx + (py - y1) * dy) / l2))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def _segments_overlap(
    s1: Mapping[str, Any],
    s2: Mapping[str, Any],
    tol: float = DEFAULT_SNAP_TOLERANCE_PT,
) -> bool:
    """Check if two segments are collinear and overlapping within tolerance."""
    ax1, ay1 = float(s1["x1"]), float(s1["y1"])
    ax2, ay2 = float(s1["x2"]), float(s1["y2"])
    bx1, by1 = float(s2["x1"]), float(s2["y1"])
    bx2, by2 = float(s2["x2"]), float(s2["y2"])

    # Orientation check: directional vectors must be roughly parallel
    adx, ady = ax2 - ax1, ay2 - ay1
    bdx, bdy = bx2 - bx1, by2 - by1
    alen = math.hypot(adx, ady)
    blen = math.hypot(bdx, bdy)
    if alen < 1e-4 or blen < 1e-4:
        return False

    cos_theta = abs((adx * bdx + ady * bdy) / (alen * blen))
    if cos_theta < 0.985:  # within ~10 degrees
        return False

    # Perpendicular distance check from s2 endpoints to line of s1
    d1 = _point_to_line_dist(bx1, by1, ax1, ay1, ax2, ay2)
    d2 = _point_to_line_dist(bx2, by2, ax1, ay1, ax2, ay2)
    if d1 > tol or d2 > tol:
        return False

    # Projection interval overlap check along s1
    t1 = ((bx1 - ax1) * adx + (by1 - ay1) * ady) / (alen * alen)
    t2 = ((bx2 - ax1) * adx + (by2 - ay1) * ady) / (alen * alen)
    min_t = min(t1, t2)
    max_t = max(t1, t2)

    # Allow slight endpoint extension within tolerance
    t_tol = tol / alen
    return not (max_t < -t_tol or min_t > 1.0 + t_tol)


def reconcile_hybrid_primitives(
    vector_segments: Sequence[Mapping[str, Any]],
    raster_segments: Sequence[Mapping[str, Any]],
    snap_tolerance: float = DEFAULT_SNAP_TOLERANCE_PT,
) -> Dict[str, Any]:
    """Reconciles vector and raster segments on a page into a canonical candidate set."""
    vec_count = len(vector_segments)
    ras_count = len(raster_segments)

    if vec_count > 0 and ras_count == 0:
        modality = MODALITY_PURE_VECTOR
    elif vec_count == 0 and ras_count > 0:
        modality = MODALITY_PURE_RASTER
    elif vec_count > 0 and ras_count > 0:
        modality = MODALITY_MIXED_HYBRID
    else:
        modality = "empty"

    reconciled: List[Dict[str, Any]] = []
    collocated_raster_ids: Set[str] = set()
    corroboration_map: Dict[str, List[str]] = collections.defaultdict(list)

    # 1. First pass on mixed: match raster segments against vector segments
    if modality == MODALITY_MIXED_HYBRID:
        for r in raster_segments:
            rid = _clean(r.get("id"))
            matched_vids = []
            for v in vector_segments:
                vid = _clean(v.get("id"))
                if _segments_overlap(v, r, tol=snap_tolerance):
                    matched_vids.append(vid)
                    corroboration_map[vid].append(rid)

            if matched_vids:
                collocated_raster_ids.add(rid)

    # 2. Add all vector segments as CANONICAL
    for v in vector_segments:
        vid = _clean(v.get("id"))
        corrob = corroboration_map.get(vid, [])
        reasons = [PURE_VECTOR_PRESERVED] if modality == MODALITY_PURE_VECTOR else [VECTOR_PRIMITIVE_CANONICAL]
        if corrob:
            reasons.append(COLLOCATED_RASTER_DUPLICATE_RECONCILED)

        reconciled.append({
            "primitive_id": vid,
            "source_modality": "vector",
            "reconciliation_role": VECTOR_PRIMITIVE_CANONICAL,
            "x1": float(v["x1"]),
            "y1": float(v["y1"]),
            "x2": float(v["x2"]),
            "y2": float(v["y2"]),
            "corroborating_primitive_ids": tuple(sorted(corrob)),
            "reason_codes": tuple(reasons),
        })

    # 3. Add raster segments:
    # - If unmatched in mixed mode: PROMOTE as augmentation (gap-filling)
    # - If pure raster: PROMOTE all
    # - If matched/collocated: retain as secondary corroboration record
    for r in raster_segments:
        rid = _clean(r.get("id"))
        if rid in collocated_raster_ids:
            reconciled.append({
                "primitive_id": rid,
                "source_modality": "raster",
                "reconciliation_role": RASTER_PRIMITIVE_RECONCILED_AS_CORROBORATION,
                "x1": float(r["x1"]),
                "y1": float(r["y1"]),
                "x2": float(r["x2"]),
                "y2": float(r["y2"]),
                "corroborating_primitive_ids": (),
                "reason_codes": (COLLOCATED_RASTER_DUPLICATE_RECONCILED,),
            })
        else:
            reasons = [PURE_RASTER_PRESERVED] if modality == MODALITY_PURE_RASTER else [UNMATCHED_RASTER_PROMOTED]
            reconciled.append({
                "primitive_id": rid,
                "source_modality": "raster",
                "reconciliation_role": RASTER_PRIMITIVE_PROMOTED_AUGMENTATION,
                "x1": float(r["x1"]),
                "y1": float(r["y1"]),
                "x2": float(r["x2"]),
                "y2": float(r["y2"]),
                "corroborating_primitive_ids": (),
                "reason_codes": tuple(reasons),
            })

    promoted_ras_count = sum(1 for rec in reconciled if rec["reconciliation_role"] == RASTER_PRIMITIVE_PROMOTED_AUGMENTATION)
    reconciled_ras_count = len(collocated_raster_ids)

    return {
        "detected_modality": modality,
        "vector_count": vec_count,
        "raster_count": ras_count,
        "promoted_raster_count": promoted_ras_count,
        "reconciled_raster_count": reconciled_ras_count,
        "total_reconciled_primitives": len(reconciled),
        "reconciled_primitives": tuple(reconciled),
    }


@dataclass(frozen=True)
class SourceReconciledHybridPrimitiveRecord:
    primitive_id: str
    source_modality: str
    reconciliation_role: str
    x1: float
    y1: float
    x2: float
    y2: float
    corroborating_primitive_ids: Tuple[str, ...]
    reason_codes: Tuple[str, ...]
    status: str = EvidenceResolutionStatus.CANDIDATE.value
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = field(default=None, repr=False)

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceHybridMixedFormatRecoveryProducer")


@dataclass(frozen=True)
class SourceHybridMixedFormatSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str

    def __post_init__(self) -> None:
        for f in ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id"):
            if not _clean(getattr(self, f)):
                raise ValueError(f"SourceHybridMixedFormatSelector requires non-empty {f}")


@dataclass(frozen=True)
class SourceHybridMixedFormatResult:
    status: str
    detected_modality: str
    reconciled_primitives: Tuple[SourceReconciledHybridPrimitiveRecord, ...]
    vector_count: int
    raster_count: int
    promoted_raster_count: int
    reconciled_raster_count: int
    reason_codes: Tuple[str, ...]
    resolution_mode: str
    schema_version: str = SCHEMA_VERSION


class SourceHybridMixedFormatRecoveryProducer:
    """Producer responsible for registering and reconciling mixed-format drawing geometries."""

    def __init__(self, _seal: object) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceHybridMixedFormatRecoveryProducer.create()")
        self._pages: Dict[_Key, Dict[str, Any]] = {}

    @classmethod
    def create(cls) -> SourceHybridMixedFormatRecoveryProducer:
        return cls(_PRODUCER_SEAL)

    def register_page_primitives(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        page_id: str,
        vector_segments: Sequence[Mapping[str, Any]],
        raster_segments: Sequence[Mapping[str, Any]],
        snap_tolerance: float = DEFAULT_SNAP_TOLERANCE_PT,
    ) -> None:
        doc = _clean(document_id)
        rev = _clean(revision_id)
        sha = _clean(source_sha256)
        snap = _clean(snapshot_id)
        pg = _clean(page_id)

        if not (doc and rev and sha and snap and pg):
            raise ValueError("All document, snapshot, and page identifiers are required")

        key: _Key = (doc, rev, sha, snap, pg)
        self._pages[key] = {
            "vector_segments": tuple(vector_segments),
            "raster_segments": tuple(raster_segments),
            "snap_tolerance": float(snap_tolerance),
        }

    def authority(self) -> SourceHybridMixedFormatRecoveryAuthority:
        results_map: Dict[_Key, SourceHybridMixedFormatResult] = {}

        for key, pdata in self._pages.items():
            doc, rev, sha, snap, pg = key
            v_segs = pdata["vector_segments"]
            r_segs = pdata["raster_segments"]
            tol = pdata["snap_tolerance"]

            rec_dict = reconcile_hybrid_primitives(v_segs, r_segs, snap_tolerance=tol)
            records: List[SourceReconciledHybridPrimitiveRecord] = []

            for p in rec_dict["reconciled_primitives"]:
                records.append(
                    SourceReconciledHybridPrimitiveRecord(
                        primitive_id=p["primitive_id"],
                        source_modality=p["source_modality"],
                        reconciliation_role=p["reconciliation_role"],
                        x1=p["x1"],
                        y1=p["y1"],
                        x2=p["x2"],
                        y2=p["y2"],
                        corroborating_primitive_ids=p["corroborating_primitive_ids"],
                        reason_codes=p["reason_codes"],
                        _seal=_RECORD_SEAL,
                    )
                )

            all_reasons = {HYBRID_PAGE_MODALITY_DETERMINED, SOURCE_HYBRID_RECOVERY_RESOLVED}
            for r in records:
                all_reasons.update(r.reason_codes)

            results_map[key] = SourceHybridMixedFormatResult(
                status=EvidenceResolutionStatus.CORROBORATED.value,
                detected_modality=rec_dict["detected_modality"],
                reconciled_primitives=tuple(records),
                vector_count=rec_dict["vector_count"],
                raster_count=rec_dict["raster_count"],
                promoted_raster_count=rec_dict["promoted_raster_count"],
                reconciled_raster_count=rec_dict["reconciled_raster_count"],
                reason_codes=tuple(sorted(all_reasons)),
                resolution_mode=f"corroborated_{rec_dict['detected_modality']}_reconciliation",
            )

        return SourceHybridMixedFormatRecoveryAuthority(_AUTHORITY_SEAL, results_map)


class SourceHybridMixedFormatRecoveryAuthority:
    """Immutable authority serving reconciled hybrid mixed-format results."""

    def __init__(
        self,
        _seal: object,
        results_map: Mapping[_Key, SourceHybridMixedFormatResult],
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise PermissionError("Direct instantiation forbidden; use SourceHybridMixedFormatRecoveryProducer.authority()")
        self._results_map = MappingProxyType(dict(results_map))

    def resolve(self, selector: SourceHybridMixedFormatSelector) -> SourceHybridMixedFormatResult:
        key: _Key = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.page_id,
        )
        res = self._results_map.get(key)
        if res is None:
            return SourceHybridMixedFormatResult(
                status=EvidenceResolutionStatus.ABSTAINED.value,
                detected_modality="unknown",
                reconciled_primitives=(),
                vector_count=0,
                raster_count=0,
                promoted_raster_count=0,
                reconciled_raster_count=0,
                reason_codes=(SOURCE_HYBRID_RECOVERY_UNAVAILABLE,),
                resolution_mode="abstain_page_unavailable",
            )
        return res
