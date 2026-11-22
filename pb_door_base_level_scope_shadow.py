"""Shadow base-level proof for one door: both adjoining floors are on the finished-floor-level slab.

The owner's rule (21 Nov 2026) verifies a door's base separately from its head level. A document's joinery head note is
a level ABOVE the finished floor, so the head only becomes an opening height once the base of this door is proven. Most
drawings give no per-door base. What many plan sets DO give is a level statement on a slab or level sheet ("... STEPPED
DOWN ... FROM FFL") and a mark on the plan at every area that is not on the finished-floor slab. This module turns that
into a proof, and abstains when any link of it is missing:

1. the door belongs to exactly ONE doorway closure of the room topology, and that closure bounds exactly TWO distinct
   rooms (so both sides of the door are enclosed floors, not open space or the outside);
2. the document states how level changes are annotated (a text block that pairs a level-change word with a finished-floor
   datum word), so that the ABSENCE of a mark in a room means something;
3. no level-change mark on the plan page lies inside either adjoining room;
4. every sheet that carries such a statement agrees with the plan on HOW MANY level-change marks exist (a stepped area
   the plan does not mark would make the absence meaningless);
5. every text block those steps rest on is text-integrity corroborated (raw text never verifies), and no word the
   text-integrity authority could not corroborate lies inside either adjoining room (it could hide a level note).

It is a candidate proof for the authority-promotion review, never an authority: it writes no quantity, host, kind or
frame, and every authority flag is False by construction. Nothing is chosen by proximity: a door that matches two
closures, a closure that bounds three rooms, or a mark on the boundary of a room is retained and the proof abstains.

The caller passes only the topology's CANDIDATE rings as rooms (a ring the topology itself abstained on is not a room) and
only the doorway closures of door kinds. Where the topology encloses only one side of a door (the other side leaks into open
space through an unresolved gap), the door abstains: the proof never guesses what the open side holds.

Limits kept explicit: the rule is only as complete as the drawing's own annotation (a level change that no sheet marks is
invisible to it); the word list below is policy and is tested with look-alikes; a room's holes are not known to the
caller (a mark inside a hole counts as inside the room, which can only add an abstention); one plan page per call.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from pb_door_row_evidence_compiler_shadow import (
    SOURCE_BASE_LEVEL_SCOPE,
    TEXT_CORROBORATED,
    BaseWitness,
)

BASE_LEVEL_SCOPE_SCHEMA_VERSION = "1.0.0"
BASE_LEVEL_SCOPE_STATUS = "DOOR_BASE_LEVEL_SCOPE_PROOF_SHADOW"
ABSTAINED = "ABSTAINED"

VERIFIED = "VERIFIED"
STATE_ABSTAINED = "ABSTAINED"

GATE_SCOPE_INVALID = "scope_invalid"
GATE_INPUT_INVALID = "level_scope_input_invalid"
GATE_NO_CLOSURE = "door_has_no_topology_closure"
GATE_COMPETING_CLOSURES = "door_matches_competing_closures"
GATE_NOT_TWO_ROOMS = "closure_not_bounded_by_two_distinct_rooms"
GATE_ROOM_MARKED = "room_carries_level_change_annotation"
GATE_NO_STATEMENT = "no_level_statement_in_the_document"
GATE_TEXT_RAW = "level_text_not_corroborated"
GATE_NO_PLAN_TEXT = "plan_page_text_missing"
GATE_NOT_RECONCILED = "level_change_marks_do_not_reconcile_across_sheets"

PROOF_REASON = "both_adjoining_floors_are_on_the_finished_floor_slab"
NEXT_STEP = "authority_promotion_review_then_existing_issuer"

# Policy vocabulary (tested with look-alikes). A level-change word is matched as a whole token after dropping any
# non-letters, so "STEP," matches and "STEPHEN" or "FOOTSTEP" do not. It is deliberately broad: a false match only adds
# an abstention, a missed word could miss a real level change.
LEVEL_CHANGE_WORD = re.compile(
    r"^(?:STEP|STEPS|STEPPED|STEPPING|RAMP|RAMPS|RAMPED|SUNK|SUNKEN|DEPRESSED|RAISED|STAIR|STAIRS|STAIRCASE)$"
)
# A statement defines how level changes are annotated, so it pairs a STEP-LIKE word (not a stair: "handrail to stairs 1000
# AFFL" says nothing about annotating floor level changes) with a finished-floor datum word. Stairs still count as marks.
STATEMENT_LEVEL_WORD = re.compile(
    r"^(?:STEP|STEPS|STEPPED|STEPPING|RAMP|RAMPS|RAMPED|SUNK|SUNKEN|DEPRESSED|RAISED)$"
)
# A finished-floor datum word. Statement = a block that pairs a step-like word with one of these.
DATUM_WORD = re.compile(r"^(?:FFL|AFFL|AFL)$")
_LETTERS = re.compile(r"[^A-Za-z]")

_AUTHORITY_FLAGS = (
    "quantity_issued", "customer_row_issued", "physical_host_authorized", "kind_authorized", "frame_authorized",
    "frozen_benchmark_scored",
)

Rect = tuple[float, float, float, float]
Point = tuple[float, float]


def _scope_ok(scope: object) -> bool:
    return (
        type(scope) is tuple and len(scope) >= 2
        and all(type(v) is str and bool(v.strip()) for v in scope)
    )


def _finite(*values: object) -> bool:
    return all(type(v) in (int, float) and math.isfinite(v) for v in values)


@dataclass(frozen=True)
class TextWord:
    text: str
    bbox: Rect


@dataclass(frozen=True)
class TextBlock:
    """One printed text block of one page: its words in reading order and whether every word is corroborated."""

    page_id: str
    block_id: str
    words: tuple[TextWord, ...]
    corroborated: bool
    observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RoomRegion:
    """One enclosed floor area of the plan page and the doorway closures that bound it."""

    room_id: str
    polygon: tuple[Point, ...]
    boundary_closure_ids: tuple[str, ...]


@dataclass(frozen=True)
class DoorClosure:
    """One doorway closure of the room topology and the native paths it is built from."""

    closure_id: str
    native_path_ids: tuple[int, ...]


@dataclass(frozen=True)
class DoorTopologyInput:
    door_id: str
    native_path_ids: tuple[int, ...]


@dataclass(frozen=True)
class LevelMark:
    page_id: str
    block_id: str
    token: str
    bbox: Rect
    corroborated: bool
    observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DoorBaseProof:
    door_id: str
    state: str
    reason: str
    closure_id: str | None
    room_ids: tuple[str, ...]
    marks_in_rooms: int
    evidence_observation_ids: tuple[str, ...]
    next_step: str = NEXT_STEP
    quantity_issued: bool = False
    customer_row_issued: bool = False
    physical_host_authorized: bool = False
    kind_authorized: bool = False
    frame_authorized: bool = False
    frozen_benchmark_scored: bool = False

    def __post_init__(self) -> None:
        for name in _AUTHORITY_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError("door_base_proof_cannot_carry_authority")

    @property
    def verified(self) -> bool:
        return self.state == VERIFIED


@dataclass(frozen=True)
class BaseProofReview:
    status: str
    reason_codes: tuple[str, ...]
    scope: tuple[str, ...]
    plan_page_id: str
    statement_pages: tuple[str, ...]
    plan_mark_count: int
    sheet_mark_counts: tuple[tuple[str, int], ...]
    doors: tuple[DoorBaseProof, ...]
    quantity_issued: bool = False
    customer_row_issued: bool = False
    frozen_benchmark_scored: bool = False
    schema_version: str = BASE_LEVEL_SCOPE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("quantity_issued", "customer_row_issued", "frozen_benchmark_scored"):
            if getattr(self, name) is not False:
                raise ValueError("base_proof_review_cannot_carry_authority")

    def to_public_summary(self) -> dict[str, object]:
        """Counts only: no door ids, closure ids, room ids, coordinates or text."""
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "doors": len(self.doors),
            "verified": sum(d.verified for d in self.doors),
            "abstained": sum(not d.verified for d in self.doors),
            "by_reason": dict(sorted(Counter(d.reason for d in self.doors).items())),
            "statement_pages": len(self.statement_pages),
            "plan_level_marks": self.plan_mark_count,
            "other_sheet_level_marks": [count for _, count in self.sheet_mark_counts],
            **{name: False for name in ("quantity_issued", "customer_row_issued", "frozen_benchmark_scored")},
        }

    def to_base_witnesses(self) -> dict[str, tuple[BaseWitness, ...]]:
        """The compiler's base witnesses: one per VERIFIED door, none for any other (never assumed)."""
        return {
            d.door_id: (BaseWitness(0.0, SOURCE_BASE_LEVEL_SCOPE, TEXT_CORROBORATED, d.evidence_observation_ids),)
            for d in self.doors if d.verified
        }


# ---------------------------------------------------------------------------------------------------------------------
# geometry
# ---------------------------------------------------------------------------------------------------------------------


def _point_in_polygon(point: Point, polygon: Sequence[Point]) -> bool:
    """Ray casting; a point ON the boundary counts as inside (the conservative direction: it adds an abstention)."""
    x, y = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        # on an edge?
        cross = (x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)
        if abs(cross) <= 1e-9 and min(x1, x2) - 1e-9 <= x <= max(x1, x2) + 1e-9 and min(y1, y2) - 1e-9 <= y <= max(y1, y2) + 1e-9:
            return True
        if (y1 > y) != (y2 > y):
            x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x < x_cross:
                inside = not inside
    return inside


def _bbox_centre(bbox: Rect) -> Point:
    return ((bbox[0] + bbox[2]) / 2.0, (bbox[1] + bbox[3]) / 2.0)


# ---------------------------------------------------------------------------------------------------------------------
# text: statements and marks
# ---------------------------------------------------------------------------------------------------------------------


def _tokens(block: TextBlock) -> list[str]:
    return [_LETTERS.sub("", w.text).upper() for w in block.words]


def is_level_statement(block: TextBlock) -> bool:
    """A block that pairs a step-like word with a finished-floor datum word."""
    tokens = _tokens(block)
    return any(STATEMENT_LEVEL_WORD.match(t) for t in tokens) and any(DATUM_WORD.match(t) for t in tokens)


def level_marks(blocks: Iterable[TextBlock]) -> tuple[LevelMark, ...]:
    """Every level-change word in a block that is not itself a statement, in a deterministic order."""
    marks: list[LevelMark] = []
    for block in blocks:
        if is_level_statement(block):
            continue
        for word, token in zip(block.words, _tokens(block)):
            if LEVEL_CHANGE_WORD.match(token):
                marks.append(LevelMark(block.page_id, block.block_id, token, word.bbox, block.corroborated,
                                       tuple(block.observation_ids)))
    return tuple(sorted(marks, key=lambda m: (m.page_id, m.block_id, m.bbox, m.token)))


def _blocks_valid(blocks: Sequence[TextBlock]) -> bool:
    for block in blocks:
        if not (isinstance(block, TextBlock) and type(block.page_id) is str and block.page_id.strip()
                and type(block.block_id) is str and type(block.corroborated) is bool):
            return False
        for word in block.words:
            if not (isinstance(word, TextWord) and type(word.text) is str and isinstance(word.bbox, tuple)
                    and len(word.bbox) == 4 and _finite(*word.bbox)):
                return False
    return True


def _rooms_valid(rooms: Sequence[RoomRegion]) -> bool:
    ids = set()
    for room in rooms:
        if not (isinstance(room, RoomRegion) and type(room.room_id) is str and room.room_id.strip()
                and room.room_id not in ids and type(room.polygon) is tuple and len(room.polygon) >= 3
                and all(isinstance(p, tuple) and len(p) == 2 and _finite(*p) for p in room.polygon)
                and type(room.boundary_closure_ids) is tuple
                and all(type(c) is str and c for c in room.boundary_closure_ids)):
            return False
        ids.add(room.room_id)
    return True


def _closures_valid(closures: Sequence[DoorClosure]) -> bool:
    ids = set()
    for closure in closures:
        if not (isinstance(closure, DoorClosure) and type(closure.closure_id) is str and closure.closure_id
                and closure.closure_id not in ids and type(closure.native_path_ids) is tuple
                and all(type(i) is int and i >= 0 for i in closure.native_path_ids)):
            return False
        ids.add(closure.closure_id)
    return True


def _doors_valid(doors: Sequence[DoorTopologyInput]) -> bool:
    ids = set()
    for door in doors:
        if not (isinstance(door, DoorTopologyInput) and type(door.door_id) is str and door.door_id.strip()
                and door.door_id not in ids and type(door.native_path_ids) is tuple
                and all(type(i) is int and i >= 0 for i in door.native_path_ids)):
            return False
        ids.add(door.door_id)
    return True


# ---------------------------------------------------------------------------------------------------------------------
# the proof
# ---------------------------------------------------------------------------------------------------------------------


def prove_door_bases(
    scope: tuple[str, ...],
    *,
    plan_page_id: str,
    doors: Sequence[DoorTopologyInput],
    closures: Sequence[DoorClosure],
    rooms: Sequence[RoomRegion],
    blocks: Sequence[TextBlock],
) -> BaseProofReview:
    """Prove, or name the gate that stops it, that each door's two adjoining floors are on the finished-floor slab."""
    if not _scope_ok(scope):
        return BaseProofReview(ABSTAINED, (GATE_SCOPE_INVALID,), (), str(plan_page_id), (), 0, (), ())
    if not (type(plan_page_id) is str and plan_page_id.strip() and _doors_valid(doors) and _closures_valid(closures)
            and _rooms_valid(rooms) and _blocks_valid(blocks)):
        return BaseProofReview(ABSTAINED, (GATE_INPUT_INVALID,), scope, str(plan_page_id), (), 0, (), ())

    blocks = tuple(blocks)
    statements = [b for b in blocks if is_level_statement(b)]
    statement_pages = tuple(sorted({b.page_id for b in statements}))
    marks = level_marks(blocks)
    plan_marks = tuple(m for m in marks if m.page_id == plan_page_id)
    sheet_counts = tuple(sorted(
        (page, sum(1 for m in marks if m.page_id == page))
        for page in statement_pages if page != plan_page_id
    ))
    plan_has_text = any(b.page_id == plan_page_id for b in blocks)
    # words the text-integrity authority could not corroborate: they could hide a level note, so a room that holds one
    # cannot be proven free of marks
    unverified_centres = [
        _bbox_centre(w.bbox) for b in blocks if b.page_id == plan_page_id and not b.corroborated for w in b.words
    ]

    # document-level gates: the same answer for every door
    document_gate = ""
    if not plan_has_text:
        document_gate = GATE_NO_PLAN_TEXT
    elif not statements:
        document_gate = GATE_NO_STATEMENT
    elif any(not b.corroborated for b in statements) or any(not m.corroborated for m in marks):
        document_gate = GATE_TEXT_RAW
    elif any(count > 0 and count != len(plan_marks) for _, count in sheet_counts):
        document_gate = GATE_NOT_RECONCILED

    room_by_id = {r.room_id: r for r in rooms}
    rooms_of_closure: dict[str, list[str]] = {}
    for room in sorted(rooms, key=lambda r: r.room_id):
        for closure_id in dict.fromkeys(room.boundary_closure_ids):
            rooms_of_closure.setdefault(closure_id, []).append(room.room_id)

    statement_ids = tuple(sorted({oid for b in statements for oid in b.observation_ids}))
    mark_ids = tuple(sorted({oid for m in plan_marks for oid in m.observation_ids}))
    results: list[DoorBaseProof] = []
    for door in sorted(doors, key=lambda d: d.door_id):
        owned = sorted(c.closure_id for c in closures if set(door.native_path_ids) & set(c.native_path_ids))
        closure_id: str | None = owned[0] if len(owned) == 1 else None
        room_ids: tuple[str, ...] = ()
        marked = 0
        if not owned:
            state, reason = STATE_ABSTAINED, GATE_NO_CLOSURE
        elif len(owned) > 1:
            state, reason = STATE_ABSTAINED, GATE_COMPETING_CLOSURES
        else:
            room_ids = tuple(rooms_of_closure.get(owned[0], ()))
            if len(room_ids) != 2:
                state, reason = STATE_ABSTAINED, GATE_NOT_TWO_ROOMS
            elif document_gate:
                state, reason = STATE_ABSTAINED, document_gate
            elif any(
                _point_in_polygon(centre, room_by_id[r].polygon) for centre in unverified_centres for r in room_ids
            ):
                state, reason = STATE_ABSTAINED, GATE_TEXT_RAW
            else:
                marked = sum(
                    1 for m in plan_marks
                    if any(_point_in_polygon(_bbox_centre(m.bbox), room_by_id[r].polygon) for r in room_ids)
                )
                if marked:
                    state, reason = STATE_ABSTAINED, GATE_ROOM_MARKED
                else:
                    state, reason = VERIFIED, PROOF_REASON
        results.append(DoorBaseProof(
            door_id=door.door_id, state=state, reason=reason, closure_id=closure_id, room_ids=room_ids,
            marks_in_rooms=marked,
            evidence_observation_ids=tuple(sorted(set(statement_ids) | set(mark_ids))) if state == VERIFIED else (),
        ))
    return BaseProofReview(
        BASE_LEVEL_SCOPE_STATUS, (document_gate,) if document_gate else (), scope, plan_page_id, statement_pages,
        len(plan_marks), sheet_counts, tuple(results),
    )
