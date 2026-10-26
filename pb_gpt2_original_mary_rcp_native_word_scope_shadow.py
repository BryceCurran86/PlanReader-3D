"""Original SHA-owned RCP text word/line source-role DIAGNOSTIC only.

Never authenticates an RCP physical ceiling zone, material definition, metric
scale, customer-facing mark, FIRM area or benchmark target. Every original
text block and competing word is preserved; no nearest room-word election.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from collections import Counter
from hashlib import sha256
from math import isfinite
import fitz
from pb_native_text_render_authority import (
    PROVEN_RENDERED, extract_native_text_render_evidence,
)

# Lexical shortlist only, NOT source semantic/material or physical ceiling grant.
_SOURCE_CEILING_CODE_CANDIDATES = frozenset(('IPF1','GRID','WFPB','FPB','IP'))

@dataclass(frozen=True)
class NativeRcpWordScopeShadow:
    source_sha256: str
    page_number: int
    original_word_address: tuple[int,int,int]
    original_text: str
    original_block_words: tuple[str,...]
    original_line_words: tuple[str,...]
    native_bbox_pdf_pt: tuple[float,float,float,float]
    original_source_role: str
    reason_codes: tuple[str,...]
    original_source_word_verified: bool = True
    original_ceiling_code_visible_ink_verified: bool = False
    original_plan_viewport_authorized: bool = False
    original_material_definition_authorized: bool = False
    physical_ceiling_zone_authorized: bool = False
    w4_wall_face_authorized: bool = False
    metric_area_authorized: bool = False
    firm_ceiling_quantity_authorized: bool = False
    commercial_projection_allowed: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


def _inside(box,outer):
    return (outer[0]<=box[0] and outer[1]<=box[1] and
            box[2]<=outer[2] and box[3]<=outer[3])


def _visible_native_ceiling_code_ink(page, word) -> bool:
    """Original glyph paint negative gate, not Unicode or ceiling authority.

    A texttrace may combine several separate words; use the source word's
    own glyph subset. All eligible source glyphs must be visibly painted.
    Never select the first matching span or rescue a partially hidden code.
    """
    try:
        box = tuple(float(v) for v in word[:4])
        text = str(word[4])
        if (not text or not all(isfinite(v) for v in box)
                or box[0] >= box[2] or box[1] >= box[3]):
            return False
        traces = tuple(page.get_texttrace())
        bboxlog = tuple(page.get_bboxlog())
        receipts = extract_native_text_render_evidence(page)
        receipt_index = {}
        for receipt in receipts:
            if type(receipt.sequence_number) is int:
                receipt_index.setdefault(
                    (receipt.sequence_number, receipt.bbox), []
                ).append(receipt)
        selected = []
        selected_seq = []
        for trace in traces:
            seq = trace.get('seqno')
            raw_box = trace.get('bbox')
            if (type(seq) is not int or not isinstance(raw_box, (tuple,list))
                    or len(raw_box) != 4):
                return False
            trace_box = tuple(float(v) for v in raw_box)
            if not all(isfinite(v) for v in trace_box):
                return False
            for glyph in trace.get('chars') or ():
                codepoint, glyph_id, _origin, raw_glyph_box = glyph
                glyph_box = tuple(float(v) for v in raw_glyph_box)
                if (len(glyph_box) != 4
                        or not all(isfinite(v) for v in glyph_box)
                        or glyph_box[0] >= glyph_box[2]
                        or glyph_box[1] >= glyph_box[3]):
                    return False
                centre_x = (glyph_box[0] + glyph_box[2]) / 2
                centre_y = (glyph_box[1] + glyph_box[3]) / 2
                if not (box[0] - .1 <= centre_x <= box[2] + .1
                        and box[1] - .1 <= centre_y <= box[3] + .1):
                    continue
                if (type(codepoint) is not int or not 0 <= codepoint <= 0x10ffff
                        or type(glyph_id) is not int or glyph_id < 0
                        or not 0 <= seq < len(bboxlog)
                        or bboxlog[seq][0] not in ('fill-text','stroke-text')):
                    return False
                possible = receipt_index.get((seq, trace_box), ())
                if (len(possible) != 1 or not possible[0].render_eligible
                        or possible[0].render_state != PROVEN_RENDERED):
                    return False
                selected.append((chr(codepoint), glyph_box))
                selected_seq.append(seq)
        if len(selected) != len(text):
            return False
        if Counter(char for char, _ in selected) != Counter(text):
            return False
        # The shared render receipt conservatively checks later filled paths,
        # images and shades, but an opaque later STROKED path can also erase
        # the original glyph (even when the final raster remains dark).
        # Inspect the nominated glyph boxes and source paint order; an
        # intersecting later stroke is unresolved, never visible-ink proof.
        for (_, glyph_box), text_seq in zip(selected, selected_seq):
            for paint in bboxlog[text_seq + 1:]:
                if paint[0] != 'stroke-path':
                    continue
                stroke_box = tuple(float(v) for v in paint[1])
                if len(stroke_box) != 4 or not all(isfinite(v) for v in stroke_box):
                    return False
                if (min(glyph_box[2], stroke_box[2]) > max(glyph_box[0], stroke_box[0])
                        and min(glyph_box[3], stroke_box[3]) > max(glyph_box[1], stroke_box[1])):
                    return False
        # Extracted word boxes include font advance/bearing margins. Source
        # ink need not TOUCH those edges: require complete matching glyph
        # coverage INSIDE the original word box, never infer global snap.
        return (min(b[0] for _, b in selected) >= box[0] - .1
                and max(b[2] for _, b in selected) <= box[2] + .1
                and min(b[1] for _, b in selected) >= box[1] - .1
                and max(b[3] for _, b in selected) <= box[3] + .1)
    except (AttributeError, IndexError, KeyError, TypeError, ValueError, OverflowError):
        return False


def inspect_original_mary_rcp_word_scope_shadow(
    pdf_bytes:bytes, *, expected_source_sha256:str,
    page_number:int, native_word_address:tuple[int,int,int],
    candidate_plan_bbox_pdf_pt:tuple[float,float,float,float],
) -> NativeRcpWordScopeShadow:
    if type(pdf_bytes) is not bytes or not pdf_bytes or sha256(pdf_bytes).hexdigest()!=expected_source_sha256:
        raise ValueError('original RCP PDF SHA mismatch')
    if (type(candidate_plan_bbox_pdf_pt) is not tuple or len(candidate_plan_bbox_pdf_pt)!=4
            or any(type(x) not in (float,int) or not isfinite(x) for x in candidate_plan_bbox_pdf_pt)
            or not candidate_plan_bbox_pdf_pt[0]<candidate_plan_bbox_pdf_pt[2]
            or not candidate_plan_bbox_pdf_pt[1]<candidate_plan_bbox_pdf_pt[3]):
        raise ValueError('a finite original plan BBOX candidate is required, not a viewport grant')
    if (type(native_word_address) is not tuple or len(native_word_address)!=3
            or any(type(x) is not int or x<0 for x in native_word_address)):
        raise ValueError('exact native source word address required')
    with fitz.open(stream=pdf_bytes,filetype='pdf') as doc:
        if type(page_number) is not int or not 1<=page_number<=len(doc):
            raise ValueError('original RCP page not found')
        page = doc[page_number-1]
        words = page.get_text('words')
        targets = [w for w in words if tuple(w[5:8]) == native_word_address]
        # Read the source paint while the original page is open, but only for
        # a candidate code. Other room/note words keep their lexical receipt.
        rendered_code = (
            len(targets) == 1
            and str(targets[0][4]).upper() in _SOURCE_CEILING_CODE_CANDIDATES
            and _visible_native_ceiling_code_ink(page, targets[0])
        )
    target=[w for w in words if tuple(w[5:8])==native_word_address]
    if len(target)!=1:
        raise ValueError('unique original native word missing')
    selected=target[0]
    block=[w for w in words if w[5]==native_word_address[0]]
    line=[w for w in block if w[6]==native_word_address[1]]
    block.sort(key=lambda w:(w[6],w[7]));line.sort(key=lambda w:w[7])
    block_words=tuple(str(w[4]) for w in block)
    line_words=tuple(str(w[4]) for w in line)
    # Rounded display coordinates can move a native word across the proposed
    # source boundary. Containment and its receipt retain the original values.
    bounds=tuple(float(selected[i]) for i in range(4))
    token=str(selected[4]).upper()
    within=_inside(bounds,candidate_plan_bbox_pdf_pt)
    if not within:
        role,reasons='SOURCE_OUTSIDE_PROPOSED_PLAN_VIEWPORT',('original_word_outside_candidate_plan_box',)
    elif token in _SOURCE_CEILING_CODE_CANDIDATES:
        if not rendered_code:
            role,reasons='SOURCE_CEILING_CODE_INK_UNRESOLVED',(
                'original_ceiling_code_glyph_paint_not_proven',
            )
            return NativeRcpWordScopeShadow(
                expected_source_sha256,page_number,native_word_address,
                str(selected[4]),block_words,line_words,bounds,role,reasons,
                original_ceiling_code_visible_ink_verified=False,
            )
        # Native text blocks with just TWO words can be mixed source notes
        # ("GRID OFFICE"), not automatically a code+figure. Verify EVERY
        # source sibling before assigning even lexical CANDIDATE status.
        native_codes=[t.upper() for t in block_words
                      if t.upper() in _SOURCE_CEILING_CODE_CANDIDATES]
        isolated=(
            len(block_words)<=4
            and native_codes == [token]
            and all(
                t.upper() in _SOURCE_CEILING_CODE_CANDIDATES
                or t.isdigit()
                or t.upper() in ('CLG','CEILING','/')
                for t in block_words
            )
        )
        if isolated:
            role,reasons='SOURCE_CEILING_CODE_WORD_CANDIDATE',('original_word_only_no_ceiling_zone_or_material_authority',)
        else:
            role,reasons='SOURCE_GENERAL_NOTE_OR_MIXED_TEXT',('original_complete_block_is_not_single_ceiling_mark',)
    elif len(block_words)>=3:
        role,reasons='SOURCE_GENERAL_NOTE_OR_MIXED_TEXT',('original_complete_block_is_not_single_ceiling_mark',)
    elif token.isdigit():
        role,reasons='SOURCE_NUMERIC_CALLOUT_WORD',('original_figure_not_an_independent_material_or_height',)
    else:
        role,reasons='SOURCE_NON_CEILING_CODE_WORD',('original_room_or_other_label_not_ceiling_material',)
    return NativeRcpWordScopeShadow(
        expected_source_sha256,page_number,native_word_address,str(selected[4]),
        block_words,line_words,bounds,role,reasons,
        original_ceiling_code_visible_ink_verified=bool(within and rendered_code))
