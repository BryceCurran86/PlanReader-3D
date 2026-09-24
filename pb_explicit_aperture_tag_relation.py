"""Source-authenticated explicit aperture-tag relation bridge.

This module does not choose an opening identity from proximity.  It only
materializes the existing EXPLICIT_APERTURE_TAG relation when authenticated
tag geometry is contained by/overlaps exactly one source-backed physical
opening candidate.  The existing authenticate_tag_binding_evidence() and
OpeningIdentityResolver remain the identity authority.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Iterable, Sequence

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_observation_authority import SourceObservationAuthority
from pb_source_opening_candidate_authority import (
    PhysicalOpeningCandidateRecord,
    TagBindingEvidence,
    TagBindingRelationKind,
    TagObservation,
    authenticate_tag_binding_evidence,
    normalize_opening_tag,
)


def _bbox(candidate: PhysicalOpeningCandidateRecord) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = candidate.geometry
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)


def _tag_attaches_to_candidate(
    tag: TagObservation,
    candidate: PhysicalOpeningCandidateRecord,
) -> bool:
    """Mirror the existing explicit-aperture geometric predicate only.

    No independent distance threshold is introduced here.  The candidate's
    source-derived tolerance provenance is the sole tolerance authority.
    """
    cx0, cy0, cx1, cy1 = _bbox(candidate)
    tx0, ty0, tx1, ty1 = tag.bounding_box
    tx0, tx1 = min(tx0, tx1), max(tx0, tx1)
    ty0, ty1 = min(ty0, ty1), max(ty0, ty1)
    tol = candidate.tolerance_provenance.derived_tolerance_pt

    tcx = 0.5 * (tx0 + tx1)
    tcy = 0.5 * (ty0 + ty1)
    center_attached = (
        cx0 - tol <= tcx <= cx1 + tol
        and cy0 - tol <= tcy <= cy1 + tol
    )
    overlaps = (
        min(cx1, tx1) >= max(cx0, tx0) - tol
        and min(cy1, ty1) >= max(cy0, ty0) - tol
    )
    return center_attached or overlaps


def build_explicit_aperture_tag_relations(
    *,
    candidates: Sequence[PhysicalOpeningCandidateRecord],
    tags: Sequence[TagObservation],
    source_observation_authority: SourceObservationAuthority,
) -> tuple[TagBindingEvidence, ...]:
    """Create lawful typed relation evidence for unambiguous aperture tags.

    Safety rules:
    - source scope must agree before geometry is considered;
    - only active physical-opening candidates participate;
    - only explicit normalizable W/D tags participate;
    - one tag geometrically attaching to multiple openings is ambiguous and
      produces no relation;
    - multiple distinct marks attaching to one opening are ambiguous and
      produce no relation;
    - the existing authenticated relation factory re-resolves every source
      observation and independently re-checks the relation geometry.

    Repeated observations of the same normalized mark may survive upstream
    OCR as separate source observations; those are not treated as competing
    semantic identities.
    """
    active = tuple(
        candidate
        for candidate in candidates
        if candidate.status == EvidenceResolutionStatus.CANDIDATE
    )
    eligible_by_tag: dict[str, list[PhysicalOpeningCandidateRecord]] = defaultdict(list)
    tag_by_id: dict[str, TagObservation] = {}

    for tag in tags:
        normalized = normalize_opening_tag(tag.raw_tag_text)
        if normalized is None:
            continue
        tag_by_id[tag.observation_id] = tag
        for candidate in active:
            if (
                tag.document_id != candidate.document_id
                or tag.revision_id != candidate.revision_id
                or tag.source_sha256 != candidate.source_sha256
                or tag.snapshot_id != candidate.snapshot_id
                or str(tag.page_id).removeprefix("page_")
                != str(candidate.page_id).removeprefix("page_")
                or tag.viewport_id != candidate.viewport_id
            ):
                continue
            if _tag_attaches_to_candidate(tag, candidate):
                eligible_by_tag[tag.observation_id].append(candidate)

    uniquely_attached: list[tuple[TagObservation, PhysicalOpeningCandidateRecord, str]] = []
    for tag_id, matched in eligible_by_tag.items():
        if len(matched) != 1:
            continue
        tag = tag_by_id[tag_id]
        normalized = normalize_opening_tag(tag.raw_tag_text)
        if normalized is None:
            continue
        uniquely_attached.append((tag, matched[0], normalized.tag))

    marks_by_candidate: dict[str, set[str]] = defaultdict(set)
    for _tag, candidate, mark in uniquely_attached:
        marks_by_candidate[candidate.candidate_id].add(mark)

    evidences: list[TagBindingEvidence] = []
    for tag, candidate, _mark in uniquely_attached:
        if len(marks_by_candidate[candidate.candidate_id]) != 1:
            continue
        # Candidate support observations are immutable, authenticated source
        # evidence already carried by the physical candidate.  The relation
        # factory re-resolves them and separately proves tag containment.
        relation_ids = tuple(dict.fromkeys(candidate.source_observation_ids))
        if not relation_ids:
            continue
        evidence = authenticate_tag_binding_evidence(
            tag=tag,
            candidate=candidate,
            relation_kind=TagBindingRelationKind.EXPLICIT_APERTURE_TAG,
            relation_observation_ids=relation_ids,
            source_lineage_root_ids=candidate.source_lineage_root_ids,
            source_observation_authority=source_observation_authority,
        )
        if evidence.status == EvidenceResolutionStatus.CORROBORATED:
            evidences.append(evidence)

    return tuple(evidences)
