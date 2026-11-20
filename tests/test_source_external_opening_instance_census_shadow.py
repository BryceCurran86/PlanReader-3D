"""Unmatched external opening census skips already-verified hosts."""
from __future__ import annotations

from dataclasses import dataclass

from pb_source_external_opening_instance_census_shadow import (
    census_unmatched_external_opening_instances,
)


@dataclass(frozen=True)
class _Swing:
    first_host_path_id: int = 1
    second_host_path_id: int = 2
    jamb_cap_path_ids: tuple[int, int] = (3, 4)
    bounds_pdf_pts: tuple[float, float, float, float] = (10.0, 20.0, 30.0, 40.0)


@dataclass(frozen=True)
class _Slider:
    first_host_path_id: int = 10
    second_host_path_id: int = 11
    jamb_cap_path_ids: tuple[int, int] = (12, 13)
    bounds_pdf_pts: tuple[float, float, float, float] = (50.0, 20.0, 80.0, 40.0)
    label_text: str = "STACKER"


def test_skips_verified_hosts_and_keeps_unmatched(monkeypatch):
    monkeypatch.setattr(
        "pb_source_external_opening_instance_census_shadow.detect_exterior_swing_door_footprint_bridges",
        lambda *a, **k: (_Swing(),),
    )
    monkeypatch.setattr(
        "pb_source_external_opening_instance_census_shadow.detect_exterior_sliding_door_footprint_bridges",
        lambda *a, **k: (_Slider(),),
    )
    monkeypatch.setattr(
        "pb_source_external_opening_instance_census_shadow.detect_exterior_window_footprint_bridges",
        lambda *a, **k: (),
    )
    census = census_unmatched_external_opening_instances(
        (), (), page_index=2, already_verified_host_keys=(frozenset({1, 2}),),
    )
    assert census.skipped_verified_count == 1
    assert census.unmatched_swing == ()
    assert len(census.unmatched_stacker_or_slider) == 1
    assert census.unmatched_stacker_or_slider[0].kind == "external_stacker_door"
    assert census.to_dict()["commercial_publishable"] is False
