from __future__ import annotations

import fitz

from pb_generic_opening_count_authority import (
    GenericOpeningCountProducer,
    GenericOpeningCountSelector,
    _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import MockOCRBackend, OCRLine
from pb_source_opening_candidate_authority import authenticate_viewport_decision
from pb_viewport_segmentation import SegmentedViewport
from pb_opening_universe_completeness_authority import (
    OpeningUniverseCompletenessAuthority,
    OpeningUniverseCompletenessRecord,
    SourceEnumerationState,
    _AUTHORITY_SEAL as UNIVERSE_AUTHORITY_SEAL,
)
from pb_page_view_class_source_adapter import (
    build_source_page_view_class_authority,
    page_viewport_id,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    PhysicalOpeningAuthority,
    PhysicalOpeningExistenceRecord,
    PhysicalOpeningExistenceResult,
)
from pb_source_observation_authority import (
    ObservationSelector,
    SourceObservationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_viewport_view_class_authority import (
    VIEW_KIND_FLOOR_PLAN,
    ViewportViewClassSelector,
)


def _floor_plan_pdf() -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=400, height=250)
    page.insert_text(fitz.Point(30, 30), "GROUND FLOOR PLAN", fontsize=12)
    payload = doc.tobytes()
    doc.close()
    return payload


def test_authenticated_page_text_derives_floor_plan_view_class() -> None:
    source = SourceVisibilityProducer(
        producer_method="page-view-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="view-doc",
        source_bytes=_floor_plan_pdf(),
        source_locator="memory://view.pdf",
    )
    authority = build_source_page_view_class_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    result = authority.resolve(
        ViewportViewClassSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            viewport_id=page_viewport_id("1"),
        )
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.view_kind == VIEW_KIND_FLOOR_PLAN
    assert result.record.evidence_observation_ids


def test_page_scoped_generic_count_uses_authenticated_page_viewport() -> None:
    doc = "doc"
    rev = "rev"
    sha = "a" * 64
    snap = "snap"
    scope = "scope"
    record = OpeningUniverseCompletenessRecord(
        record_id="univ",
        decision_scope_id=scope,
        decision_scope_kind="pages",
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        snapshot_id=snap,
        page_ids=("1",),
        viewport_id=None,
        enumeration_state=SourceEnumerationState.COMPLETE.value,
        source_decode_complete=True,
        semantic_enumeration_complete=True,
        decision_scope_complete=True,
        accounted_member_ids=("member",),
        universe_fingerprint="fp",
        reason_codes=(),
        accounted_source_observation_ids=("obs-real",),
    )
    universe = OpeningUniverseCompletenessAuthority(
        {(doc, rev, sha, snap, scope): record},
        _seal=UNIVERSE_AUTHORITY_SEAL,
    )
    object.__setattr__(
        universe,
        "_source_authentication_seal",
        _SOURCE_AUTHENTICATED_COMPLETENESS_SEAL,
    )

    physical = PhysicalOpeningAuthority(
        SourceObservationProducer(
            producer_method="view-count-test",
            producer_version="1",
        ).authority()
    )
    opening = PhysicalOpeningExistenceRecord(
        record_id="opening-1",
        source_observation_ids=("obs-real",),
        source_lineage_root_ids=("root",),
        document_id=doc,
        revision_id=rev,
        source_sha256=sha,
        snapshot_id=snap,
        page_id="1",
        viewport_id=None,
        semantic_class="opening",
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition=PHYSICAL_OPENING_EXISTS,
        structural_pattern="test",
        diagnostic_confidence=1.0,
        blocking_reasons=(),
        structural_reason_codes=(),
        producer_method="test",
        producer_version="1",
        producer_generation=1,
    )

    def _prove(selector: ObservationSelector) -> PhysicalOpeningExistenceResult:
        assert selector.observation_id == "obs-real"
        return PhysicalOpeningExistenceResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            proposition=PHYSICAL_OPENING_EXISTS,
            physical_opening_existence=PHYSICAL_OPENING_EXISTS,
            reason_codes=(),
            existence_record=opening,
        )

    object.__setattr__(physical, "prove_existence", _prove)
    object.__setattr__(
        physical,
        "compare_identity",
        lambda *_args: (_ for _ in ()).throw(AssertionError("single opening only")),
    )

    from pb_viewport_view_class_authority import ViewportViewClassProducer
    view_producer = ViewportViewClassProducer.create()
    view_producer.publish(
        ViewportViewClassSelector(
            document_id=doc,
            revision_id=rev,
            source_sha256=sha,
            snapshot_id=snap,
            viewport_id=page_viewport_id("1"),
        ),
        view_kind=VIEW_KIND_FLOOR_PLAN,
        evidence_observation_ids=("view-word",),
    )

    generic = GenericOpeningCountProducer.from_authorities(
        opening_universe_authority=universe,
        physical_opening_authority=physical,
        viewport_view_class_authority=view_producer.authority(),
    )
    result = generic.publish(
        GenericOpeningCountSelector(
            document_id=doc,
            revision_id=rev,
            source_sha256=sha,
            snapshot_id=snap,
            decision_scope_id=scope,
        )
    )
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None
    assert result.record.count == 1


def test_authenticated_page_view_class_survives_ocr_snapshot_augmentation() -> None:
    source = SourceVisibilityProducer(
        producer_method="page-view-ocr-snapshot-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="view-ocr-doc",
        source_bytes=_floor_plan_pdf(),
        source_locator="memory://view-ocr.pdf",
    )
    selector = ViewportViewClassSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        viewport_id=page_viewport_id("1"),
    )
    initial = build_source_page_view_class_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    initial_result = initial.resolve(selector)
    assert initial_result.status is EvidenceResolutionStatus.CORROBORATED
    assert initial_result.record is not None
    assert initial_result.record.view_kind == VIEW_KIND_FLOOR_PLAN

    viewport = SegmentedViewport(
        view_id=page_viewport_id("1"),
        page_number=1,
        view_type=VIEW_KIND_FLOOR_PLAN,
        label="SOURCE FLOOR PLAN PAGE",
        title_bbox=(0.0, 0.0, 0.0, 0.0),
        bounding_box=(0.0, 0.0, 400.0, 250.0),
        status="resolved",
        boundary_source="producer_page_scope",
        confidence=1.0,
    )
    decision = authenticate_viewport_decision(
        viewport=viewport,
        view_class_authority=initial,
        selector=selector,
    )
    assert decision.status is EvidenceResolutionStatus.CORROBORATED

    scale = 300.0 / 72.0
    _tags, updated = source.augment_with_raster_ocr_tags_for_tests(
        published.revision.revision_id,
        viewport_decision=decision,
        backend=MockOCRBackend(
            (
                OCRLine(
                    text="W1",
                    confidence=0.99,
                    bbox_px=(100.0 * scale, 100.0 * scale, 120.0 * scale, 110.0 * scale),
                    bbox_pt=(999.0, 999.0, 1000.0, 1000.0),
                ),
            )
        ),
    )
    assert updated.snapshot.snapshot_id != published.snapshot.snapshot_id

    current = build_source_page_view_class_authority(
        source_visibility_producer=source,
        revision_id=updated.revision.revision_id,
        page_ids=("1",),
    )
    current_result = current.resolve(
        ViewportViewClassSelector(
            document_id=updated.revision.document_id,
            revision_id=updated.revision.revision_id,
            source_sha256=updated.revision.source_sha256,
            snapshot_id=updated.snapshot.snapshot_id,
            viewport_id=page_viewport_id("1"),
        )
    )
    assert current_result.status is EvidenceResolutionStatus.CORROBORATED, current_result.reason_codes
    assert current_result.record is not None
    assert current_result.record.view_kind == VIEW_KIND_FLOOR_PLAN
