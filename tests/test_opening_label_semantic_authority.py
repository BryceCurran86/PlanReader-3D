from __future__ import annotations

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_kind_authority import OPENING_KIND_CONFLICT, resolve_opening_kind
from pb_opening_label_semantic_authority import (
    OPENING_LABEL_SEMANTIC_CONFLICT,
    OpeningLabelSemanticProducer,
)
from pb_physical_opening_authority import (
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    PHYSICAL_OPENING_EXISTS,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _pdf(*, label: str | None = None, conflict_label: bool = False) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=400.0, height=300.0)
        for first, second in (
            ((20.0, 100.0), (100.0, 100.0)),
            ((140.0, 100.0), (220.0, 100.0)),
            ((20.0, 110.0), (100.0, 110.0)),
            ((140.0, 110.0), (220.0, 110.0)),
            ((100.0, 100.0), (100.0, 110.0)),
            ((140.0, 100.0), (140.0, 110.0)),
        ):
            page.draw_line(fitz.Point(*first), fitz.Point(*second), width=1.0)
        if label:
            page.insert_text(fitz.Point(105.0, 125.0), label, fontsize=7.0)
        if conflict_label:
            page.insert_text(fitz.Point(105.0, 134.0), "DOOR", fontsize=7.0)
        page.insert_text(fitz.Point(20.0, 180.0), "LEGEND", fontsize=8.0)
        page.insert_text(
            fitz.Point(20.0, 195.0),
            "SGW     SLIDING GLASS WINDOW",
            fontsize=7.0,
        )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _ingest(payload: bytes):
    source = SourceVisibilityProducer(
        producer_method="opening-label-semantic-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="opening-label-semantic",
        source_bytes=payload,
        source_locator="fixture:opening-label-semantic",
    )
    return source, published


def _opening_selector(source, published):
    physical = source.physical_opening_authority()
    found = {}
    for observation_id in published.visible_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        result = physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            found[result.existence_record.record_id] = selector
    assert len(found) == 1
    return next(iter(found.values()))


def test_topology_without_semantic_evidence_remains_untyped() -> None:
    result = resolve_opening_kind(
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    )
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.opening_kind is None


def test_owned_label_resolves_kind_only_through_source_legend_definition() -> None:
    source, published = _ingest(_pdf(label="1218 SGW"))
    selector = _opening_selector(source, published)
    semantic = OpeningLabelSemanticProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert semantic.status is EvidenceResolutionStatus.CORROBORATED
    assert semantic.evidence is not None
    assert semantic.evidence.semantic_kind == "window"
    assert semantic.evidence.source_text_observation_ids
    assert semantic.evidence.legend_observation_ids

    resolved = resolve_opening_kind(
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
        label_kind=semantic.evidence.semantic_kind,
    )
    assert resolved.status is EvidenceResolutionStatus.CORROBORATED
    assert resolved.opening_kind == "window"
    assert resolved.structural_kind is None


def test_owned_stacker_phrase_authenticates_door_kind_without_topology_guess() -> None:
    source, published = _ingest(_pdf(label="2127 STACKER"))
    selector = _opening_selector(source, published)
    semantic = OpeningLabelSemanticProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert semantic.status is EvidenceResolutionStatus.CORROBORATED
    assert semantic.evidence is not None
    assert semantic.evidence.semantic_kind == "door"

    resolved = resolve_opening_kind(
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
        label_kind=semantic.evidence.semantic_kind,
    )
    assert resolved.status is EvidenceResolutionStatus.CORROBORATED
    assert resolved.opening_kind == "door"
    assert resolved.structural_kind is None


def test_owned_panel_lift_phrase_authenticates_door_kind() -> None:
    source, published = _ingest(_pdf(label="2148 PANEL LIFT"))
    selector = _opening_selector(source, published)
    semantic = OpeningLabelSemanticProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert semantic.status is EvidenceResolutionStatus.CORROBORATED
    assert semantic.evidence is not None
    assert semantic.evidence.semantic_kind == "door"


def test_conflicting_authenticated_semantic_evidence_fails_closed() -> None:
    source, published = _ingest(_pdf(label="1218 SGW", conflict_label=True))
    selector = _opening_selector(source, published)
    semantic = OpeningLabelSemanticProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert semantic.status is EvidenceResolutionStatus.CONFLICT
    assert semantic.evidence is None
    assert OPENING_LABEL_SEMANTIC_CONFLICT in semantic.reason_codes

    resolved = resolve_opening_kind(
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
        schedule_trade_type="doors",
        label_kind="window",
    )
    assert resolved.status is EvidenceResolutionStatus.CONFLICT
    assert resolved.opening_kind is None
    assert OPENING_KIND_CONFLICT in resolved.reason_codes