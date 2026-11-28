"""Default-off generic cross-sheet floor-finish association & threshold continuity shadow (AG-R06/R08).

Provides two generic, auditable, fail-closed shadow contracts for downstream
handoff to Claude's physical wall/ring & C22 open-plan geometry lane and MAX's
issuer integration:

1. **Cross-sheet floor-finish code association (AG-R06 / A13)**:
   - Links schedule-sheet finish specifications (canonical normalized finish code,
     material description, substrate/system) to plan-sheet room finish markers
     across the same ``source_sha256`` / ``revision_id``.
   - Rejects conflicting schedule definitions for the same canonical finish code
     and conflicting finish codes assigned to the same room without subzone split.
2. **Typed doorway / open-plan threshold continuity semantics (AG-R08 / A17)**:
   - Classifies the finish transition between two adjacent rooms/zones strictly
     from explicit source evidence:
     - ``CONTINUOUS_SAME_FINISH`` (both rooms share the same corroborated finish)
     - ``THRESHOLD_TRANSITION_AT_DOORWAY`` (different finishes separated by an
       explicit authenticated doorway/opening threshold)
     - ``OPEN_PLAN_EXPLICIT_BOUNDARY_LINE`` (different finishes in an open-plan
       adjacency with an explicit drawn finish-transition / dashed boundary line)
     - ``ABSTAINED_NO_EXPLICIT_THRESHOLD`` (different finishes in an open-plan
       adjacency with NO drawn transition line — never invents a boundary!)

Shadow-only (``shadow_only=True``, ``commercial_authority_granted=False``).
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
import re
from typing import Optional

from pb_migration_contracts import EvidenceResolutionStatus


SCHEMA_VERSION = "1.0.0"

_CODE_CLEAN_RE = re.compile(r"[\s\-_/]+")


class ThresholdContinuityKind(str, Enum):
    """Typed floor-finish continuity / threshold classification between two zones."""

    CONTINUOUS_SAME_FINISH = "continuous_same_finish"
    THRESHOLD_TRANSITION_AT_DOORWAY = "threshold_transition_at_doorway"
    OPEN_PLAN_EXPLICIT_BOUNDARY_LINE = "open_plan_explicit_boundary_line"
    ABSTAINED_NO_EXPLICIT_THRESHOLD = "abstained_no_explicit_threshold"


@dataclass(frozen=True)
class ScheduleFinishSpecWitness:
    """One finish-code definition from a schedule/legend sheet."""

    spec_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    finish_code: str
    material_description: str


@dataclass(frozen=True)
class PlanRoomFinishOccurrenceWitness:
    """One plan-sheet room finish-code marker."""

    occurrence_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    page_id: str
    viewport_id: str
    room_key: str
    finish_code: str


@dataclass(frozen=True)
class RoomAdjacencyThresholdWitness:
    """One adjacency pair between two rooms/zones for continuity semantics."""

    adjacency_id: str
    room_a_key: str
    room_b_key: str
    has_doorway_opening: bool = False
    has_explicit_finish_transition_line: bool = False
    transition_line_observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class CrossSheetRoomFinishAssociation:
    """One resolved or blocked cross-sheet room floor-finish association."""

    room_key: str
    canonical_finish_code: str
    material_description: Optional[str]
    spec_ids: tuple[str, ...]
    occurrence_ids: tuple[str, ...]
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    shadow_only: bool = True
    commercial_authority_granted: bool = False


@dataclass(frozen=True)
class ThresholdContinuityDecision:
    """Typed continuity/threshold decision for Claude C22 open-plan handoff."""

    adjacency_id: str
    room_a_key: str
    room_b_key: str
    finish_a: Optional[str]
    finish_b: Optional[str]
    continuity_kind: ThresholdContinuityKind
    status: EvidenceResolutionStatus
    transition_line_observation_ids: tuple[str, ...]
    reason_codes: tuple[str, ...]
    shadow_only: bool = True
    commercial_authority_granted: bool = False


@dataclass(frozen=True)
class FloorFinishThresholdShadowResult:
    """Aggregated shadow-only cross-sheet finish + threshold continuity packet."""

    associations: tuple[CrossSheetRoomFinishAssociation, ...]
    threshold_decisions: tuple[ThresholdContinuityDecision, ...]
    reason_codes: tuple[str, ...]
    shadow_only: bool = True
    commercial_authority_granted: bool = False
    schema_version: str = SCHEMA_VERSION


def canonicalize_finish_code(raw: str) -> str:
    """Normalize hyphenated/spaced finish codes (e.g., ``FT-03`` -> ``FT3``)."""
    cleaned = _CODE_CLEAN_RE.sub("", str(raw or "").strip().upper())
    m = re.fullmatch(r"([A-Z]+)0*(\d+)([A-Z]*)", cleaned)
    if m:
        return f"{m.group(1)}{m.group(2)}{m.group(3)}"
    return cleaned


def evaluate_cross_sheet_floor_finish_and_thresholds_shadow(
    *,
    schedule_specs: Sequence[ScheduleFinishSpecWitness],
    room_occurrences: Sequence[PlanRoomFinishOccurrenceWitness],
    adjacencies: Sequence[RoomAdjacencyThresholdWitness] = (),
) -> FloorFinishThresholdShadowResult:
    """Associate schedule finish codes to plan rooms and classify threshold continuity."""
    reasons: list[str] = []

    # 1) Index schedule specs by (doc, rev, sha, canonical_code), detecting conflicts
    spec_index: dict[tuple[str, str, str, str], list[ScheduleFinishSpecWitness]] = {}
    for spec in schedule_specs:
        code = canonicalize_finish_code(spec.finish_code)
        desc = " ".join(str(spec.material_description or "").strip().split())
        if not code or not desc:
            continue
        key = (spec.document_id, spec.revision_id, spec.source_sha256, code)
        spec_index.setdefault(key, []).append(spec)

    # 2) Group plan room occurrences by (doc, rev, sha, room_key)
    occ_by_room: dict[tuple[str, str, str, str], list[PlanRoomFinishOccurrenceWitness]] = {}
    for occ in room_occurrences:
        rkey = str(occ.room_key or "").strip()
        if not rkey:
            continue
        occ_by_room.setdefault(
            (occ.document_id, occ.revision_id, occ.source_sha256, rkey), []
        ).append(occ)

    associations: list[CrossSheetRoomFinishAssociation] = []
    corroborated_finish_by_room: dict[str, str] = {}

    for (doc_id, rev_id, sha, rkey), occs in sorted(occ_by_room.items()):
        codes = sorted({canonicalize_finish_code(o.finish_code) for o in occs if canonicalize_finish_code(o.finish_code)})
        occ_ids = tuple(sorted(o.occurrence_id for o in occs))
        if not codes:
            associations.append(
                CrossSheetRoomFinishAssociation(
                    room_key=rkey,
                    canonical_finish_code="",
                    material_description=None,
                    spec_ids=(),
                    occurrence_ids=occ_ids,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=("plan_room_finish_code_empty",),
                )
            )
            continue
        if len(codes) > 1:
            reasons.append("plan_room_conflicting_finish_codes")
            associations.append(
                CrossSheetRoomFinishAssociation(
                    room_key=rkey,
                    canonical_finish_code="|".join(codes),
                    material_description=None,
                    spec_ids=(),
                    occurrence_ids=occ_ids,
                    status=EvidenceResolutionStatus.CONFLICT,
                    reason_codes=("plan_room_conflicting_finish_codes",),
                )
            )
            continue

        code = codes[0]
        matching_specs = spec_index.get((doc_id, rev_id, sha, code), [])
        if not matching_specs:
            reasons.append("schedule_finish_spec_missing_for_code")
            associations.append(
                CrossSheetRoomFinishAssociation(
                    room_key=rkey,
                    canonical_finish_code=code,
                    material_description=None,
                    spec_ids=(),
                    occurrence_ids=occ_ids,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=("schedule_finish_spec_missing_for_code",),
                )
            )
            continue

        descs = {
            " ".join(str(s.material_description or "").strip().upper().split())
            for s in matching_specs
        }
        spec_ids = tuple(sorted(s.spec_id for s in matching_specs))
        if len(descs) > 1:
            reasons.append("schedule_finish_spec_conflicting_descriptions")
            associations.append(
                CrossSheetRoomFinishAssociation(
                    room_key=rkey,
                    canonical_finish_code=code,
                    material_description=None,
                    spec_ids=spec_ids,
                    occurrence_ids=occ_ids,
                    status=EvidenceResolutionStatus.CONFLICT,
                    reason_codes=("schedule_finish_spec_conflicting_descriptions",),
                )
            )
            continue

        canonical_desc = " ".join(str(matching_specs[0].material_description).strip().split())
        corroborated_finish_by_room[rkey] = code
        associations.append(
            CrossSheetRoomFinishAssociation(
                room_key=rkey,
                canonical_finish_code=code,
                material_description=canonical_desc,
                spec_ids=spec_ids,
                occurrence_ids=occ_ids,
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=("cross_sheet_floor_finish_corroborated",),
            )
        )

    # 3) Typed doorway / open-plan threshold continuity decisions (never invents boundaries)
    threshold_decisions: list[ThresholdContinuityDecision] = []
    for adj in adjacencies:
        fa = corroborated_finish_by_room.get(adj.room_a_key)
        fb = corroborated_finish_by_room.get(adj.room_b_key)
        if fa is None or fb is None:
            threshold_decisions.append(
                ThresholdContinuityDecision(
                    adjacency_id=adj.adjacency_id,
                    room_a_key=adj.room_a_key,
                    room_b_key=adj.room_b_key,
                    finish_a=fa,
                    finish_b=fb,
                    continuity_kind=ThresholdContinuityKind.ABSTAINED_NO_EXPLICIT_THRESHOLD,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    transition_line_observation_ids=(),
                    reason_codes=("adjacent_room_finish_unresolved",),
                )
            )
            continue
        if fa == fb:
            threshold_decisions.append(
                ThresholdContinuityDecision(
                    adjacency_id=adj.adjacency_id,
                    room_a_key=adj.room_a_key,
                    room_b_key=adj.room_b_key,
                    finish_a=fa,
                    finish_b=fb,
                    continuity_kind=ThresholdContinuityKind.CONTINUOUS_SAME_FINISH,
                    status=EvidenceResolutionStatus.CORROBORATED,
                    transition_line_observation_ids=(),
                    reason_codes=("continuous_same_floor_finish",),
                )
            )
        elif adj.has_doorway_opening:
            threshold_decisions.append(
                ThresholdContinuityDecision(
                    adjacency_id=adj.adjacency_id,
                    room_a_key=adj.room_a_key,
                    room_b_key=adj.room_b_key,
                    finish_a=fa,
                    finish_b=fb,
                    continuity_kind=ThresholdContinuityKind.THRESHOLD_TRANSITION_AT_DOORWAY,
                    status=EvidenceResolutionStatus.CORROBORATED,
                    transition_line_observation_ids=tuple(adj.transition_line_observation_ids),
                    reason_codes=("finish_transition_at_authenticated_doorway",),
                )
            )
        elif adj.has_explicit_finish_transition_line and adj.transition_line_observation_ids:
            threshold_decisions.append(
                ThresholdContinuityDecision(
                    adjacency_id=adj.adjacency_id,
                    room_a_key=adj.room_a_key,
                    room_b_key=adj.room_b_key,
                    finish_a=fa,
                    finish_b=fb,
                    continuity_kind=ThresholdContinuityKind.OPEN_PLAN_EXPLICIT_BOUNDARY_LINE,
                    status=EvidenceResolutionStatus.CORROBORATED,
                    transition_line_observation_ids=tuple(adj.transition_line_observation_ids),
                    reason_codes=("open_plan_explicit_transition_line_witnessed",),
                )
            )
        else:
            reasons.append("open_plan_transition_abstained_no_explicit_boundary")
            threshold_decisions.append(
                ThresholdContinuityDecision(
                    adjacency_id=adj.adjacency_id,
                    room_a_key=adj.room_a_key,
                    room_b_key=adj.room_b_key,
                    finish_a=fa,
                    finish_b=fb,
                    continuity_kind=ThresholdContinuityKind.ABSTAINED_NO_EXPLICIT_THRESHOLD,
                    status=EvidenceResolutionStatus.ABSTAINED,
                    transition_line_observation_ids=(),
                    reason_codes=("open_plan_transition_abstained_no_explicit_boundary",),
                )
            )

    return FloorFinishThresholdShadowResult(
        associations=tuple(associations),
        threshold_decisions=tuple(threshold_decisions),
        reason_codes=tuple(dict.fromkeys(reasons)),
    )


__all__ = [
    "CrossSheetRoomFinishAssociation",
    "FloorFinishThresholdShadowResult",
    "PlanRoomFinishOccurrenceWitness",
    "RoomAdjacencyThresholdWitness",
    "SCHEMA_VERSION",
    "ScheduleFinishSpecWitness",
    "ThresholdContinuityDecision",
    "ThresholdContinuityKind",
    "canonicalize_finish_code",
    "evaluate_cross_sheet_floor_finish_and_thresholds_shadow",
]
