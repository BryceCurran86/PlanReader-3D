"""Source-native *shadow* witness for alternating filled graphic-scale bars.

This is NOT a scale resolver or a publication path. It does not accept viewport
or physical-measurement authority, and must never feed a FIRM quantity. Callers
must separately authenticate the PDF, native text, physical drawing viewport,
scale binding, and all competing scale candidates in existing authority modules.
No project, benchmark, filename, or expected quantity enters detection.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import re
from typing import Sequence

import fitz


_END_LABEL = re.compile(r"^([1-9]\d*)m$", re.IGNORECASE)


@dataclass(frozen=True)
class NativeFilledScaleBarShadow:
    source_sha256: str
    page_id: str
    drawing_indices: tuple[int, ...]
    text_witnesses: tuple[tuple[str, tuple[float, float, float, float]], ...]
    source_span_pt: float
    physical_span_mm: float
    points_per_mm: float


@dataclass(frozen=True)
class _Rect:
    index: int
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.y1 - self.y0


def _rect_from_native_fill(index: int, path: dict) -> _Rect | None:
    """Accept only opaque black source-painted axis-aligned rectangles."""
    if (
        path.get("type") != "f"
        or path.get("color") is not None
        or tuple(path.get("fill") or ()) != (0.0, 0.0, 0.0)
        or path.get("fill_opacity") != 1.0
    ):
        return None
    bounds = path.get("rect")
    if bounds is None:
        return None
    x0, y0, x1, y1 = tuple(float(v) for v in bounds)
    if not all(map(math.isfinite, (x0, y0, x1, y1))):
        return None
    if not (x1 > x0 + 1 and y1 > y0 + 0.1 and x1 - x0 >= 2 * (y1 - y0)):
        return None
    items = tuple(path.get("items") or ())
    if len(items) == 1 and items[0][0] == "re":
        box = fitz.Rect(items[0][1])
        if max(abs(a - b) for a, b in zip(box, (x0, y0, x1, y1))) > 1e-4:
            return None
    elif len(items) == 4 and all(item[0] == "l" for item in items):
        actual = set()
        for item in items:
            a, b = item[1], item[2]
            endpoints = ((float(a.x), float(a.y)), (float(b.x), float(b.y)))
            if not (
                (abs(endpoints[0][0] - endpoints[1][0]) <= 1e-4)
                != (abs(endpoints[0][1] - endpoints[1][1]) <= 1e-4)
            ):
                return None
            actual.add(tuple(sorted(endpoints)))
        corners = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
        expected = {tuple(sorted((corners[i], corners[(i + 1) % 4]))) for i in range(4)}
        if actual != expected:
            return None
    else:
        return None
    return _Rect(index, x0, y0, x1, y1)


def _adjacent(a: _Rect, b: _Rect) -> bool:
    tolerance = max(1e-4, a.width * 1e-5)
    if abs(a.x1 - b.x0) > tolerance or abs(a.width - b.width) > tolerance:
        return False
    if abs(a.height - b.height) > tolerance:
        return False
    # Alternating top and bottom strips must touch at a single common midline.
    if abs(a.y0 - b.y1) <= tolerance and abs(a.y1 - (b.y1 + a.height)) <= tolerance:
        return True
    if abs(a.y1 - b.y0) <= tolerance and abs(b.y1 - (a.y1 + a.height)) <= tolerance:
        return True
    return False


def _word_at_boundary(
    words: Sequence[tuple], expected: str, boundary_x: float, bar_bottom: float,
    block_width: float, block_height: float,
) -> tuple[str, tuple[float, float, float, float]] | None:
    tolerance = min(4.0, max(0.75, block_width * 0.15))
    hits = []
    for row in words:
        x0, y0, x1, y1, text = row[:5]
        if not (str(text).isdigit() or _END_LABEL.fullmatch(str(text))):
            continue
        if (
            abs((x0 + x1) / 2 - boundary_x) <= tolerance
            and bar_bottom - 0.5 <= y0 <= bar_bottom + max(12.0, 4 * block_height)
            and y1 > y0
        ):
            hits.append((str(text), (float(x0), float(y0), float(x1), float(y1))))
    # A competing numeric label at the SAME native boundary blocks proof,
    # even when the expected label is also present.
    return hits[0] if len(hits) == 1 and hits[0][0].lower() == expected.lower() else None


def _source_clip_receipts(page: fitz.Page) -> dict[int, tuple[dict, ...]]:
    """Retain active source clips for each native paint sequence."""
    active: dict[int, dict] = {}
    by_seq: dict[int, tuple[dict, ...]] = {}
    for path in page.get_drawings(extended=True):
        level = int(path.get("level", 0))
        for stale in tuple(active):
            if stale > level:
                del active[stale]
        if path.get("type") == "clip":
            active[level] = path
        elif isinstance(path.get("seqno"), int):
            by_seq[path["seqno"]] = tuple(
                active[key] for key in sorted(active) if key <= level
            )
    return by_seq


def _source_ink_visible(
    page: fitz.Page, path: dict, rect: _Rect,
    bboxlog: Sequence[tuple], paths_by_seq: dict[int, dict],
    clips_by_seq: dict[int, tuple[dict, ...]],
) -> bool:
    """Fail closed on hidden, later-overpainted, or clipped native fill."""
    seq = path.get("seqno")
    box = fitz.Rect(rect.x0, rect.y0, rect.x1, rect.y1)
    if not isinstance(seq, int) or not 0 <= seq < len(bboxlog):
        return False
    kind, painted = bboxlog[seq]
    if kind != "fill-path" or max(
        abs(a - b) for a, b in zip(fitz.Rect(painted), box)
    ) > 1e-3:
        return False

    # Source-native clips may be legitimate rectangular page/view clips.
    # Their actual geometry must contain the WHOLE bar, not only a bbox
    # enclosing an irregular clipped shape.
    for clip in clips_by_seq.get(seq, ()):
        scissor = clip.get("scissor")
        items = tuple(clip.get("items") or ())
        if scissor is None or not fitz.Rect(scissor).contains(box) or len(items) != 1:
            return False
        if items[0][0] == "re":
            clip_box = fitz.Rect(items[0][1])
        elif items[0][0] == "qu":
            clip_box = fitz.Rect(items[0][1].rect)
        else:
            return False
        if max(abs(a - b) for a, b in zip(clip_box, fitz.Rect(scissor))) > 1e-3:
            return False

    # Native drawing paths remain in get_drawings() even when subsequently
    # erased. A later overlapping fill, image, text or nonblack stroke
    # invalidates source visibility; black hairline outlines are retained.
    for later in range(seq + 1, len(bboxlog)):
        later_kind, later_box = bboxlog[later]
        if not box.intersects(fitz.Rect(later_box)):
            continue
        if later_kind == "stroke-path":
            stroke = paths_by_seq.get(later)
            if stroke is not None and tuple(stroke.get("color") or ()) == (0.0, 0.0, 0.0):
                continue
        return False

    # The final rendered ink must also survive clipping and graphics-state
    # operations. Nine interior samples avoid mistaking only an edge for a
    # source-visible filled rectangle. Rendering never grants scale authority.
    pix = page.get_pixmap(
        matrix=fitz.Matrix(4, 4), colorspace=fitz.csRGB,
        alpha=False, clip=box,
    )
    if pix.width < 3 or pix.height < 3:
        return False
    for fx in (0.2, 0.5, 0.8):
        for fy in (0.2, 0.5, 0.8):
            px = round((box.x0 + box.width * fx) * 4) - pix.x
            py = round((box.y0 + box.height * fy) * 4) - pix.y
            if not (0 <= px < pix.width and 0 <= py < pix.height):
                return False
            if max(pix.pixel(px, py)) > 50:
                return False
    return True


def find_native_filled_scale_bar_shadows(
    source_bytes: bytes, *, expected_source_sha256: str, page_id: str,
) -> tuple[NativeFilledScaleBarShadow, ...]:
    """Return ALL source-native bar witnesses, never elect or publish a scale.

    Expected SHA is a fail-closed integrity check, NOT source authority: the
    existing producer must authenticate that digest and source scope itself.
    """
    if type(source_bytes) is not bytes or not re.fullmatch(r"[0-9a-f]{64}", expected_source_sha256):
        return ()
    if hashlib.sha256(source_bytes).hexdigest() != expected_source_sha256:
        return ()
    if not str(page_id).isdigit() or int(page_id) < 1:
        return ()
    try:
        document = fitz.open(stream=source_bytes, filetype="pdf")
    except (ValueError, RuntimeError, fitz.FileDataError):
        return ()
    try:
        if int(page_id) > document.page_count:
            return ()
        page = document[int(page_id) - 1]
        drawings = tuple(page.get_drawings())
        rectangles = tuple(
            rect for i, path in enumerate(drawings)
            if (rect := _rect_from_native_fill(i, path)) is not None
        )
        words = tuple(page.get_text("words"))
        by_left = sorted(rectangles, key=lambda rect: (rect.x0, rect.y0, rect.index))
        visibility_context = None
        results: dict[tuple[int, ...], NativeFilledScaleBarShadow] = {}
        for start in by_left:
            chain = [start]
            used = {start.index}
            for _ in range(20):
                nexts = [rect for rect in by_left if rect.index not in used and _adjacent(chain[-1], rect)]
                if len(nexts) != 1:
                    break  # competing paint or missing block is never guessed
                chain.append(nexts[0])
                used.add(nexts[0].index)
            n = len(chain)
            if not 2 <= n <= 20:
                continue
            # Reject interior subsets of a longer bar; they cannot start at 0.
            bottom = max(rect.y1 for rect in chain)
            label_witnesses = []
            for j in range(n + 1):
                expected = str(j) if j < n else f"{n}m"
                x = chain[0].x0 if j == 0 else chain[j - 1].x1
                witness = _word_at_boundary(words, expected, x, bottom, start.width, start.height)
                if witness is None:
                    break
                label_witnesses.append(witness)
            if len(label_witnesses) != n + 1:
                continue
            if visibility_context is None:
                visibility_context = (
                    tuple(page.get_bboxlog()),
                    {p["seqno"]: p for p in drawings if isinstance(p.get("seqno"), int)},
                    _source_clip_receipts(page),
                )
            bboxlog, paths_by_seq, clips_by_seq = visibility_context
            if not all(
                _source_ink_visible(
                    page, drawings[rect.index], rect,
                    bboxlog, paths_by_seq, clips_by_seq,
                ) for rect in chain
            ):
                continue
            ids = tuple(rect.index for rect in chain)
            span = chain[-1].x1 - chain[0].x0
            physical = float(n * 1000)
            if not math.isfinite(span) or span <= 0:
                continue
            results[ids] = NativeFilledScaleBarShadow(
                source_sha256=expected_source_sha256,
                page_id=str(page_id),
                drawing_indices=ids,
                text_witnesses=tuple(label_witnesses),
                source_span_pt=span,
                physical_span_mm=physical,
                points_per_mm=span / physical,
            )
        return tuple(results[key] for key in sorted(results))
    finally:
        document.close()


__all__ = ["NativeFilledScaleBarShadow", "find_native_filled_scale_bar_shadows"]
