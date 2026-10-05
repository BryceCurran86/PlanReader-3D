from __future__ import annotations

from io import BytesIO

import fitz
from PIL import Image, ImageDraw
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PhysicalOpeningAuthority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from pb_raster_visible_segment_detector import RasterDetectedSegment
from pb_source_observation_authority import ObservationSelector, SourceObservationProducer
import pb_source_observation_authority as source_observation
import pb_source_visibility_authority as visibility
from pb_source_visibility_authority import (
    RASTER_PDF_SEGMENT,
    RASTER_PDF_VISIBLE_SEGMENT,
    SourceVisibilityProducer,
)


def _image_pdf(image_bytes: bytes) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=200.0, height=120.0)
        page.insert_image(page.rect, stream=image_bytes, keep_proportion=False)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _blank_png() -> bytes:
    image = Image.new("RGB", (400, 240), "white")
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _wall_raster_png() -> bytes:
    image = Image.new("RGB", (400, 240), "white")
    draw = ImageDraw.Draw(image)
    for first, second in (
        ((40, 40), (360, 40)),
        ((40, 200), (360, 200)),
        ((40, 40), (40, 200)),
        ((360, 40), (360, 200)),
        ((200, 40), (200, 200)),
        ((40, 120), (360, 120)),
    ):
        draw.line((first, second), fill="black", width=3)
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def _one_segment() -> RasterDetectedSegment:
    return RasterDetectedSegment(
        pixel_geometry=(40.0, 120.0, 360.0, 120.0),
        geometry_pt=(20.0, 60.0, 180.0, 60.0),
        orientation="horizontal",
    )


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _raster_visible_records(producer: SourceVisibilityProducer, published):
    authority = producer.authority()
    records = []
    for observation_id in published.visible_observation_ids:
        result = authority.resolve_visible(_selector(published, observation_id))
        if (
            result.observation is not None
            and result.observation.observation_kind == RASTER_PDF_VISIBLE_SEGMENT
        ):
            records.append(result.observation)
    return tuple(records)


def test_single_source_owned_raster_segment_is_visible_even_when_object_is_incomplete(
    monkeypatch,
) -> None:
    payload = _image_pdf(_blank_png())
    monkeypatch.setattr(
        visibility,
        "detect_axis_aligned_raster_segments",
        lambda *args, **kwargs: (_one_segment(),),
    )
    producer = SourceVisibilityProducer(
        producer_method="task3-single-raster-segment",
        producer_version="1.0.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="task3-single-raster-segment",
        source_bytes=payload,
        source_locator="memory://task3-single-raster-segment.pdf",
        page_ids=("1",),
    )

    augmented = producer.augment_with_raster_visible_segments(
        published.revision.revision_id,
        page_ids=("1",),
    )
    raster = _raster_visible_records(producer, augmented)

    assert len(raster) == 1
    assert raster[0].geometry == pytest.approx(_one_segment().geometry_pt)

    opening = PhysicalOpeningAuthority(producer.authority()).prove_existence(
        _selector(augmented, raster[0].observation_id)
    )
    assert opening.status is EvidenceResolutionStatus.ABSTAINED


def test_raster_noise_with_no_authenticated_line_is_not_emitted(monkeypatch) -> None:
    payload = _image_pdf(_blank_png())
    monkeypatch.setattr(
        visibility,
        "detect_axis_aligned_raster_segments",
        lambda *args, **kwargs: (),
    )
    producer = SourceVisibilityProducer(
        producer_method="task3-raster-noise",
        producer_version="1.0.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="task3-raster-noise",
        source_bytes=payload,
        source_locator="memory://task3-raster-noise.pdf",
        page_ids=("1",),
    )

    augmented = producer.augment_with_raster_visible_segments(
        published.revision.revision_id,
        page_ids=("1",),
    )

    assert augmented.snapshot.snapshot_id == published.snapshot.snapshot_id
    assert _raster_visible_records(producer, augmented) == ()


def test_raster_visibility_preserves_page_parent_provenance(monkeypatch) -> None:
    payload = _image_pdf(_blank_png())
    monkeypatch.setattr(
        visibility,
        "detect_axis_aligned_raster_segments",
        lambda *args, **kwargs: (_one_segment(),),
    )
    producer = SourceVisibilityProducer(
        producer_method="task3-raster-provenance",
        producer_version="1.0.0",
    )
    published = producer.ingest_native_pdf_bytes(
        document_id="task3-raster-provenance",
        source_bytes=payload,
        source_locator="memory://task3-raster-provenance.pdf",
        page_ids=("1",),
    )
    augmented = producer.augment_with_raster_visible_segments(
        published.revision.revision_id,
        page_ids=("1",),
    )
    raster = _raster_visible_records(producer, augmented)
    assert len(raster) == 1

    visible = raster[0]
    assert len(visible.derivation_parent_ids) == 1
    parent_result = producer._producer.authority().resolve(
        _selector(augmented, visible.derivation_parent_ids[0])
    )
    assert parent_result.observation is not None
    assert parent_result.observation.observation_kind == RASTER_PDF_SEGMENT
    assert len(parent_result.observation.derivation_parent_ids) == 1

    receipt = producer._raster_visibility_receipts[
        (augmented.snapshot.snapshot_id, visible.observation_id)
    ]
    assert receipt.parent_observation_id == parent_result.observation.observation_id
    assert (
        receipt.page_parent_observation_id
        == parent_result.observation.derivation_parent_ids[0]
    )
    assert receipt.source_sha256 == augmented.revision.source_sha256
    assert receipt.page_id == "1"


def test_raster_identity_is_stable_across_detector_version_change(monkeypatch) -> None:
    payload = _image_pdf(_blank_png())
    monkeypatch.setattr(
        visibility,
        "detect_axis_aligned_raster_segments",
        lambda *args, **kwargs: (_one_segment(),),
    )

    def run(detector_version: str):
        monkeypatch.setattr(
            visibility,
            "RASTER_VISIBLE_SEGMENT_DETECTOR_VERSION",
            detector_version,
        )
        producer = SourceVisibilityProducer(
            producer_method="task3-raster-identity",
            producer_version="1.0.0",
        )
        published = producer.ingest_native_pdf_bytes(
            document_id="task3-raster-identity",
            source_bytes=payload,
            source_locator="memory://task3-raster-identity.pdf",
            page_ids=("1",),
        )
        augmented = producer.augment_with_raster_visible_segments(
            published.revision.revision_id,
            page_ids=("1",),
        )
        record = _raster_visible_records(producer, augmented)[0]
        receipt = producer._raster_visibility_receipts[
            (augmented.snapshot.snapshot_id, record.observation_id)
        ]
        parent_result = producer._producer.authority().resolve(
            _selector(augmented, record.derivation_parent_ids[0])
        )
        assert parent_result.observation is not None
        return (
            record.observation_id,
            record.source_primitive_ref,
            parent_result.observation.observation_id,
            parent_result.observation.source_primitive_ref,
            receipt.detector_version,
        )

    first = run("detector-A")
    second = run("detector-B")

    assert first[:4] == second[:4]
    assert first[4] == "detector-A"
    assert second[4] == "detector-B"


def test_raster_source_ownership_requires_full_union_coverage() -> None:
    tiled_regions = (
        (0.0, 0.0, 50.0, 50.0),
        (50.0, 0.0, 100.0, 50.0),
    )
    assert visibility._axis_aligned_geometry_fully_covered_by_rect_union(
        (10.0, 25.0, 90.0, 25.0), tiled_regions
    )
    assert not visibility._axis_aligned_geometry_fully_covered_by_rect_union(
        (10.0, 25.0, 110.0, 25.0), tiled_regions
    )


def test_visibility_derivation_cache_is_run_and_snapshot_scoped(monkeypatch) -> None:
    payload = _image_pdf(_blank_png())
    calls = 0
    original = visibility._derive_visibility_page

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(visibility, "_derive_visibility_page", counted)

    for suffix in ("a", "b"):
        producer = SourceVisibilityProducer(
            producer_method=f"task3-cache-{suffix}",
            producer_version="1.0.0",
        )
        producer.ingest_native_pdf_bytes(
            document_id="task3-cache-source",
            source_bytes=payload,
            source_locator="memory://task3-cache-source.pdf",
            page_ids=("1",),
        )

    assert calls == 2


def test_physical_wall_identity_is_stable_across_raster_detector_versions(
    monkeypatch,
) -> None:
    payload = _image_pdf(_wall_raster_png())

    def run(detector_version: str):
        monkeypatch.setattr(
            visibility,
            "RASTER_VISIBLE_SEGMENT_DETECTOR_VERSION",
            detector_version,
        )
        producer = SourceVisibilityProducer(
            producer_method="task3-wall-raster-identity",
            producer_version="1.0.0",
        )
        published = producer.ingest_native_pdf_bytes(
            document_id="task3-wall-raster-identity",
            source_bytes=payload,
            source_locator="memory://task3-wall-raster-identity.pdf",
            page_ids=("1",),
        )
        wall_producer = PhysicalWallCandidateProducer.from_source_visibility_producer(
            producer, page_ids=("1",)
        )
        wall_authority = wall_producer.authority()
        scope = next(
            result
            for result in wall_authority._scopes.values()
            if result.page_id == "1" and result.scope_kind == "page"
        )
        assert scope.records
        return tuple(
            sorted(
                (
                    record.wall_candidate_id,
                    record.physical_identity.candidate_identity_id,
                    record.physical_identity.path_fingerprint,
                    record.physical_identity.source_primitive_ids,
                )
                for record in scope.records
            )
        )

    assert run("detector-A") == run("detector-B")


def test_native_page_decode_cache_is_producer_run_scoped(monkeypatch) -> None:
    payload = _image_pdf(_blank_png())
    calls = 0
    original = source_observation._decode_native_page_for_cache

    def counted(*args, **kwargs):
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        source_observation, "_decode_native_page_for_cache", counted
    )

    for suffix in ("a", "b"):
        producer = SourceObservationProducer(
            producer_method=f"task3-native-cache-{suffix}",
            producer_version="1.0.0",
        )
        first = producer.ingest_native_pdf_bytes(
            document_id="task3-native-cache-source",
            source_bytes=payload,
            source_locator="memory://task3-native-cache-source.pdf",
            page_ids=("1",),
        )
        second = producer.ingest_native_pdf_bytes(
            document_id="task3-native-cache-source",
            source_bytes=payload,
            source_locator="memory://task3-native-cache-source.pdf",
            page_ids=("1",),
        )
        assert second.snapshot.snapshot_id == first.snapshot.snapshot_id

    assert calls == 2
