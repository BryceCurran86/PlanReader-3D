"""Source-neutral native user correction handoff tests."""
from dataclasses import replace
import hashlib

import fitz
import pytest

from pb_guided_plan_review import ReviewScope
from pb_guided_plan_review_native import build_native_review_packet, changed_review_stages
from pb_native_page_frame import NativePageFrameUnresolved


def _source(tmp_path, rotation):
    path = tmp_path / f"sample-{rotation}.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=400, height=300)
        page.draw_rect(fitz.Rect(30, 40, 350, 260))
        page.set_rotation(rotation)
        doc.save(path)
    with fitz.open(path) as doc:
        page = doc[0]
        zoom = min(1.2, 1800 / max(page.rect.width, page.rect.height))
        image = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom), alpha=False).tobytes("png")
    scope = ReviewScope(1, 2, 1, hashlib.sha256(path.read_bytes()).hexdigest(),
                        hashlib.sha256(image).hexdigest())
    return path, image, scope


def _draft(revision=1, shapes=None, answers=None):
    return {"revision": revision, "shapes": shapes if shapes is not None else [
        {"id": "wall1", "kind": "line", "category": "external_wall",
         "points": [[25, 25], [50, 50]]}
    ], "answers": answers or {}}


@pytest.mark.parametrize("rotation,expected", [
    (0, [[100,75],[200,150]]),
    (90, [[100,225],[200,150]]),
])
def test_exact_native_coordinate_handoff(tmp_path, rotation, expected):
    path, image, scope = _source(tmp_path, rotation)
    packet = build_native_review_packet(scope=scope, pdf_path=path,
                                       image_bytes=image, saved=_draft())
    for actual, target in zip(packet["corrections"][0]["native_points_pdf_pts"], expected):
        assert actual == pytest.approx(target)
    assert packet["automatic_source_verified"] is False
    assert packet["commercial_projection_allowed"] is False
    assert packet["frozen_benchmark_allowed"] is False
    assert packet["topology_recalculated"] is False
    assert "topology" in packet["affected_stage_candidates"]
    assert packet == build_native_review_packet(scope=scope, pdf_path=path,
                                                image_bytes=image, saved=_draft())


def test_changed_source_or_image_refused(tmp_path):
    path, image, scope = _source(tmp_path, 0)
    with pytest.raises(ValueError, match="Review image changed"):
        build_native_review_packet(scope=scope, pdf_path=path,
                                   image_bytes=image + b"x", saved=_draft())
    with pytest.raises(ValueError, match="Original PDF changed"):
        build_native_review_packet(scope=replace(scope, source_sha256="a"*64),
                                   pdf_path=path, image_bytes=image, saved=_draft())


def test_unsupported_rotation_refused(tmp_path):
    path, image, scope = _source(tmp_path, 180)
    with pytest.raises(NativePageFrameUnresolved):
        build_native_review_packet(scope=scope, pdf_path=path,
                                   image_bytes=image, saved=_draft())


def test_deleting_correction_invalidates_old_geometry(tmp_path):
    path, image, scope = _source(tmp_path, 0)
    def build(saved):
        return build_native_review_packet(scope=scope, pdf_path=path,
                                          image_bytes=image, saved=saved)
    old = build(_draft())
    new = build(_draft(revision=2, shapes=[]))
    assert new["affected_stage_candidates"] == []
    assert "topology" in changed_review_stages(old, new)
    assert "net_wall_areas" in changed_review_stages(old, new)
    assert changed_review_stages(new, new) == []
    with pytest.raises(ValueError, match="older"):
        changed_review_stages(new, old)
    new["automatic_source_verified"] = True
    with pytest.raises(ValueError, match="Invalid review packet"):
        changed_review_stages(old, new)


def test_finish_only_answer_does_not_invalidate_topology(tmp_path):
    path, image, scope = _source(tmp_path, 0)
    old = build_native_review_packet(scope=scope, pdf_path=path, image_bytes=image,
                                    saved=_draft())
    current = build_native_review_packet(scope=scope, pdf_path=path, image_bytes=image,
        saved=_draft(revision=2, answers={"finishes": {
            "decision": "correction_recorded", "note": "Finish schedule", "dimension_mm": None}}))
    assert changed_review_stages(old, current) == ["finishes", "costing", "model"]


def test_false_canonical_provenance_refused(tmp_path):
    path, image, scope = _source(tmp_path, 0)
    with pytest.raises(ValueError, match="Canonical preview provenance"):
        build_native_review_packet(scope=scope, pdf_path=path, image_bytes=image,
                                   saved=_draft(), canonical_report={
            "source_sha256": scope.source_sha256, "page_index": 0, "producer": "other"})


def test_saved_selected_dimension_reaches_existing_scale_request(tmp_path):
    from pb_guided_plan_review import normalise_answer
    from pb_guided_review_source_questions import (
        build_review_to_issuer_handoff, build_user_assisted_scale_issuer_request,
    )
    path, image, scope = _source(tmp_path, 0)
    marks = [{"id": "dim1", "category": "dimension_witness", "kind": "line",
              "points": [[25,25], [50,25]]}]
    answers = {"scale": normalise_answer("scale", "correction_recorded", "Figured dimension",
        2000, correction_id="dim1", witness_points=marks[0]["points"])}
    packet = build_native_review_packet(scope=scope, pdf_path=path, image_bytes=image,
        saved=_draft(shapes=marks, answers=answers))
    request = build_user_assisted_scale_issuer_request(
        handoff=build_review_to_issuer_handoff(native_review_packet=packet))
    assert request.status == "USER_ASSISTED_SCALE_INPUT_READY"
    assert request.figured_mm == 2000
    assert request.span_pdf_pts == pytest.approx(100)
    assert request.implied_mm_per_pt == pytest.approx(20)
    assert request.commercial_projection_allowed is False
    assert request.automatic_source_verified is False
    assert request.viewport_id is None
    unbound = {"scale": normalise_answer("scale", "correction_recorded", "Unbound note", 2000)}
    packet2 = build_native_review_packet(scope=scope, pdf_path=path, image_bytes=image,
        saved=_draft(revision=2, shapes=marks, answers=unbound))
    request2 = build_user_assisted_scale_issuer_request(
        handoff=build_review_to_issuer_handoff(native_review_packet=packet2))
    assert request2.status == "ABSTAINED"
    assert "scale" in changed_review_stages(packet, packet2)
    marks[0]["points"][1] = [60,25]
    with pytest.raises(ValueError, match="Scale witness changed"):
        build_native_review_packet(scope=scope, pdf_path=path, image_bytes=image,
            saved=_draft(revision=3, shapes=marks, answers=answers))
