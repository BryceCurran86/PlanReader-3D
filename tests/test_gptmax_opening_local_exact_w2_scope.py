"""Only opening-local INCOMPLETE W4 may preserve exact 2.16pt painted source pier."""
from __future__ import annotations

import inspect
import pytest

from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,
    _assemble_scope_result,
    _build_opening_local_supplemental_scope_result,
)
from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT


def test_global_w2_snap_and_complete_default_remain_unchanged():
    assert DEFAULT_GAP_SNAP_TOLERANCE_PT == 2.5
    src = inspect.getsource(_assemble_scope_result)
    assert 'gap_snap_tolerance_pt=0.0' in src
    assert 'exact_endpoint_index_shadow=True' in src
    assert 'exact_split_parent_lineage_shadow=True' in src
    assert 'else:\n        graph = build_wall_graph_for_viewport(graph_segments)' in src
    assert inspect.signature(_assemble_scope_result).parameters[
        'opening_local_exact_source_endpoints_shadow'
    ].default is False


def test_factory_never_grants_complete_wall_scope_or_viewport_authority():
    src = inspect.getsource(
        PhysicalWallCandidateProducer.from_opening_local_exact_g17_source_shadow
    )
    assert "supplemental_only=True" in src
    assert "opening_local_exact_source_endpoints_shadow=True" in src
    assert "include_authenticated_viewports=False" in src
    assert "opening_local_exact_source_endpoints_shadow" in inspect.signature(
        _build_opening_local_supplemental_scope_result
    ).parameters


def test_canonical_wall_factory_has_same_public_signature_and_production_default():
    src = inspect.getsource(PhysicalWallCandidateProducer.from_source_visibility_producer)
    assert 'supplemental_only=False' in src
    assert "opening_local_exact_source_endpoints_shadow" not in src
    assert set(inspect.signature(
        PhysicalWallCandidateProducer.from_source_visibility_producer
    ).parameters) == {"source_visibility_producer", "page_ids"}


def test_internal_canonical_scope_explicitly_rejects_exact_local_policy():
    impl = inspect.getsource(PhysicalWallCandidateProducer._from_source_visibility_producer)
    assert 'opening_local_exact_source_endpoints_shadow and not supplemental_only' in impl
    assert 'raise ValueError("exact local W2 is prohibited in complete wall scopes")' in impl


def test_exact_source_option_rejects_invalid_boolean_before_any_source_access():
    from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer as P
    with pytest.raises(TypeError, match="explicit boolean"):
        P._from_source_visibility_producer(
            object(), page_ids=("3",), include_authenticated_viewports=False,
            include_page_scopes=True, supplemental_only=True,
            opening_local_exact_source_endpoints_shadow="true",
        )
