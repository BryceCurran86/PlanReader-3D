"""Original 2.16pt source G17 opening-local W2 cannot alter global wall snap."""
import inspect
from pb_physical_wall_candidate_authority import (
    PhysicalWallCandidateProducer,_assemble_scope_result,
    _build_opening_local_supplemental_scope_result,
)
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_wall_room_topology_stage_a import DEFAULT_GAP_SNAP_TOLERANCE_PT

def test_original_global_w2_unchanged():
    assert DEFAULT_GAP_SNAP_TOLERANCE_PT == 2.5
    s=inspect.getsource(_assemble_scope_result)
    assert "gap_snap_tolerance_pt=0.0" in s
    assert "else:\n        graph = build_wall_graph_for_viewport(graph_segments)" in s
    assert inspect.signature(_assemble_scope_result).parameters[
        "opening_local_exact_source_endpoints_shadow"].default is False

def test_exact_is_only_incomplete_supplemental_factory():
    s=inspect.getsource(
        PhysicalWallCandidateProducer.from_opening_local_exact_g17_source_shadow)
    assert "supplemental_only=True" in s
    assert "opening_local_exact_source_endpoints_shadow=True" in s
    assert "opening_local_exact_source_endpoints_shadow" in inspect.signature(
        _build_opening_local_supplemental_scope_result).parameters

def test_original_live_composer_keeps_two_source_policies_separate():
    s=inspect.getsource(compose_live_wall_opening_authority)
    assert "if include_unmeasured_ink_closed_flanks_shadow" in s
    assert "from_opening_local_exact_g17_source_shadow" in s
    assert "from_opening_local_supplemental_source_visibility_producer" in s
