"""Supplemental deterministic replay attacks for Item 12.

TEST/REPLAY ONLY.  No production precision or authority semantics are changed.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_physical_opening_void_authority import PhysicalOpeningVoidRecord
from tests.frozen_physical_void_snapshot_v1 import (
    FrozenPhysicalVoidSnapshotError,
    canonical_void_snapshot,
    frozen_physical_void_hash,
)


def _record(**overrides: object) -> PhysicalOpeningVoidRecord:
    values: dict[str, object] = {
        "record_id": "void-record-1",
        "document_id": "doc-1",
        "revision_id": "rev-1",
        "source_sha256": "sha-source",
        "snapshot_id": "snap-1",
        "page_id": "1",
        "viewport_id": "viewport-1",
        "decision_scope_id": "scope-1",
        "opening_identity_id": "opening-1",
        "host_binding_record_id": "host-binding-1",
        "host_wall_id": "wall-1",
        "opening_universe_record_id": "universe-1",
        "width_record_id": "width-1",
        "height_record_id": "height-1",
        "wall_local_frame_id": "frame-1",
        "unit_mapping_record_id": "scale-1",
        "vertical_placement_record_id": "vertical-1",
        "profile_kind": "rectangular_rough_opening",
        "coordinate_unit": "metre",
        "u0": 1.2345,
        "u1": 2.1345,
        "z0": 0.0,
        "z1": 2.1,
    }
    values.update(overrides)
    return PhysicalOpeningVoidRecord(**values)


def test_micro_float_drift_does_not_change_frozen_void_hash() -> None:
    base = _record()
    drifted = replace(
        base,
        u0=base.u0 + 2e-16,
        u1=base.u1 - 2e-16,
        z0=base.z0 + 1e-16,
        z1=base.z1 - 4e-16,
    )

    assert (base.u0, base.u1, base.z0, base.z1) != (
        drifted.u0,
        drifted.u1,
        drifted.z0,
        drifted.z1,
    )
    assert frozen_physical_void_hash(base) == frozen_physical_void_hash(drifted)
    assert canonical_void_snapshot(base) == canonical_void_snapshot(drifted)


def test_snapshot_coordinates_are_integer_point_one_mm_ticks() -> None:
    snapshot = canonical_void_snapshot(_record())
    ticks = snapshot[-1]

    assert ticks == (12_345, 21_345, 0, 21_000)
    assert all(type(value) is int for value in ticks)


def test_one_grid_tick_geometry_change_changes_hash() -> None:
    base = _record()
    shifted = replace(base, u1=base.u1 + 0.0001)

    assert frozen_physical_void_hash(base) != frozen_physical_void_hash(shifted)


def test_same_geometry_different_opening_identity_cannot_launder_snapshot() -> None:
    first = _record(opening_identity_id="opening-1")
    second = _record(opening_identity_id="opening-2")

    assert canonical_void_snapshot(first)[-1] == canonical_void_snapshot(second)[-1]
    assert frozen_physical_void_hash(first) != frozen_physical_void_hash(second)


def test_same_geometry_different_host_or_frame_cannot_launder_snapshot() -> None:
    first = _record()
    wrong_host = replace(first, host_wall_id="wall-2")
    wrong_frame = replace(first, wall_local_frame_id="frame-2")

    assert frozen_physical_void_hash(first) != frozen_physical_void_hash(wrong_host)
    assert frozen_physical_void_hash(first) != frozen_physical_void_hash(wrong_frame)


def test_sub_grid_sliver_collapsing_on_replay_grid_fails_closed() -> None:
    sliver = _record(u0=0.0, u1=0.00004)

    with pytest.raises(
        FrozenPhysicalVoidSnapshotError,
        match="geometry_collapsed_during_quantization",
    ):
        canonical_void_snapshot(sliver)


def test_non_finite_coordinate_fails_closed() -> None:
    invalid = _record(z1=float("nan"))

    with pytest.raises(FrozenPhysicalVoidSnapshotError, match="non_finite_coordinate"):
        canonical_void_snapshot(invalid)


def test_coordinate_unit_must_be_wall_local_metres() -> None:
    wrong_units = _record(coordinate_unit="mm")

    with pytest.raises(FrozenPhysicalVoidSnapshotError, match="coordinate_unit_not_metre"):
        canonical_void_snapshot(wrong_units)


def test_page_global_none_viewport_is_explicit_and_not_equal_to_viewport_scope() -> None:
    page_scope = _record(viewport_id=None)
    viewport_scope = _record(viewport_id="viewport-1")

    assert frozen_physical_void_hash(page_scope) != frozen_physical_void_hash(viewport_scope)


def test_snapshotting_does_not_mutate_production_record() -> None:
    record = _record()
    before = (record.u0, record.u1, record.z0, record.z1, record.record_id)

    _ = frozen_physical_void_hash(record)

    assert (record.u0, record.u1, record.z0, record.z1, record.record_id) == before
