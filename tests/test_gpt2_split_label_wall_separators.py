"""Split-face labels stay CANDIDATE even across exact W4 source-owned walls."""
from types import SimpleNamespace as Obj
from tools.diag_gpt2_split_label_wall_separators import (
    split_face_source_wall_separator_gate as gate,
)

def candidate(ids=("face-left","face-right")):
    return Obj(
        label="EXAMPLE SPACE",record_id="source-split-candidate",
        source_room_face_record_ids=ids,
        document_id="doc",revision_id="rev",source_sha256="a"*64,
        snapshot_id="snap",page_id="7",decision_scope_id="view:7",
    )

def face(name,wall_id,edge):
    return Obj(
        record_id=name,document_id="doc",revision_id="rev",
        source_sha256="a"*64,snapshot_id="snap",page_id="7",
        decision_scope_id="view:7",
        boundary_wall_edges=((wall_id,edge),),
    )

def sample():
    return {
      "face-left":face("face-left","W4-wall-1",((5.,0.),(5.,10.))),
      "face-right":face("face-right","W4-wall-1",((5.,10.),(5.,0.))),
    }

def test_exact_reverse_edge_with_same_wall_is_separator_not_merge():
    row=gate(candidate(),sample())
    edge=row["pairwise_source_wall_gates"][0]
    assert edge["first_gate"]=="source_proven_wall_separator_do_not_merge"
    assert edge["matching_authenticated_wall_segments"][0]["source_wall_id_a"]=="W4-wall-1"
    assert row["merge_source_faces_authorized"] is False
    assert row["source_room_label_published"] is False

def test_matching_geometry_with_competing_wall_id_rejects():
    faces=sample()
    faces["face-right"]=face("face-right","W4-other",((5.,10.),(5.,0.)))
    row=gate(candidate(),faces)
    assert row["pairwise_source_wall_gates"][0]["first_gate"]=="competing_wall_owners_on_shared_source_edge"
    assert row["merge_source_faces_authorized"] is False

def test_disjoint_face_walls_do_not_imply_join():
    faces=sample()
    faces["face-right"]=face("face-right","W4-wall-1",((15.,10.),(15.,0.)))
    row=gate(candidate(),faces)
    assert row["pairwise_source_wall_gates"][0]["first_gate"]=="no_exact_shared_source_wall_separator"

def test_same_forward_orientation_is_not_proven_opposite_faces():
    faces=sample()
    faces["face-right"]=face("face-right","W4-wall-1",((5.,0.),(5.,10.)))
    assert gate(candidate(),faces)["pairwise_source_wall_gates"][0]["first_gate"]=="no_exact_shared_source_wall_separator"

def test_stale_or_missing_face_or_lineage_abstains():
    assert gate(candidate(),{})["first_gate"]=="split_source_face_record_missing"
    faces=sample()
    faces["face-right"].source_sha256="b"*64
    assert gate(candidate(),faces)["first_gate"]=="split_source_face_lineage_mismatch"

def test_missing_and_duplicate_candidate_face_id_abstains():
    assert gate(candidate(("face-left",)),sample())["first_gate"]=="split_source_face_identity_invalid"
    assert gate(candidate(("face-left","face-left")),sample())["first_gate"]=="split_source_face_identity_invalid"

def test_malformed_wall_subedge_fails_closed():
    faces=sample()
    faces["face-right"].boundary_wall_edges=(("W4-wall-1",((float("nan"),0),(5.,0))),)
    row=gate(candidate(),faces)
    assert row["pairwise_source_wall_gates"][0]["first_gate"]=="malformed_source_wall_subedges"

def test_multiple_faces_pairwise_no_automatic_transitive_join():
    faces=sample()
    faces["third"]=face("third","W4-wall-2",((40.,10.),(40.,0.)))
    row=gate(candidate(("face-left","face-right","third")),faces)
    assert len(row["pairwise_source_wall_gates"])==3
    assert row["merge_source_faces_authorized"] is False
    assert row["metric_quantity_published"] is False
