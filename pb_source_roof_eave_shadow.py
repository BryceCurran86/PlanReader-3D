"""Shadow-only source-native roof edge geometry.

This module retains path identities and native PDF coordinates. It never
calibrates a page, assigns metres, or emits a commercial quantity.
"""
from __future__ import annotations

import math
import re
from collections.abc import Sequence
from dataclasses import dataclass
from itertools import product
from typing import Any

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

# ---------------------------------------------------------------------------
# Semantic roof material matching & negative filters
# ---------------------------------------------------------------------------
ROOF_MATERIAL_POSITIVE_RE = re.compile(
    r"\b(?:roof|roofing|roof\s+covering|corrugated|galvanized|iron\s+sheet|sheet\s+roofing|roofing\s+sheet|metal\s+deck|tiles)\b",
    re.IGNORECASE,
)
ROOF_MATERIAL_NEGATIVE_RE = re.compile(
    r"\b(?:damp[- ]proof(?:ing)?|water[- ]proof(?:ing)?|fire[- ]proof(?:ing)?|sound[- ]proof(?:ing)?|bullet[- ]proof(?:ing)?|rust[- ]proof(?:ing)?|proof|proofing|dpc)\b",
    re.IGNORECASE,
)


def is_valid_roof_material_text(text: str) -> bool:
    """Validate that text genuinely authenticates roof material and is not a non-roof proof note."""
    if not text or not str(text).strip():
        return False
    t = str(text).strip()
    if ROOF_MATERIAL_NEGATIVE_RE.search(t):
        return False
    return bool(ROOF_MATERIAL_POSITIVE_RE.search(t))


@dataclass(frozen=True)
class RoofPath:
    path_id: str
    start: tuple[float, float]
    end: tuple[float, float]
    stroke: tuple[float, float, float] = (0.0, 0.0, 0.0)
    width_pt: float = 1.0
    dashes: str = "[] 0"
    path_index: int | None = None
    layer_name: str | None = None
    clip_id: str | None = None


@dataclass(frozen=True)
class RoofSourceScope:
    document_id: str
    revision_id: str
    source_sha256: str
    source_page: int
    viewport_id: str
    entity_id: str

    def __post_init__(self) -> None:
        if not self.document_id or not self.revision_id or not self.viewport_id or not self.entity_id:
            raise ValueError("document, revision, viewport and entity ownership are required")
        if len(self.source_sha256) != 64 or any(c not in "0123456789abcdef" for c in self.source_sha256.lower()):
            raise ValueError("source_sha256 must be a 64-char lower-case SHA-256 digest")
        if self.source_page < 1:
            raise ValueError("source_page must be positive")


@dataclass(frozen=True)
class RoofMaterialAnnotation:
    annotation_id: str
    text: str
    scope: RoofSourceScope
    bbox: tuple[float, float, float, float]


@dataclass(frozen=True)
class RoofEdgeAlternative:
    start_pt: float
    end_pt: float
    path_ids: tuple[str, ...]
    candidate_id: str


@dataclass(frozen=True)
class RoofEdgeCandidate:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    scope: RoofSourceScope
    span_pt: float | None = None
    start_pt: float | None = None
    end_pt: float | None = None
    path_ids: tuple[str, ...] = ()
    candidate_id: str | None = None
    pitch_deg: float | None = None
    material_annotation_ids: tuple[str, ...] = ()
    alternatives: tuple[RoofEdgeAlternative, ...] = ()
    height_pt: float | None = None
    ridge_path_ids: tuple[str, ...] = ()
    eave_path_ids: tuple[str, ...] = ()
    side_path_ids: tuple[str, ...] = ()
    orientation: str | None = None
    facade_role: str | None = None
    apex_xy: tuple[float, float] | None = None
    left_eave_xy: tuple[float, float] | None = None
    right_eave_xy: tuple[float, float] | None = None
    left_drop_pt: float | None = None
    right_drop_pt: float | None = None
    left_path_ids: tuple[str, ...] = ()
    right_path_ids: tuple[str, ...] = ()
    layout_tol_pt: float | None = None

    @property
    def source_page(self) -> int:
        return self.scope.source_page

    @property
    def viewport_id(self) -> str:
        return self.scope.viewport_id


@dataclass(frozen=True)
class RoofEaveGeometryShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    longitudinal_span_pt: float | None
    transverse_span_pt: float | None
    pitch_deg: float | None
    source_page: int | None
    viewport_ids: tuple[str, ...]
    path_ids: tuple[str, ...]
    source_scope: RoofSourceScope | None = None
    quantity_m2: None = None  # Native geometry cannot confer measurement authority.
    geometry_id: str | None = None
    ridge_candidate_ids: tuple[str, ...] = ()
    longitudinal_outer_edge_ids: tuple[str, ...] = ()
    gable_outer_edge_ids: tuple[str, ...] = ()
    pitch_evidence_id: str | None = None
    material_annotation_ids: tuple[str, ...] = ()
    physical_distinctness: str = "unresolved"
    geometry_completeness: str = "incomplete"
    blockers: tuple[str, ...] = ()
    slope_length_pt: float | None = None
    roof_plane_count: int | None = None
    gable_apex_xy: tuple[float, float] | None = None
    gable_left_drop_pt: float | None = None
    gable_right_drop_pt: float | None = None
    longitudinal_matches: tuple[tuple[str, str, float, float], ...] = ()
    reconciliation_tol_pt: float | None = None


# Alias suggested in architectural specification
SourceRoofSurfaceGeometry = RoofEaveGeometryShadow


def _visible_line(path: RoofPath) -> bool:
    return (
        bool(path.path_id)
        and math.isfinite(path.width_pt)
        and path.width_pt > 0
        and len(path.stroke) >= 3
        and all(math.isfinite(v) and 0 <= v <= .15 for v in path.stroke[:3])
        and str(path.dashes).strip() in {"[] 0", "[] 0.0", ""}
        and all(math.isfinite(v) for v in (*path.start, *path.end))
    )


def _inside(path: RoofPath, bbox: tuple[float, float, float, float]) -> bool:
    x0, y0, x1, y1 = bbox
    return all(x0 <= p[0] <= x1 and y0 <= p[1] <= y1 for p in (path.start, path.end))


def _owned_material(
    annotations: Sequence[RoofMaterialAnnotation], scope: RoofSourceScope,
    viewport_bbox: tuple[float, float, float, float],
) -> tuple[str, ...]:
    x0, y0, x1, y1 = viewport_bbox
    return tuple(sorted({
        a.annotation_id for a in annotations
        if isinstance(a, RoofMaterialAnnotation) and a.scope == scope
        and a.annotation_id and is_valid_roof_material_text(a.text)
        and x0 <= a.bbox[0] < a.bbox[2] <= x1
        and y0 <= a.bbox[1] < a.bbox[3] <= y1
    }))


def _result(
    status: EvidenceResolutionStatus, reason: str, scope: RoofSourceScope,
    *, start: float | None = None, end: float | None = None,
    path_ids: tuple[str, ...] = (), pitch_deg: float | None = None,
    material_annotation_ids: tuple[str, ...] = (),
    alternatives: tuple[RoofEdgeAlternative, ...] = (),
    height_pt: float | None = None,
    ridge_path_ids: tuple[str, ...] = (),
    eave_path_ids: tuple[str, ...] = (),
    side_path_ids: tuple[str, ...] = (),
    orientation: str | None = None,
    facade_role: str | None = None,
    apex_xy: tuple[float, float] | None = None,
    left_eave_xy: tuple[float, float] | None = None,
    right_eave_xy: tuple[float, float] | None = None,
    left_drop_pt: float | None = None,
    right_drop_pt: float | None = None,
    left_path_ids: tuple[str, ...] = (),
    right_path_ids: tuple[str, ...] = (),
    layout_tol_pt: float | None = None,
) -> RoofEdgeCandidate:
    span = None if start is None or end is None else round(end - start, 4)
    cid = None if span is None else stable_contract_id("roof_edge", {
        "document_id": scope.document_id,
        "revision_id": scope.revision_id,
        "entity_id": scope.entity_id,
        "source_sha256": scope.source_sha256,
        "source_page": scope.source_page,
        "viewport_id": scope.viewport_id,
        "start_pt": round(start, 4),
        "end_pt": round(end, 4),
    })
    return RoofEdgeCandidate(
        status=status,
        reason_codes=(reason,),
        scope=scope,
        span_pt=span,
        start_pt=start,
        end_pt=end,
        path_ids=path_ids,
        candidate_id=cid,
        pitch_deg=pitch_deg,
        material_annotation_ids=material_annotation_ids,
        alternatives=alternatives,
        height_pt=height_pt,
        ridge_path_ids=ridge_path_ids,
        eave_path_ids=eave_path_ids,
        side_path_ids=side_path_ids,
        orientation=orientation,
        facade_role=facade_role,
        apex_xy=apex_xy,
        left_eave_xy=left_eave_xy,
        right_eave_xy=right_eave_xy,
        left_drop_pt=left_drop_pt,
        right_drop_pt=right_drop_pt,
        left_path_ids=left_path_ids,
        right_path_ids=right_path_ids,
        layout_tol_pt=layout_tol_pt,
    )


def _alternatives(
    scope: RoofSourceScope, candidates: Sequence[tuple[float, float, tuple[str, ...]]],
) -> tuple[RoofEdgeAlternative, ...]:
    retained = []
    for start, end, ids in sorted(candidates):
        candidate = _result(EvidenceResolutionStatus.CANDIDATE, "native_points_only", scope,
                            start=start, end=end, path_ids=ids)
        retained.append(RoofEdgeAlternative(start, end, ids, candidate.candidate_id))
    return tuple(retained)


def _merge_horizontal_rows(
    rows: list[tuple[float, float, float, RoofPath]],
    *, xtol: float, ytol: float,
) -> list[tuple[float, float, float, tuple[str, ...]]]:
    """Combine continuous collinear strokes without discarding their path IDs."""
    layers: list[list[tuple[float, float, float, RoofPath]]] = []
    for row in sorted(rows, key=lambda r: (r[2], r[0], r[1], r[3].path_id)):
        found = next((layer for layer in layers if abs(layer[0][2] - row[2]) <= ytol / 10), None)
        if found is None:
            layers.append([row])
        else:
            found.append(row)
    merged = []
    for layer in layers:
        runs: list[tuple[float, float, set[str]]] = []
        for lo, hi, _y, path in sorted(layer, key=lambda r: (r[0], r[1], r[3].path_id)):
            if runs and lo <= runs[-1][1] + xtol:
                a, b, ids = runs[-1]
                ids.add(path.path_id)
                runs[-1] = (a, max(b, hi), ids)
            else:
                runs.append((lo, hi, {path.path_id}))
        merged.extend((a, b, layer[0][2], tuple(sorted(ids))) for a, b, ids in runs)
    return merged


def _merge_vertical_columns(
    cols: list[tuple[float, float, float, RoofPath]],
    *, xtol: float, ytol: float,
) -> list[tuple[float, float, float, tuple[str, ...]]]:
    """Combine continuous collinear vertical strokes without discarding their path IDs."""
    layers: list[list[tuple[float, float, float, RoofPath]]] = []
    for col in sorted(cols, key=lambda c: (c[0], c[1], c[2], c[3].path_id)):
        found = next((layer for layer in layers if abs(layer[0][0] - col[0]) <= xtol / 10), None)
        if found is None:
            layers.append([col])
        else:
            found.append(col)
    merged = []
    for layer in layers:
        runs: list[tuple[float, float, set[str]]] = []
        for _x, ylo, yhi, path in sorted(layer, key=lambda c: (c[1], c[2], c[3].path_id)):
            if runs and ylo <= runs[-1][1] + ytol:
                a, b, ids = runs[-1]
                ids.add(path.path_id)
                runs[-1] = (a, max(b, yhi), ids)
            else:
                runs.append((ylo, yhi, {path.path_id}))
        merged.extend((layer[0][0], a, b, tuple(sorted(ids))) for a, b, ids in runs)
    return merged


def collect_longitudinal_roof_edge(
    paths: Sequence[RoofPath], *, scope: RoofSourceScope,
    viewport_bbox: tuple[float, float, float, float],
    page_width_pt: float, roof_material_annotations: Sequence[RoofMaterialAnnotation],
    orientation: str | None = None,
) -> RoofEdgeCandidate:
    """Retain one roof-fascia outline enclosed by side edges in an elevation.

    Repeated horizontal strokes by themselves could be a dimension or title
    frame. Both side edges, solid stroke, a material callout, and one unique
    outline are required. All competing outlines remain a conflict.
    """
    owned_material = _owned_material(roof_material_annotations, scope, viewport_bbox)
    if not owned_material:
        return _result(EvidenceResolutionStatus.ABSTAINED, "roof_material_unowned", scope)
    vx0, vy0, vx1, vy1 = viewport_bbox
    w, h = vx1 - vx0, vy1 - vy0
    if w <= 0 or h <= 0 or page_width_pt <= 0:
        return _result(EvidenceResolutionStatus.ABSTAINED, "invalid_viewport", scope)
    xtol = .002 * w
    ytol = .003 * h
    scoped = [p for p in paths if _visible_line(p) and _inside(p, viewport_bbox)]
    hs: list[tuple[float, float, float, RoofPath]] = []
    vs: list[tuple[float, float, float, RoofPath]] = []
    for p in scoped:
        (x0, y0), (x1, y1) = p.start, p.end
        if abs(y1 - y0) <= ytol:
            hs.append((min(x0, x1), max(x0, x1), (y0 + y1) / 2, p))
        elif abs(x1 - x0) <= xtol and abs(y1 - y0) > ytol:
            vs.append(((x0 + x1) / 2, min(y0, y1), max(y0, y1), p))
    merged = _merge_horizontal_rows(hs, xtol=xtol, ytol=ytol)
    merged_vs = _merge_vertical_columns(vs, xtol=xtol, ytol=ytol)
    groups: list[list[tuple[float, float, float, tuple[str, ...]]]] = []
    for row in sorted(merged, key=lambda z: (z[0], z[1], z[2], z[3])):
        if not (.20 * w <= row[1] - row[0] < .9 * page_width_pt):
            continue
        found = next((g for g in groups if abs(g[0][0] - row[0]) <= xtol and abs(g[0][1] - row[1]) <= xtol), None)
        if found is None:
            groups.append([row])
        else:
            found.append(row)
    candidates = []
    for group in groups:
        ys = sorted({round(r[2], 4) for r in group})
        if len(ys) < 2 or ys[-1] - ys[0] <= ytol:
            continue
        xlo = sum(r[0] for r in group) / len(group)
        xhi = sum(r[1] for r in group) / len(group)
        side_groups = []
        for x in (xlo, xhi):
            options = [v for v in merged_vs if abs(v[0] - x) <= xtol and v[1] <= ys[0] + ytol and v[2] >= ys[-1] - ytol]
            if not options:
                break
            side_groups.append(tuple(sorted({pid for v in options for pid in v[3]})))
        if len(side_groups) != 2:
            continue
        ridge_pids = tuple(sorted({pid for r in group if abs(r[2] - ys[0]) <= ytol for pid in r[3]}))
        eave_pids = tuple(sorted({pid for r in group if abs(r[2] - ys[-1]) <= ytol for pid in r[3]}))
        side_pids = tuple(sorted(pid for side in side_groups for pid in side))
        ids = tuple(sorted({*(pid for r in group for pid in r[3]),
                            *(pid for side in side_groups for pid in side)}))
        height = round(ys[-1] - ys[0], 4)
        candidates.append((round(xlo, 4), round(xhi, 4), ids, height, ridge_pids, eave_pids, side_pids))
    if not candidates:
        return _result(EvidenceResolutionStatus.ABSTAINED, "roof_outline_unavailable", scope)
    if len(candidates) > 1:
        return _result(EvidenceResolutionStatus.CONFLICT, "competing_roof_outlines", scope,
                       alternatives=_alternatives(scope, [(c[0], c[1], c[2]) for c in candidates]))
    a, b, ids, height, ridge_ids, eave_ids, side_ids = candidates[0]
    return _result(EvidenceResolutionStatus.CANDIDATE, "roof_outline_native_points_only", scope,
                   start=a, end=b, path_ids=ids, material_annotation_ids=owned_material,
                   height_pt=height, ridge_path_ids=ridge_ids, eave_path_ids=eave_ids,
                   side_path_ids=side_ids, orientation=orientation,
                   layout_tol_pt=round(ytol, 4))


def collect_gable_outer_roof_edge(
    paths: Sequence[RoofPath], *, scope: RoofSourceScope,
    viewport_bbox: tuple[float, float, float, float],
    apex_xy: tuple[float, float], pitch_deg: float,
    structural_left_x: float, structural_right_x: float,
    roof_material_annotations: Sequence[RoofMaterialAnnotation],
) -> RoofEdgeCandidate:
    """Keep both outer slope endpoints from one authenticated gable apex."""
    owned_material = _owned_material(roof_material_annotations, scope, viewport_bbox)
    if not owned_material:
        return _result(EvidenceResolutionStatus.ABSTAINED, "roof_material_unowned", scope)
    x0, y0, x1, y1 = viewport_bbox
    if x1 <= x0 or y1 <= y0 or not (5 <= pitch_deg <= 65 and structural_left_x < structural_right_x):
        return _result(EvidenceResolutionStatus.ABSTAINED, "gable_context_invalid", scope)
    tol = .01 * (x1 - x0)
    join_tol = .001 * (x1 - x0)
    apex_x, apex_y = apex_xy
    sides: dict[int, list[tuple[float, float, str, tuple[float, float], tuple[float, float]]]] = {-1: [], 1: []}
    for p in paths:
        if not _visible_line(p) or not _inside(p, viewport_bbox):
            continue
        a, b = sorted((p.start, p.end), key=lambda pt: abs(pt[0] - apex_x))
        dx, dy = b[0] - a[0], b[1] - a[1]
        if abs(dx) < .001 * (x1 - x0):
            continue
        direction = -1 if dx < 0 else 1
        near, far = direction * (a[0] - apex_x), direction * (b[0] - apex_x)
        if near < -join_tol or far <= near:
            continue
        intercept = a[1] - (a[0] - apex_x) * dy / dx
        if abs(intercept - apex_y) > tol:
            continue
        measured = math.degrees(math.atan2(abs(dy), abs(dx)))
        if abs(measured - pitch_deg) > 1:
            continue
        sides[direction].append((max(0, near), far, p.path_id, a, b))

    if not sides[-1] or not sides[1]:
        return _result(EvidenceResolutionStatus.ABSTAINED, "outer_gable_pair_unavailable", scope)

    endpoint_options = {}
    for direction, segments in sides.items():
        reachable = []
        extent = join_tol
        for near, far, pid, a, b in sorted(segments, key=lambda s: (s[0], s[1], s[2])):
            if near > extent + join_tol:
                continue
            extent = max(extent, far)
            reachable.append((near, far, pid, a, b))
        if not reachable:
            return _result(EvidenceResolutionStatus.ABSTAINED, "outer_gable_pair_unavailable", scope)
        support_distance = abs((structural_left_x if direction < 0 else structural_right_x) - apex_x)
        terminals = [
            far for near, far, pid, a, b in reachable
            if far > support_distance + join_tol
            and not any(abs(other_near - far) <= join_tol and other_far > far + join_tol
                        for other_near, other_far, _, _, _ in reachable)
        ]
        if not terminals:
            return _result(EvidenceResolutionStatus.CONFLICT, "gable_edges_do_not_enclose_supports", scope)

        groups = []
        for far in sorted(set(terminals)):
            found = next((group for group in groups if far - group[0] <= tol), None)
            if found is None:
                groups.append([far])
            else:
                found.append(far)

        options = []
        for group in groups:
            endpoint = max(group)
            selected = {
                (near, far, pid, a, b) for near, far, pid, a, b in reachable
                if any(abs(far - t) <= join_tol for t in group)
            }
            frontier = [near for near, _, _, _, _ in selected]
            while frontier:
                distance = frontier.pop()
                for segment in reachable:
                    if segment not in selected and abs(segment[1] - distance) <= join_tol:
                        selected.add(segment)
                        frontier.append(segment[0])

            x_eave = apex_x + direction * endpoint
            y_apex_side = min(min(s[3][1], s[4][1]) for s in selected)
            y_eave_side = max(max(s[3][1], s[4][1]) for s in selected)
            drop_pt = abs(y_eave_side - y_apex_side)
            side_pids = tuple(sorted(s[2] for s in selected))
            options.append((x_eave, y_eave_side, drop_pt, side_pids, y_apex_side))

        endpoint_options[direction] = options

    pairs = [
        (left_x, left_y, left_drop, left_ids, left_apex_y, right_x, right_y, right_drop, right_ids, right_apex_y)
        for (left_x, left_y, left_drop, left_ids, left_apex_y), (right_x, right_y, right_drop, right_ids, right_apex_y)
        in product(endpoint_options[-1], endpoint_options[1])
    ]
    if len(pairs) > 1:
        alt_pairs = [(round(p[0], 4), round(p[5], 4), tuple(sorted(set(p[3] + p[8])))) for p in pairs]
        return _result(EvidenceResolutionStatus.CONFLICT, "competing_gable_edges", scope,
                       alternatives=_alternatives(scope, alt_pairs))

    left_x, left_y, left_drop, left_ids, left_apex_y, right_x, right_y, right_drop, right_ids, right_apex_y = pairs[0]
    if not (left_x <= structural_left_x < structural_right_x <= right_x):
        return _result(EvidenceResolutionStatus.CONFLICT, "gable_edges_do_not_enclose_supports", scope)

    all_ids = tuple(sorted(set(left_ids + right_ids)))
    final_apex_y = min(left_apex_y, right_apex_y)
    return _result(
        EvidenceResolutionStatus.CANDIDATE, "gable_edge_native_points_only", scope,
        start=left_x, end=right_x, path_ids=all_ids, pitch_deg=pitch_deg,
        material_annotation_ids=owned_material,
        apex_xy=(round(apex_x, 4), round(final_apex_y, 4)),
        left_eave_xy=(round(left_x, 4), round(left_y, 4)),
        right_eave_xy=(round(right_x, 4), round(right_y, 4)),
        left_drop_pt=round(left_drop, 4),
        right_drop_pt=round(right_drop, 4),
        left_path_ids=tuple(sorted(left_ids)),
        right_path_ids=tuple(sorted(right_ids)),
        layout_tol_pt=round(tol, 4),
    )


def derive_drop_matching_tolerance(
    gable: RoofEdgeCandidate,
    longitudinal: Sequence[RoofEdgeCandidate],
) -> float:
    """Derive drop-matching tolerance from existing source-native geometry / layout resolution.

    Ensures tolerance scales proportionally under uniform coordinate transformations (e.g. 1x vs 2x).
    Uses candidate layout resolution (.01 * gable_span or extractor viewport resolution),
    scaling linearly with the coordinate system.
    """
    candidate_tols = [
        c.layout_tol_pt for c in (*longitudinal, gable)
        if c.layout_tol_pt is not None and c.layout_tol_pt > 0
    ]
    if candidate_tols:
        return round(max(candidate_tols), 4)

    if gable.span_pt is not None and gable.span_pt > 0:
        return round(0.01 * gable.span_pt, 4)

    drops = [d for d in (gable.left_drop_pt, gable.right_drop_pt) if d is not None and d > 0]
    if drops:
        return round(0.03 * max(drops), 4)

    return 1.0


def _match_longitudinal_to_gable(
    longitudinal: Sequence[RoofEdgeCandidate],
    gable: RoofEdgeCandidate,
    *,
    tol: float,
) -> tuple[str, tuple[str, ...], tuple[tuple[str, str, float, float], ...]]:
    """Establish bijection between longitudinal candidates and gable sides.

    Returns:
        (distinctness, blockers, matches)
    """
    if gable.left_drop_pt is None or gable.right_drop_pt is None:
        return "unresolved", ("gable_vertical_drops_missing",), ()

    left_drop = gable.left_drop_pt
    right_drop = gable.right_drop_pt
    sym_tol = 0.001 * (gable.span_pt or 100.0)
    is_symmetric = abs(left_drop - right_drop) <= sym_tol

    c1, c2 = longitudinal[0], longitudinal[1]
    h1 = c1.height_pt
    h2 = c2.height_pt
    if h1 is None or h2 is None:
        return "unresolved", ("longitudinal_height_missing",), ()

    if is_symmetric:
        m1 = abs(h1 - left_drop) <= tol or abs(h1 - right_drop) <= tol
        m2 = abs(h2 - left_drop) <= tol or abs(h2 - right_drop) <= tol
        if not (m1 and m2):
            return "unresolved", ("longitudinal_gable_drop_mismatch",), ()

        # Symmetric roof: equal drop alone cannot prove two distinct faces.
        # Raw caller input (e.g. facade_role="front"), viewport IDs, and elevation
        # numbers cannot establish physical roof-face identity. Without upstream
        # authenticated source evidence, symmetric roofs fail closed as unproven.
        return "unresolved", ("symmetric_roof_facade_identity_unproven",), ()

    # Asymmetric roof:
    m1_left = abs(h1 - left_drop) <= tol
    m1_right = abs(h1 - right_drop) <= tol
    m2_left = abs(h2 - left_drop) <= tol
    m2_right = abs(h2 - right_drop) <= tol

    # Ambiguity: either can match both sides
    if (m1_left and m1_right) or (m2_left and m2_right):
        return "ambiguous", ("ambiguous_gable_side_match",), ()

    # Conflict: both map to the same side
    if (m1_left and m2_left) or (m1_right and m2_right):
        return "conflict", ("duplicate_or_competing_longitudinal_faces",), ()

    # Bijection
    if m1_left and m2_right:
        matches = (
            (c1.viewport_id, "left", h1, left_drop),
            (c2.viewport_id, "right", h2, right_drop),
        )
        return "distinct_front_rear_eaves", (), matches
    elif m1_right and m2_left:
        matches = (
            (c1.viewport_id, "right", h1, right_drop),
            (c2.viewport_id, "left", h2, left_drop),
        )
        return "distinct_front_rear_eaves", (), matches

    return "unresolved", ("longitudinal_gable_drop_mismatch",), ()


def reconcile_roof_eave_geometry(
    longitudinal: Sequence[RoofEdgeCandidate], transverse: RoofEdgeCandidate,
    *, pitch_deg: float,
) -> RoofEaveGeometryShadow:
    """Corroborate native geometry, never its physical scale or a quantity."""
    if len(longitudinal) < 2 or any(c.status is not EvidenceResolutionStatus.CANDIDATE for c in longitudinal) or transverse.status is not EvidenceResolutionStatus.CANDIDATE:
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.ABSTAINED, ("incomplete_roof_view_universe",), None, None, None, None, (), (),
                                      blockers=("incomplete_roof_view_universe",))
    if len(longitudinal) > 2:
        return RoofEaveGeometryShadow(
            EvidenceResolutionStatus.CONFLICT, ("competing_longitudinal_elevations",),
            None, None, None, transverse.source_page,
            tuple(sorted(c.viewport_id for c in longitudinal)), (),
            blockers=("extra_longitudinal_candidates_unresolved",),
        )

    if any((c.scope.document_id, c.scope.revision_id, c.scope.source_sha256, c.scope.source_page, c.scope.entity_id) !=
           (transverse.scope.document_id, transverse.scope.revision_id, transverse.scope.source_sha256, transverse.scope.source_page, transverse.scope.entity_id)
           for c in longitudinal):
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.CONFLICT, ("source_scope_conflict",), None, None, None, None, (), (),
                                      blockers=("source_scope_conflict",))

    view_ids = [c.viewport_id for c in longitudinal] + [transverse.viewport_id]
    if len(view_ids) != len(set(view_ids)) or not math.isfinite(pitch_deg) or transverse.pitch_deg is None or abs(transverse.pitch_deg - pitch_deg) > .01:
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.CONFLICT, ("roof_view_identity_conflict",), None, None, None, None, (), (),
                                      blockers=("roof_view_identity_conflict",))

    spans = [c.span_pt for c in longitudinal]
    if any(v is None for v in spans) or max(spans) - min(spans) > .003 * max(spans):
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.CONFLICT, ("longitudinal_elevations_disagree",), None, None, None, None, (), (),
                                      blockers=("longitudinal_elevations_disagree",))

    tol = derive_drop_matching_tolerance(transverse, longitudinal)
    distinctness, match_blockers, matches = _match_longitudinal_to_gable(longitudinal, transverse, tol=tol)
    if distinctness == "ambiguous":
        return RoofEaveGeometryShadow(
            EvidenceResolutionStatus.ABSTAINED, match_blockers,
            None, None, None, transverse.source_page, tuple(sorted(view_ids)), (),
            physical_distinctness="ambiguous", blockers=match_blockers,
            reconciliation_tol_pt=tol,
        )
    if distinctness == "conflict":
        return RoofEaveGeometryShadow(
            EvidenceResolutionStatus.CONFLICT, match_blockers,
            None, None, None, transverse.source_page, tuple(sorted(view_ids)), (),
            physical_distinctness="conflict", blockers=match_blockers,
            reconciliation_tol_pt=tol,
        )
    if distinctness != "distinct_front_rear_eaves":
        return RoofEaveGeometryShadow(
            EvidenceResolutionStatus.ABSTAINED, match_blockers or ("physical_eave_distinctness_unproven",),
            None, None, None, transverse.source_page, tuple(sorted(view_ids)), (),
            physical_distinctness="unresolved", blockers=match_blockers or ("physical_eave_distinctness_unproven",),
            reconciliation_tol_pt=tol,
        )

    ids = tuple(sorted({p for c in (*longitudinal, transverse) for p in c.path_ids}))
    ridge_ids = tuple(sorted({p for c in longitudinal for p in c.ridge_path_ids}))
    eave_ids = tuple(sorted({p for c in longitudinal for p in c.eave_path_ids}))
    mat_ids = tuple(sorted({a for c in (*longitudinal, transverse) for a in c.material_annotation_ids}))

    long_span = round(sum(spans) / len(spans), 4)
    trans_span = transverse.span_pt
    rad = math.radians(pitch_deg)
    slope_len = round(trans_span / math.cos(rad), 4) if math.cos(rad) > 0 else None

    gid = stable_contract_id("roof_surface_geometry", {
        "document_id": transverse.scope.document_id,
        "revision_id": transverse.scope.revision_id,
        "entity_id": transverse.scope.entity_id,
        "source_sha256": transverse.scope.source_sha256,
        "source_page": transverse.source_page,
        "viewport_ids": sorted(view_ids),
        "longitudinal_span_pt": long_span,
        "transverse_span_pt": trans_span,
        "pitch_deg": round(pitch_deg, 4),
    })

    pid_evidence = stable_contract_id("roof_pitch_evidence", {
        "document_id": transverse.scope.document_id,
        "revision_id": transverse.scope.revision_id,
        "entity_id": transverse.scope.entity_id,
        "source_sha256": transverse.scope.source_sha256,
        "source_page": transverse.source_page,
        "viewport_id": transverse.viewport_id,
        "pitch_deg": round(pitch_deg, 4),
    })

    return RoofEaveGeometryShadow(
        status=EvidenceResolutionStatus.CANDIDATE,
        reason_codes=("native_roof_edges_correspond_but_scale_unresolved",),
        longitudinal_span_pt=long_span,
        transverse_span_pt=trans_span,
        pitch_deg=round(pitch_deg, 4),
        source_page=transverse.source_page,
        viewport_ids=tuple(sorted(view_ids)),
        path_ids=ids,
        source_scope=transverse.scope,
        quantity_m2=None,
        geometry_id=gid,
        ridge_candidate_ids=ridge_ids,
        longitudinal_outer_edge_ids=eave_ids,
        gable_outer_edge_ids=transverse.path_ids,
        pitch_evidence_id=pid_evidence,
        material_annotation_ids=mat_ids,
        physical_distinctness=distinctness,
        geometry_completeness="complete_closed_prism",
        slope_length_pt=slope_len,
        roof_plane_count=2,
        gable_apex_xy=transverse.apex_xy,
        gable_left_drop_pt=transverse.left_drop_pt,
        gable_right_drop_pt=transverse.right_drop_pt,
        longitudinal_matches=matches,
        reconciliation_tol_pt=tol,
    )


def extract_document_roof_surface_geometry_shadow(
    doc: Any,
    *,
    document_id: str,
    revision_id: str,
    source_sha256: str,
    entity_id: str,
    target_pages: Sequence[int],
) -> RoofEaveGeometryShadow:
    """Extract and reconcile source-native roof surface geometry from drawing sheet(s).

    Pure shadow-only: returns native coordinates and spans, never calibrates scale or emits an area.
    Fail-closed: requires authentic caller-supplied provenance ownership.
    """
    if not document_id or not str(document_id).strip():
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.ABSTAINED, ("missing_document_id",), None, None, None, None, (), (), blockers=("missing_document_id",))
    if not revision_id or not str(revision_id).strip():
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.ABSTAINED, ("missing_revision_id",), None, None, None, None, (), (), blockers=("missing_revision_id",))
    if not entity_id or not str(entity_id).strip():
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.ABSTAINED, ("missing_entity_id",), None, None, None, None, (), (), blockers=("missing_entity_id",))
    if not source_sha256 or len(source_sha256) != 64 or not all(c in "0123456789abcdef" for c in source_sha256.lower()):
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.ABSTAINED, ("invalid_source_sha256",), None, None, None, None, (), (), blockers=("invalid_source_sha256",))
    if not target_pages or not isinstance(target_pages, Sequence) or len(target_pages) == 0:
        return RoofEaveGeometryShadow(EvidenceResolutionStatus.ABSTAINED, ("missing_target_pages",), None, None, None, None, (), (), blockers=("missing_target_pages",))

    from pb_source_roof_covering_authority import (
        extract_elevation_segments_from_page,
        get_elevation_viewport_search_bbox,
        resolve_gable_apex_in_viewport,
    )
    from pb_viewport_segmentation import segment_page_viewports

    for p_idx in target_pages:
        if p_idx < 0 or p_idx >= len(doc):
            continue
        page = doc[p_idx]
        pno = p_idx + 1
        vps = segment_page_viewports(page, page_number=pno)
        elev_vps = [vp for vp in vps if getattr(vp, "view_type", None) == "elevation"]
        if len(elev_vps) < 2:
            continue

        drawings = page.get_drawings()
        paths: list[RoofPath] = []
        for idx, d in enumerate(drawings):
            items = d.get("items", [])
            stroke = d.get("color", (0.0, 0.0, 0.0)) or (0.0, 0.0, 0.0)
            width = d.get("width", 1.0)
            dashes = str(d.get("dashes", "[] 0"))
            for it_idx, it in enumerate(items):
                if it[0] == "l":
                    p1, p2 = it[1], it[2]
                    paths.append(RoofPath(f"{idx}:{it_idx}", (p1.x, p1.y), (p2.x, p2.y), stroke=stroke, width_pt=width, dashes=dashes))

        raw_text_blocks = []
        for b_idx, block in enumerate(page.get_text("blocks")):
            text = block[4].strip()
            if is_valid_roof_material_text(text):
                raw_text_blocks.append((b_idx, text, (block[0], block[1], block[2], block[3])))

        gable_candidates: list[tuple[Any, RoofEdgeCandidate, float]] = []
        longitudinal_candidates: list[tuple[Any, RoofEdgeCandidate]] = []

        for vp in elev_vps:
            sbox = get_elevation_viewport_search_bbox(vp, vps, page.rect)
            scope = RoofSourceScope(document_id, revision_id, source_sha256, pno, vp.view_id, entity_id)

            vp_annos: list[RoofMaterialAnnotation] = []
            for b_idx, text, bbox in raw_text_blocks:
                if sbox[0] <= bbox[0] < bbox[2] <= sbox[2] and sbox[1] <= bbox[1] < bbox[3] <= sbox[3]:
                    vp_annos.append(RoofMaterialAnnotation(f"anno_{pno}_{b_idx}_{vp.view_id}", text, scope, bbox))

            # A. Try gable extraction
            diags, verts = extract_elevation_segments_from_page(page, sbox)
            apex_ev, reasons = resolve_gable_apex_in_viewport(diags, verts, source_page=pno)
            if apex_ev and "authenticated_gable_roofline" in reasons:
                res_g = collect_gable_outer_roof_edge(
                    paths, scope=scope, viewport_bbox=sbox,
                    apex_xy=apex_ev.apex_xy, pitch_deg=apex_ev.pitch_deg,
                    structural_left_x=apex_ev.left_support_xy[0],
                    structural_right_x=apex_ev.right_support_xy[0],
                    roof_material_annotations=vp_annos,
                )
                if res_g.status is EvidenceResolutionStatus.CANDIDATE:
                    gable_candidates.append((vp, res_g, apex_ev.pitch_deg))

            # B. Independently try longitudinal extraction
            res_l = collect_longitudinal_roof_edge(
                paths, scope=scope, viewport_bbox=sbox, page_width_pt=page.rect.width,
                roof_material_annotations=vp_annos,
            )
            if res_l.status is EvidenceResolutionStatus.CANDIDATE:
                longitudinal_candidates.append((vp, res_l))

        if len(gable_candidates) == 0:
            continue
        if len(gable_candidates) > 1:
            return RoofEaveGeometryShadow(
                EvidenceResolutionStatus.CONFLICT, ("multiple_competing_gable_systems",),
                None, None, None, pno, tuple(sorted(g[0].view_id for g in gable_candidates)), (),
                blockers=("multiple_competing_gable_systems",),
            )
        if len(longitudinal_candidates) < 2:
            return RoofEaveGeometryShadow(
                EvidenceResolutionStatus.ABSTAINED, ("incomplete_roof_view_universe",),
                None, None, None, pno, tuple(sorted(vp.view_id for vp, _ in longitudinal_candidates)), (),
                blockers=("incomplete_longitudinal_views",),
            )
        if len(longitudinal_candidates) > 2:
            return RoofEaveGeometryShadow(
                EvidenceResolutionStatus.CONFLICT, ("competing_longitudinal_elevations",),
                None, None, None, pno, tuple(sorted(vp.view_id for vp, _ in longitudinal_candidates)), (),
                blockers=("extra_longitudinal_candidates_unresolved",),
            )

        _, g_cand, pitch_deg = gable_candidates[0]
        l_cands = [lc[1] for lc in longitudinal_candidates]
        return reconcile_roof_eave_geometry(l_cands, g_cand, pitch_deg=pitch_deg)

    return RoofEaveGeometryShadow(
        EvidenceResolutionStatus.ABSTAINED, ("incomplete_roof_view_universe",),
        None, None, None, None, (), (),
        blockers=("no_matching_roof_elevation_sheet_found",),
    )
