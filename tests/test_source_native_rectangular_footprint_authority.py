"""Source-neutral adversarial geometry tests; real original is a private gate."""
from __future__ import annotations

from copy import deepcopy

import fitz
import pytest

from pb_source_native_rectangular_footprint_authority import (
    SOURCE_PRIMITIVE_CAP,
    SOURCE_SNAP_TOL_PT,
    SourceNativePhysicalFootprint,
    corroborate_source_labeled_rectangular_footprint as prove,
)


def _stroke(*segments, width=.48):
    x = [p.x for a, b in segments for p in (a, b)]
    y = [p.y for a, b in segments for p in (a, b)]
    return {
        "type": "s", "color": (0.0, 0.0, 0.0), "width": width,
        "rect": fitz.Rect(min(x), min(y), max(x), max(y)),
        "items": [("l", a, b) for a, b in segments],
    }


def _edge(a, b, *, width=.48):
    return _stroke((fitz.Point(*a), fitz.Point(*b)), width=width)



def _post(x0, y0, x1, y1, *, color=(0.0, 0.0, 0.0)):
    """A genuine four-corner native source-post QUAD, not a bounding box."""
    return {
        "type": "s", "color": color, "width": .96,
        "rect": fitz.Rect(x0, y0, x1, y1),
        "items": [("qu", fitz.Quad(
            fitz.Point(x0, y1), fitz.Point(x0, y0),
            fitz.Point(x1, y1), fitz.Point(x1, y0),
        ))],
    }


def _drawing():
    # Geometry chosen solely to test generic enclosure/aspect; the source
    # labels and dimensions have no project, quantity or benchmark ID.
    return [
        _edge((120, 150), (130, 156), width=.96),
        _edge((150, 151), (170, 157), width=.96),
        _edge((100, 100), (175, 100)),
        _edge((100, 220), (175, 220)),
        _edge((100, 115), (100, 205)),
        _edge((190, 115), (190, 205)),
        _edge((300, 300), (500, 300)),
        # Open-air bay with genuine source wall continuations; four detached
        # long strokes alone may NEVER count as a closed floor boundary.
        _edge((100, 80), (100, 115), width=.96),
        _edge((100, 205), (100, 240), width=.96),
        # The two actual native square structural posts bridge each 15pt
        # right-hand discontinuity; source snap remains 2.5pt, not 15pt.
        _post(175, 100, 190, 115),
        _post(175, 205, 190, 220),
    ]


def _prove(drawings, *, width=3000, depth=4000, label=(0, 1), excluded=()):
    return prove(
        drawings,
        source_label_path_ids=label,
        figured_width_mm=width,
        figured_depth_mm=depth,
        excluded_source_path_ids=excluded,
    )


def test_unique_source_labeled_rectangle_binds_original_figure_aspect_only():
    witness = _prove(_drawing())
    assert type(witness) is SourceNativePhysicalFootprint
    assert witness.status == "CORROBORATED"
    assert witness.physical_scope == "source_labeled_exterior_architectural_footprint"
    assert witness.boundary_source_path_ids == (2, 3, 4, 5)
    assert witness.figured_width_mm == 3000
    assert witness.figured_depth_mm == 4000
    assert witness.native_bounds_pts == (100.0, 100.0, 190.0, 220.0)
    assert witness.boundary_model == "source_post_bounded_open_bay"
    assert witness.connector_source_path_ids == (7, 8, 9, 10)
    # An upstream figure witness can include its label paths in the complete
    # exclusion roster; the binder excludes them once without treating
    # authenticated shared labels as source contamination.
    assert _prove(_drawing(), excluded=(0, 1)) == witness


@pytest.mark.parametrize("mutate", (
    "missing_top", "missing_bottom", "missing_left", "missing_right",
    "wrong_figured_ratio", "foreign_label", "missing_label",
    "same_side_no_enclosure", "duplicate_outer_edge", "foreign_dimension_edge",
    "source_too_large", "duplicate_label_identity", "foreign_source_color",
    "missing_upper_wall", "missing_lower_wall", "shifted_upper_wall",
    "shifted_lower_wall", "missing_top_post", "missing_bottom_post",
    "shifted_top_post", "shifted_bottom_post", "false_bbox_post",
    "duplicate_corner_post", "wrong_post_color",
))
def test_native_physical_footprint_does_not_guess_missing_or_rival_edges(mutate):
    rows = _drawing()
    kwargs = {}
    if mutate == "missing_top":
        rows[2] = {}
    elif mutate == "missing_bottom":
        rows[3] = {}
    elif mutate == "missing_left":
        rows[4] = {}
    elif mutate == "missing_right":
        rows[5] = {}
    elif mutate == "wrong_figured_ratio":
        kwargs["width"] = 3500
    elif mutate == "foreign_label":
        rows[1] = _edge((210, 150), (220, 157), width=.96)
    elif mutate == "missing_label":
        rows[0] = {}
    elif mutate == "same_side_no_enclosure":
        rows[5] = _edge((101, 115), (101, 205))
    elif mutate == "duplicate_outer_edge":
        rows.append(deepcopy(rows[5]))
    elif mutate == "foreign_dimension_edge":
        kwargs["excluded"] = (5,)
    elif mutate == "source_too_large":
        rows.extend({} for _ in range(SOURCE_PRIMITIVE_CAP))
    elif mutate == "duplicate_label_identity":
        kwargs["label"] = (0, 0)
    elif mutate == "foreign_source_color":
        rows[5]["color"] = (1.0, 0.0, 0.0)
    elif mutate == "missing_upper_wall":
        rows[7] = {}
    elif mutate == "missing_lower_wall":
        rows[8] = {}
    elif mutate == "shifted_upper_wall":
        rows[7] = _edge((106,80),(106,115),width=.96)
    elif mutate == "shifted_lower_wall":
        rows[8] = _edge((106,205),(106,240),width=.96)
    elif mutate == "missing_top_post":
        rows[9] = {}
    elif mutate == "missing_bottom_post":
        rows[10] = {}
    elif mutate == "shifted_top_post":
        rows[9] = _post(179,100,194,115)
    elif mutate == "shifted_bottom_post":
        rows[10] = _post(175,209,190,224)
    elif mutate == "false_bbox_post":
        # The correct bounding box without source QUAD path is insufficient.
        rows[9] = _edge((175,100),(190,115),width=.96)
    elif mutate == "duplicate_corner_post":
        rows.append(deepcopy(rows[9]))
    elif mutate == "wrong_post_color":
        rows[10]["color"] = (1.,0.,0.)
    assert _prove(rows, **kwargs) is None


@pytest.mark.parametrize(("width", "depth"), [
    (None, 4000), (True, 4000), ("3000", 4000),
    (0, 4000), (3000, 0), (3000, 60000),
])
def test_reject_untrusted_figured_dimension_types_and_extents(width, depth):
    assert _prove(_drawing(), width=width, depth=depth) is None


def test_label_is_inside_footprint_and_geometry_not_used_as_metric_area():
    rows = _drawing()
    witness = _prove(rows)
    assert witness is not None
    # Changing the source-dimension figures without changing geometry is
    # refused rather than converting PDF point lengths to customer m².
    assert _prove(rows, width=3000, depth=4500) is None
    assert SOURCE_SNAP_TOL_PT == 2.5


def test_disconnected_outline_cannot_mint_physical_owner_without_connectors():
    # Previously this fake 15pt-gap outline CORROBORATED even though the
    # immutable snap tolerance is 2.5pt. Both missing structural witnesses
    # and open corners must now ABSTAIN.
    disconnected = _drawing()[:7]
    assert _prove(disconnected) is None


def test_true_four_corner_connected_outline_is_allowed_without_posts():
    rows = _drawing()[:7]
    rows[2] = _edge((100,100), (190,100))
    rows[3] = _edge((100,220), (190,220))
    rows[4] = _edge((100,100), (100,220))
    rows[5] = _edge((190,100), (190,220))
    witness = _prove(rows)
    assert witness is not None
    assert witness.boundary_model == "continuous_closed_outline"
    assert witness.connector_source_path_ids == ()
    assert witness.boundary_source_path_ids == (2,3,4,5)
