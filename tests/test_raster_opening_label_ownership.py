from __future__ import annotations

from dataclasses import replace

import cv2
import fitz
import numpy as np
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import (
    OpeningLabelDimensionProducer,
    _gap_span_for_opening,
)
from pb_opening_label_semantic_authority import OpeningLabelSemanticProducer
from pb_physical_opening_authority import (
    JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    PHYSICAL_OPENING_EXISTS,
    RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
)
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _raster_opening_pdf(*, label: str) -> bytes:
    gray = np.full((360, 640), 255, np.uint8)
    cv2.rectangle(gray, (30, 150), (240, 164), 0, -1)
    cv2.rectangle(gray, (400, 150), (610, 164), 0, -1)
    cv2.line(gray, (240, 154), (400, 154), 0, 1)
    cv2.line(gray, (240, 160), (400, 160), 0, 1)

    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=180.0)
        page.insert_image(page.rect, stream=_png(gray), keep_proportion=False)
        # Native text is semantic/figured evidence only. The producer-owned
        # images-only render used by G17 excludes this overlay.
        page.insert_text(fitz.Point(130.0, 96.0), label, fontsize=7.0)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _prepare(label: str):
    source = SourceVisibilityProducer(
        producer_method="raster-opening-label-ownership-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="raster-opening-label-ownership",
        source_bytes=_raster_opening_pdf(label=label),
        source_locator="memory://raster-opening-label-ownership.pdf",
        page_ids=("1",),
    )
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=("1",),
    )
    assert published.raster_opening_primitive_observation_ids

    physical = source.physical_opening_authority()
    found = {}
    for observation_id in published.raster_opening_primitive_observation_ids:
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
            found[result.existence_record.record_id] = (
                selector,
                result.existence_record,
            )
    assert len(found) == 1
    return source, published, next(iter(found.values()))


def test_raster_physical_opening_can_own_native_semantic_and_dimension_label() -> None:
    source, _published, (selector, opening) = _prepare("1518 STACKER")
    assert opening.aperture_bbox_pt is not None

    semantic = OpeningLabelSemanticProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)
    assert semantic.status is EvidenceResolutionStatus.CORROBORATED
    assert semantic.evidence is not None
    assert semantic.evidence.opening_record_id == opening.record_id
    assert semantic.evidence.semantic_kind == "door"
    assert semantic.evidence.source_text_observation_ids

    dimension = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)
    assert dimension.status is EvidenceResolutionStatus.CORROBORATED
    assert dimension.evidence is not None
    assert dimension.evidence.opening_record_id == opening.record_id
    assert dimension.evidence.semantic_kind == "door"
    assert dimension.evidence.dimension_values_mm == (1500.0, 1800.0)
    assert dimension.evidence.area_m2 == pytest.approx(2.7)
    assert dimension.evidence.source_text_observation_ids


def test_swing_raster_aperture_bbox_can_own_source_label_spatially() -> None:
    source, _published, (_selector, opening) = _prepare("STACKER")
    swing = replace(
        opening,
        structural_pattern=RASTER_DOOR_SWING_WALL_BAND_INTERRUPTION,
    )
    gap = _gap_span_for_opening(source, swing)
    assert gap is not None
    assert gap.along_max > gap.along_min
    assert gap.cross_spread > 0.0


def test_raster_aperture_bbox_is_spatial_ownership_only_for_g17_raster_pattern() -> None:
    source, _published, (_selector, opening) = _prepare("STACKER")

    raster_gap = _gap_span_for_opening(source, opening)
    assert raster_gap is not None
    assert raster_gap.along_max > raster_gap.along_min
    assert raster_gap.cross_spread > 0.0

    # The exact same isolated support cannot borrow the raster bbox shortcut
    # when represented as a legacy/native structural pattern.
    non_raster = replace(
        opening,
        structural_pattern=JAMB_BOUNDED_TWO_FACE_INTERRUPTION,
    )
    assert _gap_span_for_opening(source, non_raster) is None


@pytest.mark.parametrize(
    "bbox",
    (
        None,
        (0.0, 0.0, 20.0, 20.0),
        (10.0, 10.0, 10.0, 40.0),
        (10.0, 10.0, 40.0, 10.0),
        (0.0, 0.0, float("nan"), 10.0),
    ),
)
def test_invalid_raster_aperture_bbox_cannot_own_labels(bbox) -> None:
    source, _published, (_selector, opening) = _prepare("STACKER")
    assert _gap_span_for_opening(
        source,
        replace(opening, aperture_bbox_pt=bbox),
    ) is None
