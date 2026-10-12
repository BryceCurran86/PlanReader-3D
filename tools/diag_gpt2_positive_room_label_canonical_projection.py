"""Diagnose *literal* original source label->canonical face projection failures.

No room geometry or name-based ownership is introduced. Positive source
labels must be producer-authenticated by their own original PDF replay,
and canonical matching uses exactly the original physical FACE RECEIPT.
"""
from __future__ import annotations

from collections import Counter
import re


def original_source_label_to_canonical_first_gates(
    original: dict, canonical_rooms: tuple[object, ...], *,
    expected_original_sha: str,
) -> dict:
    if (not isinstance(expected_original_sha,str)
            or re.fullmatch(r"[0-9a-f]{64}",expected_original_sha) is None
            or not isinstance(original,dict)
            or original.get("original_pdf_sha_verified")!=expected_original_sha):
        raise ValueError("original source replay SHA provenance unavailable")
    scopes=original.get("source_scope_first_failures")
    if (not isinstance(scopes,list) or not scopes
            or not isinstance(canonical_rooms,tuple)):
        raise ValueError("producer source scopes and canonical rooms required")
    sources=[]
    source_scope_ids=set()
    for scope in scopes:
        if not isinstance(scope,dict):
            raise ValueError("foreign original source scope")
        scope_id=scope.get("decision_scope_id")
        if (not isinstance(scope_id,str) or not scope_id
                or scope_id in source_scope_ids
                or scope.get("page_id")!="7"):
            raise ValueError("duplicated or foreign original page7 source scope")
        source_scope_ids.add(scope_id)
        gate=scope.get("original_source_label_gate")
        if gate is None:continue
        if not isinstance(gate,dict):raise ValueError("untrusted source label ledger")
        positive=gate.get("direct_source_labels")
        if not isinstance(positive,list):
            raise ValueError("missing original positive label inventory")
        if (type(gate.get("direct_source_label_count")) is not int
                or gate["direct_source_label_count"]!=len(positive)):
            raise ValueError("unproven original label count")
        for row in positive:
            if not isinstance(row,dict):
                raise ValueError("original source label receipt must be typed")
            face=row.get("source_face_receipt_id")
            label=row.get("label")
            face_id=row.get("source_face_id")
            words=row.get("original_text_observation_ids")
            if (any(not isinstance(x,str) or not x or x!=x.strip()
                    for x in (face,label,face_id))
                    or not isinstance(words,list) or not words
                    or any(type(x) is not str or not x or x!=x.strip()
                           for x in words)
                    or len(set(words))!=len(words)):
                raise ValueError("incomplete authenticated original label source receipt")
            sources.append((scope_id,face,label,face_id,tuple(words)))
    # Producer positive original labels must not be duplicated between
    # unrelated source rooms or use one word to assert two different rooms.
    counts=Counter(face for _,face,_,_,_ in sources)
    physical_faces=Counter(face_id for _,_,_,face_id,_ in sources)
    words=Counter(word for *_,ids in sources for word in ids)
    if (any(c!=1 for c in counts.values())
            or any(c!=1 for c in physical_faces.values())
            or any(c!=1 for c in words.values())):
        raise ValueError("original physical label face and word identity conflicted")

    canonical_by_original_face={}
    for room in canonical_rooms:
        face=getattr(room,"source_room_face_record_id",None)
        if not isinstance(face,str) or not face or face!=face.strip():
            raise ValueError("malformed canonical physical face receipt")
        canonical_by_original_face.setdefault(face,[]).append(room)

    rows=[]
    for scope,face,label,face_id,original_words in sorted(
        sources,key=lambda x:(x[2],x[1])
    ):
        matches=canonical_by_original_face.get(face,[])
        first="ORIGINAL_SOURCE_FACE_MISSING_IN_CANONICAL"
        canonical_room_id=None
        canonical_label_binding=None
        if len(matches)>1:
            first="ORIGINAL_SOURCE_FACE_DUPLICATED_IN_CANONICAL"
        elif len(matches)==1:
            room=matches[0]
            canonical_room_id=getattr(room,"canonical_room_id",None)
            canonical_label_binding=getattr(room,"room_label_binding_record_id",None)
            if (getattr(room,"source_sha256",None)!=expected_original_sha
                    or getattr(room,"page_id",None)!="7"
                    or not isinstance(canonical_room_id,str)
                    or not canonical_room_id):
                first="CANONICAL_FACE_SOURCE_PROVENANCE_MISMATCH"
            elif not isinstance(getattr(room,"room_label",None),str):
                first="CANONICAL_ROOM_LABEL_BINDING_UNAVAILABLE"
            elif room.room_label!=label:
                first="CANONICAL_ROOM_LABEL_LITERAL_CONFLICT"
            else:
                ids=getattr(room,"room_label_evidence_ids",None)
                if (not isinstance(ids,(tuple,list))
                        or any(type(word) is not str or not word or word!=word.strip()
                               for word in ids)
                        or len(set(ids))!=len(ids)
                        or not set(original_words).issubset(set(ids))
                        or not isinstance(canonical_label_binding,str)
                        or not canonical_label_binding):
                    first="ORIGINAL_TEXT_RECEIPTS_NOT_RETAINED_IN_CANONICAL"
                else:
                    first="ORIGINAL_SOURCE_LABEL_PROJECTION_PRESENT"
        rows.append({
            "original_producer_decision_scope_id":scope,
            "original_source_face_receipt_id":face,
            "original_source_face_id":face_id,
            "original_direct_label":label,
            "original_source_text_observation_ids":list(original_words),
            "canonical_matched_source_face_count":len(matches),
            "canonical_room_id":canonical_room_id,
            "canonical_label_binding_record_id":canonical_label_binding,
            "first_unproved_projection_gate":first,
            "source_room_geometry_inferred":False,
            "source_wall_ownership_inferred":False,
            "metric_area_or_finish_published":False,
        })
    return {
        "original_source_sha256":expected_original_sha,
        "authentic_positive_original_label_count":len(rows),
        "canonical_room_candidate_count":len(canonical_rooms),
        "first_projection_gates":rows,
        "no_nearest_label_fallback":True,
        "diagnostic_only":True,
        "benchmark_accuracy":None,
    }
