from pb_g17_segment_parent_line_shadow import (
    _finite_line,
    lines_mapping_from_shadow,
)


def test_finite_line_rejects_degenerate():
    assert _finite_line((0.0, 0.0, 0.0, 0.0)) is None
    assert _finite_line((0.0, 0.0, 10.0, 0.0)) == (0.0, 0.0, 10.0, 0.0)


def test_lines_mapping_from_shadow_filters_bad():
    mapping = lines_mapping_from_shadow({
        "lines_by_raw_primitive_id": {
            "a": [0.0, 0.0, 5.0, 0.0],
            "b": [1.0, 1.0, 1.0, 1.0],
        },
    })
    assert list(mapping.keys()) == ["a"]
