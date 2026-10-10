"""A non-floor-plan candidate is not a complete negative opening universe.

Synthetic source PDF supplies authentic native observations. Producer-owned
physical dispositions and page closure are separately stubbed to challenge
the semantic count gate: a typed out-of-plan negative must override an
otherwise complete structural path, without minting or guessing a count.
"""
from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    OPENING_CANDIDATE_OUTSIDE_FLOOR_PLAN_SCOPE,
    PHYSICAL_OPENING_DISPOSITION_NO_CANDIDATE,
    PhysicalOpeningCandidateClosureResult,
    PhysicalOpeningDispositionResult,
)
from pb_semantic_opening_enumeration_authority import (
    SEMANTIC_OPENING_CANDIDATE_UNIVERSE_COMPLETE,
    SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN,
    SemanticOpeningEnumerationProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer


def test_typed_nonplan_negative_blocks_candidate_universe_even_when_page_is_closed(
    monkeypatch,
) -> None:
    doc = fitz.open()
    page = doc.new_page(width=250, height=200)
    page.draw_line((20, 50), (190, 50), width=1)
    payload = doc.tobytes()
    doc.close()

    source = SourceVisibilityProducer(
        producer_method="nonplan-count-gate-source-test", producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="nonplan-test", source_bytes=payload,
        source_locator="fixture://nonplan-test.pdf",
    )
    assert published.visible_observation_ids

    physical = source.physical_opening_authority()
    monkeypatch.setattr(
        physical,
        "assess_visible_candidate_closure",
        lambda _selector: PhysicalOpeningCandidateClosureResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            page_id="1",
            candidate_universe_complete=True,
            raw_candidate_count=0,
            resolved_candidate_count=0,
            unresolved_candidate_ids=(),
            unresolved_observation_ids=(),
            reason_codes=(),
        ),
    )

    producer = SemanticOpeningEnumerationProducer.from_source_visibility_producer(source)
    monkeypatch.setattr(
        physical,
        "classify_disposition",
        lambda _selector: PhysicalOpeningDispositionResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            disposition=PHYSICAL_OPENING_DISPOSITION_NO_CANDIDATE,
            reason_codes=(OPENING_CANDIDATE_OUTSIDE_FLOOR_PLAN_SCOPE,),
        ),
    )
    outside = producer.publish_page_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id="page-1:out-of-plan",
        page_ids=("1",),
    )
    assert outside.record is not None
    assert outside.record.physical_opening_record_ids == ()
    assert outside.record.structural_enumeration_complete is True
    assert outside.record.physical_opening_universe_complete is False
    assert SEMANTIC_OPENING_CANDIDATE_UNIVERSE_COMPLETE not in outside.record.reason_codes
    assert SEMANTIC_OPENING_UNIVERSE_EXHAUSTIVENESS_UNPROVEN in outside.record.reason_codes

    # A distinct ordinary typed negative does not itself constitute
    # non-floor-plan scope. The independent source candidate-closure
    # authority remains responsible for asserting actual completeness.
    monkeypatch.setattr(
        physical,
        "classify_disposition",
        lambda _selector: PhysicalOpeningDispositionResult(
            status=EvidenceResolutionStatus.CORROBORATED,
            disposition=PHYSICAL_OPENING_DISPOSITION_NO_CANDIDATE,
            reason_codes=("no_candidate_in_covered_path",),
        ),
    )
    normal = producer.publish_page_scope(
        revision_id=published.revision.revision_id,
        decision_scope_id="page-1:covered-path",
        page_ids=("1",),
    )
    assert normal.record is not None
    assert normal.record.structural_enumeration_complete is True
    assert normal.record.physical_opening_universe_complete is True
    assert SEMANTIC_OPENING_CANDIDATE_UNIVERSE_COMPLETE in normal.record.reason_codes
