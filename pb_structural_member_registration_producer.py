"""Generic source-owned cross-view structural-member registration producer.

This layer does not count members itself. It converts authenticated structural
candidate evidence plus positive registration proofs into the observation,
relation and view-scope contracts consumed by StructuralMemberAuthority.

Count equality, list order, nearest-neighbour distance and same-size geometry are
never identity evidence here.
"""
from __future__ import annotations

from dataclasses import dataclass
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

STRUCTURAL_MEMBER_REGISTRATION_SCHEMA_VERSION = "1.0.0"

_ALLOWED_ROLE_EVIDENCE_KINDS = frozenset(
    {
        "explicit_member_mark",
        "registered_structural_symbol",
        "structural_symbol_with_host",
        "registered_grid_intersection",
        "source_defined_projection",
    }
)

_IDENTITY_ANCHOR_KINDS = frozenset(
    {
        "member_mark",
        "grid_intersection",
        "registered_coordinate",
        "source_projection",
    }
)

_SAME_PROOF_KINDS = frozenset(
    {
        "same_source_primitive",
        "explicit_member_mark",
        "registered_grid_intersection",
        "registered_coordinate",
        "source_projection",
    }
)

_DISTINCT_PROOF_KINDS = frozenset(
    {
        "distinct_member_marks",
        "distinct_registered_grid_positions",
        "explicit_distinct_instances",
    }
)

_AMBIGUOUS_PROOF_KINDS = frozenset(
    {
        "ambiguous_registration",
        "registration_collision",
    }
)


def _nonempty(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


def _unique_nonempty(values: Sequence[str], name: str) -> tuple[str, ...]:
    rows = tuple(str(value).strip() for value in values if str(value).strip())
    if not rows:
        raise ValueError(f"{name} must be non-empty")
    if len(rows) != len(set(rows)):
        rows = tuple(dict.fromkeys(rows))
    return rows


@dataclass(frozen=True)
class StructuralMemberRegistrationAnchor:
    """Positive source registration key shared by representations of one member."""

    anchor_kind: str
    system_id: str
    key: str
    source_evidence_ids: tuple[str, ...]
    schema_version: str = STRUCTURAL_MEMBER_REGISTRATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        kind = _nonempty(self.anchor_kind, "anchor_kind").lower()
        if kind not in _IDENTITY_ANCHOR_KINDS:
            raise ValueError(
                "anchor_kind must be one of: "
                + ", ".join(sorted(_IDENTITY_ANCHOR_KINDS))
            )
        object.__setattr__(self, "anchor_kind", kind)
        object.__setattr__(self, "system_id", _nonempty(self.system_id, "system_id"))
        object.__setattr__(self, "key", _nonempty(self.key, "key"))
        object.__setattr__(
            self,
            "source_evidence_ids",
            _unique_nonempty(self.source_evidence_ids, "source_evidence_ids"),
        )

    @property
    def identity_key(self) -> tuple[str, str, str]:
        return (self.anchor_kind, self.system_id, self.key)


@dataclass(frozen=True)
class StructuralMemberCandidateEvidence:
    """One positively evidenced structural-member representation in one view."""

    candidate_id: str
    member_kind: str
    page_id: str
    view_id: str
    view_type: str
    source_evidence_ids: tuple[str, ...]
    source_primitive_ids: tuple[str, ...]
    role_evidence_kind: str
    registration_anchors: tuple[StructuralMemberRegistrationAnchor, ...] = ()
    definition_id: Optional[str] = None
    schema_version: str = STRUCTURAL_MEMBER_REGISTRATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "candidate_id", _nonempty(self.candidate_id, "candidate_id"))
        object.__setattr__(self, "member_kind", _nonempty(self.member_kind, "member_kind").lower())
        object.__setattr__(self, "page_id", _nonempty(self.page_id, "page_id"))
        object.__setattr__(self, "view_id", _nonempty(self.view_id, "view_id"))
        object.__setattr__(self, "view_type", _nonempty(self.view_type, "view_type").lower())
        object.__setattr__(
            self,
            "source_evidence_ids",
            _unique_nonempty(self.source_evidence_ids, "source_evidence_ids"),
        )
        object.__setattr__(
            self,
            "source_primitive_ids",
            _unique_nonempty(self.source_primitive_ids, "source_primitive_ids"),
        )
        object.__setattr__(
            self,
            "role_evidence_kind",
            _nonempty(self.role_evidence_kind, "role_evidence_kind").lower(),
        )
        anchors = tuple(self.registration_anchors)
        if any(type(anchor) is not StructuralMemberRegistrationAnchor for anchor in anchors):
            raise TypeError("registration_anchors must contain StructuralMemberRegistrationAnchor")
        object.__setattr__(self, "registration_anchors", anchors)
        if self.definition_id is not None:
            object.__setattr__(self, "definition_id", _nonempty(self.definition_id, "definition_id"))


@dataclass(frozen=True)
class StructuralMemberSourceView:
    """Explicit completeness statement for one source-owned drawing view."""

    page_id: str
    view_id: str
    view_type: str
    complete: bool
    source_evidence_ids: tuple[str, ...]
    reason_codes: tuple[str, ...] = ()
    schema_version: str = STRUCTURAL_MEMBER_REGISTRATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(self, "page_id", _nonempty(self.page_id, "page_id"))
        object.__setattr__(self, "view_id", _nonempty(self.view_id, "view_id"))
        object.__setattr__(self, "view_type", _nonempty(self.view_type, "view_type").lower())
        object.__setattr__(
            self,
            "source_evidence_ids",
            _unique_nonempty(self.source_evidence_ids, "source_evidence_ids"),
        )
        object.__setattr__(
            self,
            "reason_codes",
            tuple(dict.fromkeys(str(reason) for reason in self.reason_codes if str(reason))),
        )


@dataclass(frozen=True)
class StructuralMemberRegistrationProof:
    """Explicit positive relation proof supplied by a source adapter."""

    left_candidate_id: str
    right_candidate_id: str
    relation: StructuralMemberRelation
    proof_kind: str
    source_evidence_ids: tuple[str, ...]
    schema_version: str = STRUCTURAL_MEMBER_REGISTRATION_SCHEMA_VERSION

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "left_candidate_id",
            _nonempty(self.left_candidate_id, "left_candidate_id"),
        )
        object.__setattr__(
            self,
            "right_candidate_id",
            _nonempty(self.right_candidate_id, "right_candidate_id"),
        )
        if self.left_candidate_id == self.right_candidate_id:
            raise ValueError("relation proof must reference two candidates")
        if type(self.relation) is not StructuralMemberRelation:
            raise TypeError("relation must be StructuralMemberRelation")
        kind = _nonempty(self.proof_kind, "proof_kind").lower()
        allowed = {
            StructuralMemberRelation.SAME_PHYSICAL_MEMBER: _SAME_PROOF_KINDS,
            StructuralMemberRelation.DISTINCT_PHYSICAL_MEMBERS: _DISTINCT_PROOF_KINDS,
            StructuralMemberRelation.AMBIGUOUS: _AMBIGUOUS_PROOF_KINDS,
        }[self.relation]
        if kind not in allowed:
            raise ValueError(
                f"proof_kind {kind!r} is not positive evidence for {self.relation.value}"
            )
        object.__setattr__(self, "proof_kind", kind)
        object.__setattr__(
            self,
            "source_evidence_ids",
            _unique_nonempty(self.source_evidence_ids, "source_evidence_ids"),
        )


@dataclass(frozen=True)
class StructuralMemberRegistrationResult:
    resolution: StructuralMemberResolution
    observations: tuple[StructuralMemberObservation, ...]
    relations: tuple[StructuralMemberRelationEvidence, ...]
    view_scopes: tuple[StructuralMemberViewScope, ...]
    rejected_candidate_ids: tuple[str, ...]
    schema_version: str = STRUCTURAL_MEMBER_REGISTRATION_SCHEMA_VERSION


class StructuralMemberRegistrationProducer:
    """Build authority inputs without weakening StructuralMemberAuthority."""

    def __init__(
        self,
        *,
        selector: StructuralMemberSelector,
        candidates: Sequence[StructuralMemberCandidateEvidence] = (),
        views: Sequence[StructuralMemberSourceView] = (),
        relation_proofs: Sequence[StructuralMemberRegistrationProof] = (),
        definitions: Sequence[StructuralMemberDefinition] = (),
    ) -> None:
        if type(selector) is not StructuralMemberSelector:
            raise TypeError("selector must be StructuralMemberSelector")
        self._selector = selector
        self._candidates = tuple(candidates)
        self._views = tuple(views)
        self._relation_proofs = tuple(relation_proofs)
        self._definitions = tuple(definitions)

    def _eligible_candidates(
        self,
    ) -> tuple[tuple[StructuralMemberCandidateEvidence, ...], tuple[str, ...]]:
        target_kind = self._selector.member_kind.strip().lower()
        eligible: list[StructuralMemberCandidateEvidence] = []
        rejected: list[str] = []
        view_by_id = {view.view_id: view for view in self._views}

        for candidate in self._candidates:
            if type(candidate) is not StructuralMemberCandidateEvidence:
                raise TypeError("candidates must contain StructuralMemberCandidateEvidence")
            view = view_by_id.get(candidate.view_id)
            if (
                candidate.member_kind != target_kind
                or candidate.role_evidence_kind not in _ALLOWED_ROLE_EVIDENCE_KINDS
                or view is None
                or view.page_id != candidate.page_id
                or view.view_type != candidate.view_type
            ):
                rejected.append(candidate.candidate_id)
                continue
            eligible.append(candidate)

        return tuple(eligible), tuple(sorted(set(rejected)))

    def _observation_for(
        self,
        candidate: StructuralMemberCandidateEvidence,
    ) -> StructuralMemberObservation:
        payload = {
            "document_id": self._selector.document_id,
            "revision_id": self._selector.revision_id,
            "source_sha256": self._selector.source_sha256,
            "snapshot_id": self._selector.snapshot_id,
            "decision_scope_id": self._selector.decision_scope_id,
            "member_kind": candidate.member_kind,
            "page_id": candidate.page_id,
            "view_id": candidate.view_id,
            "view_type": candidate.view_type,
            "source_evidence_ids": tuple(sorted(candidate.source_evidence_ids)),
            "source_primitive_ids": tuple(sorted(candidate.source_primitive_ids)),
            "definition_id": candidate.definition_id or "",
        }
        return StructuralMemberObservation(
            observation_id=stable_contract_id(
                "structural_member_observation_v1",
                payload,
                digest_chars=32,
            ),
            member_kind=candidate.member_kind,
            page_id=candidate.page_id,
            view_id=candidate.view_id,
            view_type=candidate.view_type,
            source_evidence_ids=tuple(sorted(candidate.source_evidence_ids)),
            source_primitive_ids=tuple(sorted(candidate.source_primitive_ids)),
            definition_id=candidate.definition_id,
        )

    @staticmethod
    def _merge_relation(
        relation_map: dict[
            tuple[str, str, StructuralMemberRelation],
            set[str],
        ],
        *,
        left: str,
        right: str,
        relation: StructuralMemberRelation,
        evidence_ids: Sequence[str],
    ) -> None:
        pair = tuple(sorted((left, right)))
        if pair[0] == pair[1]:
            return
        relation_map.setdefault((pair[0], pair[1], relation), set()).update(
            str(value) for value in evidence_ids if str(value)
        )

    def publish(self) -> StructuralMemberRegistrationResult:
        eligible, rejected = self._eligible_candidates()
        by_candidate_id = {candidate.candidate_id: candidate for candidate in eligible}
        if len(by_candidate_id) != len(eligible):
            raise ValueError("candidate_id must be unique")

        observations = tuple(self._observation_for(candidate) for candidate in eligible)
        observation_by_candidate = {
            candidate.candidate_id: observation
            for candidate, observation in zip(eligible, observations)
        }

        relation_map: dict[
            tuple[str, str, StructuralMemberRelation],
            set[str],
        ] = {}

        # Automatic SAME is permitted only from an exact positive identity
        # anchor and only when that anchor identifies at most one candidate in
        # each participating view. Duplicate anchor ownership within a view is
        # ambiguous and therefore never auto-collapsed.
        anchors: dict[
            tuple[str, str, str],
            list[tuple[StructuralMemberCandidateEvidence, StructuralMemberRegistrationAnchor]],
        ] = {}
        for candidate in eligible:
            for anchor in candidate.registration_anchors:
                anchors.setdefault(anchor.identity_key, []).append((candidate, anchor))

        for rows in anchors.values():
            by_view: dict[
                str,
                list[tuple[StructuralMemberCandidateEvidence, StructuralMemberRegistrationAnchor]],
            ] = {}
            for candidate, anchor in rows:
                by_view.setdefault(candidate.view_id, []).append((candidate, anchor))
            if any(len(view_rows) != 1 for view_rows in by_view.values()):
                continue
            unique = [view_rows[0] for view_rows in by_view.values()]
            for index, (left_candidate, left_anchor) in enumerate(unique):
                for right_candidate, right_anchor in unique[index + 1 :]:
                    left = observation_by_candidate[left_candidate.candidate_id]
                    right = observation_by_candidate[right_candidate.candidate_id]
                    self._merge_relation(
                        relation_map,
                        left=left.observation_id,
                        right=right.observation_id,
                        relation=StructuralMemberRelation.SAME_PHYSICAL_MEMBER,
                        evidence_ids=(
                            *left_anchor.source_evidence_ids,
                            *right_anchor.source_evidence_ids,
                        ),
                    )

        # Explicit proofs remain available for duplicate representations,
        # positive DISTINCT evidence, and explicit ambiguity. Absence of a proof
        # never creates DISTINCT and never creates SAME.
        for proof in self._relation_proofs:
            if type(proof) is not StructuralMemberRegistrationProof:
                raise TypeError(
                    "relation_proofs must contain StructuralMemberRegistrationProof"
                )
            left = observation_by_candidate.get(proof.left_candidate_id)
            right = observation_by_candidate.get(proof.right_candidate_id)
            if left is None or right is None:
                continue
            self._merge_relation(
                relation_map,
                left=left.observation_id,
                right=right.observation_id,
                relation=proof.relation,
                evidence_ids=proof.source_evidence_ids,
            )

        relations = tuple(
            StructuralMemberRelationEvidence(
                left_observation_id=left,
                right_observation_id=right,
                relation=relation,
                source_evidence_ids=tuple(sorted(evidence)),
            )
            for (left, right, relation), evidence in sorted(
                relation_map.items(),
                key=lambda item: (
                    item[0][0],
                    item[0][1],
                    item[0][2].value,
                ),
            )
        )

        candidate_view_ids = {candidate.view_id for candidate in eligible}
        view_scopes = tuple(
            StructuralMemberViewScope(
                page_id=view.page_id,
                view_id=view.view_id,
                view_type=view.view_type,
                complete=bool(view.complete),
                reason_codes=view.reason_codes,
            )
            for view in sorted(self._views, key=lambda row: row.view_id)
            if view.view_id in candidate_view_ids
        )

        resolution = StructuralMemberProducer.from_authenticated_evidence(
            selector=self._selector,
            definitions=self._definitions,
            observations=observations,
            relations=relations,
            view_scopes=view_scopes,
        ).publish()
        return StructuralMemberRegistrationResult(
            resolution=resolution,
            observations=observations,
            relations=relations,
            view_scopes=view_scopes,
            rejected_candidate_ids=rejected,
        )


__all__ = [
    "STRUCTURAL_MEMBER_REGISTRATION_SCHEMA_VERSION",
    "StructuralMemberCandidateEvidence",
    "StructuralMemberRegistrationAnchor",
    "StructuralMemberRegistrationProof",
    "StructuralMemberRegistrationProducer",
    "StructuralMemberRegistrationResult",
    "StructuralMemberSourceView",
]
