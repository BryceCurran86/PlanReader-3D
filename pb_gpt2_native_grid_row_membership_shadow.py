"""Read-only source-ink grid membership for PDF schedule rows spanning native blocks.

A native PyMuPDF text block is not an installed door or even a printed table
row. This shadow requires independently drawn source grid boundaries and ALL
producer-owned native words; it issues no type, size, count, or commercial row.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
import re

import fitz

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_door_schedule_authority import (
    SourceDoorScheduleWord,
    _DOOR_CODE,
    _producer_owned_native_words,
)
from pb_source_visibility_authority import SourceVisibilityProducer


# Negative-only D-digit competitors must not depend on the unmerged A600
# parser changes in #3762. Canonical positive codes still use _DOOR_CODE.
_DOOR_LIKE_TOKEN = re.compile(r"^D[0-9]+$")


@dataclass(frozen=True)
class NativeGridRowScope:
    page_number: int
    left_boundary_paths: tuple[int, ...]
    right_boundary_paths: tuple[int, ...]
    code_address: tuple[int, int, int]


@dataclass(frozen=True)
class NativeGridRowShadow:
    status: EvidenceResolutionStatus
    source_sha256: str
    page_number: int
    code_observation_id: str
    native_blocks: tuple[int, ...]
    member_observation_ids: tuple[str, ...]
    competing_same_code_observation_ids: tuple[str, ...]
    source_grid_boundary_paths: tuple[int, ...]
    first_unclosed_gate: str
    shadow_only: bool = True
    source_dimension_authorized: bool = False
    physical_door_identity_proven: bool = False
    opening_count_granted: bool = False
    firm_quantity_issued: bool = False
    commercial_projection_allowed: bool = False


def _original_vertical_chain(drawings, indices, *, tolerance):
    if (type(indices) is not tuple or not 1 <= len(indices) <= 100
            or any(type(i) is not int or i < 0 or i >= len(drawings)
                   for i in indices)
            or len(set(indices)) != len(indices)):
        raise ValueError("distinct original grid path addresses required")
    lines = []
    for i in indices:
        d = drawings[i]
        color = d.get("color")
        if (d.get("type") != "s" or d.get("stroke_opacity") != 1
                or d.get("fill") is not None or d.get("dashes") != "[] 0"
                or not isinstance(color, (tuple, list)) or len(color) != 3
                or any(type(v) not in (float, int) or not isfinite(v)
                       or not 0 <= v <= .04 for v in color)
                or type(d.get("width")) not in (int, float)
                or not isfinite(d["width"]) or d["width"] <= 0):
            raise ValueError("grid boundary not opaque solid source ink")
        items = d.get("items", ())
        if len(items) != 1 or items[0][0] != "l":
            raise ValueError("grid boundary must be source line, not hatch/rect")
        a, b = items[0][1:3]
        if not all(isfinite(v) for v in (a.x, a.y, b.x, b.y)):
            raise ValueError("nonfinite source grid line")
        if abs(a.x - b.x) > tolerance or abs(a.y - b.y) <= tolerance:
            raise ValueError("grid boundary must be nondegenerate vertical ink")
        lines.append((float(a.x), min(float(a.y), float(b.y)),
                      max(float(a.y), float(b.y)), float(d["width"])))
    lines.sort(key=lambda item: (item[1], item[2]))
    x = lines[0][0]
    width = lines[0][3]
    for index, line in enumerate(lines):
        if abs(line[0] - x) > tolerance or abs(line[3] - width) > tolerance:
            raise ValueError("grid path x or source stroke width disagrees")
        if index and abs(line[1] - lines[index-1][2]) > tolerance:
            raise ValueError("grid boundary contains missing or overlapping ink")
    return x, lines[0][1], lines[-1][2], width



def _assert_final_visible_grid_ink(page, drawings, indices):
    """Reject historical grid strokes erased by later painting.

    The original schedule may be page-rotated: drawing coordinates are
    unrotated, whereas pixmap pixels use page.rotation_matrix. The raster
    check is negative evidence only; dark pixels never grant a door.
    """
    scale = 2.0
    if page.rect.width * page.rect.height * scale * scale > 24_000_000:
        raise ValueError("source grid visible-ink audit exceeds bounded page")
    pix = page.get_pixmap(
        matrix=fitz.Matrix(scale, scale), colorspace=fitz.csRGB,
        alpha=False, annots=False,
    )
    # get_drawings() omits raster-image paint commands. Bind each selected
    # historical vector path to its paint sequence before accepting dark
    # final pixels, which could belong to a later black raster overlay.
    paint_log = page.get_bboxlog()
    # Native text can be painted AFTER source grid strokes. A whole texttrace
    # bbox is too broad (CAD may paint an entire table in one span); inspect
    # exact later glyph boxes, not a spanning text bbox or dark final pixels.
    text_traces_by_seq = {}
    for trace in page.get_texttrace():
        if isinstance(trace, dict) and type(trace.get("seqno")) is int:
            text_traces_by_seq.setdefault(trace["seqno"], []).append(trace)
    for index in indices:
        source_seq = drawings[index].get("seqno")
        if (type(source_seq) is not int or not 0 <= source_seq < len(paint_log)
                or paint_log[source_seq][0] != "stroke-path"):
            raise ValueError("original grid stroke paint-order receipt unavailable")
        a, b = drawings[index]["items"][0][1:3]
        x = (a.x + b.x) / 2.0
        low, high = sorted((float(a.y), float(b.y)))
        # Later image/shading paint does not appear in get_drawings().
        # Its source paint-order bbox is negative evidence even when the
        # image is black and the final raster looks like valid grid ink.
        for kind, bounds in paint_log[source_seq + 1:]:
            if kind not in ("fill-image", "fill-shade"):
                continue
            if (len(bounds) != 4 or
                    any(type(v) not in (int, float) or not isfinite(v)
                        for v in bounds)):
                raise ValueError("unverifiable later source paint bbox")
            x0, y0, x1, y1 = bounds
            if x0 <= x <= x1 and y0 < high and y1 > low:
                raise ValueError("original grid boundary overpainted by later image")
        # Later source text glyphs can conceal one portion of a stroke
        # between our raster sample points. Whole-span text bboxes are NOT
        # proof of overlap: verify each later source glyph's own ink box.
        for text_seq, (kind, bounds) in enumerate(
                paint_log[source_seq + 1:], start=source_seq + 1):
            if kind not in ("fill-text", "stroke-text"):
                continue
            if (len(bounds) != 4 or
                    any(type(v) not in (int, float) or not isfinite(v)
                        for v in bounds)):
                raise ValueError("unverifiable later source text paint bbox")
            x0, y0, x1, y1 = bounds
            if not (x0 <= x <= x1 and y0 < high and y1 > low):
                continue
            traces = text_traces_by_seq.get(text_seq, ())
            if not traces:
                raise ValueError("later text glyph source provenance unavailable")
            for trace in traces:
                glyphs = trace.get("chars")
                if not isinstance(glyphs, (tuple, list)) or not glyphs:
                    raise ValueError("later text glyph source provenance unavailable")
                for glyph in glyphs:
                    if not isinstance(glyph, (tuple, list)) or len(glyph) < 4:
                        raise ValueError("invalid later source text glyph")
                    codepoint = glyph[0]
                    if (type(codepoint) is not int
                            or not 0 <= codepoint <= 0x10ffff):
                        raise ValueError("invalid later source text glyph")
                    # Spaces have advance boxes but no painted glyph ink.
                    # A CAD-wide text span crossing the ruled grid is not
                    # proof that any visible character overpainted that grid.
                    if chr(codepoint).isspace():
                        continue
                    try:
                        glyph_box = tuple(float(v) for v in glyph[3])
                    except (TypeError, ValueError, OverflowError):
                        raise ValueError("invalid later source text glyph") from None
                    if (len(glyph_box) != 4
                            or any(not isfinite(v) for v in glyph_box)
                            or glyph_box[0] >= glyph_box[2]
                            or glyph_box[1] >= glyph_box[3]):
                        raise ValueError("invalid later source text glyph")
                    if (glyph_box[0] <= x <= glyph_box[2]
                            and glyph_box[1] < high and glyph_box[3] > low):
                        raise ValueError(
                            "original grid boundary overpainted by later text glyph"
                        )
        # A later stroke can repaint the same grid path (even black-on-black)
        # without producing a fill-path or image. The final dark raster then
        # cannot prove which source stroke owns the boundary. Use the original
        # paint-order log, not get_drawings() indices or nearest ink. Ignore
        # ordinary thin transverse grid intersections: their bbox overlap
        # along this vertical source segment is no greater than two original
        # stroke widths. Longer overlap is ambiguous and must fail closed.
        source_width = float(drawings[index]["width"])
        for kind, bounds in paint_log[source_seq + 1:]:
            if kind != "stroke-path":
                continue
            if (len(bounds) != 4 or
                    any(type(v) not in (int, float) or not isfinite(v)
                        for v in bounds)):
                raise ValueError("unverifiable later source stroke bbox")
            x0, y0, x1, y1 = bounds
            if (x0 <= x <= x1 and
                    min(y1, high) - max(y0, low) > 2 * source_width):
                raise ValueError("original grid boundary overpainted by later stroke")
        # A later opaque painted object can conceal a perfectly authentic
        # earlier vector path. Its bounding box is a conservative veto.
        for later in drawings[index + 1:]:
            if later.get("fill") is None or later.get("fill_opacity") != 1:
                continue
            box = later.get("rect")
            if (box is not None and box.x0 <= x <= box.x1
                    and box.y0 < high and box.y1 > low):
                raise ValueError("original grid boundary overpainted by opaque fill")
        for fraction in (.2, .5, .8):
            y = low + (high - low) * fraction
            visible = False
            # Antialiasing can place a 0.48pt stroke in a neighbouring pixel.
            # Search only the narrow source-stroke normal, not nearby words.
            for offset in (-.5, -.25, 0.0, .25, .5):
                rendered = fitz.Point(x + offset, y) * page.rotation_matrix
                px, py = round(rendered.x * scale), round(rendered.y * scale)
                if (0 <= px < pix.width and 0 <= py < pix.height
                        and max(pix.pixel(px, py)) <= 190):
                    visible = True
                    break
            if not visible:
                raise ValueError("original grid boundary lacks final visible ink")


def inspect_original_native_grid_row_shadow(
    original_pdf_bytes: bytes, *, source_sha256: str,
    words: tuple[SourceDoorScheduleWord, ...],
    scope: NativeGridRowScope,
    tolerance_pdf_pt: float = .06,
) -> NativeGridRowShadow:
    """Return a negative-only source grid receipt; never select an installed door."""
    if (type(original_pdf_bytes) is not bytes or not original_pdf_bytes
            or sha256(original_pdf_bytes).hexdigest() != source_sha256):
        raise ValueError("original PDF SHA mismatch")
    if (type(scope) is not NativeGridRowScope
            or type(tolerance_pdf_pt) not in (float, int)
            or not isfinite(tolerance_pdf_pt)
            or not .001 <= tolerance_pdf_pt <= .25
            or type(words) is not tuple or not words or len(words) > 25000):
        raise ValueError("invalid original grid row source scope")
    # A frozen scope cannot authenticate a mutable/list or scalar native
    # address. Check the exact shape before len()/iteration so malformed
    # caller evidence fails closed instead of raising TypeError.
    if (type(scope.code_address) is not tuple
            or len(scope.code_address) != 3
            or any(type(x) is not int or x < 0 for x in scope.code_address)):
        raise ValueError("exact native code word address required")
    with fitz.open(stream=original_pdf_bytes, filetype="pdf") as pdf:
        if type(scope.page_number) is not int or not 1 <= scope.page_number <= len(pdf):
            raise ValueError("original page outside source")
        drawings = pdf[scope.page_number-1].get_drawings()
        left = _original_vertical_chain(
            drawings, scope.left_boundary_paths, tolerance=tolerance_pdf_pt)
        right = _original_vertical_chain(
            drawings, scope.right_boundary_paths, tolerance=tolerance_pdf_pt)
        _assert_final_visible_grid_ink(
            pdf[scope.page_number-1], drawings,
            (*scope.left_boundary_paths, *scope.right_boundary_paths))
    if left[0] + tolerance_pdf_pt >= right[0] or abs(left[3]-right[3]) > tolerance_pdf_pt:
        raise ValueError("source grid row boundaries not distinct")
    if (abs(left[1]-right[1]) > tolerance_pdf_pt
            or abs(left[2]-right[2]) > tolerance_pdf_pt):
        raise ValueError("paired source grid rows span unequal columns")
    addresses = set()
    observations = set()
    for w in words:
        if (type(w) is not SourceDoorScheduleWord
                or w.page_id != str(scope.page_number)
                or w.partition_id != "page:" + str(scope.page_number)
                or (w.block_no, w.line_no, w.word_no) in addresses
                or w.observation_id in observations):
            raise ValueError("unverified or duplicated complete source word universe")
        addresses.add((w.block_no, w.line_no, w.word_no))
        observations.add(w.observation_id)
    codes = [w for w in words
             if (w.block_no, w.line_no, w.word_no) == scope.code_address]
    if len(codes) != 1 or _DOOR_CODE.fullmatch(codes[0].literal) is None:
        raise ValueError("exact canonical source code observation unavailable")
    members, touching = [], []
    for w in words:
        x0,y0,x1,y1 = w.bbox_pdf_pts
        if not all(isfinite(v) for v in (x0,y0,x1,y1)) or x0 >= x1 or y0 >= y1:
            raise ValueError("invalid original source word bbox")
        if y1 <= left[1] or y0 >= left[2] or x1 <= left[0] or x0 >= right[0]:
            continue
        if (x0 <= left[0]+tolerance_pdf_pt or x1 >= right[0]-tolerance_pdf_pt
                or y0 <= left[1]-tolerance_pdf_pt
                or y1 >= left[2]+tolerance_pdf_pt):
            touching.append(w)
        else:
            members.append(w)
    if codes[0] not in members:
        raise ValueError("source code not entirely within original ruled row")
    # All D-digit source glyphs compete for one printed ruled-row code.
    # A malformed D0/D00 is negative evidence, not a silent non-code that
    # permits the otherwise trusted Dxx to become uniquely source-owned.
    member_code = [w for w in members if _DOOR_LIKE_TOKEN.fullmatch(w.literal)]
    conflict = bool(touching or len(member_code) != 1 or
                    member_code[0] is not codes[0] or
                    any(not w.trusted for w in members))
    rivals = tuple(sorted(w.observation_id for w in words
                          if w not in members and w.literal == codes[0].literal))
    return NativeGridRowShadow(
        status=EvidenceResolutionStatus.ABSTAINED if conflict
               else EvidenceResolutionStatus.CANDIDATE,
        source_sha256=source_sha256,
        page_number=scope.page_number,
        code_observation_id=codes[0].observation_id,
        native_blocks=tuple(sorted(set(w.block_no for w in members))),
        member_observation_ids=tuple(w.observation_id for w in sorted(
            members, key=lambda w:(w.block_no,w.line_no,w.word_no))),
        competing_same_code_observation_ids=rivals,
        source_grid_boundary_paths=tuple(sorted((
            *scope.left_boundary_paths, *scope.right_boundary_paths))),
        first_unclosed_gate=(
            "original_grid_row_competing_or_untrusted_source_words" if conflict
            else "source_grid_membership_only_no_kind_host_count_or_dimensions"
        ),
    )



def _assert_original_grid_word_inventory(page, scope, words):
    """Veto missing/altered producer words in the original ruled strip.

    Published observation IDs alone cannot prove completeness: a missing
    native word, competing code or boundary-touching word must not leave a
    falsely unique row CANDIDATE. Compare native addresses, literals and PDF
    boxes from the SAME original bytes/runtime; this grants no authority.
    """
    drawings = page.get_drawings()
    left = _original_vertical_chain(
        drawings, scope.left_boundary_paths, tolerance=.06)
    right = _original_vertical_chain(
        drawings, scope.right_boundary_paths, tolerance=.06)

    def intersects(box):
        x0, y0, x1, y1 = box
        return not (y1 <= left[1] or y0 >= left[2]
                    or x1 <= left[0] or x0 >= right[0])

    raw_words = page.get_text("words") or ()
    if len(raw_words) > 25000:
        raise ValueError("original grid native word universe exceeds bound")
    original = {}
    for raw in raw_words:
        if len(raw) < 8:
            raise ValueError("incomplete original grid native word address")
        # Native block/line/word IDs are source identities, not quantities.
        # Coercing bool/float/string aliases via int() can make a malformed
        # original receipt match a different published observation address.
        if any(type(value) is not int or not 0 <= value <= 2**53
               for value in raw[5:8]):
            raise ValueError("invalid original grid native word address")
        try:
            box = tuple(float(value) for value in raw[:4])
        except (TypeError, ValueError, OverflowError):
            raise ValueError("malformed original grid native word") from None
        address = tuple(raw[5:8])
        if (len(box) != 4 or any(not isfinite(value) for value in box)
                or box[0] >= box[2] or box[1] >= box[3]
                or any(value < 0 for value in address)):
            raise ValueError("invalid original grid native word geometry/address")
        if not intersects(box):
            continue
        literal = str(raw[4]).strip()
        if not literal or address in original:
            raise ValueError("ambiguous original grid native word inventory")
        original[address] = (literal, box)

    published = {}
    for word in words:
        box = word.bbox_pdf_pts
        if not intersects(box):
            continue
        address = (word.block_no, word.line_no, word.word_no)
        if address in published:
            raise ValueError("duplicate published grid native word address")
        published[address] = (word.literal, tuple(box))
    if original != published:
        raise ValueError("original grid native word inventory differs from producer")


def audit_published_native_grid_row_shadow(
    producer: SourceVisibilityProducer, *, revision_id: str, page_id: str,
    original_pdf_bytes: bytes, scope: NativeGridRowScope,
) -> NativeGridRowShadow:
    """Derive ALL words from producer receipts, not caller-curated text boxes."""
    if type(producer) is not SourceVisibilityProducer or type(revision_id) is not str:
        raise ValueError("authentic published original source producer required")
    published = producer.published_snapshot_for_revision(revision_id)
    if (published is None or published.revision.revision_id != revision_id
            or page_id != str(scope.page_number)
            or scope.page_number not in published.coverage.decoded_pages):
        raise ValueError("foreign original source revision/page")
    words = _producer_owned_native_words(producer, published, page_id)
    # Audit only: synthetic direct-inspector tests may supply invented words.
    # Original and producer use the same pinned native extraction runtime.
    if (type(original_pdf_bytes) is not bytes
            or sha256(original_pdf_bytes).hexdigest()
                != published.revision.source_sha256):
        raise ValueError("original grid PDF SHA differs from published producer")
    with fitz.open(stream=original_pdf_bytes, filetype="pdf") as pdf:
        if not 1 <= scope.page_number <= len(pdf):
            raise ValueError("original grid page outside source")
        _assert_original_grid_word_inventory(
            pdf[scope.page_number - 1], scope, words)
    return inspect_original_native_grid_row_shadow(
        original_pdf_bytes, source_sha256=published.revision.source_sha256,
        words=words, scope=scope)
