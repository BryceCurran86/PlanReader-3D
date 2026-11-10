"""Default-off corner-leg existence and owner CRNR STACK pairing of both leaves."""
from __future__ import annotations

import fitz
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import (
    OpeningLabelDimensionProducer,
    _TrustedTextLine,
    _gap_span_for_opening,
    _label_matches_gap,
    parse_opening_label_dimensions,
)
from pb_opening_label_semantic_authority import (
    OpeningLabelSemanticProducer,
    _explicit_word_kind,
)
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_CORNER_FRAMED_OPENING_LEG,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from test_raster_corner_framed_opening_shadow import (
    _existence_records,
    _pdf,
    _png,
    _selector,
    _sheet,
)


def _prepare(*, corner_shadow: bool, **sheet):
    producer = SourceVisibilityProducer(
        producer_method="raster-corner-optin-contract",
        producer_version="1",
        raster_corner_framed_opening_shadow=corner_shadow,
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="corner-optin-contract",
        source_bytes=_pdf(_sheet(**sheet)),
        source_locator="memory://raster-corner-optin-contract.pdf",
        page_ids=("1",),
    )
    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=("1",))
    return producer, published


def test_default_off_issues_no_corner_existence() -> None:
    producer, published = _prepare(corner_shadow=False)
    assert _existence_records(producer, published) == ()


def test_opt_in_issues_one_existence_record_per_leg() -> None:
    producer, published = _prepare(corner_shadow=True)
    records = _existence_records(producer, published)
    assert len(records) == 2
    assert {record.structural_pattern for record in records} == {RASTER_CORNER_FRAMED_OPENING_LEG}
    assert all(record.proposition == PHYSICAL_OPENING_EXISTS for record in records)
    assert all(record.aperture_bbox_pt is not None for record in records)
    supports = [frozenset(record.source_observation_ids) for record in records]
    assert supports[0].isdisjoint(supports[1])
    boxes = [record.aperture_bbox_pt for record in records]
    assert boxes[0] != boxes[1]


def test_opt_in_does_not_change_an_unrelated_straight_opening() -> None:
    off_producer, off_published = _prepare(corner_shadow=False, unrelated_opening=True)
    on_producer, on_published = _prepare(corner_shadow=True, unrelated_opening=True)
    off_records = _existence_records(off_producer, off_published)
    on_records = _existence_records(on_producer, on_published)
    assert len(off_records) == 1
    assert off_records[0].structural_pattern == RASTER_FRAMED_WALL_BAND_INTERRUPTION
    framed = [record for record in on_records
              if record.structural_pattern == RASTER_FRAMED_WALL_BAND_INTERRUPTION]
    corner = [record for record in on_records
              if record.structural_pattern == RASTER_CORNER_FRAMED_OPENING_LEG]
    assert len(framed) == 1
    assert len(corner) == 2
    assert framed[0].aperture_bbox_pt == off_records[0].aperture_bbox_pt


def test_opt_in_look_alikes_issue_no_corner_existence() -> None:
    for sheet in (
        dict(frames=0),
        dict(frames=1),
        dict(face_lines=True),
        dict(solid_corner=True),
        dict(second_corner_post=True),
    ):
        producer, published = _prepare(corner_shadow=True, **sheet)
        assert not [
            record for record in _existence_records(producer, published)
            if record.structural_pattern == RASTER_CORNER_FRAMED_OPENING_LEG
        ]

    # A collinear partner is a straight framed opening, not a corner.
    producer, published = _prepare(corner_shadow=True, straight_partner=True)
    records = _existence_records(producer, published)
    assert not [
        record for record in records
        if record.structural_pattern == RASTER_CORNER_FRAMED_OPENING_LEG
    ]


def test_crnr_stack_is_the_existing_stacker_door_phrase_not_a_raw_millimetre() -> None:
    parsed = parse_opening_label_dimensions("2124 CRNR STACK")
    assert parsed is not None
    assert parsed.dimension_tokens == ("21", "24")
    assert parsed.compact_hundreds_present is True
    assert parsed.dimension_values_mm == ()
    assert _explicit_word_kind("2124 CRNR STACK") == ("door", False)
    assert _explicit_word_kind("STACK OF BRICKS") == (None, False)


def _labelled_pdf(*, stack_xy: tuple[float, float], bifold_xy: tuple[float, float] | None = None,
                  unrelated_opening: bool = False) -> bytes:
    gray = _sheet(unrelated_opening=unrelated_opening)
    doc = fitz.open()
    try:
        page = doc.new_page(width=gray.shape[1] / 2.0, height=gray.shape[0] / 2.0)
        page.insert_image(page.rect, stream=_png(gray), keep_proportion=False)
        page.insert_text(fitz.Point(*stack_xy), "2124 CRNR STACK", fontsize=7.0)
        if bifold_xy is not None:
            page.insert_text(fitz.Point(*bifold_xy), "2142 BIFOLD", fontsize=7.0)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _prepare_labelled(*, stack_xy: tuple[float, float], bifold_xy: tuple[float, float] | None = None,
                      unrelated_opening: bool = False):
    producer = SourceVisibilityProducer(
        producer_method="raster-corner-optin-contract",
        producer_version="1",
        raster_corner_framed_opening_shadow=True,
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="corner-optin-contract",
        source_bytes=_labelled_pdf(
            stack_xy=stack_xy, bifold_xy=bifold_xy, unrelated_opening=unrelated_opening),
        source_locator="memory://raster-corner-optin-labelled.pdf",
        page_ids=("1",),
    )
    published = producer.augment_with_raster_opening_primitives(
        published.revision.revision_id, page_ids=("1",))
    return producer, published


def _existence_pairs(producer, published):
    authority = producer.physical_opening_authority()
    found = {}
    for observation_id in published.raster_opening_primitive_observation_ids:
        selector = _selector(published, observation_id)
        result = authority.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            found[result.existence_record.record_id] = (selector, result.existence_record)
    return tuple(found[key] for key in sorted(found))


def _corner_pairs(producer, published):
    return tuple(
        (selector, record)
        for selector, record in _existence_pairs(producer, published)
        if record.structural_pattern == RASTER_CORNER_FRAMED_OPENING_LEG
    )


def test_opt_in_pairs_the_two_nominated_corner_leg_apertures() -> None:
    producer, published = _prepare(corner_shadow=True)
    records = _existence_records(producer, published)
    assert len(records) == 2
    authority = producer.physical_opening_authority()
    first, second = records
    assert authority.raster_corner_leg_sibling_aperture(first) == second.aperture_bbox_pt
    assert authority.raster_corner_leg_sibling_aperture(second) == first.aperture_bbox_pt


def test_opt_in_does_not_pair_an_unrelated_straight_opening_as_a_sibling() -> None:
    producer, published = _prepare(corner_shadow=True, unrelated_opening=True)
    authority = producer.physical_opening_authority()
    framed = [
        record for record in _existence_records(producer, published)
        if record.structural_pattern == RASTER_FRAMED_WALL_BAND_INTERRUPTION
    ]
    assert len(framed) == 1
    assert authority.raster_corner_leg_sibling_aperture(framed[0]) is None


def test_one_crnr_stack_callout_names_both_meeting_leaves() -> None:
    producer, published = _prepare_labelled(
        stack_xy=(130.0, 96.0),
        bifold_xy=(110.0, 168.0),
        unrelated_opening=True,
    )
    pairs = _corner_pairs(producer, published)
    assert len(pairs) == 2
    boxes = [record.aperture_bbox_pt for _selector, record in pairs]
    assert boxes[0] != boxes[1]

    semantic_producer = OpeningLabelSemanticProducer.from_source_visibility_producer(producer)
    dimension_producer = OpeningLabelDimensionProducer.from_source_visibility_producer(producer)
    owned = []
    for selector, record in pairs:
        semantic = semantic_producer.publish_scope(selector)
        assert semantic.status is EvidenceResolutionStatus.CORROBORATED
        assert semantic.evidence is not None
        assert semantic.evidence.semantic_kind == "door"
        assert any("CRNR STACK" in text.upper() for text in semantic.evidence.raw_texts)
        assert all("2142" not in text for text in semantic.evidence.raw_texts)

        dimension = dimension_producer.publish_scope(selector)
        assert dimension.status is EvidenceResolutionStatus.CORROBORATED
        assert dimension.evidence is not None
        assert dimension.evidence.semantic_kind == "door"
        assert dimension.evidence.dimension_values_mm == (2100.0, 2400.0)
        assert dimension.evidence.area_m2 == pytest.approx(5.04)
        owned.append((record, dimension.evidence.raw_text))

    assert all("2124" in text for _record, text in owned)

    # The printed callout sits on one leaf. Sibling ownership, not nearest
    # label, is what names the other leaf.
    horizontal = max(pairs, key=lambda item: item[1].aperture_bbox_pt[2] - item[1].aperture_bbox_pt[0])
    vertical = min(pairs, key=lambda item: item[1].aperture_bbox_pt[2] - item[1].aperture_bbox_pt[0])
    label = _TrustedTextLine(
        observation_ids=("synthetic",),
        text="2124 CRNR STACK",
        bbox=(130.0, 89.0, 210.0, 96.0),
    )
    assert _label_matches_gap(label, _gap_span_for_opening(producer, horizontal[1]))
    assert not _label_matches_gap(label, _gap_span_for_opening(producer, vertical[1]))
