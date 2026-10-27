"""Producer-owned source full-plan recovery engine shadow authority (Workstream C, Items 27 & 30).

Restores full-plan source interpretation after partial pipeline failures:
- Delivers an integration-ready source geometry engine that downstream agents can consume.
- Failure Isolation: prevents cross-page poisoning. When one page encounters complexity
  bounds or unproven fonts, that page is safely quarantined with its exact reason codes
  while healthy floor plan pages successfully produce verified candidate geometries.
- Integrates room boundary doorway closures, floor finishes, continuous wall systems,
  and drafting motif filtering into a coherent document manifest.
- Strictly non-publishing in shadow mode (status=CANDIDATE, commercial_projection_allowed=False,
  takeoff_eligible=False).
"""

from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_floor_finish_occurrence_ownership_shadow import (
    SourceFloorFinishMark,
    SourceFloorFinishOwnershipSelector,
    evaluate_source_floor_finish_ownership_shadow,
)
from pb_source_room_boundary_doorway_opening_shadow import (
    SourceRoomBoundaryDoorwayResult,
    SourceRoomDoorwayOpeningSelector,
    SourceRoomOpeningCandidate,
    SourceRoomWallEdge,
    evaluate_source_room_boundary_doorway_shadow,
)

SCHEMA_VERSION = "1.0.0"

# Public Reason Codes
SOURCE_FULL_PLAN_ENGINE_RESOLVED = "source_full_plan_engine_resolved"
SOURCE_FULL_PLAN_ENGINE_CANDIDATE = "source_full_plan_engine_candidate"
SOURCE_FULL_PLAN_PARTIAL_RECOVERY = "source_full_plan_partial_recovery"
SOURCE_FULL_PLAN_ENGINE_ABSTAINED = "source_full_plan_engine_abstained"
PAGE_COMPLEXITY_BLOCKED = "page_complexity_blocked"
PAGE_QUARANTINED_SAFELY = "page_quarantined_safely"
SOURCE_LINEAGE_MISMATCH = "source_lineage_mismatch"
EMPTY_PAGE_PAYLOADS = "empty_page_payloads"

_RECORD_SEAL = object()


def _clean(val: Any) -> str:
    return str(val or "").strip()


@dataclass(frozen=True)
class SourceFullPlanEngineSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str

    def __post_init__(self) -> None:
        for name in ("document_id", "revision_id", "source_sha256", "snapshot_id"):
            val = getattr(self, name)
            if not isinstance(val, str) or not val.strip():
                raise ValueError(f"Selector field {name} must be non-empty string")
        sha = self.source_sha256.lower()
        if len(sha) != 64 or not re.fullmatch(r"[0-9a-f]{64}", sha):
            raise ValueError("source_sha256 must be a 64-char lowercase hex string")


@dataclass(frozen=True)
class SourcePageInputPayload:
    page_id: str
    page_type: str = "floor_plan"
    room_polygon_candidates: tuple[tuple[str, tuple[tuple[float, float], ...]], ...] = ()
    wall_edges: tuple[SourceRoomWallEdge, ...] = ()
    opening_candidates: tuple[SourceRoomOpeningCandidate, ...] = ()
    finish_mark_candidates: tuple[SourceFloorFinishMark, ...] = ()
    is_blocked: bool = False
    block_reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.page_id, str) or not self.page_id.strip():
            raise ValueError("page_id must be non-empty string")


@dataclass(frozen=True)
class SourcePageExecutionVerdict:
    page_id: str
    page_type: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    recovered_room_ids: tuple[str, ...]
    recovered_finish_ids: tuple[str, ...]
    is_quarantined: bool = False


@dataclass(frozen=True)
class SourceFullPlanEngineRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    total_pages_evaluated: int
    successful_pages_count: int
    quarantined_pages_count: int
    total_rooms_recovered: int
    total_finish_zones_recovered: int
    page_verdicts: tuple[SourcePageExecutionVerdict, ...]
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    reason_codes: tuple[str, ...] = (SOURCE_FULL_PLAN_ENGINE_CANDIDATE,)
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    diagnostic_only: bool = True
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourceFullPlanEngineRecord is producer-owned")


@dataclass(frozen=True)
class SourceFullPlanEngineResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: SourceFullPlanEngineRecord | None = None
    selector: SourceFullPlanEngineSelector | None = None
    schema_version: str = SCHEMA_VERSION


def execute_source_full_plan_recovery_engine_shadow(
    selector: SourceFullPlanEngineSelector,
    *,
    pages: Sequence[SourcePageInputPayload],
) -> SourceFullPlanEngineResult:
    """Execute full-plan recovery with strict per-page failure isolation."""
    if not isinstance(selector, SourceFullPlanEngineSelector):
        return SourceFullPlanEngineResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_LINEAGE_MISMATCH,),
        )

    if not pages:
        return SourceFullPlanEngineResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(EMPTY_PAGE_PAYLOADS,),
            selector=selector,
        )

    verdicts: list[SourcePageExecutionVerdict] = []
    total_rooms = 0
    total_finishes = 0
    successful_pages = 0
    quarantined_pages = 0

    for page in pages:
        # Failure isolation check
        if page.is_blocked:
            reason = page.block_reason.strip() or PAGE_COMPLEXITY_BLOCKED
            verdicts.append(
                SourcePageExecutionVerdict(
                    page_id=page.page_id,
                    page_type=page.page_type,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=(reason, PAGE_QUARANTINED_SAFELY),
                    recovered_room_ids=(),
                    recovered_finish_ids=(),
                    is_quarantined=True,
                )
            )
            quarantined_pages += 1
            continue

        # Evaluate room boundary closures across doorway openings on this page
        recovered_rooms: list[str] = []
        for room_id, poly in page.room_polygon_candidates:
            room_sel = SourceRoomDoorwayOpeningSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=page.page_id,
                room_id=room_id,
                room_label=room_id,
            )
            res = evaluate_source_room_boundary_doorway_shadow(
                room_sel,
                polygon_pdf_pts=poly,
                wall_edges=page.wall_edges,
                opening_candidates=page.opening_candidates,
            )
            if res.status == EvidenceResolutionStatus.CANDIDATE:
                recovered_rooms.append(room_id)

        # Evaluate floor finish occurrences on this page
        recovered_finishes: list[str] = []
        for finish in page.finish_mark_candidates:
            # Match against each recovered room polygon
            for room_id, poly in page.room_polygon_candidates:
                if room_id not in recovered_rooms:
                    continue
                finish_sel = SourceFloorFinishOwnershipSelector(
                    document_id=selector.document_id,
                    revision_id=selector.revision_id,
                    source_sha256=selector.source_sha256,
                    snapshot_id=selector.snapshot_id,
                    page_id=page.page_id,
                    room_id=room_id,
                    material_code=finish.material_code,
                )
                f_res = evaluate_source_floor_finish_ownership_shadow(
                    finish_sel,
                    finish_mark=finish,
                    internal_face_polygon_pdf_pts=poly,
                    # Preserve the complete page-local rival universe. The evaluator
                    # must see all same-room FT2/FT3 and duplicate occurrences;
                    # a missing rival list silently bypasses its ambiguity veto.
                    other_finish_marks=page.finish_mark_candidates,
                )
                if f_res.status == EvidenceResolutionStatus.CANDIDATE:
                    recovered_finishes.append(finish.occurrence_id)

        page_rooms_tuple = tuple(sorted(recovered_rooms))
        page_finishes_tuple = tuple(sorted(recovered_finishes))
        total_rooms += len(page_rooms_tuple)
        total_finishes += len(page_finishes_tuple)

        if page_rooms_tuple or page_finishes_tuple:
            page_status = EvidenceResolutionStatus.CANDIDATE
            page_reasons = (SOURCE_FULL_PLAN_ENGINE_RESOLVED,)
            successful_pages += 1
        else:
            page_status = EvidenceResolutionStatus.ABSTAINED
            page_reasons = (SOURCE_FULL_PLAN_ENGINE_ABSTAINED,)

        verdicts.append(
            SourcePageExecutionVerdict(
                page_id=page.page_id,
                page_type=page.page_type,
                status=page_status,
                reason_codes=page_reasons,
                recovered_room_ids=page_rooms_tuple,
                recovered_finish_ids=page_finishes_tuple,
                is_quarantined=False,
            )
        )

    overall_status = (
        EvidenceResolutionStatus.CANDIDATE
        if successful_pages > 0
        else EvidenceResolutionStatus.ABSTAINED
    )
    overall_reasons = (
        (SOURCE_FULL_PLAN_ENGINE_RESOLVED, SOURCE_FULL_PLAN_PARTIAL_RECOVERY, SOURCE_FULL_PLAN_ENGINE_CANDIDATE)
        if (successful_pages > 0 and quarantined_pages > 0)
        else (SOURCE_FULL_PLAN_ENGINE_RESOLVED, SOURCE_FULL_PLAN_ENGINE_CANDIDATE)
        if (successful_pages > 0)
        else (SOURCE_FULL_PLAN_ENGINE_ABSTAINED,)
    )

    record_id = stable_contract_id(
        "source_full_plan_recovery_engine",
        {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "successful_pages": successful_pages,
            "quarantined_pages": quarantined_pages,
            "total_rooms": total_rooms,
            "total_finishes": total_finishes,
        },
        digest_chars=32,
    )

    record = SourceFullPlanEngineRecord(
        record_id=record_id,
        document_id=selector.document_id,
        revision_id=selector.revision_id,
        source_sha256=selector.source_sha256,
        snapshot_id=selector.snapshot_id,
        total_pages_evaluated=len(pages),
        successful_pages_count=successful_pages,
        quarantined_pages_count=quarantined_pages,
        total_rooms_recovered=total_rooms,
        total_finish_zones_recovered=total_finishes,
        page_verdicts=tuple(verdicts),
        status=overall_status,
        reason_codes=overall_reasons,
        schema_version=SCHEMA_VERSION,
        commercial_projection_allowed=False,
        takeoff_eligible=False,
        diagnostic_only=True,
        _seal=_RECORD_SEAL,
    )

    return SourceFullPlanEngineResult(
        status=overall_status,
        reason_codes=overall_reasons,
        record=record,
        selector=selector,
    )
