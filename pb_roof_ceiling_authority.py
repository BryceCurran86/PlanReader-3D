"""Producer-owned, source-backed roof and ceiling evidence authority (Item 31).

Public production path:

    immutable PDF/source bytes -> SourceVisibilityProducer
    -> RoofCeilingProducer.from_source_visibility_producer(...)
    -> selector-only publish/resolve

The historical implementation derived ``ceiling_area``, ``roof_plan_area``,
``roof_pitch_deg``, ``roof_surface_area`` and ``eaves_overhang_length``
straight from an ordinary wall candidate's own free-form ``metadata`` dict
-- generic wall-candidate metadata, never independently proven roof/
elevation/section evidence. This module deletes that path entirely: it
never consults ``PhysicalWallCandidateAuthority`` or any wall candidate at
all.

``ceiling_area`` / ``roof_plan_area`` require an explicit printed area
annotation labelled with the family's own keyword
(``pb_roof_ceiling_evidence.resolve_labeled_area_m2``) -- floor area and
plan footprint are never substituted.

``eaves_overhang_length`` requires an explicit witness-bound dimension
labelled ``EAVES``/``OVERHANG``
(``pb_roof_ceiling_evidence.resolve_labeled_length_m``).

``roof_pitch_deg`` and ``roof_surface_area`` always abstain. No verified
angle-dimension evidence primitive (a real arc + leader-line witness for a
printed degree figure) exists anywhere in this codebase yet, and a bare
degree-shaped text token is not corroborated evidence -- gable-wall
metadata, an assumed default pitch, or an unverified printed angle must
never mint a firm pitch. ``roof_surface_area`` depends on a real pitch, so
it abstains for the same reason rather than falling back to plan area.
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
from pb_roof_ceiling_evidence import resolve_labeled_area_m2, resolve_labeled_length_m
from pb_source_visibility_authority import SourceVisibilityProducer

ROOF_CEILING_SCHEMA_VERSION = "2.0.0"

# Public reason codes
ROOF_CEILING_RESOLVED = "roof_ceiling_resolved"
ROOF_CEILING_UNRESOLVED = "roof_ceiling_unresolved"
ROOF_CEILING_PITCH_EVIDENCE_UNAVAILABLE = "roof_ceiling_pitch_evidence_unavailable"
ROOF_CEILING_RECORD_UNAVAILABLE = "roof_ceiling_record_unavailable"
ROOF_CEILING_SOURCE_UNAVAILABLE = "roof_ceiling_source_unavailable"
ROOF_CEILING_PAGE_UNAVAILABLE = "roof_ceiling_page_unavailable"
ROOF_CEILING_VIEWPORT_MISMATCH = "roof_ceiling_viewport_mismatch"
ROOF_CEILING_GEOMETRY_INVALID = "roof_ceiling_geometry_invalid"
ROOF_CEILING_SOURCE_INTEGRITY_FAILURE = "roof_ceiling_source_integrity_failure"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = Tuple[str, str, str, str, str, Optional[str], str, str]


class RoofCeilingFamily(str, Enum):
    """Supported roof/ceiling quantity families."""
    CEILING_AREA = "ceiling_area"
    ROOF_PLAN_AREA = "roof_plan_area"
    ROOF_PITCH_DEG = "roof_pitch_deg"
    ROOF_SURFACE_AREA = "roof_surface_area"
    EAVES_OVERHANG_LENGTH = "eaves_overhang_length"


_AREA_FAMILY_LABEL_TOKENS = {
    RoofCeilingFamily.CEILING_AREA: ("ceiling",),
    RoofCeilingFamily.ROOF_PLAN_AREA: ("roof",),
}
_LENGTH_FAMILY_LABEL_TOKENS = {
    RoofCeilingFamily.EAVES_OVERHANG_LENGTH: ("eaves", "overhang"),
}
_PITCH_DEPENDENT_FAMILIES = frozenset({RoofCeilingFamily.ROOF_PITCH_DEG, RoofCeilingFamily.ROOF_SURFACE_AREA})


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


@dataclass(frozen=True)
class RoofCeilingSelector:
    """Sealed selector identifying exactly one roof/ceiling target and family."""
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: Optional[str]
    target_id: str
    family: RoofCeilingFamily

    def __post_init__(self) -> None:
        for name in ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id", "target_id"):
            _required(getattr(self, name), name)
        if self.viewport_id is not None and not str(self.viewport_id).strip():
            raise ValueError("viewport_id must be non-empty when provided")
        if not isinstance(self.family, RoofCeilingFamily):
            raise TypeError("family must be RoofCeilingFamily")

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            None if self.viewport_id is None else str(self.viewport_id),
            self.target_id,
            self.family.value,
        )


@dataclass(frozen=True)
class RoofCeilingRecord:
    """Sealed roof/ceiling authority record."""
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    target_id: str
    family: RoofCeilingFamily
    value: float
    unit: str
    dimension_chain_id: Optional[str]
    schema_version: str = ROOF_CEILING_SCHEMA_VERSION


@dataclass(frozen=True)
class RoofCeilingResult:
    """Result of roof/ceiling authority resolution."""
    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[RoofCeilingRecord] = None
    schema_version: str = ROOF_CEILING_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> RoofCeilingResult:
    return RoofCeilingResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


def _conflict(reason: str, *extras: str) -> RoofCeilingResult:
    return RoofCeilingResult(
        status=EvidenceResolutionStatus.CONFLICT,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


class RoofCeilingAuthority:
    """Sealed selector-only lookup for published roof/ceiling records."""

    def __init__(
        self,
        results: Mapping[_Key, RoofCeilingResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("RoofCeilingAuthority is producer-owned and cannot be constructed directly")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: RoofCeilingSelector) -> RoofCeilingResult:
        if type(selector) is not RoofCeilingSelector:
            raise TypeError("selector must be RoofCeilingSelector")
        return self._results.get(
            selector.key,
            _abstained(ROOF_CEILING_RECORD_UNAVAILABLE),
        )


class RoofCeilingProducer:
    """Trusted writer boundary for roof and ceiling evidence authority.

    Consumes ONLY a producer-owned ``SourceVisibilityProducer``. Every
    value is re-resolved from that producer's own immutable PDF bytes on
    every ``publish`` call; no caller-supplied ``pitch_deg``, ``area_m2``,
    ``width_m``, ``is_sloped``, overhang, family value or evidence list is
    ever accepted.
    """

    def __init__(
        self,
        source_visibility_producer: SourceVisibilityProducer,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "RoofCeilingProducer must be obtained from from_source_visibility_producer()"
            )
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        self._source = source_visibility_producer
        self._results: dict[_Key, RoofCeilingResult] = {}

    @classmethod
    def from_source_visibility_producer(
        cls, source_visibility_producer: SourceVisibilityProducer
    ) -> "RoofCeilingProducer":
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError("source_visibility_producer must be producer-owned")
        return cls(source_visibility_producer, _seal=_PRODUCER_SEAL)

    def authority(self) -> RoofCeilingAuthority:
        return RoofCeilingAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(self, selector: RoofCeilingSelector, result: RoofCeilingResult) -> RoofCeilingResult:
        self._results[selector.key] = result
        return result

    def _source_bytes(self, selector: RoofCeilingSelector) -> Optional[bytes]:
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
            raise RuntimeError(ROOF_CEILING_SOURCE_INTEGRITY_FAILURE)
        return bytes(source_bytes)

    def publish(self, selector: RoofCeilingSelector) -> RoofCeilingResult:
        """Re-resolve authenticated roof/ceiling quantity strictly from source bytes."""
        if type(selector) is not RoofCeilingSelector:
            raise TypeError("selector must be RoofCeilingSelector")

        if selector.family in _PITCH_DEPENDENT_FAMILIES:
            # No verified angle-dimension (arc + leader witness) evidence
            # primitive exists in this codebase. A bare printed degree
            # figure or gable-wall metadata is not corroborated pitch
            # evidence -- abstain rather than assume.
            return self._store(selector, _abstained(ROOF_CEILING_PITCH_EVIDENCE_UNAVAILABLE))

        source_bytes = self._source_bytes(selector)
        if source_bytes is None:
            return self._store(selector, _abstained(ROOF_CEILING_SOURCE_UNAVAILABLE))

        try:
            page_num = int(str(selector.page_id))
        except ValueError:
            return self._store(selector, _abstained(ROOF_CEILING_PAGE_UNAVAILABLE))
        if page_num < 1:
            return self._store(selector, _abstained(ROOF_CEILING_PAGE_UNAVAILABLE))

        pdf = fitz.open(stream=source_bytes, filetype="pdf")
        try:
            page_index = page_num - 1
            if page_index >= pdf.page_count:
                return self._store(selector, _abstained(ROOF_CEILING_PAGE_UNAVAILABLE))
            page = pdf.load_page(page_index)

            dimension_chain_id: Optional[str] = None
            if selector.family in _AREA_FAMILY_LABEL_TOKENS:
                tokens = _AREA_FAMILY_LABEL_TOKENS[selector.family]
                evidence = resolve_labeled_area_m2(page, page_num=page_num, family_tokens=tokens)
                if evidence is None:
                    return self._store(selector, _abstained(ROOF_CEILING_UNRESOLVED))
                if selector.viewport_id is not None and str(selector.viewport_id) != str(evidence.view_id):
                    return self._store(selector, _abstained(ROOF_CEILING_VIEWPORT_MISMATCH))
                value = round(float(evidence.area_m2), 6)
                unit = "m2"
                view_id = evidence.view_id
            elif selector.family in _LENGTH_FAMILY_LABEL_TOKENS:
                tokens = _LENGTH_FAMILY_LABEL_TOKENS[selector.family]
                evidence = resolve_labeled_length_m(page, page_num=page_num, family_tokens=tokens)
                if evidence is None:
                    return self._store(selector, _abstained(ROOF_CEILING_UNRESOLVED))
                if selector.viewport_id is not None and str(selector.viewport_id) != str(evidence.view_id):
                    return self._store(selector, _abstained(ROOF_CEILING_VIEWPORT_MISMATCH))
                value = round(float(evidence.length_m), 6)
                unit = "m"
                view_id = evidence.view_id
                dimension_chain_id = evidence.chain_id
            else:
                return self._store(selector, _abstained(ROOF_CEILING_UNRESOLVED))

            if not (value > 0.0) or not math.isfinite(value):
                return self._store(selector, _conflict(ROOF_CEILING_GEOMETRY_INVALID))
        finally:
            pdf.close()

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "viewport_id": view_id,
            "target_id": selector.target_id,
            "family": selector.family.value,
            "value": value,
            "unit": unit,
        }
        record_id = stable_contract_id("roof_ceiling", payload, digest_chars=32)
        record = RoofCeilingRecord(
            record_id=record_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            viewport_id=view_id,
            target_id=selector.target_id,
            family=selector.family,
            value=value,
            unit=unit,
            dimension_chain_id=dimension_chain_id,
        )
        return self._store(
            selector,
            RoofCeilingResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(ROOF_CEILING_RESOLVED,),
                record=record,
            ),
        )


__all__ = [
    "ROOF_CEILING_GEOMETRY_INVALID",
    "ROOF_CEILING_PAGE_UNAVAILABLE",
    "ROOF_CEILING_PITCH_EVIDENCE_UNAVAILABLE",
    "ROOF_CEILING_RECORD_UNAVAILABLE",
    "ROOF_CEILING_RESOLVED",
    "ROOF_CEILING_SCHEMA_VERSION",
    "ROOF_CEILING_SOURCE_INTEGRITY_FAILURE",
    "ROOF_CEILING_SOURCE_UNAVAILABLE",
    "ROOF_CEILING_UNRESOLVED",
    "ROOF_CEILING_VIEWPORT_MISMATCH",
    "RoofCeilingAuthority",
    "RoofCeilingFamily",
    "RoofCeilingProducer",
    "RoofCeilingRecord",
    "RoofCeilingResult",
    "RoofCeilingSelector",
]
