"""SHADOW ONLY: immutable page-frame descriptor for PDF pages.

What this is: a provenance record that states, for one page of one exact
source revision, which coordinate space its extent is expressed in, the
normalised page rotation (0/90/180/270), the native page extent, the display
(rotated) extent, where those numbers came from, and whether the page
metadata is coherent.

What this is NOT: it carries no measurement authority and is not an
``EvidenceAtom`` / ``QuantityEvidence``. It does not resolve scale, does not
touch wall, viewport or scale authority, transforms no production geometry
and has no live consumer. No production module may import it.

Native vs display rule: extents and points come in two distinct, never
interchangeable types. ``NativePageExtent`` / ``NativePoint`` live in
``NATIVE_PAGE_USER_SPACE`` (the space PyMuPDF reports ``get_drawings``,
``get_text`` words and ``extract_native_page`` segments in: unrotated,
CropBox-origin-normalised, UserUnit-scaled points). ``DisplayPageExtent`` /
``DisplayPoint`` live in ``DISPLAY_ROTATED_SPACE`` (``page.rect`` and
``page.rotation_matrix`` output). Boundary / containment helpers exist only
for the native types; moving between the spaces needs an explicit
``native_to_display`` / ``display_to_native`` call.

PROMOTION GATE: everything here is validated on synthetic fixtures only. No
authority promotion, and no wiring of this descriptor into live
physical-wall or scale authority, is allowed until a real source PDF with
genuine /Rotate 90, 180 and 270 has been obtained and the shadow comparison
rerun on it. Second-hand rotation counts are not validation.
"""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, ClassVar, Optional

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id

PAGE_FRAME_SHADOW_SCHEMA_VERSION = "1.0.0"

# Unit axis. Same spelling as pb_figured_dimension_evidence.CoordinateSpace.PDF_POINTS
# (asserted by a test); not imported here because that module drags in firm-seam
# authority modules. The value means UserUnit-scaled PyMuPDF points.
UNIT_PDF_POINTS = "pdf_points"

EXTENT_SOURCE_PAGE_RECT_SWAPPED_FOR_ROTATION = "pymupdf_page_rect_swapped_for_rotation"

LEGAL_ROTATIONS = (0, 90, 180, 270)

# float32 rounding model. PyMuPDF/MuPDF hold page boxes and geometry as float32,
# so every box-derived number carries at most 0.5 ulp_f32 of rounding per
# operation. Two tolerances are expressed in ulps of the largest float32 magnitude
# that participates (extent or absolute MediaBox coordinate x UserUnit):
#   * CROSS_CHECK_ULPS: equality of page.rect with the CropBox/MediaBox
#     intersection (a subtraction of two float32 numbers, a UserUnit multiply and
#     the MuPDF rect normalisation: a handful of half-ulps). Observed maximum on
#     the synthetic matrix (300 random boxes x rotation x UserUnit x CropBox x
#     origin): 1.5 ulp. A real orientation disagreement differs by whole extents,
#     orders of magnitude above 4 ulp.
#   * EDGE_QUANTISATION_ULPS: how far from the declared extent edge a coordinate
#     that was authored exactly on the edge can land after a content-stream
#     float32 parse, a cm scale/translate and the rect subtraction (each
#     <= 0.5 ulp). Observed maximum over 6600 synthetic cm-authored edge ends: 3
#     ulp, so 8 leaves a 2.7x margin. At A0 scale (3370 pt) the bound is ~2e-3 pt.
CROSS_CHECK_ULPS = 4
EDGE_QUANTISATION_ULPS = 8

# ---- reason / note codes (status-bearing reasons, then notes) -------------------
PAGE_FRAME_DOCUMENT_ID_MISSING = "page_frame_document_id_missing"
PAGE_FRAME_SOURCE_SHA256_INVALID = "page_frame_source_sha256_invalid"
PAGE_FRAME_REVISION_MISSING = "page_frame_revision_missing"
PAGE_FRAME_PAGE_NO_INVALID = "page_frame_page_no_invalid"
PAGE_FRAME_REVISION_MISMATCH = "page_frame_revision_does_not_match_document_and_source_hash"
PAGE_FRAME_PAGE_METADATA_UNREADABLE = "page_frame_page_metadata_unreadable"
PAGE_FRAME_DEGENERATE_EXTENT = "page_frame_degenerate_extent"
PAGE_FRAME_RECT_ORIGIN_NOT_ZERO = "page_frame_page_rect_origin_not_zero"
PAGE_FRAME_ROTATION_UNRESOLVABLE = "page_frame_rotation_unresolvable"
PAGE_FRAME_USER_UNIT_INVALID = "page_frame_user_unit_invalid"
PAGE_FRAME_ROTATION_RECT_ORIENTATION_CONFLICT = "page_frame_rotation_disagrees_with_page_rect_orientation"
PAGE_FRAME_RECT_MATCHES_NO_BOX_ORIENTATION = "page_frame_page_rect_matches_no_box_orientation"
PAGE_FRAME_ROTATE_ENTRY_NOT_ORTHOGONAL = "page_frame_rotate_entry_not_an_orthogonal_integer"
PAGE_FRAME_PAGE_NUMBER_MISMATCH = "page_frame_page_object_number_does_not_match_page_no"
PAGE_FRAME_OWNERSHIP_TEXT_NOT_UTF8 = "page_frame_ownership_text_not_utf8_encodable"

PAGE_FRAME_NOTE_NONSTANDARD_ROTATE_ENTRY = "page_frame_note_nonstandard_rotate_entry"
PAGE_FRAME_NOTE_ROTATION_NORMALISED = "page_frame_note_rotation_normalised"
PAGE_FRAME_NOTE_USER_UNIT_UNREADABLE = "page_frame_note_user_unit_unreadable"
PAGE_FRAME_NOTE_BOXES_UNREADABLE = "page_frame_note_boxes_unreadable"
PAGE_FRAME_NOTE_ORIENTATION_CROSS_CHECK_SKIPPED = "page_frame_note_orientation_cross_check_skipped"
PAGE_FRAME_NOTE_CROPBOX_EXCEEDS_MEDIABOX = "page_frame_note_cropbox_exceeds_mediabox"
PAGE_FRAME_NOTE_ROTATED_DISPLAY_DIFFERS_FROM_NATIVE = "page_frame_note_display_extent_differs_from_native"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


class FrameSpace(str, Enum):
    """Coordinate space an extent or point is expressed in (NOT a unit vocabulary)."""

    NATIVE_PAGE_USER_SPACE = "native_page_user_space"
    DISPLAY_ROTATED_SPACE = "display_rotated_space"


# ---- numeric helpers ------------------------------------------------------------
def _canon_float(value: Any, name: str) -> float:
    """Fixed float rule: real number -> float64, reject bool/non-finite, -0.0 -> 0.0.

    No rounding is applied. Values that come from PyMuPDF are float32 values that
    are exactly representable as float64, so repr() of the float64 is the
    shortest round-trip text and is identical on every platform.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a real number")
    out = float(value)
    if not math.isfinite(out):
        raise ValueError(f"{name} must be finite")
    return out + 0.0  # -0.0 + 0.0 == +0.0


def float32_ulp(value: float) -> float:
    """Spacing of float32 numbers at ``value`` (normal range); 0.0 for 0."""
    magnitude = abs(float(value))
    if magnitude == 0.0 or not math.isfinite(magnitude):
        return 0.0
    _, exponent = math.frexp(magnitude)  # magnitude = m * 2**exponent, m in [0.5, 1)
    return 2.0 ** (exponent - 1 - 23)


def normalise_rotation(value: Any) -> Optional[int]:
    """Normalise a rotation in degrees to 0/90/180/270, or None if not orthogonal."""
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if value % 90 != 0:
        return None
    return value % 360


# ---- typed points and extents ---------------------------------------------------
@dataclass(frozen=True)
class NativePoint:
    """A point in NATIVE_PAGE_USER_SPACE."""

    x: float
    y: float
    SPACE: ClassVar[FrameSpace] = FrameSpace.NATIVE_PAGE_USER_SPACE

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _canon_float(self.x, "x"))
        object.__setattr__(self, "y", _canon_float(self.y, "y"))


@dataclass(frozen=True)
class DisplayPoint:
    """A point in DISPLAY_ROTATED_SPACE."""

    x: float
    y: float
    SPACE: ClassVar[FrameSpace] = FrameSpace.DISPLAY_ROTATED_SPACE

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _canon_float(self.x, "x"))
        object.__setattr__(self, "y", _canon_float(self.y, "y"))


def _positive(value: Any, name: str) -> float:
    out = _canon_float(value, name)
    if out <= 0.0:
        raise ValueError(f"{name} must be positive")
    return out


@dataclass(frozen=True)
class NativePageExtent:
    """Box (0, 0, width, height) in NATIVE_PAGE_USER_SPACE. Not iterable."""

    width: float
    height: float
    SPACE: ClassVar[FrameSpace] = FrameSpace.NATIVE_PAGE_USER_SPACE

    def __post_init__(self) -> None:
        object.__setattr__(self, "width", _positive(self.width, "width"))
        object.__setattr__(self, "height", _positive(self.height, "height"))

    def contains(self, point: NativePoint, *, tol: float) -> bool:
        """True if ``point`` lies in the closed box, allowing ``tol`` slack."""
        return _native_contains(self, point, tol=tol)

    def point_on_edge(self, point: NativePoint, *, tol: float) -> bool:
        """True if ``point`` is inside the box (within ``tol``) and within ``tol``
        of one of its four edges. Unlike an OR over the four edge *lines*, a point
        outside the box never counts as on an edge."""
        return _native_point_on_edge(self, point, tol=tol)


@dataclass(frozen=True)
class DisplayPageExtent:
    """Box (0, 0, width, height) in DISPLAY_ROTATED_SPACE. Not iterable.

    Deliberately has no containment or boundary helper: geometry that lives in
    the native space must be converted explicitly before it can be related to it.
    """

    width: float
    height: float
    SPACE: ClassVar[FrameSpace] = FrameSpace.DISPLAY_ROTATED_SPACE

    def __post_init__(self) -> None:
        object.__setattr__(self, "width", _positive(self.width, "width"))
        object.__setattr__(self, "height", _positive(self.height, "height"))


def _require_tol(tol: Any) -> float:
    out = _canon_float(tol, "tol")
    if out < 0.0:
        raise ValueError("tol must be non-negative")
    return out


def _native_contains(extent: Any, point: Any, *, tol: float) -> bool:
    if not isinstance(extent, NativePageExtent):
        raise TypeError("a NativePageExtent is required; display extents cannot be used here")
    if not isinstance(point, NativePoint):
        raise TypeError("a NativePoint is required; display points cannot be used here")
    t = _require_tol(tol)
    return (-t <= point.x <= extent.width + t) and (-t <= point.y <= extent.height + t)


def _native_point_on_edge(extent: Any, point: Any, *, tol: float) -> bool:
    if not _native_contains(extent, point, tol=tol):
        return False
    t = _require_tol(tol)
    return (
        abs(point.x) <= t
        or abs(point.x - extent.width) <= t
        or abs(point.y) <= t
        or abs(point.y - extent.height) <= t
    )


def native_point_inside(extent: NativePageExtent, point: NativePoint, *, tol: float) -> bool:
    """Containment helper. Native types only; TypeError for anything else."""
    return _native_contains(extent, point, tol=tol)


def native_point_on_edge(extent: NativePageExtent, point: NativePoint, *, tol: float) -> bool:
    """Boundary helper. Native types only; TypeError for anything else."""
    return _native_point_on_edge(extent, point, tol=tol)


# ---- explicit conversions (exact double arithmetic, NOT fitz.Matrix) --------------
def _rotation_or_raise(rotation: Any) -> int:
    norm = normalise_rotation(rotation)
    if norm is None:
        raise ValueError("rotation must be an orthogonal multiple of 90 degrees")
    return norm


def display_extent_for(native_extent: NativePageExtent, rotation: int) -> DisplayPageExtent:
    """Display extent of a page whose native extent and rotation are known."""
    if not isinstance(native_extent, NativePageExtent):
        raise TypeError("a NativePageExtent is required")
    if _rotation_or_raise(rotation) in (90, 270):
        return DisplayPageExtent(width=native_extent.height, height=native_extent.width)
    return DisplayPageExtent(width=native_extent.width, height=native_extent.height)


def native_extent_for(display_extent: DisplayPageExtent, rotation: int) -> NativePageExtent:
    """Native extent of a page whose display extent and rotation are known."""
    if not isinstance(display_extent, DisplayPageExtent):
        raise TypeError("a DisplayPageExtent is required")
    if _rotation_or_raise(rotation) in (90, 270):
        return NativePageExtent(width=display_extent.height, height=display_extent.width)
    return NativePageExtent(width=display_extent.width, height=display_extent.height)


def native_to_display(point: NativePoint, *, native_extent: NativePageExtent, rotation: int) -> DisplayPoint:
    """Map a native point to display space for /Rotate ``rotation`` (clockwise).

    With native width w and height h: 0 -> (x, y); 90 -> (h - y, x);
    180 -> (w - x, h - y); 270 -> (y, w - x). Pure double arithmetic on the
    declared (UserUnit-scaled) extent. ``page.rotation_matrix`` is NOT UserUnit
    aware (its translation uses the unscaled extent), so it agrees with this
    function only for unscaled points: ``rotation_matrix(p) * user_unit ==
    native_to_display(p * user_unit)`` within ``4 * float32_ulp(max(w, h))``.
    """
    if not isinstance(point, NativePoint):
        raise TypeError("a NativePoint is required")
    if not isinstance(native_extent, NativePageExtent):
        raise TypeError("a NativePageExtent is required")
    rot = _rotation_or_raise(rotation)
    w, h, x, y = native_extent.width, native_extent.height, point.x, point.y
    if rot == 0:
        return DisplayPoint(x, y)
    if rot == 90:
        return DisplayPoint(h - y, x)
    if rot == 180:
        return DisplayPoint(w - x, h - y)
    return DisplayPoint(y, w - x)


def display_to_native(point: DisplayPoint, *, display_extent: DisplayPageExtent, rotation: int) -> NativePoint:
    """Inverse of :func:`native_to_display`, from the DISPLAY extent (vw, vh):
    0 -> (x, y); 90 -> (y, vw - x); 180 -> (vw - x, vh - y); 270 -> (vh - y, x)."""
    if not isinstance(point, DisplayPoint):
        raise TypeError("a DisplayPoint is required")
    if not isinstance(display_extent, DisplayPageExtent):
        raise TypeError("a DisplayPageExtent is required")
    rot = _rotation_or_raise(rotation)
    vw, vh, x, y = display_extent.width, display_extent.height, point.x, point.y
    if rot == 0:
        return NativePoint(x, y)
    if rot == 90:
        return NativePoint(y, vw - x)
    if rot == 180:
        return NativePoint(vw - x, vh - y)
    return NativePoint(vh - y, x)


# ---- descriptor -----------------------------------------------------------------
def _box_plain(box: Optional[tuple]) -> Optional[list]:
    return None if box is None else [float(v) for v in box]


def _extent_plain(extent: Any) -> Optional[dict]:
    if extent is None:
        return None
    return {
        "coordinate_space": extent.SPACE.value,
        "height": extent.height,
        "width": extent.width,
    }


@dataclass(frozen=True)
class PageFrameDescriptor:
    """Immutable, deterministic page-frame provenance record (no authority)."""

    frame_id: str
    document_id: str
    source_sha256: str
    revision: str
    page_no: Optional[int]
    status: EvidenceResolutionStatus
    reason_codes: tuple
    note_codes: tuple
    declared_coordinate_space: FrameSpace
    unit: str
    rotation: Optional[int]
    rotation_reported: Optional[int]
    rotate_entry: Optional[str]
    user_unit: Optional[float]
    native_extent: Optional[NativePageExtent]
    display_extent: Optional[DisplayPageExtent]
    extent_source: Optional[str]
    edge_quantisation_pt: Optional[float]
    mediabox_pdf_y_up: Optional[tuple]
    cropbox_pymupdf_y_down_from_mediabox_top: Optional[tuple]
    schema_version: str = PAGE_FRAME_SHADOW_SCHEMA_VERSION

    # Explicit class-level statement, also serialised.
    MEASUREMENT_AUTHORITY: ClassVar[bool] = False
    RECORD_KIND: ClassVar[str] = "page_frame_provenance_record"

    def __post_init__(self) -> None:
        if not isinstance(self.status, EvidenceResolutionStatus):
            raise TypeError("status must be an EvidenceResolutionStatus")
        object.__setattr__(self, "reason_codes", tuple(self.reason_codes))
        object.__setattr__(self, "note_codes", tuple(self.note_codes))
        if self.status is EvidenceResolutionStatus.RAW:
            if self.native_extent is None or self.display_extent is None or self.rotation is None:
                raise ValueError("a coherent (RAW) frame requires rotation and both extents")
            if self.reason_codes:
                raise ValueError("a coherent (RAW) frame carries no reason codes")
        else:
            if self.native_extent is not None:
                raise ValueError("a non-coherent frame must not expose a native extent")
            if not self.reason_codes:
                raise ValueError("a non-coherent frame requires a reason code")
        if self.frame_id != _compute_frame_id(self):
            raise ValueError("frame_id does not match the frame facts")

    @property
    def page_id(self) -> Optional[str]:
        return None if self.page_no is None else str(self.page_no)

    @property
    def is_coherent(self) -> bool:
        return self.status is EvidenceResolutionStatus.RAW and self.native_extent is not None

    def require_native_extent(self) -> NativePageExtent:
        """The native extent, or ValueError if the frame is not coherent."""
        if not self.is_coherent:
            raise ValueError("page frame is not coherent: " + ",".join(self.reason_codes))
        return self.native_extent  # type: ignore[return-value]

    def to_display(self, point: NativePoint) -> DisplayPoint:
        return native_to_display(point, native_extent=self.require_native_extent(), rotation=self.rotation)  # type: ignore[arg-type]

    def to_native(self, point: DisplayPoint) -> NativePoint:
        self.require_native_extent()
        return display_to_native(point, display_extent=self.display_extent, rotation=self.rotation)  # type: ignore[arg-type]

    def _payload(self) -> dict:
        return _payload_of(self)

    def to_plain(self) -> dict:
        """Sorted, JSON-safe plain dict. Floats follow the fixed rule in ``_canon_float``."""
        out = dict(_payload_of(self))
        out["frame_id"] = self.frame_id
        return dict(sorted(out.items()))

    def to_json(self) -> str:
        return json.dumps(self.to_plain(), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _payload_of(d: PageFrameDescriptor) -> dict:
    return {
        "cropbox_pymupdf_y_down_from_mediabox_top": _box_plain(d.cropbox_pymupdf_y_down_from_mediabox_top),
        "declared_coordinate_space": d.declared_coordinate_space.value,
        "display_extent": _extent_plain(d.display_extent),
        "document_id": d.document_id,
        "edge_quantisation_pt": d.edge_quantisation_pt,
        "extent_source": d.extent_source,
        "measurement_authority": PageFrameDescriptor.MEASUREMENT_AUTHORITY,
        "mediabox_pdf_y_up": _box_plain(d.mediabox_pdf_y_up),
        "native_extent": _extent_plain(d.native_extent),
        "note_codes": list(d.note_codes),
        "page_no": d.page_no,
        "reason_codes": list(d.reason_codes),
        "record_kind": PageFrameDescriptor.RECORD_KIND,
        "revision": d.revision,
        "rotate_entry": d.rotate_entry,
        "rotation": d.rotation,
        "rotation_reported": d.rotation_reported,
        "schema_version": d.schema_version,
        "source_sha256": d.source_sha256,
        "status": d.status.value,
        "unit": d.unit,
        "user_unit": d.user_unit,
    }


def _compute_frame_id(d: PageFrameDescriptor) -> str:
    return stable_contract_id("page_frame", _payload_of(d), digest_chars=32)


def revision_id_for(document_id: str, source_sha256: str) -> str:
    """Revision id exactly as the source-observation producers define it."""
    return stable_contract_id(
        "source_revision",
        {"document_id": document_id, "source_sha256": source_sha256},
        digest_chars=32,
    )


# ---- page reading (duck-typed; only read access) ---------------------------------
def _box_tuple(box: Any) -> Optional[tuple]:
    try:
        return tuple(_canon_float(v, "box") for v in (box.x0, box.y0, box.x1, box.y1))
    except Exception:
        return None


def _utf8_encodable(text: str) -> bool:
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _read_user_unit(page: Any) -> tuple:
    """(value, state) where state is ok / unreadable / invalid. Absent key -> 1.0."""
    parent = getattr(page, "parent", None)
    xref = getattr(page, "xref", None)
    getter = getattr(parent, "xref_get_key", None)
    if not callable(getter) or isinstance(xref, bool) or not isinstance(xref, int):
        return None, "unreadable"
    try:
        kind, raw = getter(xref, "UserUnit")
    except Exception:
        return None, "unreadable"
    if kind == "null":
        return 1.0, "ok"
    try:
        value = float(raw)
    except (TypeError, ValueError):
        return None, "invalid"
    if not math.isfinite(value) or value <= 0.0:
        return None, "invalid"
    return value, "ok"


def _read_rotate_entry(page: Any) -> Optional[str]:
    """The page dictionary's own /Rotate text, or None if absent/inherited/unreadable."""
    parent = getattr(page, "parent", None)
    xref = getattr(page, "xref", None)
    getter = getattr(parent, "xref_get_key", None)
    if not callable(getter) or isinstance(xref, bool) or not isinstance(xref, int):
        return None
    try:
        kind, raw = getter(xref, "Rotate")
    except Exception:
        return None
    return None if kind == "null" else str(raw)


def _nonstandard_rotate_entry(entry: str) -> bool:
    """True unless ``entry`` reads as an exact orthogonal integer (90, 90.0, +90, -270 ...)."""
    try:
        value = float(entry)
    except (TypeError, ValueError):
        return True
    if not math.isfinite(value):
        return True
    return not (value == int(value) and int(value) % 90 == 0)


_MAX_PARENT_DEPTH = 32


def _read_inherited_rotate_entry(page: Any) -> Optional[str]:
    """/Rotate text inherited from the page-tree ancestors when the page dictionary
    has no /Rotate of its own, else None. Read-only; a broken or cyclic chain gives None.

    MuPDF rounds a non-orthogonal /Rotate in ways that ``page.rotation`` and the
    orientation of ``page.rect`` cannot always reveal (for example 135 renders as
    180 while ``page.rotation`` reads 0 and the rect keeps its size), so the entry
    itself must be inspected, own or inherited.
    """
    parent = getattr(page, "parent", None)
    xref = getattr(page, "xref", None)
    getter = getattr(parent, "xref_get_key", None)
    if not callable(getter) or isinstance(xref, bool) or not isinstance(xref, int):
        return None
    try:
        if getter(xref, "Rotate")[0] != "null":
            return None  # the page's own entry wins; it is inspected separately
        seen = {xref}
        node = xref
        for _ in range(_MAX_PARENT_DEPTH):
            kind, raw = getter(node, "Parent")
            if kind != "xref":
                return None
            node = int(str(raw).split()[0])
            if node in seen:
                return None
            seen.add(node)
            kind, raw = getter(node, "Rotate")
            if kind != "null":
                return str(raw)
    except Exception:
        return None
    return None


def _effective_box(mediabox: tuple, cropbox: tuple, *, tol: float) -> Optional[tuple]:
    """(width, height, cropbox_exceeds_mediabox) of CropBox intersect MediaBox,
    in unscaled PDF points, or None if the intersection is empty.

    PyMuPDF reports ``page.cropbox`` with x absolute but y measured down from the
    MediaBox top, so y is converted back to PDF y-up before intersecting.
    """
    mx0, my0, mx1, my1 = mediabox
    cx0, cy0_down, cx1, cy1_down = cropbox
    cy0, cy1 = my1 - cy1_down, my1 - cy0_down
    width = min(mx1, cx1) - max(mx0, cx0)
    height = min(my1, cy1) - max(my0, cy0)
    if width <= 0.0 or height <= 0.0:
        return None
    exceeds = cx0 < mx0 - tol or cx1 > mx1 + tol or cy0 < my0 - tol or cy1 > my1 + tol
    return width, height, exceeds


def _make(
    *,
    document_id: str,
    source_sha256: str,
    revision: str,
    page_no: Optional[int],
    status: EvidenceResolutionStatus,
    reasons,
    notes=(),
    rotation: Optional[int] = None,
    rotation_reported: Optional[int] = None,
    rotate_entry: Optional[str] = None,
    user_unit: Optional[float] = None,
    native_extent: Optional[NativePageExtent] = None,
    display_extent: Optional[DisplayPageExtent] = None,
    extent_source: Optional[str] = None,
    edge_quantisation_pt: Optional[float] = None,
    mediabox: Optional[tuple] = None,
    cropbox: Optional[tuple] = None,
) -> PageFrameDescriptor:
    draft = object.__new__(PageFrameDescriptor)
    values = dict(
        frame_id="",
        document_id=document_id,
        source_sha256=source_sha256,
        revision=revision,
        page_no=page_no,
        status=status,
        reason_codes=tuple(sorted(set(reasons))),
        note_codes=tuple(sorted(set(notes))),
        declared_coordinate_space=FrameSpace.NATIVE_PAGE_USER_SPACE,
        unit=UNIT_PDF_POINTS,
        rotation=rotation,
        rotation_reported=rotation_reported,
        rotate_entry=rotate_entry,
        user_unit=user_unit,
        native_extent=native_extent,
        display_extent=display_extent,
        extent_source=extent_source,
        edge_quantisation_pt=edge_quantisation_pt,
        mediabox_pdf_y_up=mediabox,
        cropbox_pymupdf_y_down_from_mediabox_top=cropbox,
        schema_version=PAGE_FRAME_SHADOW_SCHEMA_VERSION,
    )
    for name, value in values.items():
        object.__setattr__(draft, name, value)
    frame_id = _compute_frame_id(draft)
    values["frame_id"] = frame_id
    return PageFrameDescriptor(**values)


def describe_page_frame(
    page: Any,
    *,
    document_id: str,
    source_sha256: str,
    revision: str,
    page_no: int,
) -> PageFrameDescriptor:
    """Describe one page's frame. Read-only on ``page``; never raises for bad pages.

    ABSTAINED: missing/blank ownership input, unreadable or degenerate page
    metadata, unresolvable rotation, invalid UserUnit. CONFLICT: revision does not
    equal the producer definition for (document_id, source_sha256), or the
    normalised rotation disagrees with the orientation of ``page.rect`` relative
    to the effective (CropBox intersect MediaBox, UserUnit-scaled) box, or the page's
    own or inherited /Rotate entry is not an exact orthogonal integer, or
    ``page.number`` (when it is an int) is not ``page_no - 1``. Otherwise RAW: a
    recorded page-metadata observation, never CORROBORATED.

    Binding limit: the descriptor cannot verify that ``page`` belongs to the document
    whose ``source_sha256`` is supplied; that binding is the caller's responsibility.
    """
    doc_id = document_id.strip() if isinstance(document_id, str) else ""
    sha = source_sha256.strip().lower() if isinstance(source_sha256, str) else ""
    rev = revision.strip() if isinstance(revision, str) else ""
    number = page_no if (isinstance(page_no, int) and not isinstance(page_no, bool) and page_no >= 1) else None

    ownership_reasons = []
    if not all(_utf8_encodable(v) for v in (doc_id, sha, rev)):
        # Text that cannot be encoded cannot be hashed into a frame id; never store it.
        ownership_reasons.append(PAGE_FRAME_OWNERSHIP_TEXT_NOT_UTF8)
        doc_id, sha, rev = (v if _utf8_encodable(v) else "" for v in (doc_id, sha, rev))
    if not doc_id:
        ownership_reasons.append(PAGE_FRAME_DOCUMENT_ID_MISSING)
    if not _SHA256_RE.match(sha):
        ownership_reasons.append(PAGE_FRAME_SOURCE_SHA256_INVALID)
    if not rev:
        ownership_reasons.append(PAGE_FRAME_REVISION_MISSING)
    if number is None:
        ownership_reasons.append(PAGE_FRAME_PAGE_NO_INVALID)
    common = dict(document_id=doc_id, source_sha256=sha, revision=rev, page_no=number)
    if ownership_reasons:
        return _make(status=EvidenceResolutionStatus.ABSTAINED, reasons=ownership_reasons, **common)
    if rev != revision_id_for(doc_id, sha):
        return _make(status=EvidenceResolutionStatus.CONFLICT, reasons=[PAGE_FRAME_REVISION_MISMATCH], **common)
    try:
        page_index = getattr(page, "number", None)
    except Exception:
        page_index = None
    if isinstance(page_index, int) and not isinstance(page_index, bool) and page_index + 1 != number:
        # The page object says it is a different page than the one being claimed.
        return _make(status=EvidenceResolutionStatus.CONFLICT, reasons=[PAGE_FRAME_PAGE_NUMBER_MISMATCH], **common)

    # -- read the page (read access only) --
    try:
        rect = page.rect
        rect_x0, rect_y0 = _canon_float(rect.x0, "rect.x0"), _canon_float(rect.y0, "rect.y0")
        rect_w, rect_h = _canon_float(rect.width, "rect.width"), _canon_float(rect.height, "rect.height")
        reported = page.rotation
    except Exception:
        return _make(status=EvidenceResolutionStatus.ABSTAINED, reasons=[PAGE_FRAME_PAGE_METADATA_UNREADABLE], **common)

    notes = []
    mediabox = cropbox = None
    try:
        mediabox = _box_tuple(page.mediabox)
        cropbox = _box_tuple(page.cropbox)
    except Exception:
        mediabox = cropbox = None
    if mediabox is None or cropbox is None:
        notes.append(PAGE_FRAME_NOTE_BOXES_UNREADABLE)
        mediabox = cropbox = None
    rotate_entry = _read_rotate_entry(page)
    effective_entry = rotate_entry if rotate_entry is not None else _read_inherited_rotate_entry(page)
    nonorthogonal_entry = effective_entry is not None and _nonstandard_rotate_entry(effective_entry)
    if nonorthogonal_entry:
        notes.append(PAGE_FRAME_NOTE_NONSTANDARD_ROTATE_ENTRY)
    user_unit, uu_state = _read_user_unit(page)

    rotation_reported = reported if (isinstance(reported, int) and not isinstance(reported, bool)) else None
    facts = dict(
        rotation_reported=rotation_reported,
        rotate_entry=rotate_entry,
        user_unit=user_unit,
        mediabox=mediabox,
        cropbox=cropbox,
    )

    def abstain(code: str, *, display: Optional[DisplayPageExtent] = None, rotation: Optional[int] = None):
        return _make(
            status=EvidenceResolutionStatus.ABSTAINED,
            reasons=[code],
            notes=notes,
            display_extent=display,
            rotation=rotation,
            **facts,
            **common,
        )

    if rect_w <= 0.0 or rect_h <= 0.0:
        return abstain(PAGE_FRAME_DEGENERATE_EXTENT)
    display = DisplayPageExtent(width=rect_w, height=rect_h)
    if uu_state == "invalid":
        return abstain(PAGE_FRAME_USER_UNIT_INVALID, display=display)
    if uu_state == "unreadable":
        notes.append(PAGE_FRAME_NOTE_USER_UNIT_UNREADABLE)

    rotation = normalise_rotation(reported)
    if rotation is None:
        return abstain(PAGE_FRAME_ROTATION_UNRESOLVABLE, display=display)
    if rotation != reported:
        notes.append(PAGE_FRAME_NOTE_ROTATION_NORMALISED)

    native = native_extent_for(display, rotation)
    # Magnitude of the largest float32 quantity that takes part in native coordinates.
    magnitude = max(rect_w, rect_h)
    if mediabox is not None and user_unit is not None:
        magnitude = max(magnitude, user_unit * max(abs(v) for v in mediabox))

    # -- origin guard: native extent is defined as the box (0, 0, w, h) --
    origin_tol = CROSS_CHECK_ULPS * float32_ulp(magnitude)
    if abs(rect_x0) > origin_tol or abs(rect_y0) > origin_tol:
        return _make(
            status=EvidenceResolutionStatus.CONFLICT,
            reasons=[PAGE_FRAME_RECT_ORIGIN_NOT_ZERO],
            notes=notes,
            rotation=rotation,
            display_extent=display,
            **facts,
            **common,
        )

    # -- cross-check the normalised rotation against the orientation of page.rect --
    conflict_code = None
    effective = None
    tol = CROSS_CHECK_ULPS * float32_ulp(magnitude)
    if mediabox is not None and cropbox is not None and user_unit is not None:
        effective = _effective_box(mediabox, cropbox, tol=tol)
    if effective is None:
        notes.append(PAGE_FRAME_NOTE_ORIENTATION_CROSS_CHECK_SKIPPED)
    else:
        if effective[2]:
            notes.append(PAGE_FRAME_NOTE_CROPBOX_EXCEEDS_MEDIABOX)
        ew, eh = effective[0] * user_unit, effective[1] * user_unit
        if abs(native.width - ew) > tol or abs(native.height - eh) > tol:
            swapped_match = abs(native.width - eh) <= tol and abs(native.height - ew) <= tol
            conflict_code = (
                PAGE_FRAME_ROTATION_RECT_ORIENTATION_CONFLICT if swapped_match else PAGE_FRAME_RECT_MATCHES_NO_BOX_ORIENTATION
            )
    if conflict_code is None and nonorthogonal_entry:
        # MuPDF rounds a non-orthogonal /Rotate its own way; page.rotation and the rect
        # orientation cannot be trusted to show the rendered rotation (e.g. 135 renders
        # as 180 but reads 0 with an unswapped rect). Fail closed.
        conflict_code = PAGE_FRAME_ROTATE_ENTRY_NOT_ORTHOGONAL
    if conflict_code is not None:
        return _make(
            status=EvidenceResolutionStatus.CONFLICT,
            reasons=[conflict_code],
            notes=notes,
            rotation=rotation,
            display_extent=display,
            **facts,
            **common,
        )

    if rotation in (90, 270):
        notes.append(PAGE_FRAME_NOTE_ROTATED_DISPLAY_DIFFERS_FROM_NATIVE)
    return _make(
        status=EvidenceResolutionStatus.RAW,
        reasons=[],
        notes=notes,
        rotation=rotation,
        native_extent=native,
        display_extent=display,
        extent_source=EXTENT_SOURCE_PAGE_RECT_SWAPPED_FOR_ROTATION,
        edge_quantisation_pt=EDGE_QUANTISATION_ULPS * float32_ulp(magnitude),
        **facts,
        **common,
    )


__all__ = [
    "CROSS_CHECK_ULPS",
    "DisplayPageExtent",
    "DisplayPoint",
    "EDGE_QUANTISATION_ULPS",
    "EXTENT_SOURCE_PAGE_RECT_SWAPPED_FOR_ROTATION",
    "FrameSpace",
    "LEGAL_ROTATIONS",
    "NativePageExtent",
    "NativePoint",
    "PAGE_FRAME_SHADOW_SCHEMA_VERSION",
    "PageFrameDescriptor",
    "UNIT_PDF_POINTS",
    "describe_page_frame",
    "display_extent_for",
    "display_to_native",
    "float32_ulp",
    "native_extent_for",
    "native_point_inside",
    "native_point_on_edge",
    "native_to_display",
    "normalise_rotation",
    "revision_id_for",
]
