"""Independent A120 legend row source provenance; no false ceiling authority."""
import hashlib
from pathlib import Path

import fitz
import pytest

from pb_source_material_semantic_authority import (
    _TrustedTextWord,
    _native_multirow_material_definition_candidates as source_rows,
    SourceMaterialSemanticProducer,
)
from pb_source_visibility_authority import SourceVisibilityProducer

PDF=Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SHA="b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def _word(*, block, line, index, literal, partition="original_source_p9"):
    return _TrustedTextWord(
        observation_id=f"native:{partition}:{block}:{line}:{index}",
        page_id="9",source_partition_id=partition,
        text=literal,bbox=(10.,20.,30.,40.),
        block_no=block,line_no=line,word_no=index,
        trusted=False,reason_codes=("original_text_unverified",),
    )


def _original_p9_legend_words(page):
    # PyMuPDF 1.26 and 1.28 assign different block ordinals to the same
    # PDF content. Locate the original *complete source block*, not a
    # version-specific extracted block number; preserve actual native IDs.
    words=page.get_text("words")
    by_block={}
    for w in words:
        by_block.setdefault(int(w[5]),[]).append(w)
    selected=set()
    for block,rows in by_block.items():
        tokens={str(w[4]) for w in rows}
        if ({"GRID","VINYL","PLASTER","600x1200"} <= tokens
                or "IPF1" in tokens or "CLD3" in tokens):
            selected.add(block)
    return tuple(
        _TrustedTextWord(
            observation_id=f"original_p9:{w[5]}:{w[6]}:{w[7]}",
            page_id="9",
            source_partition_id="original_p9_native_partition",
            text=str(w[4]),bbox=tuple(float(x) for x in w[:4]),
            block_no=int(w[5]),line_no=int(w[6]),word_no=int(w[7]),
            trusted=False,reason_codes=("native_pdf_text_unverified",),
        )
        for w in words if int(w[5]) in selected
    )


def test_original_a120_grid_true_ceiling_definition_has_separate_source_lines():
    raw=PDF.read_bytes()
    assert hashlib.sha256(raw).hexdigest()==SHA
    with fitz.open(stream=raw,filetype="pdf") as d:
        candidates=source_rows(_original_p9_legend_words(d[8]))
        rows={code:(owned,item) for _,_,owned,code,item in candidates}
        assert "GRID" in rows
        owned,item=rows["GRID"]
        assert len({r.block_no for r in owned})==1
        assert len({r.line_no for r in owned})==2
        assert owned[1].line_no==owned[0].line_no+1
        assert owned[0].text=="GRID"
        assert "VINYL FACED PLASTER TILE 600x1200" in item["description"]
        assert item["code"]=="GRID"
        assert item["source_semantic_role_unverified"]
        assert not item["source_material_issuer_granted"]
        assert {r.observation_id for r in owned}=={
            f"original_p9:{r.block_no}:{r.line_no}:{r.word_no}" for r in owned
        }
        assert all(not r.trusted for r in owned)
        assert "CLD3" not in rows  # Separate signage cladding schedule block.
    assert hashlib.sha256(PDF.read_bytes()).hexdigest()==SHA


def test_original_legend_multiple_code_lines_are_distinct_untrusted_source_rows():
    with fitz.open(stream=PDF.read_bytes(),filetype="pdf") as d:
        rows=source_rows(_original_p9_legend_words(d[8]))
        codes=[code for _,_,_,code,_ in rows]
        assert len(codes)==len(set(codes))
        assert "GRID" in codes
        assert "FPB" in codes
        assert "WFPB" in codes
        for _,_,words,code,_ in rows:
            assert len({w.source_partition_id for w in words})==1
            assert len({w.block_no for w in words})==1
            assert words[0].text==code
            assert not any(w.trusted for w in words)
        assert all("original_p9:" in w.observation_id
                   for _,_,words,_,_ in rows for w in words)


def test_synthetic_two_code_lines_positive_and_cladding_not_ceiling():
    words=tuple(
        _word(block=3,line=i,index=j,literal=t)
        for i,line in enumerate([
            ["GRID"],["VINYL","FACED","PLASTER","TILE","600x1200"],
            ["IPF1"],["13mm","FLUSH-SET","PLASTERBOARD","CEILING","LININGS"],
            ["CLD3"],["BY","OTHERS","SIGNAGE","CLADDING"],
        ])
        for j,t in enumerate(line)
    )
    candidates=source_rows(words)
    d={code:item for _,_,_,code,item in candidates}
    assert "GRID" in d and "IPF1" in d
    assert "CLD3" not in d
    assert "600x1200" in d["GRID"]["description"]
    assert d["GRID"]["source_semantic_role_unverified"]
    assert d["GRID"]["source_material_issuer_granted"] is False


def test_duplicate_codes_and_broken_source_lineage_abstain():
    duplicated=tuple(
        _word(block=1,line=i,index=j,literal=t)
        for i,line in enumerate([
            ["GRID"],["VINYL","FACED","TILE"],["GRID"],
            ["VINYL","FACED","TILE"],["IPF1"],["PLASTERBOARD","CEILING"],
        ]) for j,t in enumerate(line)
    )
    result=source_rows(duplicated)
    assert all(code!="GRID" for _,_,_,code,_ in result)

    broken=(
        _word(block=2,line=0,index=0,literal="GRID"),
        _word(block=2,line=2,index=0,literal="VINYL"),
        _word(block=2,line=3,index=0,literal="IPF1"),
        _word(block=2,line=4,index=0,literal="PLASTERBOARD"),
    )
    assert all(code!="GRID" for _,_,_,code,_ in source_rows(broken))

    duplicate_word_index=(
        _word(block=5,line=0,index=0,literal="GRID"),
        _word(block=5,line=1,index=0,literal="VINYL"),
        _word(block=5,line=1,index=0,literal="FACED"),
        _word(block=5,line=2,index=0,literal="IPF1"),
        _word(block=5,line=3,index=0,literal="PLASTERBOARD"),
    )
    assert source_rows(duplicate_word_index)==()


def test_new_material_producer_shadow_is_explicit_and_default_off():
    src=SourceVisibilityProducer(producer_method="source-test",producer_version="1")
    normal=SourceMaterialSemanticProducer.from_source_visibility_producer(src)
    shadow=SourceMaterialSemanticProducer.for_native_multirow_material_shadow(src)
    assert normal._source_native_multirow_material_shadow is False
    assert shadow._source_native_multirow_material_shadow is True
    assert normal.published_occurrence_results()==shadow.published_occurrence_results()==()
    with pytest.raises(TypeError):
        SourceMaterialSemanticProducer(src)



def test_pathological_large_original_text_block_abstains_without_raster_cap_change():
    many=tuple(
        _word(block=48,line=i,index=0,literal=("GRID" if i==0
            else "IPF1" if i==2 else "PLASTERBOARD"))
        for i in range(257)
    )
    assert source_rows(many)==()
    huge=tuple(
        _word(block=49,line=i//30,index=i%30,
              literal="GRID" if i==0 else "IPF1" if i==30
              else "VINYL")
        for i in range(4097)
    )
    assert source_rows(huge)==()



def test_original_cld3_signage_is_separate_source_and_never_ceiling_grid():
    raw=PDF.read_bytes()
    with fitz.open(stream=raw,filetype="pdf") as d:
        rows=source_rows(_original_p9_legend_words(d[8]))
        material={code:item for _,_,_,code,item in rows}
        assert "CLD3" not in material
        grid=material["GRID"]
        assert "VINYL FACED PLASTER TILE" in grid["description"]
        assert grid["source_semantic_role_unverified"]
        assert not grid["source_material_issuer_granted"]


def test_unverified_raw_source_code_with_no_material_semantics_abstains():
    words=tuple(
        _word(block=35,line=i,index=j,literal=t)
        for i,line in enumerate([
            ["GRID"],["NONSENSE","TYPICAL","PLAN","NOTE"],
            ["IPF1"],["13mm","PLASTERBOARD","CEILING"],
        ]) for j,t in enumerate(line)
    )
    codes={code for _,_,_,code,_ in source_rows(words)}
    assert "GRID" not in codes
    assert "IPF1" in codes


def test_same_original_source_block_does_not_grant_grid_ceiling_metric():
    with fitz.open(stream=PDF.read_bytes(),filetype="pdf") as d:
        owned=[r for r in source_rows(_original_p9_legend_words(d[8]))
               if r[3]=="GRID"]
        assert len(owned)==1
        _partition,_block,words,code,item=owned[0]
        assert len({word.block_no for word in words})==1
        assert not all(word.trusted for word in words)
        assert item["source_semantic_role_unverified"]
        assert item["source_material_issuer_granted"] is False
