"""Exact original figured-dimension terminal extension -> structural wall face.

A vertical/horizontal dimension annotation may sit away from room walls.
Only source-visible extension strokes physically connecting its terminal to
a transverse structural face can nominate that face. No nearest wall, stroke
line-width snap, outer-to-inner conversion or PDF length->metric inference.
"""
from __future__ import annotations
from dataclasses import dataclass
import math
from pb_migration_contracts import EvidenceResolutionStatus
from pb_gpt1_original_figured_face_witness_shadow import (
    SourceFiguredAxis,SourceStructuralFaceStroke,
)


@dataclass(frozen=True)
class OriginalFigureTerminalExtension:
    source_extension_stroke_id: str
    figure_terminal_index: int
    start_pdf_pt: tuple[float,float]
    end_pdf_pt: tuple[float,float]
    source_sha256: str
    revision_id: str
    page_id: str


@dataclass(frozen=True)
class OriginalFigureTerminalExtensionBindingShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str,...]
    bound_finished_face_stroke_ids: tuple[str,...]
    bound_original_witness_stroke_ids: tuple[str,...]
    competing_face_stroke_ids_by_terminal: tuple[tuple[str,...],tuple[str,...]]
    physical_wall_ids: tuple[str,...]
    diagnostic_only: bool = True


def _point(raw):
    if type(raw) not in (tuple,list) or len(raw)!=2 or any(
        type(v) not in (int,float) for v in raw
    ):
        return None
    try:pt=tuple(float(v) for v in raw)
    except (TypeError,ValueError,OverflowError):return None
    return pt if all(math.isfinite(v) for v in pt) else None


def resolve_original_figure_extension_faces_shadow(
    axis: SourceFiguredAxis,
    extensions: tuple[OriginalFigureTerminalExtension,...],
    faces: tuple[SourceStructuralFaceStroke,...],
    *,
    original_native_precision_pt: float = 0.0,
) -> OriginalFigureTerminalExtensionBindingShadow:
    """First positive attempt: source extension meets one finished wall face."""
    def block(reason,candidates=((),())):
        return OriginalFigureTerminalExtensionBindingShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),(),(),candidates,()
        )
    if (
        type(axis) is not SourceFiguredAxis
        or axis.axis not in ("horizontal","vertical")
        or type(axis.source_sha256) is not str
        or len(axis.source_sha256)!=64
        or not axis.revision_id or not axis.page_id
        or type(extensions) not in (tuple,list)
        or type(faces) not in (tuple,list)
        or type(original_native_precision_pt) not in (int,float)
        or not 0<=original_native_precision_pt<=0.1
    ):
        return block("original_figured_extension_source_scope_invalid")
    terminals=(_point(axis.first_terminal_pdf_pt),_point(axis.second_terminal_pdf_pt))
    if any(p is None for p in terminals) or terminals[0]==terminals[1]:
        return block("original_figured_extension_terminals_unavailable")
    if not extensions or not faces:
        return block("original_figured_extension_or_structural_faces_missing")
    ext_by_terminal={0:[],1:[]}
    seen_strokes=set()
    for ext in extensions:
        if (
            type(ext) is not OriginalFigureTerminalExtension
            or type(ext.figure_terminal_index) is not int
            or ext.figure_terminal_index not in (0,1)
            or type(ext.source_extension_stroke_id) is not str
            or not ext.source_extension_stroke_id
            or ext.source_extension_stroke_id in seen_strokes
            or (ext.source_sha256,ext.revision_id,ext.page_id)
            != (axis.source_sha256,axis.revision_id,axis.page_id)
        ):
            return block("original_figured_extension_identity_conflict")
        first,second=_point(ext.start_pdf_pt),_point(ext.end_pdf_pt)
        terminal=terminals[ext.figure_terminal_index]
        if first is None or second is None or first==second:
            return block("original_figured_extension_geometry_invalid")
        if math.dist(first,terminal)<=original_native_precision_pt+1e-9:
            far=second
        elif math.dist(second,terminal)<=original_native_precision_pt+1e-9:
            far=first
        else:
            return block("original_figured_extension_terminal_not_connected")
        if axis.axis=="vertical":
            if abs(first[1]-second[1])>original_native_precision_pt+1e-9:
                return block("original_figured_extension_not_transverse")
        else:
            if abs(first[0]-second[0])>original_native_precision_pt+1e-9:
                return block("original_figured_extension_not_transverse")
        seen_strokes.add(ext.source_extension_stroke_id)
        ext_by_terminal[ext.figure_terminal_index].append((ext,far))
    if any(len(ext_by_terminal[i])!=1 for i in (0,1)):
        return block("original_figured_extension_terminal_competing_or_missing")
    wall_claims=[]
    for face in faces:
        if (
            type(face) is not SourceStructuralFaceStroke
            or type(face.original_stroke_id) is not str or not face.original_stroke_id
            or not face.classified_physical_wall_id
            or (face.source_sha256,face.revision_id,face.page_id)
               != (axis.source_sha256,axis.revision_id,axis.page_id)
        ):
            return block("original_figured_extension_wall_scope_conflict")
        first,second=_point(face.first_pdf_pt),_point(face.second_pdf_pt)
        if first is None or second is None or first==second:
            return block("original_figured_extension_wall_geometry_invalid")
        wall_claims.append((face,first,second))
    contenders=[]
    for i in (0,1):
        far=ext_by_terminal[i][0][1]
        matched=[]
        for face,a,b in wall_claims:
            if axis.axis=="vertical":
                if abs(a[1]-b[1])>original_native_precision_pt+1e-9:
                    continue
                if (abs(far[1]-a[1])<=original_native_precision_pt+1e-9
                        and min(a[0],b[0])-original_native_precision_pt<=far[0]
                           <=max(a[0],b[0])+original_native_precision_pt):
                    matched.append(face)
            else:
                if abs(a[0]-b[0])>original_native_precision_pt+1e-9:
                    continue
                if (abs(far[0]-a[0])<=original_native_precision_pt+1e-9
                        and min(a[1],b[1])-original_native_precision_pt<=far[1]
                           <=max(a[1],b[1])+original_native_precision_pt):
                    matched.append(face)
        contenders.append(tuple(matched))
    rival=tuple(
        tuple(sorted(f.original_stroke_id for f in faceset))
        for faceset in contenders
    )
    if any(len(items)!=1 for items in contenders):
        return block("original_figured_extension_competing_finished_faces",rival)
    selected=tuple(group[0] for group in contenders)
    if any(w.physical_face_role!="finished_inner_face" for w in selected):
        return block("original_figured_extension_finished_face_unproved",rival)
    if selected[0].classified_physical_wall_id==selected[1].classified_physical_wall_id:
        return block("original_figured_extension_opposing_wall_identity_conflict",rival)
    return OriginalFigureTerminalExtensionBindingShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_figured_terminal_to_finished_face_shadow_only",),
        tuple(w.original_stroke_id for w in selected),
        tuple(ext_by_terminal[i][0][0].source_extension_stroke_id for i in (0,1)),
        rival,tuple(w.classified_physical_wall_id for w in selected),
    )
