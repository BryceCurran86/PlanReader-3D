from __future__ import annotations

import io
from types import SimpleNamespace

import fitz
import pytest
from PIL import Image

from pb_migration_contracts import EvidenceResolutionStatus
from pb_pdf_text_integrity_authority import (
    TEXT_CLIP_STATE_UNRESOLVED,
    TEXT_GLYPH_MAPPING_UNVERIFIED,
)
from pb_portable_raster_ocr_authority import MockOCRBackend, OCRLine
from pb_opening_elevation_frame_area_authority import (
    OPENING_ELEVATION_FRAME_AREA_UNAVAILABLE,
    OpeningElevationFrameAreaProducer,
    OpeningElevationFrameAreaSelector,
    _dimension_is_mixed_opening_assembly_span,
    opening_elevation_claim_family,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from test_pdf_text_integrity_source_state_v1 import _SYSINFO_DUP, _cmap, _pdf, _stream_obj


def _elevation_pdf(*, composite: bool = False, far_width_dimension: bool = False) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=500.0, height=400.0)
        page.insert_text((30.0, 30.0), "WINDOW ELEVATIONS", fontsize=10.0)

        # Closed source frame: 150pt x 120pt. Figured dimensions are 3000 x
        # 2400, preserving the same aspect ratio without requiring page scale.
        page.draw_rect(fitz.Rect(150.0, 120.0, 300.0, 240.0), width=1.0)
        page.insert_text((215.0, 185.0), "W1", fontsize=9.0)

        if composite:
            page.insert_text((258.0, 185.0), "D1", fontsize=9.0)

        # Horizontal figured dimension with two witness lines.  The optional
        # far placement simulates a valid dimension chain belonging to another
        # nearby elevation: it remains witness-bound but is not local enough to
        # authorize this frame.
        width_y = 45.0 if far_width_dimension else 80.0
        page.draw_line((150.0, width_y), (300.0, width_y), width=0.7)
        page.draw_line((150.0, width_y - 10.0), (150.0, 125.0), width=0.7)
        page.draw_line((300.0, width_y - 10.0), (300.0, 125.0), width=0.7)
        page.insert_text((212.0, width_y + 3.0), "3000", fontsize=8.0)

        # Vertical figured dimension with two witness lines.
        page.draw_line((110.0, 120.0), (110.0, 240.0), width=0.7)
        page.draw_line((100.0, 120.0), (155.0, 120.0), width=0.7)
        page.draw_line((100.0, 240.0), (155.0, 240.0), width=0.7)
        page.insert_text((113.0, 196.0), "2400", fontsize=8.0, rotate=90)

        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _glyph_unverified_elevation_pdf(*, unresolved_clip: bool = False) -> bytes:
    texts = "WINDOW ELEVATIONS W1 3000 2400 NOT REQUIRED"
    codes = sorted(set(map(ord, texts)))
    cmap = _cmap(
        sysinfo=_SYSINFO_DUP,
        mappings="\n".join(f"<{code:02X}> <{code:04X}>" for code in codes),
        count=len(codes),
    )
    stream = """
0.7 w
100 50 100 80 re S
100 145 m 200 145 l S
100 135 m 100 150 l S
200 135 m 200 150 l S
80 50 m 80 130 l S
70 50 m 105 50 l S
70 130 m 105 130 l S
BT /F1 10 Tf 25 180 Td (WINDOW ELEVATIONS) Tj ET
BT /F1 9 Tf 145 90 Td (W1) Tj ET
BT /F1 8 Tf 140 150 Td (3000) Tj ET
BT /F1 7 Tf 65 88 Td (2400) Tj ET
BT /F1 6 Tf 220 180 Td (NOT REQUIRED) Tj ET
"""
    if unresolved_clip:
        stream = (
            "q 10 0 m 500 0 l 10 400 l h W n "
            + stream
            + " Q"
        )
    return _pdf(
        stream,
        fonts={
            "F1": (
                5,
                "<< /Type /Font /Subtype /Type1 /BaseFont /Arial "
                "/FirstChar 32 /LastChar 126 /ToUnicode 6 0 R >>",
            )
        },
        extra={6: _stream_obj(cmap)},
    )


def _exact_word_backend(
    source,
    published,
    *,
    expected_reason_codes: tuple[str, ...] = (TEXT_GLYPH_MAPPING_UNVERIFIED,),
) -> MockOCRBackend:
    text_authority = source.text_integrity_authority()
    raster_key_to_text: dict[tuple[int, int, int], str] = {}
    required = {"WINDOW", "ELEVATIONS", "W1", "3000", "2400"}
    for observation_id in published.text_observation_ids:
        selector = ObservationSelector(
            document_id=published.revision.document_id,
            revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256,
            snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        )
        native = text_authority.resolve_text(selector)
        receipt = native.receipt
        if receipt is None or receipt.raw_text not in required:
            continue
        assert native.status is EvidenceResolutionStatus.ABSTAINED
        assert set(native.reason_codes) == set(expected_reason_codes)
        for dpi in (300, 450):
            png, _page_parent = source._producer.render_native_page_png(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                page_id=receipt.page_id,
                dpi=float(dpi),
                clip_pt=receipt.geometry,
            )
            image = Image.open(io.BytesIO(png))
            key = (dpi, image.width, image.height)
            previous = raster_key_to_text.get(key)
            assert previous in {None, receipt.raw_text}, (key, previous, receipt.raw_text)
            raster_key_to_text[key] = receipt.raw_text

    assert set(raster_key_to_text.values()) == required

    def responder(image: Image.Image, dpi: int):
        text = raster_key_to_text.get((int(dpi), image.width, image.height))
        if text is None:
            raise AssertionError(
                f"unexpected raster target: dpi={dpi} size={image.size}; "
                "non-required page words must not be OCR'd"
            )
        return (
            OCRLine(
                text=text,
                confidence=None,
                bbox_px=(1.0, 1.0, image.width - 1.0, image.height - 1.0),
            ),
        )

    return MockOCRBackend(responder=responder)


def _authority(payload: bytes):
    source = SourceVisibilityProducer(
        producer_method="opening-elevation-frame-area-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="opening-elevation-frame-area",
        source_bytes=payload,
        source_locator="memory://opening-elevation-frame-area.pdf",
    )
    producer = OpeningElevationFrameAreaProducer.from_source_visibility_producer(source)
    return published, producer.authority()


def _selector(published, mark: str) -> OpeningElevationFrameAreaSelector:
    return OpeningElevationFrameAreaSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        type_mark=mark,
    )


def test_opening_elevation_claim_family_matches_authority_title_contract() -> None:
    assert opening_elevation_claim_family(("WINDOW", "ELEVATIONS")) == "window"
    assert opening_elevation_claim_family(("DOOR", "ELEVATION")) == "door"
    assert opening_elevation_claim_family(("PROP.", "WINDOWS", "ELEVATIONS")) == "window"


def test_opening_elevation_claim_family_rejects_nonopening_or_mixed_titles() -> None:
    assert opening_elevation_claim_family(("BUILDING", "ELEVATIONS")) is None
    assert opening_elevation_claim_family(("WINDOW", "SCHEDULE")) is None
    assert (
        opening_elevation_claim_family(("WINDOW", "DOOR", "ELEVATIONS"))
        is None
    )


def _dim_item(
    dimension_id: str,
    axis_name: str,
    lo: float,
    hi: float,
    line: float,
):
    endpoints = (
        ((lo, line), (hi, line))
        if axis_name == "x"
        else ((line, lo), (line, hi))
    )
    return (
        SimpleNamespace(dimension_id=dimension_id),
        SimpleNamespace(endpoints=endpoints),
        1000.0,
        (axis_name, lo, hi),
        SimpleNamespace(),
    )


def _tag(mark: str, kind: str, x: float, y: float):
    return (
        SimpleNamespace(bbox=(x - 1.0, y - 1.0, x + 1.0, y + 1.0)),
        mark,
        kind,
    )


def test_partitioned_overall_dimension_with_adjacent_other_kind_is_composite() -> None:
    overall = _dim_item("overall", "x", 0.0, 100.0, -10.0)
    dimensions = (
        overall,
        _dim_item("part-a", "x", 0.0, 30.0, -20.0),
        _dim_item("part-b", "x", 30.0, 70.0, -20.0),
        _dim_item("part-c", "x", 70.0, 100.0, -20.0),
    )

    assert _dimension_is_mixed_opening_assembly_span(
        selected_item=overall,
        dimensions=dimensions,
        all_tags=(
            _tag("W1", "window", 50.0, 5.0),
            _tag("D1", "door", 50.0, 30.0),
        ),
        mark="W1",
        mark_kind="window",
        frame_bbox=(0.0, 0.0, 100.0, 10.0),
        locality_limit=20.0,
        tolerance=1.0,
    )


def test_shared_height_with_adjacent_door_is_not_composite_without_partition() -> None:
    overall = _dim_item("height", "x", 0.0, 100.0, -10.0)

    assert not _dimension_is_mixed_opening_assembly_span(
        selected_item=overall,
        dimensions=(overall,),
        all_tags=(
            _tag("W1", "window", 50.0, 5.0),
            _tag("D1", "door", 50.0, 30.0),
        ),
        mark="W1",
        mark_kind="window",
        frame_bbox=(0.0, 0.0, 100.0, 10.0),
        locality_limit=20.0,
        tolerance=1.0,
    )


def test_same_kind_panel_partition_does_not_become_mixed_opening_assembly() -> None:
    overall = _dim_item("overall", "x", 0.0, 100.0, -10.0)
    dimensions = (
        overall,
        _dim_item("part-a", "x", 0.0, 50.0, -20.0),
        _dim_item("part-b", "x", 50.0, 100.0, -20.0),
    )

    assert not _dimension_is_mixed_opening_assembly_span(
        selected_item=overall,
        dimensions=dimensions,
        all_tags=(
            _tag("W1", "window", 25.0, 5.0),
            _tag("W2", "window", 75.0, 30.0),
        ),
        mark="W1",
        mark_kind="window",
        frame_bbox=(0.0, 0.0, 100.0, 10.0),
        locality_limit=20.0,
        tolerance=1.0,
    )


def test_incomplete_subdimension_chain_cannot_reject_opening() -> None:
    overall = _dim_item("overall", "x", 0.0, 100.0, -10.0)
    dimensions = (
        overall,
        _dim_item("part-a", "x", 0.0, 30.0, -20.0),
        _dim_item("part-b", "x", 30.0, 60.0, -20.0),
    )

    assert not _dimension_is_mixed_opening_assembly_span(
        selected_item=overall,
        dimensions=dimensions,
        all_tags=(
            _tag("W1", "window", 50.0, 5.0),
            _tag("D1", "door", 50.0, 30.0),
        ),
        mark="W1",
        mark_kind="window",
        frame_bbox=(0.0, 0.0, 100.0, 10.0),
        locality_limit=20.0,
        tolerance=1.0,
    )


def test_partitioned_span_with_far_other_kind_is_not_local_composite() -> None:
    overall = _dim_item("overall", "x", 0.0, 100.0, -10.0)
    dimensions = (
        overall,
        _dim_item("part-a", "x", 0.0, 50.0, -20.0),
        _dim_item("part-b", "x", 50.0, 100.0, -20.0),
    )

    assert not _dimension_is_mixed_opening_assembly_span(
        selected_item=overall,
        dimensions=dimensions,
        all_tags=(
            _tag("W1", "window", 50.0, 5.0),
            _tag("D1", "door", 50.0, 100.0),
        ),
        mark="W1",
        mark_kind="window",
        frame_bbox=(0.0, 0.0, 100.0, 10.0),
        locality_limit=20.0,
        tolerance=1.0,
    )


def test_glyph_unverified_elevation_words_use_strict_raster_corroboration() -> None:
    source = SourceVisibilityProducer(
        producer_method="opening-elevation-raster-text-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="opening-elevation-raster-text",
        source_bytes=_glyph_unverified_elevation_pdf(),
        source_locator="memory://opening-elevation-raster-text.pdf",
    )
    backend = _exact_word_backend(source, published)

    producer = OpeningElevationFrameAreaProducer.from_source_visibility_producer_for_tests(
        source,
        backend,
    )
    result = producer.authority().resolve(_selector(published, "W1"))

    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record is not None
    assert result.record.area_m2 == pytest.approx(7.2)
    assert sorted((result.record.axis_x_mm, result.record.axis_y_mm)) == [2400.0, 3000.0]


def test_glyph_and_clip_unverified_elevation_words_use_post_clip_raster_proof() -> None:
    source = SourceVisibilityProducer(
        producer_method="opening-elevation-raster-clip-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="opening-elevation-raster-clip",
        source_bytes=_glyph_unverified_elevation_pdf(unresolved_clip=True),
        source_locator="memory://opening-elevation-raster-clip.pdf",
    )
    backend = _exact_word_backend(
        source,
        published,
        expected_reason_codes=(
            TEXT_GLYPH_MAPPING_UNVERIFIED,
            TEXT_CLIP_STATE_UNRESOLVED,
        ),
    )

    producer = (
        OpeningElevationFrameAreaProducer.from_source_visibility_producer_for_tests(
            source,
            backend,
        )
    )
    result = producer.authority().resolve(_selector(published, "W1"))

    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record is not None
    assert result.record.area_m2 == pytest.approx(7.2)
    assert sorted((result.record.axis_x_mm, result.record.axis_y_mm)) == [
        2400.0,
        3000.0,
    ]


def test_marked_window_elevation_proves_closed_gross_frame_area() -> None:
    published, authority = _authority(_elevation_pdf())

    result = authority.resolve(_selector(published, "W1"))

    assert result.status is EvidenceResolutionStatus.CORROBORATED, result.reason_codes
    assert result.record is not None
    record = result.record
    assert record.type_mark == "W1"
    assert record.opening_kind == "window"
    assert record.area_m2 == pytest.approx(7.2)
    assert sorted((record.axis_x_mm, record.axis_y_mm)) == [2400.0, 3000.0]
    assert record.mark_observation_id in record.source_observation_ids
    assert set(record.dimension_observation_ids).issubset(record.source_observation_ids)
    assert record.dimension_line_ids
    assert len(record.witness_line_ids) >= 4
    assert record.frame_geometry_ids


def test_composite_window_door_outer_frame_cannot_become_single_window_area() -> None:
    published, authority = _authority(_elevation_pdf(composite=True))

    result = authority.resolve(_selector(published, "W1"))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert OPENING_ELEVATION_FRAME_AREA_UNAVAILABLE in result.reason_codes


def test_remote_witness_bound_dimension_cannot_be_borrowed_by_frame() -> None:
    published, authority = _authority(
        _elevation_pdf(far_width_dimension=True)
    )

    result = authority.resolve(_selector(published, "W1"))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
    assert OPENING_ELEVATION_FRAME_AREA_UNAVAILABLE in result.reason_codes


def test_unknown_mark_never_inherits_another_elevation_frame() -> None:
    published, authority = _authority(_elevation_pdf())

    result = authority.resolve(_selector(published, "W2"))

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.record is None
