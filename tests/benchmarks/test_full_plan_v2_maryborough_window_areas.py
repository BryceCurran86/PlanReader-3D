from __future__ import annotations

import json
from pathlib import Path

PROJECT = (
    Path(__file__).resolve().parents[2]
    / "benchmarks"
    / "frozen_holdout"
    / "full_plan_v2"
    / "projects"
    / "au_qld_maryborough_service_station"
)


def _json(name: str):
    return json.loads((PROJECT / name).read_text(encoding="utf-8"))


EXPECTED = {
    "W01": (3600, 1900, 6.84),
    "W02": (4100, 1900, 7.79),
    "W05": (7585, 1900, 14.4115),
    "W06": (700, 2100, 1.47),
}


def test_window_area_truth_is_atomic_and_family_scoped() -> None:
    objects = _json("object_universe.json")
    windows = {item["source_tag"]: item for item in objects["windows"]}

    assert set(objects["window_area_source_closed_ids"]) == set(EXPECTED)
    assert set(objects["window_area_unresolved_ids"]) == {"W03", "W04"}
    assert objects["window_area_universe_complete"] is False

    for tag, (width, height, area) in EXPECTED.items():
        item = windows[tag]
        assert item["width_mm"] == width
        assert item["height_mm"] == height
        assert item["gross_frame_opening_area_m2"] == area
        assert item["area_status"] == "VERIFIED_GROSS_FRAME_OPENING"
        assert item["area_semantics"].startswith("nominal gross framed opening area")

    assert windows["W03"]["area_status"] == "UNRESOLVED"
    assert windows["W04"]["area_status"] == "UNRESOLVED"


def test_reference_takeoff_keeps_one_area_item_per_verified_window() -> None:
    reference = _json("reference_takeoff.json")
    area_items = {
        item["expected_object_refs"][0]: item
        for item in reference["items"]
        if item["item_id"].startswith("maryborough-window-")
        and item["item_id"].endswith("-gross-frame-opening-area")
    }

    assert set(area_items) == {f"maryborough:window:{tag}" for tag in EXPECTED}
    assert sum(item["expected_quantity"] for item in area_items.values()) == 30.5115

    for tag, (_, _, area) in EXPECTED.items():
        item = area_items[f"maryborough:window:{tag}"]
        assert item["expected_quantity"] == area
        assert item["unit"] == "m2"
        assert item["denominator_eligible"] is True
        assert item["verification_status"] == "VERIFIED"


def test_unresolved_window_areas_stay_explicit() -> None:
    unresolved = _json("unresolved_items.json")
    family = next(
        item for item in unresolved["unresolved_families"]
        if item["family"] == "window_areas"
    )
    assert family["status"] == "PARTIAL"
    assert "W03" in family["reason"]
    assert "W04" in family["reason"]

    reference = _json("reference_takeoff.json")
    reconciliation = reference["window_universe_reconciliation"]
    assert reconciliation["area_status"] == "PARTIAL_SOURCE_CLOSED"
    assert reconciliation["unresolved_area_ids"] == ["W03", "W04"]
    assert reconciliation["source_closed_gross_frame_opening_area_m2"] == 30.5115
