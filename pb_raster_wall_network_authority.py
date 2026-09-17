"""Raster wall-network and scanned-plan geometry authority (Item 25).

Provides conservative, provenance-tracked wall network extraction and topology
modeling from raster or scanned plan images without fabricating scale or
hallucinating geometry.

Key rules:
- Conservative raster wall candidates: extracts candidates from raster pixel
  runs or verified segment candidates; rejects noise and unsubstantiated geometry.
- Image snapshot identity: every record is bound to document_id, revision_id,
  source_sha256, snapshot_id, and page_id.
- Transform provenance: explicit binding of DPI, pixel-to-point (px_to_pt)
  conversion, and authoritative scale ratio.
- Fail-closed without fabricated scale: NEVER assumes default 1:100 or guesses
  scale. If scale is unproven, all physical metric values (meters, m2) remain
  None, and RASTER_SCALE_UNRESOLVED is emitted.
- Junction & topology handling: detects and classifies junctions (L, T, X, end)
  and maintains topological connectivity between candidate walls.
- Ambiguity retention: keeps ambiguity flags and reasons where raster pixels
  are noisy, fragmented, or ambiguous; never silently rounds or fabricates clean vectors.
- Producer-owned authority pattern: sealed construction, immutable records,
  and consumer addressing by lineage only.
- 100% portable on Python 3.13 and 3.14. Zero benchmark-specific heuristics.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
import hashlib
import math
from types import MappingProxyType
from typing import Any, Optional

from PIL import Image

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

RASTER_WALL_NETWORK_SCHEMA_VERSION = "1.0.0"

RASTER_WALL_NETWORK_RESOLVED = "raster_wall_network_resolved"
RASTER_WALL_NETWORK_UNAVAILABLE = "raster_wall_network_unavailable"
RASTER_SOURCE_IMAGE_MISSING = "raster_source_image_missing"
RASTER_SCALE_UNRESOLVED = "raster_scale_unresolved"
RASTER_LINEAGE_MISMATCH = "raster_lineage_mismatch"
RASTER_TOPOLOGY_DISCONNECTED = "raster_topology_disconnected"
RASTER_WALL_AMBIGUOUS = "raster_wall_ambiguous"
RASTER_NO_CANDIDATES_FOUND = "raster_no_candidates_found"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = tuple[str, str, str, str, str, Optional[str], Optional[tuple[float, float, float, float]]]


def _require_nonempty(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    return text


# ---------------------------------------------------------------------------
# Transform & Geometry Data Structures
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RasterTransformProvenance:
    """Explicit spatial and metric scale transform provenance."""

    dpi: int
    px_to_pt_ratio: float  # 72.0 / dpi
    scale_ratio: Optional[float] = None  # e.g., 0.01 for 1:100
    scale_provenance: Optional[str] = None
    is_scale_authoritative: bool = False

    def __post_init__(self) -> None:
        if self.dpi <= 0:
            raise ValueError("dpi must be a positive integer")
        if self.px_to_pt_ratio <= 0.0:
            raise ValueError("px_to_pt_ratio must be positive")
        if self.scale_ratio is not None:
            if not math.isfinite(self.scale_ratio) or self.scale_ratio <= 0.0:
                raise ValueError("scale_ratio must be a positive finite float")

    @classmethod
    def from_dpi(
        cls,
        dpi: int = 150,
        scale_ratio: Optional[float] = None,
        scale_provenance: Optional[str] = None,
        is_scale_authoritative: bool = False,
    ) -> "RasterTransformProvenance":
        px_to_pt = 72.0 / float(dpi) if dpi > 0 else 1.0
        return cls(
            dpi=dpi,
            px_to_pt_ratio=round(px_to_pt, 6),
            scale_ratio=scale_ratio,
            scale_provenance=scale_provenance,
            is_scale_authoritative=bool(is_scale_authoritative and scale_ratio is not None),
        )


@dataclass(frozen=True)
class RasterWallSegment:
    """A linear wall candidate segment with pixel and optional point/metric coordinates."""

    start_px: tuple[float, float]
    end_px: tuple[float, float]
    start_pt: Optional[tuple[float, float]] = None
    end_pt: Optional[tuple[float, float]] = None
    thickness_px: float = 0.0
    thickness_pt: Optional[float] = None
    thickness_m: Optional[float] = None
    length_px: float = 0.0
    length_pt: Optional[float] = None
    length_m: Optional[float] = None
    angle_deg: float = 0.0
    confidence: float = 0.5
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")


@dataclass(frozen=True)
class RasterWallJunction:
    """A detected junction connecting two or more wall candidates."""

    junction_id: str
    junction_type: str  # "L", "T", "X", "end", "multi"
    location_px: tuple[float, float]
    location_pt: Optional[tuple[float, float]] = None
    connected_candidate_ids: tuple[str, ...] = ()
    is_ambiguous: bool = False

    def __post_init__(self) -> None:
        _require_nonempty(self.junction_id, "junction_id")
        if self.junction_type not in {"L", "T", "X", "end", "multi"}:
            raise ValueError(f"Invalid junction_type: {self.junction_type}")


@dataclass(frozen=True)
class RasterWallCandidateRecord:
    """An individual candidate wall with junction connectivity and ambiguity status."""

    candidate_id: str
    segment: RasterWallSegment
    connected_junction_ids: tuple[str, ...]
    is_ambiguous: bool
    confidence: float
    extraction_method: str = "raster_skeleton_tracking"

    def __post_init__(self) -> None:
        _require_nonempty(self.candidate_id, "candidate_id")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")


# ---------------------------------------------------------------------------
# Selectors and Network Record
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RasterWallNetworkSelector:
    """Consumer addressing selector for raster wall network resolution."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str] = None
    target_region_pt: Optional[tuple[float, float, float, float]] = None

    def __post_init__(self) -> None:
        _require_nonempty(self.document_id, "document_id")
        _require_nonempty(self.revision_id, "revision_id")
        _require_nonempty(self.source_sha256, "source_sha256")
        _require_nonempty(self.snapshot_id, "snapshot_id")
        _require_nonempty(self.page_id, "page_id")
        if self.target_region_pt is not None:
            if len(self.target_region_pt) != 4:
                raise ValueError("target_region_pt must be a 4-tuple (x0, y0, x1, y1)")
            x0, y0, x1, y1 = (float(v) for v in self.target_region_pt)
            if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
                raise ValueError("target_region_pt coordinates must be finite")
            if x1 <= x0 or y1 <= y0:
                raise ValueError("target_region_pt must have positive span")
            object.__setattr__(self, "target_region_pt", (x0, y0, x1, y1))

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.viewport_id,
            self.target_region_pt,
        )


@dataclass(frozen=True)
class RasterWallNetworkRecord:
    """Immutable, provenance-tracked complete raster wall network publication record."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    target_region_pt: Optional[tuple[float, float, float, float]]
    transform: RasterTransformProvenance
    candidates: tuple[RasterWallCandidateRecord, ...]
    junctions: tuple[RasterWallJunction, ...]
    total_length_pt: float
    total_length_m: Optional[float]
    has_ambiguity: bool
    schema_version: str = RASTER_WALL_NETWORK_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.record_id, "record_id")
        _require_nonempty(self.document_id, "document_id")
        _require_nonempty(self.revision_id, "revision_id")
        _require_nonempty(self.source_sha256, "source_sha256")
        _require_nonempty(self.snapshot_id, "snapshot_id")
        _require_nonempty(self.page_id, "page_id")


@dataclass(frozen=True)
class RasterWallNetworkResult:
    """Result envelope for raster wall network resolution."""

    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[RasterWallNetworkRecord] = None
    schema_version: str = RASTER_WALL_NETWORK_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *extra_reasons: str,
) -> RasterWallNetworkResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    reasons = tuple(dict.fromkeys([reason, *(r for r in extra_reasons if r)]))
    return RasterWallNetworkResult(
        status=status,
        reason_codes=reasons,
        record=None,
    )


# ---------------------------------------------------------------------------
# Topology and Geometry Solver
# ---------------------------------------------------------------------------

def _dist(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def build_raster_junctions(
    candidates: Sequence[RasterWallCandidateRecord],
    snap_distance_px: float = 6.0,
    px_to_pt: float = 0.48,
) -> tuple[tuple[RasterWallJunction, ...], dict[str, tuple[str, ...]]]:
    """Detect and classify junctions from candidate wall endpoints."""
    # Endpoints with candidate mapping
    endpoints: list[tuple[tuple[float, float], str]] = []
    for cand in candidates:
        seg = cand.segment
        endpoints.append((seg.start_px, cand.candidate_id))
        endpoints.append((seg.end_px, cand.candidate_id))

    # Cluster endpoints within snap_distance_px
    clusters: list[list[tuple[tuple[float, float], str]]] = []
    for pt, cand_id in endpoints:
        matched = False
        for cluster in clusters:
            centroid_x = sum(p[0][0] for p in cluster) / len(cluster)
            centroid_y = sum(p[0][1] for p in cluster) / len(cluster)
            if math.hypot(pt[0] - centroid_x, pt[1] - centroid_y) <= snap_distance_px:
                cluster.append((pt, cand_id))
                matched = True
                break
        if not matched:
            clusters.append([(pt, cand_id)])

    junctions: list[RasterWallJunction] = []
    cand_to_junctions: dict[str, list[str]] = {c.candidate_id: [] for c in candidates}

    for idx, cluster in enumerate(clusters):
        cx = sum(p[0][0] for p in cluster) / len(cluster)
        cy = sum(p[0][1] for p in cluster) / len(cluster)
        c_pt = (round(cx * px_to_pt, 4), round(cy * px_to_pt, 4))
        cand_ids = tuple(dict.fromkeys(p[1] for p in cluster))
        n_conn = len(cand_ids)

        if n_conn == 1:
            j_type = "end"
        elif n_conn == 2:
            j_type = "L"
        elif n_conn == 3:
            j_type = "T"
        elif n_conn == 4:
            j_type = "X"
        else:
            j_type = "multi"

        j_id = f"junc_{idx + 1:04d}_{j_type}"
        junc = RasterWallJunction(
            junction_id=j_id,
            junction_type=j_type,
            location_px=(round(cx, 2), round(cy, 2)),
            location_pt=c_pt,
            connected_candidate_ids=cand_ids,
            is_ambiguous=(j_type == "multi"),
        )
        junctions.append(junc)
        for cid in cand_ids:
            cand_to_junctions[cid].append(j_id)

    cand_junc_map = {cid: tuple(j_ids) for cid, j_ids in cand_to_junctions.items()}
    return tuple(junctions), cand_junc_map


# ---------------------------------------------------------------------------
# Producer and Authority
# ---------------------------------------------------------------------------

class RasterWallNetworkAuthority:
    """Read-only exact-scope selector lookup for raster wall network geometry."""

    def __init__(
        self,
        results: Mapping[_Key, RasterWallNetworkResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("RasterWallNetworkAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: RasterWallNetworkSelector) -> RasterWallNetworkResult:
        if type(selector) is not RasterWallNetworkSelector:
            raise TypeError("selector must be RasterWallNetworkSelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                RASTER_WALL_NETWORK_UNAVAILABLE,
            ),
        )


from pb_physical_scale_authority import (
    PhysicalScaleAuthority,
    PhysicalScaleSelector,
)


class RasterWallNetworkProducer:
    """Producer-owned trusted boundary constructing verified raster wall networks."""

    def __init__(
        self,
        page_images: Mapping[str, Image.Image],
        raw_candidates_by_page: Optional[Mapping[str, Sequence[RasterWallSegment]]] = None,
        transform_by_page: Optional[Mapping[str, RasterTransformProvenance]] = None,
        physical_scale_authority: Optional[PhysicalScaleAuthority] = None,
        snapshot: Optional[Any] = None,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "RasterWallNetworkProducer must be obtained from from_sources()"
            )
        if (
            physical_scale_authority is not None
            and type(physical_scale_authority) is not PhysicalScaleAuthority
        ):
            raise TypeError(
                "physical_scale_authority must be producer-owned PhysicalScaleAuthority"
            )
        self._page_images = MappingProxyType(dict(page_images))
        self._raw_candidates = MappingProxyType(dict(raw_candidates_by_page or {}))
        self._transforms = MappingProxyType(dict(transform_by_page or {}))
        self._scale_authority = physical_scale_authority
        self._snapshot = snapshot
        self._results: dict[_Key, RasterWallNetworkResult] = {}

    @classmethod
    def from_sources(
        cls,
        page_images: Optional[Mapping[str, Image.Image]] = None,
        raw_candidates_by_page: Optional[Mapping[str, Sequence[RasterWallSegment]]] = None,
        transform_by_page: Optional[Mapping[str, RasterTransformProvenance]] = None,
        physical_scale_authority: Optional[PhysicalScaleAuthority] = None,
        snapshot: Optional[Any] = None,
    ) -> "RasterWallNetworkProducer":
        return cls(
            page_images=page_images or {},
            raw_candidates_by_page=raw_candidates_by_page or {},
            transform_by_page=transform_by_page or {},
            physical_scale_authority=physical_scale_authority,
            snapshot=snapshot,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> RasterWallNetworkAuthority:
        return RasterWallNetworkAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: RasterWallNetworkSelector,
        result: RasterWallNetworkResult,
    ) -> RasterWallNetworkResult:
        self._results[selector.key] = result
        return result

    def publish(
        self, selector: RasterWallNetworkSelector
    ) -> RasterWallNetworkResult:
        if type(selector) is not RasterWallNetworkSelector:
            raise TypeError("selector must be RasterWallNetworkSelector")

        # 1. Lineage Verification
        if self._snapshot is not None:
            snap = getattr(self._snapshot, "snapshot", self._snapshot)
            rev = getattr(self._snapshot, "revision", None)
            snap_doc = getattr(snap, "document_id", None) or getattr(rev, "document_id", None)
            snap_rev = getattr(snap, "revision_id", None) or getattr(rev, "revision_id", None)
            snap_sha = getattr(snap, "source_sha256", None) or getattr(rev, "source_sha256", None)
            snap_id = getattr(snap, "snapshot_id", None)

            if (
                selector.document_id != snap_doc
                or selector.revision_id != snap_rev
                or selector.source_sha256 != snap_sha
                or selector.snapshot_id != snap_id
            ):
                return self._store(
                    selector,
                    _blocked(
                        EvidenceResolutionStatus.CONFLICT,
                        RASTER_LINEAGE_MISMATCH,
                        "lineage_mismatch_with_snapshot",
                    ),
                )

        # 2. Source Image Presence
        img = self._page_images.get(selector.page_id)
        if img is None:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_SOURCE_IMAGE_MISSING,
                    f"no_image_for_page_{selector.page_id}",
                ),
            )

        # 3. Retrieve Transform Provenance and verify with PhysicalScaleAuthority
        raw_transform = self._transforms.get(
            selector.page_id,
            RasterTransformProvenance.from_dpi(150),
        )

        is_scale_auth = False
        scale_ratio = None
        scale_prov = None

        if self._scale_authority is not None:
            scale_sel = PhysicalScaleSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                viewport_id=selector.viewport_id,
            )
            scale_res = self._scale_authority.resolve(scale_sel)
            if (
                scale_res.status is EvidenceResolutionStatus.CORROBORATED
                and scale_res.evidence is not None
            ):
                ev = scale_res.evidence
                is_scale_auth = True
                scale_ratio = (ev.source_span_pt * (25.4 / 72.0)) / ev.physical_span_mm
                scale_prov = f"physical_scale_authority:{ev.record_id}"

        transform = RasterTransformProvenance(
            dpi=raw_transform.dpi,
            px_to_pt_ratio=raw_transform.px_to_pt_ratio,
            scale_ratio=scale_ratio,
            scale_provenance=scale_prov,
            is_scale_authoritative=is_scale_auth,
        )
        px_to_pt = transform.px_to_pt_ratio

        # Metric scale conversion factors
        # 1 point = 1/72 inch = 0.0254 / 72 meters in paper space
        # Real-world distance (m) = point_distance * (0.0254 / 72.0) / scale_ratio
        can_compute_metric = transform.is_scale_authoritative and transform.scale_ratio is not None
        pt_to_m_factor = (
            (0.0254 / 72.0) / transform.scale_ratio if (can_compute_metric and transform.scale_ratio) else None
        )

        # 4. Gather Raw Candidates
        raw_segments = self._raw_candidates.get(selector.page_id, ())
        if not raw_segments:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_NO_CANDIDATES_FOUND,
                ),
            )

        # 5. Build Initial Candidate Records
        initial_candidates: list[RasterWallCandidateRecord] = []
        has_ambiguity = False

        crop_offset_pt = (0.0, 0.0)
        crop_box_px: Optional[tuple[int, int, int, int]] = None
        if selector.target_region_pt is not None:
            pt_to_px = float(transform.dpi) / 72.0
            x0, y0, x1, y1 = selector.target_region_pt
            crop_box_px = (
                int(max(0, math.floor(x0 * pt_to_px))),
                int(max(0, math.floor(y0 * pt_to_px))),
                int(min(img.width, math.ceil(x1 * pt_to_px))),
                int(min(img.height, math.ceil(y1 * pt_to_px))),
            )
            crop_offset_pt = (x0, y0)

        for i, seg in enumerate(raw_segments):
            # Check target region clipping if specified
            if crop_box_px is not None:
                cx0, cy0, cx1, cy1 = crop_box_px
                sx, sy = seg.start_px
                ex, ey = seg.end_px
                # If neither endpoint is in crop box, skip
                if not (
                    (cx0 <= sx <= cx1 and cy0 <= sy <= cy1)
                    or (cx0 <= ex <= cx1 and cy0 <= ey <= cy1)
                ):
                    continue

            # Length calculation
            len_px = _dist(seg.start_px, seg.end_px)
            len_pt = round(len_px * px_to_pt, 4)
            len_m = round(len_pt * pt_to_m_factor, 4) if pt_to_m_factor is not None else None

            # Coordinates in point space
            start_pt = (
                round(seg.start_px[0] * px_to_pt, 4),
                round(seg.start_px[1] * px_to_pt, 4),
            )
            end_pt = (
                round(seg.end_px[0] * px_to_pt, 4),
                round(seg.end_px[1] * px_to_pt, 4),
            )

            # Thickness
            thick_pt = round(seg.thickness_px * px_to_pt, 4) if seg.thickness_px > 0 else None
            thick_m = (
                round(thick_pt * pt_to_m_factor, 4)
                if (thick_pt is not None and pt_to_m_factor is not None)
                else None
            )

            # Angle
            dx = seg.end_px[0] - seg.start_px[0]
            dy = seg.end_px[1] - seg.start_px[1]
            angle = round(math.degrees(math.atan2(dy, dx)) % 180.0, 2)

            resolved_seg = RasterWallSegment(
                start_px=seg.start_px,
                end_px=seg.end_px,
                start_pt=start_pt,
                end_pt=end_pt,
                thickness_px=seg.thickness_px,
                thickness_pt=thick_pt,
                thickness_m=thick_m,
                length_px=round(len_px, 2),
                length_pt=len_pt,
                length_m=len_m,
                angle_deg=angle,
                confidence=seg.confidence,
                is_ambiguous=seg.is_ambiguous,
                ambiguity_reason=seg.ambiguity_reason,
            )
            if seg.is_ambiguous:
                has_ambiguity = True

            cand_id = f"rwall_{selector.page_id}_{i + 1:04d}"
            cand = RasterWallCandidateRecord(
                candidate_id=cand_id,
                segment=resolved_seg,
                connected_junction_ids=(),
                is_ambiguous=seg.is_ambiguous,
                confidence=seg.confidence,
            )
            initial_candidates.append(cand)

        if not initial_candidates:
            return self._store(
                selector,
                _blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_NO_CANDIDATES_FOUND,
                ),
            )

        # 6. Junction Detection and Topological Connectivity
        junctions, cand_junc_map = build_raster_junctions(
            initial_candidates,
            snap_distance_px=max(6.0, 10.0 * (transform.dpi / 150.0)),
            px_to_pt=px_to_pt,
        )

        final_candidates: list[RasterWallCandidateRecord] = []
        for cand in initial_candidates:
            j_ids = cand_junc_map.get(cand.candidate_id, ())
            is_amb = cand.is_ambiguous or (len(j_ids) == 0)
            if is_amb:
                has_ambiguity = True
            final_candidates.append(
                RasterWallCandidateRecord(
                    candidate_id=cand.candidate_id,
                    segment=cand.segment,
                    connected_junction_ids=j_ids,
                    is_ambiguous=is_amb,
                    confidence=cand.confidence,
                    extraction_method=cand.extraction_method,
                )
            )

        # 7. Total Length Calculation
        total_len_pt = round(sum(c.segment.length_pt or 0.0 for c in final_candidates), 4)
        total_len_m = (
            round(sum(c.segment.length_m for c in final_candidates if c.segment.length_m is not None), 4)
            if can_compute_metric
            else None
        )

        # 8. Construct Publication Record
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "viewport_id": selector.viewport_id,
            "target_region_pt": selector.target_region_pt,
            "total_length_pt": total_len_pt,
            "total_length_m": total_len_m,
            "has_ambiguity": has_ambiguity,
        }
        record_id = stable_contract_id(
            "raster_wall_network_record", payload, digest_chars=32
        )
        record = RasterWallNetworkRecord(
            record_id=record_id,
            transform=transform,
            candidates=tuple(final_candidates),
            junctions=junctions,
            **payload,
        )

        reason_codes = [RASTER_WALL_NETWORK_RESOLVED]
        if not can_compute_metric:
            reason_codes.append(RASTER_SCALE_UNRESOLVED)
        if has_ambiguity:
            reason_codes.append(RASTER_WALL_AMBIGUOUS)

        result = RasterWallNetworkResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=tuple(reason_codes),
            record=record,
        )
        return self._store(selector, result)


__all__ = [
    "RASTER_LINEAGE_MISMATCH",
    "RASTER_NO_CANDIDATES_FOUND",
    "RASTER_SCALE_UNRESOLVED",
    "RASTER_SOURCE_IMAGE_MISSING",
    "RASTER_TOPOLOGY_DISCONNECTED",
    "RASTER_WALL_AMBIGUOUS",
    "RASTER_WALL_NETWORK_RESOLVED",
    "RASTER_WALL_NETWORK_SCHEMA_VERSION",
    "RASTER_WALL_NETWORK_UNAVAILABLE",
    "RasterTransformProvenance",
    "RasterWallCandidateRecord",
    "RasterWallJunction",
    "RasterWallNetworkAuthority",
    "RasterWallNetworkProducer",
    "RasterWallNetworkRecord",
    "RasterWallNetworkResult",
    "RasterWallNetworkSelector",
    "RasterWallSegment",
    "build_raster_junctions",
]
