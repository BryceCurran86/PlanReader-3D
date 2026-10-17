"""A drawing title names one view, or it names none."""

from pb_drawing_evidence_binding import DrawingViewClassifier, DrawingViewType


def test_one_printed_view_is_kept():
    assert DrawingViewClassifier.classify_text("GROUND FLOOR PLAN") is DrawingViewType.FLOOR_PLAN
    assert (
        DrawingViewClassifier.classify_text("REFLECTED CEILING PLAN LEVEL 1")
        is DrawingViewType.REFLECTED_CEILING_PLAN
    )
    assert DrawingViewClassifier.classify_text("DOOR SCHEDULE") is DrawingViewType.SCHEDULE
    assert DrawingViewClassifier.classify_text("NORTH ELEVATION") is DrawingViewType.ELEVATION


def test_two_printed_views_abstain_in_either_order():
    assert (
        DrawingViewClassifier.classify_text("FLOOR PLAN AND NORTH ELEVATION")
        is DrawingViewType.UNKNOWN
    )
    assert (
        DrawingViewClassifier.classify_text("NORTH ELEVATION AND FLOOR PLAN")
        is DrawingViewType.UNKNOWN
    )


def test_a_reference_line_does_not_retype_the_sheet():
    text = "NORTH ELEVATION\nREFER FLOOR PLAN"
    assert DrawingViewClassifier.classify_text(text) is DrawingViewType.ELEVATION


def test_a_reference_alone_is_not_a_view():
    assert DrawingViewClassifier.classify_text("REFER FLOOR PLAN") is DrawingViewType.UNKNOWN
    assert DrawingViewClassifier.classify_text("SEE DETAIL A") is DrawingViewType.UNKNOWN
