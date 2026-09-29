"""Shadow-only cross-view registration for structural-member observations.

This module does not detect structural members and does not publish commercial
quantities. It only converts already-authenticated, source-owned registration
anchors into relation evidence for the existing StructuralMemberProducer.

No relation is inferred from equal counts, nearest geometry, list position,
matching size, project identity, filenames, or benchmark expectations.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Dict, Mapping, Sequence, Tuple

from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_authority import (
    StructuralMemberDefinition,
    StructuralMemberObservation,
    StructuralMemberProducer,
    StructuralMemberRelation,
    StructuralMemberRelationEvidence,
    StructuralMemberResolution,
    StructuralMemberSelector,
    StructuralMemberViewScope,
)

STRUCTURAL_MEMBER_REGISTRATION_SCHEMA_VERSION = "1.0.0"
STRUCTURAL_MEMBER_REGISTRATION_RESOLVED = "structural_member_registration_resolved"
STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE = "structural_member_registration_incomplete"
STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_AMBIGUOUS = "structural_member_registration_anchor_ambiguous"
STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_CONFLICT = "structural_member_registration_anchor_conflict"
STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_INVALID = "structural_member_registration_anchor_invalid"


class StructuralMemberRegistrationAnchorKind(str, Enum):
    """Source-owned anchor families that can be compared across views."""

    GRID_INTERSECTION = "grid_intersection"
    MEMBER_MARK = "member_mark"
    PROJECTION_ID = "projection_id"


@dataclass(frozen=True)
class StructuralMemberRegistrationAnchor:
    """One exact source-owned registration fact for one member observation."""

    observation_id: str
    kind: StructuralMemberRegistrationAnchorKind
    registration_scope_id: str
    value: str
    source_evidence_ids: Tuple[str, ...]
    schema_version: str = STRUCTURAL_MEMBER_REGISTRATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not str(self.observation_id).strip():
            raise ValueError("observation_id is required")
        if type(self.kind) is not StructuralMemberRegistrationAnchorKind:
            raise TypeError("kind must be StructuralMemberRegistrationAnchorKind")
        if not str(self.registration_scope_id).strip():
            raise ValueError("registration_scope_id is required")
        if not str(self.value).strip():
            raise ValueError("value is required")
        if not self.source_evidence_ids or any(
            not str(item).strip() for item in self.source_evidence_ids
        ):
            raise ValueError("source_evidence_ids must contain source-owned evidence")


@dataclass(frozen=True)
class StructuralMemberRegistrationAudit:
    relation_count: int
    same_relation_count: int
    distinct_relation_count: int
    ambiguous_anchor_keys: Tuple[str, ...]
    conflicting_observation_ids: Tuple[str, ...]
    invalid_observation_ids: Tuple[str, ...]
    schema_version: str = STRUCTURAL_MEMBER_REGISTRATION_SCHEMA_VERSION


@dataclass(frozen=True)
class StructuralMemberRegistrationShadowResult:
    selector: StructuralMemberSelector
    resolution: StructuralMemberResolution
    relations: Tuple[StructuralMemberRelationEvidence, ...]
    view_scopes: Tuple[StructuralMemberViewScope, ...]
    reason_codes: Tuple[str, ...]
    audit: StructuralMemberRegistrationAudit
    schema_version: str = STRUCTURAL_MEMBER_REGISTRATION_SCHEMA_VERSION


def _normalize_text(value: str) -> str:
    return " ".join(str(value).split()).upper()


def _anchor_family(
    anchor: StructuralMemberRegistrationAnchor,
) -> tuple[str, str]:
    return (
        anchor.kind.value,
        _normalize_text(anchor.registration_scope_id),
    )


def _anchor_value(anchor: StructuralMemberRegistrationAnchor) -> str:
    return _normalize_text(anchor.value)


def _anchor_key(anchor: StructuralMemberRegistrationAnchor) -> tuple[str, str, str]:
    family = _anchor_family(anchor)
    return (*family, _anchor_value(anchor))


def _key_text(key: tuple[str, str, str]) -> str:
    return "|".join(key)


def _scope_by_view(
    scopes: Sequence[StructuralMemberViewScope],
) -> Dict[str, StructuralMemberViewScope]:
    return {scope.view_id: scope for scope in scopes}


def _fail_scopes_for_views(
    scopes: Sequence[StructuralMemberViewScope],
    view_ids: Sequence[str],
    reason: str,
) -> tuple[StructuralMemberViewScope, ...]:
    affected = set(view_ids)
    out = []
    for scope in scopes:
        if scope.view_id not in affected:
            out.append(scope)
            continue
        out.append(
            replace(
                scope,
                complete=False,
                reason_codes=tuple(dict.fromkeys((*scope.reason_codes, reason))),
            )
        )
    return tuple(out)


def build_structural_member_registration_shadow(
    *,
    selector: StructuralMemberSelector,
    observations: Sequence[StructuralMemberObservation],
    anchors: Sequence[StructuralMemberRegistrationAnchor],
    view_scopes: Sequence[StructuralMemberViewScope],
    definitions: Sequence[StructuralMemberDefinition] = (),
) -> StructuralMemberRegistrationShadowResult:
    """Build cross-view relation evidence and replay the existing authority.

    Exact source-owned anchors may prove SAME/DISTINCT only when their family
    (anchor kind + explicit registration scope) is comparable across views and
    the exact anchor is unique inside each contributing view.

    Missing or non-unique anchors never select a nearest/first candidate.
    """

    if type(selector) is not StructuralMemberSelector:
        raise TypeError("selector must be StructuralMemberSelector")

    ordered_observations = tuple(sorted(observations, key=lambda row: row.observation_id))
    observation_by_id: Mapping[str, StructuralMemberObservation] = {
        row.observation_id: row for row in ordered_observations
    }
    if len(observation_by_id) != len(ordered_observations):
        # Let the existing authority own the duplicate-id conflict.
        resolution = StructuralMemberProducer.from_authenticated_evidence(
            selector=selector,
            definitions=definitions,
            observations=ordered_observations,
            relations=(),
            view_scopes=view_scopes,
        ).publish()
        audit = StructuralMemberRegistrationAudit(
            relation_count=0,
            same_relation_count=0,
            distinct_relation_count=0,
            ambiguous_anchor_keys=(),
            conflicting_observation_ids=(),
            invalid_observation_ids=tuple(
                sorted(row.observation_id for row in ordered_observations)
            ),
        )
        return StructuralMemberRegistrationShadowResult(
            selector=selector,
            resolution=resolution,
            relations=(),
            view_scopes=tuple(view_scopes),
            reason_codes=(
                STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_INVALID,
                *resolution.reason_codes,
            ),
            audit=audit,
        )

    invalid_observation_ids = tuple(
        sorted(
            {
                anchor.observation_id
                for anchor in anchors
                if anchor.observation_id not in observation_by_id
            }
        )
    )
    valid_anchors = tuple(
        anchor for anchor in anchors if anchor.observation_id in observation_by_id
    )

    # One observation cannot truthfully claim two different exact values for
    # the same registration family. Fail only its view closed.
    per_observation_family: Dict[tuple[str, tuple[str, str]], set[str]] = {}
    for anchor in valid_anchors:
        key = (anchor.observation_id, _anchor_family(anchor))
        per_observation_family.setdefault(key, set()).add(_anchor_value(anchor))

    conflicting_observation_ids = tuple(
        sorted(
            observation_id
            for (observation_id, _family), values in per_observation_family.items()
            if len(values) > 1
        )
    )

    effective_scopes = tuple(view_scopes)
    if invalid_observation_ids:
        effective_scopes = _fail_scopes_for_views(
            effective_scopes,
            tuple(scope.view_id for scope in effective_scopes),
            STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_INVALID,
        )
    if conflicting_observation_ids:
        conflict_views = tuple(
            sorted(
                {
                    observation_by_id[observation_id].view_id
                    for observation_id in conflicting_observation_ids
                }
            )
        )
        effective_scopes = _fail_scopes_for_views(
            effective_scopes,
            conflict_views,
            STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_CONFLICT,
        )

    # A registration key has identity value only if it names at most one
    # observation in each view. Duplicate use in one view makes that key
    # ambiguous, not an invitation to pick the first/nearest instance.
    ids_by_view_key: Dict[tuple[str, tuple[str, str, str]], set[str]] = {}
    for anchor in valid_anchors:
        if anchor.observation_id in conflicting_observation_ids:
            continue
        observation = observation_by_id[anchor.observation_id]
        ids_by_view_key.setdefault(
            (observation.view_id, _anchor_key(anchor)), set()
        ).add(anchor.observation_id)

    ambiguous_keys = {
        key
        for (_view_id, key), observation_ids in ids_by_view_key.items()
        if len(observation_ids) > 1
    }

    usable_by_observation_family: Dict[
        str, Dict[tuple[str, str], StructuralMemberRegistrationAnchor]
    ] = {}
    for anchor in sorted(
        valid_anchors,
        key=lambda row: (
            row.observation_id,
            row.kind.value,
            _normalize_text(row.registration_scope_id),
            _anchor_value(row),
            tuple(sorted(str(e) for e in row.source_evidence_ids)),
        ),
    ):
        if anchor.observation_id in conflicting_observation_ids:
            continue
        if _anchor_key(anchor) in ambiguous_keys:
            continue
        family = _anchor_family(anchor)
        current = usable_by_observation_family.setdefault(
            anchor.observation_id, {}
        ).get(family)
        if current is None:
            usable_by_observation_family[anchor.observation_id][family] = anchor

    relation_evidence: Dict[
        tuple[str, str, StructuralMemberRelation], set[str]
    ] = {}
    for left_index, left in enumerate(ordered_observations):
        for right in ordered_observations[left_index + 1 :]:
            if left.view_id == right.view_id:
                continue
            left_families = usable_by_observation_family.get(left.observation_id, {})
            right_families = usable_by_observation_family.get(right.observation_id, {})
            for family in sorted(set(left_families) & set(right_families)):
                left_anchor = left_families[family]
                right_anchor = right_families[family]
                relation = (
                    StructuralMemberRelation.SAME_PHYSICAL_MEMBER
                    if _anchor_value(left_anchor) == _anchor_value(right_anchor)
                    else StructuralMemberRelation.DISTINCT_PHYSICAL_MEMBERS
                )
                pair = tuple(sorted((left.observation_id, right.observation_id)))
                evidence_key = (pair[0], pair[1], relation)
                relation_evidence.setdefault(evidence_key, set()).update(
                    str(item)
                    for item in (
                        *left_anchor.source_evidence_ids,
                        *right_anchor.source_evidence_ids,
                    )
                )

    relations = tuple(
        StructuralMemberRelationEvidence(
            left_observation_id=left_id,
            right_observation_id=right_id,
            relation=relation,
            source_evidence_ids=tuple(sorted(evidence_ids)),
        )
        for (left_id, right_id, relation), evidence_ids in sorted(
            relation_evidence.items(),
            key=lambda item: (item[0][0], item[0][1], item[0][2].value),
        )
    )

    resolution = StructuralMemberProducer.from_authenticated_evidence(
        selector=selector,
        definitions=definitions,
        observations=ordered_observations,
        relations=relations,
        view_scopes=effective_scopes,
    ).publish()

    reasons = []
    if ambiguous_keys:
        reasons.append(STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_AMBIGUOUS)
    if conflicting_observation_ids:
        reasons.append(STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_CONFLICT)
    if invalid_observation_ids:
        reasons.append(STRUCTURAL_MEMBER_REGISTRATION_ANCHOR_INVALID)
    if (
        resolution.status is EvidenceResolutionStatus.CORROBORATED
        and len({row.view_id for row in ordered_observations}) > 1
    ):
        reasons.append(STRUCTURAL_MEMBER_REGISTRATION_RESOLVED)
    elif resolution.status is not EvidenceResolutionStatus.CORROBORATED:
        reasons.append(STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE)
    reasons.extend(resolution.reason_codes)

    audit = StructuralMemberRegistrationAudit(
        relation_count=len(relations),
        same_relation_count=sum(
            relation.relation is StructuralMemberRelation.SAME_PHYSICAL_MEMBER
            for relation in relations
        ),
        distinct_relation_count=sum(
            relation.relation is StructuralMemberRelation.DISTINCT_PHYSICAL_MEMBERS
            for relation in relations
        ),
        ambiguous_anchor_keys=tuple(sorted(_key_text(key) for key in ambiguous_keys)),
        conflicting_observation_ids=conflicting_observation_ids,
        invalid_observation_ids=invalid_observation_ids,
    )
    return StructuralMemberRegistrationShadowResult(
        selector=selector,
        resolution=resolution,
        relations=relations,
        view_scopes=effective_scopes,
        reason_codes=tuple(dict.fromkeys(reasons)),
        audit=audit,
    )
