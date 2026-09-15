from __future__ import annotations

from dataclasses import replace
import inspect

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_AMBIGUOUS,
    PHYSICAL_OPENING_BLOCKED,
    PHYSICAL_OPENING_CANDIDATE,
    PHYSICAL_OPENING_EXISTENCE_UNRESOLVED,
    PHYSICAL_OPENING_EXISTS,
    PHYSICAL_OPENING_RESOLVED_EXISTENCE,
    REASON_CROSS_ORIENTATION_AMBIGUITY,
    REASON_JAMB_BOUNDARIES_UNRESOLVED,
    PhysicalOpeningAuthority,
)
from pb_source_observation_authority import ObservationSelector, SourceObservationProducer

Line = tuple[float, float, float, float]


def _gap(jambs: bool = True) -> list[Line]:
    lines = [
        (20, 100, 100, 100), (140, 100, 220, 100),
        (20, 120, 100, 120), (140, 120, 220, 120),
    ]
    if jambs:
        lines += [(100, 100, 100, 120), (140, 100, 140, 120)]
    return lines


def _pdf(pages: list[list[Line]], texts: list[list[str]] | None = None) -> bytes:
    doc = fitz.open()
    texts = texts or [[] for _ in pages]
    for page_index, lines in enumerate(pages):
        page = doc.new_page(width=260, height=260)
        for x0, y0, x1, y1 in lines:
            page.draw_line(fitz.Point(x0, y0), fitz.Point(x1, y1))
        for index, text in enumerate(texts[page_index]):
            page.insert_text((20, 20 + index * 14), text)
    payload = doc.tobytes()
    doc.close()
    return payload


def _fixture(pages: list[list[Line]], texts: list[list[str]] | None = None, document_id: str = "doc"):
    producer = SourceObservationProducer(producer_method="g17-v2-test", producer_version="2.0")
    published = producer.ingest_native_pdf_bytes(
        document_id=document_id,
        source_bytes=_pdf(pages, texts),
        source_locator=f"memory://{document_id}.pdf",
    )
    source = producer.authority()
    return producer, published, source, PhysicalOpeningAuthority(source)


def _selectors(published):
    return [
        ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        for observation_id in published.snapshot.observation_ids
    ]


def _segment_selector(source, published, geometry: Line):
    target = tuple(round(float(v), 3) for v in geometry)
    reverse = (target[2], target[3], target[0], target[1])
    for selector in _selectors(published):
        observation = source.resolve(selector).observation
        if observation is None or observation.observation_kind != "native_pdf_segment":
            continue
        actual = tuple(round(float(v), 3) for v in observation.geometry)
        if actual == target or actual == reverse:
            return selector
    raise AssertionError(f"missing segment {geometry}")


def _text_selector(source, published, text: str):
    for selector in _selectors(published):
        observation = source.resolve(selector).observation
        if observation is not None and observation.raw_text == text:
            return selector
    raise AssertionError(f"missing text {text}")


def test_jamb_bounded_two_face_interruption_resolves_existence_only() -> None:
    _, published, source, physical = _fixture([_gap(True)])
    selector = _segment_selector(source, published, (20, 100, 100, 100))
    result = physical.prove_existence(selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.proposition == PHYSICAL_OPENING_EXISTS
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTS
    assert result.record is not None
    assert result.record.resolution_state == PHYSICAL_OPENING_RESOLVED_EXISTENCE
    assert result.record.source_root_observation_ids == result.record.source_observation_ids
    assert result.record.viewport_id is None
    assert {"width_m", "height_m", "area_m2", "host_wall_id", "bound_wall_id"}.isdisjoint(
        result.record.__dataclass_fields__
    )


def test_wall_gap_alone_is_candidate() -> None:
    _, published, source, physical = _fixture([_gap(False)])
    selector = _segment_selector(source, published, (20, 100, 100, 100))
    result = physical.prove_existence(selector)

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.proposition is None
    assert result.physical_opening_existence == PHYSICAL_OPENING_EXISTENCE_UNRESOLVED
    assert result.record is not None
    assert result.record.resolution_state == PHYSICAL_OPENING_CANDIDATE
    assert REASON_JAMB_BOUNDARIES_UNRESOLVED in result.record.blocking_reasons


def test_tag_and_schedule_alone_are_blocked() -> None:
    producer, published, source, physical = _fixture([[]], [["D01"]])
    tag = _text_selector(source, published, "D01")
    assert physical.prove_existence(tag).record.resolution_state == PHYSICAL_OPENING_BLOCKED

    snapshot = producer.publish_derived_observation(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        observation_kind="schedule_row",
        source_primitive_ref="schedule:1",
        origin_kind="derived",
        parent_observation_ids=(tag.observation_id,),
        raw_text="D01 900 x 2100",
        observation_id="schedule-1",
    )
    schedule = replace(tag, snapshot_id=snapshot.snapshot_id, observation_id="schedule-1")
    result = physical.prove_existence(schedule)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.proposition is None


def test_swing_or_repeated_derived_observations_cannot_manufacture_jambs() -> None:
    producer, published, source, physical = _fixture([_gap(False)])
    parent = _segment_selector(source, published, (20, 100, 100, 100))
    first = producer.publish_derived_observation(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        observation_kind="door_swing",
        source_primitive_ref="swing:1",
        origin_kind="derived",
        parent_observation_ids=(parent.observation_id,),
        geometry=(100, 100, 140, 120),
        observation_id="swing-1",
    )
    second = producer.publish_derived_observation(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=first.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        observation_kind="cv_opening_detection",
        source_primitive_ref="cv:1",
        origin_kind="derived",
        parent_observation_ids=(parent.observation_id,),
        geometry=(100, 100, 140, 120),
        observation_id="cv-1",
    )
    selector = replace(parent, snapshot_id=second.snapshot_id, observation_id="cv-1")
    result = physical.prove_existence(selector)

    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.proposition is None
    assert result.record is not None
    assert "swing-1" not in result.record.source_observation_ids
    assert "cv-1" not in result.record.source_observation_ids
    assert result.record.source_root_observation_ids == (parent.observation_id,)


def test_nearby_unrelated_primitives_do_not_combine_by_proximity() -> None:
    lines = _gap(False) + [(110, 100, 110, 120), (150, 100, 150, 120)]
    _, published, source, physical = _fixture([lines])
    selector = _segment_selector(source, published, (20, 100, 100, 100))
    result = physical.prove_existence(selector)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.proposition is None


def test_cross_document_and_cross_page_evidence_cannot_combine() -> None:
    _, pa, sa, physical_a = _fixture([_gap(False)], document_id="faces")
    selector_a = _segment_selector(sa, pa, (20, 100, 100, 100))
    assert physical_a.prove_existence(selector_a).status is EvidenceResolutionStatus.CANDIDATE

    _, pp, sp, physical_pages = _fixture([
        _gap(False),
        [(100, 100, 100, 120), (140, 100, 140, 120)],
    ], document_id="pages")
    selector_page = _segment_selector(sp, pp, (20, 100, 100, 100))
    result = physical_pages.prove_existence(selector_page)
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.record is not None and result.record.page_id == "1"


def test_caller_viewport_claim_does_not_backfill_native_ownership() -> None:
    producer, published, source, physical = _fixture([_gap(True)])
    parent = _segment_selector(source, published, (20, 100, 100, 100))
    snapshot = producer.publish_derived_observation(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        base_snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
        source_partition_id="page:1",
        viewport_id="caller-vp",
        observation_kind="opening_candidate",
        source_primitive_ref="derived:1",
        origin_kind="derived",
        parent_observation_ids=(parent.observation_id,),
        observation_id="derived-1",
    )
    selector = replace(parent, snapshot_id=snapshot.snapshot_id, observation_id="derived-1")
    result = physical.prove_existence(selector)
    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.record is not None and result.record.viewport_id is None


def test_cross_orientation_overlap_is_ambiguous() -> None:
    vertical = [
        (110, 20, 110, 90), (110, 130, 110, 220),
        (130, 20, 130, 90), (130, 130, 130, 220),
        (110, 90, 130, 90), (110, 130, 130, 130),
    ]
    _, published, source, physical = _fixture([_gap(True) + vertical])
    selector = _segment_selector(source, published, (20, 100, 100, 100))
    result = physical.prove_existence(selector)
    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.proposition is None
    assert result.record is not None
    assert result.record.resolution_state == PHYSICAL_OPENING_AMBIGUOUS
    assert result.reason_codes == (REASON_CROSS_ORIENTATION_AMBIGUITY,)


def test_replay_stable_id_and_confidence_not_an_authority_input() -> None:
    _, published, source, physical = _fixture([_gap(True)])
    selector = _segment_selector(source, published, (20, 100, 100, 100))
    first = physical.prove_existence(selector)
    second = physical.prove_existence(selector)
    assert first.record is not None and second.record is not None
    assert first.record.record_id == second.record.record_id
    assert tuple(inspect.signature(PhysicalOpeningAuthority.prove_existence).parameters) == ("self", "selector")
    with pytest.raises(TypeError):
        physical.prove_existence(selector, confidence=1.0)


def test_semantic_capability_is_existence_only_and_downstream_gate_stays_closed() -> None:
    semantic = PhysicalOpeningAuthority.semantic_capabilities()
    assert semantic["physical_opening_existence"] is True
    assert all(not enabled for name, enabled in semantic.items() if name != "physical_opening_existence")
    assert all(not enabled for enabled in PhysicalOpeningAuthority.capabilities().values())
