from __future__ import annotations

import json
import math

import cv2
import fitz
import numpy as np

import pb_physical_opening_authority as g17
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _sheet() -> np.ndarray:
    gray = np.full((360, 640), 255, np.uint8)
    cv2.rectangle(gray, (30, 150), (240, 164), 0, -1)
    cv2.rectangle(gray, (400, 150), (610, 164), 0, -1)
    radius = 160
    cv2.line(gray, (240, 164), (240, 324), 0, 1)
    cv2.ellipse(
        gray,
        center=(240, 164),
        axes=(radius, radius),
        angle=0,
        startAngle=0,
        endAngle=90,
        color=0,
        thickness=1,
    )
    return gray


def _pdf(gray: np.ndarray) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=180.0)
        page.insert_image(page.rect, stream=_png(gray), keep_proportion=False)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _run(gray: np.ndarray, label: str):
    source = SourceVisibilityProducer(
        producer_method=f"diag-swing-{label}",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"diag-swing-{label}",
        source_bytes=_pdf(gray),
        source_locator=f"memory://diag-swing-{label}.pdf",
        page_ids=("1",),
    )
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=("1",),
    )

    calls = []
    original = g17._raster_door_swing_solutions

    def wrapped(thin_mask, pair, *, dpi):
        sols = original(thin_mask, pair, dpi=dpi)
        gap = pair.gap_x1 - pair.gap_x0 + 1
        pad = g17._raster_px(g17._RASTER_SWING_LEAF_JAMB_PAD_PT, dpi)
        configs = []
        for hinge_end, hinge_x, direction in (
            ("low", pair.gap_x0, 1),
            ("high", pair.gap_x1, -1),
        ):
            for side, face_y in ((-1, pair.row0), (1, pair.row1)):
                low_radius = max(
                    int(math.ceil(
                        gap * (1.0 - g17._RASTER_SWING_ARC_RADIUS_TOLERANCE)
                    )),
                    2,
                )
                high_radius = int(math.floor(
                    gap * (1.0 + g17._RASTER_SWING_ARC_RADIUS_TOLERANCE)
                ))
                best_cov = -1.0
                best_radius = None
                for radius in range(low_radius, high_radius + 1):
                    cov = g17._raster_swing_arc_coverage(
                        thin_mask,
                        (float(hinge_x), float(face_y)),
                        float(radius),
                        side=side,
                        direction=direction,
                    )
                    if cov > best_cov:
                        best_cov = cov
                        best_radius = radius
                leaf_cov = None
                if best_radius is not None:
                    if side == -1:
                        rows = slice(max(face_y - best_radius, 0), face_y)
                    else:
                        rows = slice(
                            face_y + 1,
                            min(face_y + 1 + best_radius, thin_mask.shape[0]),
                        )
                    strip = thin_mask[
                        rows,
                        max(hinge_x - pad, 0) : min(hinge_x + pad + 1, thin_mask.shape[1]),
                    ]
                    if strip.size:
                        leaf_cov = float(strip.any(axis=1).mean())
                configs.append({
                    "hinge_end": hinge_end,
                    "hinge_x": int(hinge_x),
                    "direction": int(direction),
                    "side": int(side),
                    "face_y": int(face_y),
                    "gap": int(gap),
                    "radius_range": [int(low_radius), int(high_radius)],
                    "best_radius": None if best_radius is None else int(best_radius),
                    "best_arc_coverage": float(best_cov),
                    "leaf_coverage": leaf_cov,
                })
        calls.append({
            "mask_shape": list(thin_mask.shape),
            "pair": {
                "row0": int(pair.row0),
                "row1": int(pair.row1),
                "gap_x0": int(pair.gap_x0),
                "gap_x1": int(pair.gap_x1),
                "a": list(pair.a),
                "b": list(pair.b),
                "reasons": list(pair.reasons),
            },
            "solutions": [
                {
                    "hinge_end": s.hinge_end,
                    "hinge_x": s.hinge_x,
                    "side": s.side,
                    "face_y": s.face_y,
                    "direction": s.direction,
                    "radius_px": s.radius_px,
                    "arc_coverage": s.arc_coverage,
                    "leaf_coverage": s.leaf_coverage,
                }
                for s in sols
            ],
            "configs": configs,
        })
        return sols

    g17._raster_door_swing_solutions = wrapped
    try:
        physical = source.physical_opening_authority()
        results = []
        records = {}
        for observation_id in published.raster_opening_primitive_observation_ids:
            result = physical.prove_existence(
                ObservationSelector(
                    document_id=published.revision.document_id,
                    revision_id=published.revision.revision_id,
                    source_sha256=published.revision.source_sha256,
                    snapshot_id=published.snapshot.snapshot_id,
                    observation_id=observation_id,
                )
            )
            results.append({
                "observation_id": observation_id,
                "status": result.status.value,
                "proposition": result.proposition,
                "reasons": list(result.reason_codes),
            })
            if result.existence_record is not None:
                records[result.existence_record.record_id] = {
                    "record_id": result.existence_record.record_id,
                    "pattern": result.existence_record.structural_pattern,
                    "bbox": result.existence_record.aperture_bbox_pt,
                }
    finally:
        g17._raster_door_swing_solutions = original

    return {
        "label": label,
        "input_shape": list(gray.shape),
        "primitive_count": len(published.raster_opening_primitive_observation_ids),
        "records": list(records.values()),
        "calls": calls,
        "result_reason_counts": {
            reason: sum(reason in row["reasons"] for row in results)
            for reason in sorted({r for row in results for r in row["reasons"]})
        },
    }


def main() -> None:
    base = _sheet()
    rotated = np.ascontiguousarray(np.rot90(base))
    print(json.dumps({
        "base": _run(base, "base"),
        "rotated": _run(rotated, "rotated"),
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
