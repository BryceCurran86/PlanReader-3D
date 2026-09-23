"""Live source-owned ceiling-lining extractor integration tests."""
from __future__ import annotations

import fitz

from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1
from pb_live_ceiling_lining_integration import (
    LIVE_CEILING_LINING_RESOLVED,
    LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT,
    collect_live_ceiling_lining_claims,
)
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _pdf_bytes(*, framed: bool = True) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=460.0, height=320.0)

        if framed:
            page.draw_rect(
                fitz.Rect(30.0, 25.0, 370.0, 230.0),
                color=(0, 0, 0),
                width=1.0,
            )
            page.insert_text(
                fitz.Point(120.0, 48.0),
                "GROUND FLOOR PLAN",
                fontsize=8.0,
                color=(0, 0, 0),
            )

        # Two rooms sharing a physical wall, wholly inside the viewport.
        for first, second in (
            ((70.0, 70.0), (330.0, 70.0)),
            ((330.0, 70.0), (330.0, 175.0)),
            ((330.0, 175.0), (70.0, 175.0)),
            ((70.0, 175.0), (70.0, 70.0)),
            ((200.0, 70.0), (200.0, 175.0)),
        ):
            page.draw_line(
                fitz.Point(*first),
                fitz.Point(*second),
                color=(0, 0, 0),
                width=1.0,
            )

        page.insert_text(
            fitz.Point(92.0, 122.0),
            "CEILING FINISH: CHIPBOARD",
            fontsize=7.0,
            color=(0, 0, 0),
        )

        span = POINTS_PER_METRE_AT_1_1 / 100.0
        x0, x1, y = 95.0, 95.0 + span, 205.0
        shape = page.new_shape()
        shape.draw_line(fitz.Point(x0, y), fitz.Point(x1, y))
        shape.draw_line(fitz.Point(x0, y - 6.0), fitz.Point(x0, y + 6.0))
        shape.draw_line(fitz.Point(x1, y - 6.0), fitz.Point(x1, y + 6.0))
        shape.finish(width=1.0)
        shape.commit()
        page.insert_text(fitz.Point(x0 - 2.0, y + 18.0), "0", fontsize=7.0)
        page.insert_text(fitz.Point(x1 - 4.0, y + 18.0), "1m", fontsize=7.0)

        # Keep generic extractor drawing-page classification positive.
        page.insert_text(
            fitz.Point(390.0, 285.0),
            "SCALE 1:100",
            fontsize=7.0,
        )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _write(tmp_path, *, framed: bool = True):
    path = tmp_path / ("framed.pdf" if framed else "unframed.pdf")
    path.write_bytes(_pdf_bytes(framed=framed))
    return path


def test_resolved_floor_plan_emits_live_chipboard_ceiling_claim(tmp_path) -> None:
    path = _write(tmp_path, framed=True)

    result = collect_live_ceiling_lining_claims(path, pages=(0,))

    assert result.reason_codes[0] == LIVE_CEILING_LINING_RESOLVED
    assert len(result.claims) == 1
    claim = result.claims[0]
    assert claim.tag == "ceiling_chipboard"
    assert claim.finish_descriptor == "chipboard"
    assert claim.quantity_m2 > 0.0
    assert claim.status == "provisional"
    assert claim.room_quantity_ids
    assert claim.room_entity_ids
    assert claim.evidence_ids
    assert claim.physical_scale_record_id


def test_generic_extractor_publishes_only_separate_live_provisional_prediction(tmp_path) -> None:
    path = _write(tmp_path, framed=True)

    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(
        path,
        pages=(0,),
        collect_item35_shadow=False,
    )

    ceiling = [item for item in predictions if item.tag == "ceiling_chipboard"]
    assert len(ceiling) == 1
    prediction = ceiling[0]
    assert prediction.quantity is not None and prediction.quantity > 0.0
    assert prediction.trade_type == "finishes"
    assert prediction.unit == "SM"
    assert prediction.metadata["derivation"] == "source_owned_ceiling_lining"
    assert prediction.metadata["live_authority_status"] == "provisional"
    assert prediction.metadata["commercial_projection_allowed"] is False
    assert prediction.metadata["physical_scale_record_id"]
    assert extractor.ceiling_lining_live["status"] == "corroborated"


def test_unframed_plan_does_not_fall_back_to_page_wide_ceiling_authority(tmp_path) -> None:
    path = _write(tmp_path, framed=False)

    extractor = GenericPlanReaderExtractor()
    predictions = extractor.extract_from_pdf(
        path,
        pages=(0,),
        collect_item35_shadow=False,
    )

    assert not any(item.tag.startswith("ceiling_") for item in predictions)
    assert extractor.ceiling_lining_live["claims"] == []


def _pdf_with_two_board_descriptors() -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=460.0, height=320.0)
        page.draw_rect(
            fitz.Rect(30.0, 25.0, 370.0, 230.0),
            color=(0, 0, 0),
            width=1.0,
        )
        page.insert_text(
            fitz.Point(120.0, 48.0),
            "GROUND FLOOR PLAN",
            fontsize=8.0,
            color=(0, 0, 0),
        )
        for first, second in (
            ((70.0, 70.0), (330.0, 70.0)),
            ((330.0, 70.0), (330.0, 175.0)),
            ((330.0, 175.0), (70.0, 175.0)),
            ((70.0, 175.0), (70.0, 70.0)),
            ((200.0, 70.0), (200.0, 175.0)),
        ):
            page.draw_line(
                fitz.Point(*first),
                fitz.Point(*second),
                color=(0, 0, 0),
                width=1.0,
            )
        page.insert_text(
            fitz.Point(86.0, 115.0),
            "CEILING FINISH: BOARD TYPE A",
            fontsize=6.5,
        )
        page.insert_text(
            fitz.Point(218.0, 115.0),
            "CEILING FINISH: BOARD TYPE B",
            fontsize=6.5,
        )
        span = POINTS_PER_METRE_AT_1_1 / 100.0
        x0, x1, y = 95.0, 95.0 + span, 205.0
        shape = page.new_shape()
        shape.draw_line(fitz.Point(x0, y), fitz.Point(x1, y))
        shape.draw_line(fitz.Point(x0, y - 6.0), fitz.Point(x0, y + 6.0))
        shape.draw_line(fitz.Point(x1, y - 6.0), fitz.Point(x1, y + 6.0))
        shape.finish(width=1.0)
        shape.commit()
        page.insert_text(fitz.Point(x0 - 2.0, y + 18.0), "0", fontsize=7.0)
        page.insert_text(fitz.Point(x1 - 4.0, y + 18.0), "1m", fontsize=7.0)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_distinct_finish_descriptors_that_share_one_family_tag_abstain(tmp_path) -> None:
    path = tmp_path / "tag-conflict.pdf"
    path.write_bytes(_pdf_with_two_board_descriptors())

    result = collect_live_ceiling_lining_claims(path, pages=(0,))

    assert result.claims == ()
    assert LIVE_CEILING_LINING_TAG_FAMILY_CONFLICT in result.reason_codes
