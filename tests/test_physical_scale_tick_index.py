"""Differential and scaling checks for physical-scale endpoint tick indexing."""
from __future__ import annotations

import math
import random

import pytest

import pb_physical_scale_authority as module


def _segment(
    observation_id: str,
    start: tuple[float, float],
    end: tuple[float, float],
) -> module._VisibleSegment:
    return module._VisibleSegment(
        observation_id=observation_id,
        source_primitive_ref=f"visible:segment:d1i{observation_id}",
        start=start,
        end=end,
    )


def _rotated(
    point: tuple[float, float],
    *,
    angle: float,
    scale: float,
    dx: float,
    dy: float,
) -> tuple[float, float]:
    x, y = point
    return (
        dx + scale * (x * math.cos(angle) - y * math.sin(angle)),
        dy + scale * (x * math.sin(angle) + y * math.cos(angle)),
    )


def _transform_segments(
    segments: list[module._VisibleSegment],
    *,
    angle: float,
    scale: float,
    dx: float,
    dy: float,
) -> list[module._VisibleSegment]:
    return [
        module._VisibleSegment(
            observation_id=segment.observation_id,
            source_primitive_ref=segment.source_primitive_ref,
            start=_rotated(segment.start, angle=angle, scale=scale, dx=dx, dy=dy),
            end=_rotated(segment.end, angle=angle, scale=scale, dx=dx, dy=dy),
            duplicate_observation_ids=segment.duplicate_observation_ids,
        )
        for segment in segments
    ]


def _assert_index_matches_full_scan(
    segments: list[module._VisibleSegment],
) -> None:
    index = module._TickEndpointIndex(segments)
    for baseline in segments:
        if baseline.length <= 1e-9:
            continue
        for endpoint in (baseline.start, baseline.end):
            expected = module._tick_for_endpoint(baseline, endpoint, segments)
            actual = module._tick_for_endpoint(
                baseline,
                endpoint,
                index.candidates(baseline, endpoint),
            )
            assert actual == expected


@pytest.mark.parametrize(
    "angle,scale,dx,dy",
    [
        (0.0, 1.0, 0.0, 0.0),
        (0.37, 2.5, 1000.0, -300.0),
        (math.pi / 2.0, 0.4, -128.0, 512.0),
    ],
)
def test_tick_index_matches_full_scan_under_transform_and_order(
    angle: float,
    scale: float,
    dx: float,
    dy: float,
) -> None:
    segments: list[module._VisibleSegment] = []
    for row in range(12):
        y = float(row * 90)
        start_x = float((row % 3) * 7)
        length = float(80 + row * 3)
        baseline = _segment(
            f"base-{row}",
            (start_x, y),
            (start_x + length, y),
        )
        segments.append(baseline)
        tick_length = min(30.0, length * 0.5)
        segments.append(
            _segment(
                f"left-{row}",
                (start_x, y - tick_length / 2.0),
                (start_x, y + tick_length / 2.0),
            )
        )
        segments.append(
            _segment(
                f"right-{row}",
                (start_x + length, y - tick_length / 2.0),
                (start_x + length, y + tick_length / 2.0),
            )
        )

    rng = random.Random(813)
    for index in range(180):
        x = rng.uniform(-400.0, 1400.0)
        y = rng.uniform(-300.0, 1400.0)
        length = rng.uniform(2.0, 180.0)
        theta = rng.uniform(0.0, math.pi)
        segments.append(
            _segment(
                f"distractor-{index}",
                (x, y),
                (
                    x + length * math.cos(theta),
                    y + length * math.sin(theta),
                ),
            )
        )

    transformed = _transform_segments(
        segments,
        angle=angle,
        scale=scale,
        dx=dx,
        dy=dy,
    )
    rng.shuffle(transformed)
    _assert_index_matches_full_scan(transformed)


@pytest.mark.parametrize("parameter", [0.15, 0.85])
def test_tick_index_keeps_numeric_boundary_candidates(parameter: float) -> None:
    baseline = _segment("base", (0.0, 0.0), (100.0, 0.0))
    tick_length = 50.0
    start_y = -parameter * tick_length
    tick = _segment(
        "tick",
        (0.5, start_y),
        (0.5, start_y + tick_length),
    )
    segments = [baseline, tick]

    expected = module._tick_for_endpoint(baseline, baseline.start, segments)
    index = module._TickEndpointIndex(segments)
    actual = module._tick_for_endpoint(
        baseline,
        baseline.start,
        index.candidates(baseline, baseline.start),
    )

    assert expected == (tick,)
    assert actual == expected


def test_bar_candidates_equal_full_universe_oracle(monkeypatch) -> None:
    baseline = _segment("base", (0.0, 0.0), (100.0, 0.0))
    left = _segment("left", (0.0, -10.0), (0.0, 10.0))
    right = _segment("right", (100.0, -10.0), (100.0, 10.0))
    distractors = [
        _segment(
            f"d-{index}",
            (300.0 + index * 3.0, 200.0),
            (360.0 + index * 3.0, 200.0),
        )
        for index in range(80)
    ]
    segments = [baseline, left, right, *distractors]
    words = [
        module._TrustedWord("zero", "0", (-3.0, 10.0, 3.0, 18.0)),
        module._TrustedWord(
            "physical",
            "1000 mm",
            (94.0, 10.0, 106.0, 18.0),
        ),
    ]

    indexed = module._bar_candidates(segments, words)

    monkeypatch.setattr(
        module._TickEndpointIndex,
        "candidates",
        lambda self, baseline, endpoint: self._segments,
    )
    full_scan = module._bar_candidates(segments, words)

    assert indexed == full_scan
    assert len(indexed) == 1
    assert indexed[0].segment_ids == ("base", "left", "right")
    assert indexed[0].text_ids == ("physical", "zero")


def test_dense_irrelevant_geometry_is_not_rechecked_per_endpoint() -> None:
    baseline = _segment("base", (0.0, 0.0), (100.0, 0.0))
    left = _segment("left", (0.0, -10.0), (0.0, 10.0))
    right = _segment("right", (100.0, -10.0), (100.0, 10.0))
    distractors = [
        _segment(
            f"d-{index}",
            (-2000.0 + float(index), 500.0 + float(index % 11)),
            (2000.0 + float(index), 500.0 + float(index % 11)),
        )
        for index in range(5000)
    ]
    segments = [baseline, left, right, *distractors]
    index = module._TickEndpointIndex(segments)

    left_candidates = index.candidates(baseline, baseline.start)
    right_candidates = index.candidates(baseline, baseline.end)

    assert left in left_candidates
    assert right in right_candidates
    assert len(left_candidates) < 20
    assert len(right_candidates) < 20


def test_index_preserves_duplicate_observation_exclusion() -> None:
    baseline = module._VisibleSegment(
        observation_id="base",
        source_primitive_ref="visible:segment:d1i1",
        start=(0.0, 0.0),
        end=(100.0, 0.0),
        duplicate_observation_ids=("shared",),
    )
    overlapping_tick = module._VisibleSegment(
        observation_id="tick",
        source_primitive_ref="visible:segment:d1i2",
        start=(0.0, -10.0),
        end=(0.0, 10.0),
        duplicate_observation_ids=("shared",),
    )
    independent_tick = _segment("independent", (0.0, -12.0), (0.0, 12.0))
    segments = [baseline, overlapping_tick, independent_tick]

    expected = module._tick_for_endpoint(baseline, baseline.start, segments)
    index = module._TickEndpointIndex(segments)
    actual = module._tick_for_endpoint(
        baseline,
        baseline.start,
        index.candidates(baseline, baseline.start),
    )

    assert expected == (independent_tick,)
    assert actual == expected
