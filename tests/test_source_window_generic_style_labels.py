"""Generic window type styles require genuine existing native wall & markers."""
import pytest
from pb_source_window_footprint_continuity import detect_exterior_window_footprint_bridges
from tests.test_source_window_footprint_continuity import _window_setup


@pytest.mark.parametrize("window_style", [
    "AAW","ADH","ADHW","ASHW","AFW","ALW","ASW","AW","WIN","WINDOW",
    "FGW","SGW","W1","W-09",
])
def test_explicit_generic_window_code_preserves_existing_native_host_and_markers(window_style):
    drawings, _ = _window_setup()
    bridged=detect_exterior_window_footprint_bridges(
        drawings,[(13,9,19,13,window_style)],page_index=2,
    )
    assert len(bridged)==1
    assert bridged[0].label_text == window_style
    assert (bridged[0].left_host_path_id,bridged[0].right_host_path_id)==(0,1)
    assert bridged[0].physical_wall_authenticated is False
    assert bridged[0].measurement_authorized is False


@pytest.mark.parametrize("number",["0","2","04","18","70","90","999","2400","12-12"])
def test_bare_room_grid_or_dimension_codes_remain_rejected(number):
    drawings, _=_window_setup()
    assert detect_exterior_window_footprint_bridges(
        drawings,[(13,9,19,13,number)],page_index=2,
    )==()


@pytest.mark.parametrize("door",["ASD","ASSD","VSD","CS","D1","DOOR","STACKER"])
def test_sliding_and_hinged_door_codes_never_become_windows(door):
    drawings, _=_window_setup()
    assert detect_exterior_window_footprint_bridges(
        drawings,[(13,9,19,13,door)],page_index=2,
    )==()


@pytest.mark.parametrize("style",["AAW","ADHW","AFW","ALW"])
def test_new_window_styles_still_need_real_source_wall_and_two_markers(style):
    drawings, _=_window_setup()
    assert detect_exterior_window_footprint_bridges(
        drawings[:-1],[(13,9,19,13,style)],page_index=2,
    )==()
    wrong_layer=[dict(x,layer="Furniture_Annotation") for x in drawings]
    assert detect_exterior_window_footprint_bridges(
        wrong_layer,[(13,9,19,13,style)],page_index=2,
    )==()
