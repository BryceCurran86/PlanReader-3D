"""Producer-owned physical opening void authority.

This module proves one proposition only: an authenticated physical opening
creates one rectangular rough-opening void in an authenticated host-wall frame.
It does not authorize a commercial deduction, a finish or assembly effect, a
net-wall quantity, or publication outside this evidence boundary.

The public producer accepts selectors only.  Every positive value is re-resolved
from sealed upstream authorities and joined on the exact physical-opening record
identity and source lineage.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Mapping

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_opening_dimension_authority import (
    OPENING_WIDTH_RESOLVED,
    OpeningDimensionAuthority,
)
from pb_opening_height_authority import (
    OPENING_HEIGHT_RESOLVED,
    OpeningHeightAuthority,
    OpeningHeightSelector,
)
from pb_opening_host_binding_authority import (
    OPENING_HOST_BINDING_RESOLVED,
    OpeningHostBindingAuthority,
    OpeningHostBindingSelector,
)
from pb_opening_host_frame_authority import (
    OPENING_HOST_FRAME_RESOLVED,
    OpeningHostFrameAuthority,
    OpeningHostFrameSelector,
)
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseSelector,
)
from pb_opening_vertical_placement_authority import (
    OPENING_VERTICAL_PLACEMENT_RESOLVED,
    OpeningVerticalPlacementAuthority,
    OpeningVerticalPlacementSelector,
)
from pb_physical_opening_authority import (
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
)
from pb_physical_scale_authority import (
    PHYSICAL_SCALE_RESOLVED,
    PhysicalScaleAuthority,
    PhysicalScaleSelector,
)
from pb_source_observation_authority import ObservationSelector


PHYSICAL_OPENING_VOID_SCHEMA_VERSION = "2.0.0"

PHYSICAL_OPENING_VOID_RESOLVED = "physical_opening_void_resolved"
PHYSICAL_OPENING_VOID_OPENING_UNRESOLVED = "physical_opening_void_opening_unresolved"
PHYSICAL_OPENING_VOID_HOST_UNRESOLVED = "physical_opening_void_host_unresolved"
PHYSICAL_OPENING_VOID_HOST_CONFLICT = "physical_opening_void_host_conflict"
PHYSICAL_OPENING_VOID_WIDTH_UNRESOLVED = "physical_opening_void_width_unresolved"
PHYSICAL_OPENING_VOID_HEIGHT_UNRESOLVED = "physical_opening_void_height_unresolved"
PHYSICAL_OPENING_VOID_VERTICAL_PLACEMENT_UNRESOLVED = (
    "physical_opening_void_vertical_placement_unresolved"
)
PHYSICAL_OPENING_VOID_FRAME_UNRESOLVED = "physical_opening_void_frame_unresolved"
PHYSICAL_OPENING_VOID_UNIT_MAPPING_UNRESOLVED = (
    "physical_opening_void_unit_mapping_unresolved"
)
PHYSICAL_OPENING_VOID_UNIVERSE_INCOMPLETE = "physical_opening_void_universe_incomplete"
PHYSICAL_OPENING_VOID_PROFILE_UNSUPPORTED = "physical_opening_void_profile_unsupported"
PHYSICAL_OPENING_VOID_GEOMETRY_CONFLICT = "physical_opening_void_geometry_conflict"
PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH = "physical_opening_void_lineage_mismatch"

RECTANGULAR_ROUGH_OPENING = "rectangular_rough_opening"
METRE = "metre"

_AUTHORITY_SEAL = object()
_PRODUCER_SEAL = object()
_Key = tuple[str, str, str, str, str, str, str]


@dataclass(frozen=True)
class PhysicalOpeningVoidSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    opening_identity_id: str

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
class PhysicalOpeningVoidRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    viewport_id: str | None
    decision_scope_id: str
    opening_identity_id: str
    host_binding_record_id: str
    host_wall_id: str
    opening_universe_record_id: str
    width_record_id: str
    height_record_id: str
    wall_local_frame_id: str
    unit_mapping_record_id: str
    vertical_placement_record_id: str
    profile_kind: str
    coordinate_unit: str
    u0: float
    u1: float
    z0: float
    z1: float
    schema_version: str = PHYSICAL_OPENING_VOID_SCHEMA_VERSION


@dataclass(frozen=True)
class PhysicalOpeningVoidResult:
    status: EvidenceResolutionStatus
    reason_codes: frozenset[str]
    record: PhysicalOpeningVoidRecord | None
    schema_version: str = PHYSICAL_OPENING_VOID_SCHEMA_VERSION


def _blocked(
    status: EvidenceResolutionStatus,
    reason: str,
    *upstream_reasons: str,
) -> PhysicalOpeningVoidResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    reasons = frozenset(
        [reason, *(str(item) for item in upstream_reasons if str(item))]
    )
    return PhysicalOpeningVoidResult(status=status, reason_codes=reasons, record=None)


def _lineage_matches(selector: PhysicalOpeningVoidSelector, record: object) -> bool:
    return all(
        getattr(record, name, None) == getattr(selector, name)
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
        )
    )


def _evidence_id(prefix: str, evidence: object) -> str:
    return stable_contract_id(prefix, evidence, digest_chars=32)


class PhysicalOpeningVoidAuthority:
    """Sealed selector-only lookup for published physical void records."""

    def __init__(
        self,
        results: Mapping[_Key, PhysicalOpeningVoidResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("PhysicalOpeningVoidAuthority is producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector: PhysicalOpeningVoidSelector) -> PhysicalOpeningVoidResult:
        if type(selector) is not PhysicalOpeningVoidSelector:
            raise TypeError("selector must be PhysicalOpeningVoidSelector")
        return self._results.get(
            selector.key,
            _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                PHYSICAL_OPENING_VOID_OPENING_UNRESOLVED,
            ),
        )


class PhysicalOpeningVoidProducer:
    """Trusted writer that joins the exact sealed prerequisite chain."""

    def __init__(
        self,
        physical_opening_authority: PhysicalOpeningAuthority,
        opening_universe_authority: OpeningUniverseCompletenessAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
        host_frame_authority: OpeningHostFrameAuthority,
        opening_dimension_authority: OpeningDimensionAuthority,
        opening_height_authority: OpeningHeightAuthority,
        vertical_placement_authority: OpeningVerticalPlacementAuthority,
        physical_scale_authority: PhysicalScaleAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("PhysicalOpeningVoidProducer must be obtained from from_authorities()")
        expected = (
            (physical_opening_authority, PhysicalOpeningAuthority, "physical_opening_authority"),
            (
                opening_universe_authority,
                OpeningUniverseCompletenessAuthority,
                "opening_universe_authority",
            ),
            (host_binding_authority, OpeningHostBindingAuthority, "host_binding_authority"),
            (host_frame_authority, OpeningHostFrameAuthority, "host_frame_authority"),
            (
                opening_dimension_authority,
                OpeningDimensionAuthority,
                "opening_dimension_authority",
            ),
            (opening_height_authority, OpeningHeightAuthority, "opening_height_authority"),
            (
                vertical_placement_authority,
                OpeningVerticalPlacementAuthority,
                "vertical_placement_authority",
            ),
            (physical_scale_authority, PhysicalScaleAuthority, "physical_scale_authority"),
        )
        for value, required_type, name in expected:
            if type(value) is not required_type:
                raise TypeError(f"{name} must be producer-owned {required_type.__name__}")
        self._opening = physical_opening_authority
        self._universe = opening_universe_authority
        self._host = host_binding_authority
        self._frame = host_frame_authority
        self._dimension = opening_dimension_authority
        self._height = opening_height_authority
        self._vertical = vertical_placement_authority
        self._scale = physical_scale_authority
        self._results: dict[_Key, PhysicalOpeningVoidResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_opening_authority: PhysicalOpeningAuthority,
        opening_universe_authority: OpeningUniverseCompletenessAuthority,
        host_binding_authority: OpeningHostBindingAuthority,
        host_frame_authority: OpeningHostFrameAuthority,
        opening_dimension_authority: OpeningDimensionAuthority,
        opening_height_authority: OpeningHeightAuthority,
        vertical_placement_authority: OpeningVerticalPlacementAuthority,
        physical_scale_authority: PhysicalScaleAuthority,
    ) -> "PhysicalOpeningVoidProducer":
        return cls(
            physical_opening_authority,
            opening_universe_authority,
            host_binding_authority,
            host_frame_authority,
            opening_dimension_authority,
            opening_height_authority,
            vertical_placement_authority,
            physical_scale_authority,
            _seal=_PRODUCER_SEAL,
        )

    def _store(
        self,
        key: _Key,
        result: PhysicalOpeningVoidResult,
    ) -> PhysicalOpeningVoidResult:
        existing = self._results.get(key)
        if existing is not None and existing != result:
            conflict = _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_GEOMETRY_CONFLICT,
                "physical_opening_void_producer_equivocation",
            )
            self._results[key] = conflict
            return conflict
        self._results[key] = result
        return result

    def publish(
        self,
        *,
        opening_selector: ObservationSelector,
        selector: PhysicalOpeningVoidSelector,
    ) -> PhysicalOpeningVoidResult:
        if type(opening_selector) is not ObservationSelector:
            raise TypeError("opening_selector must be ObservationSelector")
        if type(selector) is not PhysicalOpeningVoidSelector:
            raise TypeError("selector must be PhysicalOpeningVoidSelector")

        opening = self._opening.prove_existence(opening_selector)
        existence_record = opening.existence_record
        source_result = opening.source_observation
        source_observation = (
            getattr(source_result, "observation", None)
            if source_result is not None
            else None
        )
        if (
            opening.status is not EvidenceResolutionStatus.CORROBORATED
            or opening.proposition != PHYSICAL_OPENING_EXISTS
            or not opening.physical_opening_existence
            or existence_record is None
            or source_observation is None
        ):
            return _blocked(
                opening.status,
                PHYSICAL_OPENING_VOID_OPENING_UNRESOLVED,
                *opening.reason_codes,
            )
        if (
            not _lineage_matches(selector, existence_record)
            or existence_record.page_id != selector.page_id
            or existence_record.record_id != selector.opening_identity_id
            or not _lineage_matches(selector, source_observation)
            or source_observation.page_id != selector.page_id
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH,
            )

        viewport_id = source_observation.viewport_id or existence_record.viewport_id
        if (
            source_observation.viewport_id
            and existence_record.viewport_id
            and source_observation.viewport_id != existence_record.viewport_id
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH,
            )

        universe = self._universe.resolve(
            OpeningUniverseSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                decision_scope_id=selector.decision_scope_id,
            )
        )
        universe_record = universe.record
        if (
            universe.status is not EvidenceResolutionStatus.CORROBORATED
            or universe_record is None
            or not universe.decision_scope_complete
            or not universe_record.decision_scope_complete
        ):
            return _blocked(
                universe.status,
                PHYSICAL_OPENING_VOID_UNIVERSE_INCOMPLETE,
                *universe.reason_codes,
            )
        if (
            not _lineage_matches(selector, universe_record)
            or universe_record.decision_scope_id != selector.decision_scope_id
            or selector.page_id not in universe_record.page_ids
            or (
                universe_record.viewport_id is not None
                and universe_record.viewport_id != viewport_id
            )
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH,
            )

        host_selector = OpeningHostBindingSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=selector.decision_scope_id,
            opening_identity_id=selector.opening_identity_id,
        )
        host = self._host.resolve(host_selector)
        host_record = host.record
        if host.status is EvidenceResolutionStatus.CONFLICT:
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_HOST_CONFLICT,
                *host.reason_codes,
            )
        if (
            host.status is not EvidenceResolutionStatus.CORROBORATED
            or host_record is None
        ):
            return _blocked(
                host.status,
                PHYSICAL_OPENING_VOID_HOST_UNRESOLVED,
                *host.reason_codes,
            )
        if (
            not _lineage_matches(selector, host_record)
            or host_record.page_id != selector.page_id
            or host_record.decision_scope_id != selector.decision_scope_id
            or host_record.opening_identity_id != existence_record.record_id
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH,
            )

        frame_selector = OpeningHostFrameSelector(**host_selector.__dict__)
        frame = self._frame.resolve(frame_selector)
        frame_evidence = frame.evidence
        if (
            frame.status is not EvidenceResolutionStatus.CORROBORATED
            or frame_evidence is None
        ):
            return _blocked(
                frame.status,
                PHYSICAL_OPENING_VOID_FRAME_UNRESOLVED,
                *frame.reason_codes,
            )
        if (
            frame_evidence.selector != frame_selector
            or frame_evidence.opening_identity_id != existence_record.record_id
            or frame_evidence.host_binding_record_id != host_record.record_id
            or frame_evidence.host_wall_id != host_record.host_wall_id
            or frame_evidence.coordinate_unit != "pdf_point"
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH,
            )

        width = self._dimension.resolve_width(opening_selector)
        width_existence = width.opening_existence_record
        if (
            width.status is not EvidenceResolutionStatus.CORROBORATED
            or width.proposition != OPENING_WIDTH_RESOLVED
            or width.value_mm is None
            or width.axis != "width"
            or not width.dimension_record_id
            or width_existence is None
        ):
            return _blocked(
                width.status,
                PHYSICAL_OPENING_VOID_WIDTH_UNRESOLVED,
                *width.reason_codes,
            )
        if (
            width_existence.record_id != existence_record.record_id
            or not _lineage_matches(selector, width_existence)
            or width_existence.page_id != selector.page_id
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH,
            )

        height_selector = OpeningHeightSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            decision_scope_id=selector.decision_scope_id,
            opening_record_id=existence_record.record_id,
        )
        height = self._height.resolve(height_selector)
        height_evidence = height.evidence
        if (
            height.status is not EvidenceResolutionStatus.CORROBORATED
            or OPENING_HEIGHT_RESOLVED not in height.reason_codes
            or height_evidence is None
        ):
            return _blocked(
                height.status,
                PHYSICAL_OPENING_VOID_HEIGHT_UNRESOLVED,
                *height.reason_codes,
            )
        if (
            not _lineage_matches(selector, height_evidence)
            or height_evidence.opening_record_id != existence_record.record_id
            or height_evidence.units != "mm"
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH,
            )
        if height_evidence.dimension_basis != "rough_opening":
            return _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                PHYSICAL_OPENING_VOID_PROFILE_UNSUPPORTED,
            )

        vertical_selector = OpeningVerticalPlacementSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            decision_scope_id=selector.decision_scope_id,
            opening_record_id=existence_record.record_id,
        )
        vertical = self._vertical.resolve(vertical_selector)
        vertical_evidence = vertical.evidence
        if (
            vertical.status is not EvidenceResolutionStatus.CORROBORATED
            or OPENING_VERTICAL_PLACEMENT_RESOLVED not in vertical.reason_codes
            or vertical_evidence is None
        ):
            return _blocked(
                vertical.status,
                PHYSICAL_OPENING_VOID_VERTICAL_PLACEMENT_UNRESOLVED,
                *vertical.reason_codes,
            )
        if (
            not _lineage_matches(selector, vertical_evidence)
            or vertical_evidence.decision_scope_id != selector.decision_scope_id
            or vertical_evidence.opening_record_id != existence_record.record_id
            or vertical_evidence.units != "mm"
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH,
            )

        scale_selector = PhysicalScaleSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            viewport_id=viewport_id,
        )
        scale = self._scale.resolve(scale_selector)
        scale_evidence = scale.evidence
        if (
            scale.status is not EvidenceResolutionStatus.CORROBORATED
            or PHYSICAL_SCALE_RESOLVED not in scale.reason_codes
            or scale_evidence is None
        ):
            return _blocked(
                scale.status,
                PHYSICAL_OPENING_VOID_UNIT_MAPPING_UNRESOLVED,
                *scale.reason_codes,
            )
        if (
            scale_evidence.selector != scale_selector
            or scale_evidence.viewport_id != viewport_id
            or not scale_evidence.record_id
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH,
            )

        if existence_record.structural_pattern != JAMB_BOUNDED_TWO_FACE_INTERRUPTION:
            return _blocked(
                EvidenceResolutionStatus.ABSTAINED,
                PHYSICAL_OPENING_VOID_PROFILE_UNSUPPORTED,
            )

        values = (
            frame_evidence.u0_pt,
            frame_evidence.u1_pt,
            width.value_mm,
            height_evidence.height_mm,
            vertical_evidence.z0_mm,
            vertical_evidence.z1_mm,
            scale_evidence.mm_per_point,
        )
        if not all(math.isfinite(float(value)) for value in values):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_GEOMETRY_CONFLICT,
            )
        u0_pt = float(frame_evidence.u0_pt)
        u1_pt = float(frame_evidence.u1_pt)
        z0_mm = float(vertical_evidence.z0_mm)
        z1_mm = float(vertical_evidence.z1_mm)
        mm_per_point = float(scale_evidence.mm_per_point)
        if u1_pt <= u0_pt or z1_mm <= z0_mm or mm_per_point <= 0:
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_GEOMETRY_CONFLICT,
            )

        source_width_mm = (u1_pt - u0_pt) * mm_per_point
        width_mm = float(width.value_mm)
        width_numeric_tolerance = max(
            1e-9,
            abs(mm_per_point) * 2e-9,
            math.ulp(max(abs(source_width_mm), abs(width_mm))) * 16,
        )
        if not math.isclose(
            source_width_mm,
            width_mm,
            rel_tol=0.0,
            abs_tol=width_numeric_tolerance,
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_GEOMETRY_CONFLICT,
                "physical_opening_void_width_span_conflict",
            )

        height_mm = float(height_evidence.height_mm)
        vertical_height_mm = z1_mm - z0_mm
        height_numeric_tolerance = max(
            1e-9,
            math.ulp(max(abs(vertical_height_mm), abs(height_mm))) * 16,
        )
        if not math.isclose(
            vertical_height_mm,
            height_mm,
            rel_tol=0.0,
            abs_tol=height_numeric_tolerance,
        ):
            return _blocked(
                EvidenceResolutionStatus.CONFLICT,
                PHYSICAL_OPENING_VOID_GEOMETRY_CONFLICT,
                "physical_opening_void_height_span_conflict",
            )

        u0 = u0_pt * mm_per_point / 1000.0
        u1 = u1_pt * mm_per_point / 1000.0
        z0 = z0_mm / 1000.0
        z1 = z1_mm / 1000.0
        height_record_id = _evidence_id("opening_height_evidence", height_evidence)
        vertical_record_id = _evidence_id(
            "opening_vertical_placement_evidence",
            vertical_evidence,
        )
        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "viewport_id": viewport_id,
            "decision_scope_id": selector.decision_scope_id,
            "opening_identity_id": existence_record.record_id,
            "host_binding_record_id": host_record.record_id,
            "host_wall_id": host_record.host_wall_id,
            "opening_universe_record_id": universe_record.record_id,
            "width_record_id": width.dimension_record_id,
            "height_record_id": height_record_id,
            "wall_local_frame_id": frame_evidence.whole_wall_frame_id,
            "unit_mapping_record_id": scale_evidence.record_id,
            "vertical_placement_record_id": vertical_record_id,
            "profile_kind": RECTANGULAR_ROUGH_OPENING,
            "coordinate_unit": METRE,
            "u0": round(u0, 12),
            "u1": round(u1, 12),
            "z0": round(z0, 12),
            "z1": round(z1, 12),
            "schema_version": PHYSICAL_OPENING_VOID_SCHEMA_VERSION,
        }
        record = PhysicalOpeningVoidRecord(
            record_id=stable_contract_id(
                "physical_opening_void_v2",
                payload,
                digest_chars=32,
            ),
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            viewport_id=viewport_id,
            decision_scope_id=selector.decision_scope_id,
            opening_identity_id=existence_record.record_id,
            host_binding_record_id=host_record.record_id,
            host_wall_id=host_record.host_wall_id,
            opening_universe_record_id=universe_record.record_id,
            width_record_id=width.dimension_record_id,
            height_record_id=height_record_id,
            wall_local_frame_id=frame_evidence.whole_wall_frame_id,
            unit_mapping_record_id=scale_evidence.record_id,
            vertical_placement_record_id=vertical_record_id,
            profile_kind=RECTANGULAR_ROUGH_OPENING,
            coordinate_unit=METRE,
            u0=u0,
            u1=u1,
            z0=z0,
            z1=z1,
        )
        return self._store(
            selector.key,
            PhysicalOpeningVoidResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=frozenset([PHYSICAL_OPENING_VOID_RESOLVED]),
                record=record,
            ),
        )

    def authority(self) -> PhysicalOpeningVoidAuthority:
        return PhysicalOpeningVoidAuthority(self._results, _seal=_AUTHORITY_SEAL)


__all__ = [
    "PHYSICAL_OPENING_VOID_SCHEMA_VERSION",
    "PHYSICAL_OPENING_VOID_RESOLVED",
    "PHYSICAL_OPENING_VOID_OPENING_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_HOST_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_HOST_CONFLICT",
    "PHYSICAL_OPENING_VOID_WIDTH_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_HEIGHT_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_VERTICAL_PLACEMENT_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_FRAME_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_UNIT_MAPPING_UNRESOLVED",
    "PHYSICAL_OPENING_VOID_UNIVERSE_INCOMPLETE",
    "PHYSICAL_OPENING_VOID_PROFILE_UNSUPPORTED",
    "PHYSICAL_OPENING_VOID_GEOMETRY_CONFLICT",
    "PHYSICAL_OPENING_VOID_LINEAGE_MISMATCH",
    "PhysicalOpeningVoidSelector",
    "PhysicalOpeningVoidRecord",
    "PhysicalOpeningVoidResult",
    "PhysicalOpeningVoidAuthority",
    "PhysicalOpeningVoidProducer",
]
