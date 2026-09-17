"""Producer-owned roof and ceiling evidence authority (Item 31).

Implements authenticated roof and ceiling parameters:
- Ceiling area (ceiling_area)
- Roof plan area (roof_plan_area)
- Roof slope/pitch (roof_pitch_deg)
- Roof surface area (roof_surface_area)
- Eaves/overhang geometry (eaves_overhang_length)
- Ceiling/roof type binding (roof_ceiling_binding)

Architectural Invariants:
- Floor area must never automatically become ceiling area.
- Plan footprint must never automatically become roof surface area.
- No assumed pitch or overhang.
- BOQ-only descriptions cannot manufacture geometry.
- Gable wall evidence does not by itself prove roof pitch.
- Sloped vs flat ceiling must remain distinct.
- If pitch/elevation evidence is absent, abstain rather than estimate.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math
from types import MappingProxyType
from typing import Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_physical_scale_authority import (
    PhysicalScaleAuthority,
    PhysicalScaleSelector,
)

ROOF_CEILING_SCHEMA_VERSION = "1.0.0"

# Public reason codes
ROOF_CEILING_RESOLVED = "roof_ceiling_resolved"
ROOF_CEILING_UNRESOLVED = "roof_ceiling_unresolved"
ROOF_CEILING_SCALE_UNRESOLVED = "roof_ceiling_scale_unresolved"
ROOF_CEILING_LINEAGE_MISMATCH = "roof_ceiling_lineage_mismatch"
ROOF_CEILING_FLOOR_AREA_SHORTCUT_REJECTED = "roof_ceiling_floor_area_shortcut_rejected"
ROOF_CEILING_FOOTPRINT_SURFACE_SHORTCUT_REJECTED = "roof_ceiling_footprint_surface_shortcut_rejected"
ROOF_CEILING_ASSUMED_PITCH_REJECTED = "roof_ceiling_assumed_pitch_rejected"
ROOF_CEILING_ASSUMED_OVERHANG_REJECTED = "roof_ceiling_assumed_overhang_rejected"
ROOF_CEILING_BOQ_ONLY_REJECTED = "roof_ceiling_boq_only_rejected"
ROOF_CEILING_GABLE_INFERENCE_REJECTED = "roof_ceiling_gable_wall_pitch_inference_rejected"
ROOF_CEILING_RECORD_UNAVAILABLE = "roof_ceiling_record_unavailable"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str, str]


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


class RoofCeilingFamily(str, Enum):
    """Supported roof/ceiling quantity families."""
    CEILING_AREA = "ceiling_area"
    ROOF_PLAN_AREA = "roof_plan_area"
    ROOF_PITCH_DEG = "roof_pitch_deg"
    ROOF_SURFACE_AREA = "roof_surface_area"
    EAVES_OVERHANG_LENGTH = "eaves_overhang_length"
    ROOF_CEILING_BINDING = "roof_ceiling_binding"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class RoofCeilingSelector:
    """Sealed selector identifying exact roof/ceiling target and family."""
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    target_id: str
    family: RoofCeilingFamily

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "target_id",
        ):
            _required(getattr(self, name), name)
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
            self.decision_scope_id,
            self.target_id,
            self.family.value,
        )


@dataclass(frozen=True)
class RoofCeilingEvidence:
    """Authenticated observation for roof or ceiling parameter."""
    evidence_id: str
    source_sha256: str
    revision_id: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    family: RoofCeilingFamily
    measured_value: float
    unit: str           # "m2", "deg", "m"
    kind: str           # e.g. "ceiling_plan_annotation", "roof_elevation_pitch"
    method: str         # e.g. "direct_dimension", "authenticated_elevation_angle"
    confidence: float
    is_sloped: bool = False
    pitch_deg: Optional[float] = None

    def __post_init__(self) -> None:
        for name in (
            "evidence_id",
            "source_sha256",
            "revision_id",
            "snapshot_id",
            "page_id",
            "viewport_id",
            "unit",
            "kind",
            "method",
        ):
            _required(getattr(self, name), name)
        if not isinstance(self.family, RoofCeilingFamily):
            raise TypeError("family must be RoofCeilingFamily")
        if not math.isfinite(self.measured_value) or self.measured_value <= 0.0:
            raise ValueError("measured_value must be positive and finite")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")


@dataclass(frozen=True)
class RoofCeilingRecord:
    """Sealed roof/ceiling authority record."""
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    target_id: str
    family: RoofCeilingFamily
    value: float
    unit: str
    is_sloped: bool
    pitch_deg: Optional[float]
    corroborating_evidence_ids: Tuple[str, ...]
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
    """Trusted writer boundary for roof and ceiling evidence authority."""

    def __init__(
        self,
        physical_scale_authority: PhysicalScaleAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("RoofCeilingProducer must be obtained via from_authorities()")
        if type(physical_scale_authority) is not PhysicalScaleAuthority:
            raise TypeError("physical_scale_authority must be producer-owned PhysicalScaleAuthority")
        self._scale = physical_scale_authority
        self._results: dict[_Key, RoofCeilingResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_scale_authority: PhysicalScaleAuthority,
    ) -> "RoofCeilingProducer":
        return cls(physical_scale_authority, _seal=_PRODUCER_SEAL)

    def authority(self) -> RoofCeilingAuthority:
        return RoofCeilingAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: RoofCeilingSelector,
        result: RoofCeilingResult,
    ) -> RoofCeilingResult:
        self._results[selector.key] = result
        return result

    def publish(
        self,
        selector: RoofCeilingSelector,
        observations: Sequence[RoofCeilingEvidence],
    ) -> RoofCeilingResult:
        """Publish roof/ceiling quantity for selector."""
        if type(selector) is not RoofCeilingSelector:
            raise TypeError("selector must be RoofCeilingSelector")

        # 1. Resolve Scale
        scale_sel = PhysicalScaleSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
        )
        scale_res = self._scale.resolve(scale_sel)
        if (
            scale_res.status is not EvidenceResolutionStatus.CORROBORATED
            or scale_res.evidence is None
        ):
            return self._store(
                selector,
                _abstained(
                    ROOF_CEILING_SCALE_UNRESOLVED,
                    *(getattr(scale_res, "reason_codes", ()) or ()),
                ),
            )

        # 2. Filter Observations
        obs = list(observations or [])
        if not obs:
            return self._store(selector, _abstained(ROOF_CEILING_UNRESOLVED))

        forbidden_kinds = {
            "floor_area_ceiling_shortcut",
            "plan_footprint_roof_surface_shortcut",
            "assumed_pitch",
            "assumed_overhang",
            "boq_description_only",
            "gable_wall_pitch_inference",
        }
        valid_obs: list[RoofCeilingEvidence] = []
        forbidden_floor = False
        forbidden_footprint = False
        forbidden_pitch = False
        forbidden_overhang = False
        forbidden_boq = False
        forbidden_gable = False
        stale_count = 0

        for ob in obs:
            if not isinstance(ob, RoofCeilingEvidence):
                continue
            if ob.family != selector.family:
                continue
            if ob.kind == "floor_area_ceiling_shortcut":
                forbidden_floor = True
                continue
            if ob.kind == "plan_footprint_roof_surface_shortcut":
                forbidden_footprint = True
                continue
            if ob.kind == "assumed_pitch":
                forbidden_pitch = True
                continue
            if ob.kind == "assumed_overhang":
                forbidden_overhang = True
                continue
            if ob.kind == "boq_description_only":
                forbidden_boq = True
                continue
            if ob.kind == "gable_wall_pitch_inference":
                forbidden_gable = True
                continue
            if ob.kind in forbidden_kinds:
                continue

            # Lineage match
            if (
                ob.source_sha256 != selector.source_sha256
                or ob.revision_id != selector.revision_id
                or ob.snapshot_id != selector.snapshot_id
                or ob.page_id != selector.page_id
            ):
                stale_count += 1
                continue
            valid_obs.append(ob)

        if forbidden_floor and not valid_obs:
            return self._store(selector, _abstained(ROOF_CEILING_FLOOR_AREA_SHORTCUT_REJECTED))
        if forbidden_footprint and not valid_obs:
            return self._store(selector, _abstained(ROOF_CEILING_FOOTPRINT_SURFACE_SHORTCUT_REJECTED))
        if forbidden_pitch and not valid_obs:
            return self._store(selector, _abstained(ROOF_CEILING_ASSUMED_PITCH_REJECTED))
        if forbidden_overhang and not valid_obs:
            return self._store(selector, _abstained(ROOF_CEILING_ASSUMED_OVERHANG_REJECTED))
        if forbidden_boq and not valid_obs:
            return self._store(selector, _abstained(ROOF_CEILING_BOQ_ONLY_REJECTED))
        if forbidden_gable and not valid_obs:
            return self._store(selector, _abstained(ROOF_CEILING_GABLE_INFERENCE_REJECTED))
        if stale_count and not valid_obs:
            return self._store(selector, _conflict(ROOF_CEILING_LINEAGE_MISMATCH))
        if not valid_obs:
            return self._store(selector, _abstained(ROOF_CEILING_UNRESOLVED))

        # Value consensus
        val_set = {round(ob.measured_value, 6) for ob in valid_obs}
        if len(val_set) > 1:
            return self._store(selector, _conflict(ROOF_CEILING_UNRESOLVED, "conflicting_measured_values"))

        val = float(next(iter(val_set)))
        first_ob = valid_obs[0]
        unit = first_ob.unit
        is_sloped = first_ob.is_sloped
        pitch_deg = first_ob.pitch_deg
        evidence_ids = tuple(sorted({ob.evidence_id for ob in valid_obs}))

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "target_id": selector.target_id,
            "family": selector.family.value,
            "value": val,
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
            decision_scope_id=selector.decision_scope_id,
            target_id=selector.target_id,
            family=selector.family,
            value=val,
            unit=unit,
            is_sloped=is_sloped,
            pitch_deg=pitch_deg,
            corroborating_evidence_ids=evidence_ids,
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
    "ROOF_CEILING_ASSUMED_OVERHANG_REJECTED",
    "ROOF_CEILING_ASSUMED_PITCH_REJECTED",
    "ROOF_CEILING_BOQ_ONLY_REJECTED",
    "ROOF_CEILING_FLOOR_AREA_SHORTCUT_REJECTED",
    "ROOF_CEILING_FOOTPRINT_SURFACE_SHORTCUT_REJECTED",
    "ROOF_CEILING_GABLE_INFERENCE_REJECTED",
    "ROOF_CEILING_LINEAGE_MISMATCH",
    "ROOF_CEILING_RECORD_UNAVAILABLE",
    "ROOF_CEILING_RESOLVED",
    "ROOF_CEILING_SCALE_UNRESOLVED",
    "ROOF_CEILING_SCHEMA_VERSION",
    "ROOF_CEILING_UNRESOLVED",
    "RoofCeilingAuthority",
    "RoofCeilingEvidence",
    "RoofCeilingFamily",
    "RoofCeilingProducer",
    "RoofCeilingRecord",
    "RoofCeilingResult",
    "RoofCeilingSelector",
]
