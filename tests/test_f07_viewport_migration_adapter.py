from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_dimension_graph_constraint_engine import DimensionObservation
from pb_drawing_evidence_binding import DrawingViewType
from pb_figured_dimension_evidence import (
    BindingStatus,
    DimensionAnchorBinding,
    DimensionEvidenceBundle,
    ObservedGeometrySegment,
)
from pb_figured_span_scale_shadow import (
    FiguredSpanScaleScope,
    resolve_figured_span_scale_shadow,
)
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_migration_contracts import (
    EvidenceResolutionStatus,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_viewport_migration_adapter import (
    F07_VIEWPORT_NOT_AUTHORITATIVE,
    F07_VIEWPORT_PRODUCER_LINEAGE_INVALID,
    F07_VIEWPORT_SIBLING_OVERLAP,
    adapt_f07_viewport_to_migration,
)
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportBoundarySource,
    ViewportSegmentationStatus,
    is_authoritative_derived_viewport,
    segment_page_viewports,
)


SHA = "c" * 64
PAGE = 1


def _reopen(doc: fitz.Document) -> fitz.Document:
    payload = doc.tobytes()
    doc.close()
    return fitz.open(stream=payload, filetype="pdf")


def _columnar_grid_doc() -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=900, height=700)
    page.insert_text((80, 250), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((90, 620), "ROOF PLAN", fontsize=11)
    page.insert_text((380, 200), "ELEVATION E-01", fontsize=11)
    page.insert_text((380, 560), "SECTION S-01", fontsize=11)
    page.insert_text((680, 200), "ELEVATION E-02", fontsize=11)
    page.insert_text((680, 560), "SECTION S-02", fontsize=11)
    return _reopen(doc)


def _ordinary_partition_doc() -> fitz.Document:
    doc = fitz.open()
    page = doc.new_page(width=640, height=420)
    page.insert_text((80, 320), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((390, 320), "EAST ELEVATION", fontsize=11)
    return _reopen(doc)


def _context(
    *viewport_ids: str,
    revision_id: str = "rev-1",
    current_revision_id: str = "rev-1",
    source_sha256: str = SHA,
) -> ProviderContext:
    owned = tuple(viewport_ids)
    return ProviderContext(
        run_id="run",
        workspace_id="workspace",
        project_id="project",
        document_id="doc",
        source_sha256=source_sha256,
        revision_id=revision_id,
        current_revision_id=current_revision_id,
        selected_pages=(PAGE - 1,),
        owned_viewport_ids=owned,
        evidence_snapshot_id="snapshot",
        owned_page_numbers=(PAGE,),
        viewport_page_ownership=tuple((viewport_id, PAGE) for viewport_id in owned),
    )


def _visible_snapshot(viewports: list[SegmentedViewport]) -> tuple[tuple[object, ...], ...]:
    return tuple(
        (
            viewport.view_id,
            viewport.page_number,
            viewport.view_type,
            viewport.label,
            viewport.title_bbox,
            viewport.bounding_box,
            viewport.status,
            viewport.boundary_source,
            viewport.confidence,
            viewport.scale_raw,
            viewport.scale_denominator,
            viewport.scale_conflict,
            tuple(viewport.notes),
            repr(viewport.provenance),
        )
        for viewport in viewports
    )


def _dimension_bundle(
    *,
    viewport_id: str,
    bbox: tuple[float, float, float, float],
    two: bool = True,
) -> DimensionEvidenceBundle:
    x0, y0, x1, y1 = bbox
    width = x1 - x0
    height = y1 - y0
    if width < 120 or height < 120:
        raise AssertionError("fixture viewport is unexpectedly small")

    observations: list[DimensionObservation] = []
    bindings: list[DimensionAnchorBinding] = []
    geometry: list[ObservedGeometrySegment] = []

    specs = [
        ("d1", 2500.0, 70.875, (x0 + 30.0, y0 + 80.0)),
        ("d2", 1200.0, 34.02, (x0 + 30.0, y0 + 160.0)),
    ]
    if not two:
        specs = specs[:1]

    for observation_id, physical_mm, span_pt, origin in specs:
        start = origin
        end = (origin[0] + span_pt, origin[1])
        text_bbox = (
            origin[0] + 5.0,
            origin[1] - 22.0,
            min(origin[0] + 55.0, x1 - 2.0),
            origin[1] - 8.0,
        )
        observations.append(
            DimensionObservation(
                dimension_id=observation_id,
                source_page=PAGE,
                view_id=viewport_id,
                view_type=DrawingViewType.FLOOR_PLAN.value,
                bbox=text_bbox,
                raw_text=f"{physical_mm:g}",
                value=physical_mm,
                unit="mm",
                authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
                confidence=1.0,
            )
        )
        line_id = f"line-{observation_id}"
        w1 = f"w1-{observation_id}"
        w2 = f"w2-{observation_id}"
        bindings.append(
            DimensionAnchorBinding(
                observation_id=observation_id,
                status=BindingStatus.WITNESS_BOUND.value,
                dimension_line_id=line_id,
                witness_line_ids=(w1, w2),
                endpoints=(start, end),
            )
        )
        geometry.extend(
            [
                ObservedGeometrySegment(
                    segment_id=line_id,
                    source_page=PAGE,
                    start=start,
                    end=end,
                    view_id=viewport_id,
                ),
                ObservedGeometrySegment(
                    segment_id=w1,
                    source_page=PAGE,
                    start=(start[0], start[1] - 15.0),
                    end=(start[0], start[1] + 15.0),
                    view_id=viewport_id,
                ),
                ObservedGeometrySegment(
                    segment_id=w2,
                    source_page=PAGE,
                    start=(end[0], end[1] - 15.0),
                    end=(end[0], end[1] + 15.0),
                    view_id=viewport_id,
                ),
            ]
        )
    return DimensionEvidenceBundle(
        observations=observations,
        bindings=bindings,
        observed_geometry=geometry,
    )


def _scope(viewport_id: str) -> FiguredSpanScaleScope:
    return FiguredSpanScaleScope(
        document_id="doc",
        revision_id="rev-1",
        source_sha256=SHA,
        page_no=PAGE,
        viewport_id=viewport_id,
    )


def test_validated_columnar_title_grid_derived_is_preserved_and_accepted_by_shadow() -> None:
    doc = _columnar_grid_doc()
    viewports = segment_page_viewports(doc[0], page_number=PAGE)
    plan = next(v for v in viewports if v.view_type == DrawingViewType.FLOOR_PLAN.value)
    assert is_authoritative_derived_viewport(plan)

    context = _context(*(v.view_id for v in viewports))
    adapted = adapt_f07_viewport_to_migration(
        viewports,
        viewport_id=plan.view_id,
        context=context,
        page_no=PAGE,
    )
    assert not adapted.abstained
    assert adapted.viewport is not None
    assert adapted.ownership_proof is not None
    assert adapted.viewport.status is ViewportResolutionStatus.DERIVED
    assert adapted.viewport.metadata["boundary_source"] == "title_partition"
    assert adapted.viewport.metadata["partition_mode"] == "columnar_title_grid"
    assert adapted.viewport.metadata["grid_validated"] is True
    for key in (
        "column_index",
        "column_count",
        "row_index",
        "row_count",
        "title_bbox",
        "duplicate_title_bboxes",
    ):
        assert key in adapted.viewport.metadata

    bundle = _dimension_bundle(
        viewport_id=plan.view_id,
        bbox=adapted.viewport.bbox,
    )
    shadow = resolve_figured_span_scale_shadow(
        bundle,
        scope=_scope(plan.view_id),
        context=context,
        viewport=adapted.viewport,
        viewport_ownership_proof=adapted.ownership_proof,
    )
    assert shadow.status is EvidenceResolutionStatus.CORROBORATED
    assert len(shadow.candidates) == 2
    doc.close()


def test_resolved_viewport_remains_accepted_without_new_proof() -> None:
    viewport = ViewportEvidence(
        viewport_id="resolved-vp",
        document_id="doc",
        page_id=str(PAGE),
        bbox=(0.0, 0.0, 300.0, 300.0),
        view_type=DrawingViewType.FLOOR_PLAN.value,
        status=ViewportResolutionStatus.RESOLVED,
        confidence=1.0,
    )
    context = _context("resolved-vp")
    shadow = resolve_figured_span_scale_shadow(
        _dimension_bundle(viewport_id="resolved-vp", bbox=viewport.bbox, two=False),
        scope=_scope("resolved-vp"),
        context=context,
        viewport=viewport,
    )
    assert shadow.status is EvidenceResolutionStatus.CANDIDATE


def test_ordinary_title_partition_derived_is_rejected() -> None:
    doc = _ordinary_partition_doc()
    viewports = segment_page_viewports(doc[0], page_number=PAGE)
    plan = next(v for v in viewports if v.view_type == DrawingViewType.FLOOR_PLAN.value)
    assert plan.status == ViewportSegmentationStatus.DERIVED.value
    assert not is_authoritative_derived_viewport(plan)

    result = adapt_f07_viewport_to_migration(
        viewports,
        viewport_id=plan.view_id,
        context=_context(*(v.view_id for v in viewports)),
        page_no=PAGE,
    )
    assert result.abstained
    assert F07_VIEWPORT_NOT_AUTHORITATIVE in result.blocking_reasons
    doc.close()


def test_caller_forged_viewport_metadata_cannot_mint_derived_authority() -> None:
    viewport = ViewportEvidence(
        viewport_id="forged",
        document_id="doc",
        page_id=str(PAGE),
        bbox=(0.0, 0.0, 300.0, 300.0),
        view_type=DrawingViewType.FLOOR_PLAN.value,
        status=ViewportResolutionStatus.DERIVED,
        confidence=0.75,
        metadata={
            "boundary_source": "title_partition",
            "partition_mode": "columnar_title_grid",
            "grid_validated": True,
        },
    )
    shadow = resolve_figured_span_scale_shadow(
        _dimension_bundle(viewport_id="forged", bbox=viewport.bbox, two=False),
        scope=_scope("forged"),
        context=_context("forged"),
        viewport=viewport,
    )
    assert shadow.status is EvidenceResolutionStatus.ABSTAINED
    assert "authoritative_derived_ownership_missing" in shadow.reason_codes
    assert "viewport_not_resolved" in shadow.reason_codes


def test_grid_validated_without_segment_page_viewports_lineage_is_rejected() -> None:
    forged = SegmentedViewport(
        view_id="view_p1_1",
        page_number=PAGE,
        view_type=DrawingViewType.FLOOR_PLAN.value,
        label="GROUND FLOOR PLAN",
        title_bbox=(50.0, 250.0, 180.0, 265.0),
        bounding_box=(0.0, 0.0, 300.0, 350.0),
        status=ViewportSegmentationStatus.DERIVED.value,
        boundary_source=ViewportBoundarySource.TITLE_PARTITION.value,
        confidence=0.75,
        provenance={
            "partition_mode": "columnar_title_grid",
            "grid_validated": True,
            "column_index": 0,
            "column_count": 2,
            "row_index": 0,
            "row_count": 2,
            "title_bbox": (50.0, 250.0, 180.0, 265.0),
            "duplicate_title_bboxes": [],
        },
    )
    assert is_authoritative_derived_viewport(forged)
    result = adapt_f07_viewport_to_migration(
        [forged],
        viewport_id=forged.view_id,
        context=_context(forged.view_id),
        page_no=PAGE,
    )
    assert result.abstained
    assert any(
        reason.startswith(F07_VIEWPORT_PRODUCER_LINEAGE_INVALID)
        for reason in result.blocking_reasons
    )


def test_correct_partition_mode_with_wrong_boundary_source_is_rejected() -> None:
    doc = _columnar_grid_doc()
    viewports = segment_page_viewports(doc[0], page_number=PAGE)
    plan = next(v for v in viewports if v.view_type == DrawingViewType.FLOOR_PLAN.value)
    plan.boundary_source = ViewportBoundarySource.VECTOR_FRAME.value
    result = adapt_f07_viewport_to_migration(
        viewports,
        viewport_id=plan.view_id,
        context=_context(*(v.view_id for v in viewports)),
        page_no=PAGE,
    )
    assert result.abstained
    assert F07_VIEWPORT_NOT_AUTHORITATIVE in result.blocking_reasons
    doc.close()


def test_same_provenance_but_bbox_changed_downstream_is_rejected() -> None:
    doc = _columnar_grid_doc()
    viewports = segment_page_viewports(doc[0], page_number=PAGE)
    plan = next(v for v in viewports if v.view_type == DrawingViewType.FLOOR_PLAN.value)
    assert plan.bounding_box is not None
    x0, y0, x1, y1 = plan.bounding_box
    plan.bounding_box = (x0, y0, x1 - 10.0, y1)
    result = adapt_f07_viewport_to_migration(
        viewports,
        viewport_id=plan.view_id,
        context=_context(*(v.view_id for v in viewports)),
        page_no=PAGE,
    )
    assert result.abstained
    assert any(
        reason.startswith(F07_VIEWPORT_PRODUCER_LINEAGE_INVALID)
        for reason in result.blocking_reasons
    )
    doc.close()


def test_sibling_overlap_introduced_downstream_is_rejected() -> None:
    doc = _columnar_grid_doc()
    viewports = segment_page_viewports(doc[0], page_number=PAGE)
    usable = [v for v in viewports if v.bounding_box is not None]
    target, sibling = usable[0], usable[1]
    assert target.bounding_box is not None
    sibling.bounding_box = target.bounding_box
    result = adapt_f07_viewport_to_migration(
        viewports,
        viewport_id=target.view_id,
        context=_context(*(v.view_id for v in viewports)),
        page_no=PAGE,
    )
    assert result.abstained
    assert F07_VIEWPORT_SIBLING_OVERLAP in result.blocking_reasons
    doc.close()


def test_stale_revision_and_wrong_source_are_rejected() -> None:
    doc = _columnar_grid_doc()
    viewports = segment_page_viewports(doc[0], page_number=PAGE)
    target = next(v for v in viewports if is_authoritative_derived_viewport(v))

    stale = adapt_f07_viewport_to_migration(
        viewports,
        viewport_id=target.view_id,
        context=_context(
            *(v.view_id for v in viewports),
            revision_id="rev-1",
            current_revision_id="rev-2",
        ),
        page_no=PAGE,
    )
    assert stale.abstained
    assert "stale_revision" in stale.blocking_reasons

    context = _context(*(v.view_id for v in viewports))
    adapted = adapt_f07_viewport_to_migration(
        viewports,
        viewport_id=target.view_id,
        context=context,
        page_no=PAGE,
    )
    assert not adapted.abstained
    assert adapted.viewport is not None
    assert adapted.ownership_proof is not None

    shadow = resolve_figured_span_scale_shadow(
        _dimension_bundle(viewport_id=target.view_id, bbox=adapted.viewport.bbox, two=False),
        scope=FiguredSpanScaleScope(
            document_id="doc",
            revision_id="rev-1",
            source_sha256="d" * 64,
            page_no=PAGE,
            viewport_id=target.view_id,
        ),
        context=context,
        viewport=adapted.viewport,
        viewport_ownership_proof=adapted.ownership_proof,
    )
    assert shadow.status is EvidenceResolutionStatus.ABSTAINED
    assert "source_sha256_mismatch" in shadow.reason_codes
    doc.close()


def test_replay_stable_ids_input_order_invariance_and_no_mutation() -> None:
    doc = _columnar_grid_doc()
    first = segment_page_viewports(doc[0], page_number=PAGE)
    second = segment_page_viewports(doc[0], page_number=PAGE)
    target_id = next(v.view_id for v in first if is_authoritative_derived_viewport(v))
    context = _context(*(v.view_id for v in first))

    before = _visible_snapshot(first)
    one = adapt_f07_viewport_to_migration(
        first,
        viewport_id=target_id,
        context=context,
        page_no=PAGE,
    )
    reversed_result = adapt_f07_viewport_to_migration(
        list(reversed(first)),
        viewport_id=target_id,
        context=context,
        page_no=PAGE,
    )
    replay = adapt_f07_viewport_to_migration(
        second,
        viewport_id=target_id,
        context=context,
        page_no=PAGE,
    )

    assert not one.abstained
    assert not reversed_result.abstained
    assert not replay.abstained
    assert one.ownership_proof is not None
    assert reversed_result.ownership_proof is not None
    assert replay.ownership_proof is not None
    assert one.ownership_proof.ownership_id == reversed_result.ownership_proof.ownership_id
    assert one.ownership_proof.ownership_id == replay.ownership_proof.ownership_id
    assert one.ownership_proof.sibling_set_fingerprint == replay.ownership_proof.sibling_set_fingerprint
    assert _visible_snapshot(first) == before
    doc.close()


def test_live_extractor_remains_unwired_to_new_shadow_ownership_path() -> None:
    source = Path("pb_planreader_pdf_extractor.py").read_text(encoding="utf-8")
    assert "pb_viewport_migration_adapter" not in source
    assert "pb_figured_span_scale_shadow" not in source
