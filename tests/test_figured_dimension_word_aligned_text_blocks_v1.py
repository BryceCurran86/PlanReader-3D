"""Native text-direction hints must be keyed like the words they are looked up by (default-off shadow switch).

``_native_word_orientations`` reads text-line directions from ``get_text("dict")`` and the binder looks them up with the
(block, line) of ``get_text("words")``. The default dict profile also numbers image blocks, so an image earlier in the
content stream shifts every later key and lends one line's direction to another word. ``word_aligned=True`` /
``word_aligned_text_blocks=True`` reads the dict with the words profile. The default is unchanged byte for byte (it is
what the signed replays were produced with) and no production module forwards the switch until a reviewed promotion.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import re
from typing import Mapping, Optional

import fitz
import pytest

from pb_figured_dimension_evidence import (
    _native_word_orientations,
    extract_dimension_evidence_bundle,
)
from tools.diag_figured_text_flag_alignment_census import census_pdf, main as census_main

ROOT = Path(__file__).resolve().parents[1]


# --- a tiny deterministic PDF builder (stream order decides block numbering) --------------------------------------------

def _pdf_bytes(objects: Mapping[int, str]) -> bytes:
    header = b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n"
    chunks, offsets, pos = [header], {}, len(header)
    for number in sorted(objects):
        offsets[number] = pos
        chunk = f"{number} 0 obj\n".encode("ascii") + objects[number].encode("latin1") + b"\nendobj\n"
        chunks.append(chunk)
        pos += len(chunk)
    size = max(objects) + 1
    xref = [f"xref\n0 {size}\n", "0000000000 65535 f \n"]
    for number in range(1, size):
        xref.append(f"{offsets[number]:010d} 00000 n \n" if number in offsets else "0000000000 00000 f \n")
    trailer = f"trailer\n<< /Size {size} /Root 1 0 R >>\nstartxref\n{pos}\n%%EOF\n"
    return b"".join(chunks) + "".join(xref).encode("ascii") + trailer.encode("ascii")


def _pdf(stream: str) -> bytes:
    return _pdf_bytes({
        1: "<< /Type /Catalog /Pages 2 0 R >>",
        2: "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 200] /Rotate 0 "
           "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        4: f"<< /Length {len(stream.encode('latin1'))} >>\nstream\n{stream}\nendstream",
        5: "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    })


VERTICAL = "BT /F1 10 Tf 0 1 -1 0 40 60 Tm (2400) Tj ET "
HORIZONTAL = "BT /F1 10 Tf 1 0 0 1 120 150 Tm (3600) Tj ET "
IMAGE = "q 20 0 0 20 260 10 cm BI /W 1 /H 1 /CS /G /BPC 8 ID \xff EI Q "


def _open(stream: str):
    return fitz.open(stream=_pdf(stream), filetype="pdf")[0]


def _word_hints(page, *, aligned: bool) -> dict[str, Optional[str]]:
    hints = _native_word_orientations(page, word_aligned=aligned)
    return {str(w[4]): hints.get((int(w[5]), int(w[6]))) for w in page.get_text("words")}


def _tie_stream(prefix: str = "", middle: str = "", suffix: str = "") -> str:
    """A '3600' label equally close to an 80 pt horizontal and an 84 pt vertical dimension line, both with witnesses."""
    probe = _open(VERTICAL + HORIZONTAL)
    word = next(w for w in probe.get_text("words") if w[4] == "3600")
    cx, cy = (word[0] + word[2]) / 2, (word[1] + word[3]) / 2

    def seg(x1, y1, x2, y2):
        return f"{x1:.3f} {y1:.3f} m {x2:.3f} {y2:.3f} l S "

    d = 15.0
    lines = "q 1 0 0 -1 0 200 cm 0.5 w "
    lines += seg(cx - 40, cy + d, cx + 40, cy + d)
    lines += seg(cx - 40, cy + d - 6, cx - 40, cy + d + 6)
    lines += seg(cx + 40, cy + d - 6, cx + 40, cy + d + 6)
    lines += seg(cx - d, cy - 42, cx - d, cy + 42)
    lines += seg(cx - d - 6, cy - 42, cx - d + 6, cy - 42)
    lines += seg(cx - d - 6, cy + 42, cx - d + 6, cy + 42)
    lines += "Q "
    return prefix + lines + VERTICAL + middle + HORIZONTAL + suffix


def _bound_line(page, *, aligned: Optional[bool], text: str = "3600") -> Optional[str]:
    kwargs = {} if aligned is None else {"word_aligned_text_blocks": aligned}
    bundle = extract_dimension_evidence_bundle(page, page_num=1, **kwargs)
    for observation, binding in zip(bundle.observations, bundle.bindings):
        if text in str(observation.raw_text):
            return binding.dimension_line_id
    raise AssertionError("label not found")


# --- the hint maps ------------------------------------------------------------------------------------------------------

def test_without_images_both_numberings_agree() -> None:
    page = _open(VERTICAL + HORIZONTAL)
    expected = {"2400": "vertical", "3600": "horizontal"}
    assert _word_hints(page, aligned=False) == expected
    assert _word_hints(page, aligned=True) == expected


def test_default_numbering_is_shifted_by_a_leading_image_block_characterised() -> None:
    """The historical behaviour the signed outputs were produced with: keys are off by the image block."""
    page = _open(IMAGE + VERTICAL + HORIZONTAL)
    assert _word_hints(page, aligned=False) == {"2400": None, "3600": "vertical"}  # 3600 borrowed 2400's direction


@pytest.mark.parametrize(
    "stream",
    [
        IMAGE + VERTICAL + HORIZONTAL,
        VERTICAL + IMAGE + HORIZONTAL,
        VERTICAL + HORIZONTAL + IMAGE,
        IMAGE + VERTICAL + IMAGE + HORIZONTAL + IMAGE,
    ],
)
def test_word_aligned_hints_ignore_where_images_sit_in_the_content_stream(stream) -> None:
    assert _word_hints(_open(stream), aligned=True) == {"2400": "vertical", "3600": "horizontal"}


def test_a_vertical_line_in_another_block_never_lends_its_direction_to_a_horizontal_word() -> None:
    page = _open(IMAGE + VERTICAL + HORIZONTAL)
    aligned = _word_hints(page, aligned=True)
    assert aligned["3600"] == "horizontal" and aligned["2400"] == "vertical"


def test_each_numbering_has_its_own_cache_and_neither_poisons_the_other() -> None:
    page = _open(IMAGE + VERTICAL + HORIZONTAL)
    first_default = dict(_native_word_orientations(page))
    aligned = dict(_native_word_orientations(page, word_aligned=True))
    assert aligned != first_default
    assert _native_word_orientations(page) == first_default
    assert _native_word_orientations(page, word_aligned=True) == aligned


@pytest.mark.parametrize("flag", [1, 0, "yes", None, 1.0])
def test_the_switch_must_be_an_explicit_boolean(flag) -> None:
    page = _open(VERTICAL + HORIZONTAL)
    with pytest.raises(ValueError):
        _native_word_orientations(page, word_aligned=flag)
    with pytest.raises(ValueError):
        extract_dimension_evidence_bundle(page, page_num=1, word_aligned_text_blocks=flag)


# --- binding outcome ------------------------------------------------------------------------------------------------------

def test_an_unrelated_image_no_longer_decides_the_tie_when_word_aligned() -> None:
    plain = _bound_line(_open(_tie_stream()), aligned=True)
    assert plain is not None
    for stream in (_tie_stream(prefix=IMAGE), _tie_stream(middle=IMAGE), _tie_stream(suffix=IMAGE)):
        assert _bound_line(_open(stream), aligned=True) == plain


def test_default_behaviour_is_unchanged_and_still_image_dependent() -> None:
    plain = _bound_line(_open(_tie_stream()), aligned=None)
    with_image = _bound_line(_open(_tie_stream(prefix=IMAGE)), aligned=None)
    assert plain == _bound_line(_open(_tie_stream()), aligned=False)
    assert with_image == _bound_line(_open(_tie_stream(prefix=IMAGE)), aligned=False)
    assert with_image != plain  # the defect the switch addresses, kept byte for byte by default


def test_the_default_bundle_is_identical_with_or_without_the_explicit_false() -> None:
    stream = _tie_stream(prefix=IMAGE)
    implicit = extract_dimension_evidence_bundle(_open(stream), page_num=1)
    explicit = extract_dimension_evidence_bundle(_open(stream), page_num=1, word_aligned_text_blocks=False)
    assert implicit == explicit


def test_word_aligned_bundles_are_deterministic_and_the_page_is_not_mutated() -> None:
    stream = _tie_stream(prefix=IMAGE)
    page = _open(stream)
    words_before = copy.deepcopy(page.get_text("words"))
    first = extract_dimension_evidence_bundle(page, page_num=1, word_aligned_text_blocks=True)
    second = extract_dimension_evidence_bundle(_open(stream), page_num=1, word_aligned_text_blocks=True)
    assert first == second
    assert page.get_text("words") == words_before


def test_word_aligned_output_with_an_image_equals_the_default_output_of_the_same_page_without_it() -> None:
    aligned_with_image = extract_dimension_evidence_bundle(
        _open(_tie_stream(prefix=IMAGE)), page_num=1, word_aligned_text_blocks=True
    )
    default_without_image = extract_dimension_evidence_bundle(_open(_tie_stream()), page_num=1)
    assert [(b.observation_id, b.status, b.dimension_line_id) for b in aligned_with_image.bindings] == [
        (b.observation_id, b.status, b.dimension_line_id) for b in default_without_image.bindings
    ]


# --- shadow only: nothing in production forwards the switch ---------------------------------------------------------------

def test_no_production_module_forwards_the_switch_yet() -> None:
    allowed = {"pb_figured_dimension_evidence.py", "tools/diag_figured_text_flag_alignment_census.py"}
    offenders = []
    for path in ROOT.rglob("*.py"):
        rel = path.relative_to(ROOT).as_posix()
        if rel.startswith(("tests/", ".claude/", "benchmarks/")) or rel in allowed:
            continue
        if re.search(r"word_aligned(_text_blocks)?\s*=", path.read_text(encoding="utf-8", errors="ignore")):
            offenders.append(rel)
    assert offenders == []


# --- the census tool ----------------------------------------------------------------------------------------------------------

def test_census_counts_image_shifted_hints_and_binding_changes() -> None:
    report = census_pdf(_pdf(_tie_stream(prefix=IMAGE)))
    totals = report["totals"]
    assert totals["pages"] == 1 and totals["hint_changed"] >= 1
    assert totals["pages_with_hint_change"] == 1 and totals["pages_with_evidence_change"] == 1
    assert totals["bindings_changed"] == 1
    (change,) = report["pages"][0]["binding_changes"]
    assert change["before"][2] != change["after"][2]


def test_census_of_a_page_without_images_reports_nothing_to_change() -> None:
    report = census_pdf(_pdf(_tie_stream()))
    assert report["totals"]["hint_changed"] == 0 and report["totals"]["pages_with_evidence_change"] == 0


def test_census_cli_writes_json_and_prints_totals_only(tmp_path, capsys) -> None:
    source = tmp_path / "synthetic.pdf"
    source.write_bytes(_pdf(_tie_stream(prefix=IMAGE)))
    out = tmp_path / "report.json"
    assert census_main([str(source), "--pages", "1", "--output", str(out)]) == 0
    printed = json.loads(capsys.readouterr().out)
    assert printed["hint_changed"] >= 1
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["totals"] == printed and len(written["sha256"]) == 64
