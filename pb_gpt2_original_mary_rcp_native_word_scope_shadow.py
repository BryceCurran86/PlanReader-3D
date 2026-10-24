"""Original SHA-owned RCP text word/line source-role DIAGNOSTIC only.

Never authenticates an RCP physical ceiling zone, material definition, metric
scale, customer-facing mark, FIRM area or benchmark target. Every original
text block and competing word is preserved; no nearest room-word election.
"""
from __future__ import annotations
from dataclasses import dataclass, asdict
from hashlib import sha256
from math import isfinite
import fitz

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
        words=doc[page_number-1].get_text('words')
    target=[w for w in words if tuple(w[5:8])==native_word_address]
    if len(target)!=1:
        raise ValueError('unique original native word missing')
    selected=target[0]
    block=[w for w in words if w[5]==native_word_address[0]]
    line=[w for w in block if w[6]==native_word_address[1]]
    block.sort(key=lambda w:(w[6],w[7]));line.sort(key=lambda w:w[7])
    block_words=tuple(str(w[4]) for w in block)
    line_words=tuple(str(w[4]) for w in line)
    bounds=tuple(round(float(selected[i]),5) for i in range(4))
    token=str(selected[4]).upper()
    within=_inside(bounds,candidate_plan_bbox_pdf_pt)
    if not within:
        role,reasons='SOURCE_OUTSIDE_PROPOSED_PLAN_VIEWPORT',('original_word_outside_candidate_plan_box',)
    elif token in _SOURCE_CEILING_CODE_CANDIDATES:
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
        block_words,line_words,bounds,role,reasons)
