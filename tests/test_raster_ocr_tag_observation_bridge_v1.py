from __future__ import annotations

import inspect

import fitz
import pytest

from pb_clos_opening_tag_spatial_ranking import clos_passing_tag_observations
from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import MockOCRBackend, OCRLine, RapidOCRBackend
from pb_raster_ocr_tag_observation_bridge import (
    RASTER_OCR_TAG_BRIDGE_NO_TAGS,
    RASTER_OCR_TAG_BRIDGE_SCOPE_MISMATCH,
    RasterOCRTagObservationBridge,
)
from pb_source_observation_authority import (
    PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
    ObservationSelector,
)
from pb_source_opening_candidate_authority import (
    IdentityState,
    OpeningIdentityResolver,
    PhysicalOpeningCandidateRecord,
    SourceToleranceProvenance,
    authenticate_viewport_decision,
    derive_deterministic_candidate_id,
)
from pb_source_visibility_authority import (
    RASTER_OCR_PUBLISHED_CANDIDATE_ONLY,
    RASTER_OCR_SOURCE_OBSERVATION_EXISTS,
    SourceVisibilityProducer,
)
from pb_viewport_segmentation import SegmentedViewport
from pb_viewport_view_class_authority import (
    VIEW_KIND_FLOOR_PLAN,
    VIEW_KIND_SCHEDULE,
    ViewportViewClassProducer,
    ViewportViewClassSelector,
)


def _pdf_bytes() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=240, height=240)
    page.draw_line((10, 10), (220, 10), color=(0, 0, 0), width=1)
    payload = doc.tobytes()
    doc.close()
    return payload


def _ingested_source(document_id: str = "ocr-bridge-doc"):
    producer = SourceVisibilityProducer(
        producer_method="ocr-bridge-test",
        producer_version="1.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=_pdf_bytes(),
        source_locator=f"memory://{document_id}.pdf",
    )
    return producer, published


def _publish_fake_rapidocr(
    monkeypatch: pytest.MonkeyPatch,
    producer: SourceVisibilityProducer,
    published,
    lines: tuple[OCRLine, ...],
):
    monkeypatch.setattr(RapidOCRBackend, "is_available", lambda self: True)
    monkeypatch.setattr(RapidOCRBackend, "version", property(lambda self: "test-rapid-1"))
    monkeypatch.setattr(
        RapidOCRBackend,
        "extract_lines",
        lambda self, image, dpi=150: lines,
    )
    backend = RapidOCRBackend()
    result = producer.publish_page_raster_ocr_observations(
        revision_id=published.revision.revision_id,
        expected_snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        backend=backend,
        dpi=300,
    )
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.reason_codes == (RASTER_OCR_PUBLISHED_CANDIDATE_ONLY,)
    assert result.published is not None
    current = producer.published_snapshot_for_revision(
        published.revision.revision_id
    )
    assert current is not None
    assert current.snapshot.snapshot_id == result.published.snapshot.snapshot_id
    return result, current


def _authenticated_viewport(
    current,
    *,
    view_kind: str = VIEW_KIND_FLOOR_PLAN,
    viewport_id: str = "vp-floor-1",
    bbox=(0.0, 0.0, 180.0, 180.0),
    status: str = "resolved",
):
    selector = ViewportViewClassSelector(
        document_id=current.revision.document_id,
        revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,
        snapshot_id=current.snapshot.snapshot_id,
        viewport_id=viewport_id,
    )
    class_producer = ViewportViewClassProducer.create()
    class_producer.publish(
        selector,
        view_kind=view_kind,
        evidence_observation_ids=(current.snapshot.observation_ids[0],),
    )
    viewport = SegmentedViewport(
        view_id=viewport_id,
        page_number=1,
        view_type=view_kind,
        label="GROUND FLOOR PLAN",
        title_bbox=(0.0, 0.0, 10.0, 10.0),
        bounding_box=bbox,
        status=status,
        boundary_source="test_authenticated_boundary",
        confidence=1.0,
    )
    return authenticate_viewport_decision(
        viewport=viewport,
        view_class_authority=class_producer.authority(),
        selector=selector,
        require_uncropped=True,
    )


def _line(text: str, bbox) -> OCRLine:
    return OCRLine(
        text=text,
        confidence=0.99,
        bbox_px=tuple(float(v) for v in bbox),
        bbox_pt=tuple(float(v) for v in bbox),
    )


def test_producer_owned_ocr_is_derived_from_ingested_source_and_stays_nonphysical(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer, published = _ingested_source()
    result, _current = _publish_fake_rapidocr(
        monkeypatch,
        producer,
        published,
        (_line("W-1", (20, 20, 40, 30)),),
    )
    assert result.published is not None
    observation_id = result.published.ocr_observation_ids[0]

    resolved = producer.raster_ocr_authority().resolve_ocr(
        ObservationSelector(
            document_id=result.published.revision.document_id,
            revision_id=result.published.revision.revision_id,
            source_sha256=result.published.revision.source_sha256,
            snapshot_id=result.published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
    )
    assert resolved.status is EvidenceResolutionStatus.CORROBORATED
    assert resolved.proposition == RASTER_OCR_SOURCE_OBSERVATION_EXISTS
    assert resolved.observation is not None
    assert resolved.observation.raw_text == "W-1"
    assert resolved.observation.origin_kind == "producer_raster_ocr"
    assert resolved.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED


def test_public_ocr_publication_api_accepts_no_caller_page_images() -> None:
    params = inspect.signature(
        SourceVisibilityProducer.publish_page_raster_ocr_observations
    ).parameters
    assert "page_images" not in params
    assert "image" not in params
    assert "source_bytes" not in params


def test_mock_or_arbitrary_backend_cannot_publish_source_observations() -> None:
    producer, published = _ingested_source("no-mock")
    with pytest.raises(TypeError, match="exact production OCR backend"):
        producer.publish_page_raster_ocr_observations(
            revision_id=published.revision.revision_id,
            expected_snapshot_id=published.snapshot.snapshot_id,
            page_id="1",
            backend=MockOCRBackend(canned_lines=()),
            dpi=300,
        )


def test_exact_duplicate_ocr_emission_collapses_but_same_mark_at_new_location_survives(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer, published = _ingested_source("dedupe")
    result, _current = _publish_fake_rapidocr(
        monkeypatch,
        producer,
        published,
        (
            _line("W-1", (20, 20, 40, 30)),
            _line("W-1", (20, 20, 40, 30)),
            _line("W-1", (80, 20, 100, 30)),
        ),
    )
    assert result.published is not None
    assert len(result.published.ocr_observation_ids) == 2


def test_bridge_returns_only_explicit_opening_tags_inside_authenticated_floor_viewport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer, published = _ingested_source("viewport-filter")
    _result, current = _publish_fake_rapidocr(
        monkeypatch,
        producer,
        published,
        (
            _line("W-1", (20, 20, 40, 30)),
            _line("D-2", (60, 60, 80, 70)),
            _line("GENERAL NOTES", (90, 90, 140, 105)),
            _line("W-3", (190, 190, 210, 205)),
        ),
    )
    decision = _authenticated_viewport(current)
    assert decision.status is EvidenceResolutionStatus.CORROBORATED

    bridged = RasterOCRTagObservationBridge.create(
        producer
    ).produce_for_viewport(decision)
    assert bridged.status is EvidenceResolutionStatus.CANDIDATE
    assert [tag.raw_tag_text for tag in bridged.tags] == ["W-1", "D-2"]
    assert all(tag.viewport_id == "vp-floor-1" for tag in bridged.tags)
    assert all(tag.snapshot_id == current.snapshot.snapshot_id for tag in bridged.tags)


def test_bridge_fails_closed_on_stale_snapshot_bound_viewport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer, published = _ingested_source("stale-vp")
    old_decision = _authenticated_viewport(published)
    assert old_decision.status is EvidenceResolutionStatus.CORROBORATED

    _result, _current = _publish_fake_rapidocr(
        monkeypatch,
        producer,
        published,
        (_line("W-1", (20, 20, 40, 30)),),
    )
    bridged = RasterOCRTagObservationBridge.create(
        producer
    ).produce_for_viewport(old_decision)
    assert bridged.status is EvidenceResolutionStatus.ABSTAINED
    assert bridged.reason_codes == (RASTER_OCR_TAG_BRIDGE_SCOPE_MISMATCH,)


def test_non_floor_plan_viewport_cannot_emit_opening_tags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer, published = _ingested_source("schedule-vp")
    _result, current = _publish_fake_rapidocr(
        monkeypatch,
        producer,
        published,
        (_line("W-1", (20, 20, 40, 30)),),
    )
    decision = _authenticated_viewport(current, view_kind=VIEW_KIND_SCHEDULE)
    assert decision.status is EvidenceResolutionStatus.ABSTAINED
    bridged = RasterOCRTagObservationBridge.create(
        producer
    ).produce_for_viewport(decision)
    assert bridged.status is EvidenceResolutionStatus.ABSTAINED
    assert bridged.tags == ()


def test_bridge_with_no_explicit_opening_tags_abstains(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer, published = _ingested_source("no-tags")
    _result, current = _publish_fake_rapidocr(
        monkeypatch,
        producer,
        published,
        (_line("GENERAL NOTES", (20, 20, 80, 30)),),
    )
    decision = _authenticated_viewport(current)
    bridged = RasterOCRTagObservationBridge.create(
        producer
    ).produce_for_viewport(decision)
    assert bridged.status is EvidenceResolutionStatus.ABSTAINED
    assert bridged.reason_codes == (RASTER_OCR_TAG_BRIDGE_NO_TAGS,)


def test_bridged_tag_is_re_resolvable_by_generic_source_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer, published = _ingested_source("resolver")
    _result, current = _publish_fake_rapidocr(
        monkeypatch,
        producer,
        published,
        (_line("W-1", (20, 20, 40, 30)),),
    )
    decision = _authenticated_viewport(current)
    tag = RasterOCRTagObservationBridge.create(
        producer
    ).produce_for_viewport(decision).tags[0]

    resolved = producer.source_observation_authority().resolve(
        ObservationSelector(
            document_id=tag.document_id,
            revision_id=tag.revision_id,
            source_sha256=tag.source_sha256,
            snapshot_id=tag.snapshot_id,
            observation_id=tag.observation_id,
        )
    )
    assert resolved.status is EvidenceResolutionStatus.CORROBORATED
    assert resolved.observation is not None
    assert resolved.observation.raw_text == "W-1"


def test_real_bridge_to_clos_still_cannot_manufacture_identity(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    producer, published = _ingested_source("clos-identity")
    _result, current = _publish_fake_rapidocr(
        monkeypatch,
        producer,
        published,
        (_line("W-1", (24, 24, 36, 34)),),
    )
    decision = _authenticated_viewport(current)
    bridged = RasterOCRTagObservationBridge.create(
        producer
    ).produce_for_viewport(decision)
    assert len(bridged.tags) == 1

    tolerance = SourceToleranceProvenance.from_scale_and_stroke(
        scale_ratio=100.0,
        stroke_width_pt=1.0,
    )
    geometry = (20.0, 20.0, 40.0, 40.0)
    candidate_id = derive_deterministic_candidate_id(
        document_id=current.revision.document_id,
        revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,
        snapshot_id=current.snapshot.snapshot_id,
        page_id="1",
        viewport_id="vp-floor-1",
        geometry=geometry,
        structural_pattern="jamb_wall_interruption",
        source_observation_ids=("geometry-observation",),
        source_lineage_root_ids=("geometry-root",),
    )
    candidate = PhysicalOpeningCandidateRecord(
        candidate_id=candidate_id,
        document_id=current.revision.document_id,
        revision_id=current.revision.revision_id,
        source_sha256=current.revision.source_sha256,
        snapshot_id=current.snapshot.snapshot_id,
        page_id="1",
        viewport_id="vp-floor-1",
        geometry=geometry,
        structural_pattern="jamb_wall_interruption",
        context_kind="floor_plan_opening",
        source_observation_ids=("geometry-observation",),
        source_lineage_root_ids=("geometry-root",),
        tolerance_provenance=tolerance,
        status=EvidenceResolutionStatus.CANDIDATE,
        semantic_family="windows",
    )

    passing = clos_passing_tag_observations(
        candidate,
        bridged.tags,
        wall_segments=(),
    )
    assert len(passing) == 1

    identity = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=passing,
        binding_evidences=(),
        expected_semantic_family="windows",
        viewport_authenticated=True,
        revision_authenticated=True,
        source_observation_authority=producer.source_observation_authority(),
    )
    assert identity.identity_state is IdentityState.UNRESOLVED
    assert identity.status is not EvidenceResolutionStatus.CORROBORATED
