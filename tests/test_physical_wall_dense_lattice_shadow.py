from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace

import fitz

import pb_physical_wall_candidate_authority as wall_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    PhysicalWallCandidateSelector,
)
from pb_physical_wall_dense_lattice_shadow import (
    DENSE_LATTICE_EVALUATED,
    DENSE_LATTICE_GRID_LIKE,
    DENSE_LATTICE_UNAVAILABLE,
    evaluate_physical_wall_dense_lattice_shadow,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def _line(
    segment_id: str,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    *,
    path_index: int,
    width: float = 0.24,
    stroke=(0.5, 0.5, 0.5),
    layer: str = "",
) -> dict:
    return {
        "id": segment_id,
        "kind": "line",
        "kind_present": True,
        "x1": float(x1),
        "y1": float(y1),
        "x2": float(x2),
        "y2": float(y2),
        "path_index": path_index,
        "width": float(width),
        "width_present": True,
        "stroke": stroke,
        "stroke_present": True,
        "fill": None,
        "fill_present": False,
        "layer": layer,
        "layer_present": bool(layer),
        "dashes": "[] 0",
        "dashes_present": True,
    }


def _record(wall_id: str, source_ids: tuple[str, ...], *, orientation: str):
    if orientation == "horizontal":
        pts = ((0.0, 20.0), (40.0, 20.0))
    else:
        pts = ((20.0, 0.0), (20.0, 40.0))
    return SimpleNamespace(
        wall_candidate_id=wall_id,
        wall_candidate=SimpleNamespace(
            representation="single_line",
            centerline_pts=pts,
        ),
        physical_identity=SimpleNamespace(source_primitive_ids=source_ids),
    )


def _grid(
    *,
    scale: float = 1.0,
    translate=(0.0, 0.0),
    rotate: bool = False,
    split_candidate: bool = False,
):
    tx, ty = translate
    coords = (0.0, 10.0, 20.0, 30.0, 40.0)
    segments = []
    path = 0

    def transform(x: float, y: float):
        x *= scale
        y *= scale
        if rotate:
            x, y = -y, x
        return x + tx, y + ty

    for index, y in enumerate(coords):
        if index == 2 and split_candidate:
            for suffix, (a, b) in enumerate(((0.0, 20.0), (20.0, 40.0))):
                p1 = transform(a, y)
                p2 = transform(b, y)
                segments.append(
                    _line(
                        f"h-{index}-{suffix}",
                        *p1,
                        *p2,
                        path_index=path,
                        width=0.24 * scale,
                    )
                )
                path += 1
        else:
            p1 = transform(0.0, y)
            p2 = transform(40.0, y)
            segments.append(
                _line(
                    f"h-{index}",
                    *p1,
                    *p2,
                    path_index=path,
                    width=0.24 * scale,
                )
            )
            path += 1

    for index, x in enumerate(coords):
        p1 = transform(x, 0.0)
        p2 = transform(x, 40.0)
        segments.append(
            _line(
                f"v-{index}",
                *p1,
                *p2,
                path_index=path,
                width=0.24 * scale,
            )
        )
        path += 1

    # A second explicit source width makes drawing-relative "thin" meaningful.
    p1 = transform(100.0, 100.0)
    p2 = transform(140.0, 100.0)
    segments.append(
        _line(
            "thick-unrelated",
            *p1,
            *p2,
            path_index=path,
            width=0.48 * scale,
            stroke=(0.0, 0.0, 0.0),
        )
    )

    source_ids = (
        ("h-2-0", "h-2-1") if split_candidate else ("h-2",)
    )
    orientation = "vertical" if rotate else "horizontal"
    return segments, _record("candidate", source_ids, orientation=orientation)


def _evaluate(segments, record):
    return evaluate_physical_wall_dense_lattice_shadow(
        records=(record,),
        source_segments=segments,
        page_id="1",
        decision_scope_id="scope",
    )


def test_dense_thin_orthogonal_regular_lattice_is_shadow_classified() -> None:
    segments, record = _grid()
    result = _evaluate(segments, record)

    assert result.status == DENSE_LATTICE_EVALUATED
    assert result.grid_like_wall_candidate_ids == ("candidate",)
    finding = result.findings[0]
    assert finding.reason_codes == (DENSE_LATTICE_GRID_LIKE,)
    assert finding.parallel_coordinate_count == 5
    assert finding.perpendicular_coordinate_count == 5
    assert finding.repeated_parallel_gap_count == 4
    assert finding.perpendicular_intersection_count == 5
    assert finding.representative_spacing_pt == 10.0


def test_irregular_parallel_spacing_is_not_grid_like() -> None:
    segments, record = _grid()
    replacements = {0.0: 0.0, 10.0: 7.0, 20.0: 19.0, 30.0: 34.0, 40.0: 55.0}
    for segment in segments:
        if str(segment["id"]).startswith("h-"):
            y = replacements[round(float(segment["y1"]), 6)]
            segment["y1"] = y
            segment["y2"] = y
    result = _evaluate(segments, record)
    assert result.grid_like_wall_candidate_ids == ()


def test_wall_named_source_layer_is_not_grid_negative_evidence() -> None:
    segments, record = _grid()
    for segment in segments:
        if segment["id"] == "h-2":
            segment["layer"] = "A-WALL-PARTITION"
            segment["layer_present"] = True
    result = _evaluate(segments, record)
    assert result.grid_like_wall_candidate_ids == ()


def test_single_source_width_cannot_claim_relative_thinness() -> None:
    segments, record = _grid()
    segments = [item for item in segments if item["id"] != "thick-unrelated"]
    result = _evaluate(segments, record)
    assert result.status == DENSE_LATTICE_EVALUATED
    assert result.grid_like_wall_candidate_ids == ()


def test_translation_rotation_and_uniform_scale_preserve_shadow_metrics() -> None:
    baseline_segments, baseline_record = _grid()
    baseline = _evaluate(baseline_segments, baseline_record).findings[0]

    transformed_segments, transformed_record = _grid(
        scale=3.0,
        translate=(137.0, -41.0),
        rotate=True,
    )
    transformed = _evaluate(transformed_segments, transformed_record).findings[0]

    assert transformed.wall_candidate_id == baseline.wall_candidate_id
    assert transformed.parallel_coordinate_count == baseline.parallel_coordinate_count
    assert (
        transformed.perpendicular_coordinate_count
        == baseline.perpendicular_coordinate_count
    )
    assert (
        transformed.repeated_parallel_gap_count
        == baseline.repeated_parallel_gap_count
    )
    assert (
        transformed.perpendicular_intersection_count
        == baseline.perpendicular_intersection_count
    )
    assert transformed.representative_spacing_pt == 30.0
    assert transformed.family_width_pt == 0.72


def test_input_order_and_unrelated_content_do_not_change_finding() -> None:
    segments, record = _grid()
    baseline = _evaluate(segments, record)

    unrelated = _line(
        "unrelated-diagonal",
        500.0,
        500.0,
        530.0,
        517.0,
        path_index=999,
        width=0.72,
        stroke=(1.0, 0.0, 0.0),
    )
    shuffled = list(reversed([*segments, unrelated]))
    changed = _evaluate(shuffled, record)

    assert changed.grid_like_wall_candidate_ids == baseline.grid_like_wall_candidate_ids
    assert changed.findings == baseline.findings


def test_collinear_source_split_preserves_lattice_metrics() -> None:
    baseline_segments, baseline_record = _grid()
    baseline = _evaluate(baseline_segments, baseline_record).findings[0]

    split_segments, split_record = _grid(split_candidate=True)
    split = _evaluate(split_segments, split_record).findings[0]

    assert split.parallel_coordinate_count == baseline.parallel_coordinate_count
    assert split.perpendicular_coordinate_count == baseline.perpendicular_coordinate_count
    assert split.repeated_parallel_gap_count == baseline.repeated_parallel_gap_count
    assert (
        split.perpendicular_intersection_count
        == baseline.perpendicular_intersection_count
    )
    assert split.representative_spacing_pt == baseline.representative_spacing_pt


def test_evaluator_is_deterministic_and_does_not_mutate_inputs() -> None:
    segments, record = _grid()
    before = deepcopy(segments)

    first = _evaluate(segments, record)
    second = _evaluate(segments, record)

    assert second == first
    assert segments == before


def _pdf_bytes() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=240.0)
        for index, width in enumerate((0.5, 1.0, 2.0, 3.0)):
            y = 50.0 + index * 40.0
            page.draw_line(
                (40.0, y),
                (280.0, y),
                color=(0.0, 0.0, 0.0),
                width=width,
            )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _resolve(payload: bytes, *, method: str):
    source = SourceVisibilityProducer(
        producer_method=method,
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="dense-lattice-shadow-source",
        source_bytes=payload,
        source_locator="memory://dense-lattice-shadow-source.pdf",
    )
    authority = PhysicalWallCandidateProducer.from_source_visibility_producer(
        source,
        page_ids=("1",),
    ).authority()
    selector = PhysicalWallCandidateSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        decision_scope_id="wall-source:page-1",
    )
    return authority.resolve_scope(selector)


def _live_surface(result):
    return (
        result.status,
        result.scope_complete,
        result.records,
        result.source_observation_ids,
        result.document_id,
        result.revision_id,
        result.source_sha256,
        result.snapshot_id,
        result.page_id,
        result.decision_scope_id,
        result.reason_codes,
        result.equivalence,
        result.proposition,
        result.scope_kind,
        result.viewport_id,
        result.viewport_bbox,
        result.viewport_view_type,
        result.viewport_status,
        result.viewport_boundary_source,
        result.viewport_producer_fingerprint,
        result.viewport_sibling_set_fingerprint,
        result.scope_boundary_observation_ids,
        result.ambiguous_source_observation_ids,
        result.schema_version,
        result.boundary_evaluation,
        result.source_metadata_table,
    )


def test_shadow_failure_cannot_change_live_wall_scope(monkeypatch) -> None:
    payload = _pdf_bytes()
    baseline = _resolve(payload, method="dense-lattice-shadow-failure")
    assert baseline.status is EvidenceResolutionStatus.CORROBORATED
    assert baseline.dense_lattice_evaluation is not None

    def boom(**_kwargs):
        raise RuntimeError("synthetic")

    monkeypatch.setattr(
        wall_authority,
        "evaluate_physical_wall_dense_lattice_shadow",
        boom,
    )
    degraded = _resolve(payload, method="dense-lattice-shadow-failure")

    assert degraded.dense_lattice_evaluation is not None
    assert degraded.dense_lattice_evaluation.status == DENSE_LATTICE_UNAVAILABLE
    assert degraded.dense_lattice_evaluation.reason_code == (
        "dense_lattice_shadow_error:RuntimeError"
    )
    assert _live_surface(degraded) == _live_surface(baseline)
