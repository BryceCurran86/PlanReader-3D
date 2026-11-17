"""Physical outside-bar safety: source negatives never authorize wall quantity."""
from shapely.geometry import box

from pb_source_unbounded_building_face_walk_shadow import (
    _pure_original_source_nonwall_bar,
    _source_mixed_title_frame_nonwall,
    _source_printed_scale_graphic_nonwall,
    _source_named_compact_outside_post,
    _source_named_service_nonwall,
    _source_outdoor_nonwall_tick,
    _source_numbered_dimension_tick,
)


def stroke(a=(10, 20), b=(20, 20), layer="Enclosure_WallExternal", width=.34):
    return {
        "type": "s", "layer": layer, "fill": None, "color": (0, 0, 0),
        "width": width, "items": [("l", a, b)],
    }


def word(name, x, y):
    return (x, y, x + 11, y + 6, name, 0, 0, 0)


def test_mixed_source_stays_wall_unless_all_originals_are_nonwall():
    geom = box(10, 19, 20, 22)
    rows = [stroke(layer="Annotation_FloorPlan"), stroke(layer="Structure_Slab")]
    assert _pure_original_source_nonwall_bar(geom, (0, 1), rows)
    rows.append(stroke(layer="Enclosure_WallExternal"))
    assert not _pure_original_source_nonwall_bar(geom, (0, 1, 2), rows)
    rows[1]["layer"] = "Service_StormwaterGeneral"
    assert not _pure_original_source_nonwall_bar(geom, (0, 1), rows)
    assert not _pure_original_source_nonwall_bar(box(100, 100, 120, 120), (0,), rows)


def test_title_grid_requires_original_frame_and_matched_path():
    geom = box(10, 19, 20, 22)
    rows = [stroke(layer=""), stroke(layer="Annotation_General")]
    assert _source_mixed_title_frame_nonwall(geom, (0, 1), rows, frozenset({0}))
    assert not _source_mixed_title_frame_nonwall(geom, (0, 1), rows, frozenset())
    rows[1]["layer"] = "Enclosure_WallExternal"
    assert not _source_mixed_title_frame_nonwall(geom, (0, 1), rows, frozenset({0}))
    assert not _source_mixed_title_frame_nonwall(
        box(100, 100, 200, 200), (0, 1), rows, frozenset({0})
    )


def test_original_scale_graphic_requires_0_to_6_monotonic_source_numbers():
    geom = box(150, 290, 160, 310)
    rows = [stroke((150, 300), (160, 300), layer="")]
    labels = [word("Scale", 70, 300), word("1:100", 82, 300)]
    labels.extend(word(str(i), 100 + i * 28, 307) for i in range(7))
    assert _source_printed_scale_graphic_nonwall(geom, (0,), rows, labels)
    assert not _source_printed_scale_graphic_nonwall(geom, (0,), rows, labels[:4])
    rows[0]["layer"] = "Enclosure_WallExternal"
    assert not _source_printed_scale_graphic_nonwall(geom, (0,), rows, labels)


def test_compact_post_requires_source_ink_post_and_outdoor_annotation():
    geom = box(10, 20, 14, 24)
    post = {
        "type": "f", "layer": "Enclosure_WallExternal",
        "fill": (0, 0, 0), "items": [],
    }
    labels = [word("POST", 37, 15), word("ALFRESCO", 20, 40)]
    assert _source_named_compact_outside_post(geom, (0,), [post], labels)
    assert not _source_named_compact_outside_post(geom, (0,), [post], labels[:1])
    assert not _source_named_compact_outside_post(
        box(10, 20, 30, 24), (0,), [post], labels
    )


def test_service_nonwall_requires_printed_dp_or_original_bottle_receipt():
    geom = box(10, 19, 20, 22)
    rows = [stroke(layer="Service_StormwaterGeneral") for _ in range(2)]
    assert _source_named_service_nonwall(geom, (0, 1), rows, [word("DP", 16, 20)])
    assert not _source_named_service_nonwall(
        geom, (0, 1), rows, [word("GARAGE", 16, 20)]
    )
    rows[0]["layer"] = "Enclosure_WallExternal"
    assert not _source_named_service_nonwall(geom, (0, 1), rows, [word("DP", 16, 20)])


def test_outdoor_short_stroke_requires_slab_and_original_outdoor_word():
    geom = box(10, 19, 20, 22)
    rows = [
        stroke(layer="Structure_Slab"),
        stroke(layer="Finish_Floor"),
        stroke(layer="Enclosure_WallExternal"),
    ]
    assert _source_outdoor_nonwall_tick(geom, (0, 1, 2), rows, [word("ALFRESCO", 25, 25)])
    assert not _source_outdoor_nonwall_tick(geom, (0, 1, 2), rows, [word("LIVING", 25, 25)])
    rows[2]["type"] = "f"
    rows[2]["fill"] = (0, 0, 0)
    assert not _source_outdoor_nonwall_tick(
        geom, (0, 1, 2), rows, [word("ALFRESCO", 25, 25)]
    )


def test_dimension_tick_needs_two_original_printed_dimensions_not_wall_fill():
    geom = box(10, 19, 20, 22)
    rows = [stroke(), stroke((10, 21), (20, 21))]
    labels = [word("70", 25, 25), word("1,130", 25, 12)]
    assert _source_numbered_dimension_tick(geom, (0, 1), rows, labels)
    assert not _source_numbered_dimension_tick(geom, (0, 1), rows, labels[:1])
    rows[1]["type"] = "f"
    rows[1]["fill"] = (0, 0, 0)
    assert not _source_numbered_dimension_tick(geom, (0, 1), rows, labels)
