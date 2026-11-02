"""Source-owned visibility cannot launder disconnected W4 edge chains into frames.

This is a source-negative test; no source-free projected gap creates a physical
opening, wall frame, installed quantity, or frozen score.
"""
from dataclasses import replace

import pytest
import inspect
from pb_opening_host_frame_authority import OpeningHostFrameProducer

from pb_raster_source_wall_frame_projection import source_edge_axis_projection
from test_raster_source_wall_frame_projection import _fixture


def _approved_alternate_projection(record, geometry, lines):
    """Mirror the production alternate-W4 source-chain *gate*, not geometry."""
    required = set(record.physical_identity.source_primitive_ids)
    return (
        bool(required)
        and all(primitive_id in lines for primitive_id in required)
        and source_edge_axis_projection(record, geometry, lines) is not None
    )


def test_clean_source_wall_fragment_chain_is_admissible_before_visible_owner_check():
    record, geometry, lines = _fixture()
    assert _approved_alternate_projection(record, geometry, lines)
    # Source-claimed primitive presence alone is insufficient: alt frames
    # must also pass the original chain proof, not W2's 2.5pt graph snap.
    assert "and source_edge_axis_projection(" in inspect.getsource(
        OpeningHostFrameProducer._shared_host_frame
    )

@pytest.mark.parametrize("gap", [0.01, 0.5, 2.0])
def test_source_edge_gap_cannot_be_joined_by_w2_snap_or_geometry(gap):
    record, geometry, lines = _fixture()
    a, b = record.source_edge_fragments
    record.source_edge_fragments = (a, replace(b, geometry=(gap, 5.0, 15.0, 5.0)))
    # The source primitive is still authenticated and every owner looks
    # plausible, but source-edge continuity is nevertheless NOT proved.
    assert set(record.physical_identity.source_primitive_ids) <= set(lines)
    assert not _approved_alternate_projection(record, geometry, lines)


def test_source_parent_substitution_cannot_extend_alternate_wall_frame():
    record, geometry, lines = _fixture()
    lines["source"] = (-10.0, 5.0, 14.0, 5.0)
    assert not _approved_alternate_projection(record, geometry, lines)


def test_source_identity_missing_cannot_use_geometry_only():
    record, geometry, lines = _fixture()
    record.physical_identity.source_primitive_ids = ()
    assert not _approved_alternate_projection(record, geometry, lines)
