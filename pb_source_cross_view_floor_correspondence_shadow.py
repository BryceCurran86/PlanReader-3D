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
BOX_NOT_WALL_BOUNDED = "box_not_wall_bounded_on_both_sheets"
WALL_EVIDENCE_DIFFERS = "wall_evidence_differs_between_sheets"
OVERLAPPING_MEASURED_BOXES = "overlapping_measured_boxes"
MARK_TOO_CLOSE_TO_BOX_SIDE = "mark_too_close_to_box_side"
MARK_IN_UNREGISTERED_REGION = "mark_in_unregistered_region"
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
    min_margin_pt: float = 5.0,
    authority_blockers: Sequence[str] = STANDING_AUTHORITY_BLOCKERS,
) -> dict[str, Any]:
    reasons: list[str] = []
    codes = collections.Counter(m["code"] for m in marks_inside)
    if not registration_unique:
        reasons.append(REGISTRATION_NOT_UNIQUE)
    if not correspondence["wall_bounded_on_both_sheets"]:
        reasons.append(BOX_NOT_WALL_BOUNDED)
    elif not correspondence["wall_evidence_identical_on_both_sheets"]:
        reasons.append(WALL_EVIDENCE_DIFFERS)
    if other_labelled_boxes_overlapping:
        reasons.append(OVERLAPPING_MEASURED_BOXES)
    # A missing, malformed or non-finite mark margin is not a positive
    # original source containment receipt. Reject it rather than defaulting
    # to zero or letting NaN bypass the geometric comparison.
    if any(
        type(mark.get("margin_pt")) not in (int, float)
        or not math.isfinite(float(mark["margin_pt"]))
        or float(mark["margin_pt"]) < min_margin_pt
        for mark in marks_inside
    ):
        reasons.append(MARK_TOO_CLOSE_TO_BOX_SIDE)
    # Registration is an explicit source fact, not a truthy caller hint.
    if any(mark.get("registered_region") is not True for mark in marks_inside):
        reasons.append(MARK_IN_UNREGISTERED_REGION)

    if len(codes) > 1:
        status = EvidenceResolutionStatus.CONFLICT
        reasons.append(COMPETING_FINISH_CODES_IN_BOX)
    elif not codes:
        status = EvidenceResolutionStatus.ABSTAINED
        reasons.append(NO_FINISH_MARK_IN_BOX)
    elif material_code not in codes:
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

        for item in measured_boxes:
            box_sup = tuple(float(v) for v in item["dimension_box_pdf_pts"])
            canonical_floor_id = _clean(item.get("canonical_floor_id"))
            physical_room_id = _clean(item.get("physical_room_id"))
            source_room_face_record_id = _clean(item.get("source_room_face_record_id"))

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
                other_labelled_boxes_overlapping=item.get("other_labelled_boxes_overlapping", 0),
                material_code=selector.material_code,
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

        return SourceCrossViewFloorCorrespondenceResult(
            status=overall_status,
            reason_codes=tuple(overall_reasons),
            records=tuple(records),
            winning_registration=top,
            all_competing_registrations=tuple(ranked),
        )
