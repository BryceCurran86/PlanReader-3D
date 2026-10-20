"""Producer-Owned Pipeline Partial Failure Recovery and Graceful Degradation Shadow Authority.

Workstream C Item 27:
Restores full-plan source interpretation after partial pipeline failures.
Isolates subsystems (walls, openings, rooms, finishes, ceilings, schedules, levels)
behind guarded execution boundaries, quarantining localized errors/timeouts while
preserving authenticated geometry from healthy subsystems for downstream consumption.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Quarantined subsystems never project or publish commercial quantities.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
"""

from __future__ import annotations

import traceback
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

_RECOVERY_SEAL = object()


class SubsystemKind(str, Enum):
    WALLS = "WALLS"
    OPENINGS = "OPENINGS"
    ROOMS = "ROOMS"
    FINISHES = "FINISHES"
    CEILINGS = "CEILINGS"
    SCHEDULES = "SCHEDULES"
    LEVELS = "LEVELS"


class SubsystemStatus(str, Enum):
    SUCCESS = "SUCCESS"
    QUARANTINED = "QUARANTINED"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class SubsystemRecoveryResult:
    subsystem: SubsystemKind
    status: SubsystemStatus
    recovered_object_count: int
    error_reason_code: Optional[str]
    diagnostic_message: str
    payload: Optional[Any] = None

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "subsystem": self.subsystem.value,
            "status": self.status.value,
            "recovered_object_count": self.recovered_object_count,
            "error_reason_code": self.error_reason_code,
            "diagnostic_message": self.diagnostic_message,
        }


@dataclass(frozen=True)
class PartialPlanRecoveryReport:
    report_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_subsystems_count: int
    healthy_subsystems_count: int
    quarantined_subsystems_count: int
    subsystems: Tuple[SubsystemRecoveryResult, ...]
    is_partial_recovery: bool
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECOVERY_SEAL:
            raise TypeError("PartialPlanRecoveryReport is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "report_id": self.report_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_subsystems_count": self.total_subsystems_count,
            "healthy_subsystems_count": self.healthy_subsystems_count,
            "quarantined_subsystems_count": self.quarantined_subsystems_count,
            "subsystems": [s.to_dict() for s in self.subsystems],
            "is_partial_recovery": self.is_partial_recovery,
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


class PipelineFailureRecoveryShadowAuthority:
    """Manages fault-tolerant execution and partial plan recovery across drawing subsystems."""

    def __init__(self) -> None:
        self._results: Dict[SubsystemKind, SubsystemRecoveryResult] = {}

    def execute_guarded_subsystem(
        self,
        subsystem: SubsystemKind,
        func: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> SubsystemRecoveryResult:
        """Executes a subsystem task within an isolated quarantine boundary."""
        try:
            output = func(*args, **kwargs)
            count = len(output) if isinstance(output, (list, tuple, dict, set)) else 1
            res = SubsystemRecoveryResult(
                subsystem=subsystem,
                status=SubsystemStatus.SUCCESS,
                recovered_object_count=count,
                error_reason_code=None,
                diagnostic_message="Subsystem extracted successfully.",
                payload=output,
            )
        except Exception as ex:
            error_type = type(ex).__name__
            msg = str(ex).strip() or "Unhandled exception during subsystem processing"
            res = SubsystemRecoveryResult(
                subsystem=subsystem,
                status=SubsystemStatus.QUARANTINED,
                recovered_object_count=0,
                error_reason_code=f"SUBSYSTEM_QUARANTINED_{error_type.upper()}",
                diagnostic_message=f"Quarantined {subsystem.value} failure: {msg}",
                payload=None,
            )

        self._results[subsystem] = res
        return res

    def compile_recovery_report(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
    ) -> PartialPlanRecoveryReport:
        """Compiles an immutable report summarizing surviving vs quarantined subsystems."""
        subsystems_tuple = tuple(self._results.values())
        total = len(subsystems_tuple)
        healthy = sum(1 for s in subsystems_tuple if s.status == SubsystemStatus.SUCCESS)
        quarantined = sum(1 for s in subsystems_tuple if s.status == SubsystemStatus.QUARANTINED)

        is_partial = quarantined > 0 and healthy > 0
        overall_status = EvidenceResolutionStatus.CORROBORATED if healthy > 0 else EvidenceResolutionStatus.ABSTAINED

        report_id = stable_contract_id(
            "PARTIAL_PLAN_RECOVERY",
            (document_id, revision_id, source_sha256, total, healthy, quarantined),
        )

        return PartialPlanRecoveryReport(
            report_id=report_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_subsystems_count=total,
            healthy_subsystems_count=healthy,
            quarantined_subsystems_count=quarantined,
            subsystems=subsystems_tuple,
            is_partial_recovery=is_partial,
            status=overall_status,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_RECOVERY_SEAL,
        )
