from __future__ import annotations

from pb_opening_label_dimension_authority import (
    _GapSpan,
    _TrustedTextLine,
    _label_matches_gap,
)


def _line(bbox):
    return _TrustedTextLine(
        observation_ids=("text:1",),
        text="0906 SGW obs",
        bbox=tuple(float(value) for value in bbox),
    )


def test_label_bbox_overlap_owns_gap_even_when_center_is_just_outside() -> None:
    gap = _GapSpan(
        axis=(1.0, 0.0),
        normal=(0.0, 1.0),
        along_min=100.0,
        along_max=140.0,
        cross_center=55.0,
        cross_spread=10.0,
    )
    label = _line((138.0, 52.0, 143.6, 58.0))
    assert (label.bbox[0] + label.bbox[2]) / 2.0 > gap.along_max
    assert _label_matches_gap(label, gap) is True


def test_label_bbox_that_stops_short_cannot_borrow_gap_by_proximity() -> None:
    gap = _GapSpan(
        axis=(1.0, 0.0),
        normal=(0.0, 1.0),
        along_min=100.0,
        along_max=140.0,
        cross_center=55.0,
        cross_spread=10.0,
    )
    assert _label_matches_gap(_line((141.0, 52.0, 146.0, 58.0)), gap) is False


def test_bbox_overlap_rule_is_quarter_turn_invariant() -> None:
    gap = _GapSpan(
        axis=(0.0, 1.0),
        normal=(-1.0, 0.0),
        along_min=100.0,
        along_max=140.0,
        cross_center=-55.0,
        cross_spread=10.0,
    )
    label = _line((52.0, 138.0, 58.0, 143.6))
    assert (label.bbox[1] + label.bbox[3]) / 2.0 > gap.along_max
    assert _label_matches_gap(label, gap) is True


def test_cross_axis_stray_label_still_cannot_own_gap() -> None:
    gap = _GapSpan(
        axis=(1.0, 0.0),
        normal=(0.0, 1.0),
        along_min=100.0,
        along_max=140.0,
        cross_center=55.0,
        cross_spread=4.0,
    )
    assert _label_matches_gap(_line((120.0, 100.0, 130.0, 106.0)), gap) is False
