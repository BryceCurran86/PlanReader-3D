"""Producer-owned cross-view floor correspondence shadow (Item 14 & 15).

Proves that a figured dimension box on a support drawing (e.g. Page 11 floor-finish plan)
geometrically corresponds to an authenticated physical room/floor on a target drawing
(e.g. Page 7 general arrangement plan) using authenticated wall geometry:

- Purely consumes producer-owned objects or explicit geometry inputs.
- Validates exact document/revision/source/snapshot lineage.
- Derives rigid registration hypotheses from non-grid wall candidate primitives.
- Verifies that the dimension box is wall-bounded on both sheets (face + parallel second face)
  with matching covered intervals and opening void locations.
- Confirms that exactly one finish mark of the queried material code resides inside the box,
  and that no other competing finish marks or overlapping measured boxes conflict.
- Fails closed on periodic ambiguity, alias translations, open-plan spaces, or competing finish codes.
- Diagnostic/shadow only: emits CANDIDATE status for consistent geometric ownership,
  never awards commercial takeoff or modifies frozen truth.
"""
from __future__ import annotations

import bisect
import collections
from dataclasses import dataclass, field
import hashlib
import math
import random
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_visibility_authority import SourceVisibilityProducer


SCHEMA_VERSION = "1.0.0"

# Public Reason Codes
SOURCE_CROSS_VIEW_FLOOR_CORRESPONDENCE_RESOLVED = (
    "source_cross_view_floor_correspondence_resolved"
)
SOURCE_CROSS_VIEW_FLOOR_CORRESPONDENCE_CANDIDATE = (
    "source_cross_view_floor_correspondence_candidate"
)
SOURCE_CROSS_VIEW_FLOOR_CORRESPONDENCE_UNAVAILABLE = (
    "source_cross_view_floor_correspondence_unavailable"
)
SOURCE_CROSS_VIEW_FLOOR_CORRESPONDENCE_CONFLICT = (
    "source_cross_view_floor_correspondence_conflict"
)
REGISTRATION_NOT_UNIQUE = "registration_not_unique"
REGISTRATION_TRANSLATION_ALIAS = "registration_translation_alias"
REGISTRATION_SCALE_NOT_APPLIED = "registration_scale_not_applied_to_floor_box"
BOX_NOT_WALL_BOUNDED = "box_not_wall_bounded_on_both_sheets"
WALL_EVIDENCE_DIFFERS = "wall_evidence_differs_between_sheets"
OVERLAPPING_MEASURED_BOXES = "overlapping_measured_boxes"
DUPLICATE_PHYSICAL_FLOOR_IDENTITY = "duplicate_physical_floor_identity"
MISSING_PHYSICAL_FLOOR_IDENTITY = "missing_physical_floor_identity"
MARK_TOO_CLOSE_TO_BOX_SIDE = "mark_too_close_to_box_side"
MARK_IN_UNREGISTERED_REGION = "mark_in_unregistered_region"
SOURCE_FINISH_MARK_IDENTITY_INVALID = "source_finish_mark_identity_invalid"
SOURCE_FINISH_CODE_SUMMARY_BUDGET_EXCEEDED = "source_finish_code_summary_budget_exceeded"
# Source-only diagnostic output budget, NOT a geometry, raster or quantity cap.
# Full per-box code multiplicities require at least boxes * distinct codes
# entries in the worst case; never attempt a 20k * 20k materialization.
MAX_SOURCE_FINISH_CODE_BOX_SUMMARY_ENTRIES = 250_000
SOURCE_WALL_SEGMENT_UNIVERSE_INVALID = "source_wall_segment_universe_invalid"
SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED = "source_registration_vote_budget_exceeded"
SOURCE_SIDE_EVIDENCE_BUDGET_EXCEEDED = "source_side_evidence_budget_exceeded"
# Diagnostic only: bound the COMPLETE per-box × per-sheet native side search.
# This does not change the 20,000 raster primitive limit or 2.5pt snap.
MAX_SOURCE_SIDE_EVIDENCE_VISITS = 10_000_000
SOURCE_NULL_SUPPORT_TRIALS_INVALID = "source_null_support_trials_invalid"
# Preserve the established 60-trial null comparison; a caller cannot shrink
# the evidence sample or request unbounded source-shadow scoring work.
MIN_SOURCE_NULL_SUPPORT_TRIALS = 60
MAX_SOURCE_NULL_SUPPORT_TRIALS = 1000
# Diagnostic work budgets, not PDF primitive, topology snap or quantity limits.
# Never publish a partial registration if a complete source search is too costly.
MAX_SOURCE_REGISTRATION_VOTE_PAIRS = 250_000
MAX_SOURCE_REGISTRATION_SUPPORT_KEY_VISITS = 10_000_000
SOURCE_MEASURED_FLOOR_BOX_INVALID = "source_measured_floor_box_invalid"
SOURCE_PHYSICAL_FLOOR_IDENTITY_INVALID = "source_physical_floor_identity_invalid"
COMPETING_FINISH_CODES_IN_BOX = "competing_finish_codes_in_box"
MULTIPLE_SAME_CODE_FINISH_MARKS_IN_BOX = "multiple_same_code_finish_marks_in_box"
NO_FINISH_MARK_IN_BOX = "no_finish_mark_in_box"
BOX_OWNED_BY_OTHER_FINISH_CODE = "box_owned_by_other_finish_code"
FLOOR_GEOMETRICALLY_OWNED_EQUIVALENCE_NOT_AUTHENTICATED = (
    "floor_geometrically_owned_equivalence_not_authenticated"
)

# Standard Standing Authority Blockers for Candidate Tier
STANDING_AUTHORITY_BLOCKERS = (
    "support_page_has_no_source_owned_room_face_or_label_authority",
    "no_physical_wall_equivalence_authority_for_box_sides",
)

AXIS_TOL = 0.02
MIN_LEN = 3.0
COORD_TOL = 0.06
WALL_BAND = (3.0, 15.0)
SIDE_FULL = 0.95
SIDE_PARTIAL = 0.50

D4 = {
    "identity": (1.0, 0.0, 0.0, 1.0),
    "rot90": (0.0, -1.0, 1.0, 0.0),
    "rot180": (-1.0, 0.0, 0.0, -1.0),
    "rot270": (0.0, 1.0, -1.0, 0.0),
    "mirror_x": (-1.0, 0.0, 0.0, 1.0),
    "mirror_y": (1.0, 0.0, 0.0, -1.0),
    "transpose": (0.0, 1.0, 1.0, 0.0),
    "anti_transpose": (0.0, -1.0, -1.0, 0.0),
}

Lines = dict  # {"H": {coord: [(lo, hi), ...]}, "V": {...}}


def _native_source_identity(value: Any) -> tuple[str, bool]:
    """Keep an original physical/source ID verbatim; never coerce its type.

    A missing ID is already an object-local abstention. A supplied but
    malformed ID makes the complete measured-owner universe untrustworthy.
    """
    if value is None or (type(value) is str and value == ""):
        return "", False
    if type(value) is str and value == value.strip() and value.isprintable():
        return value, False
    return "", True


def _valid_source_wall_segment_universe(segments: Any) -> bool:
    """Require a complete bounded native wall-segment universe on each sheet.

    A malformed or omitted competing wall must never be silently dropped
    before rigid registration can claim a unique physical floor. Keep this
    source-only validation separate from the existing 2.5pt topology snap.
    """
    if type(segments) not in (list, tuple) or len(segments) > 20_000:
        return False
    for segment in segments:
        if not isinstance(segment, Mapping):
            return False
        for field_name in ("x1", "y1", "x2", "y2"):
            raw = segment.get(field_name)
            if type(raw) not in (int, float):
                return False
            # Beyond the exact binary64 integer range, a native PDF point
            # coordinate cannot retain reliable source endpoint identity.
            if abs(raw) > 2**53:
                return False
            try:
                value = float(raw)
            except (ValueError, OverflowError):
                return False
            if not math.isfinite(value):
                return False
    return True


def merge_intervals(intervals: Iterable[Sequence[float]]) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for lo, hi in sorted((float(a), float(b)) for a, b in intervals):
        if out and lo <= out[-1][1] + 1e-6:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return [(a, b) for a, b in out]


def build_lines(segments: Iterable[Mapping[str, float]], *, min_len: float = MIN_LEN) -> Lines:
    raw: dict[str, dict[float, list[tuple[float, float]]]] = {
        "H": collections.defaultdict(list),
        "V": collections.defaultdict(list),
    }
    for s in segments:
        x1, y1, x2, y2 = float(s["x1"]), float(s["y1"]), float(s["x2"]), float(s["y2"])
        if math.hypot(x2 - x1, y2 - y1) < min_len:
            continue
        if abs(y2 - y1) < AXIS_TOL:
            raw["H"][round(y1, 2)].append((min(x1, x2), max(x1, x2)))
        elif abs(x2 - x1) < AXIS_TOL:
            raw["V"][round(x1, 2)].append((min(y1, y2), max(y1, y2)))
    return {o: {k: merge_intervals(v) for k, v in raw[o].items()} for o in "HV"}


def orient_lines(lines: Lines, mat: Sequence[float]) -> Lines:
    a, b, c, d = (float(v) for v in mat)
    out: dict[str, dict[float, list[tuple[float, float]]]] = {
        "H": collections.defaultdict(list),
        "V": collections.defaultdict(list),
    }
    for o in "HV":
        for k, ivs in lines[o].items():
            for lo, hi in ivs:
                p = [(lo, k), (hi, k)] if o == "H" else [(k, lo), (k, hi)]
                (x1, y1), (x2, y2) = [(a * x + b * y, c * x + d * y) for x, y in p]
                if abs(y2 - y1) < 1e-6:
                    out["H"][round(y1, 3)].append((min(x1, x2), max(x1, x2)))
                else:
                    out["V"][round(x1, 3)].append((min(y1, y2), max(y1, y2)))
    return {o: {k: merge_intervals(v) for k, v in out[o].items()} for o in "HV"}


def _overlap(a: Sequence[tuple[float, float]], b: Sequence[tuple[float, float]]) -> float:
    i = j = 0
    total = 0.0
    while i < len(a) and j < len(b):
        lo, hi = max(a[i][0], b[j][0]), min(a[i][1], b[j][1])
        if hi > lo:
            total += hi - lo
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return total


class LineIndex:
    def __init__(self, lines: Lines):
        self.lines = lines
        self.keys = {o: sorted(lines[o]) for o in "HV"}

    def near(self, orient: str, coord: float, tol: float) -> list[float]:
        keys = self.keys[orient]
        i = bisect.bisect_left(keys, coord - tol)
        out = []
        while i < len(keys) and keys[i] <= coord + tol:
            out.append(keys[i])
            i += 1
        return out


def axis_support(
    src: Lines, dst: LineIndex, orient: str, dx: float, dy: float,
    tol: float = COORD_TOL, *, _visit_budget: Optional[list[int]] = None,
) -> float:
    shift_c, shift_a = (dy, dx) if orient == "H" else (dx, dy)
    total = 0.0
    for k, ivs in src[orient].items():
        # A near-key count alone does not bound the two-pointer overlap scan:
        # one native line key can hold thousands of disjoint source intervals.
        # Account for constructing shifted intervals before doing that work.
        if _visit_budget is not None:
            _visit_budget[0] += len(ivs)
            if _visit_budget[0] > MAX_SOURCE_REGISTRATION_SUPPORT_KEY_VISITS:
                raise ValueError(SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED)
        shifted = [(lo + shift_a, hi + shift_a) for lo, hi in ivs]
        nearby = dst.near(orient, k + shift_c, tol)
        if _visit_budget is not None:
            _visit_budget[0] += len(nearby)
            if _visit_budget[0] > MAX_SOURCE_REGISTRATION_SUPPORT_KEY_VISITS:
                raise ValueError(SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED)
        for k2 in nearby:
            target_intervals = dst.lines[orient][k2]
            # _overlap runs in O(len(source) + len(target)) per matched
            # native key. Conservatively meter both interval lists BEFORE
            # scanning, cumulatively across registration and null trials.
            if _visit_budget is not None:
                _visit_budget[0] += len(shifted) + len(target_intervals)
                if _visit_budget[0] > MAX_SOURCE_REGISTRATION_SUPPORT_KEY_VISITS:
                    raise ValueError(SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED)
            total += _overlap(shifted, target_intervals)
    return total


def min_axis_support(
    src: Lines, dst: LineIndex, dx: float, dy: float,
    tol: float = COORD_TOL, *, _visit_budget: Optional[list[int]] = None,
) -> tuple[float, float, float]:
    h = axis_support(src, dst, "H", dx, dy, tol, _visit_budget=_visit_budget)
    v = axis_support(src, dst, "V", dx, dy, tol, _visit_budget=_visit_budget)
    return min(h, v), h, v


def _shift_votes(src: Lines, dst: LineIndex, topn: int, limit: float = 3000.0) -> tuple[list[float], list[float]]:
    """Complete bounded shift voting; never choose a winner from partial votes.

    The old all-keys Cartesian scan admitted 20k * 20k source/target
    comparisons per orientation. Sorted destination windows exclude keys
    outside the exact shift limit, and a preflight bounds all candidate
    visits BEFORE any vote can be accumulated.
    """
    windows: dict[str, list[tuple[float, list[tuple[float, float]], int, int]]] = {
        "H": [], "V": [],
    }
    visits = 0
    for o in "HV":
        keys = dst.keys[o]
        for k, ivs in src[o].items():
            # Expand one ULP to preserve the original abs(k2-k) <= limit
            # predicate at floating-point subtraction boundaries.
            lo = bisect.bisect_left(keys, math.nextafter(k - limit, -math.inf))
            hi = bisect.bisect_right(keys, math.nextafter(k + limit, math.inf))
            visits += hi - lo
            if visits > MAX_SOURCE_REGISTRATION_VOTE_PAIRS:
                raise ValueError(SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED)
            windows[o].append((k, ivs, lo, hi))
    votes = {"H": collections.Counter(), "V": collections.Counter()}
    for o in "HV":
        keys = dst.keys[o]
        dst_lengths = {
            k2: sum(hi - lo for lo, hi in dst.lines[o][k2])
            for k2 in keys
        }
        for k, ivs, lo, hi in windows[o]:
            t_src = sum(end - start for start, end in ivs)
            for k2 in keys[lo:hi]:
                d = k2 - k
                if abs(d) > limit:
                    continue
                votes[o][round(d / 0.04) * 0.04] += min(t_src, dst_lengths[k2])
    xs = [x for x, _ in sorted(votes["V"].items(), key=lambda kv: (-kv[1], kv[0]))[:topn]]
    ys = [y for y, _ in sorted(votes["H"].items(), key=lambda kv: (-kv[1], kv[0]))[:topn]]
    return xs, ys


def rank_registrations(
    src: Lines,
    dst: Lines,
    *,
    orientations: Mapping[str, Sequence[float]] = D4,
    identity_scales: Sequence[float] = (0.5, 0.75, 1.0, 1.25, 2.0),
    topn: int = 30,
    tol: float = COORD_TOL,
    identity_only: bool = False,
) -> list[dict[str, Any]]:
    index = LineIndex(dst)
    rows: list[dict[str, Any]] = []
    support_key_visits = 0
    actual_key_visits = [0]
    for name, mat in orientations.items():
        if identity_only and name != "identity":
            continue
        scales = identity_scales if name == "identity" and not identity_only else (1.0,)
        for scale in scales:
            moved = orient_lines(src, tuple(scale * v for v in mat))
            xs, ys = _shift_votes(moved, index, topn)
            if not xs or not ys:
                continue
            # Bound the subsequent complete Cartesian translation scoring
            # and local refinement, not just the shift-vote candidate search.
            support_key_visits += (
                (len(xs) * len(ys) + 3 * 25)
                * (len(moved["H"]) + len(moved["V"]))
            )
            if support_key_visits > MAX_SOURCE_REGISTRATION_SUPPORT_KEY_VISITS:
                raise ValueError(SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED)
            pool = sorted(
                ((*min_axis_support(moved, index, dx, dy, tol, _visit_budget=actual_key_visits), dx, dy) for dx in xs for dy in ys),
                key=lambda r: (-r[0], r[3], r[4]),
            )
            if not pool:
                continue
            best = pool[0]
            # The refined winner is NOT the only locally refined source
            # hypothesis. A distinct rival may improve from weak shift-vote
            # support to near-equal wall overlap in the same refinement
            # window. Retain every evaluated refinement when testing unique
            # translation ownership; comparing only the unrefined pool can
            # falsely certify a floor/finish mark as uniquely registered.
            evaluated = list(pool)
            for s, h, v, dx, dy in pool[:3]:
                for ddx in (-0.08, -0.04, 0.0, 0.04, 0.08):
                    for ddy in (-0.08, -0.04, 0.0, 0.04, 0.08):
                        s2, h2, v2 = min_axis_support(
                            moved, index, dx + ddx, dy + ddy, tol,
                            _visit_budget=actual_key_visits,
                        )
                        candidate = (s2, h2, v2, dx + ddx, dy + ddy)
                        evaluated.append(candidate)
                        if s2 > best[0] + 1e-9:
                            best = candidate
            second = next((
                p for p in sorted(evaluated, key=lambda r: (-r[0], r[3], r[4]))
                if abs(p[3] - best[3]) > 1.0 or abs(p[4] - best[4]) > 1.0
            ), None)
            rows.append({
                "orientation": name,
                "scale": scale,
                "dx": round(best[3], 2),
                "dy": round(best[4], 2),
                "min_support_pt": round(best[0], 1),
                "h_support_pt": round(best[1], 1),
                "v_support_pt": round(best[2], 1),
                "next_distinct_translation": None if second is None else [round(second[3], 2), round(second[4], 2)],
                "next_distinct_min_support_pt": None if second is None else round(second[0], 1),
            })
    rows.sort(key=lambda r: (-r["min_support_pt"], r["orientation"], r["scale"]))
    return rows


def null_support(
    src: Lines,
    dst: Lines,
    *,
    trials: int = 100,
    seed: int = 20261014,
    span: tuple[float, float] = (1500.0, 2000.0),
) -> dict[str, float]:
    rng = random.Random(seed)
    index = LineIndex(dst)
    actual_key_visits = [0]
    vals = sorted(
        min_axis_support(
            src, index, rng.uniform(-span[0], span[0]),
            rng.uniform(-span[1], span[1]),
            _visit_budget=actual_key_visits,
        )[0]
        for _ in range(trials)
    )
    return {
        "max": vals[-1],
        "p99": vals[int(0.99 * (len(vals) - 1))],
        "median": vals[len(vals) // 2],
    }


def side_evidence(
    box: Sequence[float],
    lines: Lines,
    *,
    tol: float = COORD_TOL,
    band: tuple[float, float] = WALL_BAND,
    _index: Optional[LineIndex] = None,
    _visit_budget: Optional[list[int]] = None,
) -> dict[str, dict[str, Any]]:
    x0, y0, x1, y1 = (float(v) for v in box)
    # Producer-owned reuse: one sorted-key index per immutable sheet, not a
    # fresh 20k-key sort for every measured floor side. Reject a mismatched
    # caller index rather than comparing wall evidence from another sheet.
    if _index is not None and (
        type(_index) is not LineIndex or _index.lines is not lines
    ):
        raise ValueError("source_line_index_does_not_match_sheet")
    index = LineIndex(lines) if _index is None else _index
    out: dict[str, dict[str, Any]] = {}
    for name, orient, coord, lo, hi, sign in (
        ("x0", "V", x0, y0, y1, -1),
        ("x1", "V", x1, y0, y1, 1),
        ("y0", "H", y0, x0, x1, -1),
        ("y1", "H", y1, x0, x1, 1),
    ):
        length = hi - lo
        near_keys = index.near(orient, coord, tol)
        if _visit_budget is not None:
            # Meter every inspected native interval before the merge/sort;
            # a bounded key universe can still contain many disjoint spans.
            _visit_budget[0] += len(near_keys) + sum(
                len(lines[orient][k]) for k in near_keys
            )
            if _visit_budget[0] > MAX_SOURCE_SIDE_EVIDENCE_VISITS:
                raise ValueError(SOURCE_SIDE_EVIDENCE_BUDGET_EXCEEDED)
        covered = merge_intervals(
            (max(a, lo), min(b, hi))
            for k in near_keys
            for a, b in lines[orient][k]
            if min(b, hi) > max(a, lo)
        )
        cov = sum(b - a for a, b in covered) / length if length > 0 else 0.0
        second = []
        second_intervals = []
        # The outward paired wall face must lie within the signed thickness
        # band.  A complete 20k-key native line universe cannot be scanned
        # for every side of every measured floor box.  Search only sorted
        # keys in the inclusive outward band; preserve the original signed
        # predicate and inspect EVERY key in that band (never nearest/first).
        low = coord + sign * band[0]
        high = coord + sign * band[1]
        keys = index.keys[orient]
        # Expand the binary-search window by two representable neighbours.
        # This conservatively covers addition/subtraction rounding at exact
        # band boundaries; the predicate below remains the source of truth.
        lower = min(low, high)
        upper = max(low, high)
        for _ in range(2):
            lower = math.nextafter(lower, -math.inf)
            upper = math.nextafter(upper, math.inf)
        first = bisect.bisect_left(keys, lower)
        last = bisect.bisect_right(keys, upper)
        outward_keys = keys[first:last]
        if _visit_budget is not None:
            _visit_budget[0] += len(outward_keys) + sum(
                len(lines[orient][k]) for k in outward_keys
            )
            if _visit_budget[0] > MAX_SOURCE_SIDE_EVIDENCE_VISITS:
                raise ValueError(SOURCE_SIDE_EVIDENCE_BUDGET_EXCEEDED)
        for k in outward_keys:
            signed = (k - coord) * sign
            # A measured floor uses the room-facing wall face; its paired
            # wall face must lie outward, not across the room interior.
            if band[0] <= signed <= band[1]:
                outer_covered = merge_intervals(
                    (max(a, lo), min(b, hi))
                    for a, b in lines[orient][k]
                    if min(b, hi) > max(a, lo)
                )
                c2 = sum(b - a for a, b in outer_covered) / length if length > 0 else 0.0
                if c2 >= SIDE_PARTIAL:
                    offset = round(signed, 2)
                    second.append((offset, round(c2, 3)))
                    second_intervals.append((
                        offset,
                        [(round(a, 2), round(b, 2)) for a, b in outer_covered],
                    ))
        out[name] = {
            "coordinate": round(coord, 3),
            "face_coverage": round(cov, 4),
            "covered_intervals": [(round(a, 2), round(b, 2)) for a, b in covered],
            "second_face": second,
            "second_face_intervals": second_intervals,
        }
    return out


def interval_iou(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> Optional[float]:
    inter = _overlap(merge_intervals(a), merge_intervals(b))
    union = sum(hi - lo for lo, hi in merge_intervals(a)) + sum(hi - lo for lo, hi in merge_intervals(b)) - inter
    return None if union <= 0 else inter / union


def matching_outward_second_faces(
    support: Mapping[str, Any],
    target: Mapping[str, Any],
    *,
    shift: float,
) -> bool:
    """Require the complete outward-face offset and void pattern on both sheets.

    Merely finding *some* parallel stroke on each sheet cannot prove that the
    same physical wall thickness or second-face openings were observed.
    Retain all candidate offsets; missing, extra or different faces abstain.
    """
    src_faces = sorted(support["second_face_intervals"], key=lambda row: row[0])
    dst_faces = sorted(target["second_face_intervals"], key=lambda row: row[0])
    if not src_faces or len(src_faces) != len(dst_faces):
        return False
    for (src_offset, src_ivs), (dst_offset, dst_ivs) in zip(src_faces, dst_faces):
        if abs(src_offset - dst_offset) > COORD_TOL:
            return False
        unshifted = [(lo - shift, hi - shift) for lo, hi in dst_ivs]
        iou = interval_iou(src_ivs, unshifted)
        if iou is None or iou < 0.98:
            return False
    return True


def translate_box(
    box: Sequence[float],
    orientation: str,
    translation: Sequence[float],
) -> tuple[float, float, float, float]:
    a, b, c, d = D4[orientation]
    pts = [(box[0], box[1]), (box[2], box[1]), (box[0], box[3]), (box[2], box[3])]
    q = [(a * x + b * y + translation[0], c * x + d * y + translation[1]) for x, y in pts]
    xs, ys = [p[0] for p in q], [p[1] for p in q]
    return (min(xs), min(ys), max(xs), max(ys))


def box_correspondence(
    box_support: Sequence[float],
    *,
    lines_support: Lines,
    lines_target: Lines,
    orientation: str,
    translation: Sequence[float],
    _support_index: Optional[LineIndex] = None,
    _target_index: Optional[LineIndex] = None,
    _visit_budget: Optional[list[int]] = None,
) -> dict[str, Any]:
    box_target = translate_box(box_support, orientation, translation)
    sup = side_evidence(
        box_support, lines_support, _index=_support_index,
        _visit_budget=_visit_budget,
    )
    tgt = side_evidence(
        box_target, lines_target, _index=_target_index,
        _visit_budget=_visit_budget,
    )
    sides: dict[str, Any] = {}
    for name in sup:
        tgt_name = name
        shift = translation[1] if name in ("x0", "x1") else translation[0]
        t_iv = [(a - shift, b - shift) for a, b in tgt[tgt_name]["covered_intervals"]]
        outward_faces_match = (
            orientation == "identity"
            and matching_outward_second_faces(sup[name], tgt[tgt_name], shift=shift)
        )
        sides[name] = {
            "support_sheet": sup[name],
            "target_sheet": tgt[tgt_name],
            "outward_second_faces_match": outward_faces_match,
            "covered_interval_iou": (
                interval_iou(sup[name]["covered_intervals"], t_iv)
                if orientation == "identity"
                else None
            ),
            "wall_side": (
                "full"
                if min(sup[name]["face_coverage"], tgt[tgt_name]["face_coverage"]) >= SIDE_FULL
                and sup[name]["second_face"]
                and tgt[tgt_name]["second_face"]
                else "with_openings"
                if min(sup[name]["face_coverage"], tgt[tgt_name]["face_coverage"]) >= SIDE_PARTIAL
                and sup[name]["second_face"]
                and tgt[tgt_name]["second_face"]
                else "not_wall"
            ),
        }
    kinds = [s["wall_side"] for s in sides.values()]
    ious = [s["covered_interval_iou"] for s in sides.values() if s["covered_interval_iou"] is not None]
    bounded = all(k != "not_wall" for k in kinds)
    identical = (
        bool(ious)
        and all(i is not None and i >= 0.98 for i in ious)
        and all(s["outward_second_faces_match"] for s in sides.values())
    )
    return {
        "box_support_sheet": tuple(round(v, 3) for v in box_support),
        "box_target_sheet": tuple(round(v, 3) for v in box_target),
        "sides": sides,
        "wall_bounded_on_both_sheets": bounded,
        "wall_evidence_identical_on_both_sheets": identical,
        "side_kinds": dict(zip(sup, kinds)),
    }


def classify_floor(
    correspondence: Mapping[str, Any],
    *,
    registration_unique: bool,
    marks_inside: Sequence[Mapping[str, Any]],
    other_labelled_boxes_overlapping: int,
    material_code: str,
    identity_ambiguous: bool = False,
    identity_missing: bool = False,
    min_margin_pt: float = 5.0,
    authority_blockers: Sequence[str] = STANDING_AUTHORITY_BLOCKERS,
) -> dict[str, Any]:
    # A caller's glyph/mark receipt is not a typed source identity merely
    # because a matching finish code can be read from another mark.  Reject
    # malformed or unbounded mark universes before counting any candidates.
    if type(marks_inside) not in (tuple, list) or len(marks_inside) > 20000:
        return {
            "status": EvidenceResolutionStatus.ABSTAINED,
            "reason_codes": (SOURCE_FINISH_MARK_IDENTITY_INVALID,),
            "finish_codes_in_box": {},
            "authority_blockers": (),
            "authenticated_physical_wall_face_equivalence": False,
        }
    reasons: list[str] = []
    codes: collections.Counter[str] = collections.Counter()
    invalid_mark_identity = False
    for mark in marks_inside:
        if not isinstance(mark, Mapping):
            invalid_mark_identity = True
            continue
        code = mark.get("code")
        if type(code) is not str or not code or code != code.strip():
            invalid_mark_identity = True
            continue
        codes[code] += 1
    if invalid_mark_identity:
        reasons.append(SOURCE_FINISH_MARK_IDENTITY_INVALID)
    if registration_unique is not True:
        reasons.append(REGISTRATION_NOT_UNIQUE)
    if correspondence["wall_bounded_on_both_sheets"] is not True:
        reasons.append(BOX_NOT_WALL_BOUNDED)
    elif correspondence["wall_evidence_identical_on_both_sheets"] is not True:
        reasons.append(WALL_EVIDENCE_DIFFERS)
    if other_labelled_boxes_overlapping:
        reasons.append(OVERLAPPING_MEASURED_BOXES)
    # Source-face / physical-room / canonical-floor identifiers are a
    # one-to-one claim for this shadow correspondence. Repeating an identity
    # across distinct measured boxes cannot authenticate either owner.
    if identity_ambiguous is not False:
        reasons.append(DUPLICATE_PHYSICAL_FLOOR_IDENTITY)
    if identity_missing is not False:
        reasons.append(MISSING_PHYSICAL_FLOOR_IDENTITY)
    # A missing, malformed, overflowing or non-finite mark margin is not a
    # positive source containment receipt. Never let NaN bypass comparison.
    try:
        minimum = float(min_margin_pt) if type(min_margin_pt) in (int, float) else math.nan
    except (ValueError, OverflowError):
        minimum = math.nan

    def valid_margin(mark: Mapping[str, Any]) -> bool:
        if not isinstance(mark, Mapping):
            return False
        raw = mark.get("margin_pt")
        if type(raw) not in (int, float):
            return False
        try:
            margin = float(raw)
        except (ValueError, OverflowError):
            return False
        return math.isfinite(margin) and margin >= minimum

    if (
        not math.isfinite(minimum)
        or minimum < 0
        or any(not valid_margin(mark) for mark in marks_inside)
    ):
        reasons.append(MARK_TOO_CLOSE_TO_BOX_SIDE)
    # Registration is an explicit source fact, not a truthy caller hint.
    if any(not isinstance(mark, Mapping)
           or mark.get("registered_region") is not True for mark in marks_inside):
        reasons.append(MARK_IN_UNREGISTERED_REGION)

    if len(codes) > 1:
        status = EvidenceResolutionStatus.CONFLICT
        reasons.append(COMPETING_FINISH_CODES_IN_BOX)
    elif not codes:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons.append(NO_FINISH_MARK_IN_BOX)
    elif type(material_code) is not str or material_code not in codes:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons.append(BOX_OWNED_BY_OTHER_FINISH_CODE)
    elif sum(codes.values()) != 1:
        # Repeated same-code marks can belong to different physical finish
        # regions. One dimension box cannot choose an owner by code alone.
        status = EvidenceResolutionStatus.ABSTAINED
        reasons.append(MULTIPLE_SAME_CODE_FINISH_MARKS_IN_BOX)
    elif reasons:
        status = EvidenceResolutionStatus.ABSTAINED
    else:
        status = EvidenceResolutionStatus.CANDIDATE
        reasons = [FLOOR_GEOMETRICALLY_OWNED_EQUIVALENCE_NOT_AUTHENTICATED]

    return {
        "status": status,
        "reason_codes": tuple(reasons),
        "finish_codes_in_box": dict(codes),
        "authority_blockers": tuple(authority_blockers) if status == EvidenceResolutionStatus.CANDIDATE else (),
        "authenticated_physical_wall_face_equivalence": False,
    }


@dataclass(frozen=True)
class SourceCrossViewFloorCorrespondenceSelector:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    support_page_id: str
    target_page_id: str
    material_code: str

    def __post_init__(self) -> None:
        for field_name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "support_page_id",
            "target_page_id",
            "material_code",
        ):
            val = getattr(self, field_name)
            if type(val) is not str or not val.strip():
                raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True)
class SourceCrossViewFloorCorrespondenceRecord:
    record_id: str
    canonical_floor_id: str
    physical_room_id: str
    source_room_face_record_id: str
    support_page_id: str
    target_page_id: str
    support_dimension_box_pdf_pts: tuple[float, float, float, float]
    target_box_pdf_pts: tuple[float, float, float, float]
    registration_orientation: str
    registration_scale: float
    registration_translation_pdf_pts: tuple[float, float]
    registration_support_pt: float
    registration_runner_up_support_pt: float
    registration_null_support_pt: float
    wall_bounded_on_both_sheets: bool
    wall_evidence_identical_on_both_sheets: bool
    side_kinds: Mapping[str, str]
    finish_codes_in_box: Mapping[str, int]
    material_code: str
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    authority_blockers: tuple[str, ...] = STANDING_AUTHORITY_BLOCKERS
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False


@dataclass(frozen=True)
class SourceCrossViewFloorCorrespondenceResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    records: tuple[SourceCrossViewFloorCorrespondenceRecord, ...]
    winning_registration: Optional[dict[str, Any]] = None
    all_competing_registrations: tuple[dict[str, Any], ...] = ()



def _overlapping_measured_box_flags(
    boxes: Sequence[tuple[float, float, float, float]],
) -> list[bool]:
    """Flag every strictly positive-area overlap without enumerating pairs.

    The caller has already validated all box coordinates and bounds. Sweep
    increasing left x, expiring rectangles whose right x only touches the
    incoming left edge. Two compressed-y interval indexes retain all active
    boxes and only the active boxes not yet known to overlap. Each previously
    unmarked box is removed from the second index at most once, so even 20k
    identical overlapping boxes remain O(n log n), not O(n squared).

    The result is only a veto, never a chosen physical owner.
    """
    if not boxes:
        return []
    import heapq

    y_coords = sorted({y for box in boxes for y in (box[1], box[3])})
    y_index = {y: i for i, y in enumerate(y_coords)}
    y_ranges = [(y_index[b[1]], y_index[b[3]] - 1) for b in boxes]
    y_cells = len(y_coords) - 1

    class _ActiveY:
        def __init__(self) -> None:
            self.subtree_counts = [0] * (4 * y_cells + 4)
            self.owners: dict[int, set[int]] = {}

        def update(self, item: int, delta: int) -> None:
            left, right = y_ranges[item]

            def visit(node: int, lo: int, hi: int) -> None:
                self.subtree_counts[node] += delta
                if left <= lo and hi <= right:
                    if delta > 0:
                        self.owners.setdefault(node, set()).add(item)
                    else:
                        bucket = self.owners[node]
                        bucket.remove(item)
                        if not bucket:
                            del self.owners[node]
                    return
                mid = (lo + hi) // 2
                if left <= mid:
                    visit(node * 2, lo, mid)
                if right > mid:
                    visit(node * 2 + 1, mid + 1, hi)

            visit(1, 0, y_cells - 1)

        def find_overlap(self, item: int) -> Optional[int]:
            left, right = y_ranges[item]

            def visit(node: int, lo: int, hi: int) -> Optional[int]:
                if right < lo or hi < left or not self.subtree_counts[node]:
                    return None
                bucket = self.owners.get(node)
                if bucket:
                    return next(iter(bucket))
                if lo == hi:
                    return None
                mid = (lo + hi) // 2
                if left <= mid:
                    match = visit(node * 2, lo, mid)
                    if match is not None:
                        return match
                if right > mid:
                    return visit(node * 2 + 1, mid + 1, hi)
                return None

            return visit(1, 0, y_cells - 1)

    active = _ActiveY()
    unmarked = _ActiveY()
    marked = [False] * len(boxes)
    expirations: list[tuple[float, int]] = []
    order = sorted(
        range(len(boxes)),
        key=lambda i: (boxes[i][0], boxes[i][2], boxes[i][1], boxes[i][3], i),
    )
    for i in order:
        x0, _, x1, _ = boxes[i]
        while expirations and expirations[0][0] <= x0:
            _, old = heapq.heappop(expirations)
            active.update(old, -1)
            if not marked[old]:
                unmarked.update(old, -1)

        if active.find_overlap(i) is not None:
            marked[i] = True
            # Mark every previously unmarked overlapping rectangle, but
            # never revisit it once marked. Already-marked boxes remain in
            # the complete active index to veto future overlaps.
            while (old := unmarked.find_overlap(i)) is not None:
                marked[old] = True
                unmarked.update(old, -1)

        active.update(i, 1)
        if not marked[i]:
            unmarked.update(i, 1)
        heapq.heappush(expirations, (x1, i))
    return marked



def _finish_code_summary_exceeds_budget(
    checked_marks: Sequence[tuple[float, float, Mapping[str, Any]]],
    box_count: int,
) -> bool:
    """Bound possible complete per-box code counts before Fenwick allocation.

    A huge distinct-code universe cannot be faithfully materialized for every
    box within a bounded source-shadow memory budget. This is a diagnostic
    availability veto, not evidence that any material or room is absent.
    """
    if box_count <= 0:
        return False
    distinct = {
        mark.get("code")
        for _, _, mark in checked_marks
        if type(mark.get("code")) is str
        and bool(mark.get("code"))
        and mark.get("code") == mark.get("code").strip()
    }
    return box_count * len(distinct) > MAX_SOURCE_FINISH_CODE_BOX_SUMMARY_ENTRIES


def _indexed_marks_in_boxes(
    checked_marks: Sequence[tuple[float, float, Mapping[str, Any]]],
    boxes: Sequence[tuple[float, float, float, float]],
) -> list[tuple[list[dict[str, Any]], dict[str, int]]]:
    """Lossless classifier-predicate summary of *all* marks in each closed box.

    Offline x sweep and y Fenwick aggregates avoid O(boxes * marks) scanning.
    Each returned synthetic classifier input represents complete source counts,
    malformed codes, unregistered marks and exact five-point margin failures.
    The synthetic inputs are NOT new source receipts or measurement authority.
    The separately returned code counts preserve every source occurrence.
    """
    if not boxes:
        return []
    if not checked_marks:
        return [([], {}) for _ in boxes]
    if _finish_code_summary_exceeds_budget(checked_marks, len(boxes)):
        raise ValueError(SOURCE_FINISH_CODE_SUMMARY_BUDGET_EXCEEDED)

    xs = sorted({x for x, _, _ in checked_marks})
    ys = sorted({y for _, y, _ in checked_marks})
    y_of = {y: i + 1 for i, y in enumerate(ys)}
    tree: list[collections.Counter[tuple[str, str]]] = [
        collections.Counter() for _ in range(len(ys) + 1)
    ]
    totals = [0] * (len(ys) + 1)
    # x, phase (0 before marks, 1 add mark, 2 after marks),
    # source index, outer/inner query, sign, inclusive y-low/high indices.
    events: list[tuple[float, int, int, int, int, int, int]] = []
    outer = [collections.Counter() for _ in boxes]
    inner = [0] * len(boxes)

    def margin_limits(coords: list[float], low: float, high: float) -> tuple[float, float] | None:
        # Binary search the ORIGINAL subtraction predicate. Computing
        # low+5 or high-5 can round across a fractional native-PDF boundary.
        lo, hi = 0, len(coords)
        while lo < hi:
            mid = (lo + hi) // 2
            if coords[mid] - low >= 5.0:
                hi = mid
            else:
                lo = mid + 1
        first = lo
        lo, hi = 0, len(coords)
        while lo < hi:
            mid = (lo + hi) // 2
            if high - coords[mid] >= 5.0:
                lo = mid + 1
            else:
                hi = mid
        last = lo - 1
        return (coords[first], coords[last]) if first <= last and first < len(coords) else None

    def add_rectangle(index: int, kind: int, rect: tuple[float, float, float, float]) -> None:
        x0, y0, x1, y1 = rect
        y_low = bisect.bisect_left(ys, y0) + 1
        y_high = bisect.bisect_right(ys, y1)
        if x0 > x1 or y_low > y_high:
            return
        events.append((x0, 0, index, kind, -1, y_low, y_high))
        events.append((x1, 2, index, kind, 1, y_low, y_high))

    for index, (x0, y0, x1, y1) in enumerate(boxes):
        add_rectangle(index, 0, (x0, y0, x1, y1))
        x_bounds = margin_limits(xs, x0, x1)
        y_bounds = margin_limits(ys, y0, y1)
        if x_bounds is not None and y_bounds is not None:
            add_rectangle(index, 1, (*x_bounds[:1], *y_bounds[:1], *x_bounds[1:], *y_bounds[1:]))
    for index, (x, _, _) in enumerate(checked_marks):
        events.append((x, 1, index, 0, 0, 0, 0))

    def prefix(index: int, owner: collections.Counter | None, sign: int) -> int:
        count = 0
        while index:
            count += totals[index]
            if owner is not None:
                for key, value in tree[index].items():
                    owner[key] += sign * value
            index -= index & -index
        return count

    for _, phase, index, kind, sign, y_low, y_high in sorted(events):
        if phase == 1:
            _, y, mark = checked_marks[index]
            code = mark.get("code")
            valid = type(code) is str and bool(code) and code == code.strip()
            keys = [("code", code)] if valid else [("invalid", "")]
            if mark.get("registered_region") is not True:
                keys.append(("unregistered", ""))
            pos = y_of[y]
            while pos < len(totals):
                totals[pos] += 1
                for key in keys:
                    tree[pos][key] += 1
                pos += pos & -pos
        else:
            owner = outer[index] if kind == 0 else None
            count = (
                prefix(y_high, owner, sign)
                - prefix(y_low - 1, owner, -sign)
            )
            if kind == 0:
                outer[index][("total", "")] += sign * count
            else:
                inner[index] += sign * count

    summaries: list[tuple[list[dict[str, Any]], dict[str, int]]] = []
    for index, (x0, y0, x1, y1) in enumerate(boxes):
        counts = {
            code: count
            for (kind, code), count in outer[index].items()
            if kind == "code" and count > 0
        }
        invalid = outer[index][("invalid", "")] > 0
        unregistered = outer[index][("unregistered", "")] > 0
        total = outer[index][("total", "")]
        # Non-finite width is not a valid finite native margin; conservative
        # abstention prevents a giant finite-coordinate box granting authority.
        bad_margin = (
            total != inner[index]
            or not math.isfinite(x1 - x0)
            or not math.isfinite(y1 - y0)
        )
        # Preserve every decision predicate without materializing potentially
        # 400m box/mark pairs. classify_floor still decides CONFLICT/ABSTAIN.
        compressed = [
            {"code": code, "margin_pt": 5.0, "registered_region": True}
            for code in sorted(counts)
        ]
        repeated = next((code for code in sorted(counts) if counts[code] > 1), None)
        if repeated is not None:
            compressed.append({"code": repeated, "margin_pt": 5.0, "registered_region": True})
        if invalid:
            compressed.append({"code": None, "margin_pt": 5.0, "registered_region": True})
        if compressed:
            if bad_margin:
                compressed[0]["margin_pt"] = 0.0
            if unregistered:
                compressed[0]["registered_region"] = False
        summaries.append((compressed, counts))
    return summaries


class SourceCrossViewFloorCorrespondenceProducer:
    """Producer-owned shadow authority for cross-sheet plan correspondence."""

    def __init__(self, source: Optional[SourceVisibilityProducer] = None) -> None:
        if source is not None and type(source) is not SourceVisibilityProducer:
            raise TypeError("source must be an instance of SourceVisibilityProducer")
        self._source = source

    @classmethod
    def from_source_visibility_producer(
        cls, source: SourceVisibilityProducer
    ) -> "SourceCrossViewFloorCorrespondenceProducer":
        return cls(source)

    def evaluate_synthetic(
        self,
        *,
        selector: SourceCrossViewFloorCorrespondenceSelector,
        support_segments: Sequence[Mapping[str, float]],
        target_segments: Sequence[Mapping[str, float]],
        measured_boxes: Sequence[dict[str, Any]],
        marks: Sequence[dict[str, Any]],
        trials: int = 60,
    ) -> SourceCrossViewFloorCorrespondenceResult:
        """Pure geometric evaluation using in-memory segments and boxes."""
        # A caller-controlled null sample must not weaken the existing 60-trial
        # registration gate, crash on an empty sample, or consume unbounded work.
        # Validate it independently of malformed source inputs so all typed
        # negatives remain visible when several gates fail together.
        invalid_null_trials = (
            type(trials) is not int
            or not MIN_SOURCE_NULL_SUPPORT_TRIALS <= trials <= MAX_SOURCE_NULL_SUPPORT_TRIALS
        )
        # Validate the complete mark universe BEFORE spatial filtering. An
        # unlocatable or untyped original mark may occupy any measured box;
        # dropping it would falsely make a surviving FT2/FT3 mark unique.
        if type(marks) not in (tuple, list) or len(marks) > 20000:
            return SourceCrossViewFloorCorrespondenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(
                    SOURCE_FINISH_MARK_IDENTITY_INVALID,
                    *([SOURCE_NULL_SUPPORT_TRIALS_INVALID] if invalid_null_trials else []),
                ),
                records=(),
            )
        checked_marks: list[tuple[float, float, Mapping[str, Any]]] = []
        invalid_mark_universe = False
        for mark in marks:
            if not isinstance(mark, Mapping):
                invalid_mark_universe = True
                continue
            raw_x, raw_y = mark.get("x"), mark.get("y")
            if type(raw_x) not in (int, float) or type(raw_y) not in (int, float):
                invalid_mark_universe = True
                continue
            # Native PDF coordinates above the exact binary64 integer range
            # can alias distinct source marks during float conversion. Apply
            # the same lossless source-coordinate limit as wall and box input.
            if abs(raw_x) > 2**53 or abs(raw_y) > 2**53:
                invalid_mark_universe = True
                continue
            try:
                mx, my = float(raw_x), float(raw_y)
            except (ValueError, OverflowError):
                invalid_mark_universe = True
                continue
            if not (math.isfinite(mx) and math.isfinite(my)):
                invalid_mark_universe = True
                continue
            code = mark.get("code")
            if type(code) is not str or not code or code != code.strip():
                invalid_mark_universe = True
            # Preserve invalid codes with known coordinates so classify_floor
            # can retain the original competing mark as a typed negative.
            checked_marks.append((mx, my, mark))

        # Inspect the COMPLETE measured-box universe before registration.
        # A malformed competing room could overlap a valid FT mark, so
        # dropping it must never leave a surviving source-owner candidate.
        if type(measured_boxes) not in (tuple, list) or len(measured_boxes) > 20000:
            # A malformed box container must not erase independently observed
            # source negatives. No box can be selected from this universe.
            reasons = []
            if (
                not _valid_source_wall_segment_universe(support_segments)
                or not _valid_source_wall_segment_universe(target_segments)
            ):
                reasons.append(SOURCE_WALL_SEGMENT_UNIVERSE_INVALID)
            if invalid_mark_universe:
                reasons.append(SOURCE_FINISH_MARK_IDENTITY_INVALID)
            reasons.append(SOURCE_MEASURED_FLOOR_BOX_INVALID)
            if invalid_null_trials:
                reasons.append(SOURCE_NULL_SUPPORT_TRIALS_INVALID)
            return SourceCrossViewFloorCorrespondenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=tuple(reasons),
                records=(),
            )
        checked_boxes: list[tuple[dict[str, Any], tuple[float, float, float, float]]] = []
        invalid_box_universe = False
        for item in measured_boxes:
            if type(item) is not dict:
                invalid_box_universe = True
                continue
            raw_box = item.get("dimension_box_pdf_pts")
            if type(raw_box) not in (tuple, list) or len(raw_box) != 4:
                invalid_box_universe = True
                continue
            if any(
                type(v) not in (int, float)
                # Apply the same exact-coordinate bound to native floats
                # and integers. Oversized floats can alias PDF endpoints.
                or abs(v) > 2**53
                for v in raw_box
            ):
                invalid_box_universe = True
                continue
            try:
                box = tuple(float(v) for v in raw_box)
            except (ValueError, OverflowError):
                invalid_box_universe = True
                continue
            if not all(math.isfinite(v) for v in box):
                invalid_box_universe = True
                continue
            if box[0] >= box[2] or box[1] >= box[3]:
                invalid_box_universe = True
                continue
            checked_boxes.append((item, box))
        # Collect independent typed negatives BEFORE any early return.
        # A wholly invalid box universe must not hide malformed finish marks
        # or a competing native wall on either sheet.
        invalid_wall_universe = (
            not _valid_source_wall_segment_universe(support_segments)
            or not _valid_source_wall_segment_universe(target_segments)
        )
        summary_over_budget = _finish_code_summary_exceeds_budget(
            checked_marks, len(checked_boxes)
        )
        if (
            invalid_wall_universe
            or summary_over_budget
            or invalid_null_trials
            or (invalid_box_universe and not checked_boxes)
        ):
            reasons = []
            if invalid_wall_universe:
                reasons.append(SOURCE_WALL_SEGMENT_UNIVERSE_INVALID)
            if summary_over_budget:
                reasons.append(SOURCE_FINISH_CODE_SUMMARY_BUDGET_EXCEEDED)
            if invalid_mark_universe:
                reasons.append(SOURCE_FINISH_MARK_IDENTITY_INVALID)
            if invalid_box_universe:
                reasons.append(SOURCE_MEASURED_FLOOR_BOX_INVALID)
            if invalid_null_trials:
                reasons.append(SOURCE_NULL_SUPPORT_TRIALS_INVALID)
            return SourceCrossViewFloorCorrespondenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=tuple(reasons),
                records=(),
            )

        lines_sup = build_lines(support_segments)
        lines_tgt = build_lines(target_segments)

        try:
            ranked = rank_registrations(lines_sup, lines_tgt)
        except ValueError as exc:
            if str(exc) != SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED:
                raise
            reasons = [SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED]
            if invalid_mark_universe:
                reasons.append(SOURCE_FINISH_MARK_IDENTITY_INVALID)
            if invalid_box_universe:
                reasons.append(SOURCE_MEASURED_FLOOR_BOX_INVALID)
            return SourceCrossViewFloorCorrespondenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=tuple(reasons),
                records=(),
            )
        if not ranked:
            return SourceCrossViewFloorCorrespondenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=tuple(dict.fromkeys((
                    REGISTRATION_NOT_UNIQUE,
                    *([SOURCE_FINISH_MARK_IDENTITY_INVALID]
                      if invalid_mark_universe else []),
                    *([SOURCE_MEASURED_FLOOR_BOX_INVALID]
                      if invalid_box_universe else []),
                ))),
                records=(),
            )

        top = ranked[0]
        try:
            null_res = null_support(lines_sup, lines_tgt, trials=trials)
        except ValueError as exc:
            if str(exc) != SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED:
                raise
            reasons = [SOURCE_REGISTRATION_VOTE_BUDGET_EXCEEDED]
            if invalid_mark_universe:
                reasons.append(SOURCE_FINISH_MARK_IDENTITY_INVALID)
            if invalid_box_universe:
                reasons.append(SOURCE_MEASURED_FLOOR_BOX_INVALID)
            return SourceCrossViewFloorCorrespondenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=tuple(reasons),
                records=(),
            )
        runner_up = ranked[1]["min_support_pt"] if len(ranked) > 1 else 0.0
        # A single orientation/scale may contain several distinct translations.
        # The second translation is not ranked[1]. Require separation from
        # that rival before assigning physical floor correspondence.
        same_transform_alias = top.get("next_distinct_min_support_pt")
        if same_transform_alias is None:
            translation_unique = True
        else:
            try:
                alias_support = (
                    float(same_transform_alias)
                    if type(same_transform_alias) in (int, float)
                    else math.nan
                )
            except (ValueError, OverflowError):
                alias_support = math.nan
            translation_unique = (
                math.isfinite(alias_support)
                and alias_support >= 0.0
                and top["min_support_pt"] > 1.25 * alias_support
            )

        # Rigorous unique registration gate:
        # 1. Top support must exceed null hypothesis max by at least 10x.
        # 2. Top support must exceed runner up by at least 1.5x (unless zero competitors).
        # Registration search can propose a non-unit scale, but
        # box_correspondence/translate_box only transform orientation and
        # translation. Until the measured box and its source-wall intervals
        # are scale-transformed and independently authenticated, that winner
        # must not establish a physical floor owner.
        scale_applied = top["scale"] == 1.0
        is_unique = (
            scale_applied
            and translation_unique
            and top["min_support_pt"] > 10.0 * max(null_res["max"], 1e-6)
            and (len(ranked) == 1 or top["min_support_pt"] >= 1.5 * runner_up)
        )

        records: list[SourceCrossViewFloorCorrespondenceRecord] = []
        overall_status = (
            EvidenceResolutionStatus.CANDIDATE
            if is_unique
            else EvidenceResolutionStatus.ABSTAINED
        )
        overall_reasons = [] if is_unique else [
            REGISTRATION_SCALE_NOT_APPLIED
            if not scale_applied else
            REGISTRATION_TRANSLATION_ALIAS
            if not translation_unique else REGISTRATION_NOT_UNIQUE
        ]

        # Derive overlapping measured-floor regions from the full input
        # universe; a missing caller hint cannot confer unique mark ownership.
        overlap_flags = _overlapping_measured_box_flags(
            [box for _, box in checked_boxes]
        )

        # Index all original mark occurrences once. A dense source universe
        # must not require up to 400m repeated box/mark containment checks.
        indexed_marks = _indexed_marks_in_boxes(
            checked_marks, [box for _, box in checked_boxes]
        )

        # Derive identity collisions from the *entire* measured-box universe,
        # not from caller hints or spatial overlap alone. Two disjoint boxes
        # may still assert one physical floor, room face or canonical floor.
        identity_fields = (
            "canonical_floor_id", "physical_room_id",
            "source_room_face_record_id",
        )
        native_identities = [
            {
                field_name: _native_source_identity(item.get(field_name))
                for field_name in identity_fields
            }
            for item, _ in checked_boxes
        ]
        # A malformed rival can conceal a physical identity collision. Keep
        # all diagnostic rows, but never let another valid-looking row become
        # a unique source-owner candidate from that incomplete ID universe.
        invalid_identity_universe = any(
            malformed
            for identities in native_identities
            for _, malformed in identities.values()
        )
        identity_counts = collections.Counter(
            (field_name, value)
            for identities in native_identities
            for field_name, (value, _) in identities.items()
            if value
        )

        # Registration and null-support use their own complete indexes.
        # Physical-side checks reuse exactly one index per authenticated
        # sheet for the entire measured-box universe, with no cross-sheet
        # identity substitution and no changed geometric predicate.
        support_side_index = LineIndex(lines_sup)
        target_side_index = LineIndex(lines_tgt)
        # One cumulative budget across BOTH sheets and EVERY measured box.
        # Exhaustion discards partial records rather than publishing an
        # incomplete source correspondence universe as a candidate.
        side_evidence_visits = [0]
        for box_index, (item, box_sup) in enumerate(checked_boxes):
            identities = native_identities[box_index]
            canonical_floor_id = identities["canonical_floor_id"][0]
            physical_room_id = identities["physical_room_id"][0]
            source_room_face_record_id = identities["source_room_face_record_id"][0]

            try:
                corr = box_correspondence(
                    box_sup,
                    lines_support=lines_sup,
                    lines_target=lines_tgt,
                    orientation=top["orientation"],
                    translation=(top["dx"], top["dy"]),
                    _support_index=support_side_index,
                    _target_index=target_side_index,
                    _visit_budget=side_evidence_visits,
                )
            except ValueError as exc:
                if str(exc) != SOURCE_SIDE_EVIDENCE_BUDGET_EXCEEDED:
                    raise
                reasons = [SOURCE_SIDE_EVIDENCE_BUDGET_EXCEEDED]
                if invalid_mark_universe:
                    reasons.append(SOURCE_FINISH_MARK_IDENTITY_INVALID)
                if invalid_box_universe:
                    reasons.append(SOURCE_MEASURED_FLOOR_BOX_INVALID)
                if invalid_identity_universe:
                    reasons.append(SOURCE_PHYSICAL_FLOOR_IDENTITY_INVALID)
                return SourceCrossViewFloorCorrespondenceResult(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=tuple(reasons),
                    records=(),
                )

            # Complete source counts and all negative predicates are retained
            # without expanding the same marks across overlapping boxes.
            inside_marks, exact_code_counts = indexed_marks[box_index]
            classified = classify_floor(
                corr,
                registration_unique=is_unique,
                marks_inside=inside_marks,
                other_labelled_boxes_overlapping=(
                    item.get("other_labelled_boxes_overlapping", 0)
                    or overlap_flags[box_index]
                ),
                material_code=selector.material_code,
                identity_missing=not all((
                    canonical_floor_id, physical_room_id,
                    source_room_face_record_id,
                )),
                identity_ambiguous=any(
                    identity_counts[(field_name, value)] > 1
                    for field_name, value in (
                        ("canonical_floor_id", canonical_floor_id),
                        ("physical_room_id", physical_room_id),
                        ("source_room_face_record_id", source_room_face_record_id),
                    )
                    if value
                ),
            )
            # The compressed classifier input is decision-equivalent, while
            # the published diagnostic retains exact source-code multiplicity.
            classified["finish_codes_in_box"] = exact_code_counts

            # A malformed or unlocatable rival cannot be silently filtered
            # away to make a surviving mark uniquely authoritative. Keep
            # genuine FT2/FT3 conflicts while withholding all candidates.
            if invalid_mark_universe:
                classified["reason_codes"] = tuple(dict.fromkeys((
                    *classified["reason_codes"],
                    SOURCE_FINISH_MARK_IDENTITY_INVALID,
                )))
                if classified["status"] is EvidenceResolutionStatus.CANDIDATE:
                    classified["status"] = EvidenceResolutionStatus.ABSTAINED
                    classified["authority_blockers"] = ()

            # An unlocated or malformed sibling box may own a mark or
            # overlap this room. Keep valid diagnostic rows, but veto all
            # physical-owner candidates from an incomplete source universe.
            if invalid_box_universe:
                classified["reason_codes"] = tuple(dict.fromkeys((
                    *classified["reason_codes"],
                    SOURCE_MEASURED_FLOOR_BOX_INVALID,
                )))
                if classified["status"] is EvidenceResolutionStatus.CANDIDATE:
                    classified["status"] = EvidenceResolutionStatus.ABSTAINED
                    classified["authority_blockers"] = ()

            if invalid_identity_universe:
                classified["reason_codes"] = tuple(dict.fromkeys((
                    *classified["reason_codes"],
                    SOURCE_PHYSICAL_FLOOR_IDENTITY_INVALID,
                )))
                if classified["status"] is EvidenceResolutionStatus.CANDIDATE:
                    classified["status"] = EvidenceResolutionStatus.ABSTAINED
                    classified["authority_blockers"] = ()

            # Preserve competing-code CONFLICT and every negative; retain
            # both the transform and distinct-translation alias vetoes.
            extra_reasons = (
                ([REGISTRATION_SCALE_NOT_APPLIED] if not scale_applied else [])
                + ([REGISTRATION_TRANSLATION_ALIAS] if not translation_unique else [])
            )
            if extra_reasons:
                classified["reason_codes"] = tuple(dict.fromkeys((
                    *classified["reason_codes"], *extra_reasons,
                )))

            record_id = stable_contract_id(
                "source_cross_view_floor_correspondence_record",
                {
                    "selector": {
                        "document_id": selector.document_id,
                        "revision_id": selector.revision_id,
                        "source_sha256": selector.source_sha256,
                        "snapshot_id": selector.snapshot_id,
                        "support_page_id": selector.support_page_id,
                        "target_page_id": selector.target_page_id,
                        "material_code": selector.material_code,
                    },
                    "canonical_floor_id": canonical_floor_id,
                    "physical_room_id": physical_room_id,
                    "source_room_face_record_id": source_room_face_record_id,
                    "box_support": box_sup,
                    "box_target": corr["box_target_sheet"],
                },
            )

            rec = SourceCrossViewFloorCorrespondenceRecord(
                record_id=record_id,
                canonical_floor_id=canonical_floor_id,
                physical_room_id=physical_room_id,
                source_room_face_record_id=source_room_face_record_id,
                support_page_id=selector.support_page_id,
                target_page_id=selector.target_page_id,
                support_dimension_box_pdf_pts=corr["box_support_sheet"],
                target_box_pdf_pts=corr["box_target_sheet"],
                registration_orientation=top["orientation"],
                registration_scale=top["scale"],
                registration_translation_pdf_pts=(top["dx"], top["dy"]),
                registration_support_pt=top["min_support_pt"],
                registration_runner_up_support_pt=runner_up,
                registration_null_support_pt=null_res["max"],
                wall_bounded_on_both_sheets=corr["wall_bounded_on_both_sheets"],
                wall_evidence_identical_on_both_sheets=corr["wall_evidence_identical_on_both_sheets"],
                side_kinds=MappingProxyType(corr["side_kinds"]),
                finish_codes_in_box=MappingProxyType(classified["finish_codes_in_box"]),
                material_code=selector.material_code,
                status=classified["status"],
                reason_codes=classified["reason_codes"],
                authority_blockers=classified["authority_blockers"],
                commercial_projection_allowed=False,
                takeoff_eligible=False,
            )
            records.append(rec)

        # Registration alone is not a floor-finish correspondence. If every
        # measured floor abstains (or one is in conflict), the aggregate must
        # not advertise CANDIDATE while carrying zero candidate floor owners.
        # Keep each source mark and its typed negative for later inspection.
        if any(row.status is EvidenceResolutionStatus.CONFLICT for row in records):
            overall_status = EvidenceResolutionStatus.CONFLICT
        elif not any(row.status is EvidenceResolutionStatus.CANDIDATE for row in records):
            overall_status = EvidenceResolutionStatus.ABSTAINED
        if overall_status is not EvidenceResolutionStatus.CANDIDATE:
            overall_reasons = list(dict.fromkeys((
                *overall_reasons,
                *(reason for row in records for reason in row.reason_codes),
            )))
            if not overall_reasons:
                overall_reasons = [SOURCE_CROSS_VIEW_FLOOR_CORRESPONDENCE_UNAVAILABLE]

        return SourceCrossViewFloorCorrespondenceResult(
            status=overall_status,
            reason_codes=tuple(overall_reasons),
            records=tuple(records),
            winning_registration=top,
            all_competing_registrations=tuple(ranked),
        )
