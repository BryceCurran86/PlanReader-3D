"""Read-only proof: original Maryborough page-11 FT3 plan marks -> page-7 measured floors, from original wall geometry.

Diagnostic only.  Nothing here publishes a material occurrence, floor finish, quantity, scale, customer row or benchmark
identity, and nothing writes to the repository.  It traces the *evidence* a future shadow authority would need:

  A. one rigid page-11 -> page-7 registration, derived ONLY from W4 wall-candidate source primitives of both pages
     (production producers unchanged; producer-typed KIND_GRID separators excluded), with every competing orientation,
     scale and translation retained and scored (split-invariant collinear interval overlap, two-axis minimum, seeded null);
  B. for every already-measured floor (cross-view room-area record, dimension box on the support page) whether the
     registered box is a wall-bounded region on BOTH sheets (face line + parallel second face behind it, identical covered
     intervals) -- the physical-floor correspondence;
  C. which plan marks of the requested material code fall strictly inside each box, which other finish codes compete, and
     which marks are outside every registered region (schedule/legend cells).

Labels, filenames, expected quantities and areas never select anything.  ``--finish-codes`` is a *reporting census filter*;
a production shadow must take codes from authenticated schedule definitions.  Thresholds below are diagnostic parameters.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import hashlib
import json
import math
import random
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

EXPECTED_SHA256 = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"  # replay assertion only
SOURCE_PAGE = 7      # measured floors live here (1-based)
MARK_PAGE = 11       # plan marks and the room-area dimension systems live here (1-based)

AXIS_TOL = 0.02      # pt; a segment is axis-parallel below this
MIN_LEN = 3.0        # pt
COORD_TOL = 0.06     # pt; collinearity tolerance (PDF coordinate precision)
WALL_BAND = (3.0, 15.0)  # pt; admissible distance of a wall's second face line from a box side (either side)
SIDE_FULL = 0.95     # coverage regarded as a complete wall side
SIDE_PARTIAL = 0.50  # coverage regarded as a wall side with registered opening(s)
MARK_WINDOW = 260.0  # pt; local-registration window radius around a mark

D4 = {
    "identity": (1, 0, 0, 1), "rot90": (0, -1, 1, 0), "rot180": (-1, 0, 0, -1), "rot270": (0, 1, -1, 0),
    "mirror_x": (-1, 0, 0, 1), "mirror_y": (1, 0, 0, -1), "transpose": (0, 1, 1, 0), "anti_transpose": (0, -1, -1, 0),
}

Lines = dict  # {"H": {coord: [(lo, hi), ...]}, "V": {...}}


# --------------------------------------------------------------------------------------------- pure geometry
def merge_intervals(intervals: Iterable[Sequence[float]]) -> list[tuple[float, float]]:
    out: list[list[float]] = []
    for lo, hi in sorted((float(a), float(b)) for a, b in intervals):
        if out and lo <= out[-1][1] + 1e-6:
            out[-1][1] = max(out[-1][1], hi)
        else:
            out.append([lo, hi])
    return [(a, b) for a, b in out]


def build_lines(segments: Iterable[Mapping[str, float]], *, min_len: float = MIN_LEN) -> Lines:
    """Axis-parallel line-work as collinear interval unions (invariant to splitting/merging of segments)."""
    raw: dict[str, dict[float, list[tuple[float, float]]]] = {"H": collections.defaultdict(list), "V": collections.defaultdict(list)}
    for s in segments:
        x1, y1, x2, y2 = float(s["x1"]), float(s["y1"]), float(s["x2"]), float(s["y2"])
        if math.hypot(x2 - x1, y2 - y1) < min_len:
            continue
        if abs(y2 - y1) < AXIS_TOL:
            raw["H"][round(y1, 2)].append((min(x1, x2), max(x1, x2)))
        elif abs(x2 - x1) < AXIS_TOL:
            raw["V"][round(x1, 2)].append((min(y1, y2), max(y1, y2)))
    return {o: {k: merge_intervals(v) for k, v in raw[o].items()} for o in "HV"}


def total_length(lines: Lines) -> float:
    return sum(hi - lo for o in "HV" for ivs in lines[o].values() for lo, hi in ivs)


def orient_lines(lines: Lines, mat: Sequence[float]) -> Lines:
    """Apply a D4-or-scaled linear map (a b / c d) about the origin; axis-parallel lines stay axis-parallel."""
    a, b, c, d = mat
    out: dict[str, dict[float, list[tuple[float, float]]]] = {"H": collections.defaultdict(list), "V": collections.defaultdict(list)}
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
    """Sorted coordinate index over a Lines set."""

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
    h, v = axis_support(src, dst, "H", dx, dy, tol), axis_support(src, dst, "V", dx, dy, tol)
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
    """Every orientation / scale hypothesis with its best translation, the next distinct translation and its support.

    Deterministic: vote ties broken by value, no randomness.  Support is the two-axis minimum of split-invariant
    collinear interval overlap, so one-axis sliding along long lines or a periodic grid cannot win alone.
    """
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
                "orientation": name, "scale": scale, "dx": round(best[3], 2), "dy": round(best[4], 2),
                "min_support_pt": round(best[0], 1), "h_support_pt": round(best[1], 1), "v_support_pt": round(best[2], 1),
                "next_distinct_translation": None if second is None else [round(second[3], 2), round(second[4], 2)],
                "next_distinct_min_support_pt": None if second is None else round(second[0], 1),
            })
    rows.sort(key=lambda r: (-r["min_support_pt"], r["orientation"], r["scale"]))
    return rows


def null_support(src: Lines, dst: Lines, *, trials: int = 300, seed: int = 20261014, span: tuple[float, float] = (1500.0, 2000.0)) -> dict[str, float]:
    rng = random.Random(seed)
    index = LineIndex(dst)
    vals = sorted(min_axis_support(src, index, rng.uniform(-span[0], span[0]), rng.uniform(-span[1], span[1]))[0] for _ in range(trials))
    return {"max": vals[-1], "p99": vals[int(0.99 * (len(vals) - 1))], "median": vals[len(vals) // 2]}


def side_evidence(box: Sequence[float], lines: Lines, *, tol: float = COORD_TOL, band: tuple[float, float] = WALL_BAND) -> dict[str, dict[str, Any]]:
    """Per box side: wall face-line coverage, covered intervals, and a parallel second face behind it (outward)."""
    x0, y0, x1, y1 = (float(v) for v in box)
    index = LineIndex(lines)
    out: dict[str, dict[str, Any]] = {}
    for name, orient, coord, lo, hi, sign in (
        ("x0", "V", x0, y0, y1, -1), ("x1", "V", x1, y0, y1, 1), ("y0", "H", y0, x0, x1, -1), ("y1", "H", y1, x0, x1, 1),
    ):
        length = hi - lo
        covered = merge_intervals(
            (max(a, lo), min(b, hi)) for k in index.near(orient, coord, tol) for a, b in lines[orient][k] if min(b, hi) > max(a, lo)
        )
        cov = sum(b - a for a, b in covered) / length if length > 0 else 0.0
        # A wall has two faces a wall-thickness apart.  The measured side may lie on either face, so the second face is searched on
        # both sides; the signed offset is positive when it lies outside the box.
        second = []
        for k in index.keys[orient]:
            signed = (k - coord) * sign
            if band[0] <= abs(signed) <= band[1]:
                c2 = sum(max(0.0, min(b, hi) - max(a, lo)) for a, b in lines[orient][k]) / length
                if c2 >= SIDE_PARTIAL:
                    second.append((round(signed, 2), round(c2, 3)))
        out[name] = {"coordinate": round(coord, 3), "face_coverage": round(cov, 4), "covered_intervals": [(round(a, 2), round(b, 2)) for a, b in covered],
                     "second_face": second}
    return out


def interval_iou(a: Sequence[Sequence[float]], b: Sequence[Sequence[float]]) -> float | None:
    inter = _overlap(merge_intervals(a), merge_intervals(b))
    union = sum(hi - lo for lo, hi in merge_intervals(a)) + sum(hi - lo for lo, hi in merge_intervals(b)) - inter
    return None if union <= 0 else inter / union


def point_margin(point: Sequence[float], box: Sequence[float]) -> float:
    """Signed distance to the nearest box side: positive inside, negative outside."""
    x, y = point
    return min(x - box[0], box[2] - x, y - box[1], box[3] - y)


def translate_box(box: Sequence[float], orientation: str, translation: Sequence[float]) -> tuple[float, float, float, float]:
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
    """Registered-box wall evidence on both sheets (support-page box -> target-page box) and a typed outcome."""
    box_target = translate_box(box_support, orientation, translation)
    sup = side_evidence(box_support, lines_support)
    tgt = side_evidence(box_target, lines_target)
    # The covered intervals live in each sheet's own coordinates; compare in the support sheet's frame.
    sides: dict[str, Any] = {}
    for name in sup:
        tgt_name = name  # side names pair only under identity orientation; other orientations report side-wise coverage only
        shift = translation[1] if name in ("x0", "x1") else translation[0]
        t_iv = [(a - shift, b - shift) for a, b in tgt[tgt_name]["covered_intervals"]]
        sides[name] = {
            "support_sheet": sup[name], "target_sheet": tgt[tgt_name],
            "covered_interval_iou": interval_iou(sup[name]["covered_intervals"], t_iv) if orientation == "identity" else None,
            "wall_side": (
                "full" if min(sup[name]["face_coverage"], tgt[tgt_name]["face_coverage"]) >= SIDE_FULL and sup[name]["second_face"] and tgt[tgt_name]["second_face"]
                else "with_openings" if min(sup[name]["face_coverage"], tgt[tgt_name]["face_coverage"]) >= SIDE_PARTIAL and sup[name]["second_face"] and tgt[tgt_name]["second_face"]
                else "not_wall"
            ),
        }
    kinds = [s["wall_side"] for s in sides.values()]
    ious = [s["covered_interval_iou"] for s in sides.values() if s["covered_interval_iou"] is not None]
    bounded = all(k != "not_wall" for k in kinds)
    identical = bool(ious) and all(i is not None and i >= 0.98 for i in ious)
    return {
        "box_support_sheet": [round(v, 3) for v in box_support], "box_target_sheet": [round(v, 3) for v in box_target],
        "sides": sides, "wall_bounded_on_both_sheets": bounded, "wall_evidence_identical_on_both_sheets": identical,
        "side_kinds": dict(zip(sup, kinds)),
    }


def side_ownership(
    box: Sequence[float],
    segments: Mapping[str, Mapping[str, float]],
    owners: Mapping[str, Iterable[str]],
    grid_flags: Mapping[str, bool],
    *,
    tol: float = COORD_TOL,
    min_len: float = MIN_LEN,
) -> dict[str, dict[str, Any]]:
    """W4 source-primitive ownership behind each box side (which candidates own the primitives lying on the side).

    ``owners`` maps a source primitive id to every W4 candidate id that contains it; a primitive claimed by several
    candidates, or by none, means the side's wall evidence is candidate-level only (no unique physical-wall identity).
    """
    x0, y0, x1, y1 = (float(v) for v in box)
    out: dict[str, dict[str, Any]] = {}
    for name, orient, coord, lo, hi in (("x0", "V", x0, y0, y1), ("x1", "V", x1, y0, y1), ("y0", "H", y0, x0, x1), ("y1", "H", y1, x0, x1)):
        prims = []
        for pid, seg in segments.items():
            a, b, c, d = float(seg["x1"]), float(seg["y1"]), float(seg["x2"]), float(seg["y2"])
            if math.hypot(c - a, d - b) < min_len:
                continue
            if orient == "V" and abs(a - c) < AXIS_TOL and abs(a - coord) <= tol and min(b, d) < hi and max(b, d) > lo:
                prims.append(pid)
            elif orient == "H" and abs(b - d) < AXIS_TOL and abs(b - coord) <= tol and min(a, c) < hi and max(a, c) > lo:
                prims.append(pid)
        claimants: collections.Counter = collections.Counter()
        unowned = multi = 0
        for pid in sorted(prims):
            cands = set(owners.get(pid, ()))
            if not cands:
                unowned += 1
                continue
            multi += len(cands) > 1
            claimants.update(cands)
        out[name] = {
            "primitives_on_side": len(prims), "unowned_by_any_w4_candidate": unowned, "owned_by_multiple_candidates": multi,
            "distinct_candidates": len(claimants), "grid_opposed_candidates": sum(1 for c in claimants if grid_flags.get(c)),
        }
    return out


def ownership_blockers(ownership: Mapping[str, Mapping[str, Mapping[str, Any]]]) -> list[str]:
    """Authority blockers from side ownership on every page: any shared or unowned primitive keeps the relation at candidate level."""
    reasons: list[str] = []
    for page, sides in ownership.items():
        if any(v["owned_by_multiple_candidates"] for v in sides.values()):
            reasons.append(f"page_{page}_box_side_primitive_claimed_by_several_w4_candidates")
        if any(v["unowned_by_any_w4_candidate"] for v in sides.values()):
            reasons.append(f"page_{page}_box_side_primitive_unowned_by_w4")
    return reasons


def face_equivalence(
    face_polygon: Sequence[Sequence[float]],
    target_faces: Mapping[str, Sequence[Sequence[float]]],
    translation: Sequence[float],
    *,
    top: int = 3,
) -> list[dict[str, Any]]:
    """Every target-sheet face overlapping a support-sheet face under the translation, by IoU (all alternatives retained)."""
    from shapely.affinity import translate
    from shapely.geometry import Polygon

    moved = translate(Polygon(face_polygon).buffer(0), xoff=translation[0], yoff=translation[1])
    rows = []
    for face_id in sorted(target_faces):
        other = Polygon(target_faces[face_id]).buffer(0)
        if other.is_empty or not moved.intersects(other):
            continue
        inter = moved.intersection(other).area
        if inter <= 1e-6:
            continue
        rows.append({"face_id": face_id, "iou": round(inter / moved.union(other).area, 4), "area_pt2": round(other.area, 1)})
    rows.sort(key=lambda r: (-r["iou"], r["face_id"]))
    return rows[:top]


STANDING_AUTHORITY_BLOCKERS = (
    "support_page_has_no_source_owned_room_face_or_label_authority",
    "no_physical_wall_equivalence_authority_for_box_sides",
)


def classify_floor(
    correspondence: Mapping[str, Any],
    *,
    registration_unique: bool,
    marks_inside: Sequence[Mapping[str, Any]],
    other_labelled_boxes_overlapping: int,
    material_code: str,
    min_margin_pt: float = 5.0,
    authority_blockers: Sequence[str] = (),
) -> dict[str, Any]:
    """Typed outcome using existing EvidenceResolutionStatus values only (strings).

    The best this diagnostic can say is ``candidate``: geometric ownership consistent on both sheets.  It never emits
    ``corroborated`` because unique authenticated wall/face equivalence needs authorities that do not exist yet
    (``authority_blockers`` lists what is missing).
    """
    reasons: list[str] = []
    codes = collections.Counter(m["code"] for m in marks_inside)
    if not registration_unique:
        reasons.append("registration_not_unique")
    if not correspondence["wall_bounded_on_both_sheets"]:
        reasons.append("box_not_wall_bounded_on_both_sheets")
    elif not correspondence["wall_evidence_identical_on_both_sheets"]:
        reasons.append("wall_evidence_differs_between_sheets")
    if other_labelled_boxes_overlapping:
        reasons.append("overlapping_measured_boxes")
    if any(m["margin_pt"] < min_margin_pt for m in marks_inside):
        reasons.append("mark_too_close_to_box_side")
    if any(not m.get("registered_region", True) for m in marks_inside):
        reasons.append("mark_in_unregistered_region")
    if len(codes) > 1:
        status, reasons = "conflict", reasons + ["competing_finish_codes_in_box"]
    elif not codes:
        status, reasons = "abstained", reasons + ["no_finish_mark_in_box"]
    elif material_code not in codes:
        status, reasons = "abstained", reasons + ["box_owned_by_other_finish_code"]
    elif reasons:
        status = "abstained"
    else:
        status = "candidate"
        reasons = ["floor_geometrically_owned_equivalence_not_authenticated"]
    return {"status": status, "reason_codes": reasons, "finish_codes_in_box": dict(codes),
            "authority_blockers": list(authority_blockers) if status == "candidate" else [],
            "authenticated_physical_wall_face_equivalence": False}


# -------------------------------------------------------------------------------------- source-dependent steps
def _verify_source(pdf: Path) -> tuple[bytes, str]:
    payload = pdf.read_bytes()
    digest = hashlib.sha256(payload).hexdigest()
    if digest != EXPECTED_SHA256:
        raise ValueError("wrong Maryborough original source SHA")
    return payload, digest


def _native_segments(payload: bytes, page_number: int) -> list[dict[str, Any]]:
    import fitz
    from pb_vector_geometry_v130 import extract_native_page

    with fitz.open(stream=payload, filetype="pdf") as doc:
        return list(extract_native_page(doc[page_number - 1])["segments"])


def _w4_non_grid_evidence(payload: bytes, digest: str) -> dict[str, Any]:
    """W4 wall-candidate source primitives per page, minus producer-typed fully-grid-opposed candidates (unchanged producers)."""
    from pb_drawing_evidence_binding import DrawingViewType
    from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
    from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer, PhysicalWallCandidateSelector, _decision_scope_id
    from pb_source_composite_room_face_authority import _fully_grid_opposed_wall_evidence
    from pb_source_room_face_authority import SourceRoomFaceSelector, build_source_room_face_authority
    from pb_source_visibility_authority import SourceVisibilityProducer

    source = SourceVisibilityProducer(producer_method="claude-ft3-floor-correspondence", producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION)
    pub = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{digest[:32]}", source_bytes=payload, source_locator="memory://ft3-correspondence.pdf",
        page_ids=(str(SOURCE_PAGE), str(MARK_PAGE)),
    )
    out: dict[str, Any] = {}
    prod7 = PhysicalWallCandidateProducer.from_authenticated_viewports(source, page_ids=(str(SOURCE_PAGE),))
    auth7 = prod7.authority()
    published = source.published_snapshot_for_revision(pub.revision.revision_id)  # newest derived generation
    selectors = auth7.selectors_for_authenticated_viewports(
        document_id=published.revision.document_id, revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
        page_id=str(SOURCE_PAGE), view_type=DrawingViewType.FLOOR_PLAN.value,
    )
    if len(selectors) != 1:
        raise ValueError("source page must have exactly one authenticated floor-plan wall scope")
    scope7 = auth7.resolve_scope(selectors[0])
    prod11 = PhysicalWallCandidateProducer.from_source_visibility_producer(source, page_ids=(str(MARK_PAGE),))
    auth11 = prod11.authority()
    published = source.published_snapshot_for_revision(pub.revision.revision_id)
    scope11 = auth11.resolve_scope(PhysicalWallCandidateSelector(
        document_id=published.revision.document_id, revision_id=published.revision.revision_id, source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id, page_id=str(MARK_PAGE), decision_scope_id=_decision_scope_id(str(MARK_PAGE)),
    ))
    for page, scope, authority in ((SOURCE_PAGE, scope7, auth7), (MARK_PAGE, scope11, auth11)):
        grid_ids, _ = _fully_grid_opposed_wall_evidence(scope)
        kept, excluded = [], 0
        owners: dict[str, list[str]] = collections.defaultdict(list)
        for record in scope.records:
            for pid in record.physical_identity.source_primitive_ids:
                owners[pid].append(record.wall_candidate_id)
            if record.wall_candidate_id in grid_ids:
                excluded += 1
            else:
                kept.extend(record.physical_identity.source_primitive_ids)
        room_scope = build_source_room_face_authority(authority).resolve_scope(SourceRoomFaceSelector(
            document_id=scope.document_id, revision_id=scope.revision_id, source_sha256=scope.source_sha256,
            snapshot_id=scope.snapshot_id, page_id=scope.page_id, decision_scope_id=scope.decision_scope_id,
        ))
        out[str(page)] = {
            "w4_status": scope.status.value, "w4_scope_complete": bool(scope.scope_complete), "w4_reason_codes": list(scope.reason_codes),
            "w4_records": len(scope.records), "grid_opposed_excluded": excluded, "primitive_ids": sorted(set(kept)),
            "viewport_id": scope.viewport_id,
            "primitive_owners": {k: sorted(set(v)) for k, v in owners.items()},
            "grid_flags": {r.wall_candidate_id: r.wall_candidate_id in grid_ids for r in scope.records},
            "w5_status": room_scope.status.value, "w5_scope_complete": bool(room_scope.scope_complete),
            "faces_published": {f.face_id: {"record_id": f.record_id, "polygon": [list(p) for p in f.polygon_pdf_pts]} for f in room_scope.records},
            "faces_withheld": {f.face_id: [list(p) for p in f.polygon_pdf_pts] for f in room_scope.abstained_faces},
        }
    return out


def _capture_measured_floors(pdf: Path) -> dict[str, Any]:
    """Run the unchanged live claim once; observe the room-area producers' results in-process (no repository edit)."""
    import pb_cross_view_room_area_authority as cross_view
    import pb_same_view_room_area_authority as same_view
    from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
    from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim

    stash: dict[str, list[Any]] = {"cross": [], "same": []}
    original_cross, original_same = cross_view.CrossViewRoomAreaProducer.publish, same_view.SameViewRoomAreaProducer.publish

    def observe_cross(self):
        result = original_cross(self)
        stash["cross"].append(result)
        return result

    def observe_same(self):
        result = original_same(self)
        stash["same"].append(result)
        return result

    cross_view.CrossViewRoomAreaProducer.publish = observe_cross
    same_view.SameViewRoomAreaProducer.publish = observe_same
    try:
        claim = collect_live_physical_net_wall_claim(
            pdf, pages=(SOURCE_PAGE - 1,), topology_pages=(SOURCE_PAGE - 1,), room_area_support_pages=(MARK_PAGE - 1,),
        )
    finally:
        cross_view.CrossViewRoomAreaProducer.publish = original_cross
        same_view.SameViewRoomAreaProducer.publish = original_same
    floors_by_record = {f.source_room_face_record_id: f for f in claim.canonical_floors}
    floor_quantities = {
        str(dict(q.metadata or {}).get("upstream_room_area_quantity_id")): q for q in publish_live_floor_area_quantities(claim)
    }
    area_quantities = {q.input_entity_ids[0]: q for q in claim.room_area_quantity_evidence if not q.abstained and q.input_entity_ids}
    rooms_by_record = {r.source_room_face_record_id: r for r in claim.canonical_rooms}
    measured = []
    for result in stash["cross"] + stash["same"]:
        for record in result.records:
            meta = dict(record.area_evidence.metadata or {})
            box = meta.get("source_dimension_box_pdf_pts")
            floor = floors_by_record.get(record.source_room_face_record_id)
            room = rooms_by_record.get(record.source_room_face_record_id)
            quantity = next((q for q in claim.room_area_quantity_evidence if record.area_evidence.evidence_id in q.evidence_ids and not q.abstained), None)
            measured.append({
                "room_label": record.room_label, "area_evidence_id": record.area_evidence.evidence_id,
                "method": record.area_evidence.method, "area_m2": record.area_evidence.normalized_value,
                "source_dimension_page_id": meta.get("source_dimension_page_id"), "source_dimension_box_pdf_pts": box,
                "horizontal_value_mm": meta.get("horizontal_value_mm"), "vertical_value_mm": meta.get("vertical_value_mm"),
                "horizontal_dimension_id": getattr(record, "horizontal_dimension_id", None), "vertical_dimension_id": getattr(record, "vertical_dimension_id", None),
                "physical_room_id": record.physical_room_id, "source_room_face_record_id": record.source_room_face_record_id,
                "canonical_floor_id": getattr(floor, "canonical_floor_id", None), "physical_floor_surface_id": getattr(floor, "physical_floor_surface_id", None),
                "floor_polygon_pdf_pts": [list(p) for p in getattr(floor, "polygon_pdf_pts", ())],
                "room_area_quantity_id": getattr(quantity, "quantity_id", None),
                "floor_area_reissue_quantity_id": getattr(floor_quantities.get(getattr(quantity, "quantity_id", None)), "quantity_id", None),
                "room_polygon_pdf_pts": [list(p) for p in getattr(room, "polygon_pdf_pts", ())],
            })
    return {"measured_rooms": measured, "claim_status": getattr(claim.status, "value", str(claim.status)), "canonical_floor_count": len(claim.canonical_floors)}


def _plan_marks(payload: bytes, codes: Sequence[str]) -> list[dict[str, Any]]:
    import fitz

    wanted = {c.upper() for c in codes}
    marks = []
    with fitz.open(stream=payload, filetype="pdf") as doc:
        page = doc[MARK_PAGE - 1]
        for w in page.get_text("words", flags=fitz.TEXTFLAGS_WORDS):
            text = str(w[4]).strip().upper()
            if text in wanted:
                marks.append({"code": text, "native_bbox_pdf_pts": [round(float(v), 3) for v in w[:4]],
                              "native_source_address": [int(w[5]), int(w[6]), int(w[7])],
                              "center": [round((w[0] + w[2]) / 2, 3), round((w[1] + w[3]) / 2, 3)]})
    marks.sort(key=lambda m: (m["code"], m["center"][0], m["center"][1]))
    return marks


def _windowed(lines: Lines, center: Sequence[float], radius: float) -> Lines:
    out: dict[str, dict[float, list[tuple[float, float]]]] = {"H": {}, "V": {}}
    for k, ivs in lines["H"].items():
        if abs(k - center[1]) <= radius:
            kept = [(max(lo, center[0] - radius), min(hi, center[0] + radius)) for lo, hi in ivs if hi >= center[0] - radius and lo <= center[0] + radius]
            if kept:
                out["H"][k] = kept
    for k, ivs in lines["V"].items():
        if abs(k - center[0]) <= radius:
            kept = [(max(lo, center[1] - radius), min(hi, center[1] + radius)) for lo, hi in ivs if hi >= center[1] - radius and lo <= center[1] + radius]
            if kept:
                out["V"][k] = kept
    return out


def inspect_floor_correspondence(pdf: Path, *, material_code: str, finish_codes: Sequence[str], skip_claim: bool = False) -> dict[str, Any]:
    payload, digest = _verify_source(pdf)
    evidence = _w4_non_grid_evidence(payload, digest)
    lines: dict[int, Lines] = {}
    segments: dict[int, dict[str, Any]] = {}
    for page in (SOURCE_PAGE, MARK_PAGE):
        segments[page] = {seg["id"]: seg for seg in _native_segments(payload, page)}
        lines[page] = build_lines(segments[page][i] for i in evidence[str(page)]["primitive_ids"] if i in segments[page])
    # A. registration (p11 -> p7)
    ranking = rank_registrations(lines[MARK_PAGE], lines[SOURCE_PAGE])
    null = null_support(lines[MARK_PAGE], lines[SOURCE_PAGE])
    best = ranking[0]
    competitor = ranking[1] if len(ranking) > 1 else None
    nxt = best["next_distinct_min_support_pt"] or 0.0
    strongest_alt = max([r["min_support_pt"] for r in ranking[1:]] + [nxt])
    registration = {
        "p11_to_p7_hypotheses": ranking, "null_support_pt": null,
        "best": {k: best[k] for k in ("orientation", "scale", "dx", "dy", "min_support_pt")},
        "best_over_strongest_competitor": round(best["min_support_pt"] / strongest_alt, 2) if strongest_alt else None,
        "best_over_null_max": round(best["min_support_pt"] / max(null["max"], 1e-9), 1),
        "evidence_pt": {"p7_non_grid_wall_linework": round(total_length(lines[SOURCE_PAGE]), 1), "p11_non_grid_wall_linework": round(total_length(lines[MARK_PAGE]), 1)},
        "page_evidence": {p: {k: v for k, v in evidence[p].items() if k in ("w4_status", "w4_scope_complete", "w4_reason_codes", "w4_records", "grid_opposed_excluded", "viewport_id", "w5_status", "w5_scope_complete")} | {"faces_published": len(evidence[p]["faces_published"]), "faces_withheld": len(evidence[p]["faces_withheld"])} for p in evidence},
    }
    unique = best["orientation"] == "identity" and best["scale"] == 1.0 and best["min_support_pt"] >= 3.0 * max(strongest_alt, 1e-9) and best["min_support_pt"] >= 20.0 * max(null["max"], 1e-9)
    registration["unique"] = bool(unique)
    orientation, translation = best["orientation"], (best["dx"], best["dy"])
    # C. marks
    marks = _plan_marks(payload, finish_codes)
    index7 = LineIndex(lines[SOURCE_PAGE])
    for m in marks:
        win = _windowed(lines[MARK_PAGE], m["center"], MARK_WINDOW)
        local = rank_registrations(win, lines[SOURCE_PAGE], identity_only=True, identity_scales=(1.0,), topn=20)
        at_global = min_axis_support(orient_lines(win, D4[orientation]), index7, *translation)[0]
        m["local_registration"] = {"best_translation": [local[0]["dx"], local[0]["dy"]] if local else None, "best_support_pt": local[0]["min_support_pt"] if local else 0.0,
                                   "support_at_global_translation_pt": round(at_global, 1),
                                   "registered_region": bool(local and abs(local[0]["dx"] - translation[0]) <= 0.1 and abs(local[0]["dy"] - translation[1]) <= 0.1 and at_global >= 500.0)}
    result: dict[str, Any] = {
        "diagnostic_only": True, "source_sha256": digest, "support_page": MARK_PAGE, "target_page": SOURCE_PAGE, "material_code": material_code,
        "registration": registration, "plan_marks": marks, "measured_floors": [],
        "published_material_occurrences": 0, "published_floor_finish_quantities": 0, "customer_quantity_published": False,
        "benchmark_identity_assigned": False, "commercial_projection_allowed": False, "scale_or_metric_authority_granted": False,
    }
    if skip_claim:
        return result
    captured = _capture_measured_floors(pdf)
    result["live_claim"] = {k: v for k, v in captured.items() if k != "measured_rooms"}
    boxes = []
    for floor in captured["measured_rooms"]:
        box = floor["source_dimension_box_pdf_pts"]
        if not box or str(floor["source_dimension_page_id"]) != str(MARK_PAGE):
            floor["correspondence"] = {"status": "abstained", "reason_codes": ["measured_floor_without_support_page_dimension_box"]}
            result["measured_floors"].append(floor)
            continue
        boxes.append((floor, tuple(float(v) for v in box)))
    for floor, box in boxes:
        corr = box_correspondence(box, lines_support=lines[MARK_PAGE], lines_target=lines[SOURCE_PAGE], orientation=orientation, translation=translation)
        inside = [
            {"code": m["code"], "center": m["center"], "margin_pt": round(point_margin(m["center"], box), 2), "registered_region": m["local_registration"]["registered_region"]}
            for m in marks if point_margin(m["center"], box) > 0.0
        ]
        overlaps = sum(1 for other, ob in boxes if other is not floor and not (ob[2] <= box[0] or ob[0] >= box[2] or ob[3] <= box[1] or ob[1] >= box[3]))
        box_target = tuple(corr["box_target_sheet"])
        ownership = {
            str(MARK_PAGE): side_ownership(box, segments[MARK_PAGE], evidence[str(MARK_PAGE)]["primitive_owners"], evidence[str(MARK_PAGE)]["grid_flags"]),
            str(SOURCE_PAGE): side_ownership(box_target, segments[SOURCE_PAGE], evidence[str(SOURCE_PAGE)]["primitive_owners"], evidence[str(SOURCE_PAGE)]["grid_flags"]),
        }
        blockers = [*STANDING_AUTHORITY_BLOCKERS, *ownership_blockers(ownership)]
        if not evidence[str(SOURCE_PAGE)]["w4_scope_complete"]:
            blockers.append(f"page_{SOURCE_PAGE}_w4_scope_incomplete")
        floor["correspondence"] = {**classify_floor(corr, registration_unique=registration["unique"], marks_inside=inside, other_labelled_boxes_overlapping=overlaps,
                                                    material_code=material_code, authority_blockers=blockers),
                                   "geometry": corr, "marks_inside_box": inside, "w4_ownership_behind_box_sides": ownership}
        # competing placements: the same box test under every retained alternative translation of the identity orientation
        # (sheet-frame alignment, the best alias of each scale-1 hypothesis).  A wrong placement must fail to be wall-bounded.
        alt_translations = [(0.0, 0.0)] + [
            tuple(row["next_distinct_translation"]) for row in ranking
            if row["orientation"] == "identity" and row["scale"] == 1.0 and row["next_distinct_translation"] is not None
        ]
        alts = []
        for alt in dict.fromkeys(alt_translations):
            if abs(alt[0] - translation[0]) <= 0.1 and abs(alt[1] - translation[1]) <= 0.1:
                continue
            c2 = box_correspondence(box, lines_support=lines[MARK_PAGE], lines_target=lines[SOURCE_PAGE], orientation="identity", translation=alt)
            alts.append({"translation": [alt[0], alt[1]], "wall_bounded_on_both_sheets": c2["wall_bounded_on_both_sheets"], "side_kinds": c2["side_kinds"]})
        floor["correspondence"]["competing_registrations_box_test"] = alts
        result["measured_floors"].append(floor)
    face_index_support = {**{k: v["polygon"] for k, v in evidence[str(MARK_PAGE)]["faces_published"].items()}, **evidence[str(MARK_PAGE)]["faces_withheld"]}
    face_index_target = {**{k: v["polygon"] for k, v in evidence[str(SOURCE_PAGE)]["faces_published"].items()}, **evidence[str(SOURCE_PAGE)]["faces_withheld"]}
    record_to_face = {v["record_id"]: k for k, v in evidence[str(SOURCE_PAGE)]["faces_published"].items()}
    measured_faces = {f["room_label"]: record_to_face.get(f["source_room_face_record_id"]) for f in result["measured_floors"]}
    from shapely.geometry import Point, Polygon

    for m in marks:
        if m["code"] != material_code:
            continue
        holders = [fid for fid, poly in sorted(face_index_support.items()) if Polygon(poly).buffer(0).contains(Point(*m["center"]))]
        equiv = [face_equivalence(face_index_support[fid], face_index_target, translation) for fid in holders]
        in_boxes = [f["room_label"] for f in result["measured_floors"] if "marks_inside_box" in f["correspondence"]
                    and any(mi["center"] == m["center"] for mi in f["correspondence"]["marks_inside_box"])]
        reasons = []
        if not m["local_registration"]["registered_region"]:
            reasons.append("mark_in_unregistered_region")
        if not in_boxes:
            reasons.append("outside_every_measured_box")
        for f in result["measured_floors"]:
            if f["room_label"] in in_boxes and f["correspondence"]["status"] != "candidate":
                reasons += [f"{f['room_label']}:{r}" for r in f["correspondence"]["reason_codes"]]
        top = equiv[0][0] if equiv and equiv[0] else None
        if top is not None and top["face_id"] in measured_faces.values():
            face_join = "mark_face_is_measured_floor_face"
        else:
            face_join = "mark_face_differs_from_measured_floor_face_only_the_dimension_box_relates_them" if in_boxes else "no_measured_floor_face"
        m["binding"] = {"inside_measured_boxes": in_boxes, "support_page_faces_containing_mark": [h[-12:] for h in holders],
                        "target_page_face_alternatives_by_iou": equiv, "face_level_join": face_join, "blockers_before_any_binding": reasons}
    owners = [f for f in result["measured_floors"] if f["correspondence"]["status"] == "candidate"]
    result["geometric_candidate_owner_floors"] = [
        {k: f[k] for k in ("room_label", "canonical_floor_id", "physical_floor_surface_id", "physical_room_id", "source_room_face_record_id",
                           "area_evidence_id", "room_area_quantity_id", "floor_area_reissue_quantity_id", "area_m2")} for f in owners
    ]
    result["first_unclosed_gate"] = (
        "geometric_candidate_owner_found_authenticated_equivalence_and_material_authority_still_required"
        if owners else "no_measured_floor_geometrically_owned_by_material_marks"
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--material-code", default="FT3")
    parser.add_argument("--finish-codes", default="EPX,FT1,FT2,FT3")
    parser.add_argument("--skip-claim", action="store_true", help="registration and marks only (no live claim; no measured floors)")
    args = parser.parse_args(argv)
    report = inspect_floor_correspondence(args.pdf, material_code=args.material_code.upper(),
                                          finish_codes=[c.strip() for c in args.finish_codes.split(",") if c.strip()], skip_claim=args.skip_claim)
    text = json.dumps(report, sort_keys=True, indent=2, default=str) + "\n"
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    summary = {
        "registration": report["registration"]["best"], "registration_unique": report["registration"]["unique"],
        "best_over_strongest_competitor": report["registration"]["best_over_strongest_competitor"],
        "floors": [(f["room_label"], f["correspondence"]["status"], f["correspondence"]["reason_codes"]) for f in report["measured_floors"]],
        "geometric_candidate_owner_floors": [f["room_label"] for f in report.get("geometric_candidate_owner_floors", [])],
    }
    print(json.dumps(summary, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
