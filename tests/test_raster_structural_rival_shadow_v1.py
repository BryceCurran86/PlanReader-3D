"""Report-only structural rival proof (rank 25): off-centre fragments inside solid wall ink are recorded, drafting is not.

Real sealed source and host producers over synthetic raster pages; only the extra wall candidate is synthetic. The live frame
results are compared with the switch off and on in every case.
"""
from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import cv2
import fitz
import numpy as np
import pytest

import pb_opening_host_binding_authority as host
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus as Status
from pb_opening_host_frame_authority import OpeningHostFrameProducer
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer
from test_raster_connected_host_frame import _publish, _scope
from test_raster_door_swing_g17_contract import _png

EXTRA = "extra-fragment"


def _image(draw=None):
    image = np.full((440, 1400), 255, np.uint8)
    for lo, hi in ((230, 440), (600, 800), (960, 1160)):
        cv2.rectangle(image, (lo, 150), (hi, 164), 0, -1)
    for x in (440, 800):
        cv2.line(image, (x, 164), (x, 324), 0, 1)
        cv2.ellipse(image, (x, 164), (160, 160), 0, 0, 90, 0, 1)
    if draw is not None:
        draw(image)
    return image


def _pdf(draw=None, *, rotation=0, scale=1):
    image = np.ascontiguousarray(np.rot90(_image(draw), rotation))
    doc = fitz.open()
    width, height = (180, 320) if rotation % 2 else (320, 180)
    page = doc.new_page(width=width * scale, height=height * scale)
    page.insert_image(page.rect, stream=_png(image), keep_proportion=False)
    data = doc.tobytes(garbage=4, deflate=True)
    doc.close()
    return data


def _fixture(data, *, shadow):
    source = SourceVisibilityProducer(producer_method="structural-rival-test", producer_version="1")
    published = source.ingest_native_pdf_bytes(document_id="structural-rival-test", source_bytes=data,
                                               source_locator="memory://structural-rival.pdf", page_ids=("1",))
    composition = compose_live_wall_opening_authority(source_visibility_producer=source,
                                                      revision_id=published.revision.revision_id, page_ids=("1",))
    published = source.published_snapshot_for_revision(published.revision.revision_id)
    producer = OpeningHostFrameProducer.from_authorities(
        physical_opening_authority=composition.physical_opening_authority,
        host_binding_authority=composition.opening_host_binding_authority,
        physical_wall_candidate_authority=composition.physical_wall_candidate_authority,
        raster_structural_rival_shadow=shadow)
    bound = []
    for trace in composition.opening_bindings:
        selector = ObservationSelector(document_id=published.revision.document_id,
                                       revision_id=published.revision.revision_id,
                                       source_sha256=published.revision.source_sha256,
                                       snapshot_id=published.snapshot.snapshot_id,
                                       observation_id=trace.representative_observation_id)
        opening = composition.physical_opening_authority.prove_existence(selector).existence_record
        binding_selector = composition.binding_selectors[trace.opening_identity_id]
        binding = composition.opening_host_binding_authority.resolve(binding_selector).record
        bound.append((selector, opening, binding_selector, binding))
    return producer, tuple(bound)


def _geometry(producer, bound):
    return host._opening_geometry(producer._opening, bound[0][1])


def _with_extra(monkeypatch, producer, bound, points_of, *, reverse=False):
    """Add one synthetic wall candidate to the sealed scope; ``points_of(scope, geometry)`` gives its centreline."""
    scope = _scope(producer, bound)
    record = scope.records[0]
    points = tuple((float(x), float(y)) for x, y in points_of(scope, _geometry(producer, bound)))
    extra = replace(record, wall_candidate_id=EXTRA,
                    physical_identity=replace(record.physical_identity, source_primitive_ids=("unowned",)),
                    wall_candidate=replace(record.wall_candidate, centerline_pts=points))
    records = (*scope.records, extra)
    changed = replace(scope, records=records[::-1] if reverse else records)
    monkeypatch.setattr(producer._walls, "resolve_scope", lambda _selector: changed)


def _beside_a_wall(fraction):
    """A fragment inside the first real wall piece, offset from its centre line by ``fraction`` of the host thickness."""
    def points(scope, geometry):
        start, end = scope.records[0].wall_candidate.centerline_pts[0], scope.records[0].wall_candidate.centerline_pts[-1]
        shift = (geometry.normal[0] * fraction * geometry.thickness, geometry.normal[1] * fraction * geometry.thickness)
        return [tuple(start[i] + (end[i] - start[i]) * t + shift[i] for i in range(2)) for t in (0.15, 0.85)]

    return points


def _at(*points):
    return lambda scope, geometry: points


def _both(monkeypatch, data, points_of, **kwargs):
    """Live results with the switch off and on, and what the switch recorded."""
    outcomes = []
    for shadow in (False, True):
        producer, bound = _fixture(data, shadow=shadow)
        if points_of is not None:
            _with_extra(monkeypatch, producer, bound, points_of, **kwargs)
        results = _publish(producer, bound)
        outcomes.append((results, producer.structural_rival_shadow()))
        monkeypatch.undo()
    (off, off_records), (on, records) = outcomes
    assert off == on and off_records == ()  # report only
    return on, records


def test_the_plain_page_records_nothing_and_keeps_its_frames(monkeypatch):
    results, records = _both(monkeypatch, _pdf(), None)
    assert all(r.status is Status.CORROBORATED for r in results) and records == ()


def test_an_off_centre_fragment_inside_solid_wall_ink_is_recorded_and_changes_nothing(monkeypatch):
    results, records = _both(monkeypatch, _pdf(), _beside_a_wall(0.28))
    assert all(r.status is Status.CORROBORATED for r in results)  # the live rule still ignores it (the known gap)
    assert records and {r["wall_candidate_id"] for r in records} == {EXTRA}
    assert all(r["would_abstain"] is True and 0.74 < abs(r["offset_pt"]) <= r["band_thickness_pt"] for r in records)


@pytest.mark.parametrize("x0, top", [(1240, 154), (1240, 156), (1200, 153)])
def test_a_drawn_off_centre_continuation_wall_is_recorded_end_to_end(monkeypatch, x0, top):
    """A real competing wall from ink alone: the live rule keeps the frame, the proof says it would not."""
    data = _pdf(lambda image: cv2.rectangle(image, (x0, top), (1390, top + 14), 0, -1))
    results, records = _both(monkeypatch, data, None)
    assert all(r.status is Status.CORROBORATED for r in results)
    assert len({r["wall_candidate_id"] for r in records}) == 1 and all(r["would_abstain"] for r in records)


@pytest.mark.parametrize("kwargs", [dict(rotation=1), dict(scale=2)], ids=["rotated", "scaled"])
def test_the_proof_holds_for_turned_and_scaled_pages(monkeypatch, kwargs):
    _results, records = _both(monkeypatch, _pdf(**kwargs), _beside_a_wall(0.28))
    assert {r.get("wall_candidate_id") for r in records} == {EXTRA}


def test_record_order_does_not_matter(monkeypatch):
    data = _pdf()
    _results, forward = _both(monkeypatch, data, _beside_a_wall(0.28))
    _results, backward = _both(monkeypatch, data, _beside_a_wall(0.28), reverse=True)
    assert forward == backward


def _dimension_line(image):
    cv2.line(image, (1200, 162), (1380, 162), 0, 1)
    for x in range(1220, 1380, 40):
        cv2.line(image, (x - 6, 168), (x + 6, 156), 0, 1)


def _label_text(image):
    cv2.putText(image, "9090", (1205, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.6, 0, 1)


def _title_table(image):
    for y in (160, 190, 220):
        cv2.line(image, (1200, y), (1390, y), 150, 1)
    for x in (1200, 1260, 1330, 1390):
        cv2.line(image, (x, 160), (x, 220), 150, 1)


def _block_too_thick(image):
    cv2.rectangle(image, (1200, 148), (1380, 174), 0, -1)


# Along x 275..312 pt at y 66.24 (1.8 pt off the host centre line), beyond the last wall piece.
BEYOND = _at((276.0, 66.24), (312.0, 66.24))


@pytest.mark.parametrize("draw, points", [
    (None, BEYOND), (_dimension_line, BEYOND), (_label_text, BEYOND), (_title_table, _at((276.0, 65.45), (312.0, 65.45))),
    (_block_too_thick, BEYOND),
    (None, _at((90.0, 66.24), (112.0, 66.24))),  # runs past the end of its wall: the band does not cover it
    (None, _beside_a_wall(0.65)),  # outside the host body
], ids=["blank", "dimension-line", "label-text", "title-table", "block-too-thick", "partly-covered", "outside-body"])
def test_drafting_and_unproven_fragments_are_not_recorded(monkeypatch, draw, points):
    _results, records = _both(monkeypatch, _pdf(draw), points)
    assert records == ()


def test_a_fragment_inside_the_centre_tolerance_stays_with_the_live_rule(monkeypatch):
    results, records = _both(monkeypatch, _pdf(), _beside_a_wall(0.05))
    assert all(r.status is Status.ABSTAINED for r in results) and records == ()


def test_an_error_in_the_proof_is_reported_and_changes_nothing(monkeypatch):
    monkeypatch.setattr(OpeningHostFrameProducer, "_raster_wall_band_boxes",
                        lambda self, selector: (_ for _ in ()).throw(RuntimeError("no bands")))
    data = _pdf()
    producer, bound = _fixture(data, shadow=True)
    _with_extra(monkeypatch, producer, bound, _beside_a_wall(0.28))
    results = _publish(producer, bound)
    assert all(r.status is Status.CORROBORATED for r in results)
    assert {r.get("shadow_error") for r in producer.structural_rival_shadow()} == {"RuntimeError"}


def _proof(offset, *bands, axis=(1.0, 0.0), thickness=6.48, along=(10.0, 40.0)):
    geometry = SimpleNamespace(axis=axis, normal=(-axis[1], axis[0]), origin=(0.0, 0.0), thickness=thickness)
    record = SimpleNamespace(wall_candidate=SimpleNamespace(centerline_pts=((along[0], offset), (along[1], offset))))
    return OpeningHostFrameProducer._structural_rival_proof(record, geometry, bands)


HOST_BAND = (True, 0.0, 100.0, -3.2, 3.2)


def test_the_rule_itself():
    assert _proof(1.8, HOST_BAND) == (1.8, 6.4)
    assert _proof(0.5, HOST_BAND) is None  # inside the centre tolerance: the live rule's own case
    assert _proof(5.0, (True, 0.0, 100.0, 1.0, 7.4)) is None  # in a band, but outside the host body
    assert _proof(1.8, (True, 0.0, 100.0, 20.0, 26.4)) is None  # a parallel wall elsewhere is not this ink
    assert _proof(1.8, (False, 0.0, 100.0, -3.2, 3.2)) is None  # a band of the other direction
    assert _proof(1.8, HOST_BAND, along=(90.0, 110.0)) is None  # not covered to its end
    assert _proof(1.8, (True, 0.0, 100.0, -1.6, 2.4)) is None  # a band much thinner than the host
    assert _proof(1.8, HOST_BAND, axis=(0.8, 0.6)) is None  # a sloping host is never proven


def test_bands_pair_only_the_faces_their_ends_join():
    stacked = _pdf(lambda image: cv2.rectangle(image, (230, 168), (440, 182), 0, -1))
    producer, bound = _fixture(stacked, shadow=True)
    boxes = producer._raster_wall_band_boxes(bound[0][3])
    near = [box for box in boxes if box[0] and box[1] < 60.0]
    assert len(near) == 2 and all(5.5 < box[4] - box[3] < 7.0 for box in near)  # two walls, no box spanning between them


def test_the_switch_must_be_a_boolean():
    with pytest.raises(TypeError, match="raster_structural_rival_shadow must be a bool"):
        _fixture(_pdf(), shadow=1)
