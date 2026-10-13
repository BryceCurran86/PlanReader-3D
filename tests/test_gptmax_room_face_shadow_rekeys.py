"""Adversarial original-source W4 room-face ID rekey proof, shadow-only included."""
from copy import deepcopy
import pytest

from tools.verify_gptmax_room_face_shadow_rekeys import verify_room_face_shadow_source_rekeys

SHA="1"*64


def fixture():
    def source(snapshot):
        a="owned-pub-"+snapshot
        b="owned-abst-"+snapshot
        c="owned-shadow-"+snapshot
        def room(fid,kind):
            face={
                "face_id":fid,"area_page_pts2":6.0 if kind=="published" else 0.3,
                "polygon_pdf_pts":[[0,0],[3,0],[3,2],[0,2]],
                "boundary_wall_edges":[["wall-original",[[0,0],[3,0]]]],
                "bounding_wall_ids":["wall-original"],
                "source_sha256":SHA,"snapshot_id":snapshot,
                "page_id":"3","decision_scope_id":"wall-source:3",
            }
            if kind=="published":
                face["record_id"]="record-"+snapshot
            else:
                face["reason"]="tiny_original"
            return face
        ev={
            "status":"evaluated",
            "reason_code":"ownership_evaluated",
            "scope_complete_at_evaluation":True,
            "owned_face_ids":[a,b,c],
            "degenerate_owned_face_ids":[b],
            "unresolved_faces":[],
            "largest_owned_face_area_pt2":6.0,
            "face_edge_count":12,
            "competing_edge_count":0,
            "unowned_edge_count":0,
        }
        scope={
            "selector":{
                "document_id":"d","revision_id":"rev",
                "source_sha256":SHA,"snapshot_id":snapshot,
                "page_id":"3","decision_scope_id":"wall-source:3",
            },
            "result":{
                "status":"corroborated","scope_complete":True,
                "source_sha256":SHA,"snapshot_id":snapshot,
                "page_id":"3","decision_scope_id":"wall-source:3",
                "reason_codes":["source_room_face_scope_resolved"],
                "records":[room(a,"published")],
                "abstained_faces":[room(b,"abstained")],
                "ownership_evaluation":ev,
            },
        }
        witness={
            "decision_scope_id":"wall-source:3","page_id":"3",
            "faces":[
                {"face_id":fid,"polygon_pdf_pts":[[0,0],[3,0],[3,2],[0,2]],
                 "decision_scope_id":"wall-source:3","page_id":"3",
                 "status":kind,"authority_granted":False}
                for fid,kind in ((a,"published"),(b,"abstained"),(c,"shadow_owned_unpublished"))
            ],
        }
        # The polygon in a source face is only illustrative. The *entire*
        # physical record must remain constant except snapshot-scoped IDs.
        return {
            "source_sha256":SHA,"snapshot_id":snapshot,
            "primitive_safety_cap":20_000,
            "source_owned_wall_scopes":[{
                "snapshot_id":snapshot,"decision_scope_id":"wall-source:3",
                "records":[{"wall_candidate_id":"wall-original",
                            "physical_identity":{"edge_ids":["split-original"],
                                "source_primitive_ids":["pdf-source-original"]}}],
            }],
            "source_room_face_scopes":[scope],
            "shadow_owned_face_source_polygons":[witness],
        }
    return source("old"),source("new")


def test_full_one_to_one_source_polygon_rekey_preserves_published_and_shadow_owned():
    a,b=fixture()
    original=deepcopy((a,b))
    proof=verify_room_face_shadow_source_rekeys(a,b)
    assert proof["all_shadow_source_faces_preserved"]
    assert proof["original_shadow_owned_faces"]==3
    assert proof["published_original_faces"]==1
    assert proof["abstained_original_faces"]==1
    assert proof["shadow_unpublished_original_faces"]==1
    assert proof["new_room_quantities_granted"]==0
    assert proof["benchmark_matches_claimed"]==0
    assert (a,b)==original


@pytest.mark.parametrize("change",[
    "source_sha", "cap", "same_snapshot", "wall_path", "room_area",
    "room_edge", "published_id", "shadow_polygon", "missing_shadow",
    "shadow_promoted", "fake_extra", "duplicate_face_id",
    "missing_owned", "degenerate_changed", "owner_lost", "unknown_shadow",
    "unproven_area", "reason_changed", "different_room_page",
])
def test_shadow_source_room_face_changed_without_original_proof_is_refused(change):
    a,b=fixture()
    s=b["source_room_face_scopes"][0]
    witness=b["shadow_owned_face_source_polygons"][0]
    if change=="source_sha": b["source_sha256"]="2"*64
    elif change=="cap": b["primitive_safety_cap"]=20001
    elif change=="same_snapshot": b["snapshot_id"]="old"
    elif change=="wall_path":
        b["source_owned_wall_scopes"][0]["records"][0]["physical_identity"]["edge_ids"]=["invented"]
    elif change=="room_area":s["result"]["records"][0]["area_page_pts2"]=999.0
    elif change=="room_edge":s["result"]["records"][0]["boundary_wall_edges"]=[["invented",[[0,0],[3,0]]]]
    elif change=="published_id":s["result"]["records"][0]["face_id"]="unexpected"
    elif change=="shadow_polygon":witness["faces"][2]["polygon_pdf_pts"]=[[0,0],[9,0],[9,2],[0,2]]
    elif change=="missing_shadow":witness["faces"].pop()
    elif change=="shadow_promoted":witness["faces"][2]["authority_granted"]=True
    elif change=="fake_extra":
        c=deepcopy(witness["faces"][2]);c["face_id"]="extra";c["polygon_pdf_pts"]=[[0,0],[99,0],[99,2],[0,2]]
        witness["faces"].append(c)
    elif change=="duplicate_face_id":witness["faces"][2]["face_id"]=witness["faces"][0]["face_id"]
    elif change=="missing_owned":s["result"]["ownership_evaluation"]["owned_face_ids"].pop()
    elif change=="degenerate_changed":s["result"]["ownership_evaluation"]["degenerate_owned_face_ids"]=[]
    elif change=="owner_lost":s["result"]["ownership_evaluation"]["status"]="unavailable"
    elif change=="unknown_shadow":del b["shadow_owned_face_source_polygons"]
    elif change=="unproven_area":s["result"]["ownership_evaluation"]["largest_owned_face_area_pt2"]=999
    elif change=="reason_changed":s["result"]["records"][0]["reason"]="invented"
    elif change=="different_room_page":witness["faces"][2]["page_id"]="4"
    with pytest.raises(ValueError,match="original room-face source rekey refused"):
        verify_room_face_shadow_source_rekeys(a,b)
