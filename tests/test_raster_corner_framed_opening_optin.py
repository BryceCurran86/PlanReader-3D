"""Default-off corner-leg existence: two legs, labelled-leg semantics stay unused here."""
from __future__ import annotations

from pb_opening_label_dimension_authority import parse_opening_label_dimensions
from pb_opening_label_semantic_authority import _explicit_word_kind
from pb_physical_opening_authority import (
    PHYSICAL_OPENING_EXISTS,
    RASTER_CORNER_FRAMED_OPENING_LEG,
    RASTER_FRAMED_WALL_BAND_INTERRUPTION,
)
from pb_source_visibility_authority import SourceVisibilityProducer
from test_raster_corner_framed_opening_shadow import (
    _existence_records,
    _pdf,
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
