"""Producer-owned physical-opening void authority.

Proves the exact physical wall-void area attributable to one authenticated
opening instance at one authenticated host wall, within one exact source
scope. A positive record requires ALL of:

1. physical opening existence + local instance identity, RE-PROVEN here from
   an ``ObservationSelector`` via ``PhysicalOpeningAuthority.prove_existence``
   -- the caller's own ``opening_record_id`` is only accepted as a lookup key
   after it is checked to equal the independently-derived existence record's
   own ``record_id``. A caller cannot mint a void by supplying an invented,
   schedule/tag/OCR/CV-derived, or merely existence-shaped opening id;
2. host-wall binding, RE-RESOLVED here through a producer-owned
   ``OpeningHostBindingAuthority`` (never a bare caller wall id);
3. width AND height independently CORROBORATED by the producer-owned
   ``OpeningDimensionAuthority`` -- never a schedule row, OCR label, nearest
   text, or default/inferred size.

This module does not decide commercial deduction eligibility, net wall area,
FIRM/commercial publication, or JobHub publication -- a physical void is not
automatically an allowable deduction. Those remain separate, later,
independently-gated authorities.

KNOWN LIMITATION (true as of this writing -- see
``OPENING_VOID_HEIGHT_UNRESOLVED`` below): ``OpeningDimensionAuthority.
resolve_height`` unconditionally returns unresolved on current main; no
opening-level height evidence source exists anywhere in the codebase yet.
Every real invocation of this authority therefore abstains today. It exists
so that void resolution requires no further design work the moment a genuine
height-evidence source lands -- not to claim an accuracy gain now.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_dimension_authority import OpeningDimensionAuthority
from pb_opening_host_binding_authority import (
    OpeningHostBindingAuthority,
    OpeningHostBindingSelector,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningAuthority
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityAuthority


PHYSICAL_OPENING_VOID_SCHEMA_VERSION = "1.0.0"
_AUTHORITY_SEAL = object()
_RecordKey = tuple[str, str, str, str, str, str]

OPENING_VOID_RESOLVED = "opening_void_resolved"
OPENING_VOID_OPENING_RECORD_ID_MISMATCH = "opening_void_opening_record_id_mismatch"
OPENING_VOID_EXISTENCE_UNRESOLVED = "opening_void_existence_unresolved"
OPENING_VOID_LINEAGE_MISMATCH = "opening_void_lineage_mismatch"
OPENING_VOID_HOST_BINDING_UNRESOLVED = "opening_void_host_binding_unresolved"
OPENING_VOID_HOST_BINDING_CONFLICT = "opening_void_host_binding_conflict"
OPENING_VOID_PAGE_SCOPE_MISMATCH = "opening_void_page_scope_mismatch"
OPENING_VOID_WIDTH_UNRESOLVED = "opening_void_width_unresolved"
OPENING_VOID_HEIGHT_UNRESOLVED = "opening_void_height_unresolved"
OPENING_VOID_NONPOSITIVE_DIMENSION = "opening_void_nonpositive_dimension"


@dataclass(frozen=True)
class PhysicalOpeningVoidSelector:
    """Read-only lookup selector; carries no dimension, host, or void proof."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    opening_record_id: str

    def __post_init__(self) -> None:
        for field_name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "decision_scope_id",
            "opening_record_id",
        ):
            _require_nonempty(getattr(self, field_name), field_name)


@dataclass(frozen=True)
class PhysicalOpeningVoidRecord:
    """Immutable producer-owned positive physical-void record."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    opening_record_id: str
    host_wall_id: str
    physical_wall_identity_id: str
    width_mm: float
    height_mm: float
    void_area_m2: float
    schema_version: str = PHYSICAL_OPENING_VOID_SCHEMA_VERSION


@dataclass(frozen=True)
class PhysicalOpeningVoidResult:
    """Resolution result at the selector-only consumer boundary."""

    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[PhysicalOpeningVoidRecord] = None
    schema_version: str = PHYSICAL_OPENING_VOID_SCHEMA_VERSION

    @property
    def void_area_m2(self) -> Optional[float]:
        return self.record.void_area_m2 if self.record is not None else None


class PhysicalOpeningVoidAuthority:
    """Sealed read-only physical-void lookup surface."""

    def __init__(
        self,
        results: Mapping[_RecordKey, PhysicalOpeningVoidResult],
        *,
        _seal: object,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("PhysicalOpeningVoidAuthority is producer-owned")
        self._results = results

    def resolve(self, selector: PhysicalOpeningVoidSelector) -> PhysicalOpeningVoidResult:
        if not isinstance(selector, PhysicalOpeningVoidSelector):
            raise TypeError("selector must be PhysicalOpeningVoidSelector")
        key = _record_key(
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
            selector.decision_scope_id,
            selector.opening_record_id,
        )
        result = self._results.get(key)
        if result is not None:
            return result
        return _blocked(
            EvidenceResolutionStatus.ABSTAINED,
            "physical_opening_void_record_unavailable",
        )


class PhysicalOpeningVoidProducer:
    """Trusted writer for exact-scope physical-opening void decisions.

    Re-proves every prerequisite from producer-owned state; never accepts a
    caller-supplied opening id, host wall id, width, or height as truth.
    """

    def __init__(self) -> None:
        self._results: dict[_RecordKey, PhysicalOpeningVoidResult] = {}

    def publish_scope(
        self,
        *,
        decision_scope_id: str,
        opening_record_id: str,
        observation_selector: ObservationSelector,
        dimension_authority: OpeningDimensionAuthority,
        visibility_authority: SourceVisibilityAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
    ) -> PhysicalOpeningVoidResult:
        _require_nonempty(decision_scope_id, "decision_scope_id")
        _require_nonempty(opening_record_id, "opening_record_id")
        if not isinstance(observation_selector, ObservationSelector):
            raise TypeError("observation_selector must be ObservationSelector")
        if not isinstance(dimension_authority, OpeningDimensionAuthority):
            raise TypeError("dimension_authority must be producer-owned OpeningDimensionAuthority")
        if type(visibility_authority) is not SourceVisibilityAuthority:
            raise TypeError("visibility_authority must be producer-owned SourceVisibilityAuthority")
        if not isinstance(host_binding_authority, OpeningHostBindingAuthority):
            raise TypeError("host_binding_authority must be producer-owned OpeningHostBindingAuthority")

        key = _record_key(
            observation_selector.document_id,
            observation_selector.revision_id,
            observation_selector.source_sha256,
            observation_selector.snapshot_id,
            decision_scope_id,
            opening_record_id,
        )

        # 1. Re-prove existence. The caller's opening_record_id is not trusted
        # until it is shown to equal the independently-derived record id.
        physical = PhysicalOpeningAuthority(visibility_authority)
        existence_result = physical.prove_existence(observation_selector)
        existence = existence_result.existence_record
        if (
            existence_result.status is not EvidenceResolutionStatus.CORROBORATED
            or existence_result.proposition != PHYSICAL_OPENING_EXISTS
            or existence is None
        ):
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_VOID_EXISTENCE_UNRESOLVED,
            ))
        if existence.record_id != opening_record_id:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_VOID_OPENING_RECORD_ID_MISMATCH,
            ))

        # 2. Re-resolve host binding through the producer-owned authority --
        # never a bare caller wall id.
        host_selector = OpeningHostBindingSelector(
            document_id=existence.document_id,
            revision_id=existence.revision_id,
            source_sha256=existence.source_sha256,
            snapshot_id=existence.snapshot_id,
            decision_scope_id=decision_scope_id,
            opening_record_id=opening_record_id,
        )
        host_result = host_binding_authority.resolve(host_selector)
        if host_result.status is EvidenceResolutionStatus.CONFLICT:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_VOID_HOST_BINDING_CONFLICT,
            ))
        if host_result.status is not EvidenceResolutionStatus.CORROBORATED or host_result.record is None:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_VOID_HOST_BINDING_UNRESOLVED,
            ))
        host_record = host_result.record
        if host_record.page_id != existence.page_id:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_VOID_PAGE_SCOPE_MISMATCH,
            ))

        # 3. Re-resolve width and height. Never a schedule row, OCR label, or
        # default/inferred size -- resolve_width/resolve_height only ever
        # corroborate a producer-owned figured dimension.
        width_result = dimension_authority.resolve_width(observation_selector)
        if width_result.status is not EvidenceResolutionStatus.CORROBORATED or not width_result.value_mm:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_VOID_WIDTH_UNRESOLVED,
            ))
        height_result = dimension_authority.resolve_height(observation_selector)
        if height_result.status is not EvidenceResolutionStatus.CORROBORATED or not height_result.value_mm:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_VOID_HEIGHT_UNRESOLVED,
            ))
        width_mm = float(width_result.value_mm)
        height_mm = float(height_result.value_mm)
        if width_mm <= 0.0 or height_mm <= 0.0:
            return self._store(key, _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_VOID_NONPOSITIVE_DIMENSION,
            ))

        void_area_m2 = round((width_mm / 1000.0) * (height_mm / 1000.0), 4)
        record_payload = {
            "schema_version": PHYSICAL_OPENING_VOID_SCHEMA_VERSION,
            "document_id": existence.document_id,
            "revision_id": existence.revision_id,
            "source_sha256": existence.source_sha256,
            "snapshot_id": existence.snapshot_id,
            "page_id": existence.page_id,
            "decision_scope_id": decision_scope_id,
            "opening_record_id": opening_record_id,
            "host_wall_id": host_record.host_wall_id,
            "physical_wall_identity_id": host_record.physical_wall_identity_id,
            "width_mm": width_mm,
            "height_mm": height_mm,
            "void_area_m2": void_area_m2,
        }
        record = PhysicalOpeningVoidRecord(
            record_id=stable_contract_id("opening_void", record_payload),
            document_id=existence.document_id,
            revision_id=existence.revision_id,
            source_sha256=existence.source_sha256,
            snapshot_id=existence.snapshot_id,
            page_id=existence.page_id,
            decision_scope_id=decision_scope_id,
            opening_record_id=opening_record_id,
            host_wall_id=host_record.host_wall_id,
            physical_wall_identity_id=host_record.physical_wall_identity_id,
            width_mm=width_mm,
            height_mm=height_mm,
            void_area_m2=void_area_m2,
        )
        return self._store(
            key,
            PhysicalOpeningVoidResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=(OPENING_VOID_RESOLVED,),
                record=record,
            ),
        )

    def authority(self) -> PhysicalOpeningVoidAuthority:
        return PhysicalOpeningVoidAuthority(
            MappingProxyType(dict(self._results)),
            _seal=_AUTHORITY_SEAL,
        )

    def _store(
        self,
        key: _RecordKey,
        result: PhysicalOpeningVoidResult,
    ) -> PhysicalOpeningVoidResult:
        existing = self._results.get(key)
        if existing is not None and existing != result:
            raise RuntimeError("physical opening void producer equivocation")
        self._results[key] = result
        return result


def _record_key(
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    decision_scope_id: str,
    opening_record_id: str,
) -> _RecordKey:
    return (
        str(document_id),
        str(revision_id),
        str(source_sha256),
        str(snapshot_id),
        str(decision_scope_id),
        str(opening_record_id),
    )


def _blocked(
    status: EvidenceResolutionStatus,
    *reason_codes: str,
) -> PhysicalOpeningVoidResult:
    cleaned = tuple(dict.fromkeys(str(code) for code in reason_codes if str(code)))
    return PhysicalOpeningVoidResult(
        status=status,
        reason_codes=cleaned or ("physical_opening_void_unavailable",),
        record=None,
    )


def _require_nonempty(value: object, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


__all__ = [
    "PHYSICAL_OPENING_VOID_SCHEMA_VERSION",
    "OPENING_VOID_RESOLVED",
    "OPENING_VOID_OPENING_RECORD_ID_MISMATCH",
    "OPENING_VOID_EXISTENCE_UNRESOLVED",
    "OPENING_VOID_LINEAGE_MISMATCH",
    "OPENING_VOID_HOST_BINDING_UNRESOLVED",
    "OPENING_VOID_HOST_BINDING_CONFLICT",
    "OPENING_VOID_PAGE_SCOPE_MISMATCH",
    "OPENING_VOID_WIDTH_UNRESOLVED",
    "OPENING_VOID_HEIGHT_UNRESOLVED",
    "OPENING_VOID_NONPOSITIVE_DIMENSION",
    "PhysicalOpeningVoidAuthority",
    "PhysicalOpeningVoidProducer",
    "PhysicalOpeningVoidRecord",
    "PhysicalOpeningVoidResult",
    "PhysicalOpeningVoidSelector",
]
