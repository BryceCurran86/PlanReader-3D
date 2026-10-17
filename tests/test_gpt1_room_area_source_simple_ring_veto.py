"""A shoelace number is not a physical-room ring authority."""
from pb_room_area_quantity import _polygon_area

RECT = ((0.,0.),(10.,0.),(10.,5.),(0.,5.))
L = ((0.,0.),(9.,0.),(9.,3.),(3.,3.),(3.,7.),(0.,7.))
CROSSING_POSITIVE = ((0.,0.),(8.,0.),(0.,8.),(8.,8.),(0.,12.))


def test_source_simple_rectangular_room_area_is_preserved():
    assert _polygon_area(RECT) == 50.0
    assert _polygon_area(RECT + (RECT[0],)) == 50.0
    assert _polygon_area(tuple(reversed(RECT))) == 50.0


def test_concave_genuine_room_faces_are_still_measurable():
    assert _polygon_area(L) == 39.0
    assert _polygon_area(tuple((x + 147, y - 26) for x, y in L)) == 39.0
    assert _polygon_area(tuple((-y, x) for x, y in L)) == 39.0


def test_positive_shoelace_but_self_crossing_ink_is_not_a_room():
    assert _polygon_area(CROSSING_POSITIVE) == 0.0


def test_bowtie_and_backtracking_ink_do_not_mint_room_area():
    assert _polygon_area(((0,0),(10,10),(0,10),(10,0))) == 0.0
    assert _polygon_area(((0,0),(5,0),(5,5),(3,3),(5,5),(0,5))) == 0.0


def test_nonfinite_and_boolean_points_stay_rejected():
    assert _polygon_area(((0,0),(1,float("nan")),(1,1))) == 0.0
    assert _polygon_area(((0,0),(True,0),(1,1),(0,1))) == 0.0


def test_geos_extreme_original_pdf_points_do_not_crash_or_create_metric_area():
    # A finite PDF coordinate is not enough if its polygon arithmetic is
    # unrepresentable by GEOS/shoelace; this remains a negative authority.
    huge = 1.0e308
    invalid = ((0., 0.), (huge, huge), (huge, 0.), (0., huge))
    assert _polygon_area(invalid) == 0.0
