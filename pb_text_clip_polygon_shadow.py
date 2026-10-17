"""Shadow-only clip-state verdicts for native text: exact polygon clips and rotated pages, with every other rule unchanged.

Why this exists. ``pb_pdf_text_integrity_authority._text_clip_reasons`` blocks a word with ``text_clip_state_unresolved`` in three
situations that are conservative rather than ambiguous: (1) the page is rotated (every word of a rotated drawing sheet is blocked
before any geometry is looked at), (2) a clip that may apply is a polygon drawn as straight segments (a union of rectangles, a stepped
outline) and not one rectangle, and (3) genuinely ambiguous structure. On the original PDFs (#2849 and this module's measurement) all
words of Maryborough's rotated sheets are blocked only by (1), and Lot16's blocked words are blocked by (2).

What it does. It reuses the authority's own clip model (the extended-drawings hierarchy, the may-apply / must-apply sets, the
neighbouring-path argument, the exact-rectangle test, the disjointness exception and the 0.5 pt tolerance) and changes exactly two
things, each only when it can be PROVEN:

* a clip made only of straight segments is described by two exact polygons: a region every point of which is certainly inside the clip
  and a region outside of which every point is certainly outside it. One ring, several rings under the even-odd rule, and several
  rings of known equal winding under the non-zero rule give the same region for both. Several rings under the non-zero rule whose
  winding PyMuPDF does not expose (rectangles and quads) give the odd-cover region (certainly inside whatever the windings are) and the
  union (certainly outside beyond it). A word wholly inside the first is not clipped, a word wholly outside the second is clipped by a
  must-apply clip, anything else stays unresolved. A curve, a non-simple ring, or a malformed path is never treated as a polygon and
  keeps the authority's verdict;
* a rotated page is judged like an unrotated one only when this process has verified, on synthetic pages of known geometry rotated by
  90, 180 and 270 degrees, that the installed PyMuPDF reports extracted words, the text trace, the clip scissors and the clip paths
  (including their polygon vertices) in one and the same unrotated native frame. If that check fails, or the page rotation is not a
  multiple of 90, rotated pages stay unresolved.

What it deliberately does not do. It does not trust glyph mapping, Unicode, occlusion, optional content or any other integrity condition:
it answers only the clip question, it is not called by a live path and it changes no receipt or authority verdict. Exact rectangles
follow the authority's rules unchanged, and a word the authority proves clipped is never reported unclipped here (a differential test
enforces it).
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from dataclasses import dataclass
from typing import Dict, List, Mapping, Optional, Sequence, Tuple

import fitz
from shapely.geometry import Polygon, box
from shapely.prepared import prep

import pb_pdf_text_integrity_authority as authority

TEXT_CLIP_SHADOW_SCHEMA_VERSION = "2.0.0"

UNCLIPPED = "unclipped_proven"
CLIPPED = "clipped_proven"
UNRESOLVED = "unresolved"

REASON_ROTATED_FRAMES_UNVERIFIED = "rotated_page_frame_conventions_unverified"
REASON_CLIP_NOT_AN_EXACT_POLYGON = "clip_is_not_an_exact_straight_segment_polygon"
REASON_CLIP_STRUCTURE_UNRECONCILED = "clip_structure_unreconciled"
REASON_SUBJECT_DEGENERATE = "text_subject_box_is_degenerate"

_TOL = authority.PDF_TEXT_GEOMETRY_TOLERANCE_PT
_POINT_TOL = 1.0e-3
MAX_CLIP_RINGS = 64                                  # a clip made of more subpaths is not analysed (keeps the polygon algebra bounded)
_CACHE_PREFIX = "text_clip_shadow_"


@dataclass(frozen=True)
class ClipVerdict:
    verdict: str
    reasons: Tuple[str, ...]
    shadow_only: bool = True
    live_effect: bool = False
    text_trust_granted: bool = False


# ---------------------------------------------------------------------------------------------------------------------------------
# Frame conventions of the installed PyMuPDF, proven on rotated synthetic pages
# ---------------------------------------------------------------------------------------------------------------------------------
_FIXTURE_CLIP = (50.0, 50.0, 250.0, 120.0)                                   # native top-left frame
_FIXTURE_TEXT_ORIGIN = (60.0, 100.0)
_FIXTURE_TRIANGLE = ((300.0, 100.0), (500.0, 100.0), (400.0, 20.0))          # native top-left frame, drawn with straight segments
_FIXTURE_WIDTH, _FIXTURE_HEIGHT = 600.0, 400.0
_frame_check_cache: Dict[int, bool] = {}


def scene_document(content: bytes, rotation: int = 0, *, width: float = 600.0, height: float = 400.0) -> "fitz.Document":
    """A one-page PDF whose content stream is exactly ``content`` (font resource ``/helv``), optionally rotated."""
    document = fitz.open()
    page = document.new_page(width=width, height=height)
    page.insert_font(fontname="helv")
    xref = document.get_new_xref()
    document.update_object(xref, "<<>>")
    document.update_stream(xref, content)
    page.set_contents(xref)
    if rotation:
        page.set_rotation(rotation)
    return document


def _fixture_document(rotation: int) -> "fitz.Document":
    x0, y0, x1, y1 = _FIXTURE_CLIP
    h = _FIXTURE_HEIGHT
    triangle = " ".join(f"{x} {h - y} {'m' if i == 0 else 'l'}" for i, (x, y) in enumerate(_FIXTURE_TRIANGLE))
    content = (f"q {x0} {h - y1} {x1 - x0} {y1 - y0} re W n BT /helv 14 Tf {_FIXTURE_TEXT_ORIGIN[0]} {h - _FIXTURE_TEXT_ORIGIN[1]} Td (ABC) Tj ET Q "
               f"q {triangle} h W n 0 0 5 5 re f Q").encode("ascii")
    return scene_document(content, rotation)


def _same_vertices(ring: Sequence[Tuple[float, float]], expected: Sequence[Tuple[float, float]]) -> bool:
    """Ring (closed or not, any start) has exactly the expected vertices, up to the library tolerance."""
    points = list(ring)
    if len(points) > 1 and points[0] == points[-1]:
        points = points[:-1]
    if len(points) != len(expected):
        return False
    return all(any(abs(p[0] - e[0]) <= _TOL and abs(p[1] - e[1]) <= _TOL for p in points) for e in expected)


def native_frame_conventions_verified(rotation: int) -> bool:
    """True only when words, text trace, clip scissors and clip polygons of a rotated synthetic page share the unrotated native frame."""
    rotation = int(rotation) % 360
    if rotation == 0:
        return True
    if rotation not in (90, 180, 270):
        return False
    if rotation in _frame_check_cache:
        return _frame_check_cache[rotation]
    ok = False
    document = reference = None
    try:
        reference = _fixture_document(0)
        reference_words = reference[0].get_text("words")
        reference_trace = reference[0].get_texttrace()
        document = _fixture_document(rotation)
        page = document[0]
        words = page.get_text("words")
        trace = page.get_texttrace()
        clips = [e for e in page.get_drawings(extended=True) if e.get("type") == "clip"]
        if (len(words) == len(reference_words) == 1
                and len(trace) == len(reference_trace) == 1
                and len(clips) == 2 and page.rotation == rotation):
            word_box = tuple(float(v) for v in words[0][:4])
            trace_box = tuple(float(v) for v in trace[0]["bbox"])
            scissor = tuple(float(v) for v in fitz.Rect(clips[0]["scissor"]))
            native = fitz.Rect(0.0, 0.0, _FIXTURE_WIDTH, _FIXTURE_HEIGHT)
            inside_native = all(native.x0 - _TOL <= b[0] and b[2] <= native.x1 + _TOL and native.y0 - _TOL <= b[1] and b[3] <= native.y1 + _TOL
                                for b in (word_box, trace_box, scissor))
            # Word and trace font-metric boxes can legitimately differ. Each
            # API must instead retain all four coordinates of its own known
            # unrotated reference; agreement between two shifted APIs is not
            # independent evidence that either is in the native frame.
            same_frame_word_trace = all(
                abs(word_box[i] - float(reference_words[0][i])) <= _TOL
                and abs(trace_box[i] - float(reference_trace[0]["bbox"][i])) <= _TOL
                for i in range(4)
            )
            clip_matches = all(abs(a - b) <= _TOL for a, b in zip(scissor, _FIXTURE_CLIP))
            text_in_clip = (scissor[0] - _TOL <= word_box[0] and word_box[2] <= scissor[2] + _TOL
                            and scissor[1] - _TOL <= word_box[1] and word_box[3] <= scissor[3] + _TOL)
            rings = _rings_from_items(clips[1].get("items") or [])
            triangle_matches = rings is not None and len(rings) == 1 and _same_vertices(rings[0][0], _FIXTURE_TRIANGLE)
            ok = bool(inside_native and same_frame_word_trace and clip_matches and text_in_clip and triangle_matches)
    except Exception:
        ok = False
    finally:
        for opened in (document, reference):
            if opened is not None:
                try:
                    opened.close()
                except Exception:
                    ok = False
    _frame_check_cache[rotation] = ok
    return ok


# ---------------------------------------------------------------------------------------------------------------------------------
# Exact polygons from straight-segment clip paths
# ---------------------------------------------------------------------------------------------------------------------------------
Ring = Tuple[List[Tuple[float, float]], Optional[int]]        # closed vertex list, winding sign (+1/-1) when the library exposes it


def _signed_area(ring: Sequence[Tuple[float, float]]) -> float:
    return sum(ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1] for i in range(len(ring) - 1)) / 2.0


def _rings_from_items(items: Sequence[Sequence[object]]) -> Optional[List[Ring]]:
    """Closed subpaths of a clip made only of straight segments, rectangles and quads; None for any curve or malformed item.

    The winding sign is known only for rings built from straight segments. PyMuPDF folds an axis-aligned rectangle into a ``re`` item whose
    orientation flag does not reflect the real winding (a rectangle with a negative width reports the same flag as one with a positive
    width), and folds a quad into a ``qu`` item that has lost its vertex order, so for those the sign is None."""
    rings: List[Ring] = []
    current: List[Tuple[float, float]] = []

    def flush() -> bool:
        nonlocal current
        if current:
            if len(current) < 3:
                return False
            if abs(current[0][0] - current[-1][0]) > _POINT_TOL or abs(current[0][1] - current[-1][1]) > _POINT_TOL:
                current = current + [current[0]]                 # a clip path is closed by the fill
            if len(current) < 4:
                return False
            area = _signed_area(current)
            rings.append((current, None if area == 0.0 else (1 if area > 0.0 else -1)))
            current = []
        return True

    for item in items:
        if not item:
            return None
        kind = item[0]
        try:
            if kind == "re":
                if not flush():
                    return None
                r = fitz.Rect(item[1])
                if r.is_empty:
                    return None
                rings.append(([(r.x0, r.y0), (r.x1, r.y0), (r.x1, r.y1), (r.x0, r.y1), (r.x0, r.y0)], None))
                continue
            if kind == "qu":
                if not flush():
                    return None
                q = item[1]
                corners = [(float(q.ul.x), float(q.ul.y)), (float(q.ur.x), float(q.ur.y)), (float(q.lr.x), float(q.lr.y)), (float(q.ll.x), float(q.ll.y))]
                rings.append((corners + [corners[0]], None))
                continue
            if kind != "l":
                return None
            p0 = (float(item[1].x), float(item[1].y))
            p1 = (float(item[2].x), float(item[2].y))
        except (AttributeError, TypeError, ValueError, IndexError):
            return None
        if current and (abs(current[-1][0] - p0[0]) > _POINT_TOL or abs(current[-1][1] - p0[1]) > _POINT_TOL):
            if not flush():
                return None
        if not current:
            current = [p0]
        current.append(p1)
    if not flush():
        return None
    return rings or None


@dataclass(frozen=True)
class ClipRegion:
    """``inside`` is certainly inside the clip; everything outside ``reach`` is certainly outside it (``inside`` is within ``reach``)."""
    inside: object
    reach: object
    exact: bool


def clip_region(entry: Mapping[str, object]) -> Optional[ClipRegion]:
    """Provable inside / reach polygons of one extended-drawing clip entry, or None when it is not made only of simple straight rings."""
    rings = _rings_from_items(entry.get("items") or [])
    if rings is None or len(rings) > MAX_CLIP_RINGS:
        return None
    polygons = []
    for vertices, _winding in rings:
        poly = Polygon(vertices)
        if not poly.is_valid or poly.is_empty or poly.area <= 0.0:
            return None                                          # a non-simple or degenerate ring is not an exact polygon
        polygons.append(poly)
    if len(polygons) == 1:
        return ClipRegion(polygons[0], polygons[0], True)
    odd_cover = polygons[0]
    union = polygons[0]
    for extra in polygons[1:]:
        odd_cover = odd_cover.symmetric_difference(extra)
        union = union.union(extra)
    if bool(entry.get("even_odd")):
        return ClipRegion(odd_cover, odd_cover, True) if not odd_cover.is_empty else None
    windings = {w for _v, w in rings}
    if None not in windings and len(windings) == 1:              # non-zero rule, every ring winds the same way: the clip is their union
        return ClipRegion(union, union, True)
    # non-zero rule with windings that are unknown or mixed: a point covered by an odd number of rings has a non-zero winding number
    # whatever the signs, a point covered by none is outside, and nothing is claimed about the points covered an even number of times
    return ClipRegion(odd_cover, union, False)


@dataclass
class _PreparedRegion:
    inside: object
    reach: object


def _clip_entries(page: object) -> Optional[List[Mapping[str, object]]]:
    """The page's clip entries numbered exactly as the authority's model numbers them."""
    cache = authority._page_cache(page)
    key = _CACHE_PREFIX + "entries"
    if key in cache:
        return cache[key]
    try:
        drawings = page.get_drawings(extended=True) or []
    except Exception:
        cache[key] = None
        return None
    entries: List[Mapping[str, object]] = []
    for entry in drawings:
        raw_level = entry.get("level")
        if raw_level is None:
            continue
        try:
            if int(raw_level) < 0:
                continue
        except (TypeError, ValueError):
            continue
        if entry.get("type") != "clip":
            continue
        try:
            fitz.Rect(entry.get("scissor"))
        except (TypeError, ValueError):
            continue
        entries.append(entry)
    cache[key] = entries
    return entries


def _prepared_region(page: object, clip_id: int, clip_count: int) -> Tuple[Optional[_PreparedRegion], Optional[str]]:
    """Prepared inside / reach geometry of clip ``clip_id`` (None and the reason when it cannot be built)."""
    cache = authority._page_cache(page)
    key = _CACHE_PREFIX + "regions"
    regions = cache.setdefault(key, {})
    if clip_id in regions:
        return regions[clip_id]
    entries = _clip_entries(page)
    result: Tuple[Optional[_PreparedRegion], Optional[str]]
    if entries is None or len(entries) != clip_count or not 0 <= clip_id < clip_count:
        result = (None, REASON_CLIP_STRUCTURE_UNRECONCILED)
    else:
        region = clip_region(entries[clip_id])
        if region is None:
            result = (None, REASON_CLIP_NOT_AN_EXACT_POLYGON)
        else:
            # round joins keep the inside test no more permissive than the tolerance, mitre joins keep the outside test no less cautious
            result = (_PreparedRegion(prep(region.inside.buffer(_TOL)), prep(region.reach.buffer(_TOL, join_style=2))), None)
    regions[clip_id] = result
    return result


# ---------------------------------------------------------------------------------------------------------------------------------
# The verdict: the authority's decision flow, with polygon proofs for the clips it cannot decide and a verified rotation allowance
# ---------------------------------------------------------------------------------------------------------------------------------
def text_clip_verdict(page: object, subject_bbox: Sequence[object], seqno: Optional[int], *,
                      native_word: Optional[Mapping[str, object]] = None) -> ClipVerdict:
    """Clip verdict for one native word. See the module docstring; never trusts anything but the clip question."""
    model = authority._clip_model(page)
    has_clip_operator = authority._page_content_has_clip_operator(page)
    if model is None or has_clip_operator is None:
        return ClipVerdict(UNRESOLVED, (authority.TEXT_CLIP_STATE_UNRESOLVED, REASON_CLIP_STRUCTURE_UNRECONCILED))
    if not model.clips:
        if has_clip_operator:
            return ClipVerdict(UNRESOLVED, (authority.TEXT_CLIP_STATE_UNRESOLVED, REASON_CLIP_STRUCTURE_UNRECONCILED))
        return ClipVerdict(UNCLIPPED, ())
    if not model.consistent or seqno is None:
        return ClipVerdict(UNRESOLVED, (authority.TEXT_CLIP_STATE_UNRESOLVED, REASON_CLIP_STRUCTURE_UNRECONCILED))
    try:
        rotation = int(getattr(page, "rotation", 0) or 0)
        bbox = authority._rect_tuple(subject_bbox)
    except (TypeError, ValueError):
        return ClipVerdict(UNRESOLVED, (authority.TEXT_CLIP_STATE_UNRESOLVED,))
    if rotation % 360 != 0 and not native_frame_conventions_verified(rotation):
        return ClipVerdict(UNRESOLVED, (authority.TEXT_CLIP_STATE_UNRESOLVED, REASON_ROTATED_FRAMES_UNVERIFIED))
    positive_area = bbox[2] > bbox[0] and bbox[3] > bbox[1]

    page_cache = authority._page_cache(page)
    path_seqnos = page_cache.get("clip_model_path_seqnos")
    if path_seqnos is None:
        path_seqnos = tuple(path[0] for path in model.paths)
        page_cache["clip_model_path_seqnos"] = path_seqnos
    push_positions = page_cache.get("clip_model_push_positions")
    if push_positions is None:
        push_positions = tuple(position for position, _clip_id in model.pushes)
        page_cache["clip_model_push_positions"] = push_positions
    before_index = bisect_left(path_seqnos, seqno) - 1
    after_index = bisect_right(path_seqnos, seqno)
    before = model.paths[before_index] if before_index >= 0 else None
    after = model.paths[after_index] if after_index < len(model.paths) else None
    lo_position = before[3] if before is not None else -1
    hi_position = after[3] if after is not None else None
    stack_before = set(before[2]) if before is not None else set()
    stack_after = set(after[2]) if after is not None else None
    push_start = bisect_right(push_positions, lo_position)
    push_end = len(model.pushes) if hi_position is None else bisect_left(push_positions, hi_position)
    between = {model.pushes[index][1] for index in range(push_start, push_end)}
    if before is not None and after is not None and not between and before[1] == after[1]:
        if before[2] != after[2]:
            return ClipVerdict(UNRESOLVED, (authority.TEXT_CLIP_STATE_UNRESOLVED, REASON_CLIP_STRUCTURE_UNRECONCILED))
        may_apply = set(before[2])
        must_apply = set(before[2])
    else:
        may_apply = stack_before | between | (stack_after or set())
        must_apply = (stack_before & stack_after) if stack_after is not None else set()

    native_word_present = authority._native_word_is_present(page, native_word)
    subject = None
    clipped = False
    unresolved: List[str] = []
    for clip_id in sorted(may_apply):
        clip = model.clips[clip_id]
        contained = authority._rect_contains(clip.scissor, bbox)
        # the authority's own rules, verbatim
        if contained and clip.exact_rectangle:
            continue
        if not contained and clip_id in must_apply:
            clipped = True
            continue
        if native_word_present and clip.exact_rectangle and authority._rects_provably_disjoint(clip.scissor, bbox):
            continue
        # the only addition: a clip that is not an exact rectangle may still be an exact polygon
        if clip.exact_rectangle:
            unresolved.append(authority.TEXT_CLIP_STATE_UNRESOLVED)
            continue
        region, why_not = _prepared_region(page, clip_id, len(model.clips))
        if region is None or not positive_area:
            unresolved.extend((authority.TEXT_CLIP_STATE_UNRESOLVED, why_not or REASON_SUBJECT_DEGENERATE))
            continue
        if subject is None:
            subject = box(*bbox)
        if region.inside.contains(subject):
            continue
        if region.reach.disjoint(subject):
            if clip_id in must_apply:
                clipped = True
                continue
            if native_word_present:
                continue
        unresolved.append(authority.TEXT_CLIP_STATE_UNRESOLVED)
    if clipped:
        return ClipVerdict(CLIPPED, (authority.TEXT_CLIPPED_BY_CLIP_REGION,))
    if unresolved:
        return ClipVerdict(UNRESOLVED, tuple(dict.fromkeys(unresolved)))
    return ClipVerdict(UNCLIPPED, ())
