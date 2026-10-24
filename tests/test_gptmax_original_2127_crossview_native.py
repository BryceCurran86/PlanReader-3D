"""Cross-sheet 2127 native label proof; no host/quantity promotion."""
from pathlib import Path
from hashlib import sha256

import fitz
import pytest

from tools.diag_gptmax_original_2127_crossview_native import (
    LOT16_ORIGINAL_SHA,
    paired_native_2127_tokens,
    original_2127_crossview_receipt,
)


def _synthetic_page(*, word="STACKER", duplicate=False):
    doc=fitz.open()
    page=doc.new_page(width=600,height=300)
    page.insert_text((100,100),"2127 "+word,fontsize=10)
    if duplicate:
        page.insert_text((100,140),"2127 "+word,fontsize=10)
    return doc


def test_native_pair_requires_adjacent_words_on_same_line():
    doc=_synthetic_page()
    assert len(paired_native_2127_tokens(doc[0]))==1
    doc.close()
    doc=_synthetic_page(duplicate=True)
    assert len(paired_native_2127_tokens(doc[0]))==2
    doc.close()
    doc=_synthetic_page(word="SLIDER")
    assert paired_native_2127_tokens(doc[0])==()
    doc.close()


def test_other_drawing_or_untrusted_bytes_cannot_claim_crossview():
    doc=_synthetic_page()
    payload=doc.tobytes()
    doc.close()
    with pytest.raises(ValueError,match="SHA-verified"):
        original_2127_crossview_receipt(payload)
    with pytest.raises(ValueError,match="SHA-verified"):
        original_2127_crossview_receipt("not native bytes")


def test_exact_original_crossview_only_with_sha_verified_source():
    path=Path("documents/sources/1. Construction Plans - Lot 16 Power (REV E).pdf")
    if not path.is_file():
        pytest.skip("PRIVATE ORIGINAL SOURCE UNAVAILABLE: original-source proof NOT passed")
    data=path.read_bytes()
    from hashlib import sha256
    assert sha256(data).hexdigest()==LOT16_ORIGINAL_SHA
    receipt=original_2127_crossview_receipt(data)
    assert [r["page_number"] for r in receipt["native_marks"]]==[3,5]
    assert all(r["source_authentic"] is True for r in receipt["native_marks"])
    assert receipt["unique_structural_host_proven"] is False
    assert receipt["exact_cross_page_physical_identity_proven"] is False
    assert receipt["quantity_promotion_granted"] is False
    with pytest.raises(ValueError,match="SHA-verified"):
        original_2127_crossview_receipt(data+b"altered")


def _source_native_words(*, gap=1.0, pair_second=False, change_text=False):
    """Controlled genuine PDF-word shaped tuples with issuer block/line indices."""
    a = (10.0, 20.0, 30.0, 30.0, "2127", 0, 0, 0)
    b = (30.0 + gap, 20.0, 64.0 + gap, 30.0,
         "SLIDER" if change_text else "STACKER", 0, 0, 1)
    if not pair_second:
        return (a, b)
    return (a, b,
            (10.0, 60.0, 30.0, 70.0, "2127", 0, 1, 0),
            (31.0, 60.0, 65.0, 70.0, "STACKER", 0, 1, 1))


class _WordPage:
    def __init__(self, words):
        self.words = list(words)

    def get_text(self, mode):
        assert mode == "words"
        return self.words


@pytest.mark.parametrize("gap, expected", [
    (0.0, 1),
    (1.0, 1),
    (10.0, 1),
    (10.001, 0),
    (45.0, 0),
    (-0.001, 0),
])
def test_native_word_gap_is_bounded_by_own_ink_height(gap, expected):
    assert len(paired_native_2127_tokens(
        _WordPage(_source_native_words(gap=gap))
    )) == expected


def test_unrelated_same_line_words_are_not_a_source_owned_label_pair():
    # Same native block/line and immediate PDF word index are insufficient.
    # Distant words must remain distinct rather than produce a false 2127 mark.
    spaced = _WordPage(_source_native_words(gap=55))
    assert paired_native_2127_tokens(spaced) == ()
    assert paired_native_2127_tokens(
        _WordPage(_source_native_words(change_text=True))
    ) == ()


@pytest.mark.parametrize("scale", [0.1, 1.0, 4.0])
def test_source_word_gap_gate_is_translation_scale_covariant(scale):
    original = _source_native_words(gap=1.0)
    moved = [
        (10.0 + a[0]*scale, 37.0 + a[1]*scale,
         10.0 + a[2]*scale, 37.0 + a[3]*scale, *a[4:])
        for a in original
    ]
    assert len(paired_native_2127_tokens(_WordPage(moved))) == 1
    # A large gap stays unrelated under scale/translation.
    distant = _source_native_words(gap=100.0)
    moved_distant = [
        (10.0 + a[0]*scale, 37.0 + a[1]*scale,
         10.0 + a[2]*scale, 37.0 + a[3]*scale, *a[4:])
        for a in distant
    ]
    assert paired_native_2127_tokens(_WordPage(moved_distant)) == ()


def test_two_independent_native_pair_candidates_are_preserved_not_tiebroken():
    matches = paired_native_2127_tokens(
        _WordPage(_source_native_words(pair_second=True))
    )
    assert len(matches) == 2


def _synthetic_thirteen_page_source(*, page5_word="STACKER",
                                   double_page5=False):
    doc = fitz.open()
    try:
        for _ in range(13):
            doc.new_page(width=1200, height=900)
        doc[2].insert_text((400, 400), "2127 STACKER", fontsize=11)
        doc[4].insert_text((400, 400), "2127 " + page5_word, fontsize=11)
        if double_page5:
            doc[4].insert_text((400, 450), "2127 STACKER", fontsize=11)
        return doc.tobytes()
    finally:
        doc.close()


def test_two_source_native_pages_stay_source_only_even_with_both_labels(monkeypatch):
    from tools import diag_gptmax_original_2127_crossview_native as audit

    raw = _synthetic_thirteen_page_source()
    doc = fitz.open(stream=raw, filetype="pdf")
    try:
        centers = {}
        for n in (3, 5):
            (left, top, right, bottom), = paired_native_2127_tokens(doc[n-1])
            centers[n] = ((left+right)/2, (top+bottom)/2)
    finally:
        doc.close()
    monkeypatch.setattr(audit, "LOT16_ORIGINAL_SHA", sha256(raw).hexdigest())
    monkeypatch.setattr(audit, "_EXPECTED_CENTRES", centers)
    receipt = original_2127_crossview_receipt(raw)
    assert [r["page_number"] for r in receipt["native_marks"]] == [3,5]
    assert receipt["source_only_evidence"] is True
    assert all(not receipt[key] for key in (
        "exact_cross_page_physical_identity_proven", "unique_structural_host_proven",
        "whole_wall_frame_proven", "door_window_semantic_role_proven",
        "quantity_promotion_granted", "opening_count_completeness_proven",
    ))


@pytest.mark.parametrize("page5_word, double_page5", [
    ("SLIDER", False), ("STACKER", True),
])
def test_crosssheet_absent_or_competing_p5_label_abstains(
    monkeypatch, page5_word, double_page5,
):
    from tools import diag_gptmax_original_2127_crossview_native as audit

    raw = _synthetic_thirteen_page_source(
        page5_word=page5_word, double_page5=double_page5)
    doc = fitz.open(stream=raw, filetype="pdf")
    try:
        (left, top, right, bottom), = paired_native_2127_tokens(doc[2])
        c3 = ((left + right) / 2, (top + bottom) / 2)
    finally:
        doc.close()
    monkeypatch.setattr(audit, "LOT16_ORIGINAL_SHA", sha256(raw).hexdigest())
    monkeypatch.setattr(audit, "_EXPECTED_CENTRES", {3: c3, 5: c3})
    # Failure happens at source-pair uniqueness, before any location-based
    # authentication or downstream physical opening/host authority.
    with pytest.raises(ValueError, match="unique native 2127 STACKER"):
        original_2127_crossview_receipt(raw)
