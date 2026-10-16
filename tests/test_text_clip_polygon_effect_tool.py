"""The clip-effect diagnostic reports counts only, leaves the authority's result untouched and restores what it patched."""
from __future__ import annotations

import json

import pytest

import pb_pdf_text_integrity_authority as authority
from pb_text_clip_polygon_shadow import scene_document
from tools import diag_text_clip_polygon_effect as tool

WORD = "ZQXJV"
H = 400.0
DOT = "0 0 5 5 re f"


def pdf(clip_ops: str, *, x: float = 60.0, y: float = 100.0, rotation: int = 0) -> bytes:
    content = f"q {clip_ops} {DOT} BT /helv 14 Tf {x} {H - y} Td ({WORD}) Tj ET {DOT} Q".encode("ascii")
    return scene_document(content, rotation).tobytes()


def rect(x0, y0, x1, y1) -> str:
    return f"{x0} {H - y1} {x1 - x0} {y1 - y0} re"


UNION = f"{rect(50, 50, 200, 120)} {rect(300, 200, 450, 300)} W n"
ARCH = f"50 {H - 300} m 250 {H - 300} l 250 {H - 100} 50 {H - 100} 50 {H - 300} c h W n"
PLAIN_RECT = f"{rect(50, 50, 250, 120)} W n"


def page_row(payload: bytes) -> dict:
    return tool.effect(payload, [1])[0]


def test_a_word_in_a_polygon_clip_is_newly_trusted_by_the_clip_proof_alone():
    row = page_row(pdf(UNION))
    assert (row["words"], row["trusted_now"], row["newly_trusted_by_clip_proof_alone"], row["trusted_if_clip_proof_adopted"]) == (1, 0, 1, 1)
    assert row["still_blocked_after_clip_reason_lifted"] == {}


def test_a_word_on_a_rotated_page_is_newly_trusted_and_an_unclipped_page_is_trusted_already():
    rotated = page_row(pdf(PLAIN_RECT, rotation=90))
    assert (rotated["rotation"], rotated["trusted_now"], rotated["newly_trusted_by_clip_proof_alone"]) == (90, 0, 1)
    flat = page_row(pdf(""))
    assert (flat["trusted_now"], flat["newly_trusted_by_clip_proof_alone"]) == (1, 0)


def test_a_word_under_a_curved_clip_stays_blocked_and_is_listed_with_its_reason():
    row = page_row(pdf(ARCH, x=120, y=260))             # well inside the arch, which the authority cannot prove because it is curved
    assert row["trusted_now"] == 0 and row["newly_trusted_by_clip_proof_alone"] == 0
    assert row["still_blocked_after_clip_reason_lifted"] == {authority.TEXT_CLIP_STATE_UNRESOLVED: 1}


def test_a_word_outside_its_clip_is_not_made_visible_by_the_proof():
    row = page_row(pdf(PLAIN_RECT, x=300, y=300))
    assert row["words"] == 0 or row["newly_trusted_by_clip_proof_alone"] == 0                   # MuPDF drops fully clipped text altogether


def test_the_report_carries_counts_and_the_input_hash_but_no_word_text_and_grants_nothing():
    payload = pdf(UNION)
    result = tool.report(payload, [1])
    text = json.dumps(result)
    assert WORD not in text and "ZQ" not in text
    assert result["shadow_only"] is True and result["live_effect"] is False and result["text_trust_granted"] is False
    assert len(result["pdf_sha256"]) == 64


def test_the_authority_is_unchanged_inside_and_after_the_recording_context():
    original = authority._text_clip_reasons
    verdicts = {}
    with tool.recording_shadow_verdicts(verdicts):
        assert authority._text_clip_reasons is not original
    assert authority._text_clip_reasons is original
    with pytest.raises(RuntimeError):
        with tool.recording_shadow_verdicts(verdicts):
            raise RuntimeError("ingestion failed")
    assert authority._text_clip_reasons is original


def test_an_out_of_range_page_is_refused_and_the_cli_writes_the_report(tmp_path, capsys):
    payload = pdf(UNION)
    with pytest.raises(ValueError):
        tool.effect(payload, [2])
    source = tmp_path / "scene.pdf"
    source.write_bytes(payload)
    out = tmp_path / "report" / "effect.json"
    assert tool.main(["--pdf", str(source), "--pages", "1", "--json", str(out)]) == 0
    written = json.loads(out.read_text(encoding="utf-8"))
    assert written["pages"][0]["newly_trusted_by_clip_proof_alone"] == 1
    assert "newly trusted by the clip proof alone 1" in capsys.readouterr().out
