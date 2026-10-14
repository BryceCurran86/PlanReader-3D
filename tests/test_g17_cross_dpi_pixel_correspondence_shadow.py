"""Fail-closed cross-DPI source paint tests."""
from types import SimpleNamespace
import cv2
import numpy as np
import pytest
from pb_g17_cross_dpi_pixel_correspondence_shadow import source_owned_cross_dpi_pixel_shadow


def parent(**changes):
    fields = dict(observation_id="p3", page_id="3", document_id="doc",
                  revision_id="rev", source_sha256="a"*64,
                  snapshot_id="snap", source_partition_id="partition")
    fields.update(changes)
    return SimpleNamespace(**fields)


def image(dpi):
    canvas = np.full((dpi, dpi), 255, np.uint8)
    scale = dpi / 72
    for x0,y0,x1,y1 in [(12,20,26,20),(12,23,26,23),(26,20,26,23)]:
        cv2.line(canvas, (round(x0*scale),round(y0*scale)),
                 (round(x1*scale),round(y1*scale)), 0, 2)
    return cv2.imencode(".png",canvas)[1].tobytes()


def flank(ids=("a","b","c")):
    geoms = [(12,20,26,20),(12,23,26,23),(26,20,26,23)]
    return SimpleNamespace(source_ink_supported=True, exact_coordinate_records=tuple(
        SimpleNamespace(source_edge_fragments=(
            SimpleNamespace(geometry=g, source_primitive_ids=("raster_opening_primitive:"+i,)),
        )) for g,i in zip(geoms,ids)
    ))


def verify(flanks=None, **kwargs):
    return source_owned_cross_dpi_pixel_shadow(
        [flank()] if flanks is None else flanks,
        original_144_png=image(144), original_300_png=image(300),
        parent_144=parent(), parent_300=parent(), **kwargs,
    )


def test_ink_not_wall_or_quantity():
    result = verify()
    assert result["flanks"][0]["three_edge_same_source_paint_supported"]
    assert result["host_binding_granted"] is False
    assert result["physical_wall_equivalence_granted"] is False
    assert result["metric_quantity_granted"] is False


@pytest.mark.parametrize("key,value", [
    ("page_id","4"), ("snapshot_id","other"), ("revision_id","other"),
    ("source_sha256","b"*64), ("source_partition_id","other"),
])
def test_foreign_page_parent(key,value):
    with pytest.raises(ValueError):
        source_owned_cross_dpi_pixel_shadow(
            [flank()], original_144_png=image(144), original_300_png=image(300),
            parent_144=parent(), parent_300=parent(**{key:value}),
        )


def test_duplicate_primitive_not_three_edge_proof():
    assert not verify([flank(("a","b","a"))])["flanks"][0][
        "three_edge_same_source_paint_supported"
    ]


def test_unsupported_source_primitive_namespace():
    f=flank()
    f.exact_coordinate_records=f.exact_coordinate_records[:2]+(
        SimpleNamespace(source_edge_fragments=(
            SimpleNamespace(geometry=(26,20,26,23),
                            source_primitive_ids=("raster_segment:fake",)),
        )),
    )
    assert not verify([f])["flanks"][0]["three_edge_same_source_paint_supported"]


def test_dpi_mismatch_rejected():
    with pytest.raises(ValueError):
        verify(ordinary_dpi=300)
