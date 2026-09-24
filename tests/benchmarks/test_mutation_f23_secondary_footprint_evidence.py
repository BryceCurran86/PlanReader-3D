"""Legacy F.23 horizontal-chain suite replaced by orthogonal-depth attacks.

See ``test_mutation_f23_orthogonal_depth.py`` for the governing synthetic
matrix (all four edges, thickness traps, witness requirements, etc.).

This module keeps a narrow regression that F.15's horizontal-chain extractor
API is untouched by the F.23 depth work.
"""
from __future__ import annotations

import inspect

import pb_dimension_chain_evidence_extractor as f15


def test_f15_horizontal_chain_extractor_module_untouched_by_f23_depth_work():
    src = inspect.getsource(f15.extract_dimension_chains_from_page)
    # F.15 remains the horizontal consumer; F.23 must not invert this contract.
    assert "horizontal" in src.lower()
    assert f15.__doc__ is not None
    assert "F.15" in f15.__doc__


def test_title_partition_viewport_cannot_supply_physical_secondary_edge_geometry():
    from types import SimpleNamespace

    from pb_drawing_evidence_binding import DrawingViewType
    from pb_secondary_footprint_evidence import _eligible_plan_viewports
    from pb_viewport_segmentation import (
        ViewportBoundarySource,
        ViewportSegmentationStatus,
    )

    derived_partition = SimpleNamespace(
        status=ViewportSegmentationStatus.DERIVED.value,
        view_type=DrawingViewType.FLOOR_PLAN.value,
        bounding_box=(0.0, 0.0, 600.0, 400.0),
        boundary_source=ViewportBoundarySource.TITLE_PARTITION.value,
    )
    assert _eligible_plan_viewports(
        [derived_partition], allow_derived=True
    ) == []


def test_resolved_vector_frame_remains_valid_for_secondary_edge_geometry():
    from types import SimpleNamespace

    from pb_drawing_evidence_binding import DrawingViewType
    from pb_secondary_footprint_evidence import _eligible_plan_viewports
    from pb_viewport_segmentation import (
        ViewportBoundarySource,
        ViewportSegmentationStatus,
    )

    resolved_frame = SimpleNamespace(
        status=ViewportSegmentationStatus.RESOLVED.value,
        view_type=DrawingViewType.FLOOR_PLAN.value,
        bounding_box=(10.0, 10.0, 590.0, 390.0),
        boundary_source=ViewportBoundarySource.VECTOR_FRAME.value,
    )
    assert _eligible_plan_viewports(
        [resolved_frame], allow_derived=True
    ) == [resolved_frame]
