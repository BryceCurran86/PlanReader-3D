"""Producer-owned, source-backed secondary footprint & verandah authority (Item 29).

Production contract (frozen by the Item 29 V2 validator, see
``tests/test_secondary_footprint_source_backed_redteam_v2.py``):

    immutable PDF bytes -> SourceVisibilityProducer
    -> SecondaryFootprintProducer.from_source_visibility_producer(...)
    -> selector-only publish/resolve

``publish`` takes only a selector. It never accepts a caller-supplied
polygon, category, width, area, confidence or evidence list. Every physical
quantity is re-derived, on every publish, directly from the immutable PDF
bytes this producer's own ``SourceVisibilityProducer`` already ingested:

* the verandah *depth* comes from the existing witness-bound F.23 resolver
  (``pb_secondary_footprint_evidence.resolve_secondary_footprint_width_m``),
  which already fails closed on regex-only prose, one-sided witnesses and
  competing depths;
* the verandah *width* (the span along the building edge the label is
  adjoining) is derived from that same viewport's own bounding box, scaled
  by the points-per-metre ratio implied by the depth dimension's own drawn
  geometry versus its authenticated physical value. No separate width
  dimension, scale bar or caller-supplied ratio is required or accepted.

This is a provisional width proxy (the owning viewport's own edge span, not
a dedicated width dimension) and is documented as such rather than silently
presented as more precise than it is; area/perimeter therefore describe the
verandah's *containing plan viewport* span in the depth direction, not a
hand-traced polygon.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import math
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

import fitz

from pb_dimension_graph_constraint_engine import DimensionOrientation
from pb_figured_dimension_evidence import extract_dimension_evidence_bundle
from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_secondary_footprint_evidence import resolve_secondary_footprint_width_m
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_segmentation import ViewportSegmentationStatus, segment_page_viewports

SECONDARY_FOOTPRINT_SCHEMA_VERSION = "2.0.0"

# Public reason codes
SECONDARY_FOOTPRINT_RESOLVED = "secondary_footprint_resolved"
SECONDARY_FOOTPRINT_UNRESOLVED = "secondary_footprint_unresolved"
SECONDARY_FOOTPRINT_RECORD_UNAVAILABLE = "secondary_footprint_record_unavailable"
SECONDARY_FOOTPRINT_SOURCE_UNAVAILABLE = "secondary_footprint_source_unavailable"
SECONDARY_FOOTPRINT_PAGE_UNAVAILABLE = "secondary_footprint_page_unavailable"
SECONDARY_FOOTPRINT_VIEWPORT_MISMATCH = "secondary_footprint_viewport_mismatch"
SECONDARY_FOOTPRINT_GEOMETRY_UNAVAILABLE = "secondary_footprint_geometry_unavailable"
SECONDARY_FOOTPRINT_GEOMETRY_INVALID = "secondary_footprint_geometry_invalid"
SECONDARY_FOOTPRINT_SOURCE_INTEGRITY_FAILURE = "secondary_footprint_source_integrity_failure"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = Tuple[str, str, str, str, str, Optional[str], str]


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


class FootprintCategory(str, Enum):
    """Classification of a secondary building footprint component."""
    VERANDAH = "verandah"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class SecondaryFootprintSelector:
    """Sealed selector identifying exactly one secondary footprint component."""
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    secondary_space_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "secondary_space_id",
        ):
            _required(getattr(self, name), name)
        if self.viewport_id is not None and not str(self.viewport_id).strip():
            raise ValueError("viewport_id must be non-empty when provided")

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            None if self.viewport_id is None else str(self.viewport_id),
            self.secondary_space_id,
        )


@dataclass(frozen=True)
class SecondaryFootprintRecord:
    """Sealed record proving authenticated secondary footprint geometry."""
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    secondary_space_id: str
    category: FootprintCategory
    area_m2: float
    perimeter_m: float
    width_m: float
    depth_m: float
    edge: str
    dimension_chain_id: str
    binding_status: str
    schema_version: str = SECONDARY_FOOTPRINT_SCHEMA_VERSION


@dataclass(frozen=True)
class SecondaryFootprintResult:
    """Result of secondary footprint authority resolution."""
    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[SecondaryFootprintRecord] = None
    schema_version: str = SECONDARY_FOOTPRINT_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> SecondaryFootprintResult:
    return SecondaryFootprintResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


def _conflict(reason: str, *extras: str) -> SecondaryFootprintResult:
    return SecondaryFootprintResult(
        status=EvidenceResolutionStatus.CONFLICT,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


class SecondaryFootprintAuthority:
    """Sealed selector-only lookup for published secondary footprint records."""

    def __init__(
        self,
        results: Mapping[_Key, SecondaryFootprintResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("SecondaryFootprintAuthority is producer-owned and cannot be constructed directly")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: SecondaryFootprintSelector) -> SecondaryFootprintResult:
        if type(selector) is not SecondaryFootprintSelector:
            raise TypeError("selector must be SecondaryFootprintSelector")
        return self._results.get(
            selector.key,
            _abstained(SECONDARY_FOOTPRINT_RECORD_UNAVAILABLE),
        )


class SecondaryFootprintProducer:
    """Trusted writer boundary for secondary footprint & verandah authority.

    Consumes ONLY a producer-owned ``SourceVisibilityProducer``. Every
    physical quantity is re-resolved from that producer's own immutable PDF
    bytes on every ``publish`` call; no caller-supplied polygon, category,
    width, area or evidence list is ever accepted.
    """

    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "SecondaryFootprintProducer must be obtained from from_source_visibility_producer()"
            )
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        self._source = source_visibility_producer
        self._results: dict[_Key, SecondaryFootprintResult] = {}

    @classmethod
    def from_source_visibility_producer(
        cls, source_visibility_producer: SourceVisibilityProducer
    ) -> "SecondaryFootprintProducer":
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        return cls(source_visibility_producer, _seal=_PRODUCER_SEAL)

    def authority(self) -> SecondaryFootprintAuthority:
        return SecondaryFootprintAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: SecondaryFootprintSelector,
        result: SecondaryFootprintResult,
    ) -> SecondaryFootprintResult:
        self._results[selector.key] = result
        return result

    def _source_bytes(self, selector: SecondaryFootprintSelector) -> Optional[bytes]:
        published = self._source.published_snapshot_for_revision(selector.revision_id)
        if published is None:
            return None
        if (
            published.revision.document_id != selector.document_id
            or published.revision.source_sha256 != selector.source_sha256
            or published.snapshot.snapshot_id != selector.snapshot_id
            or self._source._producer.current_revision_id(selector.document_id) != selector.revision_id
        ):
            return None
        source_bytes = self._source._producer._store.source_bytes_by_revision.get(selector.revision_id)
        if source_bytes is None or hashlib.sha256(source_bytes).hexdigest() != selector.source_sha256:
            raise RuntimeError(SECONDARY_FOOTPRINT_SOURCE_INTEGRITY_FAILURE)
        return bytes(source_bytes)

    def publish(self, selector: SecondaryFootprintSelector) -> SecondaryFootprintResult:
        """Re-resolve authenticated secondary footprint geometry strictly from source bytes."""
        if type(selector) is not SecondaryFootprintSelector:
            raise TypeError("selector must be SecondaryFootprintSelector")

        source_bytes = self._source_bytes(selector)
        if source_bytes is None:
            return self._store(selector, _abstained(SECONDARY_FOOTPRINT_SOURCE_UNAVAILABLE))

        try:
            page_num = int(str(selector.page_id))
        except ValueError:
            return self._store(selector, _abstained(SECONDARY_FOOTPRINT_PAGE_UNAVAILABLE))
        if page_num < 1:
            return self._store(selector, _abstained(SECONDARY_FOOTPRINT_PAGE_UNAVAILABLE))

        pdf = fitz.open(stream=source_bytes, filetype="pdf")
        try:
            page_index = page_num - 1
            if page_index >= pdf.page_count:
                return self._store(selector, _abstained(SECONDARY_FOOTPRINT_PAGE_UNAVAILABLE))
            page = pdf.load_page(page_index)

            evidence = resolve_secondary_footprint_width_m(page, page_num=page_num)
            if evidence is None:
                return self._store(selector, _abstained(SECONDARY_FOOTPRINT_UNRESOLVED))
            if (
                selector.viewport_id is not None
                and str(selector.viewport_id) != str(evidence.view_id)
            ):
                return self._store(selector, _abstained(SECONDARY_FOOTPRINT_VIEWPORT_MISMATCH))

            label = str(evidence.label_text or "").strip().lower()
            if label not in ("verandah", "veranda"):
                return self._store(selector, _abstained(SECONDARY_FOOTPRINT_UNRESOLVED))
            category = FootprintCategory.VERANDAH

            viewports = segment_page_viewports(page, page_number=page_num)
            viewport = next(
                (
                    v
                    for v in viewports
                    if v.view_id == evidence.view_id
                    and v.bounding_box is not None
                    and v.status
                    in {
                        ViewportSegmentationStatus.RESOLVED.value,
                        ViewportSegmentationStatus.DERIVED.value,
                    }
                ),
                None,
            )
            if viewport is None or viewport.bounding_box is None:
                return self._store(selector, _abstained(SECONDARY_FOOTPRINT_GEOMETRY_UNAVAILABLE))
            vx0, vy0, vx1, vy1 = (float(v) for v in viewport.bounding_box)

            bundle = extract_dimension_evidence_bundle(
                page,
                page_num=page_num,
                view_id=viewport.view_id,
                view_type=viewport.view_type,
            )
            depth_obs = next(
                (o for o in bundle.observations if o.dimension_id == evidence.chain_id),
                None,
            )
            if depth_obs is None or depth_obs.bbox is None:
                return self._store(selector, _abstained(SECONDARY_FOOTPRINT_GEOMETRY_UNAVAILABLE))
            dbx0, dby0, dbx1, dby1 = (float(v) for v in depth_obs.bbox)

            if evidence.depth_orientation == DimensionOrientation.VERTICAL.value:
                depth_span_pt = abs(dby1 - dby0)
                edge_span_pt = abs(vx1 - vx0)
            else:
                depth_span_pt = abs(dbx1 - dbx0)
                edge_span_pt = abs(vy1 - vy0)

            if not (depth_span_pt > 0.0) or not math.isfinite(depth_span_pt):
                return self._store(selector, _conflict(SECONDARY_FOOTPRINT_GEOMETRY_INVALID))

            m_per_pt = float(evidence.width_m) / depth_span_pt
            if not math.isfinite(m_per_pt) or m_per_pt <= 0.0:
                return self._store(selector, _conflict(SECONDARY_FOOTPRINT_GEOMETRY_INVALID))

            depth_m = round(float(evidence.width_m), 6)
            width_m = round(edge_span_pt * m_per_pt, 6)
            if not (depth_m > 0.0 and width_m > 0.0):
                return self._store(selector, _conflict(SECONDARY_FOOTPRINT_GEOMETRY_INVALID))

            area_m2 = round(width_m * depth_m, 6)
            perimeter_m = round(2.0 * (width_m + depth_m), 6)
        finally:
            pdf.close()

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "viewport_id": evidence.view_id,
            "secondary_space_id": selector.secondary_space_id,
            "category": category.value,
            "area_m2": area_m2,
            "perimeter_m": perimeter_m,
        }
        record_id = stable_contract_id("secondary_footprint", payload, digest_chars=32)
        record = SecondaryFootprintRecord(
            record_id=record_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            viewport_id=evidence.view_id,
            secondary_space_id=selector.secondary_space_id,
            category=category,
            area_m2=area_m2,
            perimeter_m=perimeter_m,
            width_m=width_m,
            depth_m=depth_m,
            edge=evidence.edge,
            dimension_chain_id=evidence.chain_id,
            binding_status=evidence.binding_status,
        )
        return self._store(
            selector,
            SecondaryFootprintResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(SECONDARY_FOOTPRINT_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "FootprintCategory",
    "SECONDARY_FOOTPRINT_GEOMETRY_INVALID",
    "SECONDARY_FOOTPRINT_GEOMETRY_UNAVAILABLE",
    "SECONDARY_FOOTPRINT_PAGE_UNAVAILABLE",
    "SECONDARY_FOOTPRINT_RECORD_UNAVAILABLE",
    "SECONDARY_FOOTPRINT_RESOLVED",
    "SECONDARY_FOOTPRINT_SCHEMA_VERSION",
    "SECONDARY_FOOTPRINT_SOURCE_INTEGRITY_FAILURE",
    "SECONDARY_FOOTPRINT_SOURCE_UNAVAILABLE",
    "SECONDARY_FOOTPRINT_UNRESOLVED",
    "SECONDARY_FOOTPRINT_VIEWPORT_MISMATCH",
    "SecondaryFootprintAuthority",
    "SecondaryFootprintProducer",
    "SecondaryFootprintRecord",
    "SecondaryFootprintResult",
    "SecondaryFootprintSelector",
]
