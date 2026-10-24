"""Thirty printed answers: a second different value is not selected."""
from __future__ import annotations

from pb_context_floorarea_v1224 import _area_value, floor_location
from pb_contextual_wd_card_evidence import _quantity_candidates
from pb_elevation_profile_v136 import solve_height_from_text
from pb_explicit_item_count_extractor import _specific_tag
from pb_opening_tag_normalization import normalize_opening_tag
from pb_premier_takeoff_v1225 import _level
from pb_production_3d_adapter_legacy import _normalise_level_identity, _strong_floor_level_claim
from pb_project_scope_v142 import normalise_group
from pb_secondary_area_support_evidence import _support_kind, _zone_type
from pb_takeoff_accuracy_v125 import level_of, scope_of


def test_takeoff_level_keeps_one_storey_and_abstains_on_two() -> None:
    assert level_of("Level 7 Floor Plan") == "Level 7"
    assert level_of("Lower Ground") == "Lower Ground"
    assert level_of("first floor") == "Level 1"
    assert level_of("Level 1 and Level 2") == "Unassigned"
    assert level_of("first floor and second floor") == "Unassigned"
    assert level_of("Basement 1 and Ground Floor") == "Unassigned"


def test_takeoff_scope_omits_a_pattern_printed_twice() -> None:
    assert "Unit 4" in scope_of("Unit 4 Level 2")
    assert "Unit" not in scope_of("Unit 4 and Unit 9 Level 2")
    assert scope_of("Block A and Block B") == "Unassigned"


def test_premier_level_does_not_read_background_as_ground() -> None:
    assert _level("background notes") == "Unassigned"
    assert _level("Ground Floor") == "Ground"
    assert _level("Basement 2") == "Basement 2"
    assert _level("Unit 501") == "Level 5"
    assert _level("Unit 501 and Unit 601") == "Unassigned"
    assert _level("Level 1 and Level 2") == "Unassigned"


def test_production_level_identity_abstains_on_two_storeys() -> None:
    assert _normalise_level_identity("Level 1") == "level_1"
    assert _normalise_level_identity("Level 0") == "ground"
    assert _normalise_level_identity("Ground Floor") == "ground"
    assert _normalise_level_identity("Basement 1") == "basement_1"
    assert _normalise_level_identity("Level 1 and Level 2") == ""
    assert _normalise_level_identity("Ground and Level 1") == ""


def test_disagreeing_level_fields_are_not_the_first_field() -> None:
    assert _strong_floor_level_claim({"level": "Level 4"}) == "Level 4"
    assert _strong_floor_level_claim({"level": "Level 4", "level_name": "Level 4"}) == "Level 4"
    assert _strong_floor_level_claim({"level": "Level 1", "level_name": "Level 2"}) is None


def test_secondary_zone_and_support_keep_one_noun() -> None:
    assert _zone_type("covered verandah") == "verandah"
    assert _zone_type("porch") == "porch"
    assert _zone_type("verandah and porch") is None
    assert _zone_type("alfresco and patio") is None
    assert _support_kind("100mm steel column") == "column"
    assert _support_kind("100mm steel columns and piers") is None


def test_scope_group_abstains_when_two_groups_are_printed() -> None:
    assert normalise_group("Block A") == "Block A"
    assert normalise_group("Block A Block A") == "Block A"
    assert normalise_group("Block A and Block B") == ""


def test_floor_location_and_area_keep_one_printed_value() -> None:
    assert floor_location({"page_label": "A101", "extracted_text": "LEVEL 3"}) == "Level 3"
    assert floor_location({"page_label": "A101", "extracted_text": "GROUND FLOOR"}) == "Ground Floor"
    assert floor_location({"page_label": "A101", "extracted_text": "LEVEL 1 LEVEL 2"}).startswith("Internal Floor")
    assert _area_value("internal area 84.6 m2") == 84.6
    assert _area_value("84.6 m2 and 84.6 m2") == 84.6
    assert _area_value("84.6 m2 or 91.2 m2") == 0.0


def test_two_storey_heights_are_not_the_one_nearest_three_metres() -> None:
    one = solve_height_from_text("GROUND RL 12.400\nFCL RL 15.100")
    two = solve_height_from_text("RL 10.000 RL 12.700 RL 16.000")
    dimension = solve_height_from_text("CH 2700")
    assert one["confidence"] == "Verified"
    assert one["height_m"] == 2.7
    assert two["confidence"] == "Review"
    assert dimension["height_m"] == 2.7
    assert dimension["confidence"] == "High"


def test_one_opening_tag_is_kept_and_two_tags_abstain() -> None:
    assert normalize_opening_tag("Door D01 820x2040").tag == "D1"
    assert normalize_opening_tag("W1 W1").tag == "W1"
    assert normalize_opening_tag("D01 or W01") is None
    assert _specific_tag("windows", "W1 and W1") == "W1"
    assert _specific_tag("windows", "W1 or W2") == "windows"


def test_two_printed_heights_and_two_card_quantities_abstain() -> None:
    two_dims = solve_height_from_text("CH 2700 and CH 3000")
    assert two_dims["confidence"] == "Review"
    one = _quantity_candidates([("Overall Quantity: 23", (0.0, 0.0, 10.0, 10.0), 0)])
    two = _quantity_candidates([("Overall Quantity: 23 or 31", (0.0, 0.0, 10.0, 10.0), 0)])
    assert one == [(23.0, (0.0, 0.0, 10.0, 10.0))]
    assert two == []
