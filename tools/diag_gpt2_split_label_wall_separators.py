"""Read-only exact producer-owned wall separators for split source-room labels.

Exact wall geometry may prove that TWO face polygons share a physical wall.
It NEVER proves they represent one room or permits dropping the wall.
No nearest-label, PDF scale, inferred area, or topology mutation occurs here.
"""
from __future__ import annotations
import math
from typing import Any

_EPS_PDF_PT=1e-6


def _finite_native_edge(raw: Any):
    try:
        if len(raw)!=2:
            return None
        a,b=raw
        if len(a)!=2 or len(b)!=2:
            return None
        pts=((float(a[0]),float(a[1])),(float(b[0]),float(b[1])))
    except (TypeError,ValueError,IndexError):
        return None
    if not all(math.isfinite(v) for point in pts for v in point):
        return None
    if math.dist(pts[0],pts[1])<=_EPS_PDF_PT:
        return None
    return pts


def _edge_reverse_equal(first,second) -> bool:
    return all(
        math.dist(first[i],second[1-i])<=_EPS_PDF_PT
        for i in range(2)
    )


def split_face_source_wall_separator_gate(
    candidate: Any,
    faces_by_record_id: dict[str,Any],
) -> dict[str,Any]:
    """CANDIDATE-only pairwise source-wall separator provenance."""
    ids=tuple(str(v) for v in getattr(candidate,"source_room_face_record_ids",()) or ())
    label=str(getattr(candidate,"label","") or "")
    result={
        "label":label,
        "source_split_candidate_record_id":str(getattr(candidate,"record_id","") or ""),
        "source_room_face_record_ids":list(ids),
        "pairwise_source_wall_gates":[],
        "merge_source_faces_authorized":False,
        "source_room_label_published":False,
        "metric_quantity_published":False,
    }
    if not label or len(ids)<2 or len(set(ids))!=len(ids):
        result["first_gate"]="split_source_face_identity_invalid"
        return result
    actual=[]
    for face_id in ids:
        face=faces_by_record_id.get(face_id)
        if face is None or str(getattr(face,"record_id",""))!=face_id:
            result["first_gate"]="split_source_face_record_missing"
            return result
        if any(getattr(face,field,None)!=getattr(candidate,field,None)
               for field in ("document_id","revision_id","source_sha256",
                             "snapshot_id","page_id","decision_scope_id")):
            result["first_gate"]="split_source_face_lineage_mismatch"
            return result
        actual.append(face)

    for i in range(len(actual)):
        for j in range(i+1,len(actual)):
            fa,fb=actual[i],actual[j]
            edge_a=[]
            edge_b=[]
            malformed=False
            for face,bag in ((fa,edge_a),(fb,edge_b)):
                for row in getattr(face,"boundary_wall_edges",()) or ():
                    if not isinstance(row,(tuple,list)) or len(row)!=2:
                        malformed=True
                        continue
                    wall_id,raw=row
                    parsed=_finite_native_edge(raw)
                    if not str(wall_id).strip() or parsed is None:
                        malformed=True
                        continue
                    bag.append((str(wall_id),parsed))
            shared=[]
            competing=[]
            for wall_a,geom_a in edge_a:
                for wall_b,geom_b in edge_b:
                    if not _edge_reverse_equal(geom_a,geom_b):
                        continue
                    source={
                        "source_face_a":str(fa.record_id),
                        "source_face_b":str(fb.record_id),
                        "source_wall_id_a":wall_a,
                        "source_wall_id_b":wall_b,
                        "native_edge_pdf_pts":[list(p) for p in geom_a],
                    }
                    if wall_a==wall_b:
                        shared.append(source)
                    else:
                        competing.append(source)
            pair={
                "first_source_face_record_id":str(fa.record_id),
                "second_source_face_record_id":str(fb.record_id),
                "matching_authenticated_wall_segments":shared,
                "same_geometry_competing_wall_owners":competing,
            }
            if malformed:
                pair["first_gate"]="malformed_source_wall_subedges"
            elif competing:
                pair["first_gate"]="competing_wall_owners_on_shared_source_edge"
            elif shared:
                pair["first_gate"]="source_proven_wall_separator_do_not_merge"
            else:
                pair["first_gate"]="no_exact_shared_source_wall_separator"
            result["pairwise_source_wall_gates"].append(pair)
    result["first_gate"]="split_label_face_wall_adjacency_diagnostic_only"
    return result
