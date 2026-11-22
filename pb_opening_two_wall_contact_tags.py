"""Read-only source-native opening ↔ TWO traced wall SECTION tags.

An opening interrupts two wall sections; at a corner or wall junction those
sections need not be collinear. This maps independently witnessed native wall
ends to opening contacts. It never elects a whole-wall commercial host, joins
the physical walls, creates a door void, supplies a width, or issues a quantity.
The caller must source-authenticate the native PDF/trace and pass the SAME
document/revision/snapshot/page scope for all inputs.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from collections.abc import Mapping, Sequence
from typing import Any

# Original PDF native endpoint reproduction tolerance, NOT a generic wall snap.
_SOURCE_ENDPOINT_TOL_PT = 0.18


@dataclass(frozen=True)
class TracedWallSection:
    section_id: str
    scope: tuple[str, ...]
    native_path_ids: tuple[int, ...]
    start_pdf_pts: tuple[float, float]
    end_pdf_pts: tuple[float, float]


@dataclass(frozen=True)
class OpeningWallContact:
    position_pdf_pts: tuple[float, float]
    wall_end_native_path_ids: tuple[int, ...]


@dataclass(frozen=True)
class DetectedOpeningContacts:
    opening_id: str
    scope: tuple[str, ...]
    opening_native_path_ids: tuple[int, ...]
    first: OpeningWallContact
    second: OpeningWallContact


@dataclass(frozen=True)
class TwoWallOpeningTag:
    opening_id: str
    status: str
    reason: str
    wall_section_ids: tuple[str, ...] = ()
    contact_geometry: str = "UNRESOLVED"
    candidate_sections_first: tuple[str, ...] = ()
    candidate_sections_second: tuple[str, ...] = ()
    source_topology_only: bool = True
    physical_host_authorized: bool = False
    measurement_authorized: bool = False


def _point(value: object) -> tuple[float, float] | None:
    if type(value) is not tuple or len(value) != 2:
        return None
    if any(type(v) not in (int, float) for v in value):
        return None
    point = float(value[0]), float(value[1])
    return point if all(math.isfinite(v) for v in point) else None


def _ids(value: object) -> bool:
    return (
        type(value) is tuple and bool(value)
        and all(type(x) is int and x >= 0 for x in value)
        and len(value) == len(set(value))
    )


def _scope(value: object) -> bool:
    return (
        type(value) is tuple and len(value) >= 2
        and all(type(v) is str and bool(v.strip()) for v in value)
    )


def _vector_at_contact(
    wall: TracedWallSection, contact: tuple[float, float],
) -> tuple[float, float] | None:
    a = _point(wall.start_pdf_pts)
    b = _point(wall.end_pdf_pts)
    if a is None or b is None:
        return None
    if math.dist(a, b) <= _SOURCE_ENDPOINT_TOL_PT:
        return None
    # A real native wall endpoint, not nearest midpoint or unlimited snap.
    if math.dist(a, contact) <= _SOURCE_ENDPOINT_TOL_PT:
        vec = b[0] - a[0], b[1] - a[1]
    elif math.dist(b, contact) <= _SOURCE_ENDPOINT_TOL_PT:
        vec = a[0] - b[0], a[1] - b[1]
    else:
        return None
    # Finite original points can still overflow when subtracted; an infinite
    # direction is not a legitimate wall and must never create a two-wall tag.
    return vec if all(math.isfinite(v) for v in vec) else None


def tag_opening_to_two_wall_sections(
    opening: DetectedOpeningContacts,
    traced_sections: Sequence[TracedWallSection],
) -> TwoWallOpeningTag:
    """Associate exactly two source-corroborated wall sections, not one host.

    An opening at a true corner may have coincident contact points and
    noncollinear wall sections. Both native wall provenance and the actual
    wall endpoints must match; source-path intersection alone is insufficient.
    """
    oid = getattr(opening, "opening_id", "")
    if type(oid) is not str or not oid.strip():
        return TwoWallOpeningTag("", "UNRESOLVED", "opening_identity_missing")
    def blocked(reason: str, first: tuple[str, ...] = (), second: tuple[str, ...] = ()):
        return TwoWallOpeningTag(
            oid, "UNRESOLVED", reason,
            candidate_sections_first=first, candidate_sections_second=second,
        )
    if (not isinstance(opening, DetectedOpeningContacts)
            or not _scope(opening.scope)
            or not _ids(opening.opening_native_path_ids)
            or not isinstance(opening.first, OpeningWallContact)
            or not isinstance(opening.second, OpeningWallContact)
            or not _ids(opening.first.wall_end_native_path_ids)
            or not _ids(opening.second.wall_end_native_path_ids)):
        return blocked("source_opening_contact_receipt_invalid")
    first_pt = _point(opening.first.position_pdf_pts)
    second_pt = _point(opening.second.position_pdf_pts)
    if first_pt is None or second_pt is None:
        return blocked("opening_contact_geometry_invalid")
    if type(traced_sections) not in (list, tuple):
        return blocked("traced_wall_sections_invalid")
    ids: set[str] = set()
    first: list[TracedWallSection] = []
    second: list[TracedWallSection] = []
    for wall in traced_sections:
        if (not isinstance(wall, TracedWallSection)
                or type(wall.section_id) is not str or not wall.section_id.strip()
                or not _scope(wall.scope)
                or not _ids(wall.native_path_ids)
                or _point(wall.start_pdf_pts) is None
                or _point(wall.end_pdf_pts) is None):
            return blocked("traced_wall_section_receipt_invalid")
        if wall.section_id in ids:
            return blocked("duplicate_traced_wall_section_identity")
        ids.add(wall.section_id)
        if wall.scope != opening.scope:
            continue
        source_paths = set(wall.native_path_ids)
        if (source_paths.intersection(opening.first.wall_end_native_path_ids)
                and _vector_at_contact(wall, first_pt) is not None):
            first.append(wall)
        if (source_paths.intersection(opening.second.wall_end_native_path_ids)
                and _vector_at_contact(wall, second_pt) is not None):
            second.append(wall)
    first_ids = tuple(sorted(w.section_id for w in first))
    second_ids = tuple(sorted(w.section_id for w in second))
    if not first or not second:
        return blocked("two_source_wall_end_contacts_required", first_ids, second_ids)
    if len(first) != 1 or len(second) != 1:
        return blocked("competing_traced_wall_sections", first_ids, second_ids)
    if first[0].section_id == second[0].section_id:
        return blocked("one_wall_section_cannot_supply_two_sides", first_ids, second_ids)
    va = _vector_at_contact(first[0], first_pt)
    vb = _vector_at_contact(second[0], second_pt)
    assert va is not None and vb is not None
    na = math.hypot(*va)
    nb = math.hypot(*vb)
    if not all(math.isfinite(v) for v in (na, nb)) or min(na, nb) <= 0:
        return blocked("wall_direction_invalid", first_ids, second_ids)
    # Normalized cross product avoids intermediate overflow for very large
    # but finite vector coordinates; the source's real geometry still decides.
    ua = va[0] / na, va[1] / na
    ub = vb[0] / nb, vb[1] / nb
    cross = abs(ua[0] * ub[1] - ua[1] * ub[0])
    angular = cross > math.sin(math.radians(5))
    gap = (second_pt[0] - first_pt[0], second_pt[1] - first_pt[1])
    gap_length = math.hypot(*gap)
    if not math.isfinite(gap_length):
        return blocked("opening_contact_geometry_invalid", first_ids, second_ids)
    joined = gap_length <= _SOURCE_ENDPOINT_TOL_PT
    if joined and not angular:
        return blocked("coincident_collinear_contact_not_an_opening", first_ids, second_ids)
    if not angular:
        gap_x, gap_y = (gap[0] / gap_length, gap[1] / gap_length)
        # For a straight aperture both wall ends must run away from its gap.
        # A native endpoint inside a wall that continues through the aperture
        # is not a valid contact for that aperture.
        if ua[0] * gap_x + ua[1] * gap_y >= 0 or ub[0] * gap_x + ub[1] * gap_y <= 0:
            return blocked("straight_wall_section_runs_into_opening", first_ids, second_ids)
    shape = ("WALL_JUNCTION" if joined else
             "ANGLED_OPENING" if angular else "STRAIGHT_GAP")
    return TwoWallOpeningTag(
        oid, "TWO_WALL_SECTIONS_TAGGED", "source_wall_ends_and_opening_contacts_match",
        (first[0].section_id, second[0].section_id),
        shape, first_ids, second_ids,
    )


def tag_native_segmented_doorway_chords(
    drawings: Sequence[Mapping[str, Any] | None],
    chords: Sequence[Mapping[str, Any]],
    *,
    scope: tuple[str, ...],
) -> tuple[TwoWallOpeningTag, ...]:
    """Read-only adapter for already-proposed original segmented-swing chords.

    Uses the original stroke indices in each *side's wall-end proof*. Existing
    dark-line geometry and opening detection are not rerun or modified.
    """
    tags: list[TwoWallOpeningTag] = []
    if not _scope(scope):
        return ()
    for number, chord in enumerate(chords):
        try:
            horizontal = chord["horizontal"]
            lo, hi = tuple(chord["door_interval_pdf_pts"])
            band_lo, band_hi = tuple(chord["wall_band_pdf_pts"])
            left = tuple(chord["source_wall_end_left_path_indices"])
            right = tuple(chord["source_wall_end_right_path_indices"])
            source_opening = tuple(chord["source_swing_native_path_indices"])
            # Source receipts must be actual native numeric measurements.
            # float(True) and float("10") would silently launder an
            # unverified source value into a valid-looking wall contact.
            values = (lo, hi, band_lo, band_hi)
            if (type(horizontal) is not bool
                    or not all(type(x) in (int, float) and math.isfinite(x)
                               for x in values)
                    or lo > hi or band_lo > band_hi
                    or not _ids(left) or not _ids(right)
                    or not _ids(source_opening)):
                raise ValueError("invalid chord")
        except (KeyError, TypeError, ValueError, OverflowError):
            tags.append(TwoWallOpeningTag(str(number), "UNRESOLVED", "source_chord_receipt_invalid"))
            continue

        def candidates(path_ids: tuple[int, ...], coordinate: float):
            walls: list[TracedWallSection] = []
            contacts: list[tuple[float, float]] = []
            for native in path_ids:
                if type(native) is not int or native < 0 or native >= len(drawings):
                    continue
                row = drawings[native]
                if not isinstance(row, Mapping) or row.get("fill") is not None:
                    continue
                segments = row.get("items", ())
                if not isinstance(segments, (tuple, list)) or len(segments) != 1:
                    continue
                segment = segments[0]
                if (not isinstance(segment, (tuple, list))
                        or len(segment) != 3 or segment[0] != "l"):
                    continue
                try:
                    a, b = segment[1:3]
                    p = (float(a.x), float(a.y))
                    q = (float(b.x), float(b.y))
                except (TypeError, ValueError, AttributeError, OverflowError):
                    continue
                if not all(math.isfinite(v) for v in (*p, *q)):
                    continue
                axis = 0 if horizontal else 1
                across = 1 - axis
                options = [z for z in (p, q)
                           if abs(z[axis] - coordinate) <= _SOURCE_ENDPOINT_TOL_PT
                           and band_lo - 3 <= z[across] <= band_hi + 3]
                if len(options) != 1:
                    continue
                walls.append(TracedWallSection(
                    "native-wall-end:" + str(native), scope, (native,), p, q,
                ))
                contacts.append(options[0])
            return walls, contacts

        left_walls, left_contacts = candidates(left, float(lo))
        right_walls, right_contacts = candidates(right, float(hi))
        # Multiple qualifying contacts stay competing; never nearest/first.
        if len(left_contacts) != 1 or len(right_contacts) != 1:
            tags.append(TwoWallOpeningTag(
                str(number), "UNRESOLVED", "source_wall_end_contact_ambiguous",
                candidate_sections_first=tuple(x.section_id for x in left_walls),
                candidate_sections_second=tuple(x.section_id for x in right_walls),
            ))
            continue
        receipt = DetectedOpeningContacts(
            str(number), scope, source_opening,
            OpeningWallContact(left_contacts[0], left),
            OpeningWallContact(right_contacts[0], right),
        )
        tags.append(tag_opening_to_two_wall_sections(
            receipt, (*left_walls, *right_walls),
        ))
    return tuple(tags)
