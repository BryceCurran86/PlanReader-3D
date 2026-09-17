"""Producer-owned DPC and substructure quantity authority (Item 30).

Implements authenticated DPC and substructure quantities:
- DPC length (dpc_length)
- Foundation wall length (foundation_wall_length)
- Strip footing length (strip_footing_length)
- Substructure wall area (substructure_wall_area)

Architectural Invariants:
- Requires exact physical wall / foundation identity.
- No "perimeter = DPC" shortcut unless governing evidence proves it.
- No copying superstructure measurements into substructure without proven relationship.
- No default footing widths/depths.
- Fail closed if section/foundation detail evidence is required but absent.
- Strict lineage, scale, and candidate corroboration.
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
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateAuthority,
    PhysicalWallCandidateSelector,
)

DPC_SUBSTRUCTURE_SCHEMA_VERSION = "1.0.0"

# Public reason codes
DPC_SUBSTRUCTURE_RESOLVED = "dpc_substructure_resolved"
DPC_SUBSTRUCTURE_UNRESOLVED = "dpc_substructure_unresolved"
DPC_SUBSTRUCTURE_WALL_UNRESOLVED = "dpc_substructure_wall_unresolved"
DPC_SUBSTRUCTURE_SCALE_UNRESOLVED = "dpc_substructure_scale_unresolved"
DPC_SUBSTRUCTURE_LINEAGE_MISMATCH = "dpc_substructure_lineage_mismatch"
DPC_SUBSTRUCTURE_PERIMETER_SHORTCUT_REJECTED = "dpc_substructure_perimeter_shortcut_rejected"
DPC_SUBSTRUCTURE_SUPERSTRUCTURE_COPY_REJECTED = "dpc_substructure_superstructure_copy_rejected"
DPC_SUBSTRUCTURE_MISSING_SECTION_DETAIL = "dpc_substructure_missing_section_detail"
DPC_SUBSTRUCTURE_RECORD_UNAVAILABLE = "dpc_substructure_record_unavailable"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str, str]


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


class SubstructureFamily(str, Enum):
    """Supported substructure quantity families."""
    DPC_LENGTH = "dpc_length"
    FOUNDATION_WALL_LENGTH = "foundation_wall_length"
    STRIP_FOOTING_LENGTH = "strip_footing_length"
    SUBSTRUCTURE_WALL_AREA = "substructure_wall_area"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True)
class DPCSubstructureSelector:
    """Sealed selector identifying exact physical foundation component and family."""
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_foundation_id: str
    family: SubstructureFamily

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "page_id",
            "decision_scope_id",
            "physical_foundation_id",
        ):
            _required(getattr(self, name), name)
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
            self.decision_scope_id,
            self.physical_foundation_id,
            self.family.value,
        )


@dataclass(frozen=True)
class DPCSubstructureEvidence:
    """Authenticated observation for DPC or substructure quantity."""
    evidence_id: str
    source_sha256: str
    revision_id: str
    snapshot_id: str
    page_id: str
    viewport_id: str
    family: SubstructureFamily
    measured_value: float
    unit: str           # "m" or "m2"
    kind: str           # e.g. "dpc_schedule_row", "foundation_plan_wall"
    method: str         # e.g. "direct_dimension", "authenticated_section_detail"
    confidence: float

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
        if not isinstance(self.family, SubstructureFamily):
            raise TypeError("family must be SubstructureFamily")
        if not math.isfinite(self.measured_value) or self.measured_value <= 0.0:
            raise ValueError("measured_value must be positive and finite")
        if not (0.0 <= self.confidence <= 1.0):
            raise ValueError("confidence must be in [0, 1]")


@dataclass(frozen=True)
class DPCSubstructureRecord:
    """Sealed DPC/substructure quantity record."""
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str
    physical_foundation_id: str
    family: SubstructureFamily
    value: float
    unit: str
    corroborating_evidence_ids: Tuple[str, ...]
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
    """Trusted writer boundary for DPC and substructure quantity authority."""

    def __init__(
        self,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        physical_scale_authority: PhysicalScaleAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("DPCSubstructureProducer must be obtained via from_authorities()")
        if type(physical_wall_candidate_authority) is not PhysicalWallCandidateAuthority:
            raise TypeError("physical_wall_candidate_authority must be producer-owned PhysicalWallCandidateAuthority")
        if type(physical_scale_authority) is not PhysicalScaleAuthority:
            raise TypeError("physical_scale_authority must be producer-owned PhysicalScaleAuthority")
        self._wall_candidates = physical_wall_candidate_authority
        self._scale = physical_scale_authority
        self._results: dict[_Key, DPCSubstructureResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        physical_wall_candidate_authority: PhysicalWallCandidateAuthority,
        physical_scale_authority: PhysicalScaleAuthority,
    ) -> "DPCSubstructureProducer":
        return cls(
            physical_wall_candidate_authority,
            physical_scale_authority,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> DPCSubstructureAuthority:
        return DPCSubstructureAuthority(self._results, _seal=_AUTHORITY_SEAL)

    def _store(
        self,
        selector: DPCSubstructureSelector,
        result: DPCSubstructureResult,
    ) -> DPCSubstructureResult:
        self._results[selector.key] = result
        return result

    def publish(
        self,
        selector: DPCSubstructureSelector,
        observations: Sequence[DPCSubstructureEvidence],
    ) -> DPCSubstructureResult:
        """Publish DPC / substructure quantity for selector."""
        if type(selector) is not DPCSubstructureSelector:
            raise TypeError("selector must be DPCSubstructureSelector")

        # 1. Resolve Physical Wall Candidates
        cand_scope_id = f"wall-source:page-{selector.page_id}"
        cand_sel = PhysicalWallCandidateSelector(
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            page_id=selector.page_id,
            decision_scope_id=cand_scope_id,
        )
        cand_result = self._wall_candidates.resolve_scope(cand_sel)
        if (
            cand_result.status is not EvidenceResolutionStatus.CORROBORATED
            and selector.decision_scope_id != cand_scope_id
        ):
            try:
                alt_sel = PhysicalWallCandidateSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    page_id=selector.page_id,
                    decision_scope_id=selector.decision_scope_id,
                )
                alt = self._wall_candidates.resolve_scope(alt_sel)
                if alt.status is EvidenceResolutionStatus.CORROBORATED:
                    cand_result = alt
            except Exception:
                pass

        if cand_result.status is not EvidenceResolutionStatus.CORROBORATED:
            return self._store(
                selector,
                _abstained(
                    DPC_SUBSTRUCTURE_WALL_UNRESOLVED,
                    *(getattr(cand_result, "reason_codes", ()) or ()),
                ),
            )

        matching_recs = [
            r for r in getattr(cand_result, "records", ())
            if getattr(r, "wall_candidate_id", None) == selector.physical_foundation_id
            or getattr(getattr(r, "physical_identity", None), "physical_wall_id", None)
            == selector.physical_foundation_id
        ]
        if not matching_recs:
            return self._store(selector, _abstained(DPC_SUBSTRUCTURE_WALL_UNRESOLVED))

        # 2. Resolve Scale
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
                    DPC_SUBSTRUCTURE_SCALE_UNRESOLVED,
                    *(getattr(scale_res, "reason_codes", ()) or ()),
                ),
            )

        # 3. Filter Observations
        obs = list(observations or [])
        if not obs:
            return self._store(selector, _abstained(DPC_SUBSTRUCTURE_UNRESOLVED))

        forbidden_kinds = {
            "perimeter_dpc_shortcut",
            "copied_superstructure_shortcut",
            "assumed_footing_depth",
            "assumed_dpc",
        }
        valid_obs: list[DPCSubstructureEvidence] = []
        forbidden_perim = False
        forbidden_super = False
        stale_count = 0
        missing_section = False

        for ob in obs:
            if not isinstance(ob, DPCSubstructureEvidence):
                continue
            if ob.family != selector.family:
                continue
            if ob.kind == "perimeter_dpc_shortcut":
                forbidden_perim = True
                continue
            if ob.kind == "copied_superstructure_shortcut":
                forbidden_super = True
                continue
            if ob.kind in forbidden_kinds:
                continue

            if ob.method == "missing_section_detail":
                missing_section = True
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

        if forbidden_perim and not valid_obs:
            return self._store(selector, _abstained(DPC_SUBSTRUCTURE_PERIMETER_SHORTCUT_REJECTED))
        if forbidden_super and not valid_obs:
            return self._store(selector, _abstained(DPC_SUBSTRUCTURE_SUPERSTRUCTURE_COPY_REJECTED))
        if missing_section and not valid_obs:
            return self._store(selector, _abstained(DPC_SUBSTRUCTURE_MISSING_SECTION_DETAIL))
        if stale_count and not valid_obs:
            return self._store(selector, _conflict(DPC_SUBSTRUCTURE_LINEAGE_MISMATCH))
        if not valid_obs:
            return self._store(selector, _abstained(DPC_SUBSTRUCTURE_UNRESOLVED))

        # Value consensus
        val_set = {round(ob.measured_value, 6) for ob in valid_obs}
        if len(val_set) > 1:
            return self._store(selector, _conflict(DPC_SUBSTRUCTURE_UNRESOLVED, "conflicting_measured_values"))

        val = float(next(iter(val_set)))
        unit = valid_obs[0].unit
        evidence_ids = tuple(sorted({ob.evidence_id for ob in valid_obs}))

        payload = {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "page_id": selector.page_id,
            "decision_scope_id": selector.decision_scope_id,
            "physical_foundation_id": selector.physical_foundation_id,
            "family": selector.family.value,
            "value": val,
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
            decision_scope_id=selector.decision_scope_id,
            physical_foundation_id=selector.physical_foundation_id,
            family=selector.family,
            value=val,
            unit=unit,
            corroborating_evidence_ids=evidence_ids,
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
    "DPC_SUBSTRUCTURE_LINEAGE_MISMATCH",
    "DPC_SUBSTRUCTURE_MISSING_SECTION_DETAIL",
    "DPC_SUBSTRUCTURE_PERIMETER_SHORTCUT_REJECTED",
    "DPC_SUBSTRUCTURE_RECORD_UNAVAILABLE",
    "DPC_SUBSTRUCTURE_RESOLVED",
    "DPC_SUBSTRUCTURE_SCALE_UNRESOLVED",
    "DPC_SUBSTRUCTURE_SCHEMA_VERSION",
    "DPC_SUBSTRUCTURE_SUPERSTRUCTURE_COPY_REJECTED",
    "DPC_SUBSTRUCTURE_UNRESOLVED",
    "DPC_SUBSTRUCTURE_WALL_UNRESOLVED",
    "DPCSubstructureAuthority",
    "DPCSubstructureEvidence",
    "DPCSubstructureProducer",
    "DPCSubstructureRecord",
    "DPCSubstructureResult",
    "DPCSubstructureSelector",
    "SubstructureFamily",
]
