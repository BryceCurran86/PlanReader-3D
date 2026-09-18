"""Raster wall-network authority (Item 25) — fail-closed rewrite.

Physical metric wall geometry requires:
  authenticated snapshot lineage
  → producer-owned raster wall observations (pixel segments)
  → independently authenticated PhysicalScaleAuthority
  → optional paper-space topology

Caller-provided segments, transforms, DPI, scale ratios, and page-image bags
never independently mint CORROBORATED physical wall geometry.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import hashlib
import math
from types import MappingProxyType
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_scale_authority import (
    PhysicalScaleAuthority,
    PhysicalScaleSelector,
)
from pb_source_observation_authority import PublishedSourceSnapshot

RASTER_WALL_NETWORK_SCHEMA_VERSION = "1.0.0"

RASTER_WALL_NETWORK_RESOLVED = "raster_wall_network_resolved"
RASTER_WALL_NETWORK_UNAVAILABLE = "raster_wall_network_unavailable"
RASTER_LINEAGE_MISMATCH = "raster_lineage_mismatch"
RASTER_SCALE_UNRESOLVED = "raster_scale_unresolved"
RASTER_SCALE_AMBIGUOUS = "raster_scale_ambiguous"
RASTER_TRANSFORM_AMBIGUOUS = "raster_transform_ambiguous"
RASTER_NO_OBSERVATIONS = "raster_no_observations"
RASTER_WALL_AMBIGUOUS = "raster_wall_ambiguous"
RASTER_CALLER_SEGMENTS_NOT_AUTHORITY = "raster_caller_segments_not_authority"
RASTER_CALLER_TRANSFORM_NOT_AUTHORITY = "raster_caller_transform_not_authority"
RASTER_OBSERVATION_PAGE_MISMATCH = "raster_observation_page_mismatch"
RASTER_DUPLICATE_OBSERVATION = "raster_duplicate_observation"
RASTER_NON_WALL_SEGMENT = "raster_non_wall_segment"

_OBS_PRODUCER_SEAL = object()
_OBS_AUTHORITY_SEAL = object()
_NET_PRODUCER_SEAL = object()
_NET_AUTHORITY_SEAL = object()

_NetKey = tuple[
    str, str, str, str, str, Optional[str], Optional[tuple[float, float, float, float]]
]
_ObsKey = tuple[str, str, str, str, str]


def _require_nonempty(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be a non-empty string")
    return text


def _dist(p1: tuple[float, float], p2: tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


@dataclass(frozen=True)
class RasterPixelSegment:
    """Producer-owned pixel-space wall observation (not physical metres)."""

    start_px: tuple[float, float]
    end_px: tuple[float, float]
    thickness_px: float = 0.0
    confidence: float = 0.5
    is_ambiguous: bool = False
    ambiguity_reason: Optional[str] = None
    is_wall_candidate: bool = True

    def __post_init__(self) -> None:
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be between 0.0 and 1.0")
        if _dist(self.start_px, self.end_px) <= 1e-9:
            raise ValueError("segment must have positive length")


@dataclass(frozen=True)
class RasterTransformBinding:
    """Producer-owned paper transform for one page image decode.

    DPI / px→pt come from authenticated image decode provenance, never from a
    caller ``is_scale_authoritative`` flag. Physical metres still require
    ``PhysicalScaleAuthority``.
    """

    dpi: int
    px_to_pt_ratio: float
    source_image_sha256: str

    def __post_init__(self) -> None:
        if self.dpi <= 0:
            raise ValueError("dpi must be positive")
        if self.px_to_pt_ratio <= 0.0 or not math.isfinite(self.px_to_pt_ratio):
            raise ValueError("px_to_pt_ratio must be positive finite")
        _require_nonempty(self.source_image_sha256, "source_image_sha256")


@dataclass(frozen=True)
class RasterWallObservationSelector:
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
            _require_nonempty(getattr(self, name), name)

    @property
    def key(self) -> _ObsKey:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
        )


@dataclass(frozen=True)
class RasterWallObservationRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    transform: RasterTransformBinding
    segments: tuple[RasterPixelSegment, ...]
    schema_version: str = RASTER_WALL_NETWORK_SCHEMA_VERSION

    def __post_init__(self) -> None:
        _require_nonempty(self.record_id, "record_id")
        if not self.segments:
            raise ValueError("segments must be non-empty")


@dataclass(frozen=True)
class RasterWallObservationResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[RasterWallObservationRecord] = None


def _obs_blocked(
    status: EvidenceResolutionStatus, reason: str, *extra: str
) -> RasterWallObservationResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return RasterWallObservationResult(
        status=status,
        reason_codes=tuple(dict.fromkeys([reason, *(e for e in extra if e)])),
        record=None,
    )


class RasterWallObservationAuthority:
    def __init__(
        self,
        results: Mapping[_ObsKey, RasterWallObservationResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _OBS_AUTHORITY_SEAL:
            raise TypeError("RasterWallObservationAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self, selector: RasterWallObservationSelector
    ) -> RasterWallObservationResult:
        if type(selector) is not RasterWallObservationSelector:
            raise TypeError("selector must be RasterWallObservationSelector")
        return self._results.get(
            selector.key,
            _obs_blocked(
                EvidenceResolutionStatus.ABSTAINED, RASTER_WALL_NETWORK_UNAVAILABLE
            ),
        )


class RasterWallObservationProducer:
    """Publishes producer-owned raster wall observations for exact page lineage."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _OBS_PRODUCER_SEAL:
            raise TypeError(
                "RasterWallObservationProducer must be obtained from create()"
            )
        self._results: dict[_ObsKey, RasterWallObservationResult] = {}

    @classmethod
    def create(cls) -> "RasterWallObservationProducer":
        return cls(_seal=_OBS_PRODUCER_SEAL)

    def authority(self) -> RasterWallObservationAuthority:
        return RasterWallObservationAuthority(
            self._results, _seal=_OBS_AUTHORITY_SEAL
        )

    def publish(
        self,
        selector: RasterWallObservationSelector,
        *,
        transform: RasterTransformBinding,
        segments: Sequence[RasterPixelSegment],
        snapshot: PublishedSourceSnapshot,
    ) -> RasterWallObservationResult:
        if type(selector) is not RasterWallObservationSelector:
            raise TypeError("selector must be RasterWallObservationSelector")
        if type(transform) is not RasterTransformBinding:
            raise TypeError("transform must be RasterTransformBinding")
        if type(snapshot) is not PublishedSourceSnapshot:
            raise TypeError("snapshot must be PublishedSourceSnapshot")

        rev = snapshot.revision
        snap = snapshot.snapshot
        if (
            selector.document_id != rev.document_id
            or selector.revision_id != rev.revision_id
            or selector.source_sha256 != rev.source_sha256
            or selector.snapshot_id != snap.snapshot_id
        ):
            return self._store(
                selector,
                _obs_blocked(
                    EvidenceResolutionStatus.CONFLICT, RASTER_LINEAGE_MISMATCH
                ),
            )

        expected_pt = 72.0 / float(transform.dpi)
        if abs(transform.px_to_pt_ratio - expected_pt) > 1e-6:
            return self._store(
                selector,
                _obs_blocked(
                    EvidenceResolutionStatus.CONFLICT, RASTER_TRANSFORM_AMBIGUOUS
                ),
            )

        cleaned: list[RasterPixelSegment] = []
        seen: set[tuple[float, float, float, float]] = set()
        for seg in segments:
            if type(seg) is not RasterPixelSegment:
                raise TypeError("segments must be RasterPixelSegment")
            if not seg.is_wall_candidate:
                continue
            key = (
                round(seg.start_px[0], 3),
                round(seg.start_px[1], 3),
                round(seg.end_px[0], 3),
                round(seg.end_px[1], 3),
            )
            rev_key = (key[2], key[3], key[0], key[1])
            if key in seen or rev_key in seen:
                continue
            seen.add(key)
            cleaned.append(seg)

        if not cleaned:
            return self._store(
                selector,
                _obs_blocked(
                    EvidenceResolutionStatus.ABSTAINED, RASTER_NO_OBSERVATIONS
                ),
            )

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "image_sha": transform.source_image_sha256,
            "n": len(cleaned),
        }
        record = RasterWallObservationRecord(
            record_id=stable_contract_id(
                "raster_wall_obs", payload, digest_chars=32
            ),
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            transform=transform,
            segments=tuple(cleaned),
        )
        return self._store(
            selector,
            RasterWallObservationResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(RASTER_WALL_NETWORK_RESOLVED,),
                record=record,
            ),
        )

    def _store(
        self,
        selector: RasterWallObservationSelector,
        result: RasterWallObservationResult,
    ) -> RasterWallObservationResult:
        self._results[selector.key] = result
        return result


@dataclass(frozen=True)
class RasterWallSegment:
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


@dataclass(frozen=True)
class RasterWallJunction:
    junction_id: str
    junction_type: str
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
    candidate_id: str
    segment: RasterWallSegment
    connected_junction_ids: tuple[str, ...]
    is_ambiguous: bool
    confidence: float
    extraction_method: str = "producer_raster_observation"

    def __post_init__(self) -> None:
        _require_nonempty(self.candidate_id, "candidate_id")


@dataclass(frozen=True)
class RasterWallNetworkSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str] = None
    target_region_pt: Optional[tuple[float, float, float, float]] = None

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
        ):
            _require_nonempty(getattr(self, name), name)
        if self.target_region_pt is not None:
            if len(self.target_region_pt) != 4:
                raise ValueError("target_region_pt must be a 4-tuple")
            x0, y0, x1, y1 = (float(v) for v in self.target_region_pt)
            if x1 <= x0 or y1 <= y0:
                raise ValueError("target_region_pt must have positive span")
            object.__setattr__(self, "target_region_pt", (x0, y0, x1, y1))

    @property
    def key(self) -> _NetKey:
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
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    target_region_pt: Optional[tuple[float, float, float, float]]
    transform: RasterTransformBinding
    candidates: tuple[RasterWallCandidateRecord, ...]
    junctions: tuple[RasterWallJunction, ...]
    total_length_pt: float
    total_length_m: float
    has_ambiguity: bool
    scale_evidence_id: str
    schema_version: str = RASTER_WALL_NETWORK_SCHEMA_VERSION


@dataclass(frozen=True)
class RasterWallNetworkResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[RasterWallNetworkRecord] = None


def _net_blocked(
    status: EvidenceResolutionStatus, reason: str, *extra: str
) -> RasterWallNetworkResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    return RasterWallNetworkResult(
        status=status,
        reason_codes=tuple(dict.fromkeys([reason, *(e for e in extra if e)])),
        record=None,
    )


def build_raster_junctions(
    candidates: Sequence[RasterWallCandidateRecord],
    snap_distance_px: float = 6.0,
    px_to_pt: float = 0.48,
) -> tuple[tuple[RasterWallJunction, ...], dict[str, tuple[str, ...]]]:
    endpoints: list[tuple[tuple[float, float], str]] = []
    for cand in candidates:
        endpoints.append((cand.segment.start_px, cand.candidate_id))
        endpoints.append((cand.segment.end_px, cand.candidate_id))

    clusters: list[list[tuple[tuple[float, float], str]]] = []
    for pt, cand_id in endpoints:
        matched = False
        for cluster in clusters:
            cx = sum(p[0][0] for p in cluster) / len(cluster)
            cy = sum(p[0][1] for p in cluster) / len(cluster)
            if math.hypot(pt[0] - cx, pt[1] - cy) <= snap_distance_px:
                cluster.append((pt, cand_id))
                matched = True
                break
        if not matched:
            clusters.append([(pt, cand_id)])

    junctions: list[RasterWallJunction] = []
    cand_to_junctions: dict[str, list[str]] = {
        c.candidate_id: [] for c in candidates
    }
    for idx, cluster in enumerate(clusters):
        cx = sum(p[0][0] for p in cluster) / len(cluster)
        cy = sum(p[0][1] for p in cluster) / len(cluster)
        cand_ids = tuple(dict.fromkeys(p[1] for p in cluster))
        degree = len(cand_ids)
        if degree <= 1:
            jtype = "end"
        elif degree == 2:
            jtype = "L"
        elif degree == 3:
            jtype = "T"
        elif degree == 4:
            jtype = "X"
        else:
            jtype = "multi"
        jid = f"junc_{idx + 1:04d}"
        junctions.append(
            RasterWallJunction(
                junction_id=jid,
                junction_type=jtype,
                location_px=(round(cx, 3), round(cy, 3)),
                location_pt=(round(cx * px_to_pt, 4), round(cy * px_to_pt, 4)),
                connected_candidate_ids=cand_ids,
                is_ambiguous=degree > 4,
            )
        )
        for cid in cand_ids:
            cand_to_junctions[cid].append(jid)
    return tuple(junctions), {
        k: tuple(v) for k, v in cand_to_junctions.items()
    }


class RasterWallNetworkAuthority:
    def __init__(
        self,
        results: Mapping[_NetKey, RasterWallNetworkResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _NET_AUTHORITY_SEAL:
            raise TypeError("RasterWallNetworkAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self, selector: RasterWallNetworkSelector
    ) -> RasterWallNetworkResult:
        if type(selector) is not RasterWallNetworkSelector:
            raise TypeError("selector must be RasterWallNetworkSelector")
        return self._results.get(
            selector.key,
            _net_blocked(
                EvidenceResolutionStatus.ABSTAINED, RASTER_WALL_NETWORK_UNAVAILABLE
            ),
        )


class RasterWallNetworkProducer:
    """Trusted boundary: sealed observations + PhysicalScaleAuthority only."""

    def __init__(
        self,
        observation_authority: RasterWallObservationAuthority,
        physical_scale_authority: PhysicalScaleAuthority,
        snapshot: PublishedSourceSnapshot,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _NET_PRODUCER_SEAL:
            raise TypeError(
                "RasterWallNetworkProducer must be obtained from from_authorities()"
            )
        if type(observation_authority) is not RasterWallObservationAuthority:
            raise TypeError(
                "observation_authority must be producer-owned "
                "RasterWallObservationAuthority"
            )
        if type(physical_scale_authority) is not PhysicalScaleAuthority:
            raise TypeError(
                "physical_scale_authority must be producer-owned PhysicalScaleAuthority"
            )
        if type(snapshot) is not PublishedSourceSnapshot:
            raise TypeError("snapshot must be PublishedSourceSnapshot")
        self._observations = observation_authority
        self._scale = physical_scale_authority
        self._snapshot = snapshot
        self._results: dict[_NetKey, RasterWallNetworkResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        observation_authority: RasterWallObservationAuthority,
        physical_scale_authority: PhysicalScaleAuthority,
        snapshot: PublishedSourceSnapshot,
        # Explicit reject legacy caller-authority kwargs.
        raw_candidates_by_page: object = None,
        transform_by_page: object = None,
        page_images: object = None,
    ) -> "RasterWallNetworkProducer":
        if (
            raw_candidates_by_page is not None
            or transform_by_page is not None
            or page_images is not None
        ):
            raise TypeError(
                "raw_candidates_by_page / transform_by_page / page_images are not "
                "authority inputs; publish observations via "
                "RasterWallObservationProducer"
            )
        return cls(
            observation_authority=observation_authority,
            physical_scale_authority=physical_scale_authority,
            snapshot=snapshot,
            _seal=_NET_PRODUCER_SEAL,
        )

    def authority(self) -> RasterWallNetworkAuthority:
        return RasterWallNetworkAuthority(self._results, _seal=_NET_AUTHORITY_SEAL)

    def publish(
        self, selector: RasterWallNetworkSelector
    ) -> RasterWallNetworkResult:
        if type(selector) is not RasterWallNetworkSelector:
            raise TypeError("selector must be RasterWallNetworkSelector")

        rev = self._snapshot.revision
        snap = self._snapshot.snapshot
        if (
            selector.document_id != rev.document_id
            or selector.revision_id != rev.revision_id
            or selector.source_sha256 != rev.source_sha256
            or selector.snapshot_id != snap.snapshot_id
        ):
            return self._store(
                selector,
                _net_blocked(
                    EvidenceResolutionStatus.CONFLICT, RASTER_LINEAGE_MISMATCH
                ),
            )

        obs_res = self._observations.resolve(
            RasterWallObservationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
            )
        )
        if (
            obs_res.status is not EvidenceResolutionStatus.CORROBORATED
            or obs_res.record is None
        ):
            return self._store(
                selector,
                _net_blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_NO_OBSERVATIONS,
                    *(obs_res.reason_codes or ()),
                ),
            )
        obs = obs_res.record
        if obs.page_id != selector.page_id:
            return self._store(
                selector,
                _net_blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    RASTER_OBSERVATION_PAGE_MISMATCH,
                ),
            )

        scale_res = self._scale.resolve(
            PhysicalScaleSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                viewport_id=selector.viewport_id,
            )
        )
        if scale_res.status is EvidenceResolutionStatus.CONFLICT:
            return self._store(
                selector,
                _net_blocked(
                    EvidenceResolutionStatus.CONFLICT,
                    RASTER_SCALE_AMBIGUOUS,
                    *(scale_res.reason_codes or ()),
                ),
            )
        if (
            scale_res.status is not EvidenceResolutionStatus.CORROBORATED
            or scale_res.evidence is None
        ):
            return self._store(
                selector,
                _net_blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    RASTER_SCALE_UNRESOLVED,
                    *(scale_res.reason_codes or ()),
                ),
            )

        ev = scale_res.evidence
        # Drawing scale ratio: paper_mm / physical_mm using authenticated spans.
        scale_ratio = (ev.source_span_pt * (25.4 / 72.0)) / ev.physical_span_mm
        if not math.isfinite(scale_ratio) or scale_ratio <= 0.0:
            return self._store(
                selector,
                _net_blocked(
                    EvidenceResolutionStatus.ABSTAINED, RASTER_SCALE_UNRESOLVED
                ),
            )
        pt_to_m = (0.0254 / 72.0) / scale_ratio
        px_to_pt = obs.transform.px_to_pt_ratio

        candidates: list[RasterWallCandidateRecord] = []
        has_ambiguity = False
        for i, seg in enumerate(obs.segments):
            if not seg.is_wall_candidate:
                has_ambiguity = True
                continue
            if seg.is_ambiguous:
                has_ambiguity = True
            len_px = _dist(seg.start_px, seg.end_px)
            len_pt = round(len_px * px_to_pt, 4)
            len_m = round(len_pt * pt_to_m, 4)
            start_pt = (
                round(seg.start_px[0] * px_to_pt, 4),
                round(seg.start_px[1] * px_to_pt, 4),
            )
            end_pt = (
                round(seg.end_px[0] * px_to_pt, 4),
                round(seg.end_px[1] * px_to_pt, 4),
            )
            thick_pt = (
                round(seg.thickness_px * px_to_pt, 4)
                if seg.thickness_px > 0
                else None
            )
            thick_m = (
                round(thick_pt * pt_to_m, 4) if thick_pt is not None else None
            )
            dx = seg.end_px[0] - seg.start_px[0]
            dy = seg.end_px[1] - seg.start_px[1]
            angle = round(math.degrees(math.atan2(dy, dx)) % 180.0, 2)
            resolved = RasterWallSegment(
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
            candidates.append(
                RasterWallCandidateRecord(
                    candidate_id=f"rwall_{selector.page_id}_{i + 1:04d}",
                    segment=resolved,
                    connected_junction_ids=(),
                    is_ambiguous=seg.is_ambiguous,
                    confidence=seg.confidence,
                )
            )

        if not candidates:
            return self._store(
                selector,
                _net_blocked(
                    EvidenceResolutionStatus.ABSTAINED, RASTER_NO_OBSERVATIONS
                ),
            )

        if has_ambiguity or any(c.is_ambiguous for c in candidates):
            return self._store(
                selector,
                _net_blocked(
                    EvidenceResolutionStatus.ABSTAINED, RASTER_WALL_AMBIGUOUS
                ),
            )

        junctions, jmap = build_raster_junctions(
            candidates,
            snap_distance_px=max(6.0, 10.0 * (obs.transform.dpi / 150.0)),
            px_to_pt=px_to_pt,
        )
        final: list[RasterWallCandidateRecord] = []
        for cand in candidates:
            j_ids = jmap.get(cand.candidate_id, ())
            final.append(
                RasterWallCandidateRecord(
                    candidate_id=cand.candidate_id,
                    segment=cand.segment,
                    connected_junction_ids=j_ids,
                    is_ambiguous=False,
                    confidence=cand.confidence,
                )
            )

        total_pt = round(sum(c.segment.length_pt or 0.0 for c in final), 4)
        total_m = round(sum(c.segment.length_m or 0.0 for c in final), 4)
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "total_m": total_m,
            "scale_id": ev.record_id,
        }
        record = RasterWallNetworkRecord(
            record_id=stable_contract_id(
                "raster_wall_network", payload, digest_chars=32
            ),
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            viewport_id=selector.viewport_id,
            target_region_pt=selector.target_region_pt,
            transform=obs.transform,
            candidates=tuple(final),
            junctions=junctions,
            total_length_pt=total_pt,
            total_length_m=total_m,
            has_ambiguity=False,
            scale_evidence_id=ev.record_id,
        )
        return self._store(
            selector,
            RasterWallNetworkResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(RASTER_WALL_NETWORK_RESOLVED,),
                record=record,
            ),
        )

    def _store(
        self,
        selector: RasterWallNetworkSelector,
        result: RasterWallNetworkResult,
    ) -> RasterWallNetworkResult:
        self._results[selector.key] = result
        return result


def image_bytes_sha256(image_bytes: bytes) -> str:
    return hashlib.sha256(image_bytes).hexdigest()


__all__ = [
    "RASTER_CALLER_SEGMENTS_NOT_AUTHORITY",
    "RASTER_CALLER_TRANSFORM_NOT_AUTHORITY",
    "RASTER_DUPLICATE_OBSERVATION",
    "RASTER_LINEAGE_MISMATCH",
    "RASTER_NON_WALL_SEGMENT",
    "RASTER_NO_OBSERVATIONS",
    "RASTER_OBSERVATION_PAGE_MISMATCH",
    "RASTER_SCALE_AMBIGUOUS",
    "RASTER_SCALE_UNRESOLVED",
    "RASTER_TRANSFORM_AMBIGUOUS",
    "RASTER_WALL_AMBIGUOUS",
    "RASTER_WALL_NETWORK_RESOLVED",
    "RASTER_WALL_NETWORK_SCHEMA_VERSION",
    "RASTER_WALL_NETWORK_UNAVAILABLE",
    "RasterPixelSegment",
    "RasterTransformBinding",
    "RasterWallCandidateRecord",
    "RasterWallJunction",
    "RasterWallNetworkAuthority",
    "RasterWallNetworkProducer",
    "RasterWallNetworkRecord",
    "RasterWallNetworkResult",
    "RasterWallNetworkSelector",
    "RasterWallObservationAuthority",
    "RasterWallObservationProducer",
    "RasterWallObservationRecord",
    "RasterWallObservationResult",
    "RasterWallObservationSelector",
    "RasterWallSegment",
    "build_raster_junctions",
    "image_bytes_sha256",
]
