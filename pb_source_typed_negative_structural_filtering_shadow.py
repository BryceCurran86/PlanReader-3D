"""Producer-Owned Source Typed Negative Evidence Structural Filtering Shadow Authority.

Workstream C Item 28 / Playbook §13 Priority 3:
Codifies dimension witness lines, extension ticks, structural grid lines,
furniture loops, joinery lines, and glazing sills as opposing typed negative
evidence atoms without deleting legitimate wall candidates prematurely before
topological assembly.

Non-negotiable invariants:
- Shadow mode: candidate status only, non-publishing, zero commercial projection.
- Preserves 2.5 pt snap tolerance and byte-for-byte customer retention.
- No benchmark gold dependencies or project-name heuristics.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SCHEMA_VERSION = "1.0.0"

_FILTERING_SEAL = object()


class NegativeEvidenceKind(str, Enum):
    DIMENSION_WITNESS_LINE = "DIMENSION_WITNESS_LINE"
    DIMENSION_TICK = "DIMENSION_TICK"
    GRID_LINE = "GRID_LINE"
    FURNITURE_LOOP = "FURNITURE_LOOP"
    JOINERY_BOUNDARY = "JOINERY_BOUNDARY"
    GLAZING_MULLION_OR_SILL = "GLAZING_MULLION_OR_SILL"


class StructuralCandidacyStatus(str, Enum):
    CONFIRMED_STRUCTURAL_WALL = "CONFIRMED_STRUCTURAL_WALL"
    RETAINED_PENDING_TOPOLOGY = "RETAINED_PENDING_TOPOLOGY"
    DISQUALIFIED_BY_NEGATIVE_EVIDENCE = "DISQUALIFIED_BY_NEGATIVE_EVIDENCE"
    AMBIGUOUS_NEEDING_CORROBORATION = "AMBIGUOUS_NEEDING_CORROBORATION"


@dataclass(frozen=True)
class NegativeEvidenceAtom:
    atom_id: str
    kind: NegativeEvidenceKind
    start_pt: Tuple[float, float]
    end_pt: Tuple[float, float]
    stroke_width_pt: float
    confidence: float
    reason_code: str
    metadata: Mapping[str, Any]

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "atom_id": self.atom_id,
            "kind": self.kind.value,
            "start_pt": list(self.start_pt),
            "end_pt": list(self.end_pt),
            "stroke_width_pt": self.stroke_width_pt,
            "confidence": self.confidence,
            "reason_code": self.reason_code,
            "metadata": dict(self.metadata),
        }


@dataclass(frozen=True)
class SegmentStructuralEvaluation:
    segment_id: str
    start_pt: Tuple[float, float]
    end_pt: Tuple[float, float]
    stroke_width_pt: float
    status: StructuralCandidacyStatus
    positive_structural_score: float
    negative_evidence_score: float
    opposing_atoms: Tuple[NegativeEvidenceAtom, ...]
    decision_reason_code: str

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "segment_id": self.segment_id,
            "start_pt": list(self.start_pt),
            "end_pt": list(self.end_pt),
            "stroke_width_pt": self.stroke_width_pt,
            "status": self.status.value,
            "positive_structural_score": self.positive_structural_score,
            "negative_evidence_score": self.negative_evidence_score,
            "opposing_atoms": [a.to_dict() for a in self.opposing_atoms],
            "decision_reason_code": self.decision_reason_code,
        }


@dataclass(frozen=True)
class TypedNegativeFilteringReceipt:
    receipt_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    total_evaluated_segments: int
    retained_structural_count: int
    disqualified_count: int
    evaluations: Tuple[SegmentStructuralEvaluation, ...]
    status: EvidenceResolutionStatus
    schema_version: str = SCHEMA_VERSION
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _FILTERING_SEAL:
            raise TypeError("TypedNegativeFilteringReceipt is producer-owned")

    def to_dict(self) -> Mapping[str, Any]:
        return {
            "receipt_id": self.receipt_id,
            "document_id": self.document_id,
            "revision_id": self.revision_id,
            "source_sha256": self.source_sha256,
            "total_evaluated_segments": self.total_evaluated_segments,
            "retained_structural_count": self.retained_structural_count,
            "disqualified_count": self.disqualified_count,
            "evaluations": [e.to_dict() for e in self.evaluations],
            "status": self.status.value,
            "schema_version": self.schema_version,
            "commercial_projection_allowed": self.commercial_projection_allowed,
            "takeoff_eligible": self.takeoff_eligible,
        }


def _pt_dist(p1: Tuple[float, float], p2: Tuple[float, float]) -> float:
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


class SourceTypedNegativeStructuralFilteringShadowAuthority:
    """Evaluates candidate segments against typed negative evidence atoms."""

    def __init__(self, snap_tolerance_pt: float = 2.5) -> None:
        self.snap_tolerance_pt = snap_tolerance_pt
        self._atoms: List[NegativeEvidenceAtom] = []

    def register_negative_evidence_atom(
        self,
        *,
        kind: NegativeEvidenceKind,
        start_pt: Tuple[float, float],
        end_pt: Tuple[float, float],
        stroke_width_pt: float,
        confidence: float,
        reason_code: str,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> NegativeEvidenceAtom:
        meta = metadata or {}
        atom_id = stable_contract_id(
            "NEG_ATOM",
            (kind.value, start_pt, end_pt, stroke_width_pt, reason_code),
        )
        atom = NegativeEvidenceAtom(
            atom_id=atom_id,
            kind=kind,
            start_pt=start_pt,
            end_pt=end_pt,
            stroke_width_pt=stroke_width_pt,
            confidence=confidence,
            reason_code=reason_code,
            metadata=meta,
        )
        self._atoms.append(atom)
        return atom

    def evaluate_candidate_segment(
        self,
        *,
        segment_id: str,
        start_pt: Tuple[float, float],
        end_pt: Tuple[float, float],
        stroke_width_pt: float,
        is_closed_hatch_boundary: bool = False,
        has_parallel_corroboration: bool = False,
    ) -> SegmentStructuralEvaluation:
        seg_len = _pt_dist(start_pt, end_pt)
        if seg_len < 1e-4:
            return SegmentStructuralEvaluation(
                segment_id=segment_id,
                start_pt=start_pt,
                end_pt=end_pt,
                stroke_width_pt=stroke_width_pt,
                status=StructuralCandidacyStatus.DISQUALIFIED_BY_NEGATIVE_EVIDENCE,
                positive_structural_score=0.0,
                negative_evidence_score=1.0,
                opposing_atoms=(),
                decision_reason_code="ZERO_LENGTH_PRIMITIVE",
            )

        # Baseline positive structural score based on line weight and wall features
        pos_score = 0.0
        if stroke_width_pt >= 0.70:
            pos_score += 0.5
        elif stroke_width_pt >= 0.45:
            pos_score += 0.3
        else:
            pos_score += 0.1

        if is_closed_hatch_boundary:
            pos_score += 0.4
        if has_parallel_corroboration:
            pos_score += 0.3

        # Accumulate opposing negative evidence
        opposing: List[NegativeEvidenceAtom] = []
        neg_score = 0.0

        for atom in self._atoms:
            # Check proximity to atom
            d_start = _pt_dist(start_pt, atom.start_pt)
            d_end = _pt_dist(end_pt, atom.end_pt)
            is_collinear_or_touching = (
                (d_start <= self.snap_tolerance_pt and d_end <= self.snap_tolerance_pt)
                or (d_start <= self.snap_tolerance_pt and _pt_dist(end_pt, atom.start_pt) <= seg_len + self.snap_tolerance_pt)
            )

            if is_collinear_or_touching or atom.metadata.get("target_segment_id") == segment_id:
                opposing.append(atom)
                neg_score += atom.confidence

        # Determine decision
        if neg_score >= 0.8 and pos_score < 0.6:
            status = StructuralCandidacyStatus.DISQUALIFIED_BY_NEGATIVE_EVIDENCE
            reason = "DISQUALIFIED_BY_STRONG_NEGATIVE_ANNOTATION_EVIDENCE"
        elif pos_score >= 0.7:
            status = StructuralCandidacyStatus.CONFIRMED_STRUCTURAL_WALL
            reason = "CONFIRMED_WALL_POSITIVE_EVIDENCE_DOMINATES"
        elif neg_score > 0.0 and pos_score >= neg_score:
            status = StructuralCandidacyStatus.RETAINED_PENDING_TOPOLOGY
            reason = "RETAINED_CONCURRENT_EVIDENCE_DEFERRED_TO_TOPOLOGY"
        elif neg_score > 0.0:
            status = StructuralCandidacyStatus.DISQUALIFIED_BY_NEGATIVE_EVIDENCE
            reason = "DISQUALIFIED_NEGATIVE_EVIDENCE_EXCEEDS_POSITIVE"
        else:
            status = StructuralCandidacyStatus.RETAINED_PENDING_TOPOLOGY
            reason = "RETAINED_NO_OPPOSING_NEGATIVE_EVIDENCE"

        return SegmentStructuralEvaluation(
            segment_id=segment_id,
            start_pt=start_pt,
            end_pt=end_pt,
            stroke_width_pt=stroke_width_pt,
            status=status,
            positive_structural_score=round(pos_score, 4),
            negative_evidence_score=round(neg_score, 4),
            opposing_atoms=tuple(opposing),
            decision_reason_code=reason,
        )

    def compile_filtering_receipt(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        evaluations: Sequence[SegmentStructuralEvaluation],
    ) -> TypedNegativeFilteringReceipt:
        evals_tuple = tuple(evaluations)
        total = len(evals_tuple)
        retained = sum(
            1
            for e in evals_tuple
            if e.status in (
                StructuralCandidacyStatus.CONFIRMED_STRUCTURAL_WALL,
                StructuralCandidacyStatus.RETAINED_PENDING_TOPOLOGY,
            )
        )
        disqualified = sum(
            1
            for e in evals_tuple
            if e.status == StructuralCandidacyStatus.DISQUALIFIED_BY_NEGATIVE_EVIDENCE
        )

        receipt_id = stable_contract_id(
            "NEGATIVE_FILTERING_RECEIPT",
            (document_id, revision_id, source_sha256, total, retained, disqualified),
        )

        return TypedNegativeFilteringReceipt(
            receipt_id=receipt_id,
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            total_evaluated_segments=total,
            retained_structural_count=retained,
            disqualified_count=disqualified,
            evaluations=evals_tuple,
            status=EvidenceResolutionStatus.CANDIDATE,
            schema_version=SCHEMA_VERSION,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_FILTERING_SEAL,
        )
