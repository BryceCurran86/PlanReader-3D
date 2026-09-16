"""Test-only reference helpers for non-height Physical Opening Void V2 attacks.

These helpers do not mint production authority. They only encode expected geometry,
identity and fail-closed relationships that remain useful while the real positive
height / vertical-placement prerequisite is external to this lane.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Optional


@dataclass(frozen=True)
class ScopeLineageFixture:
    document_id: str
    revision_id: str
    source_sha256: str
    snapshot_id: str
    page_id: str
    decision_scope_id: str


@dataclass(frozen=True)
class ReferenceVoidRectangle:
    opening_identity_id: str
    host_physical_group_id: str
    u0_m: float
    u1_m: float
    z0_m: float
    z1_m: float

    def __post_init__(self) -> None:
        if not self.opening_identity_id:
            raise ValueError("opening_identity_id is required")
        if not self.host_physical_group_id:
            raise ValueError("host_physical_group_id is required")
        coords = (self.u0_m, self.u1_m, self.z0_m, self.z1_m)
        if not all(math.isfinite(value) for value in coords):
            raise ValueError("void coordinates must be finite")
        if self.u1_m <= self.u0_m:
            raise ValueError("u span must be positive")
        if self.z1_m <= self.z0_m:
            raise ValueError("z span must be positive")

    @property
    def physical_key(self) -> tuple[str, str]:
        return (self.opening_identity_id, self.host_physical_group_id)

    @property
    def geometry(self) -> tuple[float, float, float, float]:
        return (self.u0_m, self.u1_m, self.z0_m, self.z1_m)

    @property
    def diagnostic_area_m2(self) -> float:
        return (self.u1_m - self.u0_m) * (self.z1_m - self.z0_m)


def exact_scope_matches(expected: ScopeLineageFixture, actual: ScopeLineageFixture) -> bool:
    return actual == expected


def map_segment_span_to_group(
    *,
    segment_origin_u_m: float,
    segment_length_m: float,
    local_u0_m: float,
    local_u1_m: float,
    reversed_orientation: bool = False,
) -> tuple[float, float]:
    """Map one representation-local wall span into a physical-group u frame.

    ``segment_origin_u_m`` is the lower physical-group u coordinate covered by the
    segment. Reversing only changes the segment-local coordinate orientation; it
    must not change the represented physical span.
    """
    values = (segment_origin_u_m, segment_length_m, local_u0_m, local_u1_m)
    if not all(math.isfinite(value) for value in values):
        raise ValueError("segment mapping inputs must be finite")
    if segment_length_m <= 0.0:
        raise ValueError("segment length must be positive")
    if local_u0_m < 0.0 or local_u1_m > segment_length_m or local_u1_m <= local_u0_m:
        raise ValueError("local span must be positive and contained by the segment")

    if reversed_orientation:
        mapped_u0 = segment_origin_u_m + segment_length_m - local_u1_m
        mapped_u1 = segment_origin_u_m + segment_length_m - local_u0_m
    else:
        mapped_u0 = segment_origin_u_m + local_u0_m
        mapped_u1 = segment_origin_u_m + local_u1_m
    return (mapped_u0, mapped_u1)


def dedupe_reference_voids(
    records: Iterable[ReferenceVoidRectangle],
) -> tuple[ReferenceVoidRectangle, ...]:
    """Collapse duplicate representations by authenticated physical proposition.

    Same physical opening + same physical host + same geometry is one void. If the
    same authenticated proposition arrives with contradictory geometry, fail closed
    instead of choosing first/nearest. Distinct physical opening identities remain
    distinct even when their geometry is numerically identical.
    """
    by_key: dict[tuple[str, str], ReferenceVoidRectangle] = {}
    for record in records:
        existing = by_key.get(record.physical_key)
        if existing is None:
            by_key[record.physical_key] = record
            continue
        if existing.geometry != record.geometry:
            raise ValueError("contradictory geometry for one authenticated physical opening void")
    return tuple(by_key[key] for key in sorted(by_key))


def supported_rectangular_profile(profile_kind: Optional[str]) -> bool:
    return profile_kind == "rectangular"


def nonheight_prerequisites_ready(
    *,
    opening_identity_resolved: bool,
    host_binding_resolved: bool,
    horizontal_span_resolved: bool,
    width_resolved: bool,
    wall_local_frame_resolved: bool,
    unit_mapping_resolved: bool,
    opening_universe_complete: bool,
    relevant_wall_equivalence_unambiguous: bool,
    profile_kind: Optional[str],
) -> bool:
    """Reference gate for prerequisites owned outside the height workstream.

    Height and vertical placement are deliberately absent from this helper. A true
    result means only that the non-height side is ready; production still MUST have
    separately authenticated height and vertical placement before publishing a void.
    """
    return all(
        (
            opening_identity_resolved,
            host_binding_resolved,
            horizontal_span_resolved,
            width_resolved,
            wall_local_frame_resolved,
            unit_mapping_resolved,
            opening_universe_complete,
            relevant_wall_equivalence_unambiguous,
            supported_rectangular_profile(profile_kind),
        )
    )


def diagnostic_area_or_none(record: Optional[ReferenceVoidRectangle]) -> Optional[float]:
    if record is None:
        return None
    return record.diagnostic_area_m2
