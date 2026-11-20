"""Dimension and room-key numerals cannot be native exterior-window labels."""
import pytest
from pb_source_window_footprint_continuity import (
    detect_exterior_window_footprint_bridges,
)
from tests.test_source_window_footprint_continuity import _window_setup


@pytest.mark.parametrize("number", ["2","04","18","21","70","90","105","3"])
def test_bare_pdf_dimension_or_legend_number_is_not_window_type(number):
    drawings, _ = _window_setup()
    result=detect_exterior_window_footprint_bridges(
        drawings,[(13,9,19,13,number)],page_index=2,
    )
    assert result == ()


@pytest.mark.parametrize("label", ["ASW","AW","WIN","WINDOW","W1","W-01"])
def test_explicit_source_window_type_still_closes_existing_wall_gap(label):
    drawings, _ = _window_setup()
    result=detect_exterior_window_footprint_bridges(
        drawings,[(13,9,19,13,label)],page_index=2,
    )
    assert len(result)==1
    assert result[0].label_text==label
    assert result[0].physical_wall_authenticated is False
    assert result[0].measurement_authorized is False


def test_numeric_annotation_competes_neither_as_window_nor_as_door():
    drawings, words = _window_setup()
    result=detect_exterior_window_footprint_bridges(
        drawings, words+[(13,9,19,13,"90")], page_index=2,
    )
    assert len(result)==1
    assert result[0].label_text.lower()=="asw"


def test_bare_room_key_cannot_close_exterior_contour_without_window_label():
    drawings, _ = _window_setup()
    words=[(13,9,19,13,"04"),(13,9,19,13,"70")]
    result=detect_exterior_window_footprint_bridges(drawings,words)
    assert result == ()
