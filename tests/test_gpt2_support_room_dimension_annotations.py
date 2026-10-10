"""Native CAD block adjacency is a negative filter, not measurement proof."""
import pytest
from tools.diag_gpt2_support_room_dimension_annotations import (
    _native_annotation_relation as relation,
    audit,
)

LABEL={"block_no":7,"line_no":0,"bbox":(10.,10.,60.,30.)}

def dim(*,block=7,line=1,word=0,orientation="horizontal",box=(30.,35.,48.,48.)):
    return {"block_no":block,"line_no":line,"word_no":word,
            "orientation":orientation,"bbox":box}

def test_consecutive_native_block_lines_candidate_only():
    assert relation(LABEL,dim())=="consecutive_same_native_block"
    assert relation(LABEL,dim(line=2)) is None

def test_adjacent_source_blocks_need_zero_line_and_exact_axis_overlap():
    assert relation(LABEL,dim(block=8,line=0))=="adjacent_native_blocks_with_axis_overlap"
    assert relation(LABEL,dim(block=8,line=0,box=(110.,35.,140.,48.))) is None
    assert relation(LABEL,dim(block=8,line=0,orientation="vertical",box=(25.,15.,35.,25.)))=="adjacent_native_blocks_with_axis_overlap"
    assert relation(LABEL,dim(block=8,line=0,orientation="vertical")) is None

def test_unrelated_block_or_word_is_not_owned():
    assert relation(LABEL,dim(block=10,line=0)) is None
    assert relation(LABEL,dim(word=1)) is None
    assert relation(LABEL,dim(block=8,line=0,orientation="unknown")) is None

def test_wrong_source_sha_fails_before_rendering():
    with pytest.raises(ValueError,match="source_sha_mismatch"):
        audit(b"unrelated PDF bytes")
