"""Source-owned visibility cannot launder disconnected W4 edge chains into frames.

This is a source-negative test; no source-free projected gap creates a physical
opening, wall frame, installed quantity, or frozen score.
"""
from dataclasses import replace

import pytest

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
    # Source-claimed primitive presence never grants a frame by itself.
    # The real producer is exercised independently in the tests below.

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


def test_actual_frame_producer_cannot_skip_unpartitioned_aligned_motif_rival(monkeypatch):
    """Real synthetic source-to-frame path: motif hints never substitute for DISTINCT.

    This tests the actual frame publisher, not a copied source-edge predicate.
    No original plan, source-specific coordinates or benchmark expectations.
    """
    import pb_opening_host_frame_authority as frame_module
    from pb_migration_contracts import EvidenceResolutionStatus as Status
    from test_raster_connected_host_frame import _fixture as source_fixture
    from test_raster_connected_host_frame import _publish, _scope

    _source, _composition, producer, bound = source_fixture()
    producer._raster_split_frame_shadow = True
    baseline = _publish(producer, bound)
    assert all(result.status is Status.CORROBORATED for result in baseline)

    scope = _scope(producer, bound)
    representative = scope.records[0]
    center = baseline[0].evidence.origin_pt[1]
    rival = replace(
        representative,
        wall_candidate_id="unpartitioned-aligned-motif-rival",
        physical_identity=replace(
            representative.physical_identity, source_primitive_ids=("unowned-source",)
        ),
        wall_candidate=replace(
            representative.wall_candidate,
            centerline_pts=((10.0, center), (30.0, center)),
        ),
    )
    candidate_scope = replace(scope, records=(*scope.records, rival))
    original_scope = repr(candidate_scope)
    monkeypatch.setattr(
        producer._walls, "resolve_scope", lambda _selector: candidate_scope
    )
    # Simulate a drafting-motif classification while source equivalence
    # deliberately contains no producer-owned DISTINCT relation for this rival.
    # Old code skipped this unknown pair and erroneously granted a frame.
    monkeypatch.setattr(
        frame_module, "repeated_raster_drafting_motif_wall_ids",
        lambda _records: frozenset((rival.wall_candidate_id,)), raising=False,
    )
    for ordered in (bound, tuple(reversed(bound))):
        results = _publish(producer, ordered)
        assert all(result.status is Status.ABSTAINED and result.evidence is None
                   for result in results)
        assert all(
            "opening_host_frame_aligned_fragment_distinctness_unproven"
            in result.reason_codes for result in results
        )
    assert repr(candidate_scope) == original_scope


def test_actual_publisher_refuses_second_chance_after_failed_original_source_proof(monkeypatch):
    """No geometry-only retry or second, weaker acceptance after a source veto."""
    from pb_migration_contracts import EvidenceResolutionStatus as Status
    from test_raster_connected_host_frame import _fixture as live_fixture
    from test_raster_connected_host_frame import _publish

    _source, _composition, producer, bound = live_fixture()
    assert all(result.status is Status.CORROBORATED
               for result in _publish(producer, bound))

    # Make an otherwise valid synthetic W4 member require the strict raster
    # source-projection path. Then simulate one authoritative source veto.
    # The old alternate path retried with relaxed geometry after this veto.
    producer._raster_split_frame_shadow = True
    selected_wall_id = bound[0][3].member_wall_candidate_ids[0]
    original_projection = producer._record_projection

    def require_source(record, axis, normal, *, strict_collinearity_shadow=False):
        if strict_collinearity_shadow and record.wall_candidate_id == selected_wall_id:
            return None
        return original_projection(
            record, axis, normal,
            strict_collinearity_shadow=strict_collinearity_shadow,
        )

    monkeypatch.setattr(producer, "_record_projection", require_source)
    monkeypatch.setattr(producer, "_raster_source_projection", lambda **_kwargs: None)
    for ordering in (bound, tuple(reversed(bound))):
        results = _publish(producer, ordering)
        assert all(result.status is Status.ABSTAINED and result.evidence is None
                   for result in results)
