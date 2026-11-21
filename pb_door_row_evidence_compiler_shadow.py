"""Shadow evidence compiler: one candidate row per PHYSICAL door, once the drawings verify four things.

The owner's rule for scoring a door (21 Nov 2026): one row per physical door once the drawings verify (1) both wall
connections, (2) the width, (3) the head level and (4) the base level, using the document's joinery head note
(a head level AFL, U.N.O.) only where it applies, and verifying the base separately. This module is the composition of those
four verifications. It is NOT an issuer: it never publishes a quantity, a customer row, a host, a frame or a kind, and
every authority flag is False by construction. A row that passes is ``READY_FOR_EXISTING_ISSUER`` evidence for the
authority-promotion review (AGENTS.md); a row that does not pass names the first gate that stopped it.

Inputs are witnesses that other authorities produced (the two-wall tag, a printed or scheduled width, a head level, a base
level) with the trust each carries; nothing here reads a PDF, a filename, a project name or a benchmark value.

Rules (each has a named gate, each is tested):
* wall connections: the owner contract's tag must be ``TWO_WALL_SECTIONS_TAGGED`` with two distinct sections;
* width: only text-integrity-corroborated witnesses count (raw text never verifies); witnesses that disagree conflict,
  none is chosen; several that agree are one width;
* head level: a door-specific witness (a schedule row's height, an elevation outline on a datum) beats the document
  U.N.O. note ("unless otherwise noted"), which applies only when the door has no door-specific head witness; two
  door-specific witnesses that disagree conflict; a note whose text is not corroborated does not apply;
* base level: its own verification, never assumed. A door with no base witness stays unverified: a head level measured
  above the finished floor is not an opening height until the base is proven. The opening height is head minus base and
  must be positive;
* identity: witnesses are grouped by physical door id, so the same door seen in the plan, an enlarged inset, an
  elevation and a schedule is ONE row that all of those enrich, never several.
"""
from __future__ import annotations

import math
from collections import Counter, defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from typing import Any

from pb_migration_contracts import stable_contract_id

DOOR_ROW_EVIDENCE_SCHEMA_VERSION = "1.0.0"

# verification states
VERIFIED = "VERIFIED"
ABSTAINED = "ABSTAINED"
CONFLICT = "CONFLICT"

ROW_READY = "READY_FOR_EXISTING_ISSUER"
ROW_NOT_READY = "NOT_READY"

TEXT_CORROBORATED = "corroborated"
TEXT_RAW = "raw_unverified"

SOURCE_PLAN_LABEL = "plan_label"
SOURCE_SCHEDULE = "door_schedule_row"
SOURCE_ELEVATION = "elevation_outline_on_datum"
SOURCE_DOCUMENT_NOTE = "document_joinery_head_note"
SOURCE_BASE_ELEVATION = "elevation_base_on_ffl"
SOURCE_BASE_SCHEDULE = "schedule_base_or_sill"
SOURCE_BASE_LEVEL_SCOPE = "level_scope_proof"

TAG_TAGGED = "TWO_WALL_SECTIONS_TAGGED"

# gates (axis_reason)
GATE_WALLS_NOT_TAGGED = "wall_connections_not_tagged"
GATE_WALLS_NOT_TWO = "wall_connections_need_two_distinct_sections"
GATE_WIDTH_MISSING = "width_missing"
GATE_WIDTH_RAW = "width_text_not_corroborated"
GATE_WIDTH_CONFLICT = "width_witnesses_conflict"
GATE_WIDTH_INVALID = "width_witness_invalid"
GATE_HEAD_MISSING = "head_level_missing"
GATE_HEAD_NOTE_RAW = "head_note_text_not_corroborated"
GATE_HEAD_RAW = "head_level_text_not_corroborated"
GATE_HEAD_CONFLICT = "head_level_witnesses_conflict"
GATE_HEAD_INVALID = "head_level_witness_invalid"
GATE_BASE_UNVERIFIED = "base_level_unverified_no_proof_in_the_drawings"
GATE_BASE_RAW = "base_level_text_not_corroborated"
GATE_BASE_CONFLICT = "base_level_witnesses_conflict"
GATE_BASE_INVALID = "base_level_witness_invalid"
GATE_HEIGHT_NOT_POSITIVE = "opening_height_not_positive"
GATE_SCOPE_INVALID = "scope_invalid"
GATE_DOOR_INVALID = "door_witness_without_door_identity"
STATUS_COMPILED = "DOOR_ROW_EVIDENCE_COMPILED_SHADOW"

NEXT_STEP = "authority_promotion_review_then_existing_issuer_seal_and_customer_row"

# Witnesses of the same quantity agree when they differ by no more than this many millimetres (printed values are
# integers; this only absorbs unit conversion noise, it is not a plausibility range).
AGREE_TOL_MM = 0.5

_AUTHORITY_FLAGS = (
    "quantity_issued", "customer_row_issued", "physical_host_authorized", "physical_opening_authenticated",
    "kind_authorized", "frame_authorized", "frozen_benchmark_scored",
)

AXES = ("wall_connections", "width", "head_level", "base_level")


def _scope_ok(scope: object) -> bool:
    return (
        type(scope) is tuple and len(scope) >= 2
        and all(type(v) is str and bool(v.strip()) for v in scope)
    )


def _number(value: object) -> bool:
    return type(value) in (int, float) and math.isfinite(value)


@dataclass(frozen=True)
class WallConnectionWitness:
    """The owner contract's tag for this door (``pb_opening_two_wall_contact_tags.TwoWallOpeningTag`` fields)."""

    tag_status: str
    wall_section_ids: tuple[str, ...]
    contact_geometry: str = ""
    reason: str = ""


@dataclass(frozen=True)
class WidthWitness:
    value_mm: float
    source: str
    text_trust: str
    observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class HeadWitness:
    head_afl_mm: float
    source: str
    door_specific: bool
    text_trust: str
    observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class BaseWitness:
    base_afl_mm: float
    source: str
    text_trust: str = TEXT_CORROBORATED
    observation_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class DoorWitnesses:
    """Everything the drawings say about ONE physical door, from every view that shows it."""

    door_id: str
    walls: tuple[WallConnectionWitness, ...] = ()
    widths: tuple[WidthWitness, ...] = ()
    heads: tuple[HeadWitness, ...] = ()
    bases: tuple[BaseWitness, ...] = ()


@dataclass(frozen=True)
class AxisResult:
    axis: str
    state: str
    reason: str
    value: float | None = None
    source: str = ""


@dataclass(frozen=True)
class DoorRowEvidence:
    row_id: str
    door_id: str
    scope: tuple[str, ...]
    axes: tuple[AxisResult, ...]
    row_state: str
    first_open_gate: str
    width_mm: float | None
    head_afl_mm: float | None
    base_afl_mm: float | None
    opening_height_mm: float | None
    candidate_area_m2: float | None
    next_step: str = NEXT_STEP
    quantity_issued: bool = False
    customer_row_issued: bool = False
    physical_host_authorized: bool = False
    physical_opening_authenticated: bool = False
    kind_authorized: bool = False
    frame_authorized: bool = False
    frozen_benchmark_scored: bool = False
    schema_version: str = DOOR_ROW_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in _AUTHORITY_FLAGS:
            if getattr(self, name) is not False:
                raise ValueError("door_row_evidence_cannot_carry_authority")
        if self.row_state == ROW_READY and (
            any(a.state != VERIFIED for a in self.axes) or self.opening_height_mm is None
            or self.width_mm is None or self.candidate_area_m2 is None
        ):
            raise ValueError("a ready row needs all four axes verified")

    @property
    def ready(self) -> bool:
        return self.row_state == ROW_READY

    def axis(self, name: str) -> AxisResult:
        return next(a for a in self.axes if a.axis == name)

    def to_dict(self) -> dict[str, object]:
        return {
            "row_id": self.row_id,
            "door_id": self.door_id,
            "row_state": self.row_state,
            "first_open_gate": self.first_open_gate,
            "axes": [
                {"axis": a.axis, "state": a.state, "reason": a.reason, "value": a.value, "source": a.source}
                for a in self.axes
            ],
            "width_mm": self.width_mm,
            "head_afl_mm": self.head_afl_mm,
            "base_afl_mm": self.base_afl_mm,
            "opening_height_mm": self.opening_height_mm,
            "candidate_area_m2": self.candidate_area_m2,
            "next_step": self.next_step,
            **{name: False for name in _AUTHORITY_FLAGS},
        }


@dataclass(frozen=True)
class DoorRowCompilation:
    status: str
    reason_codes: tuple[str, ...]
    scope: tuple[str, ...]
    rows: tuple[DoorRowEvidence, ...]
    quantity_issued: bool = False
    customer_row_issued: bool = False
    frozen_benchmark_scored: bool = False
    schema_version: str = DOOR_ROW_EVIDENCE_SCHEMA_VERSION

    def __post_init__(self) -> None:
        for name in ("quantity_issued", "customer_row_issued", "frozen_benchmark_scored"):
            if getattr(self, name) is not False:
                raise ValueError("door_row_compilation_cannot_carry_authority")

    def to_public_summary(self) -> dict[str, object]:
        """Counts only: no door ids, no coordinates, no values."""
        gates = Counter(r.first_open_gate for r in self.rows)
        per_axis = {
            axis: dict(sorted(Counter(r.axis(axis).state for r in self.rows).items())) for axis in AXES
        }
        return {
            "schema_version": self.schema_version,
            "status": self.status,
            "reason_codes": list(self.reason_codes),
            "physical_doors": len(self.rows),
            "ready_for_existing_issuer": sum(r.ready for r in self.rows),
            "not_ready": sum(not r.ready for r in self.rows),
            "axis_states": per_axis,
            "first_open_gate": dict(sorted(gates.items())),
            **{name: False for name in ("quantity_issued", "customer_row_issued", "frozen_benchmark_scored")},
        }


# ---------------------------------------------------------------------------------------------------------------------
# the four verifications
# ---------------------------------------------------------------------------------------------------------------------


def _agree(values: Sequence[float]) -> bool:
    return max(values) - min(values) <= AGREE_TOL_MM


def _mean(values: Sequence[float]) -> float:
    """Witnesses that agree within the tolerance are one value; their mean is symmetric and order independent."""
    return float(sum(values)) / len(values)


def _verify_walls(walls: Sequence[WallConnectionWitness]) -> AxisResult:
    tagged = [w for w in walls if isinstance(w, WallConnectionWitness) and w.tag_status == TAG_TAGGED]
    if not tagged:
        return AxisResult("wall_connections", ABSTAINED, GATE_WALLS_NOT_TAGGED)
    for w in tagged:
        ids = w.wall_section_ids
        if type(ids) is not tuple or len(ids) != 2 or ids[0] == ids[1] or not all(type(i) is str and i for i in ids):
            return AxisResult("wall_connections", ABSTAINED, GATE_WALLS_NOT_TWO)
    # several tags for one physical door must name the same two sections, else they compete
    if len({frozenset(w.wall_section_ids) for w in tagged}) > 1:
        return AxisResult("wall_connections", CONFLICT, GATE_WALLS_NOT_TWO)
    return AxisResult("wall_connections", VERIFIED, "two_distinct_wall_sections_tagged", source=tagged[0].contact_geometry)


def _verify_width(widths: Sequence[WidthWitness]) -> AxisResult:
    if not widths:
        return AxisResult("width", ABSTAINED, GATE_WIDTH_MISSING)
    if any(not (isinstance(w, WidthWitness) and _number(w.value_mm) and w.value_mm > 0) for w in widths):
        return AxisResult("width", ABSTAINED, GATE_WIDTH_INVALID)
    good = [w for w in widths if w.text_trust == TEXT_CORROBORATED]
    if not good:
        return AxisResult("width", ABSTAINED, GATE_WIDTH_RAW)
    if not _agree([w.value_mm for w in good]):
        return AxisResult("width", CONFLICT, GATE_WIDTH_CONFLICT)
    return AxisResult("width", VERIFIED, "corroborated_width", _mean([w.value_mm for w in good]),
                      "+".join(sorted({w.source for w in good})))


def _verify_head(heads: Sequence[HeadWitness]) -> AxisResult:
    if not heads:
        return AxisResult("head_level", ABSTAINED, GATE_HEAD_MISSING)
    if any(not (isinstance(h, HeadWitness) and _number(h.head_afl_mm) and h.head_afl_mm > 0) for h in heads):
        return AxisResult("head_level", ABSTAINED, GATE_HEAD_INVALID)
    specific = [h for h in heads if h.door_specific]
    general = [h for h in heads if not h.door_specific]
    if specific:
        good = [h for h in specific if h.text_trust == TEXT_CORROBORATED]
        if not good:
            return AxisResult("head_level", ABSTAINED, GATE_HEAD_RAW)
        if not _agree([h.head_afl_mm for h in good]):
            return AxisResult("head_level", CONFLICT, GATE_HEAD_CONFLICT)
        return AxisResult("head_level", VERIFIED, "door_specific_head_level", _mean([h.head_afl_mm for h in good]),
                          "+".join(sorted({h.source for h in good})))
    good = [h for h in general if h.text_trust == TEXT_CORROBORATED]
    if not good:
        return AxisResult("head_level", ABSTAINED, GATE_HEAD_NOTE_RAW)
    if not _agree([h.head_afl_mm for h in good]):
        return AxisResult("head_level", CONFLICT, GATE_HEAD_CONFLICT)
    return AxisResult("head_level", VERIFIED, "document_note_applies_unless_otherwise_noted",
                      _mean([h.head_afl_mm for h in good]), SOURCE_DOCUMENT_NOTE)


def _verify_base(bases: Sequence[BaseWitness]) -> AxisResult:
    if not bases:
        return AxisResult("base_level", ABSTAINED, GATE_BASE_UNVERIFIED)
    if any(not (isinstance(b, BaseWitness) and _number(b.base_afl_mm) and b.base_afl_mm >= 0) for b in bases):
        return AxisResult("base_level", ABSTAINED, GATE_BASE_INVALID)
    good = [b for b in bases if b.text_trust == TEXT_CORROBORATED]
    if not good:
        return AxisResult("base_level", ABSTAINED, GATE_BASE_RAW)
    if not _agree([b.base_afl_mm for b in good]):
        return AxisResult("base_level", CONFLICT, GATE_BASE_CONFLICT)
    return AxisResult("base_level", VERIFIED, "base_level_proven", _mean([b.base_afl_mm for b in good]),
                      "+".join(sorted({b.source for b in good})))


def compile_door(scope: tuple[str, ...], door: DoorWitnesses) -> DoorRowEvidence:
    walls = _verify_walls(door.walls)
    width = _verify_width(door.widths)
    head = _verify_head(door.heads)
    base = _verify_base(door.bases)
    axes = [walls, width, head, base]
    height: float | None = None
    if head.state == VERIFIED and base.state == VERIFIED:
        raw_height = float(head.value) - float(base.value)  # type: ignore[arg-type]
        if raw_height > 0:
            height = raw_height
        else:
            base = AxisResult("base_level", ABSTAINED, GATE_HEIGHT_NOT_POSITIVE, base.value, base.source)
            axes[3] = base
    first = next((f"{a.axis}:{a.reason}" for a in axes if a.state != VERIFIED), "")
    ready = all(a.state == VERIFIED for a in axes) and height is not None and width.state == VERIFIED
    area = (float(width.value) * height / 1_000_000.0) if ready and width.value is not None and height else None  # type: ignore[operator]
    return DoorRowEvidence(
        row_id=stable_contract_id("door_row_evidence", {"scope": list(scope), "door_id": door.door_id}),
        door_id=door.door_id,
        scope=scope,
        axes=tuple(axes),
        row_state=ROW_READY if ready else ROW_NOT_READY,
        first_open_gate=first,
        width_mm=width.value if width.state == VERIFIED else None,
        head_afl_mm=head.value if head.state == VERIFIED else None,
        base_afl_mm=base.value if base.state == VERIFIED else None,
        opening_height_mm=height if ready else None,
        candidate_area_m2=area,
    )


def group_witnesses(witnesses: Iterable[DoorWitnesses]) -> tuple[DoorWitnesses, ...]:
    """One physical door, one bundle: every view's witnesses for the same door id enrich it, none creates another."""
    merged: dict[str, dict[str, list[Any]]] = defaultdict(lambda: {"walls": [], "widths": [], "heads": [], "bases": []})
    for door in witnesses:
        bucket = merged[door.door_id]
        bucket["walls"].extend(door.walls)
        bucket["widths"].extend(door.widths)
        bucket["heads"].extend(door.heads)
        bucket["bases"].extend(door.bases)
    return tuple(
        DoorWitnesses(door_id, tuple(b["walls"]), tuple(b["widths"]), tuple(b["heads"]), tuple(b["bases"]))
        for door_id, b in sorted(merged.items())
    )


def compile_door_rows(scope: tuple[str, ...], witnesses: Iterable[DoorWitnesses]) -> DoorRowCompilation:
    if not _scope_ok(scope):
        return DoorRowCompilation(ABSTAINED, (GATE_SCOPE_INVALID,), (), ())
    doors = list(witnesses)
    if any(not (isinstance(d, DoorWitnesses) and type(d.door_id) is str and d.door_id.strip()) for d in doors):
        # a witness with no door identity cannot be attributed to any door: fail closed, never drop it silently
        return DoorRowCompilation(ABSTAINED, (GATE_DOOR_INVALID,), scope, ())
    rows = tuple(compile_door(scope, d) for d in group_witnesses(doors))
    return DoorRowCompilation(STATUS_COMPILED, (), scope, rows)
