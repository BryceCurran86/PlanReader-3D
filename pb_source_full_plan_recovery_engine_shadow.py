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
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, replace
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from pb_source_visibility_authority import SourceVisibilityProducer

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
DUPLICATE_SOURCE_PAGE_ID = "duplicate_source_page_id"
DUPLICATE_SOURCE_ROOM_ID = "duplicate_source_room_id"
UNSUPPORTED_SOURCE_PAGE_TYPE = "unsupported_source_page_type"
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
    # No omitted type can silently nominate a floor-plan sheet. Source-backed
    # page classification is a separate upstream authority not supplied here.
    page_type: str = "unverified"
    room_polygon_candidates: tuple[tuple[str, tuple[tuple[float, float], ...]], ...] = ()
    wall_edges: tuple[SourceRoomWallEdge, ...] = ()
    opening_candidates: tuple[SourceRoomOpeningCandidate, ...] = ()
    finish_mark_candidates: tuple[SourceFloorFinishMark, ...] = ()
    is_blocked: bool = False
    block_reason: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.page_id, str) or not self.page_id.strip():
            raise ValueError("page_id must be non-empty string")
        if not isinstance(self.page_type, str) or not self.page_type.strip():
            raise ValueError("page_type must be non-empty string")


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
    # Only the SourceVisibilityProducer entry fills these original-page
    # view-class receipt IDs; the caller-owned direct diagnostic leaves empty.
    source_page_view_class_receipts: tuple[tuple[str, str], ...] = ()
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
    # The page universe itself must be typed before any partial recovery.
    # Invalid objects cannot supply a trustworthy page identity or owner.
    if any(not isinstance(page, SourcePageInputPayload) for page in pages):
        return SourceFullPlanEngineResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_LINEAGE_MISMATCH,),
            selector=selector,
        )

    # A PDF page identity is one source scope, never two independent rooms or
    # finish universes. Quarantine *every* colliding payload, regardless of
    # order or whether one copy was already marked blocked.
    page_id_counts = Counter(page.page_id for page in pages)

    for page in pages:
        if page_id_counts[page.page_id] != 1:
            verdicts.append(
                SourcePageExecutionVerdict(
                    page_id=page.page_id,
                    page_type=page.page_type,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=(DUPLICATE_SOURCE_PAGE_ID, PAGE_QUARANTINED_SAFELY),
                    recovered_room_ids=(),
                    recovered_finish_ids=(),
                    is_quarantined=True,
                )
            )
            quarantined_pages += 1
            continue

        # Failure isolation check
        if page.is_blocked:
            reason = (page.block_reason.strip() if isinstance(page.block_reason, str) else "") or PAGE_COMPLEXITY_BLOCKED
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

        # A non-floor-plan sheet can contain room-like rectangles and FT marks,
        # but those shapes are not an authenticated floor-plan room universe.
        # This engine has no registered cross-sheet ownership receipt.
        if page.page_type != "floor_plan":
            verdicts.append(
                SourcePageExecutionVerdict(
                    page_id=page.page_id,
                    page_type=page.page_type,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=(UNSUPPORTED_SOURCE_PAGE_TYPE, PAGE_QUARANTINED_SAFELY),
                    recovered_room_ids=(),
                    recovered_finish_ids=(),
                    is_quarantined=True,
                )
            )
            quarantined_pages += 1
            continue

        # Five source-universe integrity requirements: well-formed room IDs,
        # finite room vertices, owned wall/opening candidates, and typed marks.
        # Do not let malformed candidates erase a rival or crash downstream
        # geometry during otherwise successful page recovery.
        valid_rooms = (
            isinstance(page.room_polygon_candidates, (tuple, list))
            and all(
                isinstance(entry, (tuple, list)) and len(entry) == 2
                and isinstance(entry[0], str) and bool(entry[0].strip())
                and isinstance(entry[1], (tuple, list))
                and len(entry[1]) >= 3
                and all(
                    isinstance(pt, (tuple, list)) and len(pt) == 2
                    and all(isinstance(v, (int, float)) and not isinstance(v, bool)
                            and math.isfinite(v) for v in pt)
                    for pt in entry[1]
                )
                for entry in page.room_polygon_candidates
            )
        )
        valid_other_candidates = (
            isinstance(page.wall_edges, (tuple, list))
            and all(isinstance(edge, SourceRoomWallEdge) for edge in page.wall_edges)
            and isinstance(page.opening_candidates, (tuple, list))
            and all(isinstance(opening, SourceRoomOpeningCandidate)
                    for opening in page.opening_candidates)
            and isinstance(page.finish_mark_candidates, (tuple, list))
            and all(isinstance(mark, SourceFloorFinishMark)
                    for mark in page.finish_mark_candidates)
        )
        if not (valid_rooms and valid_other_candidates):
            verdicts.append(
                SourcePageExecutionVerdict(
                    page_id=page.page_id,
                    page_type=page.page_type,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=(SOURCE_LINEAGE_MISMATCH, PAGE_QUARANTINED_SAFELY),
                    recovered_room_ids=(),
                    recovered_finish_ids=(),
                    is_quarantined=True,
                )
            )
            quarantined_pages += 1
            continue

        # A repeated room identity on one source page cannot denote two
        # independently owned physical room faces. Quarantine the entire
        # page rather than choosing a polygon or attributing its finish marks
        # to a surviving competing room. Other source pages remain usable.
        room_id_counts = Counter(room_id for room_id, _ in page.room_polygon_candidates)
        if any(count > 1 for count in room_id_counts.values()):
            verdicts.append(
                SourcePageExecutionVerdict(
                    page_id=page.page_id,
                    page_type=page.page_type,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=(DUPLICATE_SOURCE_ROOM_ID, PAGE_QUARANTINED_SAFELY),
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

        # Evaluate each original finish occurrence against the *complete*
        # room universe. A single mark cannot own two overlapping room faces,
        # and two distinct source marks cannot reuse one occurrence identity.
        # Neither ambiguity is a recovered diagnostic finish zone.
        recovered_finishes: list[str] = []
        occurrence_counts = Counter(
            mark.occurrence_id for mark in page.finish_mark_candidates
        )
        for finish in page.finish_mark_candidates:
            if occurrence_counts[finish.occurrence_id] != 1:
                continue
            candidate_owners: list[str] = []
            # Check *every* source room polygon, including a plausible rival
            # whose doorway/wall closure abstained. An unclosed rival cannot
            # disappear from the physical ownership ambiguity universe.
            for room_id, poly in page.room_polygon_candidates:
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
                    candidate_owners.append(room_id)
            # One spatial owner is necessary, and that same owner must have
            # independently passed room-boundary recovery. No tie-breaking.
            if len(candidate_owners) == 1 and candidate_owners[0] in recovered_rooms:
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
            # Counts alone alias distinct original-page/room/finish receipts.
            # Canonical sorting makes the identity invariant to page order.
            "page_verdicts": tuple(sorted(
                (
                    v.page_id,
                    v.page_type,
                    v.status.value,
                    v.reason_codes,
                    v.recovered_room_ids,
                    v.recovered_finish_ids,
                    v.is_quarantined,
                )
                for v in verdicts
            )),
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


def execute_source_full_plan_recovery_engine_from_source_visibility_shadow(
    selector: SourceFullPlanEngineSelector,
    *,
    pages: Sequence[SourcePageInputPayload],
    source_visibility_producer: "SourceVisibilityProducer",
) -> SourceFullPlanEngineResult:
    """Run recovery using *source-produced* page class rather than caller text.

    Unlike the legacy direct diagnostic, this boundary refuses a forged
    page_type='floor_plan' when original producer text cannot corroborate it.
    The PDF's source revision and snapshot must be the selector's exact scope.
    Room polygons, dimensions and finish occurrences remain shadow candidates
    and this API never signs construction quantities.
    """
    from pb_page_view_class_source_adapter import (
        build_source_page_view_class_authority,
        page_viewport_id,
    )
    from pb_source_visibility_authority import SourceVisibilityProducer
    from pb_viewport_view_class_authority import (
        VIEW_KIND_FLOOR_PLAN,
        ViewportViewClassSelector,
    )

    if (
        type(selector) is not SourceFullPlanEngineSelector
        or type(source_visibility_producer) is not SourceVisibilityProducer
        or not isinstance(pages, (tuple, list))
        or any(type(page) is not SourcePageInputPayload for page in pages)
    ):
        return SourceFullPlanEngineResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_LINEAGE_MISMATCH,),
            selector=selector if type(selector) is SourceFullPlanEngineSelector else None,
        )
    published = source_visibility_producer.published_snapshot_for_revision(
        selector.revision_id
    )
    if (
        published is None
        or published.revision.document_id != selector.document_id
        or published.revision.revision_id != selector.revision_id
        or published.revision.source_sha256 != selector.source_sha256
        or published.snapshot.snapshot_id != selector.snapshot_id
    ):
        return SourceFullPlanEngineResult(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(SOURCE_LINEAGE_MISMATCH,),
            selector=selector,
        )

    authority = build_source_page_view_class_authority(
        source_visibility_producer=source_visibility_producer,
        revision_id=selector.revision_id,
        page_ids=tuple(page.page_id for page in pages),
    )
    classified_pages: list[SourcePageInputPayload] = []
    source_view_receipts: list[tuple[str, str]] = []
    for page in pages:
        view = authority.resolve(
            ViewportViewClassSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                viewport_id=page_viewport_id(page.page_id),
            )
        )
        # A caller's claimed classification is never a fallback. A missing,
        # conflicting, non-floor or foreign-page source receipt is quarantined.
        authenticated = (
            view.status is EvidenceResolutionStatus.CORROBORATED
            and view.record is not None
            and view.record.view_kind == VIEW_KIND_FLOOR_PLAN
            and bool(view.record.evidence_observation_ids)
        )
        classified_pages.append(
            replace(page, page_type="floor_plan" if authenticated else "unverified")
        )
        if authenticated:
            source_view_receipts.append((page.page_id, view.record.record_id))

    base_result = execute_source_full_plan_recovery_engine_shadow(
        selector, pages=tuple(classified_pages)
    )
    # The same room/mark candidates can be passed directly to the unverified
    # diagnostic API. Do not mint an indistinguishable result for the genuinely
    # source-classified path. Bind every corroborated native view-class receipt
    # to the diagnostic record's identity without granting FIRM/area authority.
    if base_result.record is None or not source_view_receipts:
        return base_result
    receipts = tuple(sorted(source_view_receipts))
    trusted_identity = stable_contract_id(
        "source_full_plan_recovery_native_page_class",
        {
            "base_record_id": base_result.record.record_id,
            "source_page_view_class_receipts": receipts,
        },
        digest_chars=32,
    )
    record = replace(
        base_result.record,
        record_id=trusted_identity,
        source_page_view_class_receipts=receipts,
    )
    return replace(base_result, record=record)
