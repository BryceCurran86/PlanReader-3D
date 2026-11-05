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
    # An upstream figure witness can include its label paths in the complete
    # exclusion roster; the binder excludes them once without treating
    # authenticated shared labels as source contamination.
    assert _prove(_drawing(), excluded=(0, 1)) == witness


@pytest.mark.parametrize("mutate", (
    "missing_top", "missing_bottom", "missing_left", "missing_right",
    "wrong_figured_ratio", "foreign_label", "missing_label",
    "same_side_no_enclosure", "duplicate_outer_edge", "foreign_dimension_edge",
    "source_too_large", "duplicate_label_identity", "foreign_source_color",
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


def test_sha_original_source_footprint_remains_unique_on_authentic_ink():
    """Private original acceptance: no synthetic witness upgrades to source FIRM."""
    import hashlib
    import os
    from pathlib import Path

    from pb_gpt1_q5446_alfresco_figure_authority import (
        PLAN_ALFRESCO_LABEL_PATHS, original_alfresco_figure_witness,
    )
    from pb_gpt1_q5446_original_area_schedule_shadow import SOURCE_SHA256

    path = os.getenv("PLANREADER_ORIGINAL_Q5446_STANDARD_PLANS")
    if not path:
        pytest.skip("private SHA-original PDF is absent from public checkout")
    data = Path(path).read_bytes()
    assert hashlib.sha256(data).hexdigest() == SOURCE_SHA256
    with fitz.open(stream=data, filetype="pdf") as doc:
        assert len(doc) == 10
        strokes = doc[0].get_drawings()
    figure = original_alfresco_figure_witness(strokes)
    assert figure is not None and figure.diagnostic_only is True
    kwargs = dict(
        source_label_path_ids=PLAN_ALFRESCO_LABEL_PATHS,
        figured_width_mm=figure.horizontal_mm,
        figured_depth_mm=figure.vertical_mm,
        excluded_source_path_ids=figure.source_vector_path_ids,
    )
    footprint = prove(strokes, **kwargs)
    assert footprint is not None and footprint.status == "CORROBORATED"
    assert len(set(footprint.boundary_source_path_ids)) == 4

    # Each separately authenticated physical edge is required. A missing edge
    # on the genuine original must not be inferred from nearby ink.
    for path_id in footprint.boundary_source_path_ids:
        altered = list(strokes)
        altered[path_id] = {**strokes[path_id], "type": "f"}
        assert prove(altered, **kwargs) is None

    # A distinct second owner for the same edge makes the footprint ambiguous.
    altered = list(strokes)
    altered.append(deepcopy(strokes[footprint.boundary_source_path_ids[-1]]))
    assert prove(altered, **kwargs) is None
