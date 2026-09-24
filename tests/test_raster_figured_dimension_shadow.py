from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from random import Random

from pb_figured_dimension_evidence import RasterCoordinateTransform
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_portable_raster_ocr_authority import OCRLine, RasterOCREvidenceRecord
from pb_raster_figured_dimension_shadow import (
    RasterAxisSegment,
    RasterDimensionScope,
    collect_raster_figured_dimension_shadow,
)


def _scope(
    *,
    placement=(0.0, 0.0, 200.0, 120.0),
    viewport="plan-1",
    source_hash="0" * 64,
):
    return RasterDimensionScope(
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=source_hash,
        snapshot_id="snap-1",
        page_id="228",
        viewport_id=viewport,
        image_id="xref-899",
        placement_bbox_pt=placement,
    )


def _record(lines, *, viewport="plan-1", target_region=(0.0, 0.0, 200.0, 120.0)):
    return RasterOCREvidenceRecord(
        record_id="ocr-record-1",
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256="0" * 64,
        snapshot_id="snap-1",
        page_id="228",
        viewport_id=viewport,
        target_region_pt=target_region,
        lines=tuple(lines),
        full_text=" ".join(line.text for line in lines),
        backend_name="tesseract",
        backend_version="test",
        dpi=300,
        confidence=None,
        reconciliation_status="provisional",
    )


def _transform(*, width_px=200.0, height_px=120.0, rotation=0):
    return RasterCoordinateTransform(
        page_width_pt=200.0,
        page_height_pt=120.0,
        raster_width_px=width_px,
        raster_height_px=height_px,
        rotation_deg=rotation,
    )


def _positive_segments(prefix=""):
    return [
        RasterAxisSegment(prefix + "dimension", (20.0, 60.0), (180.0, 60.0)),
        RasterAxisSegment(prefix + "witness-left", (20.0, 55.0), (20.0, 80.0)),
        RasterAxisSegment(prefix + "witness-right", (180.0, 55.0), (180.0, 80.0)),
    ]


def _run(lines=None, segments=None, *, transform=None, scope=None, record=None):
    lines = lines or [OCRLine("4100", 0.96, (90.0, 40.0, 110.0, 50.0))]
    return collect_raster_figured_dimension_shadow(
        ocr_record=record or _record(lines),
        segments=segments or _positive_segments(),
        transform=transform or _transform(),
        scope=scope or _scope(),
    )


def _candidate(result):
    found = [candidate for candidate in result.candidates if candidate.status is Status.CANDIDATE]
    assert len(found) == 1
    return found[0]


def test_two_sided_raster_witness_binding_is_candidate_only_and_never_area():
    result = _run()

    assert result.status is Status.CANDIDATE
    assert result.quantity_m2 is None
    candidate = _candidate(result)
    assert candidate.value_mm == 4100.0
    assert candidate.orientation == "horizontal"
    assert candidate.endpoints_pt == ((20.0, 60.0), (180.0, 60.0))
    assert set(candidate.witness_line_ids) == {"witness-left", "witness-right"}
    assert candidate.candidate_id
    assert "candidate_only" in candidate.reason_codes[0]


def test_typed_non_dimensions_do_not_enter_raster_dimension_candidates():
    lines = [
        OCRLine("2024", 0.99, (90.0, 40.0, 110.0, 50.0)),
        OCRLine("SCALE 1:100", 0.99, (60.0, 20.0, 120.0, 30.0)),
        OCRLine("W1", 0.99, (30.0, 20.0, 45.0, 30.0)),
        OCRLine("A142", 0.99, (130.0, 20.0, 160.0, 30.0)),
    ]
    result = _run(lines=lines)

    assert result.status is Status.ABSTAINED
    assert result.candidates == ()
    assert result.quantity_m2 is None


def test_missing_second_witness_abstains_instead_of_inventing_span():
    segments = _positive_segments()[:2]
    result = _run(segments=segments)

    assert result.status is Status.ABSTAINED
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.status is Status.ABSTAINED
    assert candidate.reason_codes == ("two_sided_witness_binding_unavailable",)
    assert candidate.endpoints_pt is None
    assert candidate.candidate_id is None


def test_two_plausible_dimension_lines_conflict_and_retain_alternatives():
    segments = _positive_segments() + [
        RasterAxisSegment("dimension-second", (20.0, 70.0), (180.0, 70.0)),
    ]
    result = _run(segments=segments)

    assert result.status is Status.CONFLICT
    assert len(result.candidates) == 1
    candidate = result.candidates[0]
    assert candidate.status is Status.CONFLICT
    assert candidate.reason_codes == ("competing_dimension_line_bindings",)
    assert len(candidate.alternatives) == 2
    assert len({alt.candidate_id for alt in candidate.alternatives}) == 2


def test_competing_ocr_values_at_same_source_position_conflict_before_geometry():
    lines = [
        OCRLine("4100", 0.96, (90.0, 40.0, 110.0, 50.0)),
        OCRLine("4700", 0.71, (90.5, 40.0, 110.5, 50.0)),
    ]
    result = _run(lines=lines)

    assert result.status is Status.CONFLICT
    assert len(result.candidates) == 2
    assert all(candidate.status is Status.CONFLICT for candidate in result.candidates)
    assert {
        candidate.reason_codes for candidate in result.candidates
    } == {("competing_ocr_values_same_source_position",)}
    assert {candidate.value_mm for candidate in result.candidates} == {4100.0, 4700.0}


def test_same_value_repeat_collapses_without_confidence_tie_break():
    lines = [
        OCRLine("4100", 0.20, (90.0, 40.0, 110.0, 50.0)),
        OCRLine("4100", 0.99, (90.0, 40.0, 110.0, 50.0)),
    ]
    result = _run(lines=lines)

    assert result.status is Status.CANDIDATE
    assert len([c for c in result.candidates if c.status is Status.CANDIDATE]) == 1
    assert _candidate(result).value_mm == 4100.0


def test_split_dimension_strokes_and_input_order_preserve_physical_candidate_id():
    original = _run()
    original_candidate = _candidate(original)

    segments = [
        RasterAxisSegment("dimension:a", (20.0, 60.0), (100.0, 60.0)),
        RasterAxisSegment("dimension:b", (100.0, 60.0), (180.0, 60.0)),
        RasterAxisSegment("witness-left", (20.0, 55.0), (20.0, 80.0)),
        RasterAxisSegment("witness-right", (180.0, 55.0), (180.0, 80.0)),
    ]
    shuffled = segments[:]
    Random(7).shuffle(shuffled)

    split_result = _run(segments=segments)
    shuffled_result = _run(segments=shuffled)

    assert split_result == shuffled_result
    split_candidate = _candidate(split_result)
    assert split_candidate.candidate_id == original_candidate.candidate_id
    assert split_candidate.endpoints_pt == original_candidate.endpoints_pt
    assert set(split_candidate.dimension_line_ids) == {"dimension:a", "dimension:b"}


def test_double_raster_resolution_preserves_pdf_geometry_and_stable_id():
    base = _candidate(_run())

    lines = [OCRLine("4100", 0.96, (180.0, 80.0, 220.0, 100.0))]
    segments = [
        RasterAxisSegment("dimension-hires", (40.0, 120.0), (360.0, 120.0)),
        RasterAxisSegment("witness-left-hires", (40.0, 110.0), (40.0, 160.0)),
        RasterAxisSegment("witness-right-hires", (360.0, 110.0), (360.0, 160.0)),
    ]
    result = _run(
        lines=lines,
        segments=segments,
        transform=_transform(width_px=400.0, height_px=240.0),
    )
    candidate = _candidate(result)

    assert candidate.endpoints_pt == base.endpoints_pt
    assert candidate.bbox_pt == base.bbox_pt
    assert candidate.candidate_id == base.candidate_id


def test_180_degree_raster_rotation_preserves_pdf_geometry_and_stable_id():
    base = _candidate(_run())

    lines = [OCRLine("4100", 0.96, (90.0, 70.0, 110.0, 80.0))]
    segments = [
        RasterAxisSegment("dimension-rot", (180.0, 60.0), (20.0, 60.0)),
        RasterAxisSegment("witness-left-rot", (180.0, 65.0), (180.0, 40.0)),
        RasterAxisSegment("witness-right-rot", (20.0, 65.0), (20.0, 40.0)),
    ]
    result = _run(
        lines=lines,
        segments=segments,
        transform=_transform(rotation=180),
    )
    candidate = _candidate(result)

    assert candidate.endpoints_pt == base.endpoints_pt
    assert candidate.bbox_pt == base.bbox_pt
    assert candidate.candidate_id == base.candidate_id


def test_pdf_translation_changes_only_owned_coordinates_not_binding_semantics():
    base = _candidate(_run())
    translated_scope = _scope(placement=(30.0, 45.0, 230.0, 165.0))
    result = _run(scope=translated_scope)
    candidate = _candidate(result)

    assert result.status is Status.CANDIDATE
    assert candidate.value_mm == base.value_mm
    assert candidate.orientation == base.orientation
    assert candidate.endpoints_pt == tuple(
        (x + 30.0, y + 45.0) for x, y in base.endpoints_pt
    )
    assert candidate.candidate_id != base.candidate_id


def test_unrelated_geometry_and_target_region_expansion_do_not_change_candidate():
    base = _candidate(_run())
    segments = _positive_segments() + [
        RasterAxisSegment("far-horizontal", (0.0, 110.0), (70.0, 110.0)),
        RasterAxisSegment("far-vertical", (195.0, 0.0), (195.0, 30.0)),
        RasterAxisSegment("diagonal-furniture", (10.0, 10.0), (40.0, 35.0)),
    ]
    record = _record(
        [OCRLine("4100", 0.96, (90.0, 40.0, 110.0, 50.0))],
        target_region=(-50.0, -50.0, 250.0, 170.0),
    )
    result = _run(record=record, segments=segments)
    candidate = _candidate(result)

    assert candidate.candidate_id == base.candidate_id
    assert candidate.endpoints_pt == base.endpoints_pt


def test_lineage_mismatch_abstains_before_geometry():
    record = replace(
        _record([OCRLine("4100", 0.96, (90.0, 40.0, 110.0, 50.0))]),
        source_sha256="1" * 64,
    )
    result = _run(record=record)

    assert result.status is Status.ABSTAINED
    assert result.reason_codes == ("ocr_source_hash_mismatch",)
    assert result.candidates == ()


def test_transform_must_match_explicit_image_placement_extent():
    bad_transform = RasterCoordinateTransform(
        page_width_pt=199.0,
        page_height_pt=120.0,
        raster_width_px=200.0,
        raster_height_px=120.0,
        rotation_deg=0,
    )

    try:
        _run(transform=bad_transform)
    except ValueError as exc:
        assert "placement width" in str(exc)
    else:
        raise AssertionError("mismatched transform must fail closed")


def test_replay_is_deterministic_and_inputs_are_not_mutated():
    lines = [OCRLine("4100", 0.96, (90.0, 40.0, 110.0, 50.0))]
    record = _record(lines)
    segments = _positive_segments()
    before_record = deepcopy(record)
    before_segments = deepcopy(segments)

    results = [
        _run(record=record, segments=segments)
        for _ in range(4)
    ]

    assert all(result == results[0] for result in results)
    assert _candidate(results[0]).candidate_id
    assert record == before_record
    assert segments == before_segments
    assert results[0].quantity_m2 is None
