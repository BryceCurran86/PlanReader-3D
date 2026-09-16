"""Producer-owned source-space opening/host frame authority.

This module publishes only source-space geometry (PDF points) for an exact G17
physical opening whose unique host binding has already been proved by the merged
host-binding V3 authority. It does not establish physical scale, metric geometry,
opening dimensions, vertical placement, deduction permission, or net wall area.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
import pb_opening_host_binding_authority as host_geometry
from pb_opening_host_binding_authority import (
    OPENING_HOST_BINDING_RESOLVED,
    OpeningHostBindingAuthority,
    OpeningHostBindingSelector,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityAuthority

OPENING_HOST_FRAME_SCHEMA_VERSION = "1.0.0"
OPENING_HOST_FRAME_RESOLVED = "opening_host_frame_resolved"
OPENING_HOST_FRAME_OPENING_UNAVAILABLE = "opening_host_frame_opening_unavailable"
OPENING_HOST_FRAME_HOST_UNAVAILABLE = "opening_host_frame_host_unavailable"
OPENING_HOST_FRAME_SCOPE_MISMATCH = "opening_host_frame_scope_mismatch"
OPENING_HOST_FRAME_GEOMETRY_UNAVAILABLE = "opening_host_frame_geometry_unavailable"
OPENING_HOST_FRAME_GEOMETRY_INVALID = "opening_host_frame_geometry_invalid"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_Key = tuple[str, str, str, str, str, str, str]


def _require_nonempty(value: object, field_name: str) -> str:
    clean = str(value or "").strip()
    if not clean:
        raise ValueError(f"{field_name} must be a non-empty string")
    return clean


@dataclass(frozen=True)
class OpeningHostFrameSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    opening_identity_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "opening_identity_id",
        ):
            _require_nonempty(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.page_id,
            self.decision_scope_id,
            self.opening_identity_id,
        )


@dataclass(frozen=True)
class OpeningHostFrameEvidence:
    selector: OpeningHostFrameSelector
    record_id: str
    opening_identity_id: str
    host_binding_record_id: str
    host_wall_id: str
    source_observation_ids: tuple[str, ...]
    origin_pt: tuple[float, float]
    axis_unit: tuple[float, float]
    normal_unit: tuple[float, float]
    u0_pt: float
    u1_pt: float
    wall_thickness_pt: float
    coordinate_unit: str = "pdf_point"
    schema_version: str = OPENING_HOST_FRAME_SCHEMA_VERSION


@dataclass(frozen=True)
class OpeningHostFrameResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    evidence: OpeningHostFrameEvidence | None = None
    schema_version: str = OPENING_HOST_FRAME_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    *reasons: str,
) -> OpeningHostFrameResult:
    clean = tuple(dict.fromkeys(str(reason) for reason in reasons if str(reason)))
    return OpeningHostFrameResult(
        status=status,
        reason_codes=clean or ("opening_host_frame_unavailable",),
        evidence=None,
    )


class OpeningHostFrameAuthority:
    """Sealed selector-only lookup for published source-space host frames."""

    def __init__(
        self,
        results: Mapping[_Key, OpeningHostFrameResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise ValueError("OpeningHostFrameAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: OpeningHostFrameSelector) -> OpeningHostFrameResult:
        if type(selector) is not OpeningHostFrameSelector:
            raise TypeError("selector must be OpeningHostFrameSelector")
        result = self._results.get(selector.key)
        if result is not None:
            return result
        return _blocked(
            EvidenceResolutionStatus.ABSTAINED,
            "opening_host_frame_record_unavailable",
        )


class OpeningHostFrameProducer:
    """Trusted writer that re-proves exact opening + exact host binding."""

    def __init__(
        self,
        physical_opening_authority: PhysicalOpeningAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("OpeningHostFrameProducer must be obtained from from_authorities()")
        if type(physical_opening_authority) is not PhysicalOpeningAuthority:
            raise TypeError("physical_opening_authority must be producer-owned")
        if type(physical_opening_authority.source_visibility_authority()) is not SourceVisibilityAuthority:
            raise TypeError("physical_opening_authority must be visibility-backed")
        if type(host_binding_authority) is not OpeningHostBindingAuthority:
            raise TypeError("host_binding_authority must be producer-owned")
        self._opening = physical_opening_authority
        self._host = host_binding_authority
        self._results: dict[_Key, OpeningHostFrameResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_opening_authority: PhysicalOpeningAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
    ) -> "OpeningHostFrameProducer":
        return cls(
            physical_opening_authority,
            host_binding_authority,
            _seal=_PRODUCER_SEAL,
        )

    def publish(
        self,
        *,
        opening_selector: ObservationSelector,
        host_binding_selector: OpeningHostBindingSelector,
    ) -> OpeningHostFrameResult:
        if type(opening_selector) is not ObservationSelector:
            raise TypeError("opening_selector must be ObservationSelector")
        if type(host_binding_selector) is not OpeningHostBindingSelector:
            raise TypeError("host_binding_selector must be OpeningHostBindingSelector")

        opening_result = self._opening.prove_existence(opening_selector)
        if (
            opening_result.status is not EvidenceResolutionStatus.CORROBORATED
            or opening_result.proposition != PHYSICAL_OPENING_EXISTS
            or opening_result.existence_record is None
        ):
            return _blocked(
                opening_result.status
                if opening_result.status in {
                    EvidenceResolutionStatus.ABSTAINED,
                    EvidenceResolutionStatus.CONFLICT,
                }
                else EvidenceResolutionStatus.ABSTAINED,
                OPENING_HOST_FRAME_OPENING_UNAVAILABLE,
                *opening_result.reason_codes,
            )
        opening = opening_result.existence_record

        host_result = self._host.resolve(host_binding_selector)
        if (
            host_result.status is not EvidenceResolutionStatus.CORROBORATED
            or host_result.record is None
            or OPENING_HOST_BINDING_RESOLVED not in host_result.reason_codes
        ):
            return _blocked(
                host_result.status
                if host_result.status in {
                    EvidenceResolutionStatus.ABSTAINED,
                    EvidenceResolutionStatus.CONFLICT,
                }
                else EvidenceResolutionStatus.ABSTAINED,
                OPENING_HOST_FRAME_HOST_UNAVAILABLE,
                *host_result.reason_codes,
            )
        binding = host_result.record

        lineage_matches = (
            opening.document_id == binding.document_id == host_binding_selector.document_id
            and opening.revision_id == binding.revision_id == host_binding_selector.revision_id
            and opening.source_sha256 == binding.source_sha256 == host_binding_selector.source_sha256
            and opening.snapshot_id == binding.snapshot_id == host_binding_selector.snapshot_id
            and opening.page_id == binding.page_id == host_binding_selector.page_id
            and opening.record_id == binding.opening_identity_id
            == host_binding_selector.opening_identity_id
            and binding.decision_scope_id == host_binding_selector.decision_scope_id
        )
        if not lineage_matches:
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_HOST_FRAME_SCOPE_MISMATCH,
            )

        geometry = host_geometry._opening_geometry(self._opening, opening)
        if geometry is None:
            return _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                OPENING_HOST_FRAME_GEOMETRY_UNAVAILABLE,
            )
        values = (
            *geometry.origin,
            *geometry.axis,
            *geometry.normal,
            geometry.length,
            geometry.thickness,
        )
        if (
            not all(math.isfinite(float(value)) for value in values)
            or geometry.length <= 0.0
            or geometry.thickness <= 0.0
            or not math.isclose(
                math.hypot(*geometry.axis),
                1.0,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            or not math.isclose(
                math.hypot(*geometry.normal),
                1.0,
                rel_tol=1e-9,
                abs_tol=1e-9,
            )
            or abs(geometry.axis[0] * geometry.normal[0] + geometry.axis[1] * geometry.normal[1]) > 1e-9
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                OPENING_HOST_FRAME_GEOMETRY_INVALID,
            )

        selector = OpeningHostFrameSelector(
            document_id=binding.document_id,
            revision_id=binding.revision_id,
            source_sha256=binding.source_sha256,
            snapshot_id=binding.snapshot_id,
            page_id=binding.page_id,
            decision_scope_id=binding.decision_scope_id,
            opening_identity_id=binding.opening_identity_id,
        )
        payload = {
            "selector": selector.key,
            "host_binding_record_id": binding.record_id,
            "host_wall_id": binding.host_wall_id,
            "source_observation_ids": tuple(sorted(opening.source_observation_ids)),
            "origin_pt": tuple(round(float(value), 9) for value in geometry.origin),
            "axis_unit": tuple(round(float(value), 12) for value in geometry.axis),
            "normal_unit": tuple(round(float(value), 12) for value in geometry.normal),
            "u0_pt": 0.0,
            "u1_pt": round(float(geometry.length), 9),
            "wall_thickness_pt": round(float(geometry.thickness), 9),
            "coordinate_unit": "pdf_point",
        }
        evidence = OpeningHostFrameEvidence(
            selector=selector,
            record_id=stable_contract_id("opening_host_frame_v1", payload, digest_chars=32),
            opening_identity_id=binding.opening_identity_id,
            host_binding_record_id=binding.record_id,
            host_wall_id=binding.host_wall_id,
            source_observation_ids=tuple(sorted(opening.source_observation_ids)),
            origin_pt=(float(geometry.origin[0]), float(geometry.origin[1])),
            axis_unit=(float(geometry.axis[0]), float(geometry.axis[1])),
            normal_unit=(float(geometry.normal[0]), float(geometry.normal[1])),
            u0_pt=0.0,
            u1_pt=float(geometry.length),
            wall_thickness_pt=float(geometry.thickness),
        )
        result = OpeningHostFrameResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(OPENING_HOST_FRAME_RESOLVED,),
            evidence=evidence,
        )
        existing = self._results.get(selector.key)
        if existing is not None and existing != result:
            raise RuntimeError("opening host-frame producer equivocation")
        self._results[selector.key] = result
        return result

    def authority(self) -> OpeningHostFrameAuthority:
        return OpeningHostFrameAuthority(
            MappingProxyType(dict(self._results)),
            _seal=_AUTHORITY_SEAL,
        )


__all__ = [
    "OPENING_HOST_FRAME_GEOMETRY_INVALID",
    "OPENING_HOST_FRAME_GEOMETRY_UNAVAILABLE",
    "OPENING_HOST_FRAME_HOST_UNAVAILABLE",
    "OPENING_HOST_FRAME_OPENING_UNAVAILABLE",
    "OPENING_HOST_FRAME_RESOLVED",
    "OPENING_HOST_FRAME_SCHEMA_VERSION",
    "OPENING_HOST_FRAME_SCOPE_MISMATCH",
    "OpeningHostFrameAuthority",
    "OpeningHostFrameEvidence",
    "OpeningHostFrameProducer",
    "OpeningHostFrameResult",
    "OpeningHostFrameSelector",
]
