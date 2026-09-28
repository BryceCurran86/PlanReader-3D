"""Differential and complexity checks for source-path retrace discovery."""
from __future__ import annotations

from dataclasses import replace
import math
import random

import pytest

import pb_physical_scale_authority as module


def _reference(segments):
    """Pre-index algorithm, retained as the independent semantic oracle."""
    consumed = set()
    normalized = []
    for segment in sorted(segments, key=lambda item: item.observation_id):
        if segment.observation_id in consumed:
            continue
        position = module._primitive_position(segment)
        matches = []
        if position is not None:
            for other in segments:
                other_position = module._primitive_position(other)
                if (other.observation_id != segment.observation_id
                    and other.observation_id not in consumed
                    and other_position is not None
                    and other_position[0] == position[0]
                    and abs(other_position[1] - position[1]) == 1
                    and module._distance(segment.start, other.end) <= 1e-6
                    and module._distance(segment.end, other.start) <= 1e-6):
                    matches.append(other)
        if len(matches) == 1:
            other = matches[0]
            consumed.add(other.observation_id)
            normalized.append(replace(segment, duplicate_observation_ids=tuple(sorted(
                (*segment.duplicate_observation_ids, *other.observation_ids)))))
        else:
            normalized.append(segment)
        consumed.add(segment.observation_id)
    return tuple(normalized)


def _segment(obs, drawing, item, a=(0.0, 0.0), b=(10.0, 0.0), duplicates=()):
    return module._VisibleSegment(obs, f"visible:segment:d{drawing}i{item}", a, b, duplicates)


@pytest.mark.parametrize("angle,scale,offset", [(0, 1, 0), (0.31, 10, 1000), (math.pi, 0.1, -90)])
def test_matches_original_with_conflicts_duplicates_order_and_transforms(angle, scale, offset):
    records = [
        _segment("a", 1, 1, duplicates=("prior",)),
        _segment("b", 1, 2, (10.0, 0.0), (0.0, 0.0)),
        _segment("c", 2, 4),
        _segment("d", 2, 3, (10.0, 0.0), (0.0, 0.0)),
        _segment("e", 2, 5, (10.0, 0.0), (0.0, 0.0)),
        _segment("f", 3, 1),
        _segment("g", 3, 1, (10.0, 0.0), (0.0, 0.0)),
        _segment("h", 3, 9, (10.0, 0.0), (0.0, 0.0)),
        # Adjacent but same direction must remain distinct.
        _segment("same-dir-a", 5, 10, (0.0, 5.0), (10.0, 5.0)),
        _segment("same-dir-b", 5, 11, (0.0, 5.0), (10.0, 5.0)),
        # Exact reverse geometry but non-adjacent primitive positions must remain distinct.
        _segment("non-adj-a", 6, 20, (0.0, 10.0), (10.0, 10.0)),
        _segment("non-adj-b", 6, 22, (10.0, 10.0), (0.0, 10.0)),
        replace(_segment("raster", 4, 1), source_primitive_ref="visible:raster_segment:1"),
    ]
    def point(p):
        return (offset + scale * (p[0]*math.cos(angle)-p[1]*math.sin(angle)),
                offset + scale * (p[0]*math.sin(angle)+p[1]*math.cos(angle)))
    records = [replace(r, start=point(r.start), end=point(r.end)) for r in records]
    rng = random.Random(7)
    for _ in range(8):
        rng.shuffle(records)
        before = tuple(records)
        assert module._coalesce_retraced_segments(records) == _reference(records)
        assert tuple(records) == before


def test_numeric_boundary_and_duplicate_position_buckets_preserve_all_provenance():
    records = [
        _segment("a", 8, 1),
        _segment("b", 8, 2, (10.0, 1e-6), (0.0, 1e-6)),
        _segment("c", 8, 2, (10.0, 1.0001e-6), (0.0, 1.0001e-6)),
        _segment("duplicate-id", 9, 1),
        _segment("duplicate-id", 9, 2),
    ]
    assert module._coalesce_retraced_segments(records) == _reference(records)


def test_dense_5000_segment_path_parses_each_source_position_once(monkeypatch):
    # Dense crossing/hatch geometry is irrelevant to source ancestry. The
    # permitted candidates still consist only of adjacent native positions.
    segments = [_segment(f"obs-{i:05}", 1, i, (0.0, float(i % 17)),
                         (100.0, float((i * 7) % 19))) for i in range(5000)]
    original = module._primitive_position
    calls = 0
    def bounded(segment):
        nonlocal calls
        calls += 1
        assert calls <= len(segments), "source positions are being reparsed quadratically"
        return original(segment)
    monkeypatch.setattr(module, "_primitive_position", bounded)
    result = module._coalesce_retraced_segments(segments)
    assert calls == len(segments)
    assert len(result) == len(segments)


def test_3000_unrelated_paths_never_compare_geometry(monkeypatch):
    segments = [_segment(f"obs-{i:05}", i, 0) for i in range(3000)]
    def forbidden(*args):
        raise AssertionError("compared unrelated source paths")
    monkeypatch.setattr(module, "_distance", forbidden)
    assert module._coalesce_retraced_segments(segments) == tuple(segments)
