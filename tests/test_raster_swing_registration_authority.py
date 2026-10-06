from __future__ import annotations

import cv2
import fitz
import numpy as np
import pytest

from pb_physical_opening_authority import _raster_swing_perpendicular_scale_ratio
from pb_source_observation_authority import (
    NativePageImagePlacement,
    SourceObservationProducer,
)


def _png(width: int, height: int) -> bytes:
    gray = np.full((height, width), 255, np.uint8)
    cv2.line(gray, (0, 0), (width - 1, height - 1), 0, 1)
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _pdf_with_image(*, image_width: int, image_height: int) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=180.0)
        page.insert_image(
            page.rect,
            stream=_png(image_width, image_height),
            keep_proportion=False,
        )
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_source_producer_reports_intrinsic_image_registration() -> None:
    producer = SourceObservationProducer(
        producer_method="swing-registration-test",
        producer_version="1",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="swing-registration-test",
        source_bytes=_pdf_with_image(image_width=360, image_height=640),
        source_locator="memory://swing-registration.pdf",
        page_ids=("1",),
    )
    placements = producer.native_page_image_placements(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        page_id="1",
    )

    assert len(placements) == 1
    placement = placements[0]
    assert placement.bbox_pt == pytest.approx((0.0, 0.0, 320.0, 180.0))
    assert placement.pixel_width == 360
    assert placement.pixel_height == 640


def test_swing_registration_ratio_tracks_axis_orientation() -> None:
    placement = NativePageImagePlacement(
        bbox_pt=(0.0, 0.0, 320.0, 180.0),
        pixel_width=360,
        pixel_height=640,
    )
    gap = (100.0, 60.0, 140.0, 80.0)

    horizontal = _raster_swing_perpendicular_scale_ratio(
        gap,
        "horizontal",
        (placement,),
    )
    vertical = _raster_swing_perpendicular_scale_ratio(
        gap,
        "vertical",
        (placement,),
    )

    assert horizontal == pytest.approx((180.0 / 640.0) / (320.0 / 360.0))
    assert vertical == pytest.approx(1.0 / horizontal)


def test_swing_registration_requires_gap_inside_registered_image() -> None:
    placement = NativePageImagePlacement(
        bbox_pt=(0.0, 0.0, 100.0, 100.0),
        pixel_width=100,
        pixel_height=100,
    )
    assert _raster_swing_perpendicular_scale_ratio(
        (90.0, 90.0, 120.0, 120.0),
        "horizontal",
        (placement,),
    ) is None


def test_competing_image_transforms_fail_closed() -> None:
    first = NativePageImagePlacement(
        bbox_pt=(0.0, 0.0, 320.0, 180.0),
        pixel_width=640,
        pixel_height=360,
    )
    second = NativePageImagePlacement(
        bbox_pt=(0.0, 0.0, 320.0, 180.0),
        pixel_width=320,
        pixel_height=360,
    )
    assert _raster_swing_perpendicular_scale_ratio(
        (100.0, 60.0, 140.0, 80.0),
        "horizontal",
        (first, second),
    ) is None


def test_page_registration_scale_is_quarter_turn_symmetric() -> None:
    from pb_source_visibility_authority import SourceVisibilityProducer

    original = NativePageImagePlacement(
        bbox_pt=(0.0, 0.0, 320.0, 180.0),
        pixel_width=640,
        pixel_height=360,
    )
    rotated = NativePageImagePlacement(
        bbox_pt=(0.0, 0.0, 320.0, 180.0),
        pixel_width=360,
        pixel_height=640,
    )

    original_scale = SourceVisibilityProducer._registration_scale_from_image_placements(
        (original,)
    )
    rotated_scale = SourceVisibilityProducer._registration_scale_from_image_placements(
        (rotated,)
    )

    assert original_scale == pytest.approx((1.0, 1.0))
    assert rotated_scale is not None
    assert rotated_scale[0] == pytest.approx(1.0 / rotated_scale[1])
    assert rotated_scale[0] > 1.0
    assert rotated_scale[1] < 1.0


def test_page_registration_accepts_matching_tile_transforms() -> None:
    from pb_source_visibility_authority import SourceVisibilityProducer

    placements = (
        NativePageImagePlacement(
            bbox_pt=(0.0, 0.0, 160.0, 180.0),
            pixel_width=320,
            pixel_height=360,
        ),
        NativePageImagePlacement(
            bbox_pt=(160.0, 0.0, 320.0, 180.0),
            pixel_width=320,
            pixel_height=360,
        ),
    )
    assert SourceVisibilityProducer._registration_scale_from_image_placements(
        placements
    ) == pytest.approx((1.0, 1.0))


def test_page_registration_rejects_competing_tile_transforms() -> None:
    from pb_source_visibility_authority import SourceVisibilityProducer

    placements = (
        NativePageImagePlacement(
            bbox_pt=(0.0, 0.0, 160.0, 180.0),
            pixel_width=320,
            pixel_height=360,
        ),
        NativePageImagePlacement(
            bbox_pt=(160.0, 0.0, 320.0, 180.0),
            pixel_width=160,
            pixel_height=360,
        ),
    )
    assert (
        SourceVisibilityProducer._registration_scale_from_image_placements(
            placements
        )
        is None
    )
