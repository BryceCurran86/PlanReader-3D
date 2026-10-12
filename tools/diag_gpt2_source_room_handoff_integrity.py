"""Producer-owned Maryborough source room -> floor -> quantity handoff auditor.

Read-only. No benchmark truth, name-based geometry, fallback walls, or areas.
Do not confuse an authenticated word/face receipt with a commercial floor.
"""
from __future__ import annotations
from collections import Counter
import math
import re

NAMES = ("FOOD PREP","COLD ROOM","OFFICE","FREEZER","PWD","AIRLOCK","LAUNDRY",
         "SALES","POS COUNTER","FOOD SERVICE","WASH UP","TRUCK DRIVER LOUNGE",
         "M-AMB","F-AMB","DRY STORE")


def _owned(v):
    return isinstance(v,str) and bool(v) and v==v.strip()


def _name(v):
    return " ".join(v.upper().split()) if isinstance(v,str) else ""


def _polygon(source):
    """Require valid original native geometry before reporting a floor owner.

    A positive upstream area field does not authenticate a self-intersecting
    native polygon. This diagnostic neither repairs nor measures such a face.
    """
    vertices = getattr(source, "polygon_pdf_pts", None)
    area = getattr(source, "area_page_pts2", None)
    if not (
        isinstance(vertices, (tuple, list)) and len(vertices) >= 3
        and all(
            isinstance(pt, (tuple, list)) and len(pt) == 2
            and all(type(value) in (int, float) and math.isfinite(value)
                    for value in pt)
            for pt in vertices
        )
        and type(area) in (int, float)
        and math.isfinite(area) and area > 0
    ):
        return False
    # Original-source room polygons may be open vertex rings (no repeated
    # final point); Shapely validates closure, crossings and zero area without
    # changing the vertices. Never use buffer(0) or polygon repair here.
    from shapely.errors import GEOSException
    from shapely.geometry import Polygon
    try:
        native_face = Polygon(vertices)
        return (
            not native_face.is_empty
            and native_face.is_valid
            and native_face.area > 0
            and len(native_face.interiors) == 0
        )
    except (TypeError, ValueError, OverflowError, GEOSException):
        return False

def _source(obj,sha):
    return getattr(obj,"source_sha256",None)==sha


def _metric_quantity(q):
    return (not getattr(q,"abstained",True)
            and str(getattr(q,"status","")).lower() in ("firm","corroborated")
            and getattr(q,"unit",None) in ("m2","m²")
            and type(getattr(q,"value",None)) in (int,float)
            and math.isfinite(q.value) and q.value>0
            and _owned(getattr(q,"quantity_id",None))
            and isinstance(getattr(q,"input_entity_ids",None),tuple)
            and bool(q.input_entity_ids)
            and len(set(q.input_entity_ids))==len(q.input_entity_ids)
            and isinstance(getattr(q,"evidence_ids",None),tuple)
            and bool(q.evidence_ids)
            and all(_owned(x) for x in q.evidence_ids)
            and len(q.evidence_ids)==len(set(q.evidence_ids)))


def report_source_room_handoff(claim, *, original_source_sha, targets=NAMES):
    """Report the first unproved gate for each exact producer-named room.

    A quantity is public-ready only if a UNIQUE original room, canonical
    floor, and FIRM source area all own the exact same canonical lineage.
    Finish/RCP is independently withheld until real occurrence ownership.
    """
    if not isinstance(original_source_sha,str) or not re.fullmatch(
        r"[0-9a-f]{64}",original_source_sha):
        raise ValueError("real source SHA-256 must be explicit")
    if not isinstance(targets,(list,tuple)) or not targets:
        raise ValueError("explicit report targets required")
    target_names=[_name(x) for x in targets]
    if (any(not _owned(x) for x in target_names)
            or len(set(target_names))!=len(target_names)):
        raise ValueError("ambiguous target names")
    rooms=tuple(getattr(claim,"canonical_rooms",()) or ())
    floors=tuple(getattr(claim,"canonical_floors",()) or ())
    quantities=tuple(getattr(claim,"room_area_quantity_evidence",()) or ())
    finishes=tuple(getattr(claim,"floor_finish_quantity_evidence",()) or ())
    ceilings=tuple(getattr(claim,"ceiling_lining_quantity_evidence",()) or ())
    # No foreign-source claimant can enter the report as positive evidence.
    eligible=[r for r in rooms if _name(getattr(r,"room_label",None)) in target_names]
    grouped={}
    for room in eligible:
        grouped.setdefault(_name(room.room_label),[]).append(room)
    floor_ids=Counter(getattr(f,"canonical_floor_id",None) for f in floors)
    floor_by_room={}
    for floor in floors:
        floor_by_room.setdefault(getattr(floor,"room_entity_id",None),[]).append(floor)
    q_ids=Counter(getattr(q,"quantity_id",None) for q in quantities)
    # Room-area producer QuantityEvidence is explicitly keyed to original
    # room.face_id, NOT to a canonical floor ID. Its source receipt/evidence
    # and SHA/revision/viewport must be authenticated before the later
    # floor metric projection can be checked.
    room_ids=Counter(getattr(r,"physical_room_id",None) for r in eligible)
    face_ids=Counter(getattr(r,"source_room_face_record_id",None) for r in eligible)
    direct_labels=Counter(getattr(r,"room_label_binding_record_id",None)
                          for r in eligible if _owned(getattr(r,"room_label_binding_record_id",None)))
    text_observations=Counter(id for r in eligible
        for id in (getattr(r,"room_label_evidence_ids",()) or ())
        if _owned(id))
    rows=[]
    for name in target_names:
        owners=grouped.get(name,[])
        gate="SOURCE_PHYSICAL_FACE_UNAVAILABLE"
        room_id=face_id=floor_id=quantity_id=None
        label_binding_id=None
        original_label_evidence_ids=()
        original_metric_evidence_ids=()
        original_metric_authority=None
        amount=None
        if len(owners)>1:
            gate="ROOM_LABEL_MULTIPLE_SOURCE_FACES"
        elif len(owners)==1:
            r=owners[0]
            room_id=getattr(r,"physical_room_id",None)
            face_id=getattr(r,"source_room_face_record_id",None)
            label_id=getattr(r,"room_label_binding_record_id",None)
            texts=getattr(r,"room_label_evidence_ids",()) or ()
            if (not _source(r,original_source_sha)
                    or not _owned(getattr(r,"document_id",None))
                    or not _owned(getattr(r,"revision_id",None))
                    or not _owned(getattr(r,"snapshot_id",None))
                    or not _owned(getattr(r,"decision_scope_id",None))
                    or not _owned(getattr(r,"viewport_id",None))
                    or not _owned(room_id) or not _owned(face_id)
                    or room_ids[room_id]!=1 or face_ids[face_id]!=1):
                gate="SOURCE_ROOM_FACE_IDENTITY_CONFLICT"
            elif (not _owned(label_id) or direct_labels[label_id]!=1
                    or not isinstance(texts,(tuple,list)) or not texts
                    or any(not _owned(x) or text_observations[x]!=1 for x in texts)
                    or len(set(texts))!=len(texts)):
                gate="ORIGINAL_ROOM_LABEL_RECEIPT_AMBIGUOUS"
            elif not _polygon(r) or not getattr(r,"geometry_complete",False):
                gate="SOURCE_ROOM_PHYSICAL_POLYGON_INCOMPLETE"
            else:
                label_binding_id=label_id
                original_label_evidence_ids=tuple(sorted(texts))
                matches=floor_by_room.get(getattr(r,"canonical_room_id",None),[])
                if len(matches)!=1:
                    gate="CANONICAL_FLOOR_OWNER_UNAVAILABLE"
                else:
                    f=matches[0]
                    floor_id=getattr(f,"canonical_floor_id",None)
                    if (not _source(f,original_source_sha)
                            or not _owned(floor_id) or floor_ids[floor_id]!=1
                            or f.source_room_face_record_id!=face_id
                            or f.document_id!=r.document_id
                            or f.snapshot_id!=r.snapshot_id
                            or f.page_id!=r.page_id
                            or f.viewport_id!=r.viewport_id
                            or f.polygon_pdf_pts!=r.polygon_pdf_pts
                            or not getattr(f,"geometry_complete",False)):
                        gate="FLOOR_ORIGINAL_PHYSICAL_FACE_LINEAGE_CONFLICT"
                    else:
                        # Support-only source dimensions are NOT page geometry.
                        matches=[q for q in quantities
                                 if _metric_quantity(q)
                                 and q_ids[q.quantity_id]==1
                                 and face_id in q.evidence_ids
                                 and isinstance(getattr(q,"metadata",None),dict)
                                 and q.metadata.get("source_sha256")==original_source_sha
                                 and q.metadata.get("revision_id")==r.revision_id
                                 and q.metadata.get("viewport_id")==r.viewport_id
                                 and len(q.input_entity_ids)==1
                                 and q.semantic_key=="room_area:"+q.input_entity_ids[0]]
                        if len(matches)!=1:
                            gate="FIRM_AREA_SOURCE_MEASUREMENT_UNAVAILABLE"
                        else:
                            q=matches[0]
                            quantity_id=q.quantity_id
                            original_metric_evidence_ids=tuple(sorted(q.evidence_ids))
                            original_metric_authority=(
                                q.authority if _owned(getattr(q,"authority",None)) else None
                            )
                            amount=float(q.value)
                            if (not getattr(f,"metric_geometry_complete",False)
                                or f.metric_area_quantity_id!=quantity_id
                                or not math.isfinite(getattr(f,"metric_area_m2",float("nan")) or float("nan"))
                                or not math.isclose(f.metric_area_m2,amount,abs_tol=1e-8)
                                or not getattr(f,"physical_floor_surface_identity_resolved",False)
                                or not getattr(f,"commercial_quantity_authority",False)):
                                gate="COMMERCIAL_FLOOR_AREA_AUTHORITY_UNAVAILABLE"
                            else:
                                gate="SOURCE_ROOM_AREA_READY_FOR_GPT1_GPT3_REVIEW"
        rows.append({
            "source_room_label":name,
            "first_unproved_authority":gate,
            "original_physical_room_id":room_id if _owned(room_id) else None,
            "original_source_face_receipt_id":face_id if _owned(face_id) else None,
            "canonical_floor_id":floor_id if _owned(floor_id) else None,
            "original_label_binding_record_id":label_binding_id,
            "original_label_evidence_ids":list(original_label_evidence_ids),
            "documented_area_quantity_id":quantity_id,
            "documented_area_source_evidence_ids":list(original_metric_evidence_ids),
            "documented_area_original_authority":original_metric_authority,
            "source_proven_area_m2":amount,
            "floor_finish_publication_allowed":False,
            "ceiling_lining_publication_allowed":False,
            "source_finish_occurrence_link_unavailable":True,
            "metric_area_inferred_from_page_points":False,
            "benchmark_accuracy":None,
        })
    # Raw quantity inventories are never enough to infer source room ownership.
    return {
        "source_sha256":original_source_sha,
        "reported_source_room_count":len(rows),
        "room_handoff_first_gates":rows,
        "original_source_room_candidate_count":len(eligible),
        "original_canonical_floor_candidate_count":len(floors),
        "source_room_area_quantity_candidate_count":len(quantities),
        "source_finish_quantity_candidate_count":len(finishes),
        "source_ceiling_lining_quantity_candidate_count":len(ceilings),
        "floor_finish_publication_allowed":False,
        "ceiling_lining_publication_allowed":False,
        "dry_store_must_abstain_without_new_proof":True,
        "diagnostic_only":True,
        "benchmark_accuracy":None,
    }
