"""Direct original figure ticks and witness linework are not face authority."""
import hashlib
from pathlib import Path
import fitz
import pytest
from tools.diag_source_figure_wall_witness_chain_shadow import (
    audit_figure_endpoint_witnesses as audit,
    _interval_merge,
)

ORIGINAL=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _positive_source_sheet(with_gap=False):
    doc=fitz.open()
    p=doc.new_page(width=300,height=300)
    p.draw_line((20,50),(20,150))
    p.draw_line((100,50),(130,50))
    p.draw_line((100,150),(130,150))
    if with_gap:
        p.draw_line((45,50),(100,50))
        p.draw_line((45,150),(100,150))
    else:
        p.draw_line((20,50),(100,50))
        p.draw_line((20,150),(100,150))
    return doc,p


def test_exact_joining_source_witness_line_can_reach_both_candidates():
    doc,p=_positive_source_sheet()
    result=audit(p,dimension_source_id="d0i0",candidate_wall_source_ids=("d1i0","d2i0"))
    assert result["status"]=="original_source_witness_candidates_only"
    for end in result["source_dimension_endpoints"]:
        positive=[r for r in end["original_projected_wall_candidates"]
                  if r["original_source_contiguous_ink_witness"]]
        assert len(positive)==1
        assert positive[0]["original_native_gap_pdf_pts"]==0
        assert not positive[0]["finished_interior_face_or_wall_role_authenticated"]
    assert not result["dimension_semantic_witness_proven"]
    assert result["new_quantities"]==0
    doc.close()


def test_misleading_collinear_tick_and_gap_must_not_be_bridged():
    doc,p=_positive_source_sheet(with_gap=True)
    result=audit(p,dimension_source_id="d0i0",candidate_wall_source_ids=("d1i0","d2i0"))
    for end in result["source_dimension_endpoints"]:
        matches=end["original_projected_wall_candidates"]
        assert len(matches)==1
        assert matches[0]["original_native_gap_pdf_pts"]==25
        assert not matches[0]["original_source_contiguous_ink_witness"]
    doc.close()


def test_disjoint_interval_and_reversed_strokes_are_order_invariant():
    assert _interval_merge(((30,20),(40,30),(45,47)))==[(20,40),(45,47)]
    assert _interval_merge(((45,47),(20,30),(30,40)))==[(20,40),(45,47)]


def test_bad_id_conflicting_candidates_or_cap_abstains():
    doc,p=_positive_source_sheet()
    with pytest.raises(ValueError,match="explicit_competing_native_face_ids"):
        audit(p,dimension_source_id="d0i0",candidate_wall_source_ids=("d1i0","d1i0"))
    with pytest.raises(ValueError,match="original_source_primitive_identity_required"):
        audit(p,dimension_source_id="../d0i0",candidate_wall_source_ids=("d1i0",))
    with pytest.raises(ValueError,match="original_source_primitive_unavailable"):
        audit(p,dimension_source_id="d987i0",candidate_wall_source_ids=("d1i0",))
    res=audit(p,dimension_source_id="d0i0",candidate_wall_source_ids=("d1i0",),max_original_lines=2)
    assert res["status"]=="original_line_universe_exceeds_shadow_cap"
    assert not res["source_universe_complete"]
    assert res["new_authoritative_dimensions"]==0
    doc.close()


def test_original_a502_pwd_3570_and_2200_have_unclosed_witness_extensions():
    raw=ORIGINAL.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as doc:
        page=doc[25]
        cases=(
            ("d12615i0",("d487i0","d511i0")),
            ("d12656i0",("d514i0","d498i0")),
        )
        for source_id,faces in cases:
            r=audit(page,dimension_source_id=source_id,candidate_wall_source_ids=faces)
            assert r["status"]=="original_source_witness_candidates_only"
            assert len(r["source_dimension_endpoints"])==2
            assert r["new_physical_faces"]==r["new_quantities"]==0
            assert not r["dimension_semantic_witness_proven"]
            for end in r["source_dimension_endpoints"]:
                assert len(end["original_projected_wall_candidates"])>=1
                assert all(
                    not w["original_source_contiguous_ink_witness"]
                    and w["original_native_gap_pdf_pts"]>0
                    and not w["finished_interior_face_or_wall_role_authenticated"]
                    for w in end["original_projected_wall_candidates"]
                )
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest()==SHA
