"""Producer-owned physical-opening identity graph integrity authority.

This layer validates the complete set of semantic opening identities for one
producer-owned semantic enumeration scope. It does not discover openings and it
does not use tags, OCR text, schedule rows, proximity, expected quantities, or
caller-authored identity edges.

The graph is built only from:
- SemanticOpeningEnumerationAuthority for the complete producer-owned node set;
- PhysicalOpeningAuthority.prove_existence() for each representative node; and
- PhysicalOpeningAuthority.compare_identity() for every pair of representatives.

SAME edges are unioned transitively. DISTINCT edges are then checked against
those components. Any relation such as A SAME B, B SAME C, A DISTINCT C is a
hard conflict. Any unresolved pair abstains the whole graph.
"""
from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping, Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PHYSICAL_OPENING_IDENTITIES_DISTINCT,
    PhysicalOpeningAuthority,
)
from pb_semantic_opening_enumeration_authority import (
    SemanticOpeningEnumerationAuthority,
    SemanticOpeningEnumerationSelector,
)
from pb_source_observation_authority import ObservationSelector


OPENING_IDENTITY_GRAPH_SCHEMA_VERSION = "1.0.0"

OPENING_IDENTITY_GRAPH_RESOLVED = "opening_identity_graph_resolved"
OPENING_IDENTITY_GRAPH_UNAVAILABLE = "opening_identity_graph_unavailable"
OPENING_IDENTITY_GRAPH_ENUMERATION_UNRESOLVED = (
    "opening_identity_graph_enumeration_unresolved"
)
OPENING_IDENTITY_GRAPH_EXISTENCE_UNRESOLVED = (
    "opening_identity_graph_existence_unresolved"
)
OPENING_IDENTITY_GRAPH_PAIRWISE_UNRESOLVED = (
    "opening_identity_graph_pairwise_unresolved"
)
OPENING_IDENTITY_GRAPH_CONTRADICTION = "opening_identity_graph_contradiction"
OPENING_IDENTITY_GRAPH_LINEAGE_MISMATCH = "opening_identity_graph_lineage_mismatch"
OPENING_IDENTITY_GRAPH_MEMBER_SET_MISMATCH = (
    "opening_identity_graph_member_set_mismatch"
)
OPENING_IDENTITY_GRAPH_PRODUCER_EQUIVOCATION = (
    "opening_identity_graph_producer_equivocation"
)

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()

_Key = tuple[str, str, str, str, str]


def _clean(value: object) -> str:
    return str(value or "").strip()


def _ordered_unique(values: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


@dataclass(frozen=True)
class OpeningIdentityGraphSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "decision_scope_id",
        ):
            if not _clean(getattr(self, name)):
                raise ValueError(f"{name} must be a non-empty string")

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.decision_scope_id,
        )


@dataclass(frozen=True)
class OpeningIdentityGraphRecord:
    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    decision_scope_id: str
    physical_opening_record_ids: tuple[str, ...]
    representative_observation_ids: tuple[str, ...]
    identity_components: tuple[tuple[str, ...], ...]
    proven_distinct_pairs: tuple[tuple[str, str], ...]
    reason_codes: tuple[str, ...]
    schema_version: str = OPENING_IDENTITY_GRAPH_SCHEMA_VERSION

    def __post_init__(self) -> None:
        if not self.record_id:
            raise ValueError("record_id must be non-empty")
        if len(set(self.physical_opening_record_ids)) != len(
            self.physical_opening_record_ids
        ):
            raise ValueError("physical_opening_record_ids must be unique")
        if len(self.physical_opening_record_ids) != len(
            self.representative_observation_ids
        ):
            raise ValueError(
                "representative_observation_ids must map one-to-one to openings"
            )
        flattened = tuple(
            member for component in self.identity_components for member in component
        )
        if set(flattened) != set(self.physical_opening_record_ids):
            raise ValueError("identity components must cover the exact opening node set")
        if len(flattened) != len(set(flattened)):
            raise ValueError("identity components must be disjoint")


@dataclass(frozen=True)
class OpeningIdentityGraphResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    record: Optional[OpeningIdentityGraphRecord] = None
    schema_version: str = OPENING_IDENTITY_GRAPH_SCHEMA_VERSION


class OpeningIdentityGraphAuthority:
    def __init__(
        self,
        results: Mapping[_Key, OpeningIdentityGraphResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("OpeningIdentityGraphAuthority must be producer-owned")
        self._results = MappingProxyType(dict(results))

    def resolve(
        self,
        selector: OpeningIdentityGraphSelector,
    ) -> OpeningIdentityGraphResult:
        if type(selector) is not OpeningIdentityGraphSelector:
            raise TypeError("selector must be OpeningIdentityGraphSelector")
        return self._results.get(
            selector.key,
            OpeningIdentityGraphResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(OPENING_IDENTITY_GRAPH_UNAVAILABLE,),
                record=None,
            ),
        )


class _DisjointSet:
    def __init__(self, members: tuple[str, ...]) -> None:
        self.parent = {member: member for member in members}
        self.rank = {member: 0 for member in members}

    def find(self, member: str) -> str:
        parent = self.parent[member]
        if parent != member:
            self.parent[member] = self.find(parent)
        return self.parent[member]

    def union(self, left: str, right: str) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        left_rank = self.rank[left_root]
        right_rank = self.rank[right_root]
        if left_rank < right_rank:
            left_root, right_root = right_root, left_root
            left_rank, right_rank = right_rank, left_rank
        self.parent[right_root] = left_root
        if left_rank == right_rank:
            self.rank[left_root] += 1


def _validate_identity_relations(
    *,
    nodes: tuple[str, ...],
    same_edges: tuple[tuple[str, str], ...],
    distinct_edges: tuple[tuple[str, str], ...],
) -> tuple[
    bool,
    tuple[tuple[str, ...], ...],
    tuple[tuple[str, str], ...],
]:
    """Validate transitive SAME components against all DISTINCT edges."""

    node_set = set(nodes)
    if len(node_set) != len(nodes):
        raise ValueError("identity graph nodes must be unique")

    dsu = _DisjointSet(nodes)
    for left, right in same_edges:
        if left not in node_set or right not in node_set:
            raise ValueError("identity edge references an unknown node")
        dsu.union(left, right)

    normalized_distinct: list[tuple[str, str]] = []
    contradiction = False
    for left, right in distinct_edges:
        if left not in node_set or right not in node_set:
            raise ValueError("identity edge references an unknown node")
        pair = tuple(sorted((left, right)))
        if pair not in normalized_distinct:
            normalized_distinct.append(pair)
        if dsu.find(left) == dsu.find(right):
            contradiction = True

    grouped: dict[str, list[str]] = {}
    for node in nodes:
        grouped.setdefault(dsu.find(node), []).append(node)
    components = tuple(
        sorted(
            (tuple(sorted(members)) for members in grouped.values()),
            key=lambda members: members,
        )
    )
    return contradiction, components, tuple(sorted(normalized_distinct))


class OpeningIdentityGraphProducer:
    def __init__(
        self,
        semantic_enumeration_authority: SemanticOpeningEnumerationAuthority,
        physical_opening_authority: PhysicalOpeningAuthority,
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError(
                "OpeningIdentityGraphProducer must be obtained from from_authorities()"
            )
        if type(semantic_enumeration_authority) is not SemanticOpeningEnumerationAuthority:
            raise TypeError(
                "semantic_enumeration_authority must be producer-owned"
            )
        if type(physical_opening_authority) is not PhysicalOpeningAuthority:
            raise TypeError("physical_opening_authority must be producer-owned")
        self._semantic = semantic_enumeration_authority
        self._physical = physical_opening_authority
        self._results: dict[_Key, OpeningIdentityGraphResult] = {}

    @classmethod
    def from_authorities(
        cls,
        *,
        semantic_enumeration_authority: SemanticOpeningEnumerationAuthority,
        physical_opening_authority: PhysicalOpeningAuthority,
    ) -> "OpeningIdentityGraphProducer":
        return cls(
            semantic_enumeration_authority,
            physical_opening_authority,
            _seal=_PRODUCER_SEAL,
        )

    def authority(self) -> OpeningIdentityGraphAuthority:
        return OpeningIdentityGraphAuthority(
            self._results,
            _seal=_AUTHORITY_SEAL,
        )

    def _store(
        self,
        selector: OpeningIdentityGraphSelector,
        result: OpeningIdentityGraphResult,
    ) -> OpeningIdentityGraphResult:
        prior = self._results.get(selector.key)
        if prior is not None and prior != result:
            raise RuntimeError(OPENING_IDENTITY_GRAPH_PRODUCER_EQUIVOCATION)
        self._results[selector.key] = result
        return result

    def publish(
        self,
        selector: OpeningIdentityGraphSelector,
    ) -> OpeningIdentityGraphResult:
        if type(selector) is not OpeningIdentityGraphSelector:
            raise TypeError("selector must be OpeningIdentityGraphSelector")

        semantic = self._semantic.resolve(
            SemanticOpeningEnumerationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                decision_scope_id=selector.decision_scope_id,
            )
        )
        if semantic.record is None or semantic.status is EvidenceResolutionStatus.CONFLICT:
            return self._store(
                selector,
                OpeningIdentityGraphResult(
                    status=(
                        EvidenceResolutionStatus.CONFLICT
                        if semantic.status is EvidenceResolutionStatus.CONFLICT
                        else EvidenceResolutionStatus.ABSTAINED
                    ),
                    reason_codes=_ordered_unique(
                        [
                            OPENING_IDENTITY_GRAPH_ENUMERATION_UNRESOLVED,
                            *semantic.reason_codes,
                        ]
                    ),
                    record=None,
                ),
            )

        enum_record = semantic.record
        if (
            enum_record.document_id != selector.document_id
            or enum_record.revision_id != selector.revision_id
            or enum_record.source_sha256 != selector.source_sha256
            or enum_record.snapshot_id != selector.snapshot_id
            or enum_record.decision_scope_id != selector.decision_scope_id
        ):
            return self._store(
                selector,
                OpeningIdentityGraphResult(
                    status=EvidenceResolutionStatus.CONFLICT,
                    reason_codes=(OPENING_IDENTITY_GRAPH_LINEAGE_MISMATCH,),
                    record=None,
                ),
            )

        expected_ids = tuple(sorted(enum_record.physical_opening_record_ids))
        representative_ids = tuple(enum_record.representative_observation_ids)
        if len(expected_ids) != len(representative_ids):
            return self._store(
                selector,
                OpeningIdentityGraphResult(
                    status=EvidenceResolutionStatus.CONFLICT,
                    reason_codes=(OPENING_IDENTITY_GRAPH_MEMBER_SET_MISMATCH,),
                    record=None,
                ),
            )

        selectors_by_record: dict[str, ObservationSelector] = {}
        for observation_id in representative_ids:
            obs_selector = ObservationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                observation_id=observation_id,
            )
            existence = self._physical.prove_existence(obs_selector)
            if (
                existence.status is not EvidenceResolutionStatus.CORROBORATED
                or existence.proposition != PHYSICAL_OPENING_EXISTS
                or existence.existence_record is None
            ):
                return self._store(
                    selector,
                    OpeningIdentityGraphResult(
                        status=(
                            EvidenceResolutionStatus.CONFLICT
                            if existence.status is EvidenceResolutionStatus.CONFLICT
                            else EvidenceResolutionStatus.ABSTAINED
                        ),
                        reason_codes=_ordered_unique(
                            [
                                OPENING_IDENTITY_GRAPH_EXISTENCE_UNRESOLVED,
                                *existence.reason_codes,
                            ]
                        ),
                        record=None,
                    ),
                )
            record = existence.existence_record
            if (
                record.document_id != selector.document_id
                or record.revision_id != selector.revision_id
                or record.source_sha256 != selector.source_sha256
                or record.snapshot_id != selector.snapshot_id
            ):
                return self._store(
                    selector,
                    OpeningIdentityGraphResult(
                        status=EvidenceResolutionStatus.CONFLICT,
                        reason_codes=(OPENING_IDENTITY_GRAPH_LINEAGE_MISMATCH,),
                        record=None,
                    ),
                )
            if record.record_id in selectors_by_record:
                return self._store(
                    selector,
                    OpeningIdentityGraphResult(
                        status=EvidenceResolutionStatus.CONFLICT,
                        reason_codes=(OPENING_IDENTITY_GRAPH_MEMBER_SET_MISMATCH,),
                        record=None,
                    ),
                )
            selectors_by_record[record.record_id] = obs_selector

        if tuple(sorted(selectors_by_record)) != expected_ids:
            return self._store(
                selector,
                OpeningIdentityGraphResult(
                    status=EvidenceResolutionStatus.CONFLICT,
                    reason_codes=(OPENING_IDENTITY_GRAPH_MEMBER_SET_MISMATCH,),
                    record=None,
                ),
            )

        same_edges: list[tuple[str, str]] = []
        distinct_edges: list[tuple[str, str]] = []
        for left_index, left_id in enumerate(expected_ids):
            for right_id in expected_ids[left_index + 1 :]:
                comparison = self._physical.compare_identity(
                    selectors_by_record[left_id],
                    selectors_by_record[right_id],
                )
                if comparison.status is not EvidenceResolutionStatus.CORROBORATED:
                    return self._store(
                        selector,
                        OpeningIdentityGraphResult(
                            status=(
                                EvidenceResolutionStatus.CONFLICT
                                if comparison.status is EvidenceResolutionStatus.CONFLICT
                                else EvidenceResolutionStatus.ABSTAINED
                            ),
                            reason_codes=_ordered_unique(
                                [
                                    OPENING_IDENTITY_GRAPH_PAIRWISE_UNRESOLVED,
                                    f"{left_id}_vs_{right_id}",
                                    *comparison.reason_codes,
                                ]
                            ),
                            record=None,
                        ),
                    )
                if comparison.proven_same:
                    same_edges.append((left_id, right_id))
                elif comparison.physical_opening_identity == PHYSICAL_OPENING_IDENTITIES_DISTINCT:
                    distinct_edges.append((left_id, right_id))
                else:
                    return self._store(
                        selector,
                        OpeningIdentityGraphResult(
                            status=EvidenceResolutionStatus.ABSTAINED,
                            reason_codes=(
                                OPENING_IDENTITY_GRAPH_PAIRWISE_UNRESOLVED,
                                f"{left_id}_vs_{right_id}",
                            ),
                            record=None,
                        ),
                    )

        contradiction, components, proven_distinct = _validate_identity_relations(
            nodes=expected_ids,
            same_edges=tuple(same_edges),
            distinct_edges=tuple(distinct_edges),
        )
        # The semantic enumerator already minted one independently proven
        # physical record id per node. If pairwise identity merges two of those
        # nodes, the two upstream propositions disagree even when no explicit
        # third DISTINCT edge is needed to expose the contradiction.
        if contradiction or len(components) != len(expected_ids):
            return self._store(
                selector,
                OpeningIdentityGraphResult(
                    status=EvidenceResolutionStatus.CONFLICT,
                    reason_codes=(OPENING_IDENTITY_GRAPH_CONTRADICTION,),
                    record=None,
                ),
            )

        payload = {
            "schema_version": OPENING_IDENTITY_GRAPH_SCHEMA_VERSION,
            "document_id": selector.document_id,
            "revision_id": selector.revision_id,
            "source_sha256": selector.source_sha256,
            "snapshot_id": selector.snapshot_id,
            "decision_scope_id": selector.decision_scope_id,
            "physical_opening_record_ids": expected_ids,
            "representative_observation_ids": representative_ids,
            "identity_components": components,
            "proven_distinct_pairs": proven_distinct,
        }
        record = OpeningIdentityGraphRecord(
            record_id=stable_contract_id(
                "opening_identity_graph",
                payload,
                digest_chars=32,
            ),
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            decision_scope_id=selector.decision_scope_id,
            physical_opening_record_ids=expected_ids,
            representative_observation_ids=representative_ids,
            identity_components=components,
            proven_distinct_pairs=proven_distinct,
            reason_codes=(OPENING_IDENTITY_GRAPH_RESOLVED,),
        )
        return self._store(
            selector,
            OpeningIdentityGraphResult(
                status=EvidenceResolutionStatus.CORROBORATED,
                reason_codes=record.reason_codes,
                record=record,
            ),
        )


__all__ = [
    "OPENING_IDENTITY_GRAPH_CONTRADICTION",
    "OPENING_IDENTITY_GRAPH_ENUMERATION_UNRESOLVED",
    "OPENING_IDENTITY_GRAPH_EXISTENCE_UNRESOLVED",
    "OPENING_IDENTITY_GRAPH_LINEAGE_MISMATCH",
    "OPENING_IDENTITY_GRAPH_MEMBER_SET_MISMATCH",
    "OPENING_IDENTITY_GRAPH_PAIRWISE_UNRESOLVED",
    "OPENING_IDENTITY_GRAPH_PRODUCER_EQUIVOCATION",
    "OPENING_IDENTITY_GRAPH_RESOLVED",
    "OPENING_IDENTITY_GRAPH_SCHEMA_VERSION",
    "OPENING_IDENTITY_GRAPH_UNAVAILABLE",
    "OpeningIdentityGraphAuthority",
    "OpeningIdentityGraphProducer",
    "OpeningIdentityGraphRecord",
    "OpeningIdentityGraphResult",
    "OpeningIdentityGraphSelector",
]
