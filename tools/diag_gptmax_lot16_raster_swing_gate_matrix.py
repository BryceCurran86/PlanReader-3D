from __future__ import annotations

from collections import Counter
import hashlib
import json
import math
from pathlib import Path

import cv2
import numpy as np

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    RASTER_MASS_THRESHOLD,
    RASTER_LINE_THRESHOLD,
    RASTER_POCHE_MIN_PT,
    _raster_odd,
    _raster_scaled_px,
    _raster_hairline_mask,
    _raster_axis_registration_scales,
    _raster_band_boxes,
    _raster_analysis_box,
    _raster_pair_flanks,
    _raster_to_page_box,
    _raster_gap_box_page_px,
    _raster_box_pt,
    _raster_frame_line_groups,
    _raster_wall_face_continues,
    _raster_swing_perpendicular_scale_ratio,
    _raster_door_swing_solutions,
    _RASTER_SWING_LEAF_JAMB_PAD_PT,
    _RASTER_SWING_LEAF_MIN_COVERAGE,
    _RASTER_LINE_COVERAGE,
)
from pb_raster_opening_source_primitives import (
    RASTER_LINE_RUN,
    RASTER_THIN_INK_RUN,
    RASTER_WALL_BAND_FACE,
    RASTER_WALL_BAND_END,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


PDF = Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
EXPECTED_SHA = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
PAGE_ID = "3"


def _state(value) -> str:
    return str(getattr(value, "value", value))


def main() -> None:
    source_bytes = PDF.read_bytes()
    actual_sha = hashlib.sha256(source_bytes).hexdigest()
    if actual_sha != EXPECTED_SHA:
        raise SystemExit(f"source sha mismatch: {actual_sha}")

    producer = SourceVisibilityProducer(
        producer_method="diag_gptmax_lot16_raster_swing_gate_matrix",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="diag-gptmax-lot16-raster-swing-gate-matrix",
        source_bytes=source_bytes,
        source_locator=str(PDF),
        page_ids=(PAGE_ID,),
    )
    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=(PAGE_ID,),
    )

    png_bytes, _page_parent, native_frame, dpi = producer.render_raster_opening_source_page(
        published.revision.revision_id,
        PAGE_ID,
    )
    placements = producer.raster_opening_image_placements(
        published.revision.revision_id,
        PAGE_ID,
    )
    registration_scale = producer.raster_opening_registration_scale(
        published.revision.revision_id,
        PAGE_ID,
    )
    if registration_scale is None:
        registration_scale = (1.0, 1.0)

    encoded = np.frombuffer(png_bytes, dtype=np.uint8)
    gray = cv2.imdecode(encoded, cv2.IMREAD_GRAYSCALE)
    if gray is None or gray.ndim != 2 or gray.size == 0:
        raise SystemExit("unreadable raster opening render")
    mass = (gray < RASTER_MASS_THRESHOLD).astype(np.uint8)
    line_mask = (gray < RASTER_LINE_THRESHOLD).astype(np.uint8)
    sx, sy = registration_scale
    solid_x = _raster_odd(_raster_scaled_px(RASTER_POCHE_MIN_PT, dpi, sx))
    solid_y = _raster_odd(_raster_scaled_px(RASTER_POCHE_MIN_PT, dpi, sy))
    thick = cv2.morphologyEx(
        mass,
        cv2.MORPH_OPEN,
        cv2.getStructuringElement(cv2.MORPH_RECT, (solid_x, solid_y)),
    )
    thin_mask = _raster_hairline_mask(line_mask, thick)

    visibility = producer.source_visibility_authority()
    records = []
    resolution_reasons = Counter()
    for observation_id in published.raster_opening_primitive_observation_ids:
        result = visibility.resolve_visible(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.observation is not None
        ):
            records.append(result.observation)
        else:
            for reason in result.reason_codes:
                resolution_reasons[str(reason)] += 1

    by_kind_geometry = {}
    line_runs = []
    thin_runs = []
    for record in records:
        geometry = tuple(round(float(value), 6) for value in record.geometry)
        if len(geometry) != 4:
            continue
        by_kind_geometry[(record.observation_kind, geometry)] = record
        if record.observation_kind == RASTER_LINE_RUN:
            line_runs.append(record)
        if record.observation_kind == RASTER_THIN_INK_RUN:
            thin_runs.append(record)

    def primitive_record(kind: str, geometry_px):
        geometry_pt = tuple(
            round(float(value), 6)
            for value in (
                float(v) * 72.0 / float(dpi) for v in geometry_px
            )
        )
        return by_kind_geometry.get((kind, geometry_pt))

    def band_support(page_box, axis: str, *, high_end: bool):
        x0, y0, x1, y1 = page_box
        if axis == "horizontal":
            faces_px = ((x0, y0, x1, y0), (x0, y1, x1, y1))
            end_px = (x1, y0, x1, y1) if high_end else (x0, y0, x0, y1)
        else:
            faces_px = ((x0, y0, x0, y1), (x1, y0, x1, y1))
            end_px = (x0, y1, x1, y1) if high_end else (x0, y0, x1, y0)
        rows = [primitive_record(RASTER_WALL_BAND_FACE, g) for g in faces_px]
        rows.append(primitive_record(RASTER_WALL_BAND_END, end_px))
        if any(row is None for row in rows):
            return ()
        return tuple(row for row in rows if row is not None)

    def frame_support(pair, axis: str, groups):
        gap_length = pair.gap_x1 - pair.gap_x0 + 1
        selected = {}
        for group_start, group_end in groups:
            matched_group = False
            for record in line_runs:
                line = tuple(float(value) * float(dpi) / 72.0 for value in record.geometry)
                if axis == "horizontal":
                    if abs(line[1] - line[3]) > 0.51:
                        continue
                    row = (line[1] + line[3]) / 2.0
                    if row < group_start - 0.51 or row > group_end + 0.51:
                        continue
                    run_start, run_end = sorted((line[0], line[2]))
                else:
                    if abs(line[0] - line[2]) > 0.51:
                        continue
                    row = (line[0] + line[2]) / 2.0
                    if row < group_start - 0.51 or row > group_end + 0.51:
                        continue
                    run_start, run_end = sorted((line[1], line[3]))
                overlap = max(
                    0.0,
                    min(run_end, float(pair.gap_x1))
                    - max(run_start, float(pair.gap_x0))
                    + 1.0,
                )
                if overlap / float(gap_length) + 1e-12 < _RASTER_LINE_COVERAGE:
                    continue
                selected[record.observation_id] = record
                matched_group = True
            if not matched_group:
                return ()
        return tuple(selected[k] for k in sorted(selected))

    def swing_leaf_support(solution, axis: str, along_scale: float):
        pad = _raster_scaled_px(
            _RASTER_SWING_LEAF_JAMB_PAD_PT,
            dpi,
            along_scale,
        )
        expected_start = (
            solution.face_y - solution.perpendicular_radius_px
            if solution.side == -1
            else solution.face_y + 1
        )
        expected_end = (
            solution.face_y - 1
            if solution.side == -1
            else solution.face_y + solution.perpendicular_radius_px
        )
        expected_start, expected_end = sorted((float(expected_start), float(expected_end)))
        expected_length = max(expected_end - expected_start + 1.0, 1.0)
        matched = {}
        for record in thin_runs:
            line = tuple(float(value) * float(dpi) / 72.0 for value in record.geometry)
            if axis == "vertical":
                line = (line[1], line[0], line[3], line[2])
            if abs(line[0] - line[2]) > 0.51:
                continue
            leaf_x = (line[0] + line[2]) / 2.0
            if abs(leaf_x - float(solution.hinge_x)) > float(pad) + 0.51:
                continue
            run_start, run_end = sorted((line[1], line[3]))
            overlap = max(
                0.0,
                min(run_end, expected_end)
                - max(run_start, expected_start)
                + 1.0,
            )
            if overlap / expected_length + 1e-12 < _RASTER_SWING_LEAF_MIN_COVERAGE:
                continue
            if solution.side == -1:
                if abs(run_end - float(solution.face_y)) > float(pad) + 1.0:
                    continue
            else:
                if abs(run_start - float(solution.face_y)) > float(pad) + 1.0:
                    continue
            matched[record.observation_id] = record
        return tuple(matched[k] for k in sorted(matched))

    def placement_ratios(gap_box_pt, axis: str):
        x0, y0, x1, y1 = (float(value) for value in gap_box_pt)
        rows = []
        tol = 1e-6
        for placement in placements:
            bx0, by0, bx1, by1 = placement.bbox_pt
            if not (
                bx0 - tol <= x0
                and x1 <= bx1 + tol
                and by0 - tol <= y0
                and y1 <= by1 + tol
            ):
                continue
            psx = (bx1 - bx0) / float(placement.pixel_width)
            psy = (by1 - by0) / float(placement.pixel_height)
            ratio = psy / psx if axis == "horizontal" else psx / psy
            rows.append({
                "bbox_pt": [float(v) for v in placement.bbox_pt],
                "pixel_width": int(placement.pixel_width),
                "pixel_height": int(placement.pixel_height),
                "sx_pt_per_px": psx,
                "sy_pt_per_px": psy,
                "perpendicular_ratio": ratio,
            })
        return rows

    rows = []
    stage_counts = Counter()
    unity_positive = []
    local_positive = []
    current_positive = []
    for axis in ("horizontal", "vertical"):
        along_scale, cross_scale = _raster_axis_registration_scales(axis, registration_scale)
        page_boxes = _raster_band_boxes(
            thick,
            dpi=dpi,
            axis=axis,
            registration_scale=registration_scale,
        )
        analysis_boxes = tuple(_raster_analysis_box(box, axis) for box in page_boxes)
        work_thick = thick if axis == "horizontal" else np.ascontiguousarray(thick.T)
        work_line = line_mask if axis == "horizontal" else np.ascontiguousarray(line_mask.T)
        work_thin = thin_mask if axis == "horizontal" else np.ascontiguousarray(thin_mask.T)

        for pair in _raster_pair_flanks(
            work_thick,
            analysis_boxes,
            dpi=dpi,
            along_scale=along_scale,
            cross_scale=cross_scale,
        ):
            if pair.reasons:
                for reason in pair.reasons:
                    stage_counts["pair_blocked:" + str(reason)] += 1
                continue

            page_a = _raster_to_page_box(pair.a, axis)
            page_b = _raster_to_page_box(pair.b, axis)
            support_a = band_support(page_a, axis, high_end=True)
            support_b = band_support(page_b, axis, high_end=False)
            if not support_a or not support_b:
                stage_counts["band_support_missing"] += 1
                continue

            gap_box_px = _raster_gap_box_page_px(pair, axis)
            gap_box_pt = tuple(round(value, 6) for value in _raster_box_pt(gap_box_px, dpi))

            groups = _raster_frame_line_groups(
                work_line,
                pair,
                dpi=dpi,
                cross_scale=cross_scale,
            )
            face_continues = bool(groups) and _raster_wall_face_continues(work_line, pair)
            frames = (
                frame_support(pair, axis, groups)
                if groups and not face_continues
                else ()
            )
            framed_positive = bool(frames) and len({
                record.observation_id
                for record in (*support_a, *support_b, *frames)
            }) >= 8

            local_ratio = _raster_swing_perpendicular_scale_ratio(
                gap_box_pt,
                axis,
                placements,
            )
            local_solutions = (
                ()
                if local_ratio is None
                else _raster_door_swing_solutions(
                    work_thin,
                    pair,
                    dpi=dpi,
                    perpendicular_scale_ratio=local_ratio,
                    along_scale=along_scale,
                )
            )
            unity_solutions = _raster_door_swing_solutions(
                work_thin,
                pair,
                dpi=dpi,
                perpendicular_scale_ratio=1.0,
                along_scale=along_scale,
            )
            local_leaf = (
                swing_leaf_support(local_solutions[0], axis, along_scale)
                if len(local_solutions) == 1
                else ()
            )
            unity_leaf = (
                swing_leaf_support(unity_solutions[0], axis, along_scale)
                if len(unity_solutions) == 1
                else ()
            )
            current_ok = (
                not framed_positive
                and local_ratio is not None
                and len(local_solutions) == 1
                and len(local_leaf) == 1
            )

            row = {
                "axis": axis,
                "gap_box_pt": [float(v) for v in gap_box_pt],
                "gap_length_pt": (
                    float(gap_box_pt[2] - gap_box_pt[0])
                    if axis == "horizontal"
                    else float(gap_box_pt[3] - gap_box_pt[1])
                ),
                "band_support_a_count": len(support_a),
                "band_support_b_count": len(support_b),
                "frame_group_count": len(groups),
                "face_continues": bool(face_continues),
                "frame_support_count": len(frames),
                "framed_positive": bool(framed_positive),
                "local_ratio": local_ratio,
                "placement_matches": placement_ratios(gap_box_pt, axis),
                "unity_solution_count": len(unity_solutions),
                "local_solution_count": len(local_solutions),
                "unity_leaf_support_count": len(unity_leaf),
                "local_leaf_support_count": len(local_leaf),
                "unity_solutions": [
                    {
                        "hinge_end": s.hinge_end,
                        "side": int(s.side),
                        "radius_px": int(s.radius_px),
                        "perpendicular_radius_px": int(s.perpendicular_radius_px),
                        "arc_coverage": float(s.arc_coverage),
                        "leaf_coverage": float(s.leaf_coverage),
                    }
                    for s in unity_solutions
                ],
                "local_solutions": [
                    {
                        "hinge_end": s.hinge_end,
                        "side": int(s.side),
                        "radius_px": int(s.radius_px),
                        "perpendicular_radius_px": int(s.perpendicular_radius_px),
                        "arc_coverage": float(s.arc_coverage),
                        "leaf_coverage": float(s.leaf_coverage),
                    }
                    for s in local_solutions
                ],
                "current_swing_positive": bool(current_ok),
            }
            rows.append(row)

            if len(unity_solutions) == 1:
                unity_positive.append(row)
            if len(local_solutions) == 1:
                local_positive.append(row)
            if current_ok:
                current_positive.append(row)

            if framed_positive:
                stage_counts["framed_positive"] += 1
            elif local_ratio is None:
                stage_counts["swing_blocked:no_local_registration"] += 1
            elif len(local_solutions) == 0 and len(unity_solutions) == 1:
                stage_counts["swing_blocked:registration_changed_solution"] += 1
            elif len(local_solutions) == 0:
                stage_counts["swing_blocked:no_pixel_solution"] += 1
            elif len(local_solutions) > 1:
                stage_counts["swing_blocked:ambiguous_pixel_solution"] += 1
            elif len(local_leaf) != 1:
                stage_counts["swing_blocked:leaf_lineage_support"] += 1
            else:
                stage_counts["swing_positive"] += 1

    payload = {
        "source_sha256": actual_sha,
        "page_id": PAGE_ID,
        "rotation": int(getattr(native_frame, "rotation", 0) or 0),
        "dpi": int(dpi),
        "registration_scale": [float(v) for v in registration_scale],
        "image_placement_count": len(placements),
        "primitive_observation_count": len(published.raster_opening_primitive_observation_ids),
        "resolved_primitive_count": len(records),
        "primitive_resolution_reason_counts": dict(resolution_reasons.most_common()),
        "primitive_kind_counts": dict(Counter(r.observation_kind for r in records).most_common()),
        "line_run_count": len(line_runs),
        "thin_run_count": len(thin_runs),
        "clean_pair_count": len(rows),
        "stage_counts": dict(stage_counts.most_common()),
        "unity_pixel_solution_count": len(unity_positive),
        "local_pixel_solution_count": len(local_positive),
        "current_swing_positive_count": len(current_positive),
        "unity_pixel_solution_rows": unity_positive,
        "local_pixel_solution_rows": local_positive,
        "current_swing_positive_rows": current_positive,
        "all_clean_pair_rows": rows,
    }
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
