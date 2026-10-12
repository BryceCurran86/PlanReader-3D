"""Q07 source native material word must keep original PDF lineage and word indices."""
from __future__ import annotations

from types import SimpleNamespace
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_material_semantic_authority import (
    SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE,
    _trusted_words_by_page,
)


def _read(receipt_changes=None):
    original = dict(
        geometry=(10.,20.,40.,34.), page_id="1",
        source_partition_id="native-p1", raw_text="FPB PLASTERBOARD",
        block_no=1,line_no=0,word_no=0,
        parent_observation_id="word-1", document_id="doc-1",
        revision_id="rev-1",source_sha256="a"*64,
    )
    original.update(receipt_changes or {})
    receipt = SimpleNamespace(**original)
    result = SimpleNamespace(
        receipt=receipt,status=EvidenceResolutionStatus.CORROBORATED,
        trusted_text="FPB PLASTERBOARD", reason_codes=(),
    )
    src = SimpleNamespace(
        text_integrity_authority=lambda: SimpleNamespace(
            resolve_text=lambda _selector: result,
        ),
    )
    published=SimpleNamespace(
        revision=SimpleNamespace(
            document_id="doc-1",revision_id="rev-1",source_sha256="a"*64,
        ),
        snapshot=SimpleNamespace(snapshot_id="snap-1"),
        text_observation_ids=("word-1",),
    )
    return _trusted_words_by_page(src,published)


def test_original_material_native_source_word_and_ordinal_are_preserved():
    word=_read()["1"][0]
    assert (word.block_no,word.line_no,word.word_no)==(1,0,0)
    assert word.text=="FPB PLASTERBOARD"
    assert word.source_partition_id=="native-p1"


@pytest.mark.parametrize("field,value",[
    ("parent_observation_id","word-2"),("parent_observation_id",True),
    ("document_id","foreign"),("revision_id","other"),
    ("source_sha256","f"*64),("page_id"," 1"),
    ("page_id",True),("source_partition_id",True),("raw_text",True),
    ("block_no",True),("block_no","1"),("block_no",1.8),
    ("line_no",-1),("line_no","0"),("word_no",0.5),
])
def test_native_material_word_cannot_rebind_original_source_or_word_ordinal(field,value):
    with pytest.raises(RuntimeError,match=SOURCE_MATERIAL_SOURCE_INTEGRITY_FAILURE):
        _read({field:value})


def test_optional_native_ordinals_preserve_source_missing_without_coercion():
    word=_read({"block_no":None,"line_no":None,"word_no":None})["1"][0]
    assert (word.block_no,word.line_no,word.word_no)==(0,0,0)
