"""Pure geometry fixtures for the Physical Opening Void V2 red-team lane.

TEST SUPPORT ONLY. These helpers calculate expected metamorphic relationships for
synthetic fixtures. They do not mint authority, choose evidence, or supply missing
host/height/scale/vertical-placement propositions to production.
"""
from __future__ import annotations

from dataclasses import dataclass
import math


Point = tuple[float, float]


@dataclass(frozen=True)
class WallLocalFrameFixture:
    origin: Point
    axis: Point
    points_per_m: float
    wall_length_m: float

    @property
    def end(self) -> Point:
        distance = self.wall_length_m * self.points_per_m
        return (
            self.origin[0] + self.axis[0] * distance,
            self.origin[1] + self.axis[1] * distance,
        )

    def project_u_m(self, point: Point) -> float:
        dx = float(point[0]) - self.origin[0]
        dy = float(point[1]) - self.origin[1]
        return (dx * self.axis[0] + dy * self.axis[1]) / self.points_per_m


@dataclass(frozen=True)
class WallLocalRectFixture:
    """Unauthoritative reference rectangle in wall-local metres."""

    u0: float
    u1: float
    z0: float
    z1: float

    def __post_init__(self) -> None:
        values = (self.u0, self.u1, self.z0, self.z1)
        if not all(math.isfinite(value) for value in values):
            raise ValueError("wall-local rectangle coordinates must be finite")
        if self.u1 <= self.u0 or self.z1 <= self.z0:
            raise ValueError("wall-local rectangle must have positive width and height")

    @property
    def width_m(self) -> float:
        return self.u1 - self.u0

    @property
    def height_m(self) -> float:
        return self.z1 - self.z0


def frame_from_baseline(start: Point, end: Point, *, points_per_m: float) -> WallLocalFrameFixture:
    if not math.isfinite(points_per_m) or points_per_m <= 0.0:
        raise ValueError("points_per_m must be finite and positive")
    dx = float(end[0]) - float(start[0])
    dy = float(end[1]) - float(start[1])
    length_points = math.hypot(dx, dy)
    if not math.isfinite(length_points) or length_points <= 0.0:
        raise ValueError("baseline must be finite and non-degenerate")
    return WallLocalFrameFixture(
        origin=(float(start[0]), float(start[1])),
        axis=(dx / length_points, dy / length_points),
        points_per_m=float(points_per_m),
        wall_length_m=length_points / float(points_per_m),
    )


def reverse_frame(frame: WallLocalFrameFixture) -> WallLocalFrameFixture:
    return WallLocalFrameFixture(
        origin=frame.end,
        axis=(-frame.axis[0], -frame.axis[1]),
        points_per_m=frame.points_per_m,
        wall_length_m=frame.wall_length_m,
    )


def project_span_m(frame: WallLocalFrameFixture, first: Point, second: Point) -> tuple[float, float]:
    values = sorted((frame.project_u_m(first), frame.project_u_m(second)))
    return (values[0], values[1])


def span_is_inside_frame(frame: WallLocalFrameFixture, span: tuple[float, float]) -> bool:
    """Whether a projected span belongs wholly to this reference frame."""
    u0, u1 = span
    return 0.0 <= u0 <= u1 <= frame.wall_length_m


def reverse_rect_u(rect: WallLocalRectFixture, *, wall_length_m: float) -> WallLocalRectFixture:
    if not math.isfinite(wall_length_m) or wall_length_m <= 0.0:
        raise ValueError("wall_length_m must be finite and positive")
    if rect.u0 < 0.0 or rect.u1 > wall_length_m:
        raise ValueError("rectangle must lie inside the wall frame")
    return WallLocalRectFixture(
        u0=wall_length_m - rect.u1,
        u1=wall_length_m - rect.u0,
        z0=rect.z0,
        z1=rect.z1,
    )


def canonical_rect_signature(
    rect: WallLocalRectFixture,
    *,
    wall_length_m: float,
    ndigits: int = 9,
) -> tuple[float, float, float, float]:
    """Stable test-only signature under legitimate host-baseline reversal.

    This is reference math only. It does not establish that a wall representation is
    physically equivalent or that a rectangle is authoritative. Those propositions
    must be proven upstream before this normalization may be relevant.
    """
    reversed_rect = reverse_rect_u(rect, wall_length_m=wall_length_m)
    forward = tuple(round(value, ndigits) for value in (rect.u0, rect.u1, rect.z0, rect.z1))
    reverse = tuple(
        round(value, ndigits)
        for value in (
            reversed_rect.u0,
            reversed_rect.u1,
            reversed_rect.z0,
            reversed_rect.z1,
        )
    )
    return min(forward, reverse)


def rigid_transform_point(point: Point, *, angle_rad: float, tx: float, ty: float) -> Point:
    cosine = math.cos(angle_rad)
    sine = math.sin(angle_rad)
    x, y = float(point[0]), float(point[1])
    return (
        x * cosine - y * sine + float(tx),
        x * sine + y * cosine + float(ty),
    )
