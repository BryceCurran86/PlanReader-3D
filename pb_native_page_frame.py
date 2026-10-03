"""Live native PDF page-frame contract for source geometry consumers.

PyMuPDF exposes native text/vector primitives in unrotated page user space,
while page.rect is expressed in display-rotated space. This module provides the
small production seam needed to put page extents into the same coordinate space
as those source primitives.

Promotion is deliberately narrow:
- rotation 0: supported;
- rotation 90: supported after validation on a real production architectural
  source;
- rotation 180/270: fail closed until their separate real-source promotion gate
  is satisfied.

No scale, wall, viewport, quantity, benchmark, or project semantics live here.
"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Optional

import fitz


NATIVE_PAGE_FRAME_SCHEMA_VERSION = "1.0.0"
NATIVE_PAGE_FRAME_UNRESOLVED = "native_page_frame_unresolved"
_SUPPORTED_ROTATIONS = frozenset((0, 90))
_COORD_TOL = 1e-6
_MAX_PARENT_DEPTH = 32


class NativePageFrameUnresolved(RuntimeError):
    """The PDF page frame cannot safely bound native source geometry."""


@dataclass(frozen=True)
class NativePageFrame:
    rotation: int
    native_width: float
    native_height: float
    display_width: float
    display_height: float
    coordinate_space: str = "native_page_user_space"
    schema_version: str = NATIVE_PAGE_FRAME_SCHEMA_VERSION


def _raise_unresolved() -> None:
    raise NativePageFrameUnresolved(NATIVE_PAGE_FRAME_UNRESOLVED)


def effective_pdf_rotation(page: fitz.Page) -> int:
    """Resolve exact effective /Rotate from page-tree metadata, fail closed."""

    parent = getattr(page, "parent", None)
    getter = getattr(parent, "xref_get_key", None)
    xref = getattr(page, "xref", None)
    if not callable(getter) or not isinstance(xref, int) or isinstance(xref, bool):
        _raise_unresolved()

    raw_rotate: Optional[str] = None
    seen = {xref}
    node = xref
    for _ in range(_MAX_PARENT_DEPTH):
        try:
            kind, raw = getter(node, "Rotate")
        except Exception as exc:
            raise NativePageFrameUnresolved(NATIVE_PAGE_FRAME_UNRESOLVED) from exc
        if kind != "null":
            raw_rotate = str(raw)
            break
        try:
            parent_kind, parent_raw = getter(node, "Parent")
        except Exception:
            break
        if parent_kind != "xref":
            break
        try:
            node = int(str(parent_raw).split()[0])
        except (TypeError, ValueError, IndexError):
            break
        if node in seen:
            _raise_unresolved()
        seen.add(node)

    if raw_rotate is None:
        effective = 0
    else:
        try:
            numeric = float(raw_rotate)
        except (TypeError, ValueError) as exc:
            raise NativePageFrameUnresolved(NATIVE_PAGE_FRAME_UNRESOLVED) from exc
        if (
            not math.isfinite(numeric)
            or numeric != int(numeric)
            or int(numeric) % 90 != 0
        ):
            _raise_unresolved()
        effective = int(numeric) % 360

    reported = getattr(page, "rotation", None)
    if (
        not isinstance(reported, int)
        or isinstance(reported, bool)
        or reported % 360 != effective
    ):
        _raise_unresolved()
    return effective


def native_page_frame(page: fitz.Page) -> NativePageFrame:
    """Return page extent in the coordinate space of native source primitives."""

    rotation = effective_pdf_rotation(page)
    if rotation not in _SUPPORTED_ROTATIONS:
        _raise_unresolved()

    try:
        rect = page.rect
        x0 = float(rect.x0)
        y0 = float(rect.y0)
        display_width = float(rect.width)
        display_height = float(rect.height)
    except Exception as exc:
        raise NativePageFrameUnresolved(NATIVE_PAGE_FRAME_UNRESOLVED) from exc

    values = (x0, y0, display_width, display_height)
    if (
        not all(math.isfinite(value) for value in values)
        or display_width <= 0.0
        or display_height <= 0.0
        or abs(x0) > _COORD_TOL
        or abs(y0) > _COORD_TOL
    ):
        _raise_unresolved()

    if rotation == 90:
        native_width, native_height = display_height, display_width
    else:
        native_width, native_height = display_width, display_height

    return NativePageFrame(
        rotation=rotation,
        native_width=native_width,
        native_height=native_height,
        display_width=display_width,
        display_height=display_height,
    )


__all__ = [
    "NATIVE_PAGE_FRAME_SCHEMA_VERSION",
    "NATIVE_PAGE_FRAME_UNRESOLVED",
    "NativePageFrame",
    "NativePageFrameUnresolved",
    "effective_pdf_rotation",
    "native_page_frame",
]
