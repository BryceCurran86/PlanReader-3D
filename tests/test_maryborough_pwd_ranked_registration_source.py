"""PWD source registration must own the doorway position, never a page-shift constant."""
from __future__ import annotations

from pb_source_cross_view_floor_correspondence_shadow import (
    EvidenceResolutionStatus,
    authenticate_maryborough_pwd_cross_sheet_correspondence,
)
import pb_source_cross_view_floor_correspondence_shadow as producer


class _Page:
    def get_drawings(self):
        return ({"items": ()},)

    def get_text(self, _mode):
        return ()


class _Document:
    page_count = 28

    def __getitem__(self, index):
        assert 0 <= index < self.page_count
        return _Page()


def _configure(monkeypatch, ranked):
    segments = (
        {"x1": 20.0, "y1": 40.0, "x2": 120.0, "y2": 40.0},
        {"x1": 20.0, "y1": 40.0, "x2": 20.0, "y2": 140.0},
    )
    monkeypatch.setattr(producer, "_extract_segments_from_drawings",
                        lambda _drawings: segments)
    monkeypatch.setattr(producer, "_extract_marks_from_page",
                        lambda _page: ())
    monkeypatch.setattr(producer, "_authenticate_d15_door_schedule_row",
                        lambda *_args, **_kwargs: {"width_mm": 920.0})
    source_box = (110.0, 200.0, 220.0, 378.5)
    monkeypatch.setattr(producer, "_authenticate_p11_pwd_dimension_witness_box",
                        lambda *_args, **_kwargs: source_box)
    monkeypatch.setattr(producer, "rank_registrations",
                        lambda *_args, **_kwargs: ranked)
    monkeypatch.setattr(producer, "null_support",
                        lambda *_args, **_kwargs: {"max": 1.0})
    return source_box


def _call():
    return authenticate_maryborough_pwd_cross_sheet_correspondence(
        document_id="source-neutral-document",
        revision_id="source-neutral-revision",
        source_sha256="f" * 64,
        snapshot_id="source-neutral-snapshot",
        canonical_floor_id="source-neutral-floor",
        physical_room_id="source-neutral-room",
        source_room_face_record_id="source-neutral-face",
        registration_translation=(-999.0, 888.0),  # deliberately forged prior guess
        doc=_Document(),  # deliberately unauthenticated: NEVER commercial
    )


def test_painted_ranked_translation_locates_target_door_not_caller_offset(monkeypatch):
    ranked = [{
        "orientation": "identity", "scale": 1.0,
        "dx": 43.75, "dy": -12.5, "min_support_pt": 100.0,
    }]
    box = _configure(monkeypatch, ranked)
    captured = []

    def check_door(**kwargs):
        captured.append(kwargs)
        return None  # deliberately missing physical proof, so ABSTAIN

    monkeypatch.setattr(producer, "_authenticate_d13_physical_doorway_boundary",
                        check_door)
    result = _call()
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert not result.commercial_projection_allowed
    assert len(captured) == 1
    assert captured[0]["box_sup"] == box
    assert captured[0]["box_tgt"] == (
        box[0] + ranked[0]["dx"], box[1] + ranked[0]["dy"],
        box[2] + ranked[0]["dx"], box[3] + ranked[0]["dy"],
    )


def test_competing_source_transforms_do_not_reach_physical_door(monkeypatch):
    ranked = [
        {"orientation": "identity", "scale": 1.0,
         "dx": 43.75, "dy": -12.5, "min_support_pt": 100.0},
        {"orientation": "identity", "scale": 1.0,
         "dx": -31.0, "dy": 21.0, "min_support_pt": 90.0},
    ]
    _configure(monkeypatch, ranked)
    called = []

    def no_door(**kwargs):
        called.append(kwargs)
        raise AssertionError("ambiguous registration must not reach door gate")

    monkeypatch.setattr(producer, "_authenticate_d13_physical_doorway_boundary",
                        no_door)
    result = _call()
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert producer.REGISTRATION_NOT_UNIQUE in result.reason_codes
    assert not called
    assert not result.commercial_projection_allowed
