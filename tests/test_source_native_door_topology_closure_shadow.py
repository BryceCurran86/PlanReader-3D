"""Topology-only CS/sliding closures never become physical walls."""
from __future__ import annotations

from pb_source_native_cavity_slider_jamb_shadow import NativeCavitySliderThreshold
from pb_source_native_door_topology_closure_shadow import (
    build_source_native_door_topology_closures,
)


def test_conflicting_cs_same_gap_abstains_duplicate_and_keeps_no_wall_authority(monkeypatch):
    first = NativeCavitySliderThreshold(
        cs_word_index=1, width_word_index=0, printed_width_mm=720,
        horizontal=True, band_pdf_pts=(100.0, 103.0),
        clear_interval_pdf_pts=(40.0, 63.0), host_path_ids=(0, 1),
        jamb_path_ids=(2, 3), leaf_path_id=4, page_index=2,
    )
    second = NativeCavitySliderThreshold(
        cs_word_index=11, width_word_index=10, printed_width_mm=870,
        horizontal=True, band_pdf_pts=(100.0, 103.0),
        clear_interval_pdf_pts=(40.0, 63.0), host_path_ids=(10, 11),
        jamb_path_ids=(12, 13), leaf_path_id=14, page_index=2,
    )
    monkeypatch.setattr(
        "pb_source_native_door_topology_closure_shadow.match_source_native_cavity_sliders",
        lambda *a, **k: (first, second),
    )
    monkeypatch.setattr(
        "pb_source_native_door_topology_closure_shadow.detect_exterior_sliding_door_footprint_bridges",
        lambda *a, **k: (),
    )
    census = build_source_native_door_topology_closures((), (), page_index=2)
    assert census.duplicate_cavity_gap_abstained == 1
    assert census.cavity_slider_closures == ()
    assert census.physical_wall_authenticated is False
    assert census.to_dict()["commercial_publishable"] is False


def test_unique_cs_receipt_is_topology_only_not_wall(monkeypatch):
    receipt = NativeCavitySliderThreshold(
        cs_word_index=1, width_word_index=0, printed_width_mm=720,
        horizontal=True, band_pdf_pts=(100.0, 103.0),
        clear_interval_pdf_pts=(40.0, 63.0), host_path_ids=(0, 1),
        jamb_path_ids=(2, 3), leaf_path_id=4, page_index=2,
    )
    monkeypatch.setattr(
        "pb_source_native_door_topology_closure_shadow.match_source_native_cavity_sliders",
        lambda *a, **k: (receipt,),
    )
    monkeypatch.setattr(
        "pb_source_native_door_topology_closure_shadow.detect_exterior_sliding_door_footprint_bridges",
        lambda *a, **k: (),
    )
    census = build_source_native_door_topology_closures((), (), page_index=2)
    assert census.status == "CANDIDATE"
    assert len(census.cavity_slider_closures) == 1
    closure = census.cavity_slider_closures[0]
    assert closure.kind == "topology_only_cavity_slider"
    assert closure.topology_only is True
    assert closure.physical_wall_authenticated is False
    assert closure.to_dict()["doorway_is_not_physical_wall"] is True
