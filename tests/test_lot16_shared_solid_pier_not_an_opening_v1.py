"""A solid pier shared by two adjacent openings stays wall: it is never an opening.

Source-neutral regression (no production change). Two framed raster gaps are separated by a solid wall pier; the
physical-opening authority must publish exactly the two gaps and must never place an opening record on, or let a
neighbour's aperture reach into, the pier. Look-alike pier renderings (outline only, hatch poche, chase through a
solid pier) and narrow piers may abstain, but none may mint an opening on the pier.

The original-source check at the bottom reads the owner's private Lot16 PDF IN PLACE when it is available (path from
``PLANREADER_LOT16_ORIGINAL_PDF`` or the repository-relative ``documents/sources`` location) and is skipped otherwise.
It checks only geometry and identities, never an expected quantity, and reads no benchmark file.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import cv2
import fitz
import numpy as np
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer

ROOT = Path(__file__).resolve().parents[1]
PX_PER_PT = 2.0  # the synthetic image is drawn at two pixels per source point
BAND = (150, 164)  # wall band rows (7 pt thick)
FRAME_ROWS = (154, 160)  # glazing / frame lines inside a gap
TOL_PX = 3  # raster edge tolerance


def _sheet(pier_px: int, *, gap_px: int = 160, wall_px: int = 210, lead_px: int = 30, frame_rows=FRAME_ROWS):
    """Wall | gap | PIER | gap | wall. Returns (image, gap1, pier, gap2) in pixel columns."""
    width = lead_px + wall_px + gap_px + pier_px + gap_px + wall_px + 60
    gray = np.full((360, width), 255, np.uint8)
    y0, y1 = BAND
    x = lead_px
    cv2.rectangle(gray, (x, y0), (x + wall_px, y1), 0, -1)
    x += wall_px
    gap1 = (x, x + gap_px)
    for row in frame_rows:
        cv2.line(gray, (x, row), (x + gap_px, row), 0, 1)
    x += gap_px
    pier = (x, x + pier_px)
    cv2.rectangle(gray, (x, y0), (x + pier_px, y1), 0, -1)
    x += pier_px
    gap2 = (x, x + gap_px)
    for row in frame_rows:
        cv2.line(gray, (x, row), (x + gap_px, row), 0, 1)
    x += gap_px
    cv2.rectangle(gray, (x, y0), (x + wall_px, y1), 0, -1)
    return gray, gap1, pier, gap2


def _pdf(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    doc = fitz.open()
    height, width = gray.shape
    page = doc.new_page(width=width / PX_PER_PT, height=height / PX_PER_PT)
    page.insert_image(page.rect, stream=bytes(encoded), keep_proportion=False)
    payload = bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    return payload


def _records(gray: np.ndarray):
    return _records_from_pdf(_pdf(gray))


def _records_from_pdf(payload: bytes):
    producer = SourceVisibilityProducer(producer_method="shared-pier-negative", producer_version="1")
    published = producer.ingest_native_pdf_bytes(
        document_id="shared-pier-negative", source_bytes=payload,
        source_locator="memory://shared-pier-negative.pdf", page_ids=("1",),
    )
    published = producer.augment_with_raster_opening_primitives(published.revision.revision_id, page_ids=("1",))
    authority = producer.physical_opening_authority()
    records = {}
    for observation_id in published.raster_opening_primitive_observation_ids:
        result = authority.prove_existence(ObservationSelector(
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        ))
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            records[result.existence_record.record_id] = result.existence_record
    return tuple(records[key] for key in sorted(records))


def _span_px(record) -> tuple[float, float]:
    bbox = record.aperture_bbox_pt
    assert bbox is not None
    return bbox[0] * PX_PER_PT, bbox[2] * PX_PER_PT


def _reaches_into(record, pier: tuple[int, int]) -> bool:
    lo, hi = _span_px(record)
    return hi > pier[0] + TOL_PX and lo < pier[1] - TOL_PX


@pytest.mark.parametrize("pier_px", [40, 90, 160])
def test_two_openings_sharing_a_solid_pier_publish_exactly_the_two_gaps(pier_px):
    gray, gap1, pier, gap2 = _sheet(pier_px)
    records = _records(gray)
    assert len(records) == 2
    spans = sorted(_span_px(record) for record in records)
    for (lo, hi), gap in zip(spans, (gap1, gap2)):
        assert abs(lo - gap[0]) <= TOL_PX and abs(hi - gap[1]) <= TOL_PX
    assert not any(_reaches_into(record, pier) for record in records)
    assert len({record.record_id for record in records}) == 2


@pytest.mark.parametrize("shift_px", [0, 60, 200])
def test_translation_moves_the_openings_and_never_the_pier(shift_px):
    base, gap1, pier, gap2 = _sheet(90)
    shifted, sgap1, spier, sgap2 = _sheet(90, lead_px=30 + shift_px)
    reference = sorted(_span_px(record) for record in _records(base))
    moved_records = _records(shifted)
    moved = sorted(_span_px(record) for record in moved_records)
    assert len(reference) == len(moved) == 2
    for (rlo, rhi), (mlo, mhi) in zip(reference, moved):
        assert abs((mlo - rlo) - shift_px) <= TOL_PX and abs((mhi - rhi) - shift_px) <= TOL_PX
    assert spier[0] - pier[0] == shift_px
    assert not any(_reaches_into(record, spier) for record in moved_records)


def test_mirrored_sheet_keeps_two_openings_and_a_clear_pier():
    gray, _gap1, pier, _gap2 = _sheet(90)
    mirrored = np.ascontiguousarray(gray[:, ::-1])
    width = mirrored.shape[1]
    mirrored_pier = (width - pier[1], width - pier[0])
    records = _records(mirrored)
    assert len(records) == 2
    assert not any(_reaches_into(record, mirrored_pier) for record in records)


def _outline_pier(gray, pier):
    cv2.rectangle(gray, (pier[0], BAND[0]), (pier[1], BAND[1]), 255, -1)
    cv2.rectangle(gray, (pier[0], BAND[0]), (pier[1], BAND[1]), 0, 1)


def _faces_only_pier(gray, pier):
    cv2.rectangle(gray, (pier[0], BAND[0]), (pier[1], BAND[1]), 255, -1)
    cv2.line(gray, (pier[0], BAND[0]), (pier[1], BAND[0]), 0, 1)
    cv2.line(gray, (pier[0], BAND[1]), (pier[1], BAND[1]), 0, 1)


def _hatched_pier(gray, pier):
    cv2.rectangle(gray, (pier[0], BAND[0]), (pier[1], BAND[1]), 255, -1)
    for column in range(pier[0] - 14, pier[1] + 14, 6):
        cv2.line(gray, (column, BAND[1]), (column + 14, BAND[0]), 0, 1)
    cv2.rectangle(gray, (pier[0], BAND[0]), (pier[1], BAND[1]), 0, 1)


def _chased_pier(gray, pier):
    for row in FRAME_ROWS:  # a chase through a solid pier looks like frame lines
        cv2.line(gray, (pier[0], row), (pier[1], row), 255, 1)


@pytest.mark.parametrize("draw", [_outline_pier, _faces_only_pier, _hatched_pier, _chased_pier])
def test_look_alike_pier_renderings_never_mint_an_opening_on_the_pier(draw):
    gray, _gap1, pier, _gap2 = _sheet(90)
    draw(gray, pier)
    records = _records(gray)
    assert not any(_reaches_into(record, pier) for record in records)
    assert len(records) <= 2


@pytest.mark.parametrize("pier_px", [6, 16])
def test_narrow_shared_pier_may_abstain_but_never_merges_the_neighbours(pier_px):
    gray, gap1, pier, gap2 = _sheet(pier_px)
    records = _records(gray)
    assert not any(_reaches_into(record, pier) for record in records)
    for record in records:
        lo, hi = _span_px(record)
        width = hi - lo
        assert width <= (gap1[1] - gap1[0]) + 2 * TOL_PX  # never one aperture spanning both gaps


def test_control_without_any_pier_the_checks_see_one_merged_opening():
    """Teeth: if the pier were not wall the two gaps become one aperture, and both assertions above would fire."""
    gray, gap1, pier, _gap2 = _sheet(0)
    records = _records(gray)
    assert len(records) == 1
    assert _reaches_into(records[0], pier)
    lo, hi = _span_px(records[0])
    assert hi - lo > (gap1[1] - gap1[0]) + 2 * TOL_PX


def test_replay_is_deterministic_and_input_is_not_mutated():
    gray, _gap1, _pier, _gap2 = _sheet(90)
    # PyMuPDF stamps a random trailer /ID into every serialisation, so the replay must reuse ONE source byte string.
    payload = _pdf(gray)
    before = (hashlib.sha256(gray.tobytes()).hexdigest(), hashlib.sha256(payload).hexdigest())
    first = [(record.record_id, record.aperture_bbox_pt) for record in _records_from_pdf(payload)]
    second = [(record.record_id, record.aperture_bbox_pt) for record in _records_from_pdf(payload)]
    assert first == second and len(first) == 2
    assert (hashlib.sha256(gray.tobytes()).hexdigest(), hashlib.sha256(payload).hexdigest()) == before


# ---------------------------------------------------------------------------------------------------------------
# Original-source check (private PDF read in place; skipped when absent). Geometry and identities only.
# ---------------------------------------------------------------------------------------------------------------
LOT16_SHA256 = "10109b4b6e85e6e27af81f6399ce4b92abfdba80f87dc69dd5887bd6f3a65844"
SIGNED_ROWS = ROOT / "docs/engineering/lot16_original_signed_eight_row_20261015/production/verified_customer_rows.json"
SOUTH_DOOR_STACKER_PIER = (716.16, 760.56, 426.24, 429.6)  # x0, x1, y0, y1 in source points
LINE_TOL_PT = 3.0
OVERLAP_PT = 0.6


def _original_pdf() -> Path | None:
    for candidate in (
        os.environ.get("PLANREADER_LOT16_ORIGINAL_PDF"),
        str(ROOT / "documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf"),
    ):
        if candidate and Path(candidate).is_file():
            return Path(candidate)
    return None


def _piers_between_adjacent_apertures(boxes):
    """Spans between consecutive apertures on one wall line: (x0, x1, y0, y1) in points."""
    piers = []
    for horizontal in (True, False):
        group = []
        for box in boxes:
            wide, high = box[2] - box[0], box[3] - box[1]
            if (wide >= high) == horizontal:
                group.append(box)
        key = (lambda b: ((b[1] + b[3]) / 2, b[0])) if horizontal else (lambda b: ((b[0] + b[2]) / 2, b[1]))
        group.sort(key=key)
        for a, b in zip(group, group[1:]):
            if horizontal and abs((a[1] + a[3]) / 2 - (b[1] + b[3]) / 2) <= LINE_TOL_PT and b[0] > a[2] + 0.1:
                piers.append((a[2], b[0], min(a[1], b[1]), max(a[3], b[3])))
            if not horizontal and abs((a[0] + a[2]) / 2 - (b[0] + b[2]) / 2) <= LINE_TOL_PT and b[1] > a[3] + 0.1:
                piers.append((min(a[0], b[0]), max(a[2], b[2]), a[3], b[1]))
    return piers


def _overlap_pt(box, rect) -> float:
    return max(0.0, min(box[2], rect[1]) - max(box[0], rect[0])) * max(0.0, min(box[3], rect[3]) - max(box[1], rect[2]))


def test_pier_finder_returns_the_span_between_collinear_apertures_only():
    horizontal = [(10.0, 100.0, 40.0, 103.0), (80.0, 100.5, 120.0, 103.5), (200.0, 150.0, 240.0, 153.0)]
    assert _piers_between_adjacent_apertures(horizontal) == [(40.0, 80.0, 100.0, 103.5)]
    vertical = [(50.0, 10.0, 53.0, 40.0), (50.5, 90.0, 53.5, 120.0), (90.0, 10.0, 93.0, 40.0)]
    assert _piers_between_adjacent_apertures(vertical) == [(50.0, 53.5, 40.0, 90.0)]
    assert _piers_between_adjacent_apertures([(0.0, 0.0, 10.0, 3.0), (10.0, 0.0, 20.0, 3.0)]) == []  # abutting: no pier


def test_pier_overlap_measure_detects_an_aperture_inside_the_pier_and_ignores_the_neighbours():
    pier = (40.0 + OVERLAP_PT, 80.0 - OVERLAP_PT, 100.0, 103.5)
    assert _overlap_pt((60.0, 100.0, 70.0, 103.0), pier) > 0.0  # a third aperture on the pier is caught
    assert _overlap_pt((10.0, 100.0, 40.0, 103.0), pier) == 0.0  # left neighbour ends where the pier starts
    assert _overlap_pt((80.0, 100.5, 120.0, 103.5), pier) == 0.0  # right neighbour starts where the pier ends
    assert _overlap_pt((60.0, 120.0, 70.0, 123.0), pier) == 0.0  # same x, different wall line


def test_lot16_original_every_shared_pier_stays_wall_and_the_signed_eight_identities_remain():
    pdf = _original_pdf()
    if pdf is None:
        pytest.skip("private Lot16 original PDF not available")
    payload = pdf.read_bytes()
    assert hashlib.sha256(payload).hexdigest() == LOT16_SHA256

    source = SourceVisibilityProducer(
        producer_method="live-physical-net-wall", producer_version="1", raster_paired_outer_faces_shadow=True,
    )
    initial = source.ingest_native_pdf_bytes(
        document_id=f"live-source:{LOT16_SHA256[:32]}", source_bytes=payload,
        source_locator="memory://pdf", page_ids=(3,),
    )
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority

    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source, revision_id=initial.revision.revision_id, page_ids=("3",),
        include_unmeasured_ink_closed_flanks_shadow=True, source_fragment_roles_shadow=True,
    )
    published = source.published_snapshot_for_revision(initial.revision.revision_id)
    record = composition.semantic_enumeration_result.record
    authority = composition.physical_opening_authority
    records = {}
    for observation_id in record.representative_observation_ids:
        result = authority.prove_existence(ObservationSelector(
            document_id=published.revision.document_id, revision_id=published.revision.revision_id,
            source_sha256=published.revision.source_sha256, snapshot_id=published.snapshot.snapshot_id,
            observation_id=observation_id,
        ))
        if result.existence_record is not None and result.existence_record.aperture_bbox_pt is not None:
            records[result.existence_record.record_id] = result.existence_record

    signed = {
        entity for row in json.loads(SIGNED_ROWS.read_text(encoding="utf-8")) for entity in row["canonical_entity_ids"]
    }
    assert len(signed) == 8
    assert signed <= set(records), "a signed physical opening identity is no longer produced"

    boxes = {key: tuple(float(v) for v in value.aperture_bbox_pt) for key, value in records.items()}
    piers = _piers_between_adjacent_apertures(list(boxes.values()))
    door_stacker =[p for p in piers if abs(p[0] - SOUTH_DOOR_STACKER_PIER[0]) < 0.5 and abs(p[1] - SOUTH_DOOR_STACKER_PIER[1]) < 0.5]
    assert len(door_stacker) == 1, "the door/stacker pier must be a gap between exactly two apertures"
    assert len(piers) >= 8
    for pier in piers:
        rect = (pier[0] + OVERLAP_PT, pier[1] - OVERLAP_PT, pier[2], pier[3])
        offenders = [key for key, box in boxes.items() if _overlap_pt(box, rect) > 0.0]
        assert not offenders, f"an opening reaches into the solid pier {pier}: {offenders}"
