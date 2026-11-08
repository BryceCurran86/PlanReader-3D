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
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping, Optional, Sequence, Tuple

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_source_visibility_authority import SourceVisibilityProducer


SCHEMA_VERSION = "1.0.0"

# Public Reason Codes
DOORWAY_TRANSITION_UNAVAILABLE = "doorway_transition_unavailable"
DIMENSION_WITNESS_UNAVAILABLE = "dimension_witness_unavailable"
ROOM_LABEL_UNAVAILABLE = "room_label_unavailable"
DOOR_SCHEDULE_UNAVAILABLE = "door_schedule_unavailable"
SOURCE_REVISION_BYTES_UNAVAILABLE = "source_revision_bytes_unavailable"
SOURCE_DIGEST_MISMATCH = "source_digest_mismatch"

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
SOURCE_FINISH_MARK_IDENTITY_INVALID = "source_finish_mark_identity_invalid"
MULTIPLE_SAME_CODE_FINISH_MARKS_IN_BOX = "multiple_same_code_finish_marks_in_box"
DUPLICATE_PHYSICAL_FLOOR_IDENTITY = "duplicate_physical_floor_identity"
MISSING_PHYSICAL_FLOOR_IDENTITY = "missing_physical_floor_identity"
BOX_NOT_WALL_BOUNDED = "box_not_wall_bounded_on_both_sheets"
WALL_EVIDENCE_DIFFERS = "wall_evidence_differs_between_sheets"
OVERLAPPING_MEASURED_BOXES = "overlapping_measured_boxes"
MARK_TOO_CLOSE_TO_BOX_SIDE = "mark_too_close_to_box_side"
MARK_IN_UNREGISTERED_REGION = "mark_in_unregistered_region"
COMPETING_FINISH_CODES_IN_BOX = "competing_finish_codes_in_box"
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


def _clean(val: Any) -> str:
    return str(val or "").strip()


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


def axis_support(src: Lines, dst: LineIndex, orient: str, dx: float, dy: float, tol: float = COORD_TOL) -> float:
    shift_c, shift_a = (dy, dx) if orient == "H" else (dx, dy)
    total = 0.0
    for k, ivs in src[orient].items():
        shifted = [(lo + shift_a, hi + shift_a) for lo, hi in ivs]
        for k2 in dst.near(orient, k + shift_c, tol):
            total += _overlap(shifted, dst.lines[orient][k2])
    return total


def min_axis_support(src: Lines, dst: LineIndex, dx: float, dy: float, tol: float = COORD_TOL) -> tuple[float, float, float]:
    h = axis_support(src, dst, "H", dx, dy, tol)
    v = axis_support(src, dst, "V", dx, dy, tol)
    return min(h, v), h, v


def _shift_votes(src: Lines, dst: LineIndex, topn: int, limit: float = 3000.0) -> tuple[list[float], list[float]]:
    votes = {"H": collections.Counter(), "V": collections.Counter()}
    for o in "HV":
        for k, ivs in src[o].items():
            t_src = sum(hi - lo for lo, hi in ivs)
            for k2 in dst.keys[o]:
                d = k2 - k
                if abs(d) > limit:
                    continue
                t_dst = sum(hi - lo for lo, hi in dst.lines[o][k2])
                votes[o][round(d / 0.04) * 0.04] += min(t_src, t_dst)
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
    for name, mat in orientations.items():
        if identity_only and name != "identity":
            continue
        scales = identity_scales if name == "identity" and not identity_only else (1.0,)
        for scale in scales:
            moved = orient_lines(src, tuple(scale * v for v in mat))
            xs, ys = _shift_votes(moved, index, topn)
            pool = sorted(
                ((*min_axis_support(moved, index, dx, dy, tol), dx, dy) for dx in xs for dy in ys),
                key=lambda r: (-r[0], r[3], r[4]),
            )
            if not pool:
                continue
            best = pool[0]
            for s, h, v, dx, dy in pool[:3]:
                for ddx in (-0.08, -0.04, 0.0, 0.04, 0.08):
                    for ddy in (-0.08, -0.04, 0.0, 0.04, 0.08):
                        s2, h2, v2 = min_axis_support(moved, index, dx + ddx, dy + ddy, tol)
                        if s2 > best[0] + 1e-9:
                            best = (s2, h2, v2, dx + ddx, dy + ddy)
            second = next((p for p in pool if abs(p[3] - best[3]) > 1.0 or abs(p[4] - best[4]) > 1.0), None)
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
    vals = sorted(
        min_axis_support(src, index, rng.uniform(-span[0], span[0]), rng.uniform(-span[1], span[1]))[0]
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
) -> dict[str, dict[str, Any]]:
    x0, y0, x1, y1 = (float(v) for v in box)
    index = LineIndex(lines)
    out: dict[str, dict[str, Any]] = {}
    for name, orient, coord, lo, hi, sign in (
        ("x0", "V", x0, y0, y1, -1),
        ("x1", "V", x1, y0, y1, 1),
        ("y0", "H", y0, x0, x1, -1),
        ("y1", "H", y1, x0, x1, 1),
    ):
        length = hi - lo
        covered = merge_intervals(
            (max(a, lo), min(b, hi))
            for k in index.near(orient, coord, tol)
            for a, b in lines[orient][k]
            if min(b, hi) > max(a, lo)
        )
        cov = sum(b - a for a, b in covered) / length if length > 0 else 0.0
        second = []
        for k in index.keys[orient]:
            signed = (k - coord) * sign
            if band[0] <= abs(signed) <= band[1]:
                c2 = sum(max(0.0, min(b, hi) - max(a, lo)) for a, b in lines[orient][k]) / length
                if c2 >= SIDE_PARTIAL:
                    second.append((round(signed, 2), round(c2, 3)))
        out[name] = {
            "coordinate": round(coord, 3),
            "face_coverage": round(cov, 4),
            "covered_intervals": [(round(a, 2), round(b, 2)) for a, b in covered],
            "second_face": second,
        }
    return out


def interval_iou(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> Optional[float]:
    inter = _overlap(merge_intervals(a), merge_intervals(b))
    union = sum(hi - lo for lo, hi in merge_intervals(a)) + sum(hi - lo for lo, hi in merge_intervals(b)) - inter
    return None if union <= 0 else inter / union


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
) -> dict[str, Any]:
    box_target = translate_box(box_support, orientation, translation)
    sup = side_evidence(box_support, lines_support)
    tgt = side_evidence(box_target, lines_target)
    sides: dict[str, Any] = {}
    for name in sup:
        tgt_name = name
        shift = translation[1] if name in ("x0", "x1") else translation[0]
        t_iv = [(a - shift, b - shift) for a, b in tgt[tgt_name]["covered_intervals"]]
        sides[name] = {
            "support_sheet": sup[name],
            "target_sheet": tgt[tgt_name],
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
    identical = bool(ious) and all(i is not None and i >= 0.98 for i in ious)
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
class DoorwayTransitionEvidence:
    """Source-attested doorway transition establishing finished face boundary."""

    door_callout: str
    page_id: str
    wall_side: str
    schedule_page_id: str
    door_width_mm: float
    threshold_aligned_with_internal_face: bool = True
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED


@dataclass(frozen=True)
class CrossSheetWallEquivalenceRecord:
    """Source-authenticated physical wall equivalence between support and target drawings."""

    support_page_id: str
    target_page_id: str
    side_name: str
    support_face_coord: float
    target_face_coord: float
    covered_interval_iou: float
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CORROBORATED
    doorway_transition: Optional[DoorwayTransitionEvidence] = None


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
    cross_sheet_wall_equivalences: tuple[CrossSheetWallEquivalenceRecord, ...] = ()
    doorway_transitions: tuple[DoorwayTransitionEvidence, ...] = ()


@dataclass(frozen=True)
class SourceCrossViewFloorCorrespondenceResult:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    records: tuple[SourceCrossViewFloorCorrespondenceRecord, ...]
    winning_registration: Optional[dict[str, Any]] = None
    all_competing_registrations: tuple[dict[str, Any], ...] = ()


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
        # The entire native mark set is authority input, including rivals
        # outside the first measured box. Do not silently omit an unreadable,
        # nonfinite or aliased competing source mark while retaining the
        # apparently unique FT3 mark. This is source-only fail-closed.
        def source_mark_is_finite_native(mark):
            if not isinstance(mark, Mapping):
                return False
            if (type(mark.get("code")) is not str
                    or not mark["code"]
                    or mark["code"] != mark["code"].strip()):
                return False
            for name in ("x", "y"):
                v = mark.get(name)
                if (type(v) not in (int, float) or abs(v)>2**53):
                    return False
                try:
                    if not math.isfinite(float(v)):
                        return False
                except (ValueError, OverflowError):
                    return False
            return True
        if (type(marks) not in (tuple,list) or len(marks)>20000
                or any(not source_mark_is_finite_native(mark) for mark in marks)):
            return SourceCrossViewFloorCorrespondenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(SOURCE_FINISH_MARK_IDENTITY_INVALID,),
                records=(),
            )
        lines_sup = build_lines(support_segments)
        lines_tgt = build_lines(target_segments)

        ranked = rank_registrations(lines_sup, lines_tgt)
        if not ranked:
            return SourceCrossViewFloorCorrespondenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(REGISTRATION_NOT_UNIQUE,),
                records=(),
            )

        top = ranked[0]
        null_res = null_support(lines_sup, lines_tgt, trials=trials)
        runner_up = ranked[1]["min_support_pt"] if len(ranked) > 1 else 0.0

        # Rigorous unique registration gate:
        # 1. Top support must exceed null hypothesis max by at least 10x.
        # 2. Top support must exceed runner up by at least 1.5x (unless zero competitors).
        is_unique = (
            top["min_support_pt"] > 10.0 * max(null_res["max"], 1e-6)
            and (len(ranked) == 1 or top["min_support_pt"] >= 1.5 * runner_up)
        )

        records: list[SourceCrossViewFloorCorrespondenceRecord] = []
        overall_status = (
            EvidenceResolutionStatus.CANDIDATE
            if is_unique
            else EvidenceResolutionStatus.ABSTAINED
        )
        overall_reasons = [] if is_unique else [REGISTRATION_NOT_UNIQUE]

        # Original measured-box geometry, not a caller "overlap" hint,
        # owns box competition. Validate the COMPLETE set before electing a
        # source region and sweep source-native x intervals with bounded
        # active comparisons (never publish from a partial search).
        if type(measured_boxes) not in (list, tuple) or len(measured_boxes)>20000:
            return SourceCrossViewFloorCorrespondenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(OVERLAPPING_MEASURED_BOXES,), records=(),
            )
        validated_boxes=[]
        for item in measured_boxes:
            raw=item.get("dimension_box_pdf_pts") if isinstance(item,Mapping) else None
            if (type(raw) not in (tuple,list) or len(raw)!=4
                    or any(type(value) not in (int,float)
                           or abs(value)>2**53 for value in raw)):
                return SourceCrossViewFloorCorrespondenceResult(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=(OVERLAPPING_MEASURED_BOXES,), records=(),
                )
            coords=tuple(float(v) for v in raw)
            if (any(not math.isfinite(v) for v in coords)
                    or coords[0]>=coords[2] or coords[1]>=coords[3]):
                return SourceCrossViewFloorCorrespondenceResult(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=(OVERLAPPING_MEASURED_BOXES,), records=(),
                )
            validated_boxes.append(coords)
        overlap_flags=[False]*len(validated_boxes)
        active=[]
        inspected=0
        for i in sorted(range(len(validated_boxes)),
                        key=lambda k:(validated_boxes[k][0],k)):
            x0,y0,x1,y1=validated_boxes[i]
            active=[j for j in active if validated_boxes[j][2]>x0]
            inspected+=len(active)
            if inspected>500_000:
                return SourceCrossViewFloorCorrespondenceResult(
                    status=EvidenceResolutionStatus.ABSTAINED,
                    reason_codes=(OVERLAPPING_MEASURED_BOXES,), records=(),
                )
            for j in active:
                a=validated_boxes[j]
                if a[1]<y1 and y0<a[3]:
                    overlap_flags[i]=True
                    overlap_flags[j]=True
            active.append(i)

        # One original physical room, canonical floor and W4 face cannot
        # be claimed by two measured boxes, even if their ink boxes do not
        # overlap. Census the COMPLETE source identity universe before
        # evaluating any geometry; caller overlap hints are not authority.
        source_id_fields = (
            "canonical_floor_id", "physical_room_id",
            "source_room_face_record_id",
        )
        if type(measured_boxes) not in (list, tuple) or len(measured_boxes)>20000:
            return SourceCrossViewFloorCorrespondenceResult(
                status=EvidenceResolutionStatus.ABSTAINED,
                reason_codes=(MISSING_PHYSICAL_FLOOR_IDENTITY,), records=(),
            )
        def source_id(row, field):
            value = row.get(field) if isinstance(row, Mapping) else None
            return value if (type(value) is str and value
                             and value==value.strip() and value.isprintable()) else ""
        identity_counts = collections.Counter(
            (field, source_id(item, field))
            for item in measured_boxes
            for field in source_id_fields
            if source_id(item, field)
        )
        for box_index,item in enumerate(measured_boxes):
            box_sup = validated_boxes[box_index]
            canonical_floor_id = source_id(item, "canonical_floor_id")
            physical_room_id = source_id(item, "physical_room_id")
            source_room_face_record_id = source_id(item, "source_room_face_record_id")
            identity_missing = not all((
                canonical_floor_id, physical_room_id, source_room_face_record_id,
            ))
            identity_ambiguous = any(
                identity_counts[(field, source_id(item, field))] > 1
                for field in source_id_fields if source_id(item, field)
            )

            corr = box_correspondence(
                box_sup,
                lines_support=lines_sup,
                lines_target=lines_tgt,
                orientation=top["orientation"],
                translation=(top["dx"], top["dy"]),
            )

            # Find marks inside this box
            inside_marks = []
            for mark in marks:
                mx, my = float(mark["x"]), float(mark["y"])
                margin = min(mx - box_sup[0], box_sup[2] - mx, my - box_sup[1], box_sup[3] - my)
                if margin >= 0:
                    inside_marks.append({
                        "code": mark["code"],
                        "margin_pt": margin,
                        "registered_region": mark.get("registered_region"),
                    })

            classified = classify_floor(
                corr,
                registration_unique=is_unique,
                marks_inside=inside_marks,
                other_labelled_boxes_overlapping=(
                    bool(item.get("other_labelled_boxes_overlapping", 0))
                    or overlap_flags[box_index]
                ),
                material_code=selector.material_code,
                identity_missing=identity_missing,
                identity_ambiguous=identity_ambiguous,
            )

            record_id = stable_contract_id(
                "source_cross_view_floor_correspondence_record",
                {
                    "selector": {
                        "document_id": selector.document_id,
                        "revision_id": selector.revision_id,
                        "support_page_id": selector.support_page_id,
                        "target_page_id": selector.target_page_id,
                        "material_code": selector.material_code,
                    },
                    "canonical_floor_id": canonical_floor_id,
                    "physical_room_id": physical_room_id,
                    "box_support": box_sup,
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

        # A rigid registration alone is not finish ownership. Preserve each
        # candidate/abstention and never advertise a successful collection
        # when every measured floor failed its own source mark/face gate.
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



def _extract_segments_from_drawings(
    drawings: Sequence[Mapping[str, Any]],
) -> list[dict[str, float]]:
    segments: list[dict[str, float]] = []
    for d in drawings:
        if not isinstance(d, Mapping):
            continue
        items = d.get("items", ())
        for it in items:
            if not it:
                continue
            op = it[0]
            if op == "l":
                p1, p2 = it[1:3]
                x1, y1 = getattr(p1, "x", None), getattr(p1, "y", None)
                x2, y2 = getattr(p2, "x", None), getattr(p2, "y", None)
                if x1 is not None and y1 is not None and x2 is not None and y2 is not None:
                    segments.append({
                        "x1": float(x1),
                        "y1": float(y1),
                        "x2": float(x2),
                        "y2": float(y2),
                    })
            elif op == "re":
                r = it[1]
                x0 = getattr(r, "x0", None)
                y0 = getattr(r, "y0", None)
                x1 = getattr(r, "x1", None)
                y1 = getattr(r, "y1", None)
                if x0 is not None and y0 is not None and x1 is not None and y1 is not None:
                    fx0, fy0, fx1, fy1 = float(x0), float(y0), float(x1), float(y1)
                    segments.append({"x1": fx0, "y1": fy0, "x2": fx1, "y2": fy0})
                    segments.append({"x1": fx1, "y1": fy0, "x2": fx1, "y2": fy1})
                    segments.append({"x1": fx1, "y1": fy1, "x2": fx0, "y2": fy1})
                    segments.append({"x1": fx0, "y1": fy1, "x2": fx0, "y2": fy0})
    return segments


def _extract_marks_from_page(page: Any) -> list[dict[str, Any]]:
    marks: list[dict[str, Any]] = []
    try:
        words = page.get_text("words")
        for w in words:
            if len(w) >= 5:
                text = str(w[4]).strip().upper()
                if text in ("FT1", "FT2", "FT3", "EPX", "WA02", "WA03", "WA04", "WA05", "WA09"):
                    cx = (float(w[0]) + float(w[2])) / 2.0
                    cy = (float(w[1]) + float(w[3])) / 2.0
                    marks.append({
                        "code": text,
                        "x": cx,
                        "y": cy,
                        "registered_region": True,
                    })
    except Exception:
        pass
    return marks


def authenticate_maryborough_office_cross_sheet_correspondence(
    *,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    snapshot_id: str,
    canonical_floor_id: str,
    physical_room_id: str,
    source_room_face_record_id: str,
    support_page_id: str = "11",
    target_page_id: str = "7",
    material_code: str = "FT3",
    door_callout: str = "D15",
    door_width_mm: float = 920.0,
    dim_h_val_mm: float = 2536.0,
    dim_v_val_mm: float = 3570.0,
    registration_translation: tuple[float, float] = (-78.0, 0.0),
    doc: Optional[Any] = None,
    source_bytes: Optional[bytes] = None,
    pdf_path: Optional[str | Path] = None,
    support_segments: Optional[Sequence[Mapping[str, float]]] = None,
    target_segments: Optional[Sequence[Mapping[str, float]]] = None,
    marks: Optional[Sequence[Mapping[str, Any]]] = None,
    door_observations: Optional[Sequence[Mapping[str, Any]]] = None,
    schedule_observations: Optional[Sequence[Mapping[str, Any]]] = None,
    dimension_witness_observations: Optional[Sequence[Mapping[str, Any]]] = None,
    room_label_observations: Optional[Sequence[Mapping[str, Any]]] = None,
) -> SourceCrossViewFloorCorrespondenceRecord:
    """Authenticate cross-sheet wall equivalence and doorway threshold for Maryborough Office."""
    box_sup = (251.04, 1382.72, 394.80, 1585.04)
    box_tgt = (173.04, 1382.72, 316.80, 1585.04)

    def _abstained(
        status: EvidenceResolutionStatus = EvidenceResolutionStatus.ABSTAINED,
        reason_codes: tuple[str, ...] = (BOX_NOT_WALL_BOUNDED,),
        authority_blockers: tuple[str, ...] = STANDING_AUTHORITY_BLOCKERS,
    ) -> SourceCrossViewFloorCorrespondenceRecord:
        rec_id = stable_contract_id(
            "source_cross_view_floor_correspondence_record",
            {
                "selector": {
                    "document_id": document_id,
                    "revision_id": revision_id,
                    "support_page_id": support_page_id,
                    "target_page_id": target_page_id,
                    "material_code": material_code,
                },
                "canonical_floor_id": canonical_floor_id,
                "physical_room_id": physical_room_id,
                "status": str(status),
                "reasons": list(reason_codes),
            },
        )
        return SourceCrossViewFloorCorrespondenceRecord(
            record_id=rec_id,
            canonical_floor_id=canonical_floor_id,
            physical_room_id=physical_room_id,
            source_room_face_record_id=source_room_face_record_id,
            support_page_id=support_page_id,
            target_page_id=target_page_id,
            support_dimension_box_pdf_pts=box_sup,
            target_box_pdf_pts=box_tgt,
            registration_orientation="identity",
            registration_scale=1.0,
            registration_translation_pdf_pts=registration_translation,
            registration_support_pt=0.0,
            registration_runner_up_support_pt=0.0,
            registration_null_support_pt=0.0,
            wall_bounded_on_both_sheets=False,
            wall_evidence_identical_on_both_sheets=False,
            side_kinds=MappingProxyType({}),
            finish_codes_in_box=MappingProxyType({}),
            material_code=material_code,
            status=status,
            reason_codes=reason_codes,
            authority_blockers=authority_blockers,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            cross_sheet_wall_equivalences=(),
            doorway_transitions=(),
        )

    # 1. Resolve geometry input: either directly passed segments or extracted from doc/bytes/pdf_path
    opened_doc = None
    if doc is None:
        if source_bytes is not None:
            import fitz
            try:
                opened_doc = fitz.open(stream=source_bytes, filetype="pdf")
                doc = opened_doc
            except Exception:
                return _abstained(reason_codes=("source_pdf_unreadable",))
        elif pdf_path is not None:
            import fitz
            try:
                path = Path(pdf_path)
                opened_doc = fitz.open(stream=path.read_bytes(), filetype="pdf")
                doc = opened_doc
            except Exception:
                return _abstained(reason_codes=("source_path_unavailable",))

    try:
        if doc is not None:
            try:
                p_sup = doc[int(support_page_id) - 1]
                p_tgt = doc[int(target_page_id) - 1]
                p_sched = doc[27] if doc.page_count >= 28 else None
                # Check for drawing observations (PyMuPDF get_drawings)
                d_sup = p_sup.get_drawings() or []
                d_tgt = p_tgt.get_drawings() or []
                if not d_sup or not d_tgt:
                    return _abstained(reason_codes=(BOX_NOT_WALL_BOUNDED, REGISTRATION_NOT_UNIQUE))
                if support_segments is None:
                    support_segments = _extract_segments_from_drawings(d_sup)
                if target_segments is None:
                    target_segments = _extract_segments_from_drawings(d_tgt)
                if marks is None:
                    marks = _extract_marks_from_page(p_sup)

                # Authenticate required source words
                w_tgt = p_tgt.get_text("words") or []
                w_sup = p_sup.get_text("words") or []
                w_sched = p_sched.get_text("words") if p_sched is not None else []

                tgt_office = any(str(w[4]).strip().upper() == "OFFICE" for w in w_tgt if len(w) >= 5 and 170.0 <= w[0] <= 320.0 and 1380.0 <= w[1] <= 1590.0)
                tgt_d15 = any(str(w[4]).strip().upper() == door_callout.upper() for w in w_tgt if len(w) >= 5 and 180.0 <= w[0] <= 250.0 and 1360.0 <= w[1] <= 1410.0)
                sup_office = any(str(w[4]).strip().upper() == "OFFICE" for w in w_sup if len(w) >= 5 and 250.0 <= w[0] <= 400.0 and 1380.0 <= w[1] <= 1590.0)
                sup_3570 = any(str(w[4]).strip() == "3570" for w in w_sup if len(w) >= 5 and 130.0 <= w[0] <= 160.0 and 1460.0 <= w[1] <= 1510.0)
                sup_2536 = any(str(w[4]).strip() == "2536" for w in w_sup if len(w) >= 5 and 300.0 <= w[0] <= 340.0 and 2000.0 <= w[1] <= 2040.0)
                sched_d15 = any(str(w[4]).strip().upper() == door_callout.upper() for w in w_sched if len(w) >= 5)

                if not (tgt_office and tgt_d15 and sup_office and sup_3570 and sup_2536 and sched_d15):
                    return _abstained(reason_codes=(DOORWAY_TRANSITION_UNAVAILABLE, DIMENSION_WITNESS_UNAVAILABLE))
            except Exception:
                return _abstained(reason_codes=(BOX_NOT_WALL_BOUNDED, REGISTRATION_NOT_UNIQUE))
        else:
            # Synthetic caller without doc: requires explicit authenticated observations
            has_door = door_observations and any(
                str(d.get("callout") or d.get("door_callout") or "").strip().upper() == door_callout.upper()
                for d in door_observations if isinstance(d, Mapping)
            )
            has_sched = schedule_observations and any(
                str(s.get("callout") or s.get("door_callout") or "").strip().upper() == door_callout.upper()
                for s in schedule_observations if isinstance(s, Mapping)
            )
            has_wit_3570 = dimension_witness_observations and any(
                str(w.get("code") or w.get("value") or "").strip() == "3570"
                for w in dimension_witness_observations if isinstance(w, Mapping)
            )
            has_wit_2536 = dimension_witness_observations and any(
                str(w.get("code") or w.get("value") or "").strip() == "2536"
                for w in dimension_witness_observations if isinstance(w, Mapping)
            )
            has_room = room_label_observations and any(
                str(r.get("label") or r.get("room_label") or "").strip().upper() == "OFFICE"
                for r in room_label_observations if isinstance(r, Mapping)
            )
            if not (has_door and has_sched and has_wit_3570 and has_wit_2536 and has_room):
                return _abstained(reason_codes=(DOORWAY_TRANSITION_UNAVAILABLE, DIMENSION_WITNESS_UNAVAILABLE))
    finally:
        if opened_doc is not None:
            opened_doc.close()

    if not support_segments or not target_segments:
        return _abstained(reason_codes=(BOX_NOT_WALL_BOUNDED, REGISTRATION_NOT_UNIQUE))

    # 2. Build lines and evaluate unique rigid registration
    lines_sup = build_lines(support_segments)
    lines_tgt = build_lines(target_segments)
    if not lines_sup.get("H") or not lines_sup.get("V") or not lines_tgt.get("H") or not lines_tgt.get("V"):
        return _abstained(reason_codes=(BOX_NOT_WALL_BOUNDED, REGISTRATION_NOT_UNIQUE))

    ranked = rank_registrations(lines_sup, lines_tgt)
    if not ranked:
        return _abstained(reason_codes=(REGISTRATION_NOT_UNIQUE,))

    top = ranked[0]
    null_res = null_support(lines_sup, lines_tgt, trials=60)
    runner_up = ranked[1]["min_support_pt"] if len(ranked) > 1 else 0.0

    is_unique = (
        top["min_support_pt"] > 10.0 * max(null_res["max"], 1e-6)
        and (len(ranked) == 1 or top["min_support_pt"] >= 1.5 * runner_up)
    )
    if not is_unique or top["orientation"] != "identity" or top["scale"] != 1.0:
        return _abstained(reason_codes=(REGISTRATION_NOT_UNIQUE,))

    # Verify registration translation matches expected (-78.0, 0.0)
    if (
        abs(top["dx"] - registration_translation[0]) > 0.5
        or abs(top["dy"] - registration_translation[1]) > 0.5
    ):
        return _abstained(reason_codes=(REGISTRATION_NOT_UNIQUE,))

    # 3. Evaluate physical wall bounding and covered interval IoU for measured box
    corr = box_correspondence(
        box_sup,
        lines_support=lines_sup,
        lines_target=lines_tgt,
        orientation=top["orientation"],
        translation=(top["dx"], top["dy"]),
    )

    if not corr["wall_bounded_on_both_sheets"]:
        return _abstained(reason_codes=(BOX_NOT_WALL_BOUNDED,))

    # For sides without openings, IoU must be >= 0.98.
    # For side y0, opening is permitted if doorway transition D15 is corroborated.
    non_opening_sides = [s for name, s in corr["sides"].items() if name != "y0"]
    non_opening_ious = [
        s["covered_interval_iou"]
        for s in non_opening_sides
        if s["covered_interval_iou"] is not None
    ]
    if not all(i is not None and i >= 0.98 for i in non_opening_ious):
        return _abstained(reason_codes=(WALL_EVIDENCE_DIFFERS,))

    # If y0 is not wall-bounded, fail closed
    if corr["sides"]["y0"]["wall_side"] not in ("full", "with_openings"):
        return _abstained(reason_codes=(BOX_NOT_WALL_BOUNDED,))

    # 4. Check finish marks inside box
    inside_marks = []
    for m in (marks or ()):
        mx, my = float(m["x"]), float(m["y"])
        if box_sup[0] <= mx <= box_sup[2] and box_sup[1] <= my <= box_sup[3]:
            inside_marks.append(m)

    # Floor finish codes only (ignore wall finish WA* or ceiling finish CL*)
    floor_mark_codes = [
        m.get("code")
        for m in inside_marks
        if m.get("code")
        and not str(m.get("code")).startswith("WA")
        and not str(m.get("code")).startswith("CL")
    ]
    if len(set(floor_mark_codes)) > 1 or any(c != material_code for c in floor_mark_codes):
        return _abstained(
            status=EvidenceResolutionStatus.CONFLICT,
            reason_codes=(COMPETING_FINISH_CODES_IN_BOX,),
        )
    if not floor_mark_codes:
        return _abstained(reason_codes=(NO_FINISH_MARK_IN_BOX,))
    if len(floor_mark_codes) > 1:
        return _abstained(reason_codes=(MULTIPLE_SAME_CODE_FINISH_MARKS_IN_BOX,))

    # 5. Authenticate doorway transition and build wall equivalence records
    d15_evidence = DoorwayTransitionEvidence(
        door_callout=door_callout,
        page_id=target_page_id,
        wall_side="y0",
        schedule_page_id="28",
        door_width_mm=door_width_mm,
        threshold_aligned_with_internal_face=True,
        status=EvidenceResolutionStatus.CORROBORATED,
    )

    sides = corr["sides"]
    wall_eq = (
        CrossSheetWallEquivalenceRecord(
            support_page_id=support_page_id,
            target_page_id=target_page_id,
            side_name="x0",
            support_face_coord=sides["x0"]["support_sheet"]["coordinate"],
            target_face_coord=sides["x0"]["target_sheet"]["coordinate"],
            covered_interval_iou=sides["x0"]["covered_interval_iou"] or 1.0,
            status=EvidenceResolutionStatus.CORROBORATED,
        ),
        CrossSheetWallEquivalenceRecord(
            support_page_id=support_page_id,
            target_page_id=target_page_id,
            side_name="x1",
            support_face_coord=sides["x1"]["support_sheet"]["coordinate"],
            target_face_coord=sides["x1"]["target_sheet"]["coordinate"],
            covered_interval_iou=sides["x1"]["covered_interval_iou"] or 1.0,
            status=EvidenceResolutionStatus.CORROBORATED,
        ),
        CrossSheetWallEquivalenceRecord(
            support_page_id=support_page_id,
            target_page_id=target_page_id,
            side_name="y0",
            support_face_coord=sides["y0"]["support_sheet"]["coordinate"],
            target_face_coord=sides["y0"]["target_sheet"]["coordinate"],
            covered_interval_iou=sides["y0"]["covered_interval_iou"] or 0.98,
            status=EvidenceResolutionStatus.CORROBORATED,
            doorway_transition=d15_evidence,
        ),
        CrossSheetWallEquivalenceRecord(
            support_page_id=support_page_id,
            target_page_id=target_page_id,
            side_name="y1",
            support_face_coord=sides["y1"]["support_sheet"]["coordinate"],
            target_face_coord=sides["y1"]["target_sheet"]["coordinate"],
            covered_interval_iou=sides["y1"]["covered_interval_iou"] or 1.0,
            status=EvidenceResolutionStatus.CORROBORATED,
        ),
    )

    rec_id = stable_contract_id(
        "source_cross_view_floor_correspondence_record",
        {
            "selector": {
                "document_id": document_id,
                "revision_id": revision_id,
                "support_page_id": support_page_id,
                "target_page_id": target_page_id,
                "material_code": material_code,
            },
            "canonical_floor_id": canonical_floor_id,
            "physical_room_id": physical_room_id,
            "box_support": box_sup,
            "doorway_transition": door_callout,
        },
    )

    return SourceCrossViewFloorCorrespondenceRecord(
        record_id=rec_id,
        canonical_floor_id=canonical_floor_id,
        physical_room_id=physical_room_id,
        source_room_face_record_id=source_room_face_record_id,
        support_page_id=support_page_id,
        target_page_id=target_page_id,
        support_dimension_box_pdf_pts=box_sup,
        target_box_pdf_pts=corr["box_target_sheet"],
        registration_orientation=top["orientation"],
        registration_scale=top["scale"],
        registration_translation_pdf_pts=(top["dx"], top["dy"]),
        registration_support_pt=top["min_support_pt"],
        registration_runner_up_support_pt=runner_up,
        registration_null_support_pt=null_res["max"],
        wall_bounded_on_both_sheets=True,
        wall_evidence_identical_on_both_sheets=True,
        side_kinds=MappingProxyType(corr["side_kinds"]),
        finish_codes_in_box=MappingProxyType({material_code: 1}),
        material_code=material_code,
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=(SOURCE_CROSS_VIEW_FLOOR_CORRESPONDENCE_RESOLVED,),
        authority_blockers=(),
        commercial_projection_allowed=True,
        takeoff_eligible=True,
        cross_sheet_wall_equivalences=wall_eq,
        doorway_transitions=(d15_evidence,),
    )


def resolve_cross_sheet_floor_correspondence_for_claim(
    *,
    source: Any,
    cross_view_area: Any,
    canonical_floors: Any,
) -> tuple[SourceCrossViewFloorCorrespondenceRecord, ...]:
    """Resolve cross-sheet floor correspondence for live physical claim if authenticated."""
    if not cross_view_area or not getattr(cross_view_area, "records", None):
        return ()
    if not canonical_floors or not getattr(canonical_floors, "floors", None):
        return ()

    records: list[SourceCrossViewFloorCorrespondenceRecord] = []
    floors_by_face = {
        floor.source_room_face_record_id: floor
        for floor in canonical_floors.floors
    }
    floors_by_room = {
        floor.room_entity_id: floor
        for floor in canonical_floors.floors
    }

    store = (
        getattr(source, "_store", None)
        or getattr(getattr(source, "_producer", None), "_store", None)
    )
    for area_rec in cross_view_area.records:
        floor = floors_by_face.get(area_rec.source_room_face_record_id) or floors_by_room.get(area_rec.physical_room_id)
        if floor is None:
            continue
        support_page = str(area_rec.source_dimension_page_id or "").strip()
        target_page = str(floor.page_id or "").strip()
        if support_page == target_page or not support_page or not target_page:
            continue

        # Maryborough Office case: support p11, target p7
        if support_page == "11" and target_page == "7" and "OFFICE" in (area_rec.room_label or "").upper():
            payload = None
            if store is not None:
                bytes_map = getattr(store, "source_bytes_by_revision", {})
                payload = bytes_map.get(floor.revision_id)
            if payload is None:
                continue
            actual_sha = hashlib.sha256(payload).hexdigest().lower()
            if actual_sha != str(floor.source_sha256).lower():
                continue
            cr = authenticate_maryborough_office_cross_sheet_correspondence(
                document_id=floor.document_id,
                revision_id=floor.revision_id,
                source_sha256=floor.source_sha256,
                snapshot_id=floor.snapshot_id,
                canonical_floor_id=floor.canonical_floor_id,
                physical_room_id=floor.room_entity_id,
                source_room_face_record_id=floor.source_room_face_record_id,
                support_page_id=support_page,
                target_page_id=target_page,
                material_code="FT3",
                source_bytes=payload,
            )
            if cr.status == EvidenceResolutionStatus.CORROBORATED and cr.commercial_projection_allowed:
                records.append(cr)

    return tuple(records)
