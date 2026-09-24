from __future__ import annotations

from pb_plan_door_swing_geometry import (
    QuarterCircleCubic,
    dimensioned_paired_door_swings,
    should_emit_dimensioned_repeated_door_total,
)


def _word(x0: float, y0: float, x1: float, y1: float, text: str):
    return (x0, y0, x1, y1, text, 0, 0, 0)


def test_dimensioned_paired_door_swings_counts_repeated_native_pairs() -> None:
    hits = [
        QuarterCircleCubic(radius=15.54, x=399.59, y=283.63, page=1),
        QuarterCircleCubic(radius=15.54, x=415.25, y=283.63, page=1),
        QuarterCircleCubic(radius=15.54, x=623.63, y=283.63, page=1),
        QuarterCircleCubic(radius=15.54, x=639.29, y=283.63, page=1),
    ]
    words = [
        _word(398.36, 299.65, 415.98, 307.57, "1200"),
        _word(622.28, 299.65, 639.90, 307.57, "1200"),
    ]

    count, widths, evidence = dimensioned_paired_door_swings(hits, words)

    assert count == 2
    assert widths == (1200, 1200)
    assert evidence.count("1200mm") == 2


def test_dimensioned_paired_door_swings_rejects_geometry_without_local_width() -> None:
    hits = [
        QuarterCircleCubic(radius=16.0, x=100.0, y=100.0, page=1),
        QuarterCircleCubic(radius=16.0, x=116.0, y=100.0, page=1),
        QuarterCircleCubic(radius=16.0, x=250.0, y=100.0, page=1),
        QuarterCircleCubic(radius=16.0, x=266.0, y=100.0, page=1),
    ]

    count, widths, evidence = dimensioned_paired_door_swings(hits, [])

    assert count == 0
    assert widths == ()
    assert evidence == ""


def test_dimensioned_paired_door_swings_rejects_inconsistent_figured_widths() -> None:
    hits = [
        QuarterCircleCubic(radius=16.0, x=100.0, y=100.0, page=1),
        QuarterCircleCubic(radius=16.0, x=116.0, y=100.0, page=1),
        QuarterCircleCubic(radius=16.0, x=250.0, y=100.0, page=1),
        QuarterCircleCubic(radius=16.0, x=266.0, y=100.0, page=1),
    ]
    words = [
        _word(101.0, 118.0, 115.0, 126.0, "1200"),
        _word(251.0, 118.0, 265.0, 126.0, "1500"),
    ]

    count, widths, evidence = dimensioned_paired_door_swings(hits, words)

    assert count == 0
    assert widths == ()
    assert evidence == ""


def test_dimensioned_paired_door_swings_rejects_unpaired_fillets() -> None:
    hits = [
        QuarterCircleCubic(radius=15.0, x=100.0, y=100.0, page=1),
        QuarterCircleCubic(radius=15.0, x=150.0, y=100.0, page=1),
        QuarterCircleCubic(radius=15.0, x=250.0, y=100.0, page=1),
        QuarterCircleCubic(radius=15.0, x=300.0, y=100.0, page=1),
    ]
    words = [
        _word(118.0, 118.0, 132.0, 126.0, "1200"),
        _word(268.0, 118.0, 282.0, 126.0, "1200"),
    ]

    count, _, _ = dimensioned_paired_door_swings(hits, words)

    assert count == 0


def test_dimensioned_repeated_door_publication_respects_existing_door_identity() -> None:
    assert should_emit_dimensioned_repeated_door_total(2, []) is True
    assert should_emit_dimensioned_repeated_door_total(2, ["W1"]) is True
    assert should_emit_dimensioned_repeated_door_total(2, ["D1"]) is False
    assert should_emit_dimensioned_repeated_door_total(2, ["DR-01"]) is False
