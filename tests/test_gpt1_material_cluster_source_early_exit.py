"""GPT1 Q06: do not OCR a source cluster that cannot meet minimum row count."""
from __future__ import annotations

import pb_source_material_semantic_authority as material


def _word(text: str, block_no: int):
    return material._TrustedTextWord(
        observation_id=f"src-{block_no}", page_id="1",
        source_partition_id="source-partition-1",
        text=text, bbox=(10.0, block_no * 15.0, 90.0, block_no * 15.0 + 10.0),
        block_no=block_no, line_no=0, word_no=0,
        trusted=False, reason_codes=("text_glyph_mapping_unverified",),
    )


def test_empty_native_definition_candidate_set_skips_all_expensive_ocr(monkeypatch):
    title = _word("FINISH SCHEDULE", 1)
    calls = []

    def no_definitions(words):
        calls.append(tuple(words))
        return ()

    def forbidden_recovery(**_kwargs):
        raise AssertionError("OCR must not run without two source definition rows")

    monkeypatch.setattr(material, "_raw_material_definition_candidates", no_definitions)
    monkeypatch.setattr(material, "_recover_native_material_block", forbidden_recovery)
    blocks, rejected = material._trusted_native_material_schedule_cluster_blocks(
        source=None, published=None, raster=None, words=(title,),
    )
    assert calls == [(title,)]
    assert blocks == rejected == ()


def test_one_row_cannot_trigger_unnecessary_material_title_raster_recovery(monkeypatch):
    title = _word("MATERIAL FINISH SCHEDULE", 1)
    one_row = ("partition", 2, (_word("FT1 floor tile", 2),), "FT1", {})
    monkeypatch.setattr(
        material, "_raw_material_definition_candidates",
        lambda words: (one_row,),
    )
    monkeypatch.setattr(
        material, "_recover_native_material_block",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected raster OCR")),
    )
    blocks, blocked = material._trusted_native_material_schedule_cluster_blocks(
        source=None, published=None, raster=None, words=(title, one_row[2][0]),
    )
    assert blocks == blocked == ()


def test_two_native_candidates_still_enter_existing_authentication_path(monkeypatch):
    words = (_word("FT1 floor tile", 1), _word("FT2 vinyl flooring", 2))
    seen = []
    monkeypatch.setattr(
        material, "_raw_material_definition_candidates",
        lambda _: (("p", 1, (words[0],), "FT1", {}),
                   ("p", 2, (words[1],), "FT2", {})),
    )
    original_group = material._group_native_material_block_words

    def counted_group(rows):
        seen.append(tuple(rows))
        return original_group(rows)

    monkeypatch.setattr(material, "_group_native_material_block_words", counted_group)
    blocks, blocked = material._trusted_native_material_schedule_cluster_blocks(
        source=None, published=None, raster=None, words=words,
    )
    assert seen == [words]
    assert blocks == blocked == ()



def test_fully_source_trusted_native_material_block_never_enters_raster_path(monkeypatch):
    from dataclasses import replace
    words = (
        replace(_word("FT1", 1), trusted=True, reason_codes=()),
        replace(_word("Porcelain floor tile", 1), trusted=True, reason_codes=(),
                word_no=1, observation_id="src-1-word-2"),
    )

    def fail_expensive(*args, **kwargs):
        raise AssertionError("already-trusted native source must not run raster OCR")

    monkeypatch.setattr(material, "_recover_admissible_viewport_words", fail_expensive)
    monkeypatch.setattr(material, "_recover_admissible_viewport_lines", fail_expensive)
    assert material._recover_native_material_block(
        source=None, published=None, raster=None, block_words=words,
    ) == words


def test_any_untrusted_native_material_word_retains_original_recovery_path(monkeypatch):
    from dataclasses import replace
    trusted = replace(_word("FT1", 1), trusted=True, reason_codes=())
    unresolved = replace(_word("floor tile", 1), word_no=1, observation_id="src-1b")
    words = (trusted, unresolved)
    calls = []

    def recover_words(*, words, **kwargs):
        calls.append("word")
        return words

    def recover_lines(*, words, **kwargs):
        calls.append("line")
        return words

    monkeypatch.setattr(material, "_recover_admissible_viewport_words", recover_words)
    monkeypatch.setattr(material, "_recover_admissible_viewport_lines", recover_lines)
    assert material._recover_native_material_block(
        source=None, published=None, raster=None, block_words=words,
    ) == words
    assert calls == ["word", "line"]
