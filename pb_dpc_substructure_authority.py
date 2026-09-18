"""Producer-owned, source-backed DPC and substructure quantity authority (Item 30).

Public production path:

    immutable PDF/source bytes -> SourceVisibilityProducer
    -> DPCSubstructureProducer.from_source_visibility_producer(...)
    -> selector-only publish/resolve

An ordinary superstructure wall candidate does NOT prove a DPC, foundation
or strip-footing proposition. This module never consults
``PhysicalWallCandidateAuthority`` or any generic wall/perimeter length at
all -- every run length is re-derived, on every publish, from an explicit,
witness-bound family-labelled dimension callout
(``pb_substructure_run_evidence.resolve_substructure_run_length_m``) found
directly in this producer's own immutable PDF bytes. If no such callout
exists, the authority abstains; it never substitutes wall or perimeter
geometry, and never invents a default footing width or depth.

``SUBSTRUCTURE_WALL_AREA`` additionally requires a *separate*, independently
witness-bound depth/height callout in the same viewport (real section/detail
evidence); without one it abstains with
``DPC_SUBSTRUCTURE_MISSING_SECTION_DETAIL`` rather than assuming a depth.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import math
from types import MappingProxyType
from typing import Mapping, Optional, Tuple

import fitz

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_substructure_run_evidence import resolve_substructure_run_length_m

DPC_SUBSTRUCTURE_SCHEMA_VERSION = "2.0.0"

# Public reason codes
DPC_SUBSTRUCTURE_RESOLVED = "dpc_substructure_resolved"
DPC_SUBSTRUCTURE_UNRESOLVED = "dpc_substructure_unresolved"
DPC_SUBSTRUCTURE_MISSING_SECTION_DETAIL = "dpc_substructure_missing_section_detail"
DPC_SUBSTRUCTURE_RECORD_UNAVAILABLE = "dpc_substructure_record_unavailable"
DPC_SUBSTRUCTURE_SOURCE_UNAVAILABLE = "dpc_substructure_source_unavailable"
DPC_SUBSTRUCTURE_PAGE_UNAVAILABLE = "dpc_substructure_page_unavailable"
DPC_SUBSTRUCTURE_VIEWPORT_MISMATCH = "dpc_substructure_viewport_mismatch"
DPC_SUBSTRUCTURE_GEOMETRY_INVALID = "dpc_substructure_geometry_invalid"
DPC_SUBSTRUCTURE_SOURCE_INTEGRITY_FAILURE = "dpc_substructure_source_integrity_failure"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = Tuple[str, str, str, str, str, Optional[str], str, str]

_DEPTH_TOKENS: Tuple[str, ...] = ("depth", "height")


class SubstructureFamily(str, Enum):
    """Supported substructure quantity families."""
    DPC_LENGTH = "dpc_length"
    FOUNDATION_WALL_LENGTH = "foundation_wall_length"
    STRIP_FOOTING_LENGTH = "strip_footing_length"
    SUBSTRUCTURE_WALL_AREA = "substructure_wall_area"


_FAMILY_LABEL_TOKENS: Mapping[SubstructureFamily, Tuple[str, ...]] = {
    SubstructureFamily.DPC_LENGTH: ("dpc",),
    SubstructureFamily.FOUNDATION_WALL_LENGTH: ("foundation",),
    SubstructureFamily.STRIP_FOOTING_LENGTH: ("footing",),
    SubstructureFamily.SUBSTRUCTURE_WALL_AREA: ("foundation",),
}


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


@dataclass(frozen=True)
class DPCSubstructureSelector:
    """Sealed selector identifying exactly one physical substructure run and family."""
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    physical_run_id: str
    family: SubstructureFamily

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "physical_run_id",
        ):
            _required(getattr(self, name), name)
        if self.viewport_id is not None and not str(self.viewport_id).strip():
            raise ValueError("viewport_id must be non-empty when provided")
        if not isinstance(self.family, SubstructureFamily):
            raise TypeError("family must be SubstructureFamily")

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            None if self.viewport_id is None else str(self.viewport_id),
            self.physical_run_id,
            self.family.value,
        )


@dataclass(frozen=True)
class DPCSubstructureRecord:
    """Sealed DPC/substructure quantity record."""
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    physical_run_id: str
    family: SubstructureFamily
    value: float
    unit: str
    dimension_chain_id: str
    depth_dimension_chain_id: Optional[str]
    binding_status: str
    schema_version: str = DPC_SUBSTRUCTURE_SCHEMA_VERSION


@dataclass(frozen=True)
class DPCSubstructureResult:
    """Result of DPC/substructure authority resolution."""
    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[DPCSubstructureRecord] = None
    schema_version: str = DPC_SUBSTRUCTURE_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> DPCSubstructureResult:
    return DPCSubstructureResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


def _conflict(reason: str, *extras: str) -> DPCSubstructureResult:
    return DPCSubstructureResult(
        status=EvidenceResolutionStatus.CONFLICT,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


class DPCSubstructureAuthority:
    """Sealed selector-only lookup for published DPC/substructure records."""

    def __init__(
        self,
        results: Mapping[_Key, DPCSubstructureResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("DPCSubstructureAuthority is producer-owned and cannot be constructed directly")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: DPCSubstructureSelector) -> DPCSubstructureResult:
        if type(selector) is not DPCSubstructureSelector:
            raise TypeError("selector must be DPCSubstructureSelector")
        return self._results.get(
            selector.key,
            _abstained(DPC_SUBSTRUCTURE_RECORD_UNAVAILABLE),
        )


class DPCSubstructureProducer:
    """Trusted writer boundary for DPC and substructure quantity authority.

    Consumes ONLY a producer-owned ``SourceVisibilityProducer``. Every
    physical quantity is re-resolved from that producer's own immutable PDF
    bytes on every ``publish`` call; no caller-supplied family value,
    physical-run identity, length, depth or evidence list is ever accepted.
    """

    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "DPCSubstructureProducer must be obtained from from_source_visibility_producer()"
            )
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        self._source = source_visibility_producer
        self._results: dict[_Key, DPCSubstructureResult] = {}

    @classmethod
    def from_source_visibility_producer(
        cls, source_visibility_producer: SourceVisibilityProducer
    ) -> "DPCSubstructureProducer":
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        return cls(source_visibility_producer, _seal=_PRODUCER_SEAL)

    def authority(self) -> DPCSubstructureAuthority:
        return DPCSubstructureAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: DPCSubstructureSelector,
        result: DPCSubstructureResult,
    ) -> DPCSubstructureResult:
        self._results[selector.key] = result
        return result

    def _source_bytes(self, selector: DPCSubstructureSelector) -> Optional[bytes]:
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
            raise RuntimeError(DPC_SUBSTRUCTURE_SOURCE_INTEGRITY_FAILURE)
        return bytes(source_bytes)

    def publish(self, selector: DPCSubstructureSelector) -> DPCSubstructureResult:
        """Re-resolve authenticated DPC/substructure quantity strictly from source bytes."""
        if type(selector) is not DPCSubstructureSelector:
            raise TypeError("selector must be DPCSubstructureSelector")

        source_bytes = self._source_bytes(selector)
        if source_bytes is None:
            return self._store(selector, _abstained(DPC_SUBSTRUCTURE_SOURCE_UNAVAILABLE))

        try:
            page_num = int(str(selector.page_id))
        except ValueError:
            return self._store(selector, _abstained(DPC_SUBSTRUCTURE_PAGE_UNAVAILABLE))
        if page_num < 1:
            return self._store(selector, _abstained(DPC_SUBSTRUCTURE_PAGE_UNAVAILABLE))

        pdf = fitz.open(stream=source_bytes, filetype="pdf")
        try:
            page_index = page_num - 1
            if page_index >= pdf.page_count:
                return self._store(selector, _abstained(DPC_SUBSTRUCTURE_PAGE_UNAVAILABLE))
            page = pdf.load_page(page_index)

            run_tokens = _FAMILY_LABEL_TOKENS[selector.family]
            evidence = resolve_substructure_run_length_m(page, page_num=page_num, family_tokens=run_tokens)
            if evidence is None:
                return self._store(selector, _abstained(DPC_SUBSTRUCTURE_UNRESOLVED))
            if (
                selector.viewport_id is not None
                and str(selector.viewport_id) != str(evidence.view_id)
            ):
                return self._store(selector, _abstained(DPC_SUBSTRUCTURE_VIEWPORT_MISMATCH))

            length_m = round(float(evidence.length_m), 6)
            if not (length_m > 0.0) or not math.isfinite(length_m):
                return self._store(selector, _conflict(DPC_SUBSTRUCTURE_GEOMETRY_INVALID))

            depth_chain_id: Optional[str] = None
            if selector.family == SubstructureFamily.SUBSTRUCTURE_WALL_AREA:
                depth_evidence = resolve_substructure_run_length_m(
                    page, page_num=page_num, family_tokens=_DEPTH_TOKENS
                )
                if depth_evidence is None or depth_evidence.view_id != evidence.view_id:
                    return self._store(selector, _abstained(DPC_SUBSTRUCTURE_MISSING_SECTION_DETAIL))
                depth_m = round(float(depth_evidence.length_m), 6)
                if not (depth_m > 0.0) or not math.isfinite(depth_m):
                    return self._store(selector, _conflict(DPC_SUBSTRUCTURE_GEOMETRY_INVALID))
                value = round(length_m * depth_m, 6)
                unit = "m2"
                depth_chain_id = depth_evidence.chain_id
            else:
                value = length_m
                unit = "m"
        finally:
            pdf.close()

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "viewport_id": evidence.view_id,
            "physical_run_id": selector.physical_run_id,
            "family": selector.family.value,
            "value": value,
            "unit": unit,
        }
        record_id = stable_contract_id("dpc_substructure", payload, digest_chars=32)
        record = DPCSubstructureRecord(
            record_id=record_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            viewport_id=evidence.view_id,
            physical_run_id=selector.physical_run_id,
            family=selector.family,
            value=value,
            unit=unit,
            dimension_chain_id=evidence.chain_id,
            depth_dimension_chain_id=depth_chain_id,
            binding_status=evidence.binding_status,
        )
        return self._store(
            selector,
            DPCSubstructureResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(DPC_SUBSTRUCTURE_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "DPC_SUBSTRUCTURE_GEOMETRY_INVALID",
    "DPC_SUBSTRUCTURE_MISSING_SECTION_DETAIL",
    "DPC_SUBSTRUCTURE_PAGE_UNAVAILABLE",
    "DPC_SUBSTRUCTURE_RECORD_UNAVAILABLE",
    "DPC_SUBSTRUCTURE_RESOLVED",
    "DPC_SUBSTRUCTURE_SCHEMA_VERSION",
    "DPC_SUBSTRUCTURE_SOURCE_INTEGRITY_FAILURE",
    "DPC_SUBSTRUCTURE_SOURCE_UNAVAILABLE",
    "DPC_SUBSTRUCTURE_UNRESOLVED",
    "DPC_SUBSTRUCTURE_VIEWPORT_MISMATCH",
    "DPCSubstructureAuthority",
    "DPCSubstructureProducer",
    "DPCSubstructureRecord",
    "DPCSubstructureResult",
    "DPCSubstructureSelector",
    "SubstructureFamily",
]
