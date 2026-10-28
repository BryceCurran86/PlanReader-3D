"""Producer-owned source page-11 to page-7 plan correspondence shadow authority (Item 15).

Proves the geometric and physical correspondence between multi-sheet floor plan drawings:
- Derives rigid 2D registration (orientation, scale, translation) between support sheet
  (e.g., page 11) and target sheet (e.g., page 7) from split-invariant collinear interval
  overlap of non-grid wall linework.
- Evaluates candidate room dimension boxes on both sheets to verify four-sided physical
  wall enclosure with outward parallel second faces (wall thickness band 3.0 - 15.0 pt).
- Proves identical wall opening intervals via high interval IoU (>= 0.98).
- Verifies material finish mark containment (e.g. FT3 in OFFICE) and rejects competing
  finish codes or open-plan zones.
- Operates strictly in shadow mode with CANDIDATE status and non-commercial flags.
"""
from __future__ import annotations

import bisect
import collections
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple

from pb_migration_contracts import (
    EvidenceResolutionStatus,
    stable_contract_id,
)

SOURCE_PAGE_PLAN_CORRESPONDENCE_SCHEMA_VERSION = "1.0.0"

# Public Reason Codes
PAGE_PLAN_CORRESPONDENCE_RESOLVED = "page_plan_correspondence_resolved"
PAGE_PLAN_CORRESPONDENCE_UNRESOLVED = "page_plan_correspondence_unresolved"
ROOM_NOT_WALL_BOUNDED_ON_BOTH_SHEETS = "room_not_wall_bounded_on_both_sheets"
WALL_EVIDENCE_MISMATCH_ACROSS_SHEETS = "wall_evidence_mismatch_across_sheets"
REGISTRATION_SUPPORT_INSUFFICIENT = "registration_support_insufficient"
AMBIGUOUS_REGISTRATION_CANDIDATE = "ambiguous_registration_candidate"
COMPETING_FINISH_CODES_IN_ROOM = "competing_finish_codes_in_room"
MARK_OUTSIDE_REGISTERED_ROOM = "mark_outside_registered_room"
PLAN_CORRESPONDENCE_RECORD_UNAVAILABLE = "plan_correspondence_record_unavailable"
DEGENERATE_ROOM_BOX_GEOMETRY = "degenerate_room_box_geometry"

_PRODUCER_SEAL = object()
_AUTHORITY_SEAL = object()
_RECORD_SEAL = object()

_Key = Tuple[str, str, str, str, str, str, str, str]  # doc/rev/sha/snap/sup_page/tgt_page/scope/room

AXIS_TOL = 0.02
MIN_LEN = 3.0
COORD_TOL = 0.06
WALL_BAND = (3.0, 15.0)
SIDE_FULL = 0.95
SIDE_PARTIAL = 0.50

D4 = {
    "identity": (1, 0, 0, 1),
    "rot90": (0, -1, 1, 0),
    "rot180": (-1, 0, 0, -1),
    "rot270": (0, 1, -1, 0),
    "mirror_x": (-1, 0, 0, 1),
    "mirror_y": (1, 0, 0, -1),
    "transpose": (0, 1, 1, 0),
    "anti_transpose": (0, -1, -1, 0),
}

Lines = Dict[str, Dict[float, List[Tuple[float, float]]]]


def _required(value: object, name: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{name} must be non-empty")
    return text


# ── Pure Geometric Registration & Wall Interval Algorithms ────────────────────


def merge_intervals(intervals: Iterable[Sequence[float]]) -> List[Tuple[float, float]]:
    out: List[List[float]] = []
    for lo, hi in sorted((float(a), float(b)) for a, b in intervals):
        if out and lo <= out[-1][1] + 1e-6:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return [(a, b) for a, b in out]


def build_lines(segments: Iterable[Mapping[str, Any]], *, min_len: float = MIN_LEN) -> Lines:
    """Axis-parallel linework as collinear interval unions."""
    raw: Dict[str, Dict[float, List[Tuple[float, float]]]] = {
        "H": collections.defaultdict(list),
        "V": collections.defaultdict(list),
    }
    for s in segments:
        if "p1" in s and "p2" in s:
            x1, y1 = float(s["p1"][0]), float(s["p1"][1])
            x2, y2 = float(s["p2"][0]), float(s["p2"][1])
        elif "x1" in s and "y1" in s and "x2" in s and "y2" in s:
            x1, y1, x2, y2 = float(s["x1"]), float(s["y1"]), float(s["x2"]), float(s["y2"])
        else:
            continue

        if math.hypot(x2 - x1, y2 - y1) < min_len:
            continue
        if abs(y2 - y1) < AXIS_TOL:
            raw["H"][round(y1, 2)].append((min(x1, x2), max(x1, x2)))
        elif abs(x2 - x1) < AXIS_TOL:
            raw["V"][round(x1, 2)].append((min(y1, y2), max(y1, y2)))
    return {o: {k: merge_intervals(v) for k, v in raw[o].items()} for o in "HV"}


def orient_lines(lines: Lines, mat: Sequence[float]) -> Lines:
    """Apply D4-or-scaled linear map about origin."""
    a, b, c, d = mat
    out: Dict[str, Dict[float, List[Tuple[float, float]]]] = {
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


def _overlap(a: Sequence[Tuple[float, float]], b: Sequence[Tuple[float, float]]) -> float:
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
    """Sorted coordinate index over a Lines set."""

    def __init__(self, lines: Lines):
        self.lines = lines
        self.keys = {o: sorted(lines[o]) for o in "HV"}

    def near(self, orient: str, coord: float, tol: float) -> List[float]:
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


def min_axis_support(src: Lines, dst: LineIndex, dx: float, dy: float, tol: float = COORD_TOL) -> Tuple[float, float, float]:
    h, v = axis_support(src, dst, "H", dx, dy, tol), axis_support(src, dst, "V", dx, dy, tol)
    return min(h, v), h, v


def _shift_votes(src: Lines, dst: LineIndex, topn: int, limit: float = 3000.0) -> Tuple[List[float], List[float]]:
    votes: Dict[str, collections.Counter] = {"H": collections.Counter(), "V": collections.Counter()}
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
) -> List[Dict[str, Any]]:
    """Rank every orientation / scale hypothesis with its best translation."""
    index = LineIndex(dst)
    rows: List[Dict[str, Any]] = []
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


def side_evidence(
    box: Sequence[float],
    lines: Lines,
    *,
    tol: float = COORD_TOL,
    band: Tuple[float, float] = WALL_BAND,
) -> Dict[str, Dict[str, Any]]:
    """Per box side: wall face-line coverage, covered intervals, and parallel second face."""
    x0, y0, x1, y1 = (float(v) for v in box)
    index = LineIndex(lines)
    out: Dict[str, Dict[str, Any]] = {}
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


def point_margin(point: Sequence[float], box: Sequence[float]) -> float:
    """Signed distance to the nearest box side: positive inside, negative outside."""
    x, y = point
    return min(x - box[0], box[2] - x, y - box[1], box[3] - y)


def translate_box(
    box: Sequence[float],
    orientation: str,
    translation: Sequence[float],
) -> Tuple[float, float, float, float]:
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
) -> Dict[str, Any]:
    """Registered-box wall evidence on both sheets."""
    box_target = translate_box(box_support, orientation, translation)
    sup = side_evidence(box_support, lines_support)
    tgt = side_evidence(box_target, lines_target)
    sides: Dict[str, Any] = {}
    for name in sup:
        tgt_name = name
        shift = translation[1] if name in ("x0", "x1") else translation[0]
        t_iv = [(a - shift, b - shift) for a, b in tgt[tgt_name]["covered_intervals"]]
        sides[name] = {
            "support_sheet": sup[name],
            "target_sheet": tgt[tgt_name],
            "covered_interval_iou": interval_iou(sup[name]["covered_intervals"], t_iv) if orientation == "identity" else None,
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


# ── Contracts ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class SourcePagePlanCorrespondenceSelector:
    """Selector identifying the support and target page context for room correspondence."""

    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    support_page_id: str
    target_page_id: str
    decision_scope_id: str
    room_name: str

    def __post_init__(self) -> None:
        for name in (
            "document_id",
            "revision_id",
            "source_sha256",
            "snapshot_id",
            "support_page_id",
            "target_page_id",
            "decision_scope_id",
            "room_name",
        ):
            _required(getattr(self, name), name)

    @property
    def key(self) -> _Key:
        return (
            self.document_id,
            self.revision_id,
            self.source_sha256,
            self.snapshot_id,
            self.support_page_id,
            self.target_page_id,
            self.decision_scope_id,
            self.room_name,
        )


@dataclass(frozen=True)
class SourcePagePlanCorrespondenceRecord:
    """Sealed record proving correspondence between support and target plan views."""

    record_id: str
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    support_page_id: str
    target_page_id: str
    decision_scope_id: str
    room_name: str
    box_support_sheet: Tuple[float, float, float, float]
    box_target_sheet: Tuple[float, float, float, float]
    orientation: str
    scale: float
    translation: Tuple[float, float]
    min_support_pt: float
    wall_bounded_both_sheets: bool
    wall_evidence_identical: bool
    contained_finish_marks: Tuple[str, ...]
    side_coverage_summary: Mapping[str, str]
    corroborating_evidence_ids: Tuple[str, ...]
    status: EvidenceResolutionStatus = EvidenceResolutionStatus.CANDIDATE
    commercial_projection_allowed: bool = False
    takeoff_eligible: bool = False
    schema_version: str = SOURCE_PAGE_PLAN_CORRESPONDENCE_SCHEMA_VERSION
    _seal: object = None

    def __post_init__(self) -> None:
        if self._seal is not _RECORD_SEAL:
            raise TypeError("SourcePagePlanCorrespondenceRecord is producer-owned and cannot be constructed directly")


@dataclass(frozen=True)
class SourcePagePlanCorrespondenceResult:
    """Result of cross-sheet plan correspondence evaluation."""

    status: EvidenceResolutionStatus
    reason_codes: Tuple[str, ...]
    record: Optional[SourcePagePlanCorrespondenceRecord] = None
    schema_version: str = SOURCE_PAGE_PLAN_CORRESPONDENCE_SCHEMA_VERSION


def _abstained(reason: str, *extras: str) -> SourcePagePlanCorrespondenceResult:
    return SourcePagePlanCorrespondenceResult(
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=tuple(dict.fromkeys([reason, *(str(r) for r in extras if str(r))])),
        record=None,
    )


# ── Producer & Authority ───────────────────────────────────────────────────────


class SourcePagePlanCorrespondenceAuthority:
    """Sealed lookup authority for published cross-sheet plan correspondences."""

    def __init__(
        self,
        records: Mapping[_Key, SourcePagePlanCorrespondenceResult],
        *,
        _seal: object = None,
    ) -> None:
        if _seal is not _AUTHORITY_SEAL:
            raise TypeError("SourcePagePlanCorrespondenceAuthority is producer-owned and cannot be constructed directly")
        self._records = MappingProxyType(dict(records))

    def resolve(self, selector: SourcePagePlanCorrespondenceSelector) -> SourcePagePlanCorrespondenceResult:
        if type(selector) is not SourcePagePlanCorrespondenceSelector:
            raise TypeError("selector must be SourcePagePlanCorrespondenceSelector")
        return self._records.get(selector.key, _abstained(PLAN_CORRESPONDENCE_RECORD_UNAVAILABLE))


class SourcePagePlanCorrespondenceProducer:
    """Producer for authenticated cross-sheet plan correspondence."""

    def __init__(self, *, _seal: object = None) -> None:
        if _seal is not _PRODUCER_SEAL:
            raise TypeError("SourcePagePlanCorrespondenceProducer must be obtained via create()")
        self._results: Dict[_Key, SourcePagePlanCorrespondenceResult] = {}

    @classmethod
    def create(cls) -> SourcePagePlanCorrespondenceProducer:
        return cls(_seal=_PRODUCER_SEAL)

    def evaluate_and_publish(
        self,
        selector: SourcePagePlanCorrespondenceSelector,
        *,
        support_segments: Iterable[Mapping[str, Any]],
        target_segments: Iterable[Mapping[str, Any]],
        room_box_support: Sequence[float],
        plan_marks: Optional[Sequence[Mapping[str, Any]]] = None,
        expected_finish_code: Optional[str] = None,
        min_registration_support: float = 1000.0,
    ) -> SourcePagePlanCorrespondenceResult:
        """Evaluate cross-sheet registration, boundary enclosure, and material marks."""
        if type(selector) is not SourcePagePlanCorrespondenceSelector:
            raise TypeError("selector must be SourcePagePlanCorrespondenceSelector")

        # 1. Validate room box geometry
        if len(room_box_support) != 4 or room_box_support[0] >= room_box_support[2] or room_box_support[1] >= room_box_support[3]:
            res = _abstained(DEGENERATE_ROOM_BOX_GEOMETRY)
            self._results[selector.key] = res
            return res

        # 2. Build lines from segments
        lines_sup = build_lines(support_segments)
        lines_tgt = build_lines(target_segments)

        # 3. Compute rigid 2D registration
        ranked = rank_registrations(lines_sup, lines_tgt)
        if not ranked or ranked[0]["min_support_pt"] < min_registration_support:
            res = _abstained(REGISTRATION_SUPPORT_INSUFFICIENT)
            self._results[selector.key] = res
            return res

        best_reg = ranked[0]
        # Check competitor ambiguity
        if len(ranked) > 1 and best_reg["min_support_pt"] < 1.5 * ranked[1]["min_support_pt"]:
            res = _abstained(AMBIGUOUS_REGISTRATION_CANDIDATE)
            self._results[selector.key] = res
            return res

        orientation = best_reg["orientation"]
        scale = float(best_reg["scale"])
        translation = (float(best_reg["dx"]), float(best_reg["dy"]))

        # 4. Evaluate physical wall correspondence across sheets
        corr = box_correspondence(
            room_box_support,
            lines_support=lines_sup,
            lines_target=lines_tgt,
            orientation=orientation,
            translation=translation,
        )

        if not corr["wall_bounded_on_both_sheets"]:
            res = _abstained(ROOM_NOT_WALL_BOUNDED_ON_BOTH_SHEETS)
            self._results[selector.key] = res
            return res

        if not corr["wall_evidence_identical_on_both_sheets"]:
            res = _abstained(WALL_EVIDENCE_MISMATCH_ACROSS_SHEETS)
            self._results[selector.key] = res
            return res

        # 5. Evaluate finish marks inside support sheet room box
        marks_in_box: List[str] = []
        # Candidate observations stay geometry-only: no mark becomes material
        # authority merely because its text lies inside a caller-supplied box.
        mark_observations: List[Tuple[str, float, float]] = []
        competing_marks: List[str] = []

        if plan_marks:
            for m in plan_marks:
                code = str(m.get("code") or m.get("text") or "").strip()
                pos = m.get("pos") or m.get("center") or ((m.get("x0", 0) + m.get("x1", 0)) / 2.0, (m.get("y0", 0) + m.get("y1", 0)) / 2.0)
                if point_margin(pos, room_box_support) > 0:
                    if expected_finish_code and code != expected_finish_code:
                        competing_marks.append(code)
                    else:
                        marks_in_box.append(code)
                        mark_observations.append((code, float(pos[0]), float(pos[1])))

        if competing_marks:
            res = _abstained(COMPETING_FINISH_CODES_IN_ROOM)
            self._results[selector.key] = res
            return res

        # 6. Mint a candidate *claim* identity, not just a selector identity.
        # Reusing an ID for changed wall-face evidence/marks would let a
        # downstream diagnostic mistake two mutually exclusive hypotheses
        # for one verified physical room. Sorted mark observations and merged
        # source intervals make the ID input-order/split invariant.
        side_claims = {
            name: {
                "support_face_intervals": side["support_sheet"]["covered_intervals"],
                "target_face_intervals": side["target_sheet"]["covered_intervals"],
                "support_second_faces": side["support_sheet"]["second_face"],
                "target_second_faces": side["target_sheet"]["second_face"],
            }
            for name, side in sorted(corr["sides"].items())
        }
        rec_id = stable_contract_id(
            "source_page_plan_correspondence",
            {
                "document_id": selector.document_id,
                "revision_id": selector.revision_id,
                "source_sha256": selector.source_sha256,
                "snapshot_id": selector.snapshot_id,
                "support_page_id": selector.support_page_id,
                "target_page_id": selector.target_page_id,
                "decision_scope_id": selector.decision_scope_id,
                "room_name": selector.room_name,
                "box_support_sheet": corr["box_support_sheet"],
                "box_target_sheet": corr["box_target_sheet"],
                "orientation": orientation,
                "scale": scale,
                "translation": translation,
                "side_claims": side_claims,
                "mark_observations": sorted(mark_observations),
            },
        )

        record = SourcePagePlanCorrespondenceRecord(
            record_id=rec_id,
            document_id=selector.document_id,
            revision_id=selector.revision_id,
            source_sha256=selector.source_sha256,
            snapshot_id=selector.snapshot_id,
            support_page_id=selector.support_page_id,
            target_page_id=selector.target_page_id,
            decision_scope_id=selector.decision_scope_id,
            room_name=selector.room_name,
            box_support_sheet=corr["box_support_sheet"],
            box_target_sheet=corr["box_target_sheet"],
            orientation=orientation,
            scale=scale,
            translation=translation,
            min_support_pt=float(best_reg["min_support_pt"]),
            wall_bounded_both_sheets=corr["wall_bounded_on_both_sheets"],
            wall_evidence_identical=corr["wall_evidence_identical_on_both_sheets"],
            contained_finish_marks=tuple(sorted(marks_in_box)),
            side_coverage_summary=MappingProxyType(corr["side_kinds"]),
            corroborating_evidence_ids=tuple(sorted([f"p{selector.support_page_id}_box", f"p{selector.target_page_id}_box"])),
            status=EvidenceResolutionStatus.CANDIDATE,
            commercial_projection_allowed=False,
            takeoff_eligible=False,
            _seal=_RECORD_SEAL,
        )

        res = SourcePagePlanCorrespondenceResult(
            status=EvidenceResolutionStatus.CANDIDATE,
            reason_codes=(PAGE_PLAN_CORRESPONDENCE_RESOLVED,),
            record=record,
        )
        self._results[selector.key] = res
        return res

    def authority(self) -> SourcePagePlanCorrespondenceAuthority:
        return SourcePagePlanCorrespondenceAuthority(self._results, _seal=_AUTHORITY_SEAL)
