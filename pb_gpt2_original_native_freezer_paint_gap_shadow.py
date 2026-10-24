"""Original two-width wall-face ink gap against thinner filling (SOURCE ONLY).

Does not classify any installed door, wall, panel, threshold, FT2/FT3/EPX
floor, figure/scale, FIRM or commercial quantity. Original source path IDs
are caller-proposed diagnostic candidates, NOT producer-issued physical IDs.
"""
from __future__ import annotations
from dataclasses import dataclass
from hashlib import sha256
from math import isfinite
import fitz
from pb_migration_contracts import EvidenceResolutionStatus
from pb_gpt2_original_native_crossview_wall_caps_shadow import _source_line


@dataclass(frozen=True)
class NativePaintGapScope:
    page_number: int
    thick_outer_face_paths: tuple[int,int,int,int]
    thin_inner_filling_paths: tuple[int,int]


@dataclass(frozen=True)
class NativePaintGapCandidate:
    page_number: int
    original_path_ids: tuple[int,...]
    gap_x_pdf_pt: tuple[float,float]
    wall_face_y_pdf_pt: tuple[float,float]
    thick_width_pdf_pt: float
    thin_width_pdf_pt: float


@dataclass(frozen=True)
class OriginalPaintGapShadow:
    status: EvidenceResolutionStatus
    source_sha256: str
    first: NativePaintGapCandidate
    second: NativePaintGapCandidate
    candidate_translations: tuple[tuple[float,float,bool],...]
    matching_translation: tuple[float,float] | None
    reason_codes: tuple[str,...]
    shadow_only: bool = True
    structural_wall_owned: bool = False
    physical_door_owned: bool = False
    doorway_threshold_owned: bool = False
    material_floor_owned: bool = False
    metric_area_owned: bool = False
    firm_quantity_issued: bool = False
    commercial_projection_allowed: bool = False



def _is_visible_solid_black_original_stroke(drawing, minimum_width:float=0.05)->bool:
    """Source visibility test, not an independently proven physical-wall role."""
    try:
        opacity=drawing.get("stroke_opacity")
        width=drawing.get("width")
        color=drawing.get("color")
        return (
            type(opacity) in (int,float) and isfinite(opacity)
            and opacity == 1.0
            and drawing.get("dashes") == "[] 0"
            and drawing.get("fill") is None
            and type(width) in (int,float) and isfinite(width)
            and width >= minimum_width
            and type(color) in (tuple,list) and len(color)==3
            and all(type(component) in (int,float) and isfinite(component)
                    and 0.0 <= component <= .04 for component in color)
        )
    except (ValueError,TypeError,OverflowError):
        return False


def _is_visible_opaque_black_original_fill(drawing)->bool:
    """Filled native rectangle paint is a rival even without a line stroke."""
    fill=drawing.get("fill")
    opacity=drawing.get("fill_opacity")
    return (
        type(opacity) in (int,float) and isfinite(opacity)
        and opacity==1.0
        and type(fill) in (tuple,list) and len(fill)==3
        and all(type(x) in (int,float) and isfinite(x)
                and 0.0<=x<=.04 for x in fill)
    )


def _selected_original_painted_line(drawings,address:int):
    # A selected invisible/dashed source stroke must fail here before the
    # stricter, already-merged native wall-cap helper examines it. Preserve
    # the parent helper's own index, geometry and source-line validation.
    if (type(address) is int and 0 <= address < len(drawings)
            and not _is_visible_solid_black_original_stroke(drawings[address])):
        raise ValueError("selected original painted stroke is invisible or non-solid")
    return _source_line(drawings,address)

def _inspect_native_paint_gap(page, scope:NativePaintGapScope, tolerance:float):
    ids=(*scope.thick_outer_face_paths,*scope.thin_inner_filling_paths)
    if len(ids)!=6 or len(set(ids))!=6:
        raise ValueError("six distinct original painted paths required")
    drawings=page.get_drawings()
    thick=[_selected_original_painted_line(drawings,i) for i in scope.thick_outer_face_paths]
    thin=[_selected_original_painted_line(drawings,i) for i in scope.thin_inner_filling_paths]
    if any(abs(a[1]-a[3])>tolerance for a in (*thick,*thin)):
        raise ValueError("source painted wall/filling spans are not horizontal")
    levels=sorted({round(a[1],2) for a in thick})
    if len(levels)!=2 or levels[1]-levels[0]<=tolerance:
        raise ValueError("no independent two-line original thick wall faces")
    caps=[]
    for level in levels:
        outer=[a for a in thick if abs(a[1]-level)<=tolerance]
        filling=[a for a in thin if abs(a[1]-level)<=tolerance]
        if len(outer)!=2 or len(filling)!=1:
            raise ValueError("source band has incomplete face or filling inventory")
        (left,right)=sorted(tuple(sorted((a[0],a[2]))) for a in outer)
        gap=(left[1],right[0])
        if gap[1]-gap[0]<=tolerance:
            raise ValueError("original thick wall ink never separates into two ends")
        inner=tuple(sorted((filling[0][0],filling[0][2])))
        if abs(inner[0]-gap[0])>tolerance or abs(inner[1]-gap[1])>tolerance:
            raise ValueError("thin original source does not span complete thick-wall gap")
        caps.append(gap)
    if any(abs(a-b)>tolerance for a,b in zip(*caps)):
        raise ValueError("thick wall-face source gap differs across parallel strokes")
    outer_widths=[a[4] for a in thick]
    inner_widths=[a[4] for a in thin]
    if (max(outer_widths)-min(outer_widths)>0.05
            or max(inner_widths)-min(inner_widths)>0.05
            or min(outer_widths)-max(inner_widths)<0.25):
        raise ValueError("two independent original paint-width roles unproven")
    lo,hi=caps[0]
    for index,drawing in enumerate(drawings):
        if index in ids:
            continue
        stroke_rival=_is_visible_solid_black_original_stroke(
            drawing, minimum_width=min(outer_widths)-0.05)
        filled_rival=_is_visible_opaque_black_original_fill(drawing)
        if not (stroke_rival or filled_rival):
            continue
        for item in drawing["items"]:
            # A solid opaque black rectangle FILL is source paint, even if
            # it has no stroke/width/dashes at all. It is only negative
            # opposing ink: never physical wall or door evidence.
            if filled_rival and item[0]=="re":
                rect=item[1]
                if (not isinstance(rect,fitz.Rect) or
                    not all(isfinite(v) for v in
                            (rect.x0,rect.y0,rect.x1,rect.y1))):
                    raise ValueError("competing original fill rectangle invalid")
                if (any(rect.y0<=level<=rect.y1 for level in levels)
                    and min(rect.x1,hi)-max(rect.x0,lo)>tolerance):
                    raise ValueError(
                        "competing original opaque black fill bridges selected gap"
                    )
            if not stroke_rival:
                continue
            # Native solid outline rectangles are emitted as "re", not
            # four separate "l" entries.  Their painted horizontal edges
            # must take part in the SAME competing-thick-ink census.
            if item[0] == "l":
                p, q = item[1:3]
                segments = ((p.x, p.y, q.x, q.y),)
            elif item[0] == "re":
                rect = item[1]
                if (
                    not isinstance(rect, fitz.Rect)
                    or not all(isfinite(v) for v in
                               (rect.x0, rect.y0, rect.x1, rect.y1))
                ):
                    raise ValueError("competing original rectangle geometry invalid")
                segments = (
                    (rect.x0, rect.y0, rect.x1, rect.y0),
                    (rect.x0, rect.y1, rect.x1, rect.y1),
                )
            else:
                continue
            for x1,y1,x2,y2 in segments:
                if (abs(y1-y2)>tolerance or
                        min(abs(y1-y) for y in levels)>tolerance):
                    continue
                a,b=sorted((x1,x2))
                # Source-native endpoint return <= witness tolerance does
                # not defeat a gap.  Any greater solid thick overlap does.
                if min(b,hi)-max(a,lo)>tolerance:
                    raise ValueError(
                        "competing original thick wall ink bridges selected gap"
                    )
    return NativePaintGapCandidate(scope.page_number,tuple(sorted(ids)),
        tuple(round(z,5) for z in caps[0]),tuple(levels),
        round(outer_widths[0],4),round(inner_widths[0],4))


def audit_original_paint_gap_crossview_shadow(
    source_bytes:bytes, *, expected_sha256:str,
    first:NativePaintGapScope,second:NativePaintGapScope,
    translations:tuple[tuple[float,float],...],tolerance:float=0.25,
)->OriginalPaintGapShadow:
    if type(source_bytes) is not bytes or sha256(source_bytes).hexdigest()!=expected_sha256:
        raise ValueError("SHA-pinned original PDF bytes unavailable or foreign")
    if (type(tolerance) not in (int,float) or not isfinite(tolerance)
            or not 0.001<=tolerance<=0.25):
        raise ValueError("original native ink tolerance invalid")
    if not translations:
        raise ValueError("all competing original source transformations required")
    with fitz.open(stream=source_bytes,filetype="pdf") as pdf:
        if (type(first) is not NativePaintGapScope or type(second) is not NativePaintGapScope
                or min(first.page_number,second.page_number)<1
                or max(first.page_number,second.page_number)>len(pdf)
                or first.page_number==second.page_number):
            raise ValueError("invalid two original page scopes")
        a=_inspect_native_paint_gap(pdf[first.page_number-1],first,tolerance)
        b=_inspect_native_paint_gap(pdf[second.page_number-1],second,tolerance)
    seen=set();checks=[];accepted=[]
    for trans in translations:
        if (type(trans) not in (tuple,list) or len(trans)!=2
                or any(type(x) not in (int,float) or not isfinite(x) for x in trans)):
            raise ValueError("invalid original source translation")
        dx,dy=(round(float(x),5) for x in trans)
        if (dx,dy) in seen:raise ValueError("repeated translation cannot cast two votes")
        seen.add((dx,dy))
        matching=(all(abs(x+dx-y)<=tolerance for x,y in zip(a.gap_x_pdf_pt,b.gap_x_pdf_pt))
                  and all(abs(x+dy-y)<=tolerance for x,y in zip(a.wall_face_y_pdf_pt,b.wall_face_y_pdf_pt)))
        checks.append((dx,dy,matching))
        if matching:accepted.append((dx,dy))
    unique=len(accepted)==1
    return OriginalPaintGapShadow(
        EvidenceResolutionStatus.CANDIDATE if unique else EvidenceResolutionStatus.ABSTAINED,
        expected_sha256,a,b,tuple(sorted(checks)),accepted[0] if unique else None,
        ("original_two_width_wall_ink_only",) if unique
        else ("original_painted_gap_registration_unproven",),
    )
