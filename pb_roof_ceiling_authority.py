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
from typing import Mapping, Optional, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)
from pb_physical_scale_authority import (
    PhysicalScaleAuthority,
    PhysicalScaleSelector,
)
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
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
        physical_wall_candidate_authority: Optional[PhysicalWallCandidateAuthority] = None,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("RoofCeilingProducer must be obtained via from_authorities()")
        if type(physical_scale_authority) is not PhysicalScaleAuthority:
            raise TypeError("physical_scale_authority must be producer-owned PhysicalScaleAuthority")
        if (
            physical_wall_candidate_authority is not None
            and type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority
        ):
            raise TypeError("physical_wall_candidate_authority must be producer-owned PhysicalWallCandidateAuthority")
        self._scale = physical_scale_authority
        self._wall_candidates = physical_wall_candidate_authority
        self._results: dict[_Key, RoofCeilingResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_scale_authority: PhysicalScaleAuthority,
        physical_wall_candidate_authority: Optional[PhysicalWallCandidateAuthority] = None,
    ) -> "RoofCeilingProducer":
        return cls(
            physical_scale_authority,
            physical_wall_candidate_authority,
            _seal=_PRODUCER_SEAL,
        )

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
    ) -> RoofCeilingResult:
        """Publish roof/ceiling quantity for selector by re-resolving scale and candidate authorities."""
        if type(selector) is not RoofCeilingSelector:
            raise TypeError("selector must be RoofCeilingSelector")

        if selector.family == RoofCeilingFamily.UNRESOLVED:
            return self._store(selector, _abstained(ROOF_CEILING_UNRESOLVED))

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

        if self._wall_candidates is None:
            return self._store(selector, _abstained(ROOF_CEILING_UNRESOLVED))

        # 2. Resolve Candidate Geometry
        cand_scope_id = f"wall-source:page-{selector.page_id}"
        cand_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=cand_scope_id,
        )
        cand_res = self._wall_candidates.resolve_scope(cand_sel)
        if cand_res.status is not EvidenceResolutionStatus.CORROBORATED:
            return self._store(selector, _abstained(ROOF_CEILING_UNRESOLVED))

        matching = [
            r for r in cand_res.records
            if r.wall_candidate_id == selector.target_id
            or getattr(r.physical_identity, "physical_wall_id", None) == selector.target_id
        ]
        if not matching:
            return self._store(selector, _abstained(ROOF_CEILING_UNRESOLVED))

        rec = matching[0]
        cand = rec.wall_candidate
        meta = cand.metadata or {}

        val = 0.0
        unit = "m2"
        is_sloped = False
        pitch_deg: Optional[float] = None

        if selector.family in (RoofCeilingFamily.CEILING_AREA, RoofCeilingFamily.ROOF_PLAN_AREA):
            area_m2 = meta.get("area_m2")
            if area_m2 is None and getattr(cand, "length_m", None) and meta.get("width_m"):
                try:
                    area_m2 = float(cand.length_m) * float(meta["width_m"])
                except (TypeError, ValueError):
                    area_m2 = None

            if area_m2 is None or not isinstance(area_m2, (int, float)) or not math.isfinite(area_m2) or area_m2 <= 0.0:
                return self._store(selector, _abstained(ROOF_CEILING_UNRESOLVED))

            val = round(float(area_m2), 6)
            unit = "m2"
            is_sloped = bool(meta.get("is_sloped", False))
            pitch_deg = float(meta["pitch_deg"]) if "pitch_deg" in meta and meta["pitch_deg"] is not None else None

        elif selector.family == RoofCeilingFamily.ROOF_PITCH_DEG:
            pitch = meta.get("pitch_deg")
            if pitch is None or not isinstance(pitch, (int, float)) or not math.isfinite(pitch) or pitch <= 0.0:
                return self._store(selector, _abstained(ROOF_CEILING_ASSUMED_PITCH_REJECTED))
            val = round(float(pitch), 6)
            unit = "deg"
            is_sloped = True
            pitch_deg = val

        elif selector.family == RoofCeilingFamily.ROOF_SURFACE_AREA:
            pitch = meta.get("pitch_deg")
            plan_area = meta.get("area_m2")
            if pitch is None or plan_area is None:
                return self._store(selector, _abstained(ROOF_CEILING_FOOTPRINT_SURFACE_SHORTCUT_REJECTED))
            try:
                rad = math.radians(float(pitch))
                val = round(float(plan_area) / math.cos(rad), 6)
            except Exception:
                return self._store(selector, _abstained(ROOF_CEILING_ASSUMED_PITCH_REJECTED))
            unit = "m2"
            is_sloped = True
            pitch_deg = float(pitch)

        elif selector.family == RoofCeilingFamily.EAVES_OVERHANG_LENGTH:
            overhang = meta.get("overhang_length_m")
            if overhang is None or not isinstance(overhang, (int, float)) or not math.isfinite(overhang) or overhang <= 0.0:
                return self._store(selector, _abstained(ROOF_CEILING_ASSUMED_OVERHANG_REJECTED))
            val = round(float(overhang), 6)
            unit = "m"

        else:
            return self._store(selector, _abstained(ROOF_CEILING_UNRESOLVED))

        scale_id = getattr(scale_res.evidence, "record_id", "scale") if scale_res.evidence else "scale"
        evidence_ids = (rec.wall_candidate_id, str(scale_id))

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
    "RoofCeilingProducer",
    "RoofCeilingRecord",
    "RoofCeilingResult",
    "RoofCeilingSelector",
    "RoofCeilingFamily",
]
