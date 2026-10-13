"""Independently prove snapshot-only physical source room-face rekeys.

This is READ-ONLY original source diagnostic, not a canonical space, measured
floor, new source wall, new host, customer output or benchmark acceptance.
Snapshot-scoped face IDs are only mapped by unique polygon geometry and
original W4 source ancestry (never by label, quantity, count or list index).
"""
from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import asdict
import json
from pathlib import Path
from typing import Any


def _require(ok: bool, description: str) -> None:
    if not ok:
        raise ValueError("original room-face source rekey refused: " + description)


def owned_shadow_face_polygon_witness(scope: object, result: object) -> list[dict[str, Any]]:
    """Reconstruct every source-owned shadow polygon, INCLUDING unpublished ones.

    Use precisely the live W4 wall edges and original planar-face extraction
    already consumed by SourceRoomFaceOwnershipEvaluation. Recompute the
    source-scoped address only to link the original owning polygon, never to
    publish it as a measurable/canonical room.
    """
    from pb_source_room_face_authority import (
        _canonical_polygon, _wall_edges, extract_planar_faces, stable_contract_id,
        OWNERSHIP_EVALUATION_EVALUATED,
    )
    _require(result.ownership_evaluation.status == OWNERSHIP_EVALUATION_EVALUATED,
             "original shadow ownership was not evaluated")
    wall_edges: dict[str, Any] = {}
    duplicate: set[Any] = set()
    owners: dict[Any, str] = {}
    for record in tuple(getattr(scope, "records", ()) or ()):
        wall_id = str(getattr(record, "wall_candidate_id", "") or "")
        edges = _wall_edges(record)
        if not wall_id or not edges:
            continue
        _require(wall_id not in wall_edges, "duplicate original wall candidate")
        wall_edges[wall_id] = edges
        for edge in edges:
            if edge in owners and owners[edge] != wall_id:
                duplicate.add(edge)
            else:
                owners[edge] = wall_id
    _require(bool(wall_edges), "no original W4 geometry")
    segments = [(edge[0], edge[1])
                for wall_id in sorted(wall_edges)
                for edge in wall_edges[wall_id]]
    if duplicate:
        segments = list(dict.fromkeys(segments))
    faces = extract_planar_faces(segments, min_area=1e-6)
    published = {face.face_id for face in result.records}
    abstained = {face.face_id for face in result.abstained_faces}
    _require(not (published & abstained), "one face published and abstained")
    raw_map: dict[str, tuple[Any, ...]] = {}
    for face in faces:
        polygon = _canonical_polygon(face)
        if not polygon:
            continue
        face_id = stable_contract_id("source_room_face", {
            "document_id": scope.document_id,
            "revision_id": scope.revision_id,
            "source_sha256": scope.source_sha256,
            "snapshot_id": scope.snapshot_id,
            "page_id": scope.page_id,
            "decision_scope_id": scope.decision_scope_id,
            "polygon": polygon,
        }, digest_chars=32)
        if face_id in raw_map:
            _require(raw_map[face_id] == polygon,
                     "hash address collision for distinct source polygons")
        else:
            raw_map[face_id] = polygon
    owned = tuple(result.ownership_evaluation.owned_face_ids)
    _require(len(owned) == len(set(owned)), "duplicated owned shadow face ID")
    _require(set(owned) <= set(raw_map), "shadow-owned face lacks original polygon")
    _require(published <= set(owned), "published face lacks owned geometry")
    _require(abstained <= set(owned), "abstained face lacks owned geometry")
    _require(published | abstained <= set(raw_map),
             "retained room face lacks original geometry")
    return [
        {
            "face_id": face_id,
            "polygon_pdf_pts": [list(pt) for pt in raw_map[face_id]],
            "page_id": str(scope.page_id),
            "decision_scope_id": str(scope.decision_scope_id),
            "status": ("published" if face_id in published else
                       "abstained" if face_id in abstained else
                       "shadow_owned_unpublished"),
            "authority_granted": False,
        }
        for face_id in sorted(owned)
    ]


def _key(item: Mapping[str, Any], fields: Sequence[str]) -> str:
    return json.dumps({field:item.get(field) for field in fields},
                      sort_keys=True, separators=(",", ":"))


def _physical_record_signature(face: Mapping[str, Any]) -> str:
    exclude = {"face_id", "record_id", "snapshot_id"}
    return json.dumps({k:v for k,v in face.items() if k not in exclude},
                      sort_keys=True, separators=(",", ":"))


def _as_groups(stage: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    items = stage.get("shadow_owned_face_source_polygons")
    _require(isinstance(items,list), "missing producer-owned shadow polygon witness")
    scopes={}
    for item in items:
        _require(isinstance(item,Mapping) and set(item)=={"decision_scope_id","page_id","faces"},
                 "unknown shadow room scope schema")
        key=str(item["page_id"])+":"+str(item["decision_scope_id"])
        _require(key not in scopes, "duplicate room-face shadow scope")
        scopes[key]=item
    return scopes


def verify_room_face_shadow_source_rekeys(
    before: Mapping[str, Any], after: Mapping[str, Any],
) -> dict[str, Any]:
    """Prove full W4 and unique physical room polygons, 5+ shadow-only included."""
    sha=before.get("source_sha256")
    _require(isinstance(sha,str) and len(sha)==64 and after.get("source_sha256")==sha,
             "original source SHA changed")
    _require(before.get("snapshot_id") != after.get("snapshot_id"),
             "no distinct source snapshot event")
    _require(before.get("primitive_safety_cap")==after.get("primitive_safety_cap")==20_000,
             "raster cap changed")
    old_walls=before.get("source_owned_wall_scopes")
    new_walls=after.get("source_owned_wall_scopes")
    _require(isinstance(old_walls,list) and isinstance(new_walls,list)
             and len(old_walls)==len(new_walls) and bool(old_walls),
             "W4 original wall scope missing")
    for old,new in zip(old_walls,new_walls):
        _require(old.get("records")==new.get("records"),
                 "original W4 physical source ancestry or geometry changed")
        stable=lambda obj:{k:v for k,v in obj.items() if k!="snapshot_id"}
        _require(stable(old)==stable(new),"original W4 physical scope metadata changed")

    old_groups=_as_groups(before)
    new_groups=_as_groups(after)
    old_scope_rows=before.get("source_room_face_scopes")
    new_scope_rows=after.get("source_room_face_scopes")
    _require(isinstance(old_scope_rows,list) and isinstance(new_scope_rows,list)
             and len(old_scope_rows)==len(new_scope_rows)==len(old_groups)==len(new_groups),
             "source room scope universe changed")
    def scopes(rows):
        indexed={}
        for row in rows:
            _require(isinstance(row,Mapping) and set(row)=={"selector","result"},
                     "unexpected room face scope fields")
            x=row["selector"]
            key=str(x["page_id"])+":"+str(x["decision_scope_id"])
            _require(key not in indexed,"duplicated room face source scope")
            indexed[key]=row
        return indexed
    old_scopes=scopes(old_scope_rows)
    new_scopes=scopes(new_scope_rows)
    _require(set(old_scopes)==set(new_scopes)==set(old_groups)==set(new_groups),
             "different source room page/scope ownership")
    total=0;pub=0;abstained=0;shadow_only=0
    for scope_id in sorted(old_scopes):
        os,ns=old_scopes[scope_id],new_scopes[scope_id]
        _require({k:v for k,v in os["selector"].items() if k!="snapshot_id"} ==
                 {k:v for k,v in ns["selector"].items() if k!="snapshot_id"},
                 "source room face selector changed")
        old_result,new_result=os["result"],ns["result"]
        _require(set(old_result)==set(new_result),"room face scope schema changed")
        for k in old_result:
            if k not in {"records","abstained_faces","ownership_evaluation","snapshot_id"}:
                _require(old_result[k]==new_result[k],
                         "source room face scope physical status changed: "+k)
        # Every published/abstained physical original record must match as a
        # unique entire source proposition, not merely as one matching area.
        for key in ("records","abstained_faces"):
            aa=old_result[key];bb=new_result[key]
            old_sigs=Counter(_physical_record_signature(r) for r in aa)
            new_sigs=Counter(_physical_record_signature(r) for r in bb)
            _require(old_sigs==new_sigs and all(c==1 for c in old_sigs.values()),
                     "published/abstained room polygon or original W4 boundary changed")
        old_faces=old_groups[scope_id]["faces"];new_faces=new_groups[scope_id]["faces"]
        _require(isinstance(old_faces,list) and isinstance(new_faces,list),
                 "shadow original polygon group is missing")
        def by_signature(faces):
            keys=set()
            found={}
            for face in faces:
                _require(set(face)=={"face_id","polygon_pdf_pts","page_id",
                         "decision_scope_id","status","authority_granted"},
                         "unknown shadow room polygon fields")
                _require(face["authority_granted"] is False,
                         "shadow face promoted to physical/canonical authority")
                _require(face["page_id"]+":"+face["decision_scope_id"]==scope_id,
                         "shadow polygon source page ownership changed")
                fid=face["face_id"]
                _require(isinstance(fid,str) and fid not in keys,
                         "invalid or duplicated shadow polygon ID")
                keys.add(fid)
                sig=_key(face,("polygon_pdf_pts","page_id","decision_scope_id","status"))
                _require(sig not in found,"ambiguous duplicate original shadow polygon")
                found[sig]=fid
            return found,keys
        old_index,oldids=by_signature(old_faces)
        new_index,newids=by_signature(new_faces)
        # Prove that the actual published and explicitly ABSTAINED face rows
        # carry the precise original source polygon addresses in this witness.
        # An attacker cannot silently rekey a face row by altering face_id
        # while leaving its snapshot-independent geometry unchanged.
        for witness_rows, scoped_result in (
            (old_faces, old_result), (new_faces, new_result),
        ):
            witness_by_id={r["face_id"]:r for r in witness_rows}
            recorded_ids=set()
            for live_key, expected_status in (
                ("records", "published"),
                ("abstained_faces", "abstained"),
            ):
                for physical in scoped_result[live_key]:
                    face_id=physical.get("face_id")
                    source_witness=witness_by_id.get(face_id)
                    _require(source_witness is not None
                             and source_witness["status"]==expected_status,
                             "published/abstained source face address unproven")
                    _require(physical.get("polygon_pdf_pts") ==
                             source_witness["polygon_pdf_pts"],
                             "published/abstained room polygon disagrees with source")
                    recorded_ids.add(face_id)
            _require(len(recorded_ids) == sum(
                r["status"] in {"published","abstained"}
                for r in witness_rows
            ), "original published/abstained face role changed")
        _require(set(old_index)==set(new_index),
                 "shadow-owned original polygon/source ancestry changed")
        mapping={old_index[k]:new_index[k] for k in old_index}
        _require(len(mapping)==len(oldids)==len(newids),
                 "shadow room polygon identity mapping not bijective")
        old_eval,new_eval=old_result["ownership_evaluation"],new_result["ownership_evaluation"]
        _require(set(old_eval)==set(new_eval),
                 "shadow source owner evaluation fields changed")
        for k in old_eval:
            if k in ("owned_face_ids","degenerate_owned_face_ids"):
                o=old_eval[k];n=new_eval[k]
                _require(set(o) <= oldids and set(n) <= newids
                         and {mapping[v] for v in o}==set(n) and len(o)==len(n),
                         "unverified source-owning face IDs changed: "+k)
            else:
                _require(old_eval[k]==new_eval[k],
                         "original W4 edge/source ownership evaluation changed: "+k)
        _require(set(old_eval["owned_face_ids"])==oldids
                 and set(new_eval["owned_face_ids"])==newids,
                 "producer witness omitted source-owned faces")
        total+=len(old_faces)
        pub+=sum(face["status"]=="published" for face in old_faces)
        abstained+=sum(face["status"]=="abstained" for face in old_faces)
        shadow_only+=sum(face["status"]=="shadow_owned_unpublished" for face in old_faces)
    return {"source_sha256":sha,"all_shadow_source_faces_preserved":True,
            "original_shadow_owned_faces":total,
            "published_original_faces":pub,"abstained_original_faces":abstained,
            "shadow_unpublished_original_faces":shadow_only,
            "new_room_quantities_granted":0,"benchmark_matches_claimed":0}


def main() -> None:
    import argparse
    parser=argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--baseline",type=Path,required=True)
    parser.add_argument("--candidate",type=Path,required=True)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    before=json.loads(args.baseline.read_text())
    after=json.loads(args.candidate.read_text())
    report=verify_room_face_shadow_source_rekeys(before,after)
    if args.output:
        args.output.write_text(json.dumps(report,sort_keys=True,indent=2)+"\n")
    print(json.dumps(report,sort_keys=True))


if __name__=="__main__":
    main()
