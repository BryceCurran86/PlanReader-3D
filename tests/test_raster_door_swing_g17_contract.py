from __future__ import annotations

import cv2
import fitz
import numpy as np

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


SWING_PATTERN = "raster_door_swing_wall_band_interruption"


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _sheet(
    *,
    leaf: bool,
    arc: bool,
    second_swing: bool = False,
    leaf_bundle: bool = False,
) -> np.ndarray:
    gray = np.full((360, 640), 255, np.uint8)

    # Generic wall-band interruption. The gap is 160 px wide and the wall band
    # is 14 px thick. No text, tags, dimensions, or project-specific values.
    cv2.rectangle(gray, (30, 150), (240, 164), 0, -1)
    cv2.rectangle(gray, (400, 150), (610, 164), 0, -1)

    radius = 160
    if leaf:
        cv2.line(gray, (240, 164), (240, 324), 0, 1)
        if leaf_bundle:
            # One physical leaf may rasterize as a compact pair of parallel
            # source runs. G17 must preserve both records without treating the
            # representation itself as a second swing configuration.
            cv2.line(gray, (242, 164), (242, 324), 0, 1)
    if arc:
        cv2.ellipse(
            gray,
            center=(240, 164),
            axes=(radius, radius),
            angle=0,
            startAngle=0,
            endAngle=90,
            color=0,
            thickness=1,
        )

    if second_swing:
        cv2.line(gray, (400, 164), (400, 324), 0, 1)
        cv2.ellipse(
            gray,
            center=(400, 164),
            axes=(radius, radius),
            angle=0,
            startAngle=90,
            endAngle=180,
            color=0,
            thickness=1,
        )
    return gray


def _pdf(gray: np.ndarray) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=180.0)
        page.insert_image(page.rect, stream=_png(gray), keep_proportion=False)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _results(gray: np.ndarray):
    source = SourceVisibilityProducer(
        producer_method="raster-door-swing-g17-contract",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="raster-door-swing-g17-contract",
        source_bytes=_pdf(gray),
        source_locator="memory://raster-door-swing-g17-contract.pdf",
        page_ids=("1",),
    )
    published = source.augment_with_raster_opening_primitives(
        published.revision.revision_id,
        page_ids=("1",),
    )
    assert published.raster_opening_primitive_observation_ids

    physical = source.physical_opening_authority()
    results = []
    for observation_id in published.raster_opening_primitive_observation_ids:
        result = physical.prove_existence(
            ObservationSelector(
                document_id=published.revision.document_id,
                revision_id=published.revision.revision_id,
                source_sha256=published.revision.source_sha256,
                snapshot_id=published.snapshot.snapshot_id,
                observation_id=observation_id,
            )
        )
        results.append(result)
    return tuple(results)


def _records(results):
    found = {}
    for result in results:
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            found[result.existence_record.record_id] = result.existence_record
    return tuple(found[key] for key in sorted(found))


def test_one_unambiguous_leaf_and_quarter_arc_proves_one_swing_opening() -> None:
    """EXPECTED RED until G17 promotes reviewed producer-owned swing evidence."""

    records = _records(_results(_sheet(leaf=True, arc=True)))
    assert len(records) == 1
    assert records[0].structural_pattern == SWING_PATTERN
    assert records[0].aperture_bbox_pt is not None


def test_compact_parallel_leaf_runs_preserve_one_physical_swing() -> None:
    records = _records(
        _results(_sheet(leaf=True, arc=True, leaf_bundle=True))
    )
    assert len(records) == 1
    assert records[0].structural_pattern == SWING_PATTERN
    assert records[0].aperture_bbox_pt is not None
    # Both producer-owned thin runs remain in the physical-opening provenance;
    # the authority does not pick a nearest/first representative.
    assert len(records[0].source_observation_ids) > 7


def test_quarter_turn_preserves_one_swing_opening() -> None:
    """EXPECTED RED until the swing rule is orientation-invariant in G17."""

    rotated = np.ascontiguousarray(
        np.rot90(_sheet(leaf=True, arc=True))
    )
    records = _records(_results(rotated))
    assert len(records) == 1
    assert records[0].structural_pattern == SWING_PATTERN


def test_leaf_without_arc_does_not_prove_an_opening() -> None:
    assert _records(_results(_sheet(leaf=True, arc=False))) == ()


def test_arc_without_leaf_does_not_prove_an_opening() -> None:
    assert _records(_results(_sheet(leaf=False, arc=True))) == ()


def test_two_valid_swing_configurations_fail_closed_as_ambiguous() -> None:
    results = _results(_sheet(leaf=True, arc=True, second_swing=True))
    assert _records(results) == ()
    assert any(
        result.status is EvidenceResolutionStatus.CONFLICT
        for result in results
    )
