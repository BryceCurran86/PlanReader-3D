"""Original figured word ↔ independent ticks ↔ original wall-cap ink: SOURCE ONLY.

Typed native PDF addresses are re-extracted under immutable SHA. Diagnostic
word/path correspondence does NOT issue wall, door, threshold, height/width
measurement authority, FIRM quantity, floor finish or commercial records.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
import fitz
from pb_migration_contracts import EvidenceResolutionStatus
from pb_gpt2_original_native_crossview_wall_caps_shadow import _source_line


@dataclass(frozen=True)
class OriginalFiguredTickScope:
    page_number: int
    word_address: tuple[int,int,int]
    baseline_path: int
    diagonal_tick_pairs: tuple[tuple[int,int],tuple[int,int]]
    vertical_extension_pairs: tuple[tuple[int,int],tuple[int,int]]
    wall_cap_paths: tuple[int,int]


@dataclass(frozen=True)
class OriginalFiguredWallCapShadow:
    status: EvidenceResolutionStatus
    source_sha256: str
    original_page_number: int
    original_word_address: tuple[int,int,int]
    original_figure_text: str
    source_declared_figure_mm: float | None
    source_tick_x_pdf_pt: tuple[float,float]
    source_cap_x_pdf_pt: tuple[float,float]
    figure_text_center_pdf_pt: float
    reason_codes: tuple[str,...]
    shadow_only: bool = True
    physical_wall_owned: bool = False
    physical_door_owned: bool = False
    doorway_threshold_owned: bool = False
    metric_measurement_owned: bool = False
    floor_or_ceiling_finish_owned: bool = False
    signed_quantity_issued: bool = False
    commercial_projection_allowed: bool = False


def audit_original_figured_cap_chain_shadow(
    original_pdf_bytes:bytes,*,expected_sha256:str,
    scope:OriginalFiguredTickScope,native_tolerance_pt:float=0.25,
)->OriginalFiguredWallCapShadow:
    if type(original_pdf_bytes) is not bytes or sha256(original_pdf_bytes).hexdigest()!=expected_sha256:
        raise ValueError("original PDF source SHA or bytes unavailable")
    if (type(scope) is not OriginalFiguredTickScope
            or type(native_tolerance_pt) not in (int,float)
            or not isfinite(native_tolerance_pt)
            or not 0.001<=native_tolerance_pt<=0.25):
        raise ValueError("original source selector/tolerance invalid")
    paths=(scope.baseline_path,*scope.diagonal_tick_pairs[0],
           *scope.diagonal_tick_pairs[1],*scope.vertical_extension_pairs[0],
           *scope.vertical_extension_pairs[1],*scope.wall_cap_paths)
    if len(paths)!=11 or len(set(paths))!=11:
        raise ValueError("all native original dimension and cap paths must be distinct")
    with fitz.open(stream=original_pdf_bytes,filetype="pdf") as document:
        if scope.page_number<1 or scope.page_number>len(document):
            raise ValueError("original source page unavailable")
        page=document[scope.page_number-1]
        words=[w for w in page.get_text("words")
               if tuple(int(i) for i in w[5:8])==scope.word_address]
        if len(words)!=1:
            raise ValueError("word source block/line/index not uniquely visible")
        word=words[0]
        strokes=page.get_drawings()
        baseline=_source_line(strokes,scope.baseline_path)
        diagonal_pairs=[[ _source_line(strokes,p) for p in pair]
                        for pair in scope.diagonal_tick_pairs]
        extension_pairs=[[ _source_line(strokes,p) for p in pair]
                         for pair in scope.vertical_extension_pairs]
        cap_lines=[_source_line(strokes,p) for p in scope.wall_cap_paths]
    tol=native_tolerance_pt
    if abs(baseline[1]-baseline[3])>tol:
        raise ValueError("original figured dimension baseline not horizontal")
    pivots=[]
    for index,pair in enumerate(diagonal_pairs):
        ends=[(line[0],line[1]) for line in pair]+[(line[2],line[3]) for line in pair]
        common=[e for e in ends if sum(
            abs(e[0]-candidate[0])<=tol and abs(e[1]-candidate[1])<=tol
            for candidate in ends)>=2]
        if not common:
            raise ValueError("two independent dimension diagonal ticks do not share source pivot")
        pivot=common[0]
        if (abs(pivot[1]-baseline[1])>tol
                or not min(baseline[0],baseline[2])-tol<=pivot[0]<=max(baseline[0],baseline[2])+tol):
            raise ValueError("original dimension tick not on one source baseline")
        for line in extension_pairs[index]:
            if (abs(line[0]-line[2])>tol
                    or abs(line[0]-pivot[0])>tol
                    or not min(line[1],line[3])-tol<=pivot[1]<=max(line[1],line[3])+tol):
                raise ValueError("original extension line does not own figured tick")
        pivots.append(pivot)
    pivots.sort()
    if pivots[1][0]-pivots[0][0]<=tol:
        raise ValueError("the two original figured dimension ticks collapse")
    for line in cap_lines:
        if (abs(line[0]-line[2])>tol
                or min(line[1],line[3])<pivots[0][1]
                or min(line[1],line[3])-pivots[0][1]>30):
            raise ValueError("source cap is not the finite line below the original figured tick")
    caps=sorted(line[0] for line in cap_lines)
    if any(abs(x-y)>tol for x,y in zip(caps,[pivot[0] for pivot in pivots])):
        raise ValueError("original printed figure ticks and two wall caps are unrelated")
    center=(float(word[0])+float(word[2]))*0.5
    midpoint=(pivots[0][0]+pivots[1][0])*0.5
    figure_centered=abs(center-midpoint)<=(float(word[2])-float(word[0]))*0.5+tol
    # A native numeric word with the right x-centre but printed elsewhere
    # on the sheet is NOT owned by these two original dimension ticks.
    # Preserve the source's own glyph height as the local vertical band;
    # no plan-wide nearest-label or wall snap is permitted here.
    word_top,word_bottom=float(word[1]),float(word[3])
    word_height=word_bottom-word_top
    figure_near_source_baseline=(
        isfinite(word_height) and word_height>0
        and word_top-word_height-tol <= baseline[1]
        <= word_bottom+word_height+tol
    )
    figure_text=str(word[4])
    numeric=None
    try:
        if figure_text.replace(".", "", 1).isdigit() and 0<float(figure_text)<1e7:
            numeric=float(figure_text)
    except (TypeError,ValueError,OverflowError):
        pass
    valid=numeric is not None and figure_centered and figure_near_source_baseline
    return OriginalFiguredWallCapShadow(
        EvidenceResolutionStatus.CANDIDATE if valid else EvidenceResolutionStatus.ABSTAINED,
        expected_sha256,scope.page_number,scope.word_address,figure_text,
        numeric if valid else None,
        tuple(round(p[0],5) for p in pivots),
        tuple(round(x,5) for x in caps),
        round(center,5),
        ("original_figured_word_and_two_native_caps_candidate_only",) if valid
        else ("original_figured_word_has_competing_tick_owner",),
    )
