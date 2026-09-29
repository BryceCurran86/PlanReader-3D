"""Producer-owned structural-member identity and completeness authority."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Mapping, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

STRUCTURAL_MEMBER_SCHEMA_VERSION = "1.0.0"
STRUCTURAL_MEMBER_SCOPE_RESOLVED = "structural_member_scope_resolved"
STRUCTURAL_MEMBER_SCOPE_INCOMPLETE = "structural_member_scope_incomplete"
STRUCTURAL_MEMBER_RELATION_AMBIGUOUS = "structural_member_relation_ambiguous"
STRUCTURAL_MEMBER_RELATION_CONFLICT = "structural_member_relation_conflict"
STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE = "structural_member_registration_incomplete"
STRUCTURAL_MEMBER_COUNT_CONFLICT = "structural_member_count_conflict"
STRUCTURAL_MEMBER_DEFINITION_ONLY = "structural_member_definition_only"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()


class StructuralMemberRelation(str, Enum):
    SAME_PHYSICAL_MEMBER = "same_physical_member"
    DISTINCT_PHYSICAL_MEMBERS = "distinct_physical_members"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True)
class StructuralMemberDefinition:
    definition_id: str
    member_kind: str
    section_spec: str
    source_evidence_ids: tuple[str, ...]
    page_id: str
    view_id: str
    schema_version: str = STRUCTURAL_MEMBER_SCHEMA_VERSION


@dataclass(frozen=True)
class StructuralMemberObservation:
    observation_id: str
    member_kind: str
    page_id: str
    view_id: str
    view_type: str
    source_evidence_ids: tuple[str, ...]
    source_primitive_ids: tuple[str, ...] = ()
    definition_id: Optional[str] = None
    schema_version: str = STRUCTURAL_MEMBER_SCHEMA_VERSION


@dataclass(frozen=True)
class StructuralMemberRelationEvidence:
    left_observation_id: str
    right_observation_id: str
    relation: StructuralMemberRelation
    source_evidence_ids: tuple[str, ...]
    schema_version: str = STRUCTURAL_MEMBER_SCHEMA_VERSION


@dataclass(frozen=True)
class StructuralMemberViewScope:
    page_id: str
    view_id: str
    view_type: str
    complete: bool
    reason_codes: tuple[str, ...] = ()
    schema_version: str = STRUCTURAL_MEMBER_SCHEMA_VERSION


@dataclass(frozen=True)
class StructuralMemberSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    member_kind: str


@dataclass(frozen=True)
class PhysicalStructuralMember:
    physical_member_id: str
    member_kind: str
    observation_ids: tuple[str, ...]
    source_evidence_ids: tuple[str, ...]
    source_primitive_ids: tuple[str, ...]
    page_ids: tuple[str, ...]
    view_ids: tuple[str, ...]
    definition_ids: tuple[str, ...]
    schema_version: str = STRUCTURAL_MEMBER_SCHEMA_VERSION


@dataclass(frozen=True)
class StructuralMemberResolution:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    selector: StructuralMemberSelector
    members: tuple[PhysicalStructuralMember, ...]
    definitions: tuple[StructuralMemberDefinition, ...]
    unresolved_observation_ids: tuple[str, ...]
    schema_version: str = STRUCTURAL_MEMBER_SCHEMA_VERSION

    @property
    def quantity(self) -> Optional[int]:
        return len(self.members) if self.status is EvidenceResolutionStatus.CORROBORATED else None


class StructuralMemberProducer:
    def __init__(self, *, selector, definitions, observations, relations, view_scopes, _seal=None):
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("Use from_authenticated_evidence()")
        self._selector = selector
        self._definitions = tuple(definitions)
        self._observations = tuple(observations)
        self._relations = tuple(relations)
        self._view_scopes = tuple(view_scopes)
        self._result = None

    @classmethod
    def from_authenticated_evidence(cls, *, selector, definitions=(), observations=(), relations=(), view_scopes=()):
        if type(selector) is not StructuralMemberSelector:
            raise TypeError("selector must be StructuralMemberSelector")
        return cls(selector=selector, definitions=definitions, observations=observations,
                   relations=relations, view_scopes=view_scopes, _seal=_PRODUCER_SEAL)

    def _blocked(self, status, *reasons, definitions=(), unresolved=()):
        return StructuralMemberResolution(
            status=status,
            reason_codes=tuple(dict.fromkeys(str(r) for r in reasons if str(r))),
            selector=self._selector,
            members=(),
            definitions=tuple(definitions),
            unresolved_observation_ids=tuple(unresolved),
        )

    def publish(self):
        if self._result is not None:
            return self._result
        kind = self._selector.member_kind.strip().lower()
        defs = tuple(d for d in self._definitions if d.member_kind.strip().lower() == kind)
        obs = tuple(o for o in self._observations if o.member_kind.strip().lower() == kind)
        by_id = {o.observation_id: o for o in obs}
        if len(by_id) != len(obs):
            self._result = self._blocked(EvidenceResolutionStatus.CONFLICT,
                                         STRUCTURAL_MEMBER_RELATION_CONFLICT,
                                         definitions=defs)
            return self._result
        if not obs:
            self._result = self._blocked(
                EvidenceResolutionStatus.ABSTAINED,
                STRUCTURAL_MEMBER_DEFINITION_ONLY if defs else STRUCTURAL_MEMBER_SCOPE_INCOMPLETE,
                definitions=defs,
            )
            return self._result

        required_views = {o.view_id for o in obs}
        scopes = {s.view_id: s for s in self._view_scopes if s.view_id in required_views}
        if set(scopes) != required_views or any(not s.complete for s in scopes.values()):
            reasons = [STRUCTURAL_MEMBER_SCOPE_INCOMPLETE]
            for s in scopes.values():
                if not s.complete:
                    reasons.extend(s.reason_codes)
            self._result = self._blocked(EvidenceResolutionStatus.ABSTAINED, *reasons,
                                         definitions=defs, unresolved=tuple(sorted(by_id)))
            return self._result

        pair_relations = {}
        ambiguous = set()
        for r in self._relations:
            if r.left_observation_id not in by_id or r.right_observation_id not in by_id:
                continue
            if r.left_observation_id == r.right_observation_id:
                continue
            pair = tuple(sorted((r.left_observation_id, r.right_observation_id)))
            pair_relations.setdefault(pair, set()).add(r.relation)
            if r.relation is StructuralMemberRelation.AMBIGUOUS:
                ambiguous.update(pair)

        if any(len(v) > 1 for v in pair_relations.values()):
            self._result = self._blocked(EvidenceResolutionStatus.CONFLICT,
                                         STRUCTURAL_MEMBER_RELATION_CONFLICT,
                                         definitions=defs, unresolved=tuple(sorted(by_id)))
            return self._result
        if ambiguous:
            self._result = self._blocked(EvidenceResolutionStatus.ABSTAINED,
                                         STRUCTURAL_MEMBER_RELATION_AMBIGUOUS,
                                         definitions=defs, unresolved=tuple(sorted(ambiguous)))
            return self._result

        parent = {oid: oid for oid in by_id}
        def find(x):
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x
        def union(a,b):
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[max(ra,rb)] = min(ra,rb)

        distinct_pairs = []
        for pair, values in pair_relations.items():
            relation = next(iter(values))
            if relation is StructuralMemberRelation.SAME_PHYSICAL_MEMBER:
                union(*pair)
            elif relation is StructuralMemberRelation.DISTINCT_PHYSICAL_MEMBERS:
                distinct_pairs.append(pair)
        if any(find(a) == find(b) for a,b in distinct_pairs):
            self._result = self._blocked(EvidenceResolutionStatus.CONFLICT,
                                         STRUCTURAL_MEMBER_RELATION_CONFLICT,
                                         definitions=defs, unresolved=tuple(sorted(by_id)))
            return self._result

        groups = {}
        for o in obs:
            groups.setdefault(find(o.observation_id), []).append(o)

        counts_by_view = {
            view_id: sum(1 for members in groups.values() if any(m.view_id == view_id for m in members))
            for view_id in sorted(required_views)
        }
        if len(set(counts_by_view.values())) > 1:
            self._result = self._blocked(EvidenceResolutionStatus.CONFLICT,
                                         STRUCTURAL_MEMBER_COUNT_CONFLICT,
                                         definitions=defs, unresolved=tuple(sorted(by_id)))
            return self._result

        # Equal per-view counts do not prove cross-view identity. When more
        # than one complete view claims the same physical scope, every resolved
        # member must be positively registered across every complete view.
        # Otherwise plan/elevation/section duplicates would be double-counted.
        if len(required_views) > 1:
            incomplete_groups = [
                tuple(sorted(member.observation_id for member in members))
                for members in groups.values()
                if {member.view_id for member in members} != required_views
            ]
            if incomplete_groups:
                self._result = self._blocked(
                    EvidenceResolutionStatus.ABSTAINED,
                    STRUCTURAL_MEMBER_REGISTRATION_INCOMPLETE,
                    definitions=defs,
                    unresolved=tuple(sorted({
                        observation_id
                        for group in incomplete_groups
                        for observation_id in group
                    })),
                )
                return self._result

        members = []
        for grouped in sorted(groups.values(), key=lambda g: min(x.observation_id for x in g)):
            grouped = sorted(grouped, key=lambda x: x.observation_id)
            evidence = tuple(sorted({e for x in grouped for e in x.source_evidence_ids}))
            payload = {"selector": self._selector.__dict__, "kind": kind,
                       "observation_ids": [x.observation_id for x in grouped],
                       "source_evidence_ids": evidence}
            members.append(PhysicalStructuralMember(
                physical_member_id=stable_contract_id("physical_structural_member_v1", payload, digest_chars=32),
                member_kind=kind,
                observation_ids=tuple(x.observation_id for x in grouped),
                source_evidence_ids=evidence,
                source_primitive_ids=tuple(sorted({p for x in grouped for p in x.source_primitive_ids})),
                page_ids=tuple(sorted({x.page_id for x in grouped})),
                view_ids=tuple(sorted({x.view_id for x in grouped})),
                definition_ids=tuple(sorted({x.definition_id for x in grouped if x.definition_id})),
            ))

        self._result = StructuralMemberResolution(
            status=EvidenceResolutionStatus.CORROBORATED,
            reason_codes=(STRUCTURAL_MEMBER_SCOPE_RESOLVED,),
            selector=self._selector,
            members=tuple(members),
            definitions=defs,
            unresolved_observation_ids=(),
        )
        return self._result

    def authority(self):
        return StructuralMemberAuthority(MappingProxyType({self._selector: self.publish()}),
                                         _seal=_AUTHORITY_SEAL)


class StructuralMemberAuthority:
    def __init__(self, results: Mapping[StructuralMemberSelector, StructuralMemberResolution], *, _seal=None):
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("StructuralMemberAuthority is producer-sealed")
        self._results = MappingProxyType(dict(results))

    def resolve(self, selector):
        result = self._results.get(selector)
        if result is not None:
            return result
        return StructuralMemberResolution(
            status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(STRUCTURAL_MEMBER_SCOPE_INCOMPLETE,),
            selector=selector,
            members=(), definitions=(), unresolved_observation_ids=(),
        )
