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
