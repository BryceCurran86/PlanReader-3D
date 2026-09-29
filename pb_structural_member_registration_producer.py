"""Authenticated cross-view structural-member registration producer.

This module does not discover structural members from arbitrary geometry. It
accepts only source observations that already carry positive member-proposition
evidence, turns them into stable StructuralMemberObservation records, derives
only positive identity/distinctness relations, and delegates final completeness
and quantity publication to StructuralMemberAuthority.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional, Sequence

from pb_migration_contracts import stable_contract_id
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

STRUCTURAL_REGISTRATION_SCHEMA_VERSION = "1.0.0"


class StructuralRegistrationAnchorKind(str, Enum):
    GRID_INTERSECTION = "grid_intersection"
    SOURCE_INSTANCE_MARK = "source_instance_mark"
    PROJECTED_POSITION = "projected_position"
    HOST_LINE_POSITION = "host_line_position"


@dataclass(frozen=True)
class StructuralRegistrationAnchor:
    """One positive source-owned physical registration locator."""

    kind: StructuralRegistrationAnchorKind
    namespace_id: str
    value_id: str
    source_evidence_ids: tuple[str, ...]
    schema_version: str = STRUCTURAL_REGISTRATION_SCHEMA_VERSION


@dataclass(frozen=True)
class AuthenticatedStructuralMemberObservation:
    """Authenticated structural-member source observation.

    member_proposition_evidence_ids is deliberately separate from raw primitive
    evidence. A wall end, jamb, square, or foundation symbol cannot become a
    member observation merely because it has geometry.
    """

    member_kind: str
    page_id: str
    view_id: str
    view_type: str
    source_evidence_ids: tuple[str, ...]
    source_primitive_ids: tuple[str, ...]
    member_proposition_evidence_ids: tuple[str, ...]
    registration_anchors: tuple[StructuralRegistrationAnchor, ...] = ()
    definition_id: Optional[str] = None
    geometry_signature: str = ""
    schema_version: str = STRUCTURAL_REGISTRATION_SCHEMA_VERSION


@dataclass(frozen=True)
class AuthenticatedStructuralMemberView:
    page_id: str
    view_id: str
    view_type: str
    complete: bool
    source_evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...] = ()
    schema_version: str = STRUCTURAL_REGISTRATION_SCHEMA_VERSION


@dataclass(frozen=True)
class StructuralMemberRegistrationResult:
    selector: StructuralMemberSelector
    observations: tuple[StructuralMemberObservation, ...]
    relations: tuple[StructuralMemberRelationEvidence, ...]
    view_scopes: tuple[StructuralMemberViewScope, ...]
    resolution: StructuralMemberResolution
    schema_version: str = STRUCTURAL_REGISTRATION_SCHEMA_VERSION


def _clean_nonempty(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted({str(value).strip() for value in values if str(value).strip()}))


def _observation_id(
    selector: StructuralMemberSelector,
    source: AuthenticatedStructuralMemberObservation,
) -> str:
    return stable_contract_id(
        "structural_observation_v1",
        {
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "member_kind": source.member_kind.strip().lower(),
            "page_id": source.page_id,
            "view_id": source.view_id,
            "view_type": source.view_type,
            "source_evidence_ids": _clean_nonempty(source.source_evidence_ids),
            "source_primitive_ids": _clean_nonempty(source.source_primitive_ids),
            "member_proposition_evidence_ids": _clean_nonempty(
                source.member_proposition_evidence_ids
            ),
            "definition_id": source.definition_id or "",
        },
        digest_chars=32,
    )


def _relation_evidence_ids(
    left: AuthenticatedStructuralMemberObservation,
    right: AuthenticatedStructuralMemberObservation,
    *,
    extra: Sequence[str] = (),
) -> tuple[str, ...]:
    return _clean_nonempty(
        (
            *left.member_proposition_evidence_ids,
            *right.member_proposition_evidence_ids,
            *extra,
        )
    )


def _anchor_map(
    source: AuthenticatedStructuralMemberObservation,
) -> dict[
    tuple[StructuralRegistrationAnchorKind, str],
    dict[str, StructuralRegistrationAnchor],
]:
    out: dict[
        tuple[StructuralRegistrationAnchorKind, str],
        dict[str, StructuralRegistrationAnchor],
    ] = {}
    for anchor in source.registration_anchors:
        namespace = str(anchor.namespace_id).strip()
        value = str(anchor.value_id).strip()
        evidence = _clean_nonempty(anchor.source_evidence_ids)
        if not namespace or not value or not evidence:
            continue
        out.setdefault((anchor.kind, namespace), {})[value] = anchor
    return out


def _pair_relations(
    left_id: str,
    left: AuthenticatedStructuralMemberObservation,
    right_id: str,
    right: AuthenticatedStructuralMemberObservation,
) -> tuple[StructuralMemberRelationEvidence, ...]:
    relations: list[StructuralMemberRelationEvidence] = []

    shared_primitives = tuple(
        sorted(
            set(_clean_nonempty(left.source_primitive_ids))
            & set(_clean_nonempty(right.source_primitive_ids))
        )
    )
    if shared_primitives:
        relations.append(
            StructuralMemberRelationEvidence(
                left_observation_id=left_id,
                right_observation_id=right_id,
                relation=StructuralMemberRelation.SAME_PHYSICAL_MEMBER,
                source_evidence_ids=_relation_evidence_ids(
                    left,
                    right,
                    extra=shared_primitives,
                ),
            )
        )

    left_anchors = _anchor_map(left)
    right_anchors = _anchor_map(right)
    for namespace_key in sorted(
        set(left_anchors) & set(right_anchors),
        key=lambda item: (item[0].value, item[1]),
    ):
        left_values = left_anchors[namespace_key]
        right_values = right_anchors[namespace_key]
        shared_values = sorted(set(left_values) & set(right_values))
        for value in shared_values:
            evidence = (
                *left_values[value].source_evidence_ids,
                *right_values[value].source_evidence_ids,
            )
            relations.append(
                StructuralMemberRelationEvidence(
                    left_observation_id=left_id,
                    right_observation_id=right_id,
                    relation=StructuralMemberRelation.SAME_PHYSICAL_MEMBER,
                    source_evidence_ids=_relation_evidence_ids(
                        left,
                        right,
                        extra=evidence,
                    ),
                )
            )

        if shared_values:
            continue

        if left_values and right_values:
            evidence = tuple(
                evidence_id
                for anchor in (*left_values.values(), *right_values.values())
                for evidence_id in anchor.source_evidence_ids
            )
            relations.append(
                StructuralMemberRelationEvidence(
                    left_observation_id=left_id,
                    right_observation_id=right_id,
                    relation=StructuralMemberRelation.DISTINCT_PHYSICAL_MEMBERS,
                    source_evidence_ids=_relation_evidence_ids(
                        left,
                        right,
                        extra=evidence,
                    ),
                )
            )

    unique: dict[
        tuple[str, str, StructuralMemberRelation],
        StructuralMemberRelationEvidence,
    ] = {}
    for relation in relations:
        key = (
            relation.left_observation_id,
            relation.right_observation_id,
            relation.relation,
        )
        existing = unique.get(key)
        if existing is None:
            unique[key] = relation
        else:
            unique[key] = StructuralMemberRelationEvidence(
                left_observation_id=relation.left_observation_id,
                right_observation_id=relation.right_observation_id,
                relation=relation.relation,
                source_evidence_ids=_clean_nonempty(
                    (*existing.source_evidence_ids, *relation.source_evidence_ids)
                ),
            )
    return tuple(
        unique[key]
        for key in sorted(unique, key=lambda item: (item[0], item[1], item[2].value))
    )


def build_structural_member_registration_authority(
    *,
    selector: StructuralMemberSelector,
    source_observations: Sequence[AuthenticatedStructuralMemberObservation],
    source_views: Sequence[AuthenticatedStructuralMemberView],
    definitions: Sequence[StructuralMemberDefinition] = (),
) -> StructuralMemberRegistrationResult:
    """Build authority inputs from authenticated source evidence."""

    if type(selector) is not StructuralMemberSelector:
        raise TypeError("selector must be StructuralMemberSelector")

    kind = selector.member_kind.strip().lower()
    accepted: list[
        tuple[str, AuthenticatedStructuralMemberObservation, StructuralMemberObservation]
    ] = []
    for source in source_observations:
        if source.member_kind.strip().lower() != kind:
            continue
        proposition_ids = _clean_nonempty(source.member_proposition_evidence_ids)
        evidence_ids = _clean_nonempty(source.source_evidence_ids)
        primitive_ids = _clean_nonempty(source.source_primitive_ids)
        if not proposition_ids or not evidence_ids:
            continue
        observation_id = _observation_id(selector, source)
        accepted.append(
            (
                observation_id,
                source,
                StructuralMemberObservation(
                    observation_id=observation_id,
                    member_kind=kind,
                    page_id=str(source.page_id),
                    view_id=str(source.view_id),
                    view_type=str(source.view_type),
                    source_evidence_ids=_clean_nonempty(
                        (*evidence_ids, *proposition_ids)
                    ),
                    source_primitive_ids=primitive_ids,
                    definition_id=source.definition_id,
                ),
            )
        )

    by_id: dict[
        str,
        tuple[AuthenticatedStructuralMemberObservation, StructuralMemberObservation],
    ] = {}
    for observation_id, source, observation in accepted:
        prior = by_id.get(observation_id)
        if prior is None:
            by_id[observation_id] = (source, observation)
        elif prior[1] != observation:
            raise RuntimeError("structural observation id equivocation")

    ordered = [(oid, *by_id[oid]) for oid in sorted(by_id)]
    relations: list[StructuralMemberRelationEvidence] = []
    for index, (left_id, left_source, _) in enumerate(ordered):
        for right_id, right_source, _ in ordered[index + 1 :]:
            relations.extend(
                _pair_relations(
                    left_id,
                    left_source,
                    right_id,
                    right_source,
                )
            )

    view_scopes = tuple(
        StructuralMemberViewScope(
            page_id=str(view.page_id),
            view_id=str(view.view_id),
            view_type=str(view.view_type),
            complete=bool(view.complete),
            reason_codes=_clean_nonempty(view.reason_codes),
        )
        for view in sorted(
            source_views,
            key=lambda row: (str(row.view_id), str(row.page_id)),
        )
    )
    observations = tuple(row[2] for row in ordered)
    relation_rows = tuple(
        sorted(
            relations,
            key=lambda row: (
                row.left_observation_id,
                row.right_observation_id,
                row.relation.value,
                row.source_evidence_ids,
            ),
        )
    )
    resolution = StructuralMemberProducer.from_authenticated_evidence(
        selector=selector,
        definitions=tuple(definitions),
        observations=observations,
        relations=relation_rows,
        view_scopes=view_scopes,
    ).publish()
    return StructuralMemberRegistrationResult(
        selector=selector,
        observations=observations,
        relations=relation_rows,
        view_scopes=view_scopes,
        resolution=resolution,
    )
