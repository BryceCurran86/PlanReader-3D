"""Regression for native material schedule title/row ownership."""
from types import SimpleNamespace
import pb_source_material_semantic_authority as semantic

def _word(partition, block, line, text, x0, x1, y):
    return semantic._TrustedTextWord(
        observation_id=f"{partition}:{block}:{line}", page_id="9",
        source_partition_id=partition, text=text,
        bbox=(x0, y, x1, y + 10), block_no=block,
        line_no=line, word_no=0, trusted=True, reason_codes=(),
    )

def _source_words():
    return (
        _word("same", 1, 0, "CEILING FINISHES SCHEDULE", 20, 185, 20),
        _word("same", 2, 0, "FPB", 25, 145, 65),
        _word("same", 2, 1, "FLUSHSET PLASTERBOARD", 25, 145, 77),
        _word("same", 3, 0, "WFPB", 25, 170, 115),
        _word("same", 3, 1, "WET AREA FLUSHSET PLASTERBOARD", 25, 170, 127),
        _word("same", 4, 0, "GRID", 350, 510, 175),
        _word("same", 4, 1, "SUSPENDED CEILING GRID SYSTEM", 350, 510, 187),
        _word("foreign", 5, 0, "GRID", 30, 180, 175),
        _word("foreign", 5, 1, "SUSPENDED CEILING GRID SYSTEM", 30, 180, 187),
    )

def _run(monkeypatch, words):
    monkeypatch.setattr(
        semantic, "_recover_native_material_block",
        lambda **kwargs: tuple(kwargs["block_words"]),
    )
    blocks, _ = semantic._trusted_native_material_schedule_cluster_blocks(
        source=SimpleNamespace(), published=SimpleNamespace(),
        raster=SimpleNamespace(), words=words,
    )
    return {
        str(item["code"]).upper()
        for block in blocks
        for item in semantic.parse_schedule_text(
            block.text, page_id=9, page_label="page:9"
        )
    }

def test_aligned_rows_authenticate_without_foreign_or_displaced_rows(monkeypatch):
    assert _run(monkeypatch, _source_words()) == {"FPB", "WFPB"}

def test_single_aligned_row_cannot_be_completed_by_displaced_row(monkeypatch):
    words = tuple(word for word in _source_words() if word.block_no != 3)
    assert _run(monkeypatch, words) == set()

def test_vertical_native_title_allows_adjacent_code_column_not_distant_page_rows(monkeypatch):
    words = (
        _word("same", 1, 0, "CEILING FINISHES SCHEDULE", 1402, 1418, 622),
        _word("same", 2, 0, "FPB", 1377, 1389, 333),
        _word("same", 2, 1, "FLUSHSET PLASTERBOARD", 1377, 1389, 345),
        _word("same", 3, 0, "WFPB", 1409, 1421, 333),
        _word("same", 3, 1, "WET AREA FLUSHSET PLASTERBOARD", 1409, 1421, 345),
        _word("same", 4, 0, "GRID", 800, 812, 1100),
        _word("same", 4, 1, "SUSPENDED CEILING GRID SYSTEM", 800, 812, 1112),
    )
    # A native vertical title is tall; use source-owned text extents.
    title = words[0]
    from dataclasses import replace
    words = (replace(title, bbox=(1402, 622, 1418, 785)),) + words[1:]
    assert _run(monkeypatch, words) == {"FPB", "WFPB"}
