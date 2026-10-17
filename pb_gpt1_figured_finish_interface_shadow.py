"""Measured source floor-finish transitions and trim lines — shadow only.

A finish transition is a shared *physical source* interface between two
different independently authenticated material zones. Contact by proximity,
shared labels or equal area is insufficient to issue a linear trim.
"""
from __future__ import annotations

from dataclasses import dataclass
import math

from pb_migration_contracts import EvidenceResolutionStatus


@dataclass(frozen=True)
class OriginalFinishInterfaceFace:
    source_interface_id: str
    physical_zone_id: str
    source_material_occurrence_id: str
    material_code: str
    start_metric_mm: tuple[float, float]
    end_metric_mm: tuple[float, float]
    source_boundary_stroke_ids: tuple[str, ...]
    source_sha256: str
    revision_id: str
    page_id: str


@dataclass(frozen=True)
class FiguredFinishInterfaceShadow:
    status: EvidenceResolutionStatus
    reason_codes: tuple[str, ...]
    candidate_trim_length_m_by_interface: tuple[tuple[str,float], ...]
    candidate_total_trim_length_m: float | None
    distinct_material_pairs: tuple[tuple[str,str], ...]
    diagnostic_only: bool = True


def _point(raw):
    if type(raw) not in (tuple,list) or len(raw)!=2:
        return None
    if any(type(v) not in (int,float) for v in raw):
        return None
    try:
        pair=(float(raw[0]),float(raw[1]))
    except (TypeError,ValueError,OverflowError):
        return None
    return pair if all(math.isfinite(v) for v in pair) else None


def measure_figured_finish_transition_trims_shadow(
    interface_faces: tuple[OriginalFinishInterfaceFace,...],
) -> FiguredFinishInterfaceShadow:
    """Deduplicate two-sided interfaces; never count same trim twice."""
    def block(reason):
        return FiguredFinishInterfaceShadow(
            EvidenceResolutionStatus.ABSTAINED,(reason,),(),None,()
        )
    if type(interface_faces) not in (tuple,list) or len(interface_faces)<2:
        return block("source_finish_interface_owner_unavailable")
    groups={}
    for face in interface_faces:
        if type(face) is not OriginalFinishInterfaceFace:
            return block("source_finish_interface_record_invalid")
        p,q=_point(face.start_metric_mm),_point(face.end_metric_mm)
        if p is None or q is None or p==q:
            return block("source_finish_interface_measurement_invalid")
        if (
            any(type(v) is not str or not v for v in (
                face.source_interface_id,face.physical_zone_id,
                face.source_material_occurrence_id,face.material_code,
                face.source_sha256,face.revision_id,face.page_id
            ))
            or type(face.source_boundary_stroke_ids) not in (tuple,list)
            or not face.source_boundary_stroke_ids
            or any(type(v) is not str or not v for v in face.source_boundary_stroke_ids)
        ):
            return block("source_finish_interface_receipts_incomplete")
        groups.setdefault(face.source_interface_id,[]).append((face,p,q))
    results,materials=[],[]
    for interface,faces in sorted(groups.items()):
        if len(faces)!=2:
            return block("source_finish_interface_two_material_owners_unavailable")
        a,ap,aq=faces[0];b,bp,bq=faces[1]
        if (
            a.physical_zone_id==b.physical_zone_id
            or a.source_material_occurrence_id==b.source_material_occurrence_id
            or (a.source_sha256,a.revision_id,a.page_id)
            !=(b.source_sha256,b.revision_id,b.page_id)
            or set(a.source_boundary_stroke_ids)!=set(b.source_boundary_stroke_ids)
            or not ((ap==bp and aq==bq) or (ap==bq and aq==bp))
        ):
            return block("source_finish_interface_physical_geometry_conflict")
        if a.material_code==b.material_code:
            # Same material adjoining itself does not need a finish transition.
            continue
        length=math.dist(ap,aq)/1000.0
        if not math.isfinite(length) or length<=0:
            return block("source_finish_interface_length_invalid")
        results.append((interface,length))
        materials.append(tuple(sorted((a.material_code,b.material_code))))
    return FiguredFinishInterfaceShadow(
        EvidenceResolutionStatus.CANDIDATE,
        ("original_source_finish_trim_shadow_only",),
        tuple(results),math.fsum(x for _,x in results),
        tuple(materials),
    )
