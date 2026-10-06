"""Shadow evidence for dense orthogonal drafting lattices in wall candidates.

This module is descriptive only. It never removes a source segment, changes a
PhysicalWallCandidate, alters physical equivalence, or raises/lowers wall
authority.

The evaluator looks for a deliberately narrow source pattern:
- producer-owned native line primitives from singleton source paths;
- explicit solid stroke, explicit finite positive width, no fill;
- exact horizontal/vertical geometry;
- the thinnest explicit stroke family only when the drawing contains more than
  one distinct explicit width;
- the same source graphic-state family occurs in both orthogonal directions;
- parallel members exhibit repeated source-derived spacing; and
- the candidate intersects multiple perpendicular members of that same family.

The spacing tolerance is derived from the source stroke width itself. No project,
page, room, coordinate, expected quantity, or benchmark value participates.

A positive finding means only "grid-like source evidence is present". It is not
permission to delete or demote a physical wall candidate.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
from types import MappingProxyType
from typing import Any, Mapping, Optional, Sequence

from pb_migration_contracts import stable_contract_id


PHYSICAL_WALL_DENSE_LATTICE_SHADOW_SCHEMA_VERSION = "1.0.0"
DENSE_LATTICE_EVALUATED = "evaluated"
DENSE_LATTICE_UNAVAILABLE = "unavailable"
DENSE_LATTICE_GRID_LIKE = "dense_orthogonal_lattice_source_evidence"

_COORD_TOL = 1e-6
_MIN_PARALLEL_GAP_SUPPORT = 3
_MIN_PERPENDICULAR_INTERSECTIONS = 2


@dataclass(frozen=True)
class PhysicalWallDenseLatticeFinding:
    finding_id: str
    wall_candidate_id: str
    source_primitive_ids: tuple[str, ...]
    orientation: str
    family_width_pt: float
    parallel_coordinate_count: int
    perpendicular_coordinate_count: int
    repeated_parallel_gap_count: int
    perpendicular_intersection_count: int
    representative_spacing_pt: float
    reason_codes: tuple[str, ...]


@dataclass(frozen=True)
class PhysicalWallDenseLatticeShadowEvaluation:
    status: str
    reason_code: Optional[str]
    page_id: str
    decision_scope_id: str
    evaluated_wall_candidate_ids: tuple[str, ...]
    grid_like_wall_candidate_ids: tuple[str, ...]
    findings: tuple[PhysicalWallDenseLatticeFinding, ...]
    schema_version: str = PHYSICAL_WALL_DENSE_LATTICE_SHADOW_SCHEMA_VERSION

    @property
    def findings_by_wall_id(self) -> Mapping[str, PhysicalWallDenseLatticeFinding]:
        return MappingProxyType(
            {item.wall_candidate_id: item for item in self.findings}
        )

    def is_grid_like(self, wall_candidate_id: str) -> bool:
        if self.status != DENSE_LATTICE_EVALUATED:
            return False
        return str(wall_candidate_id) in set(self.grid_like_wall_candidate_ids)


def unavailable_physical_wall_dense_lattice_shadow(
    *,
    page_id: str,
    decision_scope_id: str,
    reason_code: str,
) -> PhysicalWallDenseLatticeShadowEvaluation:
    return PhysicalWallDenseLatticeShadowEvaluation(
        status=DENSE_LATTICE_UNAVAILABLE,
        reason_code=str(reason_code),
        page_id=str(page_id),
        decision_scope_id=str(decision_scope_id),
        evaluated_wall_candidate_ids=(),
        grid_like_wall_candidate_ids=(),
        findings=(),
    )


def _stable_source_value(value: Any) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        return round(value, 9)
    if isinstance(value, int):
        return value
    if isinstance(value, (list, tuple)):
        return tuple(_stable_source_value(item) for item in value)
    if isinstance(value, Mapping):
        return tuple(
            sorted(
                (str(key), _stable_source_value(item))
                for key, item in value.items()
            )
        )
    return str(value)


def _solid_dashes(value: object) -> bool:
    compact = " ".join(str(value or "").strip().split())
    return compact in {"", "[]", "[] 0", "[ ] 0"}


def _orientation(segment: Mapping[str, Any]) -> Optional[str]:
    try:
        x1 = float(segment["x1"])
        y1 = float(segment["y1"])
        x2 = float(segment["x2"])
        y2 = float(segment["y2"])
    except (KeyError, TypeError, ValueError, OverflowError):
        return None
    if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
        return None
    if abs(y2 - y1) <= _COORD_TOL and abs(x2 - x1) > _COORD_TOL:
        return "horizontal"
    if abs(x2 - x1) <= _COORD_TOL and abs(y2 - y1) > _COORD_TOL:
        return "vertical"
    return None


def _style_key(segment: Mapping[str, Any]) -> Optional[tuple[object, ...]]:
    if str(segment.get("kind") or "") != "line":
        return None
    if _orientation(segment) is None:
        return None
    if not bool(segment.get("width_present", False)):
        return None
    if not bool(segment.get("stroke_present", False)):
        return None
    if bool(segment.get("fill_present", False)):
        return None
    if bool(segment.get("layer_present", False)) and "wall" in str(
        segment.get("layer") or ""
    ).lower():
        return None
    if bool(segment.get("dashes_present", False)) and not _solid_dashes(
        segment.get("dashes")
    ):
        return None
    try:
        width = float(segment.get("width"))
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(width) or width <= 0.0:
        return None
    return (
        round(width, 9),
        _stable_source_value(segment.get("stroke")),
        _solid_dashes(segment.get("dashes")),
    )


def _axis_coordinate(segment: Mapping[str, Any], orientation: str) -> float:
    if orientation == "horizontal":
        return round((float(segment["y1"]) + float(segment["y2"])) * 0.5, 6)
    return round((float(segment["x1"]) + float(segment["x2"])) * 0.5, 6)


def _segment_interval(
    segment: Mapping[str, Any], orientation: str
) -> tuple[float, float]:
    if orientation == "horizontal":
        values = (float(segment["x1"]), float(segment["x2"]))
    else:
        values = (float(segment["y1"]), float(segment["y2"]))
    return tuple(sorted(values))


def _distinct_coordinates(
    segments: Sequence[Mapping[str, Any]], orientation: str
) -> tuple[float, ...]:
    return tuple(
        sorted(
            {
                _axis_coordinate(segment, orientation)
                for segment in segments
                if _orientation(segment) == orientation
            }
        )
    )


def _spacing_support(
    coordinates: Sequence[float],
    *,
    tolerance: float,
) -> tuple[float, int]:
    values = tuple(sorted(float(value) for value in coordinates))
    gaps = tuple(
        right - left
        for left, right in zip(values, values[1:])
        if right - left > _COORD_TOL
    )
    if not gaps:
        return 0.0, 0

    candidates = []
    for gap in gaps:
        support = sum(
            1 for other in gaps if abs(float(other) - float(gap)) <= tolerance
        )
        candidates.append((support, float(gap)))
    support, representative = max(
        candidates,
        key=lambda item: (item[0], -item[1]),
    )
    return representative, support


def _candidate_intersects_perpendicular(
    candidate_segments: Sequence[Mapping[str, Any]],
    *,
    orientation: str,
    perpendicular_segments: Sequence[Mapping[str, Any]],
) -> int:
    crossing_coordinates: set[float] = set()
    for candidate in candidate_segments:
        c0, c1 = _segment_interval(candidate, orientation)
        fixed = _axis_coordinate(candidate, orientation)
        for other in perpendicular_segments:
            if orientation == "horizontal":
                other_fixed = _axis_coordinate(other, "vertical")
                o0, o1 = _segment_interval(other, "vertical")
            else:
                other_fixed = _axis_coordinate(other, "horizontal")
                o0, o1 = _segment_interval(other, "horizontal")
            if (
                c0 - _COORD_TOL <= other_fixed <= c1 + _COORD_TOL
                and o0 - _COORD_TOL <= fixed <= o1 + _COORD_TOL
            ):
                crossing_coordinates.add(round(other_fixed, 6))
    return len(crossing_coordinates)


def _candidate_on_repeated_spacing(
    candidate_segments: Sequence[Mapping[str, Any]],
    *,
    orientation: str,
    family_coordinates: Sequence[float],
    representative_spacing: float,
    tolerance: float,
) -> bool:
    if representative_spacing <= 0.0:
        return False
    family = tuple(sorted(float(value) for value in family_coordinates))
    candidate_coords = {
        _axis_coordinate(segment, orientation)
        for segment in candidate_segments
    }
    for coordinate in candidate_coords:
        if coordinate not in family:
            continue
        index = family.index(coordinate)
        neighbor_gaps = []
        if index > 0:
            neighbor_gaps.append(coordinate - family[index - 1])
        if index + 1 < len(family):
            neighbor_gaps.append(family[index + 1] - coordinate)
        if any(
            abs(gap - representative_spacing) <= tolerance
            for gap in neighbor_gaps
        ):
            return True
    return False


def evaluate_physical_wall_dense_lattice_shadow(
    *,
    records: Sequence[object],
    source_segments: Sequence[Mapping[str, Any]],
    page_id: str,
    decision_scope_id: str,
) -> PhysicalWallDenseLatticeShadowEvaluation:
    """Describe grid-like wall candidates without changing any authority."""

    segments = tuple(source_segments)
    by_id: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    path_counts: Counter[object] = Counter()
    explicit_widths: set[float] = set()

    for segment in segments:
        raw_id = str(segment.get("id") or "").strip()
        if raw_id:
            by_id[raw_id].append(segment)
        path_counts[segment.get("path_index")] += 1
        if bool(segment.get("width_present", False)):
            try:
                width = float(segment.get("width"))
            except (TypeError, ValueError, OverflowError):
                continue
            if math.isfinite(width) and width > 0.0:
                explicit_widths.add(round(width, 9))

    # Drawing-relative "thin" evidence is meaningful only when the source has
    # more than one explicit finite width.
    if len(explicit_widths) < 2:
        return PhysicalWallDenseLatticeShadowEvaluation(
            status=DENSE_LATTICE_EVALUATED,
            reason_code=None,
            page_id=str(page_id),
            decision_scope_id=str(decision_scope_id),
            evaluated_wall_candidate_ids=tuple(
                sorted(
                    str(getattr(record, "wall_candidate_id", ""))
                    for record in records
                    if str(getattr(record, "wall_candidate_id", ""))
                )
            ),
            grid_like_wall_candidate_ids=(),
            findings=(),
        )
    minimum_width = min(explicit_widths)

    eligible_segments: list[Mapping[str, Any]] = []
    for segment in segments:
        style = _style_key(segment)
        if style is None or float(style[0]) != minimum_width:
            continue
        path_index = segment.get("path_index")
        if path_index is None or path_counts[path_index] != 1:
            continue
        eligible_segments.append(segment)

    style_groups: dict[
        tuple[object, ...], dict[str, list[Mapping[str, Any]]]
    ] = defaultdict(lambda: {"horizontal": [], "vertical": []})
    for segment in eligible_segments:
        style = _style_key(segment)
        orientation = _orientation(segment)
        if style is not None and orientation is not None:
            style_groups[style][orientation].append(segment)

    evaluated_ids: list[str] = []
    findings: list[PhysicalWallDenseLatticeFinding] = []

    for record in records:
        wall_id = str(getattr(record, "wall_candidate_id", "")).strip()
        if not wall_id:
            continue
        evaluated_ids.append(wall_id)
        candidate = getattr(record, "wall_candidate", None)
        identity = getattr(record, "physical_identity", None)
        if (
            candidate is None
            or str(getattr(candidate, "representation", "")) != "single_line"
            or identity is None
        ):
            continue

        source_ids = tuple(
            sorted(
                dict.fromkeys(
                    str(value)
                    for value in tuple(
                        getattr(identity, "source_primitive_ids", ()) or ()
                    )
                    if str(value)
                )
            )
        )
        if not source_ids:
            continue

        candidate_segments: list[Mapping[str, Any]] = []
        ambiguous_source = False
        for source_id in source_ids:
            matches = tuple(by_id.get(source_id, ()))
            if len(matches) != 1:
                ambiguous_source = True
                break
            candidate_segments.append(matches[0])
        if ambiguous_source or not candidate_segments:
            continue

        styles = {_style_key(segment) for segment in candidate_segments}
        orientations = {_orientation(segment) for segment in candidate_segments}
        if None in styles or None in orientations:
            continue
        if len(styles) != 1 or len(orientations) != 1:
            continue

        style = next(iter(styles))
        orientation = next(iter(orientations))
        if style is None or orientation is None:
            continue
        if float(style[0]) != minimum_width:
            continue
        if any(
            segment not in eligible_segments
            for segment in candidate_segments
        ):
            continue

        family = style_groups.get(style)
        if not family:
            continue
        perpendicular = "vertical" if orientation == "horizontal" else "horizontal"
        parallel_segments = tuple(family[orientation])
        perpendicular_segments = tuple(family[perpendicular])
        parallel_coordinates = _distinct_coordinates(
            parallel_segments, orientation
        )
        perpendicular_coordinates = _distinct_coordinates(
            perpendicular_segments, perpendicular
        )
        width_tolerance = max(float(style[0]), _COORD_TOL)
        representative_spacing, spacing_support = _spacing_support(
            parallel_coordinates,
            tolerance=width_tolerance,
        )
        if spacing_support < _MIN_PARALLEL_GAP_SUPPORT:
            continue
        if not _candidate_on_repeated_spacing(
            candidate_segments,
            orientation=orientation,
            family_coordinates=parallel_coordinates,
            representative_spacing=representative_spacing,
            tolerance=width_tolerance,
        ):
            continue
        intersections = _candidate_intersects_perpendicular(
            candidate_segments,
            orientation=orientation,
            perpendicular_segments=perpendicular_segments,
        )
        if intersections < _MIN_PERPENDICULAR_INTERSECTIONS:
            continue

        family_payload = {
            "style": style,
            "parallel_coordinate_count": len(parallel_coordinates),
            "perpendicular_coordinate_count": len(perpendicular_coordinates),
            "representative_spacing_pt": round(representative_spacing, 6),
        }
        finding_id = stable_contract_id(
            "physical_wall_dense_lattice_shadow",
            {
                "wall_candidate_id": wall_id,
                "source_primitive_ids": source_ids,
                "family": family_payload,
            },
            digest_chars=32,
        )
        findings.append(
            PhysicalWallDenseLatticeFinding(
                finding_id=finding_id,
                wall_candidate_id=wall_id,
                source_primitive_ids=source_ids,
                orientation=orientation,
                family_width_pt=float(style[0]),
                parallel_coordinate_count=len(parallel_coordinates),
                perpendicular_coordinate_count=len(perpendicular_coordinates),
                repeated_parallel_gap_count=spacing_support,
                perpendicular_intersection_count=intersections,
                representative_spacing_pt=round(representative_spacing, 6),
                reason_codes=(DENSE_LATTICE_GRID_LIKE,),
            )
        )

    ordered_findings = tuple(
        sorted(findings, key=lambda item: item.wall_candidate_id)
    )
    return PhysicalWallDenseLatticeShadowEvaluation(
        status=DENSE_LATTICE_EVALUATED,
        reason_code=None,
        page_id=str(page_id),
        decision_scope_id=str(decision_scope_id),
        evaluated_wall_candidate_ids=tuple(sorted(set(evaluated_ids))),
        grid_like_wall_candidate_ids=tuple(
            item.wall_candidate_id for item in ordered_findings
        ),
        findings=ordered_findings,
    )


__all__ = [
    "DENSE_LATTICE_EVALUATED",
    "DENSE_LATTICE_GRID_LIKE",
    "DENSE_LATTICE_UNAVAILABLE",
    "PHYSICAL_WALL_DENSE_LATTICE_SHADOW_SCHEMA_VERSION",
    "PhysicalWallDenseLatticeFinding",
    "PhysicalWallDenseLatticeShadowEvaluation",
    "evaluate_physical_wall_dense_lattice_shadow",
    "unavailable_physical_wall_dense_lattice_shadow",
]
