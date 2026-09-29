"""Authenticated cross-view structural-member registration producer.

This module does not discover structural members from arbitrary geometry. It
accepts only source-scoped observations carrying positive member-proposition
evidence, derives conservative cross-view relation evidence, and delegates
final completeness and quantity publication to StructuralMemberAuthority.

The input records remain plain dataclasses so TEST-ONLY diagnostics can inspect
and construct deliberately unauthenticated rows. Publication, however, accepts
only rows minted by StructuralMemberRegistrationEvidenceProducer. Directly
constructed or mutated rows fail closed.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_structural_member_authority import (
    STRUCTURAL_MEMBER_RELATION_CONFLICT,
    STRUCTURAL_MEMBER_SCOPE_INCOMPLETE,
    StructuralMemberDefinition,
    StructuralMemberObservation,
    StructuralMemberProducer,
    StructuralMemberRelation,
    StructuralMemberRelationEvidence,
    StructuralMemberResolution,
    StructuralMemberSelector,
    StructuralMemberViewScope,
)

STRUCTURAL_REGISTRATION_SCHEMA_VERSION = "2.0.0"

STRUCTURAL_REGISTRATION_INPUT_UNAUTHENTICATED = (
    "structural_registration_input_unauthenticated"
)
STRUCTURAL_REGISTRATION_SOURCE_SCOPE_MISMATCH = (
    "structural_registration_source_scope_mismatch"
)
STRUCTURAL_REGISTRATION_OBSERVATION_EQUIVOCATION = (
    "structural_registration_observation_equivocation"
)
STRUCTURAL_REGISTRATION_ANCHOR_CONFLICT = (
    "structural_registration_anchor_conflict"
)
STRUCTURAL_REGISTRATION_ANCHOR_AMBIGUOUS = (
    "structural_registration_anchor_ambiguous"
)
STRUCTURAL_REGISTRATION_VIEW_OWNERSHIP_CONFLICT = (
    "structural_registration_view_ownership_conflict"
)

_SOURCE_INPUT_SEAL = object()
_EVIDENCE_PRODUCER_SEAL = object()


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
    """Source-scoped structural-member observation.

    Rows constructed directly are intentionally non-authoritative. The
    registration builder checks the producer seal, exact source lineage,
    source-scope receipt, and deterministic record id before consuming one.
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
    document_id: str = ""
    revision_id: str = ""
    source_sha256: str = ""
    snapshot_id: str = ""
    source_scope_receipt_id: str = ""
    record_id: str = ""
    schema_version: str = STRUCTURAL_REGISTRATION_SCHEMA_VERSION
    _producer_seal: object = field(
        default=None,
        repr=False,
        compare=False,
    )


@dataclass(frozen=True)
class AuthenticatedStructuralMemberView:
    page_id: str
    view_id: str
    view_type: str
    complete: bool
    source_evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...] = ()
    document_id: str = ""
    revision_id: str = ""
    source_sha256: str = ""
    snapshot_id: str = ""
    source_scope_receipt_id: str = ""
    record_id: str = ""
    schema_version: str = STRUCTURAL_REGISTRATION_SCHEMA_VERSION
    _producer_seal: object = field(
        default=None,
        repr=False,
        compare=False,
    )


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


def _selector_source_payload(selector: StructuralMemberSelector) -> dict[str, str]:
    return {
        "document_id": str(selector.document_id),
        "revision_id": str(selector.revision_id),
        "source_sha256": str(selector.source_sha256),
        "snapshot_id": str(selector.snapshot_id),
    }


def _source_scope_receipt_id(selector: StructuralMemberSelector) -> str:
    return stable_contract_id(
        "structural_registration_source_scope_v2",
        _selector_source_payload(selector),
        digest_chars=32,
    )


def _normalised_anchor_payload(
    anchors: Sequence[StructuralRegistrationAnchor],
) -> tuple[dict[str, object], ...]:
    rows = []
    for anchor in anchors:
        if type(anchor) is not StructuralRegistrationAnchor:
            raise TypeError("registration anchors must be StructuralRegistrationAnchor")
        namespace = str(anchor.namespace_id).strip()
        value = str(anchor.value_id).strip()
        evidence = _clean_nonempty(anchor.source_evidence_ids)
        if (
            type(anchor.kind) is not StructuralRegistrationAnchorKind
            or not namespace
            or not value
            or not evidence
        ):
            raise ValueError("registration anchor must have kind, namespace, value, and evidence")
        rows.append(
            {
                "kind": anchor.kind.value,
                "namespace_id": namespace,
                "value_id": value,
                "source_evidence_ids": evidence,
            }
        )
    return tuple(
        sorted(
            rows,
            key=lambda row: (
                str(row["kind"]),
                str(row["namespace_id"]),
                str(row["value_id"]),
                tuple(row["source_evidence_ids"]),
            ),
        )
    )


def _observation_record_payload(
    selector: StructuralMemberSelector,
    *,
    member_kind: str,
    page_id: str,
    view_id: str,
    view_type: str,
    source_evidence_ids: Sequence[str],
    source_primitive_ids: Sequence[str],
    member_proposition_evidence_ids: Sequence[str],
    registration_anchors: Sequence[StructuralRegistrationAnchor],
    definition_id: Optional[str],
    geometry_signature: str,
) -> dict[str, object]:
    return {
        **_selector_source_payload(selector),
        "source_scope_receipt_id": _source_scope_receipt_id(selector),
        "member_kind": str(member_kind).strip().lower(),
        "page_id": str(page_id),
        "view_id": str(view_id),
        "view_type": str(view_type),
        "source_evidence_ids": _clean_nonempty(source_evidence_ids),
        "source_primitive_ids": _clean_nonempty(source_primitive_ids),
        "member_proposition_evidence_ids": _clean_nonempty(
            member_proposition_evidence_ids
        ),
        "registration_anchors": _normalised_anchor_payload(registration_anchors),
        "definition_id": str(definition_id or ""),
        "geometry_signature": str(geometry_signature or ""),
    }


def _view_record_payload(
    selector: StructuralMemberSelector,
    *,
    page_id: str,
    view_id: str,
    view_type: str,
    complete: bool,
    source_evidence_ids: Sequence[str],
    reason_codes: Sequence[str],
) -> dict[str, object]:
    return {
        **_selector_source_payload(selector),
        "source_scope_receipt_id": _source_scope_receipt_id(selector),
        "page_id": str(page_id),
        "view_id": str(view_id),
        "view_type": str(view_type),
        "complete": bool(complete),
        "source_evidence_ids": _clean_nonempty(source_evidence_ids),
        "reason_codes": _clean_nonempty(reason_codes),
    }


class StructuralMemberRegistrationEvidenceProducer:
    """Producer boundary for source-scoped structural registration inputs.

    Production construction requires an exact SourceVisibilityProducer snapshot.
    The test factory exists only for deterministic synthetic/adversarial tests.
    Neither path proves member semantics by itself; proposition evidence remains
    an upstream responsibility.
    """

    def __init__(
        self,
        *,
        selector: StructuralMemberSelector,
        source_scope_receipt_id: str,
        _seal: object = None,
    ) -> None:
        if _seal is not _EVIDENCE_PRODUCER_SEAL:
            raise TypeError(
                "Use from_source_visibility() or create_for_tests()"
            )
        self._selector = selector
        self._source_scope_receipt_id = source_scope_receipt_id

    @classmethod
    def from_source_visibility(
        cls,
        *,
        selector: StructuralMemberSelector,
        source_visibility_producer,
    ) -> "StructuralMemberRegistrationEvidenceProducer":
        from pb_source_visibility_authority import SourceVisibilityProducer

        if type(selector) is not StructuralMemberSelector:
            raise TypeError("selector must be StructuralMemberSelector")
        if type(source_visibility_producer) is not SourceVisibilityProducer:
            raise TypeError(
                "source_visibility_producer must be producer-owned "
                "SourceVisibilityProducer"
            )
        published = source_visibility_producer.published_snapshot_for_revision(
            selector.revision_id
        )
        if published is None:
            raise ValueError(STRUCTURAL_REGISTRATION_INPUT_UNAUTHENTICATED)
        if (
            str(published.revision.document_id) != str(selector.document_id)
            or str(published.revision.revision_id) != str(selector.revision_id)
            or str(published.revision.source_sha256) != str(selector.source_sha256)
            or str(published.snapshot.snapshot_id) != str(selector.snapshot_id)
        ):
            raise ValueError(STRUCTURAL_REGISTRATION_SOURCE_SCOPE_MISMATCH)
        return cls(
            selector=selector,
            source_scope_receipt_id=_source_scope_receipt_id(selector),
            _seal=_EVIDENCE_PRODUCER_SEAL,
        )

    @classmethod
    def create_for_tests(
        cls,
        *,
        selector: StructuralMemberSelector,
    ) -> "StructuralMemberRegistrationEvidenceProducer":
        if type(selector) is not StructuralMemberSelector:
            raise TypeError("selector must be StructuralMemberSelector")
        return cls(
            selector=selector,
            source_scope_receipt_id=_source_scope_receipt_id(selector),
            _seal=_EVIDENCE_PRODUCER_SEAL,
        )

    def observation(
        self,
        *,
        member_kind: str,
        page_id: str,
        view_id: str,
        view_type: str,
        source_evidence_ids: Sequence[str],
        source_primitive_ids: Sequence[str],
        member_proposition_evidence_ids: Sequence[str],
        registration_anchors: Sequence[StructuralRegistrationAnchor] = (),
        definition_id: Optional[str] = None,
        geometry_signature: str = "",
    ) -> AuthenticatedStructuralMemberObservation:
        payload = _observation_record_payload(
            self._selector,
            member_kind=member_kind,
            page_id=page_id,
            view_id=view_id,
            view_type=view_type,
            source_evidence_ids=source_evidence_ids,
            source_primitive_ids=source_primitive_ids,
            member_proposition_evidence_ids=member_proposition_evidence_ids,
            registration_anchors=registration_anchors,
            definition_id=definition_id,
            geometry_signature=geometry_signature,
        )
        record_id = stable_contract_id(
            "authenticated_structural_member_observation_v2",
            payload,
            digest_chars=32,
        )
        return AuthenticatedStructuralMemberObservation(
            member_kind=str(member_kind),
            page_id=str(page_id),
            view_id=str(view_id),
            view_type=str(view_type),
            source_evidence_ids=_clean_nonempty(source_evidence_ids),
            source_primitive_ids=_clean_nonempty(source_primitive_ids),
            member_proposition_evidence_ids=_clean_nonempty(
                member_proposition_evidence_ids
            ),
            registration_anchors=tuple(registration_anchors),
            definition_id=definition_id,
            geometry_signature=str(geometry_signature or ""),
            document_id=str(self._selector.document_id),
            revision_id=str(self._selector.revision_id),
            source_sha256=str(self._selector.source_sha256),
            snapshot_id=str(self._selector.snapshot_id),
            source_scope_receipt_id=self._source_scope_receipt_id,
            record_id=record_id,
            _producer_seal=_SOURCE_INPUT_SEAL,
        )

    def view(
        self,
        *,
        page_id: str,
        view_id: str,
        view_type: str,
        complete: bool,
        source_evidence_ids: Sequence[str],
        reason_codes: Sequence[str] = (),
    ) -> AuthenticatedStructuralMemberView:
        payload = _view_record_payload(
            self._selector,
            page_id=page_id,
            view_id=view_id,
            view_type=view_type,
            complete=complete,
            source_evidence_ids=source_evidence_ids,
            reason_codes=reason_codes,
        )
        record_id = stable_contract_id(
            "authenticated_structural_member_view_v2",
            payload,
            digest_chars=32,
        )
        return AuthenticatedStructuralMemberView(
            page_id=str(page_id),
            view_id=str(view_id),
            view_type=str(view_type),
            complete=bool(complete),
            source_evidence_ids=_clean_nonempty(source_evidence_ids),
            reason_codes=_clean_nonempty(reason_codes),
            document_id=str(self._selector.document_id),
            revision_id=str(self._selector.revision_id),
            source_sha256=str(self._selector.source_sha256),
            snapshot_id=str(self._selector.snapshot_id),
            source_scope_receipt_id=self._source_scope_receipt_id,
            record_id=record_id,
            _producer_seal=_SOURCE_INPUT_SEAL,
        )


def _observation_is_authenticated(
    selector: StructuralMemberSelector,
    source: object,
) -> bool:
    if type(source) is not AuthenticatedStructuralMemberObservation:
        return False
    if source._producer_seal is not _SOURCE_INPUT_SEAL:
        return False
    expected_source = _selector_source_payload(selector)
    if (
        source.document_id != expected_source["document_id"]
        or source.revision_id != expected_source["revision_id"]
        or source.source_sha256 != expected_source["source_sha256"]
        or source.snapshot_id != expected_source["snapshot_id"]
        or source.source_scope_receipt_id != _source_scope_receipt_id(selector)
    ):
        return False
    try:
        payload = _observation_record_payload(
            selector,
            member_kind=source.member_kind,
            page_id=source.page_id,
            view_id=source.view_id,
            view_type=source.view_type,
            source_evidence_ids=source.source_evidence_ids,
            source_primitive_ids=source.source_primitive_ids,
            member_proposition_evidence_ids=source.member_proposition_evidence_ids,
            registration_anchors=source.registration_anchors,
            definition_id=source.definition_id,
            geometry_signature=source.geometry_signature,
        )
    except (TypeError, ValueError):
        return False
    expected_id = stable_contract_id(
        "authenticated_structural_member_observation_v2",
        payload,
        digest_chars=32,
    )
    return source.record_id == expected_id


def _view_is_authenticated(
    selector: StructuralMemberSelector,
    source: object,
) -> bool:
    if type(source) is not AuthenticatedStructuralMemberView:
        return False
    if source._producer_seal is not _SOURCE_INPUT_SEAL:
        return False
    expected_source = _selector_source_payload(selector)
    if (
        source.document_id != expected_source["document_id"]
        or source.revision_id != expected_source["revision_id"]
        or source.source_sha256 != expected_source["source_sha256"]
        or source.snapshot_id != expected_source["snapshot_id"]
        or source.source_scope_receipt_id != _source_scope_receipt_id(selector)
    ):
        return False
    payload = _view_record_payload(
        selector,
        page_id=source.page_id,
        view_id=source.view_id,
        view_type=source.view_type,
        complete=source.complete,
        source_evidence_ids=source.source_evidence_ids,
        reason_codes=source.reason_codes,
    )
    expected_id = stable_contract_id(
        "authenticated_structural_member_view_v2",
        payload,
        digest_chars=32,
    )
    return source.record_id == expected_id


def _observation_source_key(
    selector: StructuralMemberSelector,
    source: AuthenticatedStructuralMemberObservation,
) -> str:
    """Identity of the source proposition before registration interpretation."""
    return stable_contract_id(
        "structural_observation_source_key_v2",
        {
            **_selector_source_payload(selector),
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


def _observation_id(
    selector: StructuralMemberSelector,
    source: AuthenticatedStructuralMemberObservation,
) -> str:
    return stable_contract_id(
        "structural_observation_v2",
        {
            "source_key": _observation_source_key(selector, source),
            "record_id": source.record_id,
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
    *,
    banned_values: set[tuple[str, str, str]] | None = None,
) -> dict[
    tuple[StructuralRegistrationAnchorKind, str],
    dict[str, tuple[str, ...]],
]:
    """Return all anchor evidence without first/last overwrite."""
    banned_values = banned_values or set()
    out: dict[
        tuple[StructuralRegistrationAnchorKind, str],
        dict[str, tuple[str, ...]],
    ] = {}
    evidence_sets: dict[
        tuple[StructuralRegistrationAnchorKind, str, str],
        set[str],
    ] = {}
    for anchor in source.registration_anchors:
        namespace = str(anchor.namespace_id).strip()
        value = str(anchor.value_id).strip()
        evidence = _clean_nonempty(anchor.source_evidence_ids)
        if (
            type(anchor.kind) is not StructuralRegistrationAnchorKind
            or not namespace
            or not value
            or not evidence
        ):
            continue
        simple_key = (anchor.kind.value, namespace, value)
        if simple_key in banned_values:
            continue
        evidence_sets.setdefault((anchor.kind, namespace, value), set()).update(
            evidence
        )

    for (kind, namespace, value), evidence in evidence_sets.items():
        out.setdefault((kind, namespace), {})[value] = tuple(sorted(evidence))
    return out


def _anchor_family_conflicts(
    source: AuthenticatedStructuralMemberObservation,
) -> tuple[tuple[str, str], ...]:
    values_by_family: dict[tuple[str, str], set[str]] = {}
    for anchor in source.registration_anchors:
        if type(anchor) is not StructuralRegistrationAnchor:
            continue
        namespace = str(anchor.namespace_id).strip()
        value = str(anchor.value_id).strip()
        if (
            type(anchor.kind) is not StructuralRegistrationAnchorKind
            or not namespace
            or not value
            or not _clean_nonempty(anchor.source_evidence_ids)
        ):
            continue
        values_by_family.setdefault((anchor.kind.value, namespace), set()).add(value)
    return tuple(
        sorted(
            family
            for family, values in values_by_family.items()
            if len(values) > 1
        )
    )


def _ambiguous_anchor_values(
    sources: Sequence[AuthenticatedStructuralMemberObservation],
) -> tuple[
    set[tuple[str, str, str]],
    set[str],
]:
    """Find anchor values naming multiple observations in one view."""
    observations_by_view_value: dict[
        tuple[str, str, str, str],
        set[str],
    ] = {}
    for source in sources:
        source_key = source.record_id
        seen_for_source = set()
        for anchor in source.registration_anchors:
            if (
                type(anchor) is not StructuralRegistrationAnchor
                or type(anchor.kind) is not StructuralRegistrationAnchorKind
            ):
                continue
            namespace = str(anchor.namespace_id).strip()
            value = str(anchor.value_id).strip()
            if not namespace or not value or not _clean_nonempty(anchor.source_evidence_ids):
                continue
            local = (anchor.kind.value, namespace, value)
            if local in seen_for_source:
                continue
            seen_for_source.add(local)
            observations_by_view_value.setdefault(
                (source.view_id, *local),
                set(),
            ).add(source_key)

    ambiguous_values: set[tuple[str, str, str]] = set()
    ambiguous_views: set[str] = set()
    for (view_id, kind, namespace, value), source_ids in (
        observations_by_view_value.items()
    ):
        if len(source_ids) > 1:
            ambiguous_values.add((kind, namespace, value))
            ambiguous_views.add(view_id)
    return ambiguous_values, ambiguous_views


def _pair_relations(
    left_id: str,
    left: AuthenticatedStructuralMemberObservation,
    right_id: str,
    right: AuthenticatedStructuralMemberObservation,
    *,
    banned_anchor_values: set[tuple[str, str, str]],
) -> tuple[StructuralMemberRelationEvidence, ...]:
    relations: list[StructuralMemberRelationEvidence] = []

    # A raw primitive id is page/view-local unless an upstream producer proves
    # a cross-view registration. It may collapse duplicate representations in
    # the same exact view, but cannot by itself establish cross-view identity.
    if left.page_id == right.page_id and left.view_id == right.view_id:
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
        return tuple(relations)

    # Cross-view anchor evidence is never applied between two observations from
    # the same view id. Same-view instances remain distinct unless they share an
    # exact source primitive representation as handled above.
    if left.view_id == right.view_id:
        return ()

    left_anchors = _anchor_map(left, banned_values=banned_anchor_values)
    right_anchors = _anchor_map(right, banned_values=banned_anchor_values)
    for namespace_key in sorted(
        set(left_anchors) & set(right_anchors),
        key=lambda item: (item[0].value, item[1]),
    ):
        left_values = left_anchors[namespace_key]
        right_values = right_anchors[namespace_key]
        shared_values = sorted(set(left_values) & set(right_values))
        for value in shared_values:
            evidence = (
                *left_values[value],
                *right_values[value],
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
                for evidence_ids in (*left_values.values(), *right_values.values())
                for evidence_id in evidence_ids
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


def _blocked_result(
    *,
    selector: StructuralMemberSelector,
    status: EvidenceResolutionStatus,
    reason_codes: Sequence[str],
    observations: Sequence[StructuralMemberObservation] = (),
    view_scopes: Sequence[StructuralMemberViewScope] = (),
    definitions: Sequence[StructuralMemberDefinition] = (),
) -> StructuralMemberRegistrationResult:
    resolution = StructuralMemberResolution(
        status=status,
        reason_codes=tuple(dict.fromkeys(str(reason) for reason in reason_codes)),
        selector=selector,
        members=(),
        definitions=tuple(definitions),
        unresolved_observation_ids=tuple(
            sorted(observation.observation_id for observation in observations)
        ),
    )
    return StructuralMemberRegistrationResult(
        selector=selector,
        observations=tuple(observations),
        relations=(),
        view_scopes=tuple(view_scopes),
        resolution=resolution,
    )


def build_structural_member_registration_authority(
    *,
    selector: StructuralMemberSelector,
    source_observations: Sequence[AuthenticatedStructuralMemberObservation],
    source_views: Sequence[AuthenticatedStructuralMemberView],
    definitions: Sequence[StructuralMemberDefinition] = (),
) -> StructuralMemberRegistrationResult:
    """Build authority inputs from producer-authenticated source evidence."""

    if type(selector) is not StructuralMemberSelector:
        raise TypeError("selector must be StructuralMemberSelector")

    source_observations = tuple(source_observations)
    source_views = tuple(source_views)

    if any(
        not _observation_is_authenticated(selector, source)
        for source in source_observations
    ) or any(not _view_is_authenticated(selector, view) for view in source_views):
        return _blocked_result(
            selector=selector,
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(
                STRUCTURAL_MEMBER_SCOPE_INCOMPLETE,
                STRUCTURAL_REGISTRATION_INPUT_UNAUTHENTICATED,
            ),
            definitions=definitions,
        )

    kind = selector.member_kind.strip().lower()
    eligible_sources = tuple(
        source
        for source in source_observations
        if source.member_kind.strip().lower() == kind
    )

    # Exact duplicate source propositions are harmless. The same source
    # proposition carrying different anchors/geometry is equivocation, not two
    # independent physical members.
    by_source_key: dict[str, AuthenticatedStructuralMemberObservation] = {}
    for source in eligible_sources:
        source_key = _observation_source_key(selector, source)
        prior = by_source_key.get(source_key)
        if prior is None:
            by_source_key[source_key] = source
        elif prior != source:
            return _blocked_result(
                selector=selector,
                status=EvidenceResolutionStatus.CONFLICT,
                reason_codes=(
                    STRUCTURAL_MEMBER_RELATION_CONFLICT,
                    STRUCTURAL_REGISTRATION_OBSERVATION_EQUIVOCATION,
                ),
                definitions=definitions,
            )

    eligible_sources = tuple(
        by_source_key[key] for key in sorted(by_source_key)
    )

    # Contradictory values for one anchor family on one observation are source
    # conflict. Do not let a shared value hide the contradictory sibling value.
    if any(_anchor_family_conflicts(source) for source in eligible_sources):
        return _blocked_result(
            selector=selector,
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(
                STRUCTURAL_MEMBER_RELATION_CONFLICT,
                STRUCTURAL_REGISTRATION_ANCHOR_CONFLICT,
            ),
            definitions=definitions,
        )

    accepted: list[
        tuple[str, AuthenticatedStructuralMemberObservation, StructuralMemberObservation]
    ] = []
    for source in eligible_sources:
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

    ordered = tuple(sorted(accepted, key=lambda row: row[0]))

    grouped_views: dict[str, list[AuthenticatedStructuralMemberView]] = {}
    for view in source_views:
        grouped_views.setdefault(str(view.view_id), []).append(view)

    ambiguous_values, ambiguous_views = _ambiguous_anchor_values(
        tuple(row[1] for row in ordered)
    )

    view_scope_rows: list[StructuralMemberViewScope] = []
    for view_id in sorted(grouped_views):
        group = grouped_views[view_id]
        signatures = {
            (
                str(view.page_id),
                str(view.view_type),
                bool(view.complete),
                _clean_nonempty(view.source_evidence_ids),
                _clean_nonempty(view.reason_codes),
            )
            for view in group
        }
        first = sorted(
            group,
            key=lambda row: (
                str(row.page_id),
                str(row.view_type),
                bool(row.complete),
                row.record_id,
            ),
        )[0]
        evidence_ids = _clean_nonempty(first.source_evidence_ids)
        reasons = list(_clean_nonempty(first.reason_codes))
        complete = bool(first.complete) and bool(evidence_ids)
        if bool(first.complete) and not evidence_ids:
            reasons.append("structural_view_completeness_unproven")
        if len(signatures) > 1:
            complete = False
            reasons.append("structural_view_scope_conflict")
        if view_id in ambiguous_views:
            complete = False
            reasons.append(STRUCTURAL_REGISTRATION_ANCHOR_AMBIGUOUS)

        matching_observations = [
            source
            for _, source, _ in ordered
            if source.view_id == view_id
        ]
        if any(
            source.page_id != first.page_id
            or source.view_type != first.view_type
            for source in matching_observations
        ):
            complete = False
            reasons.append(STRUCTURAL_REGISTRATION_VIEW_OWNERSHIP_CONFLICT)

        view_scope_rows.append(
            StructuralMemberViewScope(
                page_id=str(first.page_id),
                view_id=view_id,
                view_type=str(first.view_type),
                complete=complete,
                reason_codes=_clean_nonempty(reasons),
            )
        )

    view_scopes = tuple(view_scope_rows)
    observations = tuple(row[2] for row in ordered)

    relations: list[StructuralMemberRelationEvidence] = []
    for index, (left_id, left_source, _) in enumerate(ordered):
        for right_id, right_source, _ in ordered[index + 1 :]:
            relations.extend(
                _pair_relations(
                    left_id,
                    left_source,
                    right_id,
                    right_source,
                    banned_anchor_values=ambiguous_values,
                )
            )

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


__all__ = [
    "AuthenticatedStructuralMemberObservation",
    "AuthenticatedStructuralMemberView",
    "STRUCTURAL_REGISTRATION_ANCHOR_AMBIGUOUS",
    "STRUCTURAL_REGISTRATION_ANCHOR_CONFLICT",
    "STRUCTURAL_REGISTRATION_INPUT_UNAUTHENTICATED",
    "STRUCTURAL_REGISTRATION_OBSERVATION_EQUIVOCATION",
    "STRUCTURAL_REGISTRATION_SCHEMA_VERSION",
    "STRUCTURAL_REGISTRATION_SOURCE_SCOPE_MISMATCH",
    "STRUCTURAL_REGISTRATION_VIEW_OWNERSHIP_CONFLICT",
    "StructuralMemberRegistrationEvidenceProducer",
    "StructuralMemberRegistrationResult",
    "StructuralRegistrationAnchor",
    "StructuralRegistrationAnchorKind",
    "build_structural_member_registration_authority",
]
