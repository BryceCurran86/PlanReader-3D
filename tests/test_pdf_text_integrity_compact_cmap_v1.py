"""Compact ToUnicode CMap tokenization regressions."""
from pb_pdf_text_integrity_authority import _valid_tounicode_cmap


def _cmap(body: str) -> bytes:
    return (
        "/CIDInit /ProcSet findresource begin\n"
        "12 dict begin\n"
        "begincmap\n"
        "/CMapType 2 def\n"
        "/CMapName/R24 def\n"
        "1 begincodespacerange\n"
        "<00><ff>\n"
        "endcodespacerange\n"
        f"{body}\n"
        "endcmap\n"
        "CMapName currentdict /CMap defineresource pop\n"
        "end\n"
        "end\n"
    ).encode("latin1")


def test_compact_bfrange_tokens_are_valid_pdf_cmap_syntax() -> None:
    stream = _cmap(
        "2 beginbfrange\n"
        "<01><01><0041>\n"
        "<02><02><0042>\n"
        "endbfrange"
    )
    assert _valid_tounicode_cmap(stream) is True


def test_compact_bfchar_tokens_are_valid_pdf_cmap_syntax() -> None:
    stream = _cmap(
        "2 beginbfchar\n"
        "<01><0041>\n"
        "<02><0042>\n"
        "endbfchar"
    )
    assert _valid_tounicode_cmap(stream) is True


def test_compact_mapping_count_mismatch_still_fails_closed() -> None:
    stream = _cmap(
        "2 beginbfrange\n"
        "<01><01><0041>\n"
        "endbfrange"
    )
    assert _valid_tounicode_cmap(stream) is False
