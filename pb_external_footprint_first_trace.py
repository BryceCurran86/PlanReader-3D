"""Mandatory first geometry stage: source-PDF external footprint ink trace.

Reads the exact bytes that the original source producer will ingest. This stage
cannot infer scale, classify a roof/site border as a building, mint walls or
authorize customer quantities. The candidate is a review overlay only.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import hashlib
import math
from typing import Mapping, Sequence


@dataclass(frozen=True)
class ExternalFootprintTrace:
    source_sha256: str
    page_index: int
    status: str
    reason: str
    polygon_pdf_pts: tuple[tuple[float, float], ...] = ()
    bbox_pdf_pts: tuple[float, float, float, float] | None = None
    candidate_count: int = 0
    page_drawings_examined: int = 0
    commercial_publishable: bool = False
    measurement_authorized: bool = False
    # ``polygon_pdf_pts`` / ``bbox_pdf_pts`` come from the DISPLAYED raster, so on a rotated page they live in
    # display space, while ``get_drawings()`` rows and ``get_text()`` words live in the page's NATIVE space.
    # None means upright (the two spaces coincide). Otherwise the six floats of the display space -> native space
    # map, in the same UserUnit-scaled points as the polygon: the rotation part of PyMuPDF's
    # ``page.derotation_matrix`` with its translation re-derived from the scaled page extent (PyMuPDF's own
    # translation is the UNSCALED extent) and cross-checked against it. See ``_read_page_frame``.
    page_derotation_matrix: tuple[float, float, float, float, float, float] | None = None

    def to_dict(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "source_sha256": self.source_sha256,
            "page_index": self.page_index,
            "status": self.status,
            "reason": self.reason,
            "polygon_pdf_pts": [list(p) for p in self.polygon_pdf_pts],
            "bbox_pdf_pts": list(self.bbox_pdf_pts) if self.bbox_pdf_pts else None,
            "candidate_count": self.candidate_count,
            "page_drawings_examined": self.page_drawings_examined,
            "commercial_publishable": False,
            "measurement_authorized": False,
        }
        if self.page_derotation_matrix is not None:  # absent on an upright page: its output is unchanged
            payload["page_derotation_matrix"] = list(self.page_derotation_matrix)
        return payload


Point = tuple[float, float]
Matrix6 = tuple[float, float, float, float, float, float]
_MATRIX_DET_FLOOR = 1e-12
_FRAME_ORIGIN_TOL = 1e-6  # the displayed page starts at the origin of the display frame
_FRAME_TRANSLATION_REL_TOL = 1e-5  # relative to each translation (reference floor 1 pt); PyMuPDF's matrix is float32
_FRAME_ROTATION_PART_TOL = 1e-9  # the rotation part is made of 0 and +-1


def _float_matrix(matrix: object) -> Matrix6 | None:
    """The frame as six finite floats that form an invertible map, else None.

    The conversion runs inside the guard: an integer beyond the double range raises OverflowError, a numeric
    string or a boolean is not a frame number, and a determinant that overflows is refused, never applied.
    A singular frame cannot relate the two spaces.
    """
    if type(matrix) is not tuple or len(matrix) != 6:
        return None
    values: list[float] = []
    for v in matrix:
        if type(v) not in (int, float):
            return None
        try:
            number = float(v)
        except OverflowError:
            return None
        if not math.isfinite(number):
            return None
        values.append(number + 0.0)  # + 0.0: no negative zero
    a, b, c, d, e, f = values
    det = a * d - b * c
    if not math.isfinite(det) or abs(det) < _MATRIX_DET_FLOOR:
        return None
    return (a, b, c, d, e, f)


def _matrix_inverse(matrix: Matrix6) -> Matrix6:
    """The inverse of a frame that ``_float_matrix`` accepted (finite, determinant clear of zero)."""
    a, b, c, d, e, f = matrix
    det = a * d - b * c
    return (d / det, -b / det, -c / det, a / det, (c * f - d * e) / det, (b * e - a * f) / det)


def _apply_matrix(matrix: Matrix6, points: Sequence[Sequence[float]]) -> tuple[Point, ...] | None:
    """The points mapped through the frame; None when one cannot be mapped to a finite point."""
    a, b, c, d, e, f = matrix
    try:
        mapped = tuple((a * float(x) + c * float(y) + e, b * float(x) + d * float(y) + f) for x, y in points)
    except (OverflowError, TypeError, ValueError):
        return None
    return mapped if all(math.isfinite(v) for p in mapped for v in p) else None


def footprint_polygon_in_native_space(trace: "ExternalFootprintTrace") -> tuple[Point, ...] | None:
    """The trace polygon in the native page space of ``get_drawings()`` rows (identity on an upright page).

    None when the trace carries a frame that is not six finite numbers forming an invertible map, or points the
    frame cannot map to finite coordinates: callers abstain, never guess.
    """
    matrix = trace.page_derotation_matrix
    if matrix is None:
        return trace.polygon_pdf_pts
    frame = _float_matrix(matrix)
    return None if frame is None else _apply_matrix(frame, trace.polygon_pdf_pts)


def footprint_bbox_in_native_space(trace: "ExternalFootprintTrace") -> tuple[float, float, float, float] | None:
    """The trace bbox in native page space (identity on an upright page; None for an invalid frame)."""
    bbox = trace.bbox_pdf_pts
    matrix = trace.page_derotation_matrix
    if bbox is None or matrix is None:
        return bbox
    frame = _float_matrix(matrix)
    if frame is None:
        return None
    x0, y0, x1, y1 = bbox
    corners = _apply_matrix(frame, ((x0, y0), (x1, y0), (x1, y1), (x0, y1)))
    if corners is None:
        return None
    xs, ys = [p[0] for p in corners], [p[1] for p in corners]
    return (min(xs), min(ys), max(xs), max(ys))


def native_points_to_display_space(
    trace: "ExternalFootprintTrace", points: Sequence[Sequence[float]],
) -> tuple[Point, ...] | None:
    """Native-space points in the trace's own (display) space, rounded to 0.001 (identity when upright)."""
    matrix = trace.page_derotation_matrix
    if matrix is None:
        return tuple((float(x), float(y)) for x, y in points)
    frame = _float_matrix(matrix)
    inverse = None if frame is None else _matrix_inverse(frame)
    shown = None if inverse is None else _apply_matrix(inverse, points)
    if shown is None:
        return None
    return tuple((round(x, 3) + 0.0, round(y, 3) + 0.0) for x, y in shown)


def _declared_user_unit(page: object) -> float | None:
    """The page's /UserUnit (1.0 when the key is absent); None when it cannot be read as a positive finite number."""
    parent, xref = getattr(page, "parent", None), getattr(page, "xref", None)
    getter = getattr(parent, "xref_get_key", None)
    if not callable(getter) or isinstance(xref, bool) or not isinstance(xref, int):
        return None
    try:
        kind, raw = getter(xref, "UserUnit")
    except Exception:  # noqa: BLE001 - a reader that fails leaves the frame unestablished
        return None
    if kind == "null":
        return 1.0
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None
    return value if math.isfinite(value) and value > 0.0 else None


def _read_page_frame(page: object) -> tuple[bool, Matrix6 | None]:
    """(readable, matrix): the page's display -> native map in UserUnit-scaled points; matrix None when upright.

    ``page.rect``, the raster polygon and the ``get_drawings()`` rows are all in UserUnit-scaled points, but
    PyMuPDF's ``page.derotation_matrix`` translates by the UNSCALED page extent. The matrix is therefore derived
    from the scaled display extent and the rotation, and accepted only when PyMuPDF's own matrix agrees with it:
    the same rotation part, and its translation times the declared /UserUnit equal to the derived translation.
    A page whose frame cannot be established this way is reported unreadable, never guessed. An upright page
    reads nothing else.
    """
    try:
        rotation = int(page.rotation)  # type: ignore[attr-defined]
    except (AttributeError, TypeError, ValueError):
        return False, None
    if not rotation:
        return True, None
    if rotation not in (90, 180, 270):
        return False, None
    unit = _declared_user_unit(page)
    try:
        rect = page.rect  # type: ignore[attr-defined]
        x0, y0, width, height = (float(rect.x0), float(rect.y0), float(rect.width), float(rect.height))
        stored = tuple(float(v) for v in page.derotation_matrix)  # type: ignore[attr-defined]
    except (AttributeError, TypeError, ValueError, OverflowError):
        return False, None
    if unit is None or len(stored) != 6 or not all(math.isfinite(v) for v in (x0, y0, width, height, *stored)):
        return False, None
    if width <= 0.0 or height <= 0.0 or abs(x0) > _FRAME_ORIGIN_TOL or abs(y0) > _FRAME_ORIGIN_TOL:
        return False, None
    derived: Matrix6 = {  # display -> native for a page whose displayed extent is width x height
        90: (0.0, -1.0, 1.0, 0.0, 0.0, width),
        180: (-1.0, 0.0, 0.0, -1.0, width, height),
        270: (0.0, 1.0, -1.0, 0.0, height, 0.0),
    }[rotation]
    if any(abs(s - d) > _FRAME_ROTATION_PART_TOL for s, d in zip(stored[:4], derived[:4])):
        return False, None
    if any(abs(s * unit - d) > _FRAME_TRANSLATION_REL_TOL * max(abs(d), 1.0) for s, d in zip(stored[4:], derived[4:])):
        return False, None
    return True, derived


def _abstain(sha: str, index: int, reason: str, drawings: int = 0) -> ExternalFootprintTrace:
    return ExternalFootprintTrace(sha, index, "ABSTAINED", reason, page_drawings_examined=drawings)


def _bounded_raster_scale(page_width_pts: float, page_height_pts: float) -> float:
    """Keep the diagnostic raster longest axis at or under 2400 pixels."""
    axes = (page_width_pts, page_height_pts)
    if not all(math.isfinite(d) and d > 0 for d in axes):
        raise ValueError("external_footprint_invalid_page_dimensions")
    return min(1.8, 2400.0 / max(axes))


def _competing_disjoint_envelopes(
    ranked: Sequence[tuple[float, tuple[int, int, int, int], object]],
) -> bool:
    """Two separate large shapes cannot be called one unique building footprint.

    Nested contours from a thick wall are normal; only comparably sized,
    NON-overlapping enclosing contours compete. Never join them with raster ink.
    """
    if len(ranked) < 2:
        return False
    leading_area, (x, y, w, h), _ = ranked[0]
    for area, (rx, ry, rw, rh), _ in ranked[1:]:
        if area < leading_area * 0.8:
            continue
        if x + w < rx or rx + rw < x or y + h < ry or ry + rh < y:
            return True
    return False


def _polygon_has_self_intersection(points: Sequence[tuple[float, float]]) -> bool:
    """Reject crossed ink contours; adjacent edges may meet at endpoints.

    The first-trace raster stage already caps polygons at 200 vertices.
    This check is diagnostic-only and never fabricates wall geometry.
    """
    n = len(points)
    if n < 4:
        return False

    def orientation(a, b, c):
        return (b[0] - a[0]) * (c[1] - a[1]) - (b[1] - a[1]) * (c[0] - a[0])

    def on_segment(a, b, p):
        return (min(a[0], b[0]) - 1e-8 <= p[0] <= max(a[0], b[0]) + 1e-8
                and min(a[1], b[1]) - 1e-8 <= p[1] <= max(a[1], b[1]) + 1e-8)

    for i in range(n):
        a, b = points[i], points[(i + 1) % n]
        if a == b:
            return True
        for j in range(i + 1, n):
            if j == i + 1 or (i == 0 and j == n - 1):
                continue
            c, d = points[j], points[(j + 1) % n]
            o1, o2 = orientation(a, b, c), orientation(a, b, d)
            o3, o4 = orientation(c, d, a), orientation(c, d, b)
            if ((o1 > 1e-8 and o2 < -1e-8 or o1 < -1e-8 and o2 > 1e-8)
                and (o3 > 1e-8 and o4 < -1e-8 or o3 < -1e-8 and o4 > 1e-8)):
                return True
            if ((abs(o1) <= 1e-8 and on_segment(a, b, c))
                or (abs(o2) <= 1e-8 and on_segment(a, b, d))
                or (abs(o3) <= 1e-8 and on_segment(c, d, a))
                or (abs(o4) <= 1e-8 and on_segment(c, d, b))):
                return True
    return False


def trace_external_footprint_first(
    pdf_bytes: bytes,
    *,
    source_sha256: str,
    page_indices: Sequence[int],
    require_native_edge_support: bool = False,
) -> tuple[ExternalFootprintTrace, ...]:
    """Attempt one exterior outline per selected topology page, before inner geometry.

    The visual mask is a bounded *diagnostic candidate*, never physical wall
    existence/face ownership. Open or rival building envelopes are not promoted.
    No source locations or hand-drawn polygons are caller inputs.

    ``require_native_edge_support`` (default OFF: results are unchanged) abstains
    a near-rectangular candidate whose long edges are drawn only in a much
    lighter native pen than the wall linework inside it (a site or roof frame).
    Missing, ambiguous or oversized native evidence never abstains. See
    ``pb_source_footprint_native_edge_support_shadow``.
    """
    if not isinstance(pdf_bytes, bytes) or hashlib.sha256(pdf_bytes).hexdigest() != source_sha256:
        raise ValueError("external_footprint_original_source_sha_mismatch")
    if not isinstance(page_indices, (tuple, list)) or not page_indices or any(
        type(i) is not int or i < 0 for i in page_indices
    ) or len(set(page_indices)) != len(page_indices):
        raise ValueError("external_footprint_requires_unique_topology_pages")
    try:
        import cv2
        import fitz
        import numpy as np
    except ImportError:
        return tuple(_abstain(source_sha256, i, "external_footprint_raster_backend_unavailable")
                     for i in page_indices)

    results: list[ExternalFootprintTrace] = []
    with fitz.open(stream=pdf_bytes, filetype="pdf") as doc:
        for index in page_indices:
            if index >= len(doc):
                raise ValueError("external_footprint_page_outside_original")
            page = doc[index]
            # Bound raster memory on high-resolution A0/A1 plans.
            scale = _bounded_raster_scale(float(page.rect.width), float(page.rect.height))
            raster = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False, colorspace=fitz.csRGB)
            width, height = raster.width, raster.height
            pixels = np.frombuffer(raster.samples, dtype=np.uint8).reshape(height, width, 3)
            # Dark solid wall paint only; pale landscape, furniture fills and
            # green exclusion art never define the exterior wall outline.
            gray = cv2.cvtColor(pixels, cv2.COLOR_RGB2GRAY)
            r, g, b = (pixels[:, :, c].astype(np.int16) for c in range(3))
            green = (g > r * 1.25) & (g > b * 1.08) & (g > 40)
            ink = np.where((gray < 125) & ~green, 255, 0).astype(np.uint8)
            # Floor-plan title blocks are commonly printed in the lowest band.
            # This excludes text; never removes physical topological evidence
            # permanently from the original source PDF.
            ink[int(height * .82):, :] = 0
            outer = []
            competing_envelopes = 0
            for radius in (3, 5, 8):
                # The graduated close is for SHADOW connectivity only. It does
                # not instantiate a physical door, wall, or commercial area.
                closed = cv2.morphologyEx(
                    ink, cv2.MORPH_CLOSE,
                    cv2.getStructuringElement(cv2.MORPH_RECT, (radius, radius)),
                    iterations=1,
                )
                contours, _ = cv2.findContours(closed, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
                candidates = []
                sheet_area = float(width * height)
                for contour in contours:
                    area = abs(float(cv2.contourArea(contour)))
                    x, y, w, h = cv2.boundingRect(contour)
                    share = area / sheet_area
                    if not (.025 <= share <= .62) or w < width * .17 or h < height * .12:
                        continue
                    # Refuse title/page frames; there is no legitimate building
                    # wall physically traced on the sheet boundary.
                    if x < width * .012 or y < height * .012 or x + w > width * .988:
                        continue
                    if y + h > height * .82:
                        continue
                    polygon = cv2.approxPolyDP(
                        contour, max(1.5, .003 * cv2.arcLength(contour, True)), True
                    ).reshape(-1, 2)
                    if len(polygon) < 4 or len(polygon) > 200:
                        continue
                    candidates.append((area, (x, y, w, h), polygon))
                if candidates:
                    # The largest bounded enclosing trace is a *candidate*
                    # only. A competing building/site envelope cannot be
                    # independently authenticated by visual ink alone.
                    ranked = sorted(candidates, key=lambda item: item[0], reverse=True)
                    if _competing_disjoint_envelopes(ranked):
                        competing_envelopes = len(ranked)
                        break
                    outer = ranked
                    break
            if competing_envelopes:
                results.append(replace(
                    _abstain(source_sha256, index, "external_footprint_competing_disjoint_envelopes"),
                    candidate_count=competing_envelopes,
                ))
                continue
            if not outer:
                results.append(_abstain(
                    source_sha256, index, "external_footprint_no_closed_wall_ink_candidate",
                ))
                continue
            area, (x, y, w, h), polygon = outer[0]
            points = tuple(
                (round(float(px) / scale, 3), round(float(py) / scale, 3))
                for px, py in polygon
            )
            if len(set(points)) < 4 or not all(math.isfinite(q) for xy in points for q in xy):
                results.append(_abstain(source_sha256, index, "external_footprint_invalid_polygon"))
                continue
            if _polygon_has_self_intersection(points):
                results.append(_abstain(source_sha256, index, "external_footprint_self_intersecting_candidate"))
                continue
            if require_native_edge_support:
                from pb_source_footprint_native_edge_support_shadow import (
                    MAX_CANDIDATE_VERTICES,
                    STATUS_UNSUPPORTED,
                    assess_footprint_native_edge_support,
                )

                # The raster polygon is in VISIBLE page space; native rows are in the page's UNROTATED
                # space. Compare them in one space (identity on an unrotated page).
                try:
                    native_rows = page.get_drawings() if len(points) <= MAX_CANDIDATE_VERTICES else ()
                    native_points = tuple(
                        tuple(fitz.Point(px, py) * page.derotation_matrix) for px, py in points
                    )
                except (ValueError, RuntimeError, OSError, AttributeError):
                    native_rows, native_points = (), points
                if assess_footprint_native_edge_support(native_points, native_rows).status == STATUS_UNSUPPORTED:
                    results.append(_abstain(
                        source_sha256, index, "external_footprint_unverified_native_wall_edges",
                        drawings=len(native_rows),
                    ))
                    continue
            bbox = tuple(round(float(v) / scale, 3) for v in (x, y, x + w, y + h))
            frame_readable, frame_matrix = _read_page_frame(page)
            if not frame_readable:
                results.append(_abstain(source_sha256, index, "external_footprint_rotated_page_frame_unreadable"))
                continue
            results.append(ExternalFootprintTrace(
                source_sha256=source_sha256,
                page_index=index,
                status="CANDIDATE",
                reason="external_footprint_ink_trace_needs_physical_wall_owner_and_scale",
                polygon_pdf_pts=points,
                bbox_pdf_pts=bbox,
                candidate_count=len(outer),
                commercial_publishable=False,
                measurement_authorized=False,
                page_derotation_matrix=frame_matrix,
            ))
    return tuple(results)

@dataclass(frozen=True)
class BoundedFootprintDrawingScope:
    """Source-index-preserving diagnostics, never commercial physical walls."""

    status: str
    reason: str
    page_index: int
    drawings: tuple[dict | object, ...]
    selected_source_path_indices: tuple[int, ...]
    wall_native_primitive_count: int
    source_total_paths: int
    commercial_publishable: bool = False


def bound_native_drawings_to_footprint(
    drawings: Sequence[object],
    *,
    trace: ExternalFootprintTrace,
    expected_source_sha256: str,
) -> BoundedFootprintDrawingScope:
    """Scope the EXISTING native path list by a source-hashed exterior candidate.

    Keep the exact original path indices with inert rows outside the selected
    window. This is a candidate room-tracing *diagnostic* only. It cannot
    transform missing wall identity into proven exterior geometry. Cropping a
    dense page does not enlarge the 20,000-primitive owner limit.
    """
    from collections.abc import Mapping

    if trace.source_sha256 != expected_source_sha256:
        raise ValueError("footprint_source_revision_mismatch")
    if trace.status != "CANDIDATE" or trace.bbox_pdf_pts is None:
        return BoundedFootprintDrawingScope(
            "ABSTAINED", "footprint_candidate_required",
            trace.page_index, (), (), 0, len(drawings),
        )
    x0, y0, x1, y1 = trace.bbox_pdf_pts
    if not all(math.isfinite(n) for n in (x0, y0, x1, y1)) or not (
        x0 < x1 and y0 < y1
    ):
        raise ValueError("footprint_nonfinite_or_invalid_bbox")
    # The raster bbox is in display space; the rows are in native page space. Compare them in one space.
    native_bbox = footprint_bbox_in_native_space(trace)
    if native_bbox is None:
        return BoundedFootprintDrawingScope(
            "ABSTAINED", "footprint_frame_matrix_invalid",
            trace.page_index, (), (), 0, len(drawings),
        )
    x0, y0, x1, y1 = native_bbox
    # Source-PDF points, never a physical mm scale inference. Expand enough
    # to keep the wall's drawn stroke outside the visual envelope.
    padx = min(24.0, max(3.0, (x1 - x0) * .02))
    pady = min(24.0, max(3.0, (y1 - y0) * .02))
    inert = {"layer": "", "fill": None, "color": None, "items": ()}
    retained: list[object] = []
    indices: list[int] = []
    for index, row in enumerate(drawings):
        if not isinstance(row, Mapping) or not row.get("items"):
            retained.append(inert)
            continue
        box = row.get("rect")
        if box is None:
            retained.append(inert)
            continue
        try:
            a, b, c, d = map(float, (box.x0, box.y0, box.x1, box.y1))
        except (TypeError, ValueError, AttributeError):
            retained.append(inert)
            continue
        # A malformed/reversed source path rect cannot prove that its ink
        # falls inside this viewport. Treat as inert, never sort the reversed
        # coordinates into fabricated native wall ownership.
        if not all(math.isfinite(v) for v in (a, b, c, d)) or c < a or d < b:
            retained.append(inert)
            continue
        if c < x0 - padx or a > x1 + padx or d < y0 - pady or b > y1 + pady:
            retained.append(inert)
            continue
        indices.append(index)
        retained.append(row)

    # Count only true wall-support primitives (named/black/dark). Mid-gray
    # doorway/glazing evidence rows stay in the index-preserving keep-list
    # but must not alone authorize a bounded footprint viewport.
    from pb_layered_wall_doorway_room_ring_shadow import (
        _is_source_wall_support_row,
        _source_wall_ink_candidate_drawings,
    )

    wall_ink, _count, _green = _source_wall_ink_candidate_drawings(retained)
    primitives = sum(
        len(row.get("items", ()))
        for row in wall_ink
        if isinstance(row, Mapping) and _is_source_wall_support_row(row)
    )
    # The raster can return a closed contour from furniture, labels or a
    # page border. A candidate source-native viewport must actually retain
    # at least one eligible original wall-ink primitive. Otherwise it is an
    # empty selection, not a useful source-wall topology candidate.
    if primitives == 0:
        status = "ABSTAINED"
        reason = "bounded_source_viewport_has_no_native_wall_ink"
    elif primitives > 20_000:
        status = "ABSTAINED"
        reason = "bounded_source_viewport_exceeds_20000_primitive_cap"
    else:
        status = "CANDIDATE"
        reason = "bounded_footprint_trace_only_needs_physical_wall_proof"
    return BoundedFootprintDrawingScope(
        status, reason, trace.page_index, tuple(retained) if status == "CANDIDATE" else (),
        tuple(indices) if status == "CANDIDATE" else (),
        primitives, len(drawings),
    )


def refine_external_footprint_against_wall_ink(
    trace: ExternalFootprintTrace,
    drawings: Sequence[Mapping[str, object] | object],
) -> tuple[ExternalFootprintTrace, Mapping[str, object]]:
    """Collapse unsupported rectangular contour boxes using source wall ink.

    Shadow/candidate only. Does not mint walls, scale, or customer quantities.
    Genuine alcoves whose paired faces are painted stay in the polygon.
    """
    if trace.status != "CANDIDATE" or len(trace.polygon_pdf_pts) < 4:
        return trace, {
            "collapsed_detour_count": 0,
            "reason_codes": ["footprint_not_eligible_for_detour_refine"],
            "commercial_publishable": False,
            "measurement_authorized": False,
        }
    from pb_source_unsupported_rectangular_detour_shadow import (
        collapse_unsupported_rectangular_detours,
        wall_ink_segments_from_drawings,
    )

    # The raster polygon is in display space; the rows are in native page space. Compare them in one space,
    # then hand the corrected polygon back in the trace's own space.
    invalid_frame_receipt: Mapping[str, object] = {
        "collapsed_detour_count": 0,
        "reason_codes": ["footprint_frame_matrix_invalid"],
        "commercial_publishable": False,
        "measurement_authorized": False,
    }
    native_polygon = footprint_polygon_in_native_space(trace)
    if native_polygon is None:
        return trace, invalid_frame_receipt
    mapping_rows = tuple(
        row for row in drawings if isinstance(row, Mapping)
    )
    receipt = collapse_unsupported_rectangular_detours(
        native_polygon,
        wall_ink_segments_from_drawings(mapping_rows),
    )

    def receipt_in_trace_space() -> Mapping[str, object]:
        payload = receipt.to_dict()
        if trace.page_derotation_matrix is None:
            return payload
        shown = native_points_to_display_space(trace, receipt.polygon_pdf_pts)
        return {**payload, "polygon_pdf_pts": [list(p) for p in shown or ()]}

    if receipt.collapsed_detour_count <= 0:
        return trace, receipt_in_trace_space()
    # The old raster bbox still contains the rejected fake excursions.
    # Crop native-source review using the corrected, source-backed outline;
    # keep the regular scoping pad and all original source path indices.
    coords = (
        receipt.polygon_pdf_pts if trace.page_derotation_matrix is None
        else native_points_to_display_space(trace, receipt.polygon_pdf_pts)
    )
    if coords is None:  # the frame cannot carry the corrected outline back to the trace's own space
        return trace, invalid_frame_receipt
    corrected_bbox = (
        round(min(x for x, _ in coords), 3),
        round(min(y for _, y in coords), 3),
        round(max(x for x, _ in coords), 3),
        round(max(y for _, y in coords), 3),
    )
    refined = replace(
        trace,
        polygon_pdf_pts=coords,
        bbox_pdf_pts=corrected_bbox,
        reason=(
            "external_footprint_ink_trace_collapsed_unsupported_detours_"
            "needs_physical_wall_owner_and_scale"
        ),
    )
    return refined, receipt_in_trace_space()
