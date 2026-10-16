"""Native clip proof and drawing sequence survive split lineage only."""
from __future__ import annotations

import copy
import math

import pytest

from pb_accuracy_v13_engines_v145 import split_segments_at_intersections
from pb_wall_room_topology_primitive_lineage import (
    attach_lineage_to_split_fragments,
    fabricated_live_fields,
    lineage_from_source_segments,
)
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport


def _segment(**overrides):
    base = {
        "id": "s",
        "kind": "line",
        "x1": 0.0,
        "y1": 0.0,
        "x2": 10.0,
        "y2": 0.0,
    }
    base.update(overrides)
    return base


def _record(**overrides):
    return lineage_from_source_segments(
        [_segment(**overrides)],
        retain_native_clip_sequence_shadow=True,
    )["source_records"][0]


def test_default_lineage_does_not_gain_clip_or_sequence_fields() -> None:
    segment = _segment(
        clip_shape_known=True,
        clip_exact_rect=[1.0, 2.0, 3.0, 4.0],
        sequence_number=7,
        path_index=True,
    )
    record = lineage_from_source_segments([segment])["source_records"][0]
    assert "clip_shape_known" not in record
    assert "clip_exact_rect" not in record
    assert "sequence_number" not in record
    assert record["path_index"] == 1
    graph = build_wall_graph_for_viewport([segment])
    edge_record = graph["edges"][0]["primitive_lineage"]["source_records"][0]
    assert "sequence_number" not in edge_record
    with pytest.raises(TypeError):
        lineage_from_source_segments([segment], retain_native_clip_sequence_shadow="yes")


def test_absent_clip_proof_and_sequence_are_not_invented() -> None:
    record = _record()
    assert "clip_shape_known" not in record
    assert "clip_exact_rect" not in record
    assert "clip_exact_rect_present" not in record
    assert "sequence_number" not in record
    assert "sequence_number_present" not in record
    assert record["clip_present"] is False


def test_proven_finite_clip_rect_is_retained() -> None:
    record = _record(
        clip_shape_known=True,
        clip_exact_rect=[1.0, 2.0, 3.0, 4.0],
        sequence_number=7,
    )
    assert record["clip_shape_known"] is True
    assert record["clip_exact_rect"] == [1.0, 2.0, 3.0, 4.0]
    assert record["clip_exact_rect_present"] is True
    assert record["sequence_number"] == 7
    assert record["sequence_number_present"] is True
    assert record["clip_present"] is False


@pytest.mark.parametrize(
    "shape_known",
    [False, 1, "yes", None],
)
def test_unproven_shape_cannot_make_a_rect_present(shape_known) -> None:
    record = _record(clip_shape_known=shape_known, clip_exact_rect=(0.0, 0.0, 8.0, 8.0))
    assert record["clip_shape_known"] is False
    assert record["clip_exact_rect"] == (0.0, 0.0, 8.0, 8.0)
    assert record["clip_exact_rect_present"] is False


@pytest.mark.parametrize(
    "rect",
    [
        [0.0, 0.0, math.nan, 1.0],
        [0.0, 0.0, math.inf, 1.0],
        [0.0, 0.0, 1.0],
        [0.0, 0.0, 1.0, True],
        "0 0 1 1",
        [],
        None,
    ],
)
def test_non_rect_clip_is_retained_and_not_present(rect) -> None:
    record = _record(clip_shape_known=True, clip_exact_rect=rect)
    assert record["clip_exact_rect"] == rect
    assert record["clip_exact_rect_present"] is False


@pytest.mark.parametrize(
    "sequence",
    [True, False, 1.0, "7", None, ""],
)
def test_non_integer_sequence_is_not_coerced(sequence) -> None:
    record = _record(sequence_number=sequence)
    assert record["sequence_number"] == sequence
    assert record["sequence_number_present"] is False


@pytest.mark.parametrize(
    ("field", "raw", "expected"),
    [
        ("path_index", True, True),
        ("path_index", False, False),
        ("item_index", True, True),
        ("edge_index", False, False),
        ("path_index", 3, 3),
        ("item_index", 0, 0),
        ("edge_index", "4", 4),
    ],
)
def test_boolean_path_index_is_not_invented(field, raw, expected) -> None:
    record = _record(**{field: raw})
    assert record[field] == expected
    assert type(record[field]) is type(expected)


def test_zero_sequence_number_stays_present() -> None:
    record = _record(sequence_number=0)
    assert record["sequence_number"] == 0
    assert record["sequence_number_present"] is True


def test_source_mutation_does_not_rewrite_retained_clip() -> None:
    segment = _segment(clip_shape_known=True, clip_exact_rect=[0.0, 0.0, 4.0, 4.0])
    record = lineage_from_source_segments(
        [segment], retain_native_clip_sequence_shadow=True,
    )["source_records"][0]
    segment["clip_exact_rect"][0] = 99.0
    assert record["clip_exact_rect"] == [0.0, 0.0, 4.0, 4.0]


def test_plural_clip_rects_are_retained_without_election() -> None:
    left = _segment(id="a", clip_shape_known=True, clip_exact_rect=[0.0, 0.0, 2.0, 2.0])
    right = _segment(id="b", clip_shape_known=True, clip_exact_rect=[3.0, 3.0, 5.0, 5.0])
    forward = lineage_from_source_segments(
        [left, right], retain_native_clip_sequence_shadow=True,
    )
    reverse = lineage_from_source_segments(
        [right, left], retain_native_clip_sequence_shadow=True,
    )
    assert forward["source_primitive_ids"] == reverse["source_primitive_ids"] == ["a", "b"]
    rects = {row["id"]: row["clip_exact_rect"] for row in forward["source_records"]}
    assert rects == {
        "a": [0.0, 0.0, 2.0, 2.0],
        "b": [3.0, 3.0, 5.0, 5.0],
    }
    assert {row["id"]: row["clip_exact_rect"] for row in reverse["source_records"]} == rects
    assert "clip" not in forward["attribute_conflicts"]


@pytest.mark.parametrize(
    "transform",
    [
        lambda s: {**s, "x1": s["x1"] + 40.0, "x2": s["x2"] + 40.0},
        lambda s: {**s, "x1": s["x1"] * 2.0, "x2": s["x2"] * 2.0},
        lambda s: {**s, "x1": -s["y1"], "y1": s["x1"], "x2": -s["y2"], "y2": s["x2"]},
    ],
)
def test_geometry_transform_does_not_rewrite_source_clip(transform) -> None:
    segment = _segment(
        clip_shape_known=True,
        clip_exact_rect=[1.0, 2.0, 3.0, 4.0],
        sequence_number=4,
    )
    moved = transform(copy.deepcopy(segment))
    record = lineage_from_source_segments(
        [moved], retain_native_clip_sequence_shadow=True,
    )["source_records"][0]
    assert record["clip_exact_rect"] == [1.0, 2.0, 3.0, 4.0]
    assert record["sequence_number"] == 4


def test_split_fragments_keep_parent_sequence_and_live_sentinels() -> None:
    source = _segment(
        id="axis",
        x2=20.0,
        clip_shape_known=True,
        clip_exact_rect=[0.0, -1.0, 20.0, 1.0],
        sequence_number=11,
    )
    cross = _segment(id="cross", x1=8.0, y1=-3.0, x2=8.0, y2=3.0)
    indexes: list[int] = []
    pairs = split_segments_at_intersections(
        [((item["x1"], item["y1"]), (item["x2"], item["y2"])) for item in (source, cross)],
        source_parent_indexes=indexes,
    )
    rows = attach_lineage_to_split_fragments(
        pairs, (source, cross), source_parent_indexes=indexes,
        retain_native_clip_sequence_shadow=True,
    )
    axis_rows = [
        row for row in rows if "axis" in row["primitive_lineage"]["source_primitive_ids"]
    ]
    assert axis_rows
    for row in axis_rows:
        assert fabricated_live_fields().items() <= row.items()
        parent = next(
            record
            for record in row["primitive_lineage"]["source_records"]
            if record["id"] == "axis"
        )
        assert parent["sequence_number"] == 11
        assert parent["clip_exact_rect_present"] is True
    graph = build_wall_graph_for_viewport(
        [source], retain_native_clip_sequence_shadow=True,
    )
    edge = graph["edges"][0]
    assert edge["width"] == 0.0
    assert edge["stroke"] is None
    assert edge["layer"] == ""
    assert edge["dashes"] == ""
    assert edge["primitive_lineage"]["source_records"][0]["sequence_number"] == 11
