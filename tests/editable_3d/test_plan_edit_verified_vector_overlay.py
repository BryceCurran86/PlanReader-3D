"""Source-verified page-specific vector overlays, reversible and fail closed."""
from __future__ import annotations

from dataclasses import replace
from hashlib import sha256

import fitz
import pytest

from pb_plan_edit_revision_bundle import RelatedPageCoverage, render_related_page_revision
from pb_plan_edit_verified_vector_overlay import (
    VerifiedPageLineOverlay, original_pdf_line_count,
    validate_verified_overlays,
)
from test_plan_edit_revision_store import _fixture, _conn
from pb_plan_edit_revision_store import save_plan_edit_revision, get_plan_edit_pdf


def _source_pdf():
    doc = fitz.open()
    for i in range(3):
        page = doc.new_page(width=600,height=500)
        page.insert_text((30,60),f"Original geometry page {i + 1}")
        if i < 2:
            page.draw_line((40,100+i*20),(240,100+i*20),
                           color=(0,0,0),width=0.8)
    result=doc.tobytes()
    doc.close()
    return result


def _fixture_with_verified_vector_overlays():
    _,user,workspace,ledger,coverage,command=_fixture()
    source = _source_pdf()
    source_sha = sha256(source).hexdigest()
    new_scope=replace(workspace.scope,source_sha256=source_sha)
    ws=replace(
        workspace,scope=new_scope,
        source_witnesses={
            "wall-1":replace(workspace.source_witnesses["wall-1"],
                             source_sha256=source_sha),
        },
    )
    links=tuple(replace(x,source_sha256=source_sha) for x in coverage.links)
    marks=(
        VerifiedPageLineOverlay(
            page_index=0,page_label="1",native_geometry_ref="path-18",
            canonical_object_id="canonical-wall-1",
            original_pdf_segment=((40.,100.),(240.,100.)),
            proposed_pdf_segment=((40.,100.),(280.,100.)),
            original_source_receipt_id="pdf-native-stroke-A101",
            transform_receipt_id="calibration-A101",
            model_correction_receipt_id="command-1",
            producer_accepted=True,projection_kind="source_verified_plan",
        ),
        VerifiedPageLineOverlay(
            page_index=1,page_label="2",
            native_geometry_ref="elevation-wall-18",
            canonical_object_id="canonical-wall-1",
            original_pdf_segment=((40.,120.),(240.,120.)),
            proposed_pdf_segment=((40.,120.),(240.,90.)),
            original_source_receipt_id="pdf-native-stroke-A201",
            transform_receipt_id="elevation-transform-A201",
            model_correction_receipt_id="command-1",
            producer_accepted=True,projection_kind="source_verified_elevation",
        ),
    )
    return (source,user,ws,ledger,
            replace(coverage,source_sha256=source_sha,links=links,
                    vector_overlays=marks,vector_projection_complete=True),
            {**command,"sourceSha256":source_sha})


def _generate(f):
    original,user,ws,ledger,coverage,cmd=f
    return render_related_page_revision(
        original,scope=ws.scope,edited=ws.objects[0],
        witness=ws.source_witnesses["wall-1"],
        canonical_object_id="canonical-wall-1",
        coverage=coverage,revision_label="PR-R0001",
        correction_field="height",prior_value=2.4,new_value=3.0,
        correction_id=cmd["commandId"],
    )


def test_both_registered_pages_gain_distinct_source_projected_real_pdf_vectors():
    f=_fixture_with_verified_vector_overlays()
    product=_generate(f)
    assert len(product.related_pages)==2
    assert all(item["vectorGeometryOverlayDrawn"] for item in product.related_pages)
    assert [p["vectorOverlayKind"] for p in product.related_pages]==[
        "source_verified_plan","source_verified_elevation",
    ]
    assert not any(p["geometryRedrawn"] for p in product.related_pages)
    with fitz.open(stream=product.bytes,filetype="pdf") as doc:
        assert doc.page_count==3
        assert original_pdf_line_count(doc[0],((40.,100.),(280.,100.)))==1
        assert original_pdf_line_count(doc[1],((40.,120.),(240.,90.)))==1
        assert original_pdf_line_count(doc[0],((40.,100.),(240.,100.)))==1
        assert original_pdf_line_count(doc[1],((40.,120.),(240.,120.)))==1
        assert not tuple(doc[2].annots() or ())
        assert len(doc[2].get_drawings())==0
    assert sha256(f[0]).hexdigest()==product.original_sha256


def test_missing_page_transform_or_nonunique_original_stroke_abstains():
    f=_fixture_with_verified_vector_overlays()
    original,user,ws,ledger,coverage,cmd=f
    for bad in (
        replace(coverage,vector_overlays=coverage.vector_overlays[:1]),
        replace(coverage,vector_projection_complete=False),
        replace(coverage,vector_overlays=tuple(
            replace(p,model_correction_receipt_id="some-other-command")
            for p in coverage.vector_overlays)),
        replace(coverage,vector_overlays=tuple(
            replace(p,original_pdf_segment=((42.,100.),(240.,100.)))
            if p.page_index==0 else p for p in coverage.vector_overlays)),
    ):
        with pytest.raises(ValueError):
            _generate((original,user,ws,ledger,bad,cmd))
    with fitz.open(stream=original,filetype="pdf") as d:
        d[0].draw_line((40,100),(240,100))
        double=d.tobytes()
    # Exact SHA must first be independently re-established when source changes.
    with pytest.raises(ValueError,match="sha"):
        render_related_page_revision(
            double,scope=ws.scope,edited=ws.objects[0],
            witness=ws.source_witnesses["wall-1"],
            canonical_object_id="canonical-wall-1",coverage=coverage,
            revision_label="PR-R0001",correction_field="height",
            prior_value=2.4,new_value=3.0,correction_id=cmd["commandId"],
        )


def test_nonfinite_out_of_bounds_forged_or_noop_patches_rejected():
    patch=_fixture_with_verified_vector_overlays()[4].vector_overlays[0]
    for changed in (
        {"proposed_pdf_segment":((40.,100.),(240.,100.))},
        {"proposed_pdf_segment":((float("nan"),100.),(240.,100.))},
        {"original_source_receipt_id":patch.transform_receipt_id},
        {"producer_accepted":False},
        {"projection_kind":"freehand"},
    ):
        with pytest.raises(ValueError):
            replace(patch,**changed)


def test_atomic_saved_revision_records_source_verified_vector_coverage():
    f=_fixture_with_verified_vector_overlays()
    original,user,ws,ledger,coverage,cmd=f
    db=_conn()
    saved=save_plan_edit_revision(
        db,principal=user,workspace=ws,workspace_db_id=1,ledger=ledger,
        command=cmd,original_pdf_bytes=original,page_coverage=coverage,
    )
    assert saved["sourceVerifiedVectorOverlayComplete"] is True
    assert all(p["vectorGeometryOverlayDrawn"] for p in saved["pagesRevised"])
    revision,hash_=get_plan_edit_pdf(db,user,ws,saved["revisionId"])
    assert sha256(revision).hexdigest()==hash_
    assert db.execute("SELECT count(*) FROM editable_3d_correction_events").fetchone()[0]==1


def test_nonvector_revision_still_uses_safe_coordination_annotations():
    original,user,ws,ledger,coverage,cmd=_fixture_with_verified_vector_overlays()
    without=replace(coverage,vector_overlays=(),vector_projection_complete=False)
    result=_generate((original,user,ws,ledger,without,cmd))
    assert all(p["vectorGeometryOverlayDrawn"] is False for p in result.related_pages)
    assert all(p["geometryRedrawn"] is False for p in result.related_pages)


def test_native_source_line_counts_distinct_paths_not_pymupdf_forward_back_edges():
    source=_source_pdf()
    with fitz.open(stream=source,filetype="pdf") as doc:
        page=doc[0]
        assert original_pdf_line_count(
            page,((40.,100.),(240.,100.))) == 1
        page.draw_line((40,100),(240,100),color=(0,0,0),width=0.8)
        assert original_pdf_line_count(
            page,((40.,100.),(240.,100.))) == 2
