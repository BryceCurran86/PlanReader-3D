"""Tests for pb_raster_ocr_tag_observation_bridge.py (Item 35 PR 2).

Uses a real in-memory PDF and the real SourceObservationProducer /
SourceObservationAuthority / ViewportViewClassAuthority /
authenticate_viewport_decision() -- not mocks -- so this proves genuine
interop with the unmodified #539 authority, not just that this module's
own internals are internally consistent. All content synthetic; no
project coordinates or expected counts.
"""
from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_portable_raster_ocr_authority import OCRLine
from pb_raster_ocr_tag_observation_bridge import publish_ocr_lines_as_tag_observations
from pb_source_observation_authority import ObservationSelector, SourceObservationProducer
from pb_source_opening_candidate_authority import (
    IdentityState,
    OpeningIdentityResolver,
    authenticate_viewport_decision,
)
from pb_viewport_segmentation import SegmentedViewport
from pb_viewport_view_class_authority import (
    VIEW_KIND_ELEVATION,
    VIEW_KIND_FLOOR_PLAN,
    ViewportViewClassProducer,
    ViewportViewClassSelector,
)
from tests.test_source_opening_universe_evidence_v1 import make_candidate


def _ingest_blank_page(document_id: str = "doc_bridge_test"):
    doc = fitz.open()
    doc.new_page(width=1000, height=1000)
    payload = doc.tobytes()
    doc.close()
    producer = SourceObservationProducer(producer_method="test_producer", producer_version="1.0")
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id, source_bytes=payload, source_locator="memory://bridge_test.pdf"
    )
    authority = producer.authority()
    page_obs_id = next(
        oid
        for oid in published.snapshot.observation_ids
        if authority.resolve(
            ObservationSelector(
                document_id=document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=oid,
            )
        ).observation.observation_kind
        == "native_pdf_page"
    )
    return producer, authority, published, page_obs_id


def _authenticated_floor_plan_decision(document_id: str, revision_id: str, view_kind: str = VIEW_KIND_FLOOR_PLAN):
    selector = ViewportViewClassSelector(
        document_id=document_id,
        revision_id=revision_id,
        source_sha256="a" * 64,
        snapshot_id="snap_vp",
        viewport_id="vp_1",
    )
    vc_producer = ViewportViewClassProducer.create()
    vc_producer.publish(selector, view_kind=view_kind, evidence_observation_ids=("obs_title_1",))
    viewport = SegmentedViewport(
        view_id="vp_1",
        page_number=1,
        view_type=view_kind,
        label="TEST VIEW",
        title_bbox=(0.0, 0.0, 50.0, 20.0),
        bounding_box=(0.0, 0.0, 1000.0, 1000.0),
        status="resolved",
        boundary_source="vector_frame",
        confidence=1.0,
    )
    return authenticate_viewport_decision(
        viewport=viewport, view_class_authority=vc_producer.authority(), selector=selector
    )


def _line(text: str, bbox_pt, confidence=None) -> OCRLine:
    scale = 1.0
    x0, y0, x1, y1 = bbox_pt
    return OCRLine(
        text=text,
        confidence=confidence,
        bbox_px=(x0 / scale, y0 / scale, x1 / scale, y1 / scale),
        bbox_pt=bbox_pt,
    )


def test_end_to_end_real_pdf_and_real_authorities_produce_corroborated_tag() -> None:
    producer, authority, published, page_obs_id = _ingest_blank_page()
    decision = _authenticated_floor_plan_decision(
        "doc_bridge_test", published.revision.revision_id
    )
    assert decision.status == EvidenceResolutionStatus.CORROBORATED

    tags, final_snapshot = publish_ocr_lines_as_tag_observations(
        producer=producer,
        authority=authority,
        document_id="doc_bridge_test",
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        base_snapshot_id=published.snapshot.snapshot_id,
        base_snapshot_observation_ids=published.snapshot.observation_ids,
        page_id="1",
        page_observation_id=page_obs_id,
        source_partition_id="page:1",
        viewport_decision=decision,
        ocr_lines=[_line("D-1", (100.0, 100.0, 120.0, 115.0), confidence=0.97)],
    )
    assert len(tags) == 1
    assert tags[0].raw_tag_text == "D-1"
    assert tags[0].bounding_box == (100.0, 100.0, 120.0, 115.0)
    assert tags[0].snapshot_id == final_snapshot
    assert tags[0].viewport_id == "vp_1"
    # Genuinely authenticated, not a caller-fabricated TagObservation.
    assert tags[0]._seal is not None


def test_non_floor_plan_viewport_publishes_nothing() -> None:
    producer, authority, published, page_obs_id = _ingest_blank_page("doc_bridge_elev")
    decision = _authenticated_floor_plan_decision(
        "doc_bridge_elev", published.revision.revision_id, view_kind=VIEW_KIND_ELEVATION
    )
    assert decision.status != EvidenceResolutionStatus.CORROBORATED

    tags, final_snapshot = publish_ocr_lines_as_tag_observations(
        producer=producer,
        authority=authority,
        document_id="doc_bridge_elev",
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        base_snapshot_id=published.snapshot.snapshot_id,
        base_snapshot_observation_ids=published.snapshot.observation_ids,
        page_id="1",
        page_observation_id=page_obs_id,
        source_partition_id="page:1",
        viewport_decision=decision,
        ocr_lines=[_line("W-1", (10.0, 10.0, 30.0, 25.0))],
    )
    assert tags == ()
    assert final_snapshot == published.snapshot.snapshot_id


def test_duplicate_detections_of_one_mark_collapse_to_one_tag_observation() -> None:
    producer, authority, published, page_obs_id = _ingest_blank_page("doc_bridge_dupe")
    decision = _authenticated_floor_plan_decision("doc_bridge_dupe", published.revision.revision_id)

    # Same physical mark, "detected" twice at slightly different bbox
    # (as two preprocessing passes of the same real stamp would).
    lines = [
        _line("D-2", (200.0, 200.0, 220.0, 214.0), confidence=0.9),
        _line("D-2", (200.6, 200.4, 220.5, 214.3), confidence=0.6),
    ]
    tags, _ = publish_ocr_lines_as_tag_observations(
        producer=producer,
        authority=authority,
        document_id="doc_bridge_dupe",
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        base_snapshot_id=published.snapshot.snapshot_id,
        base_snapshot_observation_ids=published.snapshot.observation_ids,
        page_id="1",
        page_observation_id=page_obs_id,
        source_partition_id="page:1",
        viewport_decision=decision,
        ocr_lines=lines,
    )
    assert len(tags) == 1
    # Highest-confidence instance's geometry is the one kept.
    assert tags[0].bounding_box == (200.0, 200.0, 220.0, 214.0)


def test_distinct_marks_are_not_merged_even_when_geometrically_close() -> None:
    producer, authority, published, page_obs_id = _ingest_blank_page("doc_bridge_distinct")
    decision = _authenticated_floor_plan_decision(
        "doc_bridge_distinct", published.revision.revision_id
    )
    lines = [
        _line("W-1", (300.0, 300.0, 315.0, 312.0)),
        _line("W-2", (301.0, 301.0, 316.0, 313.0)),  # different text, almost same spot
    ]
    tags, _ = publish_ocr_lines_as_tag_observations(
        producer=producer,
        authority=authority,
        document_id="doc_bridge_distinct",
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        base_snapshot_id=published.snapshot.snapshot_id,
        base_snapshot_observation_ids=published.snapshot.observation_ids,
        page_id="1",
        page_observation_id=page_obs_id,
        source_partition_id="page:1",
        viewport_decision=decision,
        ocr_lines=lines,
    )
    assert {t.raw_tag_text for t in tags} == {"W-1", "W-2"}


def test_confidence_never_gates_publication() -> None:
    """A None-confidence line (e.g. from WinOCR, which has no confidence
    API at all) must publish exactly as readily as a high-confidence one
    -- confidence is not part of this bridge's decision path."""
    producer, authority, published, page_obs_id = _ingest_blank_page("doc_bridge_conf")
    decision = _authenticated_floor_plan_decision("doc_bridge_conf", published.revision.revision_id)
    tags, _ = publish_ocr_lines_as_tag_observations(
        producer=producer,
        authority=authority,
        document_id="doc_bridge_conf",
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        base_snapshot_id=published.snapshot.snapshot_id,
        base_snapshot_observation_ids=published.snapshot.observation_ids,
        page_id="1",
        page_observation_id=page_obs_id,
        source_partition_id="page:1",
        viewport_decision=decision,
        ocr_lines=[_line("D-1", (5.0, 5.0, 20.0, 18.0), confidence=None)],
    )
    assert len(tags) == 1
    assert tags[0].raw_tag_text == "D-1"


def test_published_tag_integrates_with_real_unmodified_identity_resolver() -> None:
    """Prove genuine interop: a TagObservation from this bridge, handed to
    the real OpeningIdentityResolver with no relation evidence, resolves
    exactly as UNRESOLVED as any other tag would -- this bridge does not
    grant OCR-sourced tags any special treatment in identity resolution."""
    producer, authority, published, page_obs_id = _ingest_blank_page("doc_bridge_integ")
    decision = _authenticated_floor_plan_decision(
        "doc_bridge_integ", published.revision.revision_id
    )
    tags, final_snapshot = publish_ocr_lines_as_tag_observations(
        producer=producer,
        authority=authority,
        document_id="doc_bridge_integ",
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        base_snapshot_id=published.snapshot.snapshot_id,
        base_snapshot_observation_ids=published.snapshot.observation_ids,
        page_id="1",
        page_observation_id=page_obs_id,
        source_partition_id="page:1",
        viewport_decision=decision,
        ocr_lines=[_line("D1", (400.0, 400.0, 415.0, 412.0))],
    )
    assert len(tags) == 1

    candidate = make_candidate(
        document_id="doc_bridge_integ",
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=final_snapshot,
        viewport_id="vp_1",
        geometry=(395.0, 395.0, 420.0, 420.0),
    )
    result = OpeningIdentityResolver.resolve_tag_binding(
        candidate=candidate,
        nearby_tags=list(tags),
        expected_semantic_family="doors",
        viewport_authenticated=True,
        revision_authenticated=True,
        source_observation_authority=authority,
    )
    assert result.identity_state == IdentityState.UNRESOLVED
    assert result.bound_tag != "D1"
