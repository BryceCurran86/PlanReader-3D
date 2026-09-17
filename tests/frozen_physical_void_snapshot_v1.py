"""Deterministic frozen snapshots for Physical Opening Void replay only.

TEST/REPLAY SUPPORT ONLY.  Physical Opening Void production keeps full-precision
floats.  Frozen replay converts the already-authoritative wall-local rectangle to
integer 0.1 mm ticks so insignificant binary float drift cannot change snapshot
signatures.  Lineage is retained in the snapshot so equal geometry cannot launder
one physical opening into another.
"""
from __future__ import annotations

from hashlib import sha256
import json
import math
from typing import Any


GRID_SIZE_M = 1e-4
TICKS_PER_METRE = 10_000
SNAPSHOT_SCHEMA = "planreader_physical_opening_void_snapshot_v1"


class FrozenPhysicalVoidSnapshotError(ValueError):
    """The authoritative void cannot be represented on the frozen replay grid."""


def _required_text(record: object, name: str) -> str:
    value = getattr(record, name, None)
    if value is None and name == "viewport_id":
        return ""
    text = str(value or "").strip()
    if not text:
        raise FrozenPhysicalVoidSnapshotError(f"missing_lineage:{name}")
    return text


def _snap_tick(value: Any) -> int:
    number = float(value)
    if not math.isfinite(number):
        raise FrozenPhysicalVoidSnapshotError("non_finite_coordinate")
    # Python integers are used deliberately instead of NumPy int64: the frozen
    # JSON representation is platform-independent and cannot overflow at int64.
    return int(round(number * TICKS_PER_METRE))


def canonical_void_snapshot(record: object) -> tuple[object, ...]:
    """Canonical integer snapshot of one authoritative wall-local void record."""
    if _required_text(record, "coordinate_unit") != "metre":
        raise FrozenPhysicalVoidSnapshotError("coordinate_unit_not_metre")

    u0 = _snap_tick(getattr(record, "u0", None))
    u1 = _snap_tick(getattr(record, "u1", None))
    z0 = _snap_tick(getattr(record, "z0", None))
    z1 = _snap_tick(getattr(record, "z1", None))
    if u1 <= u0 or z1 <= z0:
        raise FrozenPhysicalVoidSnapshotError("geometry_collapsed_during_quantization")

    return (
        SNAPSHOT_SCHEMA,
        "metre",
        TICKS_PER_METRE,
        (
            _required_text(record, "document_id"),
            _required_text(record, "revision_id"),
            _required_text(record, "source_sha256"),
            _required_text(record, "snapshot_id"),
            _required_text(record, "page_id"),
            _required_text(record, "viewport_id"),
            _required_text(record, "decision_scope_id"),
            _required_text(record, "opening_identity_id"),
            _required_text(record, "host_binding_record_id"),
            _required_text(record, "host_wall_id"),
            _required_text(record, "opening_universe_record_id"),
            _required_text(record, "width_record_id"),
            _required_text(record, "height_record_id"),
            _required_text(record, "wall_local_frame_id"),
            _required_text(record, "unit_mapping_record_id"),
            _required_text(record, "vertical_placement_record_id"),
            _required_text(record, "profile_kind"),
            _required_text(record, "schema_version"),
        ),
        (u0, u1, z0, z1),
    )


def frozen_physical_void_hash(record: object) -> str:
    encoded = json.dumps(
        canonical_void_snapshot(record),
        separators=(",", ":"),
        ensure_ascii=True,
    ).encode("ascii")
    return sha256(encoded).hexdigest()


__all__ = [
    "GRID_SIZE_M",
    "TICKS_PER_METRE",
    "SNAPSHOT_SCHEMA",
    "FrozenPhysicalVoidSnapshotError",
    "canonical_void_snapshot",
    "frozen_physical_void_hash",
]
