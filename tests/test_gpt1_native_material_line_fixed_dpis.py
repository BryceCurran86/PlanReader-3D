"""Fixed, non-adaptive source-native material-line OCR authority profile.

The source-native path must choose both views BEFORE OCR. No result-dependent
retry, text normalization of punctuation, or direct trust promotion is allowed.
"""
from __future__ import annotations

from types import SimpleNamespace

import pb_source_material_semantic_authority as material
from pb_raster_text_corroboration_authority import RASTER_TEXT_CORROBORATION_DPIS


def test_native_material_line_profile_is_fixed_high_resolution() -> None:
    assert RASTER_TEXT_CORROBORATION_DPIS == (300, 450)
    assert material._MATERIAL_NATIVE_LINE_OCR_DPIS == (450, 600)
    assert len(set(material._MATERIAL_NATIVE_LINE_OCR_DPIS)) == 2


def test_native_material_block_invokes_only_the_fixed_profile(monkeypatch) -> None:
    word = SimpleNamespace(
        observation_id="native-word-id",
        page_id="11",
        source_partition_id="page:11",
        block_no=7,
        bbox=(10.0, 20.0, 23.0, 34.0),
        trusted=False,
    )
    calls = []

    def from_words(**kw):
        calls.append(("words", tuple(kw["words"])))
        return tuple(kw["words"])

    def from_line(**kw):
        calls.append(("line", kw["render_dpis"], tuple(kw["words"])))
        return tuple(kw["words"])

    monkeypatch.setattr(material, "_recover_admissible_viewport_words", from_words)
    monkeypatch.setattr(material, "_recover_admissible_viewport_lines", from_line)
    result = material._recover_native_material_block(
        source=object(),
        published=object(),
        raster=object(),
        block_words=(word,),
    )
    assert result == (word,)
    assert calls == [
        ("words", (word,)),
        ("line", (450, 600), (word,)),
    ]


def test_native_profile_cannot_authorise_text_without_evidence(monkeypatch) -> None:
    # The wrapper never changes trusted=False itself: only its existing
    # source/geometry/text/dual-DPI proof may return an authenticated word.
    word = SimpleNamespace(
        observation_id="native-word-id",
        page_id="11",
        source_partition_id="page:11",
        block_no=7,
        bbox=(10.0, 20.0, 23.0, 34.0),
        trusted=False,
    )
    monkeypatch.setattr(
        material, "_recover_admissible_viewport_words",
        lambda **kw: tuple(kw["words"]),
    )
    monkeypatch.setattr(
        material, "_recover_admissible_viewport_lines",
        lambda **kw: tuple(kw["words"]),
    )
    result = material._recover_native_material_block(
        source=object(), published=object(), raster=object(),
        block_words=(word,),
    )
    assert len(result) == 1
    assert result[0].trusted is False
