"""Actual producer-bound G17 candidates never grant physical wall authority."""
from copy import deepcopy
from dataclasses import replace

import numpy as np
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_local_g17_wall_shadow import build_opening_local_g17_wall_shadow
from pb_physical_wall_candidate_authority import PhysicalWallCandidateProducer
from tests.test_raster_framed_opening_g17_contract import (
    _closure_source, _corroborated_records, _prepare, _selector, _sheet,
)


def address(source, published):
    records = _corroborated_records(source, published)
    assert len(records) == 1
    return _selector(published, records[0].source_observation_ids[0])


def test_actual_source_to_original_w4_primitives_without_augmentation(monkeypatch):
    source, published = _prepare(frame_lines=2)
    selector = address(source, published)
    before = deepcopy(source._raster_opening_primitive_receipts)
    def forbidden(*args, **kwargs):
        raise AssertionError("shadow must never augment published source")
    monkeypatch.setattr(source, "augment_with_raster_visible_segments", forbidden)
    monkeypatch.setattr(source, "augment_with_raster_opening_primitives", forbidden)
    result = build_opening_local_g17_wall_shadow(source, selector)
    assert source.published_snapshot_for_revision(selector.revision_id) == published
    assert source._raster_opening_primitive_receipts == before
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert len(result.flanks) == 2
    for flank in result.flanks:
        assert flank.source_ink_supported
        assert len(flank.source_parent_ids) == 3
        assert len(flank.default_records) == len(flank.exact_coordinate_records) == 3
        assert flank.default_junction_types.count("l_corner") == 2
        assert "near_junction_review" in flank.default_junction_types
        for record in flank.exact_coordinate_records:
            assert record.physical_identity.usable
            assert all(p.startswith("raster_opening_primitive:")
                       for p in record.physical_identity.source_primitive_ids)
            assert all(set(f.source_primitive_ids) <= set(record.physical_identity.source_primitive_ids)
                       for f in record.source_edge_fragments)
    assert not result.scope_complete
    assert not result.physical_wall_role_granted
    assert not result.opening_host_granted
    assert not result.metric_quantity_granted
    # A candidate wrapper is not a source producer or sealed wall universe.
    with pytest.raises(TypeError):
        PhysicalWallCandidateProducer.from_source_visibility_producer(result)


def test_selector_order_and_replay_keep_same_candidate_ids():
    source, published = _prepare(frame_lines=2)
    records = _corroborated_records(source, published)
    selectors = [_selector(published, oid) for oid in records[0].source_observation_ids]
    first = build_opening_local_g17_wall_shadow(source, selectors[0])
    for selector in reversed(selectors):
        current = build_opening_local_g17_wall_shadow(source, selector)
        assert replace(current, source_selector=first.source_selector) == first


@pytest.mark.parametrize("turns,scale,pad", [(0,1,0), (1,1,0), (2,1,0), (3,1,0), (0,0.5,0), (0,1,40)])
def test_source_geometry_transforms_preserve_candidates_without_wall_role(turns, scale, pad):
    gray = np.ascontiguousarray(np.rot90(_sheet(frame_lines=2), turns))
    gray = np.pad(gray, ((pad,pad), (pad,pad)), constant_values=255)
    source, published = _closure_source(gray, scale=scale)
    result = build_opening_local_g17_wall_shadow(source, address(source,published))
    assert len(result.flanks) == 2
    assert all(f.source_ink_supported and len(f.exact_coordinate_records) == 3 for f in result.flanks)
    assert not result.opening_host_granted
    assert not result.metric_quantity_granted


@pytest.mark.parametrize("field", ["document_id", "source_sha256", "revision_id", "snapshot_id"])
def test_foreign_source_addresses_cannot_create_local_candidates(field):
    source, published = _prepare(frame_lines=2)
    selector = replace(address(source,published), **{field:"foreign"})
    with pytest.raises(ValueError):
        build_opening_local_g17_wall_shadow(source, selector)


def test_caller_reports_and_producer_lookalikes_are_rejected():
    source, published = _prepare(frame_lines=2)
    selector = address(source,published)
    with pytest.raises(TypeError):
        build_opening_local_g17_wall_shadow({"source_closed":True}, selector)
    with pytest.raises(TypeError):
        build_opening_local_g17_wall_shadow(source, {"observation_id":selector.observation_id})


@pytest.mark.parametrize("damage", ["receipt", "parent", "geometry", "source_bytes"])
def test_changed_producer_source_fails_even_after_positive_shadow_replay(damage):
    source, published = _prepare(frame_lines=2)
    selector = address(source,published)
    positive = build_opening_local_g17_wall_shadow(source,selector)
    assert len(positive.flanks) == 2
    store = source._producer._store
    key = (selector.snapshot_id,selector.observation_id)
    observation = store.observations[key]
    if damage == "receipt":
        source._raster_opening_primitive_receipts.pop(key)
    elif damage == "parent":
        parent_key=(selector.snapshot_id,observation.derivation_parent_ids[0])
        store.observations.pop(parent_key)
    elif damage == "geometry":
        store.observations[key]=replace(observation,geometry=(1.,2.,3.,4.))
    else:
        store.source_bytes_by_revision[selector.revision_id]=b"foreign bytes"
    try:
        result = build_opening_local_g17_wall_shadow(source,selector)
    except (ValueError, RuntimeError):
        return
    assert result.flanks == ()
    assert not result.opening_host_granted


@pytest.mark.parametrize("frames", [0,1])
def test_weak_original_gap_cannot_create_w4_scope(frames):
    source, published = _prepare(frame_lines=frames)
    result = build_opening_local_g17_wall_shadow(
        source, _selector(published,published.raster_opening_primitive_observation_ids[0]))
    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.flanks == ()
    assert not result.opening_host_granted
