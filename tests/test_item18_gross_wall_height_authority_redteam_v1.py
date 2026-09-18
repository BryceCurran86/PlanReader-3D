"""Independent supplemental Item 18 attack.

TEST ONLY / EXPECTED RED / NEVER MERGE.

This does not modify frozen PR #469.  It isolates a new trust-boundary attack
found while reviewing corrected PR #471 head 437e18c67e8a27b85990df61586c1eb1c82362fc:
a caller-controlled object or Mapping must not satisfy the wall-height authority
prerequisite for gross-wall geometry.
"""
from __future__ import annotations

import pytest

from pb_gross_wall_geometry_authority import GrossWallGeometryProducer
from pb_opening_host_frame_authority import OpeningHostFrameAuthority
from pb_physical_scale_authority import PhysicalScaleAuthority
from pb_physical_wall_candidate_authority import PhysicalWallCandidateAuthority


class _ForgedHeightResolver:
    def resolve(self, selector):  # pragma: no cover - construction must reject first
        raise AssertionError("forged resolver reached")


def _shell(cls):
    return object.__new__(cls)


def _construct_with(height_source):
    return GrossWallGeometryProducer.from_authorities(
        physical_wall_candidate_authority=_shell(PhysicalWallCandidateAuthority),
        host_frame_authority=_shell(OpeningHostFrameAuthority),
        physical_scale_authority=_shell(PhysicalScaleAuthority),
        wall_height_authority=height_source,
    )


@pytest.mark.parametrize(
    "height_source",
    [
        _ForgedHeightResolver(),
        {},
        {"wall-A": object()},
    ],
)
def test_caller_controlled_height_sources_are_rejected_at_constructor_boundary(height_source) -> None:
    """Knowing or fabricating a plausible height source must never enter trust state."""
    with pytest.raises(TypeError):
        _construct_with(height_source)


def test_public_factory_cannot_accept_plain_object_as_wall_height_authority() -> None:
    with pytest.raises(TypeError):
        _construct_with(object())
