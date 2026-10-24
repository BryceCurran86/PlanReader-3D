"""G17 must not choose source ancestry by raster record iteration order.

All fixtures use generated native PDF/image bytes; they never read benchmark
targets, permit host promotion, or import original customer quantity rows.
"""
from copy import deepcopy
from dataclasses import replace

import pytest

from pb_physical_opening_authority import RASTER_FRAMED_WALL_BAND_INTERRUPTION
from pb_raster_opening_source_primitives import RASTER_WALL_BAND_FACE
from test_raster_framed_opening_g17_contract import _prepare, _selector


def _owned_source_records():
    producer, published = _prepare(frame_lines=2)
    authority = producer.physical_opening_authority()
    selector = _selector(published, published.raster_opening_primitive_observation_ids[0])
    visible = authority._source_visibility_authority.resolve_raster_opening_primitive(selector)
    assert visible.observation is not None
    rows, failures = authority._raster_primitive_snapshot_records(visible)
    assert not failures and rows
    return producer, authority, visible.observation, rows


def test_unique_original_face_proof_is_retained_and_deterministic():
    producer, authority, seed, rows = _owned_source_records()
    before = deepcopy(producer._producer._store.observations)
    assert any(row.observation_kind == RASTER_WALL_BAND_FACE for row in rows)
    original = authority._raster_framed_candidates_for(seed, rows)
    assert len(original) == 1
    assert original[0].structural_pattern == RASTER_FRAMED_WALL_BAND_INTERRUPTION
    assert original == authority._raster_framed_candidates_for(seed, rows)
    assert producer._producer._store.observations == before


@pytest.mark.parametrize("reverse", [False, True])
def test_duplicate_source_primitive_geometry_must_abstain_not_elect_a_record(reverse):
    producer, authority, seed, rows = _owned_source_records()
    originals = deepcopy(producer._producer._store.observations)
    wall_face = next(r for r in rows if r.observation_kind == RASTER_WALL_BAND_FACE)
    duplicate = replace(wall_face, observation_id="separate_source_parent_identity")
    changed = (*rows, duplicate) if not reverse else (duplicate, *reversed(rows))
    result = authority._raster_framed_candidates_for(seed, changed)
    # A second physically indistinguishable source claim is an unresolved
    # identity collision, not evidence that one candidate owns both roots.
    assert result == ()
    key = authority._visible_page_candidate_key(seed)
    assert key in authority._raster_gap_audit_incomplete
    assert producer._producer._store.observations == originals
