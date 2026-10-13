"""Read-only source-positive G17 → exact W4 primitive, no speculative host."""
from __future__ import annotations
from copy import deepcopy
from types import SimpleNamespace as Row
import pytest

from pb_migration_contracts import EvidenceResolutionStatus as Status
from tools.diag_gptmax_raster_unhosted_flank_source import (
    audit_g17_unhosted_flank_original_ancestry as audit,
)


SHA="1"*64
SNAP="snapshot_original"


def fixture():
    revision=Row(document_id="d",revision_id="rev",source_sha256=SHA)
    pub=Row(revision=revision,snapshot=Row(snapshot_id=SNAP),
            raster_opening_primitive_observation_ids=("G17-left","G17-right"))
    def observation(oid,primitive):
        return Row(observation_id=oid,observation_kind="raster_wall_band_face",
                   source_primitive_ref=primitive,geometry=(1.,2.,3.,4.),
                   derivation_parent_ids=("source-parent-1",),page_id="3",
                   source_sha256=SHA,snapshot_id=SNAP)
    originals={
        "G17-left":observation("G17-left","raster-left-original"),
        "G17-right":observation("G17-right","raster-right-missing-W4"),
    }
    def resolve(selector):
        return Row(status=Status.CORROBORATED,
                   observation=originals.get(selector.observation_id))
    parent=Row(observation_id="source-parent-1",
               observation_kind="raster_pdf_visible_line",
               source_primitive_ref="original-visible-parent",
               geometry=(1.,2.,3.,4.),page_id="3",
               source_sha256=SHA,snapshot_id=SNAP)
    def resolve_parent(selector):
        return Row(status=Status.CORROBORATED,
                   observation=parent if selector.observation_id=="source-parent-1" else None)
    visibility=Row(resolve_raster_opening_primitive=resolve,
                   _source_authority=Row(resolve=resolve_parent))
    source=Row(authority=lambda:visibility)
    root=Row(status=Status.CORROBORATED,
             existence_record=Row(
                 record_id="physical-opening-source-original",
                 source_observation_ids=("G17-right","G17-left"),
                 snapshot_id=SNAP,source_sha256=SHA,page_id="3"))
    opening=Row(prove_existence=lambda _:root)
    trace=Row(status=Status.ABSTAINED,
              opening_identity_id="physical-opening-source-original",
              representative_observation_id="G17-left",
              host_wall_id=None,record_id=None,
              reason_codes=("no_authenticated_host_wall_band",
                  "raster_source_band_right_source_primitive_unmapped"))
    wall=Row(wall_candidate_id="w4-original-a",
             physical_identity=Row(usable=True,
                 candidate_identity_id="physical-w4-original",
                 source_primitive_ids=("raster-left-original",)))
    wall2=Row(wall_candidate_id="w4-original-b",
             physical_identity=Row(usable=True,
                 candidate_identity_id="other-original-owner",
                 source_primitive_ids=("raster-left-original",)))
    scope=Row(status=Status.CORROBORATED,scope_complete=True,
              source_sha256=SHA,revision_id="rev",snapshot_id=SNAP,
              page_id="3",decision_scope_id="wall-source:page-3",
              records=(wall,wall2))
    comp=Row(physical_opening_authority=opening,
             physical_wall_candidate_authority=Row(_scopes={"page3":scope}),
             opening_bindings=(trace,))
    return source,pub,comp,originals,root,trace,scope


def test_exact_original_primitive_join_preserves_ambiguous_W4_owners_but_no_host():
    source,pub,comp,originals,root,trace,scope=fixture()
    before=deepcopy(originals)
    rows=audit(source,pub,comp)
    assert len(rows)==1
    row=rows[0]
    assert row["physical_opening_id"]=="physical-opening-source-original"
    assert row["host_status"]=="abstained"
    assert row["host_granted"] is False
    assert row["aperture_geometry_complete_granted"] is False
    assert row["opening_height_or_count_granted"] is False
    assert row["metric_quantity_granted"] is False
    originals_out=row["source_g17_observations"]
    assert [x["observation_id"] for x in originals_out]==["G17-left","G17-right"]
    assert len(originals_out[0]["exact_source_ref_w4_candidates"])==2
    assert originals_out[1]["exact_source_ref_w4_candidates"]==[]
    assert originals_out[0]["geometry_pdf_pts"]==[1.,2.,3.,4.]
    assert originals_out[0]["authenticated_source_parents"]==[{
        "observation_id":"source-parent-1",
        "observation_kind":"raster_pdf_visible_line",
        "source_primitive_ref":"original-visible-parent",
        "geometry_pdf_pts":[1.,2.,3.,4.],
        "exact_source_ref_w4_candidates":[],
    }]
    assert originals==before


def test_other_non_G17_abstention_is_not_reclassified():
    source,pub,comp,originals,root,trace,scope=fixture()
    trace.reason_codes=("opening_dimension_unavailable",)
    assert audit(source,pub,comp)==[]


@pytest.mark.parametrize("damage",[
    "wrong_opening", "lost_original_source", "source_rekey", "missing_G17",
    "unverified_G17", "wrong_original_page", "duplicate_G17",
    "forged_host", "bad_wall_id","missing_parent","foreign_W4_snapshot",
])
def test_source_G17_flank_witness_fails_closed_on_unauthenticated_input(damage):
    source,pub,comp,originals,root,trace,scope=fixture()
    if damage=="wrong_opening":root.existence_record.record_id="different-opening"
    elif damage=="lost_original_source":root.status=Status.ABSTAINED
    elif damage=="source_rekey":root.existence_record.source_sha256="2"*64
    elif damage=="missing_G17":
        pub.raster_opening_primitive_observation_ids=("G17-left",)
    elif damage=="unverified_G17":
        del originals["G17-right"]
    elif damage=="wrong_original_page":originals["G17-right"].page_id="8"
    elif damage=="duplicate_G17":
        root.existence_record.source_observation_ids=("G17-left","G17-left")
    elif damage=="forged_host":trace.host_wall_id="invented-wall"
    elif damage=="bad_wall_id":
        scope.records[0].wall_candidate_id=""
    elif damage=="missing_parent":
        originals["G17-left"].derivation_parent_ids=("nonexistent-original-parent",)
    elif damage=="foreign_W4_snapshot":
        scope.snapshot_id="foreign-source-snapshot"
    with pytest.raises(RuntimeError):
        audit(source,pub,comp)


def test_unrelated_original_page_owner_cannot_satisfy_exact_G17_primitive():
    source,pub,comp,originals,root,trace,scope=fixture()
    # Even with an identical primitive reference and physically close-looking
    # line on an unrelated page, it is never an original page-3 W4 owner.
    scope.page_id="4"
    rows=audit(source,pub,comp)
    assert len(rows)==1
    assert all(not receipt["exact_source_ref_w4_candidates"]
               for receipt in rows[0]["source_g17_observations"])


def test_original_exact_source_parent_ref_never_selects_other_page_wall():
    source,pub,comp,originals,root,trace,scope=fixture()
    scope.records[0].physical_identity.source_primitive_ids=(
        "original-visible-parent",)
    scope.page_id="4"
    rows=audit(source,pub,comp)
    parents=[p for o in rows[0]["source_g17_observations"]
             for p in o["authenticated_source_parents"]]
    assert parents and all(not p["exact_source_ref_w4_candidates"] for p in parents)
