"""Original PDF page identity must survive native opening preflight.

A typed aperture without its original page cannot be matched to a room's
source-owned boundary. These tests do not authorize any wall or floor area.
"""
from __future__ import annotations

import pytest
import pb_new_exterior_wall_preflight as preflight


def test_native_page_index_forwarded_to_all_existing_aperture_detectors(monkeypatch):
    called = {}
    for name in (
        "detect_exterior_window_footprint_bridges",
        "detect_exterior_garage_door_footprint_bridges",
        "detect_exterior_swing_door_footprint_bridges",
        "detect_exterior_sliding_door_footprint_bridges",
        "detect_source_neutral_wall_seams",
    ):
        def capture(*args, _name=name, **kwargs):
            called[_name] = kwargs.get("page_index")
            return ()
        monkeypatch.setattr(preflight, name, capture)

    report = preflight.attempt_source_native_outer_wall_first(
        [], source_ink_already_scoped=True,
        source_words=[(0, 0, 9, 9, "ASW")],
        source_page_index=2,
    )
    assert set(called) == {
        "detect_exterior_window_footprint_bridges",
        "detect_exterior_garage_door_footprint_bridges",
        "detect_exterior_swing_door_footprint_bridges",
        "detect_exterior_sliding_door_footprint_bridges",
        "detect_source_neutral_wall_seams",
    }
    assert set(called.values()) == {2}
    assert report.measurement_authorized is False


def test_page_index_must_be_exact_valid_pdf_index():
    for bad in (-2, True, 2.5, "2"):
        with pytest.raises(ValueError, match="source_page_index_invalid"):
            preflight.attempt_source_native_outer_wall_first(
                [], source_ink_already_scoped=True, source_page_index=bad,
            )


def test_legacy_unscoped_diagnostic_stays_unmatched_to_real_page(monkeypatch):
    called = {}
    def window_recorder(*args, **kwargs):
        called["page_index"] = kwargs.get("page_index")
        return ()
    monkeypatch.setattr(
        preflight, "detect_exterior_window_footprint_bridges",
        window_recorder,
    )
    report = preflight.attempt_source_native_outer_wall_first(
        [], source_ink_already_scoped=True,
        source_words=[(0, 0, 9, 9, "ASW")],
    )
    assert called["page_index"] == -1
    assert report.measurement_authorized is False
