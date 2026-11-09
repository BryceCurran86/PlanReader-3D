"""Synthetic contract for the raster corner framed-opening SHADOW detector.

Every sheet here is generic geometry: two orthogonal solid wall bands whose
single ends face a shared corner square, with optional frame lines. No text,
dimension, project, benchmark or expected quantity enters any fixture.
"""
from __future__ import annotations

import random
import re
from dataclasses import replace
from pathlib import Path

import cv2
import fitz
import numpy as np
import pytest

import pb_raster_corner_framed_opening_shadow as corner
from pb_migration_contracts import EvidenceResolutionStatus
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import (
    RASTER_OPENING_PRIMITIVE_RENDER_DPI,
    SourceVisibilityProducer,
)

ROOT = Path(__file__).resolve().parents[1]
# The producer resamples the whole embedded image, so an edge may move by one
# render pixel when the image size changes; nothing finer is claimed.
RENDER_PX_PT = 72.0 / RASTER_OPENING_PRIMITIVE_RENDER_DPI + 1e-6

# Image pixels; the page is half the image size, so 2 px = 1 pt.
H_BAND = ((400, 150), (610, 164))
V_BAND = ((100, 20), (114, 100))
H_FRAME_ROWS = (154, 160)
V_FRAME_COLS = (104, 110)
H_CLEAR_SPAN_PT = (400 - 115) / 2.0
V_CLEAR_SPAN_PT = (150 - 101) / 2.0
SPAN_TOL_PT = 0.75


def _png(gray: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", gray)
    assert ok
    return bytes(encoded)


def _sheet(
    *,
    frames: int = 2,
    face_lines: bool = False,
    solid_corner: bool = False,
    h_frame_start: int = 100,
    straight_partner: bool = False,
    second_corner_post: bool = False,
    furniture: bool = False,
    unrelated_opening: bool = False,
    split_frames: bool = False,
) -> np.ndarray:
    gray = np.full((360, 640), 255, np.uint8)
    cv2.rectangle(gray, *H_BAND, 0, -1)
    cv2.rectangle(gray, *V_BAND, 0, -1)
    for y in H_FRAME_ROWS[:frames]:
        if split_frames:
            cv2.line(gray, (h_frame_start, y), (260, y), 0, 1)
            cv2.line(gray, (250, y), (400, y), 0, 1)
        else:
            cv2.line(gray, (h_frame_start, y), (400, y), 0, 1)
    for x in V_FRAME_COLS[:frames]:
        cv2.line(gray, (x, 100), (x, 164), 0, 1)
    if face_lines:
        # The wall faces keep running past the jamb: a recess, not an opening.
        cv2.line(gray, (114, 150), (400, 150), 0, 1)
        cv2.line(gray, (114, 164), (400, 164), 0, 1)
    if solid_corner:
        cv2.rectangle(gray, (100, 150), (114, 164), 0, -1)
    if straight_partner:
        # A collinear band behind the corner makes a straight gap through it.
        cv2.rectangle(gray, (20, 150), (60, 164), 0, -1)
    if second_corner_post:
        # A second orthogonal band whose end also faces the same horizontal jamb.
        cv2.rectangle(gray, (160, 20), (174, 100), 0, -1)
        for x in (164, 170):
            cv2.line(gray, (x, 100), (x, 164), 0, 1)
    if furniture:
        # Double lines beside, not inside, the band cross ranges.
        for y in (175, 181):
            cv2.line(gray, (100, y), (400, y), 0, 1)
        for x in (125, 131):
            cv2.line(gray, (x, 100), (x, 164), 0, 1)
    if unrelated_opening:
        cv2.rectangle(gray, (30, 300), (200, 314), 0, -1)
        cv2.rectangle(gray, (330, 300), (500, 314), 0, -1)
        for y in (304, 310):
            cv2.line(gray, (200, y), (330, y), 0, 1)
    return gray


def _pdf(gray: np.ndarray, *, page_scale: float = 1.0, rotation: int = 0) -> bytes:
    doc = fitz.open()
    page = doc.new_page(width=page_scale * gray.shape[1] / 2.0,
                        height=page_scale * gray.shape[0] / 2.0)
    page.insert_image(page.rect, stream=_png(gray), keep_proportion=False)
    if rotation:
        page.set_rotation(rotation)
    payload = bytes(doc.tobytes(garbage=4, deflate=True))
    doc.close()
    return payload


def _ingest(payload: bytes, *, augment: bool = True):
    producer = SourceVisibilityProducer(
        producer_method="raster-corner-shadow-contract", producer_version="1")
    published = producer.ingest_native_pdf_bytes(
        document_id="corner-shadow-contract", source_bytes=payload,
        source_locator="memory://raster-corner-shadow-contract.pdf", page_ids=("1",))
    if augment:
        published = producer.augment_with_raster_opening_primitives(
            published.revision.revision_id, page_ids=("1",))
    return producer, published


def _publish(gray: np.ndarray, *, page_scale: float = 1.0, augment: bool = True,
             rotation: int = 0):
    return _ingest(_pdf(gray, page_scale=page_scale, rotation=rotation), augment=augment)


def _detect(producer, published):
    return corner.detect_raster_corner_framed_openings_shadow(
        producer, revision_id=published.revision.revision_id, page_id="1")


def _run(gray: np.ndarray, **kwargs):
    producer, published = _publish(gray, **kwargs)
    return _detect(producer, published)


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _existence_records(producer, published):
    authority = producer.physical_opening_authority()
    records = {}
    for observation_id in published.raster_opening_primitive_observation_ids:
        result = authority.prove_existence(_selector(published, observation_id))
        if (result.status is EvidenceResolutionStatus.CORROBORATED
                and result.proposition == PHYSICAL_OPENING_EXISTS
                and result.existence_record is not None):
            records[result.existence_record.record_id] = result.existence_record
    return tuple(records[key] for key in sorted(records))


def _only_candidate(result):
    assert result.status is EvidenceResolutionStatus.CANDIDATE
    assert result.reason_codes == (corner.CORNER_FRAMED_OPENING_NOMINATED,)
    assert len(result.candidates) == 1
    return result.candidates[0]


def _spans(candidate) -> list[float]:
    return sorted((candidate.horizontal_leg.leg_span_pt, candidate.vertical_leg.leg_span_pt))


def _signature(nomination, *, dx: float = 0.0, dy: float = 0.0):
    """Corner geometry in page points, translated back by (dx, dy)."""
    h, v = nomination.horizontal_leg, nomination.vertical_leg
    x0, y0, x1, y1 = nomination.corner_box_pt
    values = (
        x0 - dx, y0 - dy, x1 - dx, y1 - dy,
        h.clear_span_along_pt[0] - dx, h.clear_span_along_pt[1] - dx,
        h.cross_range_pt[0] - dy, h.cross_range_pt[1] - dy, h.leg_span_pt,
        v.clear_span_along_pt[0] - dy, v.clear_span_along_pt[1] - dy,
        v.cross_range_pt[0] - dx, v.cross_range_pt[1] - dx, v.leg_span_pt,
    )
    labels = (nomination.status, nomination.reason_codes, h.jamb_at_high_band_end,
              v.jamb_at_high_band_end, len(h.frame_line_observation_ids) >= 2,
              len(v.frame_line_observation_ids) >= 2)
    return labels, values


def _assert_same_corner(actual, expected, *, dx: float = 0.0, dy: float = 0.0) -> None:
    actual_labels, actual_values = _signature(actual, dx=dx, dy=dy)
    expected_labels, expected_values = _signature(expected)
    assert actual_labels == expected_labels
    assert actual_values == pytest.approx(expected_values, abs=RENDER_PX_PT)


def test_two_leg_framed_corner_is_nominated_without_any_authority() -> None:
    producer, published = _publish(_sheet())
    result = _detect(producer, published)
    candidate = _only_candidate(result)

    assert candidate.horizontal_leg.leg_span_pt == pytest.approx(H_CLEAR_SPAN_PT, abs=SPAN_TOL_PT)
    assert candidate.vertical_leg.leg_span_pt == pytest.approx(V_CLEAR_SPAN_PT, abs=SPAN_TOL_PT)
    assert candidate.corner_post_dimension_pt <= 7.5 + SPAN_TOL_PT
    assert candidate.first_remaining_gate == corner.CORNER_EXISTENCE_AUTHORITY_UNPROMOTED
    assert candidate.shadow_only and result.shadow_only
    assert not (candidate.takeoff_eligible or candidate.physical_opening_authority
                or candidate.deduction_authority or result.takeoff_eligible)
    for leg in (candidate.horizontal_leg, candidate.vertical_leg):
        assert leg.jamb_end_observation_id
        assert len(leg.face_observation_ids) == 2
        assert len(leg.frame_line_observation_ids) >= 2
    published_ids = set(published.raster_opening_primitive_observation_ids)
    assert set(candidate.source_observation_ids) <= published_ids
    assert len(candidate.source_observation_ids) >= 10
    # The ordinary straight-interruption detector still issues nothing here.
    assert _existence_records(producer, published) == ()


@pytest.mark.parametrize("frames", [0, 1])
def test_corner_without_two_frame_lines_per_leg_is_not_nominated(frames: int) -> None:
    result = _run(_sheet(frames=frames))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (corner.CORNER_FRAMED_OPENING_UNAVAILABLE,)
    assert result.nominations == ()
    assert result.rejected_geometric_corner_count >= 1


def test_furniture_double_lines_beside_the_bands_are_not_frames() -> None:
    result = _run(_sheet(frames=0, furniture=True))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.candidates == ()


@pytest.mark.parametrize(
    ("sheet", "reason"),
    [
        (dict(face_lines=True), corner.CORNER_LEG_WALL_FACE_INK_CONTINUES),
        (dict(solid_corner=True), corner.CORNER_SQUARE_SOLID_UNRESOLVED),
        (dict(h_frame_start=130), corner.CORNER_FRAME_DISCONNECTED),
        (dict(straight_partner=True), corner.CORNER_STRAIGHT_GAP_ALTERNATIVE),
    ],
)
def test_framed_look_alikes_abstain_with_a_typed_reason(sheet, reason: str) -> None:
    result = _run(_sheet(**sheet))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.candidates == ()
    assert reason in {nomination.reason_codes[0] for nomination in result.nominations}
    for nomination in result.nominations:
        assert nomination.status is EvidenceResolutionStatus.ABSTAINED
        assert nomination.first_remaining_gate == nomination.reason_codes[0]


def test_two_corner_posts_for_one_jamb_retain_both_and_abstain() -> None:
    result = _run(_sheet(second_corner_post=True))
    ambiguous = [nomination for nomination in result.nominations
                 if nomination.reason_codes == (corner.CORNER_BAND_END_OWNER_AMBIGUOUS,)]
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.candidates == ()
    assert len(ambiguous) == 2
    assert len({nomination.horizontal_leg.band_box_pt for nomination in ambiguous}) == 1
    assert len({nomination.vertical_leg.band_box_pt for nomination in ambiguous}) == 2


@pytest.mark.parametrize("turns", [0, 1, 2, 3])
def test_quarter_turns_preserve_one_nomination_and_leg_spans(turns: int) -> None:
    candidate = _only_candidate(_run(np.ascontiguousarray(np.rot90(_sheet(), turns))))
    assert _spans(candidate) == pytest.approx(
        sorted((H_CLEAR_SPAN_PT, V_CLEAR_SPAN_PT)), abs=SPAN_TOL_PT)


@pytest.mark.parametrize(("top", "left"), [(36, 60), (40, 0), (0, 25)])
def test_translation_moves_the_corner_without_changing_the_legs(top: int, left: int) -> None:
    base = _only_candidate(_run(_sheet()))
    shifted_gray = cv2.copyMakeBorder(_sheet(), top, 0, left, 0, cv2.BORDER_CONSTANT, value=255)
    shifted = _only_candidate(_run(shifted_gray))
    _assert_same_corner(shifted, base, dx=left / 2.0, dy=top / 2.0)


@pytest.mark.parametrize("page_scale", [0.75, 1.5])
def test_page_scale_scales_the_legs(page_scale: float) -> None:
    candidate = _only_candidate(_run(_sheet(), page_scale=page_scale))
    assert candidate.horizontal_leg.leg_span_pt == pytest.approx(
        page_scale * H_CLEAR_SPAN_PT, abs=page_scale * SPAN_TOL_PT)
    assert candidate.vertical_leg.leg_span_pt == pytest.approx(
        page_scale * V_CLEAR_SPAN_PT, abs=page_scale * SPAN_TOL_PT)


def test_viewport_expansion_and_unrelated_content_do_not_change_the_corner() -> None:
    base = _only_candidate(_run(_sheet()))
    expanded_gray = cv2.copyMakeBorder(_sheet(), 0, 120, 0, 200, cv2.BORDER_CONSTANT, value=255)
    expanded = _only_candidate(_run(expanded_gray))
    producer, published = _publish(_sheet(unrelated_opening=True))
    with_unrelated = _only_candidate(_detect(producer, published))

    _assert_same_corner(expanded, base)
    _assert_same_corner(with_unrelated, base)
    # The unrelated straight opening is still the ordinary detector's business.
    assert len(_existence_records(producer, published)) == 1


def test_split_frame_strokes_with_identical_pixels_are_invariant() -> None:
    split = _only_candidate(_run(_sheet(split_frames=True)))
    whole = _only_candidate(_run(_sheet()))
    assert _signature(split) == _signature(whole)


def test_replay_is_deterministic_with_stable_ids() -> None:
    payload = _pdf(_sheet())
    first = _detect(*_ingest(payload))
    second = _detect(*_ingest(payload))
    assert first.to_dict() == second.to_dict()
    assert first.candidates[0].candidate_id.startswith("raster_corner_framed_opening_shadow_")
    assert first.candidates[0].candidate_id != _only_candidate(
        _detect(*_ingest(_pdf(_sheet(), page_scale=1.5)))).candidate_id


def test_primitive_input_order_does_not_change_nominations() -> None:
    producer, published = _publish(_sheet(second_corner_post=True))
    png_bytes, _parent, _frame, dpi = producer.render_raster_opening_source_page(
        published.revision.revision_id, "1")
    gray = cv2.imdecode(np.frombuffer(png_bytes, dtype=np.uint8), cv2.IMREAD_GRAYSCALE)
    visibility = producer.authority()
    records = [
        visibility.resolve_raster_opening_primitive(_selector(published, observation_id)).observation
        for observation_id in published.raster_opening_primitive_observation_ids
    ]

    def summary(items):
        return sorted(
            (item["corner_px"], item["reason"] or "",
             tuple(sorted(key for selected in item["frames"] for key in selected)))
            for item in items)

    baseline, rejected = corner._nominate(gray, records, dpi=dpi, registration_scale=(1.0, 1.0))
    for seed in range(3):
        shuffled = list(records)
        random.Random(seed).shuffle(shuffled)
        items, shuffled_rejected = corner._nominate(
            gray, shuffled, dpi=dpi, registration_scale=(1.0, 1.0))
        assert summary(items) == summary(baseline)
        assert shuffled_rejected == rejected


def test_detection_does_not_mutate_the_producer_or_production_detection() -> None:
    producer, published = _publish(_sheet(unrelated_opening=True))
    before_snapshot = producer.published_snapshot_for_revision(published.revision.revision_id)
    before_records = _existence_records(producer, published)

    _detect(producer, published)
    _detect(producer, published)

    assert producer.published_snapshot_for_revision(published.revision.revision_id) is before_snapshot
    assert before_snapshot.raster_opening_primitive_observation_ids == (
        published.raster_opening_primitive_observation_ids)
    assert _existence_records(producer, published) == before_records


def test_unpublished_primitives_abstain() -> None:
    result = _run(_sheet(), augment=False)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes == (corner.CORNER_RASTER_PRIMITIVES_UNAVAILABLE,)
    assert result.nominations == ()


def test_rotated_native_page_abstains() -> None:
    result = _run(_sheet(), rotation=90)
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.reason_codes in {
        (corner.CORNER_ROTATED_RENDER_UNSUPPORTED,),
        (corner.CORNER_RASTER_PRIMITIVES_UNAVAILABLE,),
    }
    assert result.nominations == ()


def test_caller_cannot_inject_a_producer_or_grant_authority() -> None:
    with pytest.raises(TypeError):
        corner.detect_raster_corner_framed_openings_shadow(
            object(), revision_id="r", page_id="1")
    candidate = _only_candidate(_run(_sheet()))
    for field in ("takeoff_eligible", "physical_opening_authority", "deduction_authority"):
        with pytest.raises(ValueError):
            replace(candidate, **{field: True})
    with pytest.raises(ValueError):
        replace(candidate, shadow_only=False)
    with pytest.raises(ValueError):
        replace(candidate, first_remaining_gate=corner.CORNER_FRAME_DISCONNECTED)


def test_private_diagnostic_prints_counts_only_and_refuses_repo_output(tmp_path) -> None:
    from tools import diag_cursor_corner_framed_opening_shadow as diag

    report = diag.run_corner_shadow(_pdf(_sheet()), pages=(1,))
    summary = diag.sanitized_summary(report)
    encoded = repr(summary)
    assert summary["pages"][0]["candidate_count"] == 1
    assert "_pt" not in encoded and "observation" not in encoded and "candidate_id" not in encoded
    assert report["pages"][0]["nominations"][0]["corner_box_pt"]

    source = tmp_path / "private.pdf"
    source.write_bytes(_pdf(_sheet()))
    with pytest.raises(ValueError):
        diag.main(["--pdf", str(source), "--page", "1",
                   "--output", str(ROOT / "corner-shadow-should-not-exist.json")])
    assert not (ROOT / "corner-shadow-should-not-exist.json").exists()


def test_no_production_module_imports_the_shadow_detector() -> None:
    pattern = re.compile(r"\bpb_raster_corner_framed_opening_shadow\b")
    allowed = {
        ROOT / "pb_raster_corner_framed_opening_shadow.py",
        ROOT / "tools" / "diag_cursor_corner_framed_opening_shadow.py",
    }
    importers = [
        path.relative_to(ROOT).as_posix()
        for path in [*ROOT.glob("*.py"), *ROOT.glob("tools/*.py"), *ROOT.glob("app/**/*.py")]
        if path not in allowed and pattern.search(path.read_text(encoding="utf-8", errors="ignore"))
    ]
    assert importers == []
