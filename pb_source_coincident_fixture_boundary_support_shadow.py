"""Generic bounded coincident fixture/finish-edge boundary corroboration shadow.

Shadow-only, default-off source-evidence module. Does NOT widen structural wall
snap tolerances globally and does NOT grant commercial publication authority.

Primary support requires four structural wall sides at standard snap tolerance.
When exactly three sides have structural wall support and the fourth side abuts
a built-in fixture or finish transition (e.g., bath hob, shower tray, cabinetry
edge), this module evaluates whether the fourth side carries an exact coincident
continuous boundary stroke backed by an exterior structural wall within a
bounded fixture depth and corroborated by interior finish hatching.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

SHADOW_SCHEMA_VERSION = "1.0.0"

DEFAULT_STRUCTURAL_SNAP_PT = 2.5
DEFAULT_STRUCTURAL_MIN_WIDTH_PT = 0.72
DEFAULT_STRUCTURAL_MAX_WIDTH_PT = 2.40
DEFAULT_STRUCTURAL_MIN_COVERAGE = 0.40

DEFAULT_COINCIDENT_TOLERANCE_PT = 0.25
DEFAULT_COINCIDENT_MIN_WIDTH_PT = 0.40
DEFAULT_COINCIDENT_MIN_COVERAGE = 0.90

DEFAULT_BACKING_WALL_MIN_OFFSET_PT = 2.5
DEFAULT_BACKING_WALL_MAX_OFFSET_PT = 35.0
DEFAULT_BACKING_WALL_MIN_COVERAGE = 0.15


@dataclass(frozen=True)
class BoundarySideEvidence:
    side: str
    structural_coverage: float
    structural_path_ids: tuple[int, ...]
    structural_passed: bool
    coincident_coverage: float = 0.0
    coincident_path_ids: tuple[int, ...] = ()
    backing_wall_coverage: float = 0.0
    backing_wall_path_ids: tuple[int, ...] = ()
    coincident_fixture_passed: bool = False


@dataclass(frozen=True)
class CoincidentFixtureBoundarySupportResult:
    status: str
    source_sha256: str
    page_number: int
    supported: bool
    support_mode: str
    structural_sides_passed: int
    coincident_fixture_side: str | None
    side_evidence: tuple[BoundarySideEvidence, ...]
    all_support_path_ids: tuple[int, ...]
    reason_codes: tuple[str, ...]
    commercial_projection_allowed: bool = False
    shadow_only: bool = True
    schema_version: str = SHADOW_SCHEMA_VERSION


def _is_black_stroke(path: Mapping[str, Any]) -> bool:
    if path.get("type") != "s":
        return False
    color = path.get("color")
    if not color or len(color) != 3:
        return False
    return all(isinstance(c, (int, float)) and abs(float(c)) <= 1e-6 for c in color)


def _iter_line_segments(path: Mapping[str, Any]) -> list[tuple[float, float, float, float]]:
    segs: list[tuple[float, float, float, float]] = []
    for item in path.get("items") or ():
        if not item:
            continue
        op = item[0]
        if op == "l" and len(item) >= 3:
            p1, p2 = item[1], item[2]
            x1 = float(p1.x if hasattr(p1, "x") else p1[0])
            y1 = float(p1.y if hasattr(p1, "y") else p1[1])
            x2 = float(p2.x if hasattr(p2, "x") else p2[0])
            y2 = float(p2.y if hasattr(p2, "y") else p2[1])
            segs.append((x1, y1, x2, y2))
        elif op == "re" and len(item) >= 2:
            r = item[1]
            rx0 = float(r.x0 if hasattr(r, "x0") else r[0])
            ry0 = float(r.y0 if hasattr(r, "y0") else r[1])
            rx1 = float(r.x1 if hasattr(r, "x1") else r[2])
            ry1 = float(r.y1 if hasattr(r, "y1") else r[3])
            segs.extend((
                (rx0, ry0, rx1, ry0),
                (rx1, ry0, rx1, ry1),
                (rx1, ry1, rx0, ry1),
                (rx0, ry1, rx0, ry0),
            ))
    return segs


def _union_coverage(intervals: Sequence[tuple[float, float, int]], span: float) -> float:
    if not intervals or span <= 0.0:
        return 0.0
    ordered = sorted((a, b) for a, b, _ in intervals)
    merged: list[list[float]] = []
    for lo, hi in ordered:
        if not merged or lo > merged[-1][1] + 0.05:
            merged.append([lo, hi])
        else:
            merged[-1][1] = max(merged[-1][1], hi)
    return sum(b - a for a, b in merged) / span


def _collect_aligned_intervals(
    drawings: Sequence[Mapping[str, Any]],
    *,
    side: str,
    at: float,
    start: float,
    end: float,
    min_width: float,
    max_width: float,
    min_signed_offset: float,
    max_signed_offset: float,
    exclude_path_id: int | None = None,
) -> list[tuple[float, float, int]]:
    """Collect axis-aligned black stroke intervals matching exact signed offset band.

    Signed offset is measured positively toward the exterior of the bbox:
      L: at - x   (exterior is x < at)
      R: x - at   (exterior is x > at)
      T: at - y   (exterior is y < at)
      B: y - at   (exterior is y > at)
    """
    intervals: list[tuple[float, float, int]] = []
    for path_id, path in enumerate(drawings):
        if exclude_path_id is not None and path_id == exclude_path_id:
            continue
        if not _is_black_stroke(path):
            continue
        width = path.get("width")
        if not isinstance(width, (int, float)):
            continue
        w_val = float(width)
        if not (min_width <= w_val <= max_width):
            continue
        for x1, y1, x2, y2 in _iter_line_segments(path):
            if side in ("L", "R"):
                if abs(x1 - x2) > 0.15:
                    continue
                coord = 0.5 * (x1 + x2)
                signed_off = (at - coord) if side == "L" else (coord - at)
                low, high = (y1, y2) if y1 <= y2 else (y2, y1)
            else:
                if abs(y1 - y2) > 0.15:
                    continue
                coord = 0.5 * (y1 + y2)
                signed_off = (at - coord) if side == "T" else (coord - at)
                low, high = (x1, x2) if x1 <= x2 else (x2, x1)
            if not (min_signed_offset <= signed_off <= max_signed_offset):
                continue
            lo = max(start, low)
            hi = min(end, high)
            if hi - lo > 0.1:
                intervals.append((lo, hi, path_id))
    return intervals


def evaluate_coincident_fixture_boundary_support_shadow(
    *,
    drawings: Sequence[Mapping[str, Any]],
    bbox_pts: tuple[float, float, float, float],
    source_sha256: str,
    page_number: int,
    hatch_support_count: int,
    exclude_ring_path_id: int | None = None,
    structural_snap_pt: float = DEFAULT_STRUCTURAL_SNAP_PT,
    structural_min_width_pt: float = DEFAULT_STRUCTURAL_MIN_WIDTH_PT,
    structural_max_width_pt: float = DEFAULT_STRUCTURAL_MAX_WIDTH_PT,
    structural_min_coverage: float = DEFAULT_STRUCTURAL_MIN_COVERAGE,
    coincident_tolerance_pt: float = DEFAULT_COINCIDENT_TOLERANCE_PT,
    coincident_min_width_pt: float = DEFAULT_COINCIDENT_MIN_WIDTH_PT,
    coincident_min_coverage: float = DEFAULT_COINCIDENT_MIN_COVERAGE,
    backing_wall_min_offset_pt: float = DEFAULT_BACKING_WALL_MIN_OFFSET_PT,
    backing_wall_max_offset_pt: float = DEFAULT_BACKING_WALL_MAX_OFFSET_PT,
    backing_wall_min_coverage: float = DEFAULT_BACKING_WALL_MIN_COVERAGE,
) -> CoincidentFixtureBoundarySupportResult:
    """Evaluate 4-side structural or bounded 3-wall + 1-coincident-fixture support."""
    if not isinstance(source_sha256, str) or len(source_sha256.strip()) < 16 or page_number < 1:
        return CoincidentFixtureBoundarySupportResult(
            status="ABSTAINED",
            source_sha256=str(source_sha256 or ""),
            page_number=int(page_number) if isinstance(page_number, int) else 0,
            supported=False,
            support_mode="none",
            structural_sides_passed=0,
            coincident_fixture_side=None,
            side_evidence=(),
            all_support_path_ids=(),
            reason_codes=("source_provenance_incomplete",),
        )

    x0, y0, x1, y1 = (float(v) for v in bbox_pts)
    if x1 <= x0 or y1 <= y0:
        return CoincidentFixtureBoundarySupportResult(
            status="ABSTAINED",
            source_sha256=source_sha256,
            page_number=page_number,
            supported=False,
            support_mode="none",
            structural_sides_passed=0,
            coincident_fixture_side=None,
            side_evidence=(),
            all_support_path_ids=(),
            reason_codes=("degenerate_room_bbox",),
        )

    sides_spec = (
        ("L", x0, y0, y1),
        ("R", x1, y0, y1),
        ("T", y0, x0, x1),
        ("B", y1, x0, x1),
    )

    prelim: list[BoundarySideEvidence] = []
    missing_sides: list[tuple[str, float, float, float]] = []
    for side, at, start, end in sides_spec:
        span = end - start
        ivs = _collect_aligned_intervals(
            drawings,
            side=side,
            at=at,
            start=start,
            end=end,
            min_width=structural_min_width_pt,
            max_width=structural_max_width_pt,
            min_signed_offset=-structural_snap_pt,
            max_signed_offset=structural_snap_pt,
            exclude_path_id=exclude_ring_path_id,
        )
        cov = _union_coverage(ivs, span)
        pids = tuple(sorted({pid for _, _, pid in ivs}))
        passed = cov >= structural_min_coverage
        prelim.append(
            BoundarySideEvidence(
                side=side,
                structural_coverage=round(cov, 4),
                structural_path_ids=pids,
                structural_passed=passed,
            )
        )
        if not passed:
            missing_sides.append((side, at, start, end))

    structural_passed_count = 4 - len(missing_sides)
    if structural_passed_count == 4:
        all_ids = tuple(sorted({pid for ev in prelim for pid in ev.structural_path_ids}))
        return CoincidentFixtureBoundarySupportResult(
            status="CORROBORATED_FOUR_WALL_SUPPORT",
            source_sha256=source_sha256,
            page_number=page_number,
            supported=True,
            support_mode="four_structural_walls",
            structural_sides_passed=4,
            coincident_fixture_side=None,
            side_evidence=tuple(prelim),
            all_support_path_ids=all_ids,
            reason_codes=("four_side_structural_wall_support_verified",),
        )

    if structural_passed_count < 3:
        return CoincidentFixtureBoundarySupportResult(
            status="ABSTAINED",
            source_sha256=source_sha256,
            page_number=page_number,
            supported=False,
            support_mode="none",
            structural_sides_passed=structural_passed_count,
            coincident_fixture_side=None,
            side_evidence=tuple(prelim),
            all_support_path_ids=(),
            reason_codes=("insufficient_structural_wall_sides",),
        )

    # Exactly 3 structural sides passed: inspect the single remaining side under strict coincident rules.
    miss_side, miss_at, miss_start, miss_end = missing_sides[0]
    miss_span = miss_end - miss_start

    # Check exact coincident finish/fixture boundary stroke (0.40 <= w < structural_min_width, |off| <= 0.25pt)
    coinc_ivs = _collect_aligned_intervals(
        drawings,
        side=miss_side,
        at=miss_at,
        start=miss_start,
        end=miss_end,
        min_width=coincident_min_width_pt,
        max_width=max(coincident_min_width_pt, structural_min_width_pt - 1e-6),
        min_signed_offset=-coincident_tolerance_pt,
        max_signed_offset=coincident_tolerance_pt,
        exclude_path_id=exclude_ring_path_id,
    )
    coinc_cov = _union_coverage(coinc_ivs, miss_span)
    coinc_pids = tuple(sorted({pid for _, _, pid in coinc_ivs}))

    # Check exterior structural backing wall beyond built-in fixture depth (2.5 < off <= 35pt)
    back_ivs = _collect_aligned_intervals(
        drawings,
        side=miss_side,
        at=miss_at,
        start=miss_start,
        end=miss_end,
        min_width=structural_min_width_pt,
        max_width=structural_max_width_pt,
        min_signed_offset=backing_wall_min_offset_pt + 1e-6,
        max_signed_offset=backing_wall_max_offset_pt,
        exclude_path_id=exclude_ring_path_id,
    )
    back_cov = _union_coverage(back_ivs, miss_span)
    back_pids = tuple(sorted({pid for _, _, pid in back_ivs}))

    reasons: list[str] = []
    if hatch_support_count < 1:
        reasons.append("interior_finish_hatch_uncorroborated")
    if not coinc_ivs:
        reasons.append("coincident_boundary_stroke_unavailable")
    elif coinc_cov < coincident_min_coverage:
        reasons.append("coincident_boundary_coverage_incomplete")
    if back_cov < backing_wall_min_coverage:
        reasons.append("exterior_structural_backing_wall_unavailable")

    coinc_passed = len(reasons) == 0
    updated: list[BoundarySideEvidence] = []
    for ev in prelim:
        if ev.side == miss_side:
            updated.append(
                BoundarySideEvidence(
                    side=ev.side,
                    structural_coverage=ev.structural_coverage,
                    structural_path_ids=ev.structural_path_ids,
                    structural_passed=False,
                    coincident_coverage=round(coinc_cov, 4),
                    coincident_path_ids=coinc_pids,
                    backing_wall_coverage=round(back_cov, 4),
                    backing_wall_path_ids=back_pids,
                    coincident_fixture_passed=coinc_passed,
                )
            )
        else:
            updated.append(ev)

    if coinc_passed:
        all_ids = tuple(
            sorted(
                {pid for ev in updated for pid in (*ev.structural_path_ids, *ev.coincident_path_ids, *ev.backing_wall_path_ids)}
            )
        )
        return CoincidentFixtureBoundarySupportResult(
            status="CORROBORATED_THREE_WALL_PLUS_COINCIDENT_FIXTURE_BOUNDARY",
            source_sha256=source_sha256,
            page_number=page_number,
            supported=True,
            support_mode="three_structural_walls_plus_coincident_fixture_edge",
            structural_sides_passed=3,
            coincident_fixture_side=miss_side,
            side_evidence=tuple(updated),
            all_support_path_ids=all_ids,
            reason_codes=("three_structural_walls_plus_exact_coincident_fixture_boundary_verified",),
        )

    return CoincidentFixtureBoundarySupportResult(
        status="ABSTAINED",
        source_sha256=source_sha256,
        page_number=page_number,
        supported=False,
        support_mode="none",
        structural_sides_passed=3,
        coincident_fixture_side=None,
        side_evidence=tuple(updated),
        all_support_path_ids=(),
        reason_codes=tuple(reasons),
    )
