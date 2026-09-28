"""Producer-owned structural-member definition, identity, and completeness authority.

This module deliberately separates a member definition (for example a schedule
definition such as "50 mm CHS pillar") from physical member instances. A
definition never creates quantity. Quantity is published only when producer-owned
physical instances are complete for the requested scope and cross-view identity
is positively reconciled.

No proximity-only deduplication, benchmark expectation, caller count, nearest
choice, or default quantity enters this authority.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id


STRUCTURAL_MEMBER_SCHEMA_VERSION = "1.0.0"

STRUCTURAL_MEMBER_RESOLVED = "structural_member_quantity_resolved"
STRUCTURAL_MEMBER_DEFINITION_UNAVAILABLE = "structural_member_definition_unavailable"
STRUCTURAL_MEMBER_INSTANCE_UNAVAILABLE = "structural_member_physical_instance_unavailable"
STRUCTURAL_MEMBER_COMPLETENESS_UNAVAILABLE = "structural_member_completeness_unavailable"
STRUCTURAL_MEMBER_SCOPE_CROPPED = "structural_member_scope_cropped"
STRUCTURAL_MEMBER_CONTINUATION_UNRESOLVED = "structural_member_continuation_unresolved"
STRUCTURAL_MEMBER_BAYS_INCOMPLETE = "structural_member_bays_incomplete"
STRUCTURAL_MEMBER_CROSS_VIEW_REGISTRATION_AMBIGUOUS = (
    "structural_member_cross_view_registration_ambiguous"
)
STRUCTURAL_MEMBER_VIEW_COUNT_CONFLICT = "structural_member_view_count_conflict"
STRUCTURAL_MEMBER_IDENTITY_CONFLICT = "structural_member_identity_conflict"
STRUCTURAL_MEMBER_IDENTITY_AMBIGUOUS = "structural_member_identity_ambiguous"
STRUCTURAL_MEMBER_INSTANCE_EVIDENCE_INSUFFICIENT = (
    "structural_member_instance_evidence_insufficient"
)

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()


class StructuralMemberIdentityClass(str, Enum):
    SAME_PHYSICAL_MEMBER = "same_physical_member"
    DISTINCT_PHYSICAL_MEMBERS = "distinct_physical_members"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class StructuralMemberDefinition:
    definition_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    member_kind: str
    section_text: str
    source_evidence_ids: tuple[str, ...]
    source_page_ids: tuple[str, ...]
    source_view_ids: tuple[str, ...]
    schema_version: str = STRUCTURAL_MEMBER_SCHEMA_VERSION


@dataclass(frozen=True)
class StructuralMemberInstance:
    candidate_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    scope_id: str
    definition_id: str
    page_id: str
    view_id: str
    view_kind: str
    source_evidence_ids: tuple[str, ...]
    source_role: str
    member_tag: Optional[str] = None
    grid_location: Optional[str] = None
    has_closed_geometry: bool = False
    has_structural_symbol: bool = False
    bound_callout_definition_id: Optional[str] = None
    bbox: Optional[tuple[float, float, float, float]] = None
    schema_version: str = STRUCTURAL_MEMBER_SCHEMA_VERSION


@dataclass(frozen=True)
class StructuralMemberIdentityRelation:
    left_candidate_id: str
    right_candidate_id: str
    classification: StructuralMemberIdentityClass
    source_evidence_ids: tuple[str, ...]
    schema_version: str = STRUCTURAL_MEMBER_SCHEMA_VERSION


@dataclass(frozen=True)
class StructuralMemberCompleteness:
    scope_id: str
    definition_id: str
    instance_bearing_view_ids: tuple[str, ...]
    complete_view_ids: tuple[str, ...]
    cropped_view_ids: tuple[str, ...] = ()
    unresolved_continuation_view_ids: tuple[str, ...] = ()
    missing_bay_view_ids: tuple[str, ...] = ()
    cross_view_registration_complete: bool = False
    source_evidence_ids: tuple[str, ...] = ()
    schema_version: str = STRUCTURAL_MEMBER_SCHEMA_VERSION


@dataclass(frozen=True)
class StructuralMemberSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    scope_id: str
    definition_id: str


@dataclass(frozen=True)
class StructuralMemberQuantityResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    definition_id: str
    scope_id: str
    quantity: Optional[int]
    physical_member_ids: tuple[str, ...]
    member_candidate_groups: tuple[tuple[str, ...], ...]
    source_evidence_ids: tuple[str, ...]
    source_page_ids: tuple[str, ...]
    source_view_ids: tuple[str, ...]
    schema_version: str = STRUCTURAL_MEMBER_SCHEMA_VERSION


def _clean_tuple(values: Sequence[object]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value).strip() for value in values if str(value).strip()))


def _blocked(
    selector: StructuralMemberSelector,
    status: EvidenceResolutionStatus,
    *reasons: str,
) -> StructuralMemberQuantityResult:
    if status is EvidenceResolutionStatus.CORROBORATED:
        status = EvidenceResolutionStatus.ABSTAINED
    clean = _clean_tuple(reasons)
    return StructuralMemberQuantityResult(
        status=status,
        reason_codes=clean or (STRUCTURAL_MEMBER_COMPLETENESS_UNAVAILABLE,),
        definition_id=selector.definition_id,
        scope_id=selector.scope_id,
        quantity=None,
        physical_member_ids=(),
        member_candidate_groups=(),
        source_evidence_ids=(),
        source_page_ids=(),
        source_view_ids=(),
    )


def _instance_has_positive_evidence(instance: StructuralMemberInstance) -> bool:
    role = str(instance.source_role or "").strip().lower()
    if role in {"wall_end", "opening_jamb", "wall_jamb", "door_jamb", "window_jamb"}:
        return False
    if not instance.source_evidence_ids:
        return False

    tag = bool(str(instance.member_tag or "").strip())
    grid = bool(str(instance.grid_location or "").strip())
    callout = (
        str(instance.bound_callout_definition_id or "").strip()
        == str(instance.definition_id).strip()
    )

    return bool(
        (instance.has_closed_geometry and (tag or callout))
        or (instance.has_structural_symbol and (tag or grid or callout))
        or (tag and grid)
    )


class StructuralMemberProducer:
    """Trusted writer scoped to one immutable source snapshot."""

    def __init__(
        self,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("use StructuralMemberProducer.for_source_snapshot()")
        for name, value in (
            ("document_id", document_id),
            ("revision_id", revision_id),
            ("source_sha256", source_sha256),
            ("snapshot_id", snapshot_id),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{name} must be non-empty")
        self.document_id = str(document_id)
        self.revision_id = str(revision_id)
        self.source_sha256 = str(source_sha256)
        self.snapshot_id = str(snapshot_id)
        self._definitions: dict[str, StructuralMemberDefinition] = {}
        self._instances: dict[str, StructuralMemberInstance] = {}
        self._relations: list[StructuralMemberIdentityRelation] = []
        self._completeness: dict[tuple[str, str], StructuralMemberCompleteness] = {}
        self._rejected_instance_evidence_ids: set[str] = set()

    @classmethod
    def for_source_snapshot(
        cls,
        *,
        document_id: str,
        revision_id: str,
        source_sha256: str,
        snapshot_id: str,
    ) -> "StructuralMemberProducer":
        return cls(
            document_id=document_id,
            revision_id=revision_id,
            source_sha256=source_sha256,
            snapshot_id=snapshot_id,
            _seal=_PRODUCER_SEAL,
        )

    def publish_definition(
        self,
        *,
        member_kind: str,
        section_text: str,
        source_evidence_ids: Sequence[str],
        source_page_ids: Sequence[str] = (),
        source_view_ids: Sequence[str] = (),
    ) -> StructuralMemberDefinition:
        kind = str(member_kind or "").strip().lower()
        section = " ".join(str(section_text or "").split())
        evidence = _clean_tuple(source_evidence_ids)
        if not kind or not evidence:
            raise ValueError("member_kind and source_evidence_ids are required")
        payload = {
            "lineage": (
                self.document_id,
                self.revision_id,
                self.source_sha256,
                self.snapshot_id,
            ),
            "member_kind": kind,
            "section_text": section,
            "source_evidence_ids": evidence,
            "source_page_ids": _clean_tuple(source_page_ids),
            "source_view_ids": _clean_tuple(source_view_ids),
        }
        definition_id = stable_contract_id(
            "structural_member_definition_v1", payload, digest_chars=32
        )
        record = StructuralMemberDefinition(
            definition_id=definition_id,
            document_id=self.document_id,
            revision_id=self.revision_id,
            source_sha256=self.source_sha256,
            snapshot_id=self.snapshot_id,
            member_kind=kind,
            section_text=section,
            source_evidence_ids=evidence,
            source_page_ids=_clean_tuple(source_page_ids),
            source_view_ids=_clean_tuple(source_view_ids),
        )
        existing = self._definitions.get(definition_id)
        if existing is not None and existing != record:
            raise RuntimeError("structural member definition equivocation")
        self._definitions[definition_id] = record
        return record

    def publish_instance(
        self,
        *,
        scope_id: str,
        definition_id: str,
        page_id: str,
        view_id: str,
        view_kind: str,
        source_evidence_ids: Sequence[str],
        source_role: str = "structural_member",
        member_tag: Optional[str] = None,
        grid_location: Optional[str] = None,
        has_closed_geometry: bool = False,
        has_structural_symbol: bool = False,
        bound_callout_definition_id: Optional[str] = None,
        bbox: Optional[tuple[float, float, float, float]] = None,
    ) -> Optional[StructuralMemberInstance]:
        definition = self._definitions.get(str(definition_id))
        if definition is None:
            raise ValueError("definition_id is not producer-owned")
        for name, value in (
            ("scope_id", scope_id),
            ("page_id", page_id),
            ("view_id", view_id),
            ("view_kind", view_kind),
        ):
            if not str(value or "").strip():
                raise ValueError(f"{name} must be non-empty")

        evidence = _clean_tuple(source_evidence_ids)
        payload = {
            "lineage": (
                self.document_id,
                self.revision_id,
                self.source_sha256,
                self.snapshot_id,
            ),
            "scope_id": str(scope_id),
            "definition_id": str(definition_id),
            "page_id": str(page_id),
            "view_id": str(view_id),
            "view_kind": str(view_kind).strip().lower(),
            "source_evidence_ids": evidence,
            "source_role": str(source_role or "").strip().lower(),
            "member_tag": str(member_tag or "").strip(),
            "grid_location": str(grid_location or "").strip(),
            "has_closed_geometry": bool(has_closed_geometry),
            "has_structural_symbol": bool(has_structural_symbol),
            "bound_callout_definition_id": str(bound_callout_definition_id or "").strip(),
            "bbox": None if bbox is None else tuple(float(v) for v in bbox),
        }
        candidate_id = stable_contract_id(
            "structural_member_candidate_v1", payload, digest_chars=32
        )
        record = StructuralMemberInstance(
            candidate_id=candidate_id,
            document_id=self.document_id,
            revision_id=self.revision_id,
            source_sha256=self.source_sha256,
            snapshot_id=self.snapshot_id,
            scope_id=str(scope_id),
            definition_id=str(definition_id),
            page_id=str(page_id),
            view_id=str(view_id),
            view_kind=str(view_kind).strip().lower(),
            source_evidence_ids=evidence,
            source_role=str(source_role or "").strip().lower(),
            member_tag=(str(member_tag).strip() if member_tag is not None else None),
            grid_location=(str(grid_location).strip() if grid_location is not None else None),
            has_closed_geometry=bool(has_closed_geometry),
            has_structural_symbol=bool(has_structural_symbol),
            bound_callout_definition_id=(
                str(bound_callout_definition_id).strip()
                if bound_callout_definition_id is not None
                else None
            ),
            bbox=None if bbox is None else tuple(float(v) for v in bbox),
        )
        if not _instance_has_positive_evidence(record):
            self._rejected_instance_evidence_ids.update(evidence)
            return None

        existing = self._instances.get(candidate_id)
        if existing is not None and existing != record:
            raise RuntimeError("structural member instance equivocation")
        self._instances[candidate_id] = record
        return record

    def publish_relation(
        self,
        *,
        left_candidate_id: str,
        right_candidate_id: str,
        classification: StructuralMemberIdentityClass,
        source_evidence_ids: Sequence[str],
    ) -> StructuralMemberIdentityRelation:
        if not isinstance(classification, StructuralMemberIdentityClass):
            raise TypeError("classification must be StructuralMemberIdentityClass")
        left_id = str(left_candidate_id)
        right_id = str(right_candidate_id)
        if left_id == right_id:
            raise ValueError("identity relation requires two candidate ids")
        if left_id not in self._instances or right_id not in self._instances:
            raise ValueError("identity relation candidates must be producer-owned")
        evidence = _clean_tuple(source_evidence_ids)
        if not evidence:
            raise ValueError("identity relation requires positive source evidence")
        ordered = sorted((left_id, right_id))
        relation = StructuralMemberIdentityRelation(
            left_candidate_id=ordered[0],
            right_candidate_id=ordered[1],
            classification=classification,
            source_evidence_ids=evidence,
        )
        self._relations.append(relation)
        return relation

    def publish_completeness(
        self,
        *,
        scope_id: str,
        definition_id: str,
        instance_bearing_view_ids: Sequence[str],
        complete_view_ids: Sequence[str],
        cropped_view_ids: Sequence[str] = (),
        unresolved_continuation_view_ids: Sequence[str] = (),
        missing_bay_view_ids: Sequence[str] = (),
        cross_view_registration_complete: bool = False,
        source_evidence_ids: Sequence[str] = (),
    ) -> StructuralMemberCompleteness:
        scope = str(scope_id or "").strip()
        definition_key = str(definition_id or "").strip()
        views = _clean_tuple(instance_bearing_view_ids)
        evidence = _clean_tuple(source_evidence_ids)
        if definition_key not in self._definitions:
            raise ValueError("definition_id is not producer-owned")
        if not scope or not views or not evidence:
            raise ValueError(
                "scope_id, instance_bearing_view_ids, and source_evidence_ids are required"
            )
        record = StructuralMemberCompleteness(
            scope_id=scope,
            definition_id=definition_key,
            instance_bearing_view_ids=views,
            complete_view_ids=_clean_tuple(complete_view_ids),
            cropped_view_ids=_clean_tuple(cropped_view_ids),
            unresolved_continuation_view_ids=_clean_tuple(
                unresolved_continuation_view_ids
            ),
            missing_bay_view_ids=_clean_tuple(missing_bay_view_ids),
            cross_view_registration_complete=bool(cross_view_registration_complete),
            source_evidence_ids=evidence,
        )
        key = (scope, definition_key)
        existing = self._completeness.get(key)
        if existing is not None and existing != record:
            raise RuntimeError("structural member completeness equivocation")
        self._completeness[key] = record
        return record

    def authority(self) -> "StructuralMemberAuthority":
        return StructuralMemberAuthority(
            definitions=MappingProxyType(dict(self._definitions)),
            instances=MappingProxyType(dict(self._instances)),
            relations=tuple(self._relations),
            completeness=MappingProxyType(dict(self._completeness)),
            rejected_instance_evidence_ids=tuple(
                sorted(self._rejected_instance_evidence_ids)
            ),
            _seal=_AUTHORITY_SEAL,
        )


class StructuralMemberAuthority:
    def __init__(
        self,
        *,
        definitions: Mapping[str, StructuralMemberDefinition],
        instances: Mapping[str, StructuralMemberInstance],
        relations: tuple[StructuralMemberIdentityRelation, ...],
        completeness: Mapping[str, StructuralMemberCompleteness],
        rejected_instance_evidence_ids: tuple[str, ...],
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("StructuralMemberAuthority is producer-sealed")
        self._definitions = definitions
        self._instances = instances
        self._relations = relations
        self._completeness = completeness
        self.rejected_instance_evidence_ids = rejected_instance_evidence_ids

    def resolve(
        self, selector: StructuralMemberSelector
    ) -> StructuralMemberQuantityResult:
        if not isinstance(selector, StructuralMemberSelector):
            raise TypeError("selector must be StructuralMemberSelector")

        definition = self._definitions.get(selector.definition_id)
        if definition is None:
            return _blocked(
                selector,
                EvidenceResolutionStatus.ABSTAINED,
                STRUCTURAL_MEMBER_DEFINITION_UNAVAILABLE,
            )
        lineage = (
            selector.document_id,
            selector.revision_id,
            selector.source_sha256,
            selector.snapshot_id,
        )
        definition_lineage = (
            definition.document_id,
            definition.revision_id,
            definition.source_sha256,
            definition.snapshot_id,
        )
        if lineage != definition_lineage:
            return _blocked(
                selector,
                EvidenceResolutionStatus.ABSTAINED,
                STRUCTURAL_MEMBER_DEFINITION_UNAVAILABLE,
            )

        completeness = self._completeness.get(
            (selector.scope_id, selector.definition_id)
        )
        if completeness is None:
            return _blocked(
                selector,
                EvidenceResolutionStatus.ABSTAINED,
                STRUCTURAL_MEMBER_COMPLETENESS_UNAVAILABLE,
            )
        expected_views = set(completeness.instance_bearing_view_ids)
        complete_views = set(completeness.complete_view_ids)
        if completeness.cropped_view_ids:
            return _blocked(
                selector,
                EvidenceResolutionStatus.ABSTAINED,
                STRUCTURAL_MEMBER_SCOPE_CROPPED,
            )
        if completeness.unresolved_continuation_view_ids:
            return _blocked(
                selector,
                EvidenceResolutionStatus.ABSTAINED,
                STRUCTURAL_MEMBER_CONTINUATION_UNRESOLVED,
            )
        if completeness.missing_bay_view_ids:
            return _blocked(
                selector,
                EvidenceResolutionStatus.ABSTAINED,
                STRUCTURAL_MEMBER_BAYS_INCOMPLETE,
            )
        if not expected_views.issubset(complete_views):
            return _blocked(
                selector,
                EvidenceResolutionStatus.ABSTAINED,
                STRUCTURAL_MEMBER_COMPLETENESS_UNAVAILABLE,
            )
        if len(expected_views) > 1 and not completeness.cross_view_registration_complete:
            return _blocked(
                selector,
                EvidenceResolutionStatus.ABSTAINED,
                STRUCTURAL_MEMBER_CROSS_VIEW_REGISTRATION_AMBIGUOUS,
            )

        candidates = tuple(
            record
            for record in self._instances.values()
            if record.scope_id == selector.scope_id
            and record.definition_id == selector.definition_id
            and (
                record.document_id,
                record.revision_id,
                record.source_sha256,
                record.snapshot_id,
            )
            == lineage
        )
        if not candidates:
            return _blocked(
                selector,
                EvidenceResolutionStatus.ABSTAINED,
                STRUCTURAL_MEMBER_INSTANCE_UNAVAILABLE,
            )
        candidate_by_id = {record.candidate_id: record for record in candidates}
        if any(record.view_id not in expected_views for record in candidates):
            return _blocked(
                selector,
                EvidenceResolutionStatus.CONFLICT,
                STRUCTURAL_MEMBER_VIEW_COUNT_CONFLICT,
            )

        pair_classes: dict[
            tuple[str, str], set[StructuralMemberIdentityClass]
        ] = {}
        relation_evidence: set[str] = set()
        for relation in self._relations:
            if (
                relation.left_candidate_id not in candidate_by_id
                or relation.right_candidate_id not in candidate_by_id
            ):
                continue
            pair = tuple(
                sorted((relation.left_candidate_id, relation.right_candidate_id))
            )
            pair_classes.setdefault(pair, set()).add(relation.classification)
            relation_evidence.update(relation.source_evidence_ids)

        if any(len(values) > 1 for values in pair_classes.values()):
            return _blocked(
                selector,
                EvidenceResolutionStatus.CONFLICT,
                STRUCTURAL_MEMBER_IDENTITY_CONFLICT,
            )

        parent = {candidate_id: candidate_id for candidate_id in candidate_by_id}

        def find(value: str) -> str:
            while parent[value] != value:
                parent[value] = parent[parent[value]]
                value = parent[value]
            return value

        def union(left: str, right: str) -> None:
            left_root = find(left)
            right_root = find(right)
            if left_root != right_root:
                if left_root < right_root:
                    parent[right_root] = left_root
                else:
                    parent[left_root] = right_root

        for pair, values in pair_classes.items():
            classification = next(iter(values))
            if classification is StructuralMemberIdentityClass.SAME_PHYSICAL_MEMBER:
                union(pair[0], pair[1])

        for pair, values in pair_classes.items():
            classification = next(iter(values))
            if (
                classification is StructuralMemberIdentityClass.DISTINCT_PHYSICAL_MEMBERS
                and find(pair[0]) == find(pair[1])
            ):
                return _blocked(
                    selector,
                    EvidenceResolutionStatus.CONFLICT,
                    STRUCTURAL_MEMBER_IDENTITY_CONFLICT,
                )
            if (
                classification is StructuralMemberIdentityClass.AMBIGUOUS
                and find(pair[0]) != find(pair[1])
            ):
                return _blocked(
                    selector,
                    EvidenceResolutionStatus.ABSTAINED,
                    STRUCTURAL_MEMBER_IDENTITY_AMBIGUOUS,
                )

        grouped: dict[str, list[StructuralMemberInstance]] = {}
        for candidate in candidates:
            grouped.setdefault(find(candidate.candidate_id), []).append(candidate)

        ordered_groups = tuple(
            tuple(sorted(record.candidate_id for record in records))
            for _root, records in sorted(grouped.items())
        )

        if len(expected_views) > 1:
            for group_ids in ordered_groups:
                group_views = {
                    candidate_by_id[candidate_id].view_id
                    for candidate_id in group_ids
                }
                if group_views != expected_views:
                    return _blocked(
                        selector,
                        EvidenceResolutionStatus.CONFLICT,
                        STRUCTURAL_MEMBER_VIEW_COUNT_CONFLICT,
                    )

        physical_member_ids = tuple(
            stable_contract_id(
                "physical_structural_member_v1",
                {
                    "definition_id": selector.definition_id,
                    "scope_id": selector.scope_id,
                    "candidate_ids": group_ids,
                },
                digest_chars=32,
            )
            for group_ids in ordered_groups
        )
        source_evidence = set(definition.source_evidence_ids)
        source_evidence.update(completeness.source_evidence_ids)
        source_evidence.update(relation_evidence)
        source_pages: set[str] = set(definition.source_page_ids)
        source_views: set[str] = set(definition.source_view_ids)
        for candidate in candidates:
            source_evidence.update(candidate.source_evidence_ids)
            source_pages.add(candidate.page_id)
            source_views.add(candidate.view_id)

        return StructuralMemberQuantityResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(STRUCTURAL_MEMBER_RESOLVED,),
            definition_id=selector.definition_id,
            scope_id=selector.scope_id,
            quantity=len(physical_member_ids),
            physical_member_ids=physical_member_ids,
            member_candidate_groups=ordered_groups,
            source_evidence_ids=tuple(sorted(source_evidence)),
            source_page_ids=tuple(sorted(source_pages)),
            source_view_ids=tuple(sorted(source_views)),
        )


__all__ = [
    "STRUCTURAL_MEMBER_BAYS_INCOMPLETE",
    "STRUCTURAL_MEMBER_COMPLETENESS_UNAVAILABLE",
    "STRUCTURAL_MEMBER_CONTINUATION_UNRESOLVED",
    "STRUCTURAL_MEMBER_CROSS_VIEW_REGISTRATION_AMBIGUOUS",
    "STRUCTURAL_MEMBER_DEFINITION_UNAVAILABLE",
    "STRUCTURAL_MEMBER_IDENTITY_AMBIGUOUS",
    "STRUCTURAL_MEMBER_IDENTITY_CONFLICT",
    "STRUCTURAL_MEMBER_INSTANCE_EVIDENCE_INSUFFICIENT",
    "STRUCTURAL_MEMBER_INSTANCE_UNAVAILABLE",
    "STRUCTURAL_MEMBER_RESOLVED",
    "STRUCTURAL_MEMBER_SCOPE_CROPPED",
    "STRUCTURAL_MEMBER_SCHEMA_VERSION",
    "STRUCTURAL_MEMBER_VIEW_COUNT_CONFLICT",
    "StructuralMemberAuthority",
    "StructuralMemberCompleteness",
    "StructuralMemberDefinition",
    "StructuralMemberIdentityClass",
    "StructuralMemberIdentityRelation",
    "StructuralMemberInstance",
    "StructuralMemberProducer",
    "StructuralMemberQuantityResult",
    "StructuralMemberSelector",
]
