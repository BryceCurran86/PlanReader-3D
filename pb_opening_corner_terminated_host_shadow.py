"""Shadow-only diagnostic: corner-terminated two-face reveal-stub host evidence.

Why this exists
---------------
``JAMB_BOUNDED_TWO_FACE_INTERRUPTION`` openings are bound to a host wall through
exact W4 source-primitive lineage of their four wall-face stubs. The existing
reveal-stub resolver needs a *collinear* flanking wall past BOTH flanks. An
opening whose far flank is a building corner (the host wall's two faces end on a
drawn mitre against a perpendicular wall) has no collinear continuation there,
so every existing host path abstains with ``no_authenticated_host_wall_band``.

This module asks one question about such an opening and answers it as
**diagnostic evidence only**:

    One flank independently owns a collinear host lineage on BOTH faces, and the
    other flank's two stubs end on a DRAWN mitre whose end points are also the
    start points of two parallel perpendicular wall faces that are exactly one
    host-wall thickness apart.

Contract (see ``AGENTS.md`` and the 9 Nov 2026 MAX decision on #4135)
---------------------------------------------------------------------
* Default off. ``assess_corner_terminated_host_shadow`` returns ``()`` unless the
  caller passes the strict boolean ``enabled=True``. Nothing in production imports
  this module.
* The result never populates the host-binding registry, ``host_wall_id``,
  ``host_binding_record_id``, a frame, a quantity or a customer row. A positive
  result is ``EvidenceResolutionStatus.CANDIDATE``, never ``CORROBORATED``.
* The perpendicular wall is a TERMINATOR witness. It is never merged into the
  collinear host equivalence group and never proves a complete frame or filling.
* Only DRAWN connections count: contact means exact source-coordinate
  coincidence (``CONTACT_TOL_PT``). The 2.5 pt gap snap is only used, unchanged,
  to decide whether an already drawn-connected W4 candidate is locally owned by
  that stub end (the same constant the existing resolvers use). It never closes
  an undrawn gap.
* Every wall-owned drawn primitive on the page participates (not a pre-filtered
  candidate list). Unexplained wall-owned contact, a second terminator, a
  collinear continuation, ambiguous equivalence or unclean boundary evidence
  abstains or conflicts. Nothing is resolved by nearest, first or smallest.
* Inputs are never mutated; the result is deterministic and order-invariant.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable, Optional, Sequence

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT

CORNER_HOST_SHADOW_SCHEMA_VERSION = "1.0.0"

CONTACT_TOL_PT = 1e-3
THICKNESS_MATCH_TOL_PT = 1e-3
OUTWARD_EXTENT_MIN_PT = 0.5
PARALLEL_TOL = math.sin(math.radians(5.0))
_LOCAL_OWNER_TOL_PT = DEFAULT_GAP_SNAP_TOLERANCE_PT + 1e-6

CORNER_HOST_CANDIDATE = "corner_terminated_two_face_stub_host_candidate_shadow"
FACES_UNSUPPORTED = "corner_opening_faces_unsupported"
STUBS_NOT_STAGGERED = "corner_stub_ends_not_staggered"
COLLINEAR_CONTINUATION = "corner_collinear_continuation_present"
UNEXPLAINED_CONTACT = "corner_unexplained_wall_contact"
MITRE_NOT_DRAWN = "corner_mitre_not_drawn"
PERPENDICULAR_NOT_DRAWN = "corner_perpendicular_face_not_drawn"
PERPENDICULAR_THROUGH = "corner_perpendicular_wall_passes_through"
TERMINATOR_AMBIGUOUS = "corner_terminator_ambiguous"
FACES_NOT_SAME_SIDE = "corner_perpendicular_faces_not_same_side"
THICKNESS_MISMATCH = "corner_perpendicular_wall_thickness_mismatch"
STAGGER_INCONSISTENT = "corner_stagger_inconsistent"
TERMINATOR_NOT_CLEAN = "corner_terminator_wall_evidence_not_clean"
FLANK_UNMAPPED = "corner_collinear_flank_unmapped"
FLANK_NOT_CLEAN = "corner_collinear_flank_wall_evidence_not_clean"
FLANK_AMBIGUOUS = "corner_collinear_flank_ambiguous"
TERMINATOR_OVERLAPS_HOST = "corner_terminator_overlaps_host_lineage"
ORIENTATION_AMBIGUOUS = "corner_orientation_ambiguous"
WALL_SCOPE_UNAVAILABLE = "corner_wall_scope_unavailable"
WALL_SCOPE_OWNERSHIP_MISMATCH = "corner_wall_scope_ownership_mismatch"
OPENING_GEOMETRY_UNAVAILABLE = "corner_opening_geometry_unavailable"

# Reported when a shadow positive exists: the registry, binding, frame, quantity
# and customer fields stay untouched, so the first remaining gate is the
# authority-promotion review itself.
PROMOTION_GATE = "authority_promotion_review_required_registry_untouched"
_OWNERSHIP_MISMATCH = object()

Point = tuple[float, float]
Line = tuple[float, float, float, float]


@dataclass(frozen=True)
class CornerFrame:
    """Opening axis frame in page points. ``origin`` sits on the first jamb."""

    origin: Point
    axis: Point
    normal: Point
    length: float
    thickness: float


@dataclass(frozen=True)
class FaceStub:
    """One drawn wall-face stub that belongs to the opening's own support."""

    primitive_id: str
    line: Line


@dataclass(frozen=True)
class OwnerRef:
    """A W4 candidate that owns a drawn primitive (facts copied, not authority)."""

    wall_candidate_id: str
    equivalence_group: tuple[str, ...]
    clean: bool
    centerline_pts: tuple[Point, ...]


@dataclass(frozen=True)
class DrawnPrimitive:
    """A wall-owned authenticated native source line (unowned ink is not wall evidence)."""

    primitive_id: str
    line: Line
    owners: tuple[OwnerRef, ...]


@dataclass(frozen=True)
class CornerTerminatedHostShadowResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    collinear_side: Optional[str] = None
    host_member_ids: tuple[str, ...] = ()
    host_equivalence_groups: tuple[tuple[str, ...], ...] = ()
    terminator_witness_ids: tuple[str, ...] = ()
    terminator_primitive_ids: tuple[str, ...] = ()
    mitre_primitive_ids: tuple[str, ...] = ()
    perpendicular_thickness_pt: Optional[float] = None
    stagger_pt: Optional[float] = None
    result_id: Optional[str] = None
    schema_version: str = CORNER_HOST_SHADOW_SCHEMA_VERSION

    @property
    def is_candidate(self) -> bool:
        return self.status is EvidenceResolutionStatus.CANDIDATE


@dataclass(frozen=True)
class CornerTerminatedHostShadowRecord:
    """One diagnostic row per non-hosted two-face opening. Never an authority."""

    opening_identity_id: str
    page_id: str
    binding_status: str
    binding_reason_codes: tuple[str, ...]
    result: CornerTerminatedHostShadowResult
    first_remaining_gate: str


_OWNERSHIP_FIELDS = ("document_id", "revision_id", "source_sha256", "snapshot_id", "page_id")


def wall_scope_is_owned_by_opening(scope, opening, selector) -> bool:
    """Exact document/revision/SHA/snapshot/page ownership of the wall scope.

    A foreign, stale or re-based wall scope (any of the five ids differs from the
    opening's own, or from the selector the composition used) is never evidence
    for this opening.
    """

    for name in _OWNERSHIP_FIELDS:
        wanted = str(getattr(opening, name))
        if str(getattr(scope, name)) != wanted or str(getattr(selector, name)) != wanted:
            return False
    return True


# --------------------------------------------------------------------- geometry

def _dot(a: Point, b: Point) -> float:
    return a[0] * b[0] + a[1] * b[1]


def _cross(a: Point, b: Point) -> float:
    return a[0] * b[1] - a[1] * b[0]


def _sub(a: Point, b: Point) -> Point:
    return (a[0] - b[0], a[1] - b[1])


def _unit(line: Line) -> Optional[Point]:
    dx, dy = line[2] - line[0], line[3] - line[1]
    norm = math.hypot(dx, dy)
    if not math.isfinite(norm) or norm <= 1e-9:
        return None
    return (dx / norm, dy / norm)


def _endpoints(line: Line) -> tuple[Point, Point]:
    return ((line[0], line[1]), (line[2], line[3]))


def _distance_to_segment(point: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= 0.0:
        return math.hypot(point[0] - a[0], point[1] - a[1])
    t = max(0.0, min(1.0, ((point[0] - a[0]) * dx + (point[1] - a[1]) * dy) / length_sq))
    return math.hypot(point[0] - (a[0] + t * dx), point[1] - (a[1] + t * dy))


def _touches(line: Line, point: Point) -> bool:
    a, b = _endpoints(line)
    return _distance_to_segment(point, a, b) <= CONTACT_TOL_PT


def _same_point(a: Point, b: Point) -> bool:
    return math.hypot(a[0] - b[0], a[1] - b[1]) <= CONTACT_TOL_PT


def _axis_data(line: Line, frame: CornerFrame) -> Optional[tuple[float, float, float]]:
    """(lo, hi, offset) of a line parallel to the opening axis, else ``None``."""

    unit = _unit(line)
    if unit is None or abs(_cross(unit, frame.axis)) > PARALLEL_TOL:
        return None
    points = _endpoints(line)
    along = tuple(_dot(_sub(p, frame.origin), frame.axis) for p in points)
    offsets = tuple(_dot(_sub(p, frame.origin), frame.normal) for p in points)
    if max(offsets) - min(offsets) > CONTACT_TOL_PT:
        return None
    return (min(along), max(along), sum(offsets) / len(offsets))


def _s_of(point: Point, frame: CornerFrame) -> float:
    return _dot(_sub(point, frame.origin), frame.axis)


def _n_of(point: Point, frame: CornerFrame) -> float:
    return _dot(_sub(point, frame.origin), frame.normal)


def _owner_is_local(owner: OwnerRef, point: Point) -> bool:
    pts = owner.centerline_pts
    if len(pts) < 2:
        return False
    return min(
        _distance_to_segment(point, a, b) for a, b in zip(pts, pts[1:])
    ) <= _LOCAL_OWNER_TOL_PT


# ----------------------------------------------------------------- result helpers

def _result(
    status: EvidenceResolutionStatus,
    reasons: Sequence[str],
    **kwargs,
) -> CornerTerminatedHostShadowResult:
    payload = {
        "schema_version": CORNER_HOST_SHADOW_SCHEMA_VERSION,
        "status": status.value,
        "reasons": tuple(reasons),
        "side": kwargs.get("collinear_side"),
        "host": tuple(kwargs.get("host_member_ids", ())),
        "terminator": tuple(kwargs.get("terminator_witness_ids", ())),
        "terminator_primitives": tuple(kwargs.get("terminator_primitive_ids", ())),
        "mitre": tuple(kwargs.get("mitre_primitive_ids", ())),
    }
    return CornerTerminatedHostShadowResult(
        status=status,
        reason_codes=tuple(reasons),
        result_id=stable_contract_id("corner_terminated_host_shadow", payload, digest_chars=32),
        **kwargs,
    )


@dataclass(frozen=True)
class _Attempt:
    result: CornerTerminatedHostShadowResult
    depth: int


def _stop(depth: int, status: EvidenceResolutionStatus, reason: str, side: Optional[str]) -> _Attempt:
    return _Attempt(_result(status, (reason,), collinear_side=side), depth)


@dataclass(frozen=True)
class _Stub:
    primitive_id: str
    line: Line
    lo: float
    hi: float
    offset: float


def _classify_stubs(frame: CornerFrame, faces: Sequence[FaceStub]):
    if len(faces) != 4:
        return None
    rows = []
    for face in faces:
        data = _axis_data(face.line, frame)
        if data is None:
            return None
        rows.append(_Stub(face.primitive_id, face.line, data[0], data[1], data[2]))
    left = [r for r in rows if abs(r.hi) <= CONTACT_TOL_PT and r.lo < -CONTACT_TOL_PT]
    right = [
        r for r in rows
        if abs(r.lo - frame.length) <= CONTACT_TOL_PT and r.hi > frame.length + CONTACT_TOL_PT
    ]
    if len(left) != 2 or len(right) != 2:
        return None

    def by_sign(side_rows):
        neg = [r for r in side_rows if r.offset < 0.0]
        pos = [r for r in side_rows if r.offset > 0.0]
        if len(neg) != 1 or len(pos) != 1:
            return None
        return neg[0], pos[0]

    left_pair, right_pair = by_sign(left), by_sign(right)
    if left_pair is None or right_pair is None:
        return None
    if (
        abs(left_pair[0].offset - right_pair[0].offset) > CONTACT_TOL_PT
        or abs(left_pair[1].offset - right_pair[1].offset) > CONTACT_TOL_PT
    ):
        return None
    return {"left": left_pair, "right": right_pair}


def _outer_point(stub: _Stub, frame: CornerFrame, side: str) -> Point:
    points = _endpoints(stub.line)
    target = stub.lo if side == "left" else stub.hi
    return min(points, key=lambda p: abs(_s_of(p, frame) - target))


def _evaluate(
    frame: CornerFrame,
    stubs: dict,
    drawn: Sequence[DrawnPrimitive],
    own_ids: frozenset[str],
    are_ambiguous: Callable[[str, str], bool],
    collinear_side: str,
) -> _Attempt:
    corner_side = "right" if collinear_side == "left" else "left"
    corner_neg, corner_pos = stubs[corner_side]
    a_pt = _outer_point(corner_neg, frame, corner_side)
    b_pt = _outer_point(corner_pos, frame, corner_side)
    s_a, s_b = _s_of(a_pt, frame), _s_of(b_pt, frame)
    stagger = abs(s_a - s_b)
    if stagger <= CONTACT_TOL_PT:
        return _stop(1, EvidenceResolutionStatus.ABSTAINED, STUBS_NOT_STAGGERED, collinear_side)
    outward_sign = 1.0 if corner_side == "right" else -1.0

    mitre_ids: list[str] = []
    perp_ids: dict[str, list[tuple[str, float]]] = {"a": [], "b": []}
    terminator_owners: dict[str, OwnerRef] = {}
    terminator_prims: set[str] = set()

    for label, point in (("a", a_pt), ("b", b_pt)):
        for prim in drawn:
            if prim.primitive_id in own_ids or not _touches(prim.line, point):
                continue
            end0, end1 = _endpoints(prim.line)
            unit = _unit(prim.line)
            if unit is None:
                continue
            data = _axis_data(prim.line, frame)
            if data is not None:
                # Collinear with the host axis. The part that lies on the aperture
                # side of the stub end (duplicates, through lines) is not corner
                # evidence; anything running outward is a collinear continuation.
                s_point = _s_of(point, frame)
                extent = (data[1] - s_point) if corner_side == "right" else (s_point - data[0])
                if extent > CONTACT_TOL_PT:
                    return _stop(2, EvidenceResolutionStatus.ABSTAINED, COLLINEAR_CONTINUATION, collinear_side)
                continue
            is_mitre = (
                (_same_point(end0, a_pt) and _same_point(end1, b_pt))
                or (_same_point(end0, b_pt) and _same_point(end1, a_pt))
            )
            if is_mitre:
                if prim.primitive_id not in mitre_ids:
                    mitre_ids.append(prim.primitive_id)
                for owner in prim.owners:
                    terminator_owners[owner.wall_candidate_id] = owner
                terminator_prims.add(prim.primitive_id)
                continue
            if abs(_dot(unit, frame.axis)) <= PARALLEL_TOL:
                if not (_same_point(end0, point) or _same_point(end1, point)):
                    return _stop(2, EvidenceResolutionStatus.ABSTAINED, PERPENDICULAR_THROUGH, collinear_side)
                far = end1 if _same_point(end0, point) else end0
                direction = 1.0 if _n_of(far, frame) - _n_of(point, frame) > 0.0 else -1.0
                perp_ids[label].append((prim.primitive_id, direction))
                for owner in prim.owners:
                    terminator_owners[owner.wall_candidate_id] = owner
                terminator_prims.add(prim.primitive_id)
                continue
            return _stop(2, EvidenceResolutionStatus.ABSTAINED, UNEXPLAINED_CONTACT, collinear_side)

    if not mitre_ids:
        return _stop(3, EvidenceResolutionStatus.ABSTAINED, MITRE_NOT_DRAWN, collinear_side)
    if not perp_ids["a"] or not perp_ids["b"]:
        return _stop(3, EvidenceResolutionStatus.ABSTAINED, PERPENDICULAR_NOT_DRAWN, collinear_side)
    directions = {d for _, d in perp_ids["a"]} | {d for _, d in perp_ids["b"]}
    if len(directions) != 1:
        multi_a = len({d for _, d in perp_ids["a"]}) > 1
        multi_b = len({d for _, d in perp_ids["b"]}) > 1
        if multi_a or multi_b:
            return _stop(4, EvidenceResolutionStatus.CONFLICT, TERMINATOR_AMBIGUOUS, collinear_side)
        return _stop(4, EvidenceResolutionStatus.ABSTAINED, FACES_NOT_SAME_SIDE, collinear_side)
    direction = next(iter(directions))
    if abs(stagger - frame.thickness) > THICKNESS_MATCH_TOL_PT:
        return _stop(5, EvidenceResolutionStatus.ABSTAINED, THICKNESS_MISMATCH, collinear_side)
    # An outer corner sits on the face opposite to the perpendicular wall's
    # direction and runs further outward than the inner face.
    outer_is_neg = direction > 0.0
    outer_stub_s = s_a if outer_is_neg else s_b
    inner_stub_s = s_b if outer_is_neg else s_a
    if outward_sign * (outer_stub_s - inner_stub_s) <= CONTACT_TOL_PT:
        return _stop(5, EvidenceResolutionStatus.ABSTAINED, STAGGER_INCONSISTENT, collinear_side)
    if not terminator_owners or any(not o.clean for o in terminator_owners.values()):
        return _stop(6, EvidenceResolutionStatus.ABSTAINED, TERMINATOR_NOT_CLEAN, collinear_side)

    # ---- the collinear flank must independently own a host lineage on BOTH faces
    host_owners: dict[str, OwnerRef] = {}
    groups: set[tuple[str, ...]] = set()
    flank_stubs = stubs[collinear_side]
    for stub in flank_stubs:
        point = _outer_point(stub, frame, collinear_side)
        s_point = _s_of(point, frame)
        role_owners: dict[str, OwnerRef] = {}
        for prim in drawn:
            if prim.primitive_id in own_ids:
                continue
            data = _axis_data(prim.line, frame)
            if data is None or abs(data[2] - stub.offset) > CONTACT_TOL_PT:
                continue
            if not (data[0] - CONTACT_TOL_PT <= s_point <= data[1] + CONTACT_TOL_PT):
                continue
            outward = (s_point - data[0]) if collinear_side == "left" else (data[1] - s_point)
            if outward <= OUTWARD_EXTENT_MIN_PT:
                continue
            for owner in prim.owners:
                if _owner_is_local(owner, point):
                    role_owners[owner.wall_candidate_id] = owner
        if not role_owners:
            return _stop(7, EvidenceResolutionStatus.ABSTAINED, FLANK_UNMAPPED, collinear_side)
        if any(not o.clean for o in role_owners.values()):
            return _stop(7, EvidenceResolutionStatus.ABSTAINED, FLANK_NOT_CLEAN, collinear_side)
        ids = sorted(role_owners)
        for i, first in enumerate(ids):
            for second in ids[i + 1:]:
                if are_ambiguous(first, second):
                    return _stop(7, EvidenceResolutionStatus.CONFLICT, FLANK_AMBIGUOUS, collinear_side)
        role_groups = {role_owners[i].equivalence_group for i in ids}
        if len(role_groups) != 1:
            return _stop(7, EvidenceResolutionStatus.CONFLICT, FLANK_AMBIGUOUS, collinear_side)
        groups |= role_groups
        host_owners.update(role_owners)

    if set(host_owners) & set(terminator_owners):
        return _stop(8, EvidenceResolutionStatus.ABSTAINED, TERMINATOR_OVERLAPS_HOST, collinear_side)

    return _Attempt(
        _result(
            EvidenceResolutionStatus.CANDIDATE,
            (CORNER_HOST_CANDIDATE,),
            collinear_side=collinear_side,
            host_member_ids=tuple(sorted(host_owners)),
            host_equivalence_groups=tuple(sorted(groups)),
            terminator_witness_ids=tuple(sorted(terminator_owners)),
            terminator_primitive_ids=tuple(sorted(terminator_prims)),
            mitre_primitive_ids=tuple(sorted(mitre_ids)),
            perpendicular_thickness_pt=round(stagger, 6),
            stagger_pt=round(stagger, 6),
        ),
        9,
    )


def resolve_corner_terminated_stub_host_shadow(
    frame: CornerFrame,
    faces: Sequence[FaceStub],
    drawn: Sequence[DrawnPrimitive],
    are_ambiguous: Callable[[str, str], bool] = lambda first, second: False,
) -> CornerTerminatedHostShadowResult:
    """Pure geometric core. Deterministic, order-invariant, no input mutation."""

    drawn = tuple(sorted(drawn, key=lambda p: (p.primitive_id, p.line)))
    faces = tuple(sorted(faces, key=lambda f: (f.primitive_id, f.line)))
    stubs = _classify_stubs(frame, faces)
    if stubs is None:
        return _result(EvidenceResolutionStatus.ABSTAINED, (FACES_UNSUPPORTED,))
    own_ids = frozenset(f.primitive_id for f in faces)
    attempts = [
        _evaluate(frame, stubs, drawn, own_ids, are_ambiguous, side)
        for side in ("left", "right")
    ]
    positives = [a for a in attempts if a.result.is_candidate]
    if len(positives) == 2:
        return _result(EvidenceResolutionStatus.CONFLICT, (ORIENTATION_AMBIGUOUS,))
    if positives:
        return positives[0].result
    best = max(attempts, key=lambda a: (a.depth, a.result.reason_codes))
    return best.result


# ---------------------------------------------------------------------- adapter

def assess_corner_terminated_host_shadow(
    composition,
    *,
    enabled: bool = False,
) -> tuple[CornerTerminatedHostShadowRecord, ...]:
    """Read-only adapter over an existing ``LiveWallOpeningAuthorityComposition``.

    Returns ``()`` unless ``enabled`` is the boolean ``True``. Reads only
    producer-owned authorities already held by the composition; writes nothing.
    """

    if type(enabled) is not bool:
        raise TypeError("enabled must be a bool")
    if not enabled:
        return ()

    from pb_opening_host_binding_authority import (
        _authenticated_native_source_lines,
        _build_local_boundary_scope_invariant_index,
        _equivalence_group_for,
        _equivalence_group_lookup,
        _line,
        _opening_geometry,
        _pair_lookup,
        _positive_gap_source_pairs,
        _raw_source_primitive_id,
    )
    from pb_physical_opening_authority import JAMB_BOUNDED_TWO_FACE_INTERRUPTION
    from pb_physical_wall_candidate_authority import PhysicalWallCandidateSelector
    from pb_physical_wall_identity import PhysicalEquivalenceClass
    from pb_source_observation_authority import ObservationSelector

    poa = composition.physical_opening_authority
    visibility = poa.source_visibility_authority()
    scope_cache: dict = {}
    records_out: list[CornerTerminatedHostShadowRecord] = []

    def scope_context(selector, opening):
        key = (selector.snapshot_id, selector.page_id, selector.decision_scope_id)
        if key in scope_cache:
            return scope_cache[key]
        scope = composition.physical_wall_candidate_authority.resolve_scope(
            PhysicalWallCandidateSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                page_id=selector.page_id,
                decision_scope_id=selector.decision_scope_id,
            )
        )
        ctx = None
        if not wall_scope_is_owned_by_opening(scope, opening, selector):
            ctx = _OWNERSHIP_MISMATCH
        elif (
            scope.status is EvidenceResolutionStatus.CORROBORATED
            and scope.records
            and scope.equivalence is not None
        ):
            index = _build_local_boundary_scope_invariant_index(scope)
            if index is not None:
                group_lookup = _equivalence_group_lookup(scope.equivalence)
                pairs = _pair_lookup(scope.equivalence)
                ambiguous_value = PhysicalEquivalenceClass.AMBIGUOUS_PHYSICAL_EQUIVALENCE

                def clean(record) -> bool:
                    ident, wall = record.physical_identity, record.wall_candidate
                    return bool(
                        ident.usable
                        and ident.candidate_identity_id
                        and any(str(v).strip() for v in ident.source_primitive_ids)
                        and not wall.is_curved
                        and "non_simple_chain_topology_fallback_ordering" not in wall.reason_codes
                        and record.wall_candidate_id not in index.unsafe_ids
                        and record.wall_candidate_id not in index.unsafe_group_bridge_member_ids
                    )

                owners_by_pid: dict[str, list[OwnerRef]] = {}
                for record in scope.records:
                    ref = OwnerRef(
                        wall_candidate_id=str(record.wall_candidate_id),
                        equivalence_group=tuple(
                            _equivalence_group_for(
                                scope.equivalence, record.wall_candidate_id, group_lookup=group_lookup
                            )
                        ),
                        clean=clean(record),
                        centerline_pts=tuple(
                            (float(p[0]), float(p[1])) for p in record.wall_candidate.centerline_pts
                        ),
                    )
                    for pid in record.physical_identity.source_primitive_ids:
                        owners_by_pid.setdefault(str(pid), []).append(ref)
                lines = _authenticated_native_source_lines(poa, opening, scope.source_observation_ids)
                drawn = tuple(
                    DrawnPrimitive(pid, tuple(float(v) for v in line), tuple(owners_by_pid[pid]))
                    for pid, line in lines.items()
                    if pid in owners_by_pid
                )

                def are_ambiguous(first: str, second: str) -> bool:
                    key2 = tuple(sorted((first, second)))
                    return pairs.get(key2) is ambiguous_value

                ctx = (drawn, are_ambiguous)
        scope_cache[key] = ctx
        return ctx

    for trace in composition.opening_bindings:
        if trace.status is EvidenceResolutionStatus.CORROBORATED:
            continue
        selector = composition.binding_selectors.get(trace.opening_identity_id)
        if selector is None:
            continue
        probe = poa.prove_existence(
            ObservationSelector(
                document_id=selector.document_id,
                revision_id=selector.revision_id,
                source_sha256=selector.source_sha256,
                snapshot_id=selector.snapshot_id,
                observation_id=trace.representative_observation_id,
            )
        )
        opening = probe.existence_record
        if (
            opening is None
            or probe.status is not EvidenceResolutionStatus.CORROBORATED
            or opening.structural_pattern != JAMB_BOUNDED_TWO_FACE_INTERRUPTION
        ):
            continue

        ctx = scope_context(selector, opening)
        geometry = _opening_geometry(poa, opening)
        if ctx is _OWNERSHIP_MISMATCH:
            result = _result(EvidenceResolutionStatus.ABSTAINED, (WALL_SCOPE_OWNERSHIP_MISMATCH,))
        elif ctx is None:
            result = _result(EvidenceResolutionStatus.ABSTAINED, (WALL_SCOPE_UNAVAILABLE,))
        elif geometry is None:
            result = _result(EvidenceResolutionStatus.ABSTAINED, (OPENING_GEOMETRY_UNAVAILABLE,))
        else:
            observations = []
            for oid in opening.source_observation_ids:
                seen = visibility.resolve_visible(
                    ObservationSelector(
                        document_id=opening.document_id,
                        revision_id=opening.revision_id,
                        source_sha256=opening.source_sha256,
                        snapshot_id=opening.snapshot_id,
                        observation_id=oid,
                    )
                )
                if seen.status is EvidenceResolutionStatus.CORROBORATED and seen.observation is not None:
                    observations.append(seen.observation)
            faces = []
            for pair in _positive_gap_source_pairs(observations):
                for record in (pair[0], pair[1]):
                    line = _line(record)
                    pid = _raw_source_primitive_id(record)
                    if line is not None and pid:
                        faces.append(FaceStub(str(pid), tuple(float(v) for v in line)))
            frame = CornerFrame(
                origin=(float(geometry.origin[0]), float(geometry.origin[1])),
                axis=(float(geometry.axis[0]), float(geometry.axis[1])),
                normal=(float(geometry.normal[0]), float(geometry.normal[1])),
                length=float(geometry.length),
                thickness=float(geometry.thickness),
            )
            drawn, are_ambiguous = ctx
            result = resolve_corner_terminated_stub_host_shadow(frame, faces, drawn, are_ambiguous)

        records_out.append(
            CornerTerminatedHostShadowRecord(
                opening_identity_id=str(trace.opening_identity_id),
                page_id=str(trace.page_id),
                binding_status=str(trace.status.value),
                binding_reason_codes=tuple(trace.reason_codes),
                result=result,
                first_remaining_gate=(
                    PROMOTION_GATE if result.is_candidate else (result.reason_codes[0] if result.reason_codes else "unknown")
                ),
            )
        )
    return tuple(sorted(records_out, key=lambda r: r.opening_identity_id))


__all__ = [
    "CONTACT_TOL_PT",
    "CORNER_HOST_CANDIDATE",
    "CORNER_HOST_SHADOW_SCHEMA_VERSION",
    "PROMOTION_GATE",
    "CornerFrame",
    "CornerTerminatedHostShadowRecord",
    "CornerTerminatedHostShadowResult",
    "DrawnPrimitive",
    "FaceStub",
    "OwnerRef",
    "assess_corner_terminated_host_shadow",
    "resolve_corner_terminated_stub_host_shadow",
    "wall_scope_is_owned_by_opening",
]
