"""Test-only reference geometry for the Net-wall Boolean Union validator.

This module has no authority role. It exists only to state the mathematical behavior
that future production must match *after* upstream wall/void/applicability authority
has selected the correct polygons.
"""
from __future__ import annotations

from collections.abc import Iterable

from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union


def reference_void_union(voids: Iterable[BaseGeometry]) -> BaseGeometry:
    """Union already-authenticated/applicable void geometry exactly once."""
    items = tuple(voids)
    return unary_union(items)


def reference_net_wall_polygon(
    gross_wall: BaseGeometry,
    voids: Iterable[BaseGeometry],
) -> BaseGeometry:
    """Reference model: gross wall polygon minus geometric union of voids."""
    return gross_wall.difference(reference_void_union(voids))


def normalized_wkb_hex(geometry: BaseGeometry) -> str:
    """Canonicalized test serialization used only for replay determinism assertions."""
    return geometry.normalize().wkb_hex