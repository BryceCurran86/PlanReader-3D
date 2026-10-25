"""Read-only original-PDF dimension-leader to opening-cap ink correspondence.

A source-authenticated figure/leader pair is not a physical W4 doorway, a
measurement scale, a floor threshold or a FIRM construction quantity.
"""
from __future__ import annotations
from collections import Counter
from dataclasses import dataclass, asdict
from hashlib import sha256
from math import isfinite
import fitz
from pb_native_text_render_authority import (
    PROVEN_RENDERED, extract_native_text_render_evidence,
)


@dataclass(frozen=True)
class OriginalDoorLeaderScope:
    page_number: int
    text_block: int
    text_line: int
    text_word: int
    baseline_path: int
    cap_paths: tuple[int,int]
    left_tick_paths: tuple[int,int,int,int]
    right_tick_paths: tuple[int,int,int,int]


@dataclass(frozen=True)
class OriginalDoorFigureSourceShadow:
    status: str
    source_sha256: str
    original_page: int
    original_word_address: tuple[int,int,int]
    original_figured_text: str
    drawn_leader_cap_x_pdf_pt: tuple[float,float]
    native_dimension_line_y_pdf_pt: float
    original_gap_span_pdf_pt: float
    rival_same_line_word_texts: tuple[str,...]
    source_path_ids: tuple[int,...]
    reasons: tuple[str,...]
    shadow_only: bool = True
    actual_door_identity_proven: bool = False
    original_w4_wall_issued: bool = False
    opening_jamb_identity_granted: bool = False
    physical_doorway_threshold_issued: bool = False
    figure_width_mm_authorized_for_physical_opening: bool = False
    floor_finish_area_issued: bool = False
    customer_projection_allowed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _native_line(page, drawings, n: int):
    if type(n) is not int or n < 0 or n >= len(drawings):
        raise ValueError('original drawing path not found')
    d = drawings[n]
    opacity=d.get('stroke_opacity')
    if (type(opacity) not in (int,float) or not isfinite(opacity)
            or opacity != 1.0 or d.get('dashes') != '[] 0'):
        raise ValueError('original dimension source path is not visible solid ink')
    items=d.get('items',())
    color=d.get('color')
    original_black_ink=(
        type(color) in (tuple,list) and len(color)==3
        and all(type(v) in (int,float) and isfinite(v)
                and 0.0 <= v <= .04 for v in color)
    )
    if (len(items) not in (1,2) or items[0][0] != 'l'
            or not original_black_ink
            or d.get('fill') is not None):
        raise ValueError('original path not a black source line')
    if len(items)==2 and (items[1][0]!='l' or items[1][1] != items[0][2]
                          or items[1][2] != items[0][1]):
        raise ValueError('original two-stroke path does not reverse same ink')
    p,q = items[0][1:3]
    vals = (float(p.x),float(p.y),float(q.x),float(q.y),float(d['width']))
    if not all(isfinite(v) for v in vals) or vals[4] <= 0:
        raise ValueError('invalid original source segment')
    return vals


def _require_visible_original_figure_word(page, word, expected: str) -> None:
    """Fail closed unless the decoded word is covered by visible native glyph ink.

    A PyMuPDF word may be invisible (PDF text render mode 3). Texttrace spans
    can contain *several* words, and even reverse their character order:
    resolve the exact glyph subset by its source word bbox, never by
    span-level string equality, first span, or a nearest-text guess.
    This is negative-only appearance evidence, not Unicode/font authority.
    """
    box = tuple(float(v) for v in word[:4])
    if not all(isfinite(v) for v in box) or box[0] >= box[2] or box[1] >= box[3]:
        raise ValueError('figured text source glyph bounds invalid')
    try:
        traces = tuple(page.get_texttrace())
        bboxlog = tuple(page.get_bboxlog())
        render = extract_native_text_render_evidence(page)
    except Exception as exc:
        raise ValueError('figured text native render evidence unavailable') from exc
    render_by_seq = {}
    for receipt in render:
        seq = receipt.sequence_number
        if seq is None or seq in render_by_seq:
            raise ValueError('figured text native render sequence ambiguous')
        render_by_seq[seq] = receipt
    selected = []
    for trace in traces:
        seq = trace.get('seqno')
        for glyph in trace.get('chars') or ():
            try:
                codepoint, glyph_id, _origin, raw_box = glyph
                glyph_box = tuple(float(v) for v in raw_box)
                if (len(glyph_box) != 4 or not all(isfinite(v) for v in glyph_box)
                        or glyph_box[0] >= glyph_box[2] or glyph_box[1] >= glyph_box[3]):
                    raise ValueError('invalid glyph bounds')
                centre_x = (glyph_box[0] + glyph_box[2]) / 2
                centre_y = (glyph_box[1] + glyph_box[3]) / 2
            except (TypeError, ValueError, IndexError) as exc:
                raise ValueError('figured text glyph integrity unresolved') from exc
            if not (box[0] - .1 <= centre_x <= box[2] + .1
                    and box[1] - .1 <= centre_y <= box[3] + .1):
                continue
            receipt = render_by_seq.get(seq)
            if (type(seq) is not int or not 0 <= seq < len(bboxlog)
                    or bboxlog[seq][0] not in ('fill-text', 'stroke-text')
                    or receipt is None or not receipt.render_eligible
                    or receipt.render_state != PROVEN_RENDERED):
                raise ValueError('figured text is not visibly painted original glyph ink')
            if (type(codepoint) is not int or not 0 <= codepoint <= 0x10ffff
                    or type(glyph_id) is not int or glyph_id < 0):
                raise ValueError('figured text glyph identity unresolved')
            selected.append((chr(codepoint), glyph_box))
    if len(selected) != len(expected) or Counter(char for char, _ in selected) != Counter(expected):
        raise ValueError('figured text exact source glyph coverage unavailable')
    if (abs(min(b[0] for _, b in selected) - box[0]) > .5
            or abs(max(b[2] for _, b in selected) - box[2]) > .5):
        raise ValueError('figured text native glyph geometry disagrees with source word')


def inspect_original_door_figure_leader_shadow(original_pdf_bytes:bytes, *,
    source_sha256:str, scope:OriginalDoorLeaderScope,
    expected_cap_x_pdf_pt:tuple[float,float],
    expected_figured_word:str='1000',tolerance_pdf_pt:float=.06,
) -> OriginalDoorFigureSourceShadow:
    if (type(original_pdf_bytes) is not bytes or not original_pdf_bytes
            or sha256(original_pdf_bytes).hexdigest() != source_sha256):
        raise ValueError('source original immutable PDF SHA mismatch')
    if (type(scope) is not OriginalDoorLeaderScope
            or type(tolerance_pdf_pt) not in (int,float) or not isfinite(tolerance_pdf_pt)
            or not .001 <= tolerance_pdf_pt <= .25):
        raise ValueError('invalid original source scope or tolerance')
    paths=(scope.baseline_path,*scope.cap_paths,*scope.left_tick_paths,*scope.right_tick_paths)
    if len(paths)!=11 or len(set(paths))!=11:
        raise ValueError('dimension line, two caps and eight tick/extension paths must be distinct')
    if (type(expected_cap_x_pdf_pt) is not tuple or len(expected_cap_x_pdf_pt)!=2
            or not all(type(v) in (float,int) and isfinite(v) for v in expected_cap_x_pdf_pt)
            or expected_cap_x_pdf_pt[1]-expected_cap_x_pdf_pt[0]<=tolerance_pdf_pt):
        raise ValueError('ordered source cap coordinates required')
    with fitz.open(stream=original_pdf_bytes,filetype='pdf') as pdf:
        if not 1<=scope.page_number<=len(pdf):
            raise ValueError('original source page not found')
        pg=pdf[scope.page_number-1]
        words=[w for w in pg.get_text('words') if tuple(w[5:8]) ==
               (scope.text_block,scope.text_line,scope.text_word)]
        if len(words)!=1 or words[0][4] != expected_figured_word or not expected_figured_word.isdigit():
            raise ValueError('exact figured dimension original word unavailable')
        _require_visible_original_figure_word(pg, words[0], expected_figured_word)
        rivals=tuple(sorted(w[4] for w in pg.get_text('words') if
            w[5]==scope.text_block and w[6]==scope.text_line and w[7]!=scope.text_word))
        drawings=pg.get_drawings()
        baseline=_native_line(pg,drawings,scope.baseline_path)
        cap_left=_native_line(pg,drawings,scope.cap_paths[0])
        cap_right=_native_line(pg,drawings,scope.cap_paths[1])
        left=tuple(_native_line(pg,drawings,p) for p in scope.left_tick_paths)
        right=tuple(_native_line(pg,drawings,p) for p in scope.right_tick_paths)
    if abs(baseline[1]-baseline[3])>tolerance_pdf_pt:
        raise ValueError('figured original dimension baseline is not horizontal')
    y=baseline[1]
    bounds=tuple(sorted((baseline[0],baseline[2])))
    # A printed number and a dimension leader on the same original page
    # are not source-associated merely by caller-supplied word/path indices.
    # Require the actual native word glyph box to occupy the claimed
    # between-ticks chord and lie within its own glyph height of the leader.
    # This is a negative-only source check, never figured width authority.
    figure_bbox=tuple(float(v) for v in words[0][:4])
    figure_h=figure_bbox[3]-figure_bbox[1]
    if (not all(isfinite(v) for v in figure_bbox)
            or figure_h<=0
            or figure_bbox[0]<expected_cap_x_pdf_pt[0]-tolerance_pdf_pt
            or figure_bbox[2]>expected_cap_x_pdf_pt[1]+tolerance_pdf_pt
            or min(abs(y-figure_bbox[1]),abs(y-figure_bbox[3]))>figure_h+tolerance_pdf_pt):
        raise ValueError('original figured word glyph does not belong to claimed dimension chord')
    if any(x<bounds[0]-tolerance_pdf_pt or x>bounds[1]+tolerance_pdf_pt for x in expected_cap_x_pdf_pt):
        raise ValueError('original dimension baseline does not bracket both wall caps')
    for cap,x in zip((cap_left,cap_right),expected_cap_x_pdf_pt):
        if abs(cap[0]-cap[2])>tolerance_pdf_pt or abs(cap[0]-x)>tolerance_pdf_pt:
            raise ValueError('dimension leader x does not match original wall cap')
        if not min(cap[1],cap[3])>y:
            raise ValueError('wall cap does not lie beyond original dimension baseline')
    for strokes,x in ((left,expected_cap_x_pdf_pt[0]),(right,expected_cap_x_pdf_pt[1])):
        extensions=[a for a in strokes if abs(a[0]-a[2])<=tolerance_pdf_pt]
        diagonals=[a for a in strokes if abs(a[0]-a[2])>tolerance_pdf_pt
                   and abs(a[1]-a[3])>tolerance_pdf_pt]
        if len(extensions)!=2 or len(diagonals)!=2:
            raise ValueError('independent original dimension ticks/extensions incomplete')
        if any(abs(a[0]-x)>tolerance_pdf_pt or
               min(abs(a[1]-y),abs(a[3]-y))>tolerance_pdf_pt for a in extensions):
            raise ValueError('original extension lines do not meet source dimension ticks')
        if any(min(abs(a[0]-x)+abs(a[1]-y),abs(a[2]-x)+abs(a[3]-y))>tolerance_pdf_pt
               for a in diagonals):
            raise ValueError('original leader arrow heads not source-owned at dimension tick')
    return OriginalDoorFigureSourceShadow(
        'SOURCE_FIGURE_LEADER_CANDIDATE',source_sha256,scope.page_number,
        (scope.text_block,scope.text_line,scope.text_word),expected_figured_word,
        tuple(round(float(x),5) for x in expected_cap_x_pdf_pt),round(float(y),5),
        round(float(expected_cap_x_pdf_pt[1]-expected_cap_x_pdf_pt[0]),5),
        rivals,tuple(sorted(paths)),('original_door_figured_leader_source_only_no_w4_physical_owner',))
