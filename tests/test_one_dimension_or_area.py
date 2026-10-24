"""One printed dimension or area is kept. Two different values abstain."""

from pb_auto_geometry_v1219 import (
    extract_substrate_area_candidates,
    extract_unit_area_candidates,
)
from pb_opening_schedule_v171 import parse_dimension, parse_single_dimension
from pb_unit_floor_area_textfix_v1221 import extract_unit_area_candidates as textfix_areas
from pb_unit_floor_area_v1221 import extract_unit_area_candidates as wider_areas


def test_one_length_is_kept_and_two_lengths_abstain():
    assert parse_single_dimension("820mm") == 820
    assert parse_single_dimension("820mm and 820mm") == 820
    assert parse_single_dimension("820mm or 900mm") is None
    assert parse_single_dimension("1m or 2m") is None


def test_one_opening_pair_is_kept_and_two_pairs_abstain():
    assert parse_dimension("820 x 2040") == (820, 2040)
    assert parse_dimension("FRL 240/240/240 920x2040") == (920, 2040)
    assert parse_dimension("820 x 2040 or 920 x 2040") == (None, None)
    assert parse_dimension("820/2040 or 920/2040") == (None, None)
    assert parse_dimension("820mm 2040mm 900mm") == (None, None)


def test_one_documented_area_is_kept_and_two_areas_abstain():
    rows = extract_unit_area_candidates("UNIT 101\nInternal floor area 84.6 m²")
    assert rows[0]["area_m2"] == 84.6
    repeated = extract_unit_area_candidates("UNIT 101 84.6 m2\n84.6 m²")
    assert repeated[0]["area_m2"] == 84.6
    assert extract_unit_area_candidates("UNIT 101\n84.6 m2 or 91.2 m2") == []
    assert textfix_areas("UNIT 501\nTYPE A\n84.6 m²\n91.2 m2") == []
    assert wider_areas("UNIT 501\n84.6 m² or 91.2 m2") == []


def test_one_substrate_area_is_kept_and_two_areas_abstain():
    rows = extract_substrate_area_candidates("EC1 Lineaboard Cladding 145.8 m2")
    assert rows[0]["area_m2"] == 145.8
    assert extract_substrate_area_candidates("EC1 Lineaboard Cladding 145.8 m2 and 88.2 m2") == []
