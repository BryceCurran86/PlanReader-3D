"""Shadow: how the ink on and across a wall face is painted, relative to the wall's own face lines (S2b).

Perception nominates. Geometry relates. This module does not publish quantities, decide roles or release a veto.

It joins two source-owned inputs: the physical-opening authority's face ink inventory (every jamb-bounded structure among
the named members, survivor or set aside, with each face-collinear line located as ``opening_local`` or as running on past
one or both jambs, and the lines between the faces) and the producer's authenticated native paint facts. For every line
it reports exact relations to the structure's own face lines and to any nominated strip ink: same style, same drawing
path, where in the PDF's paint order it falls and how far, whether it is an unstroked fill boundary, whether its stroke
is transparent. There are no thresholds and no role. A line whose paint facts are not available is reported as such, not
guessed. Every competing structure and every shared support line is kept, so a consumer can see everything that stands
between a gap and an opening-local reading. Atoms are CANDIDATE with unknown polarity; nothing here is evidence FOR or
AGAINST an opening, and ``Shadow`` receipts grant nothing.

Reuses ``EvidenceAtom`` / ``EvidenceResolutionStatus`` / ``stable_contract_id``. No consumer exists.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Optional, Sequence

from pb_migration_contracts import EvidenceAtom, EvidenceResolutionStatus, stable_contract_id

FACE_INK_PAINT_RELATION_SCHEMA_VERSION = "face_ink_paint_relation_shadow.v1"
FACE_INK_ROLE_UNRESOLVED = "face_collinear_ink_role_unresolved"
PAINT_FACT_UNAVAILABLE = "face_ink_paint_fact_unavailable"
PAINT_FACT_INTEGRITY_FAILURE = "face_ink_paint_fact_integrity_failure"
INVENTORY_NOT_AVAILABLE = "face_ink_inventory_not_available"

STANDING_LIMITS = (
    "relations_are_exact_paint_measures_not_roles",
    "no_threshold_decides_whether_two_lines_belong_to_one_drawing_block",
    "an_unavailable_paint_fact_is_reported_not_guessed",
    "competing_structures_and_shared_support_are_retained_never_ranked",
    "paint_order_distance_is_the_pdfs_own_sequence_number_difference",
    "no_polarity_is_assigned_so_the_evidence_neither_supports_nor_opposes_an_opening",
)


def _style(fact: Any) -> tuple:
    return (fact.kind, fact.stroke_color, fact.stroke_width, fact.stroke_opacity, fact.dashes, fact.layer)


def _is_parallel(fact: Any, direction: Sequence[float]) -> bool:
    x1, y1, x2, y2 = fact.geometry
    length = math.hypot(x2 - x1, y2 - y1)
    if length <= 0.0:
        return False
    return abs(((x2 - x1) * direction[1] - (y2 - y1) * direction[0]) / length) <= 1e-6


@dataclass(frozen=True)
class FaceInkPaintRelation:
    """Exact paint relations of one line to one structure; ``None`` where a fact was not available."""

    relation_id: str
    structure_id: str
    structure_status: str
    observation_id: str
    kind: str                                   # face_ink | interior_ink
    extent_class: Optional[str]
    locality: Optional[str]
    paint_fact_available: bool
    stroke_color: Optional[tuple]
    stroke_width: Optional[float]
    stroke_opacity: Optional[float]
    sequence_number: Optional[int]
    path_index: Optional[int]
    unstroked_fill_boundary: Optional[bool]
    stroke_is_transparent: Optional[bool]
    stroke_is_partially_transparent: Optional[bool]
    same_style_as_face_member_ids: tuple
    same_path_as_member_ids: tuple
    paint_order_among_face_members: Optional[str]     # before_all | after_all | among
    nearest_face_member_sequence_distance: Optional[int]
    nearest_strip_ink_sequence_distance: Optional[int]
    in_strip_ink: bool
    reason_codes: tuple


@dataclass(frozen=True)
class FaceInkPaintRelationShadow:
    """Receipt: relations for every line of every structure, nothing granted, nothing decided."""

    schema_version: str
    status: EvidenceResolutionStatus
    reason_codes: tuple
    document_id: Optional[str]
    page_id: Optional[str]
    structure_ids: tuple
    shared_support_ids: tuple
    relations: tuple
    unresolved_observation_ids: tuple
    standing_limits: tuple = STANDING_LIMITS
    decides_existence: bool = False
    decides_role: bool = False
    releases_veto: bool = False
    grants_quantity: bool = False
    grants_firm_authority: bool = False
    publishes_atoms_to_live_path: bool = False

    def __post_init__(self) -> None:
        if (self.decides_existence or self.decides_role or self.releases_veto or self.grants_quantity
                or self.grants_firm_authority or self.publishes_atoms_to_live_path):
            raise ValueError("a face ink paint relation shadow decides nothing and grants nothing")

    def to_atoms(self) -> tuple:
        """One CANDIDATE atom with unknown polarity per relation. They support and oppose nothing."""
        from pb_wall_room_topology_typed_negative_evidence import KIND_UNKNOWN, POLARITY_UNKNOWN

        atoms = []
        for relation in self.relations:
            metadata = {name: getattr(relation, name) for name in relation.__dataclass_fields__}
            metadata["polarity"] = POLARITY_UNKNOWN
            atoms.append(EvidenceAtom(
                evidence_id=stable_contract_id("face_ink_paint_relation", metadata, digest_chars=32),
                document_id=str(self.document_id or "unknown"), page_id=str(self.page_id or "unknown"),
                kind=KIND_UNKNOWN, method="face_ink_paint_relation_shadow",
                status=EvidenceResolutionStatus.CANDIDATE, reason_codes=(FACE_INK_ROLE_UNRESOLVED,),
                metadata=metadata))
        return tuple(atoms)


def relate_face_ink_to_paint(
    inventory: Any,
    paint_facts: Sequence[Any],
    *,
    strip_ink_ids: Sequence[str] = (),
    document_id: Optional[str] = None,
) -> FaceInkPaintRelationShadow:
    """Pure join of a face ink inventory with authenticated paint facts (duck-typed on their attributes)."""
    structures = tuple(getattr(inventory, "structures", ()) or ())
    if not structures:
        return FaceInkPaintRelationShadow(
            schema_version=FACE_INK_PAINT_RELATION_SCHEMA_VERSION, status=EvidenceResolutionStatus.ABSTAINED,
            reason_codes=(INVENTORY_NOT_AVAILABLE,), document_id=document_id,
            page_id=getattr(inventory, "page_id", None), structure_ids=(), shared_support_ids=(), relations=(),
            unresolved_observation_ids=())
    facts = {fact.observation_id: fact for fact in paint_facts}
    strip = tuple(sorted(set(map(str, strip_ink_ids))))
    strip_sequences = sorted(facts[i].sequence_number for i in strip if i in facts)
    relations = []
    unresolved = set()
    for structure in sorted(structures, key=lambda s: s.candidate_id):
        face_members = tuple(sorted(
            i for i in structure.member_ids
            if i in facts and _is_parallel(facts[i], structure.direction)))
        member_sequences = sorted(facts[i].sequence_number for i in face_members)
        lines = [("face_ink", ink.observation_id, ink.extent_class, ink.locality) for ink in structure.face_ink]
        lines += [("interior_ink", oid, None, None) for oid in structure.interior_ink_ids]
        for kind, observation_id, extent_class, locality in sorted(lines, key=lambda row: (row[0], row[1])):
            fact = facts.get(observation_id)
            if fact is None:
                unresolved.add(observation_id)
                payload = dict(
                    structure_id=structure.candidate_id, structure_status=structure.status, observation_id=observation_id,
                    kind=kind, extent_class=extent_class, locality=locality, paint_fact_available=False)
                relations.append(FaceInkPaintRelation(
                    relation_id=stable_contract_id("face_ink_paint_relation_row", payload, digest_chars=32),
                    structure_id=structure.candidate_id, structure_status=structure.status,
                    observation_id=observation_id, kind=kind, extent_class=extent_class, locality=locality,
                    paint_fact_available=False, stroke_color=None, stroke_width=None, stroke_opacity=None,
                    sequence_number=None, path_index=None, unstroked_fill_boundary=None, stroke_is_transparent=None,
                    stroke_is_partially_transparent=None, same_style_as_face_member_ids=(), same_path_as_member_ids=(),
                    paint_order_among_face_members=None, nearest_face_member_sequence_distance=None,
                    nearest_strip_ink_sequence_distance=None, in_strip_ink=observation_id in strip,
                    reason_codes=(PAINT_FACT_UNAVAILABLE,)))
                continue
            sequence = fact.sequence_number
            same_style = tuple(i for i in face_members if i != observation_id and _style(facts[i]) == _style(fact))
            same_path = tuple(i for i in face_members if i != observation_id and facts[i].path_index == fact.path_index)
            order = (None if not member_sequences else
                     "before_all" if sequence < member_sequences[0] else
                     "after_all" if sequence > member_sequences[-1] else "among")
            nearest_member = (None if not member_sequences else min(abs(sequence - s) for s in member_sequences))
            nearest_strip = (None if not strip_sequences else min(abs(sequence - s) for s in strip_sequences))
            payload = dict(
                structure_id=structure.candidate_id, observation_id=observation_id, kind=kind, sequence=sequence,
                style=_style(fact), same_style=same_style, same_path=same_path, order=order,
                nearest_member=nearest_member, nearest_strip=nearest_strip)
            relations.append(FaceInkPaintRelation(
                relation_id=stable_contract_id("face_ink_paint_relation_row", payload, digest_chars=32),
                structure_id=structure.candidate_id, structure_status=structure.status, observation_id=observation_id,
                kind=kind, extent_class=extent_class, locality=locality, paint_fact_available=True,
                stroke_color=fact.stroke_color, stroke_width=fact.stroke_width, stroke_opacity=fact.stroke_opacity,
                sequence_number=sequence, path_index=fact.path_index,
                unstroked_fill_boundary=fact.stroke_color is None and fact.fill is not None,
                stroke_is_transparent=fact.stroke_is_transparent,
                stroke_is_partially_transparent=fact.stroke_is_partially_transparent,
                same_style_as_face_member_ids=same_style, same_path_as_member_ids=same_path,
                paint_order_among_face_members=order, nearest_face_member_sequence_distance=nearest_member,
                nearest_strip_ink_sequence_distance=nearest_strip, in_strip_ink=observation_id in strip,
                reason_codes=()))
    shared = tuple(sorted({i for s in structures for i in s.shared_member_ids}))
    return FaceInkPaintRelationShadow(
        schema_version=FACE_INK_PAINT_RELATION_SCHEMA_VERSION,
        status=EvidenceResolutionStatus.CANDIDATE if not unresolved else EvidenceResolutionStatus.ABSTAINED,
        reason_codes=(FACE_INK_ROLE_UNRESOLVED,) + ((PAINT_FACT_UNAVAILABLE,) if unresolved else ()),
        document_id=document_id, page_id=getattr(inventory, "page_id", None),
        structure_ids=tuple(sorted(s.candidate_id for s in structures)), shared_support_ids=shared,
        relations=tuple(relations), unresolved_observation_ids=tuple(sorted(unresolved)))


class FaceInkPaintRelationAudit:
    """Adapter: the real authority and producer behind the pure join. Default off, read-only, unwired."""

    def __init__(self, physical_authority: Any, producer: Any, *, enabled: bool = False) -> None:
        self._physical = physical_authority
        self._producer = producer
        self._enabled = bool(enabled)

    def audit(self, selector: Any, member_observation_ids: Sequence[str], *,
              strip_ink_ids: Sequence[str] = ()) -> FaceInkPaintRelationShadow:
        if not self._enabled:
            return FaceInkPaintRelationShadow(
                schema_version=FACE_INK_PAINT_RELATION_SCHEMA_VERSION, status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=("face_ink_paint_relation_shadow_disabled",), document_id=None, page_id=None,
                structure_ids=(), shared_support_ids=(), relations=(), unresolved_observation_ids=())
        inventory = self._physical.seeded_face_ink_inventory(selector, member_observation_ids)
        needed = set(map(str, member_observation_ids)) | set(map(str, strip_ink_ids))
        for structure in inventory.structures:
            needed |= {ink.observation_id for ink in structure.face_ink}
            needed |= set(structure.interior_ink_ids)
        needed.add(str(selector.observation_id))
        try:
            facts = self._producer.native_paint_facts(selector, observation_ids=tuple(sorted(needed)))
        except RuntimeError:
            return FaceInkPaintRelationShadow(
                schema_version=FACE_INK_PAINT_RELATION_SCHEMA_VERSION, status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(PAINT_FACT_INTEGRITY_FAILURE,), document_id=selector.document_id,
                page_id=getattr(inventory, "page_id", None), structure_ids=(), shared_support_ids=(), relations=(),
                unresolved_observation_ids=())
        return relate_face_ink_to_paint(
            inventory, facts, strip_ink_ids=strip_ink_ids, document_id=selector.document_id)


__all__ = [
    "FACE_INK_PAINT_RELATION_SCHEMA_VERSION",
    "FACE_INK_ROLE_UNRESOLVED",
    "FaceInkPaintRelation",
    "FaceInkPaintRelationAudit",
    "FaceInkPaintRelationShadow",
    "PAINT_FACT_INTEGRITY_FAILURE",
    "PAINT_FACT_UNAVAILABLE",
    "STANDING_LIMITS",
    "relate_face_ink_to_paint",
]
