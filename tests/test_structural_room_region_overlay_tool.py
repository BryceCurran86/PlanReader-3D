"""The room-region overlay tool is read-only, deterministic and reports the shadow verdicts without granting anything."""
from __future__ import annotations

import json
import sys

import fitz

from pb_portable_raster_ocr_authority import MockOCRBackend, OCRLine
from tools.diag_structural_room_region_overlay import main, room_name_candidates, run

T = 2.6


def _strip(page, x0, y0, x1, y1, *, color=(0, 0, 0), width=0.96):
    page.draw_rect(fitz.Rect(x0, y0, x1, y1), color=color, width=width)


def _plan(path, *, with_text=True, rotation=0, title_block=False):
    document = fitz.open()
    page = document.new_page(width=842, height=595)
    if title_block:
        page.draw_rect(fitz.Rect(500, 400, 700, 500), color=None, fill=(0, 0, 0))     # stands for a title block / client panel
    _strip(page, 100, 100, 400, 100 + T)
    _strip(page, 100, 300 - T, 400, 300)
    _strip(page, 100, 100 + T, 100 + T, 300 - T)
    _strip(page, 400 - T, 100 + T, 400, 300 - T)
    _strip(page, 250 - T / 2, 100 + T, 250 + T / 2, 160)                    # partition with a 24 pt doorway
    _strip(page, 250 - T / 2, 184, 250 + T / 2, 300 - T)
    if with_text:
        page.insert_text((150, 220), "BED 1", fontname="helv", fontsize=10)
        page.insert_text((300, 220), "KITCHEN", fontname="helv", fontsize=10)
        page.insert_text((150, 150), "NOTE 12", fontname="helv", fontsize=10)
    if rotation:
        page.set_rotation(rotation)
    document.save(str(path))
    document.close()


def test_the_overlay_reports_two_rooms_their_names_and_the_doorway_chord(tmp_path):
    pdf = tmp_path / "plan.pdf"
    _plan(pdf)
    before = pdf.read_bytes()
    png, summary_path = tmp_path / "out" / "plan.png", tmp_path / "out" / "plan.json"
    png.parent.mkdir()
    summary = run(pdf, 1, png, summary_path, dpi=60)
    assert pdf.read_bytes() == before                                       # read-only
    assert png.exists() and png.stat().st_size > 1000
    assert json.loads(summary_path.read_text(encoding="utf-8")) == json.loads(json.dumps(summary, sort_keys=True))
    assert summary["regions"]["listed"] == 2 and summary["regions"]["typed_opening_chords"] >= 1
    names = sorted(c["text"] for row in summary["region_rows"] for c in row["native_room_name_candidates"])
    assert names == ["BED 1", "KITCHEN"]                                    # NOTE 12 is not a room name
    assert all(c["trust"] == "not_supplied" for row in summary["region_rows"] for c in row["native_room_name_candidates"])
    assert all(row["closure_chord_count"] >= 1 for row in summary["region_rows"])
    assert summary["shadow_only"] is True and summary["live_effect"] is False
    assert summary["room_authority_granted"] is False and summary["scale_authority_granted"] is False
    assert all(row["ocr_candidate_lines"] == [] for row in summary["region_rows"])
    assert summary["share_safe"] is True


def test_the_summary_is_deterministic(tmp_path):
    pdf = tmp_path / "plan.pdf"
    _plan(pdf)
    assert run(pdf, 1, None, None) == run(pdf, 1, None, None)


def test_room_name_candidates_use_whole_lines_and_the_existing_vocabulary(tmp_path):
    pdf = tmp_path / "plan.pdf"
    _plan(pdf)
    page = fitz.open(str(pdf))[0]
    labels = room_name_candidates(page)
    assert sorted(lab.text for lab in labels) == ["BED 1", "KITCHEN"]
    assert all(lab.trust == "not_supplied" and lab.source_word_ids for lab in labels)


def test_a_page_without_walls_has_no_regions_and_a_page_without_text_has_no_names(tmp_path):
    document = fitz.open()
    document.new_page(width=300, height=300)
    blank = tmp_path / "blank.pdf"
    document.save(str(blank))
    document.close()
    assert run(blank, 1, None, None)["regions"]["listed"] == 0
    pdf = tmp_path / "silent.pdf"
    _plan(pdf, with_text=False)
    summary = run(pdf, 1, None, None)
    assert summary["regions"]["listed"] == 2 and summary["native_room_name_candidates_on_page"] == 0


def test_the_cli_writes_the_files_and_prints_a_summary_without_the_polygons(tmp_path, capsys):
    pdf = tmp_path / "plan.pdf"
    _plan(pdf)
    out = tmp_path / "nested" / "deeper"
    argv = sys.argv
    sys.argv = ["tool", "--pdf", str(pdf), "--page", "1", "--png", str(out / "a.png"), "--json", str(out / "a.json"), "--dpi", "50"]
    try:
        assert main() == 0
    finally:
        sys.argv = argv
    printed = json.loads(capsys.readouterr().out)
    assert printed["regions"]["listed"] == 2 and "region_rows" not in printed
    assert (out / "a.png").exists() and (out / "a.json").exists()


def _centre_line(text):
    def responder(image, dpi):
        w, h = image.size
        box_px = (w / 2 - 20.0, h / 2 - 6.0, w / 2 + 20.0, h / 2 + 6.0)
        return [OCRLine(text, 0.93, box_px, tuple(round(v * 72.0 / dpi, 4) for v in box_px))]
    return responder


def test_candidate_ocr_readings_are_attached_to_the_region_they_stand_in_and_flagged_candidate_only(tmp_path):
    pdf = tmp_path / "plan.pdf"
    _plan(pdf, with_text=False)
    summary = run(pdf, 1, None, None, ocr_candidates=True, ocr_backend=MockOCRBackend(responder=_centre_line("BED 1")))
    rows = [line for row in summary["region_rows"] for line in row["ocr_candidate_lines"]]
    assert len(rows) == 2 and all(r["candidate_only"] is True and "text" not in r for r in rows)      # share-safe: no raw text
    assert all(r["room_name_vocabulary_match"] == "BED 1" and r["confidence"] == 0.93 for r in rows)
    private = run(pdf, 1, None, None, ocr_candidates=True, ocr_backend=MockOCRBackend(responder=_centre_line("BED 1")), private_detail=True)
    assert private["share_safe"] is False
    assert all(line["text"] == "BED 1" for row in private["region_rows"] for line in row["ocr_candidate_lines"])
    # native text trust is untouched by the optional OCR readings
    assert summary["room_authority_granted"] is False and summary["native_room_name_candidates_on_page"] == 0


def test_a_reading_that_is_not_a_room_name_is_kept_but_not_matched_and_an_unavailable_backend_adds_nothing(tmp_path):
    pdf = tmp_path / "plan.pdf"
    _plan(pdf, with_text=False)
    note = run(pdf, 1, None, None, ocr_candidates=True, ocr_backend=MockOCRBackend(responder=_centre_line("NOTE 12 SEE SPEC")),
               private_detail=True)
    rows = [line for row in note["region_rows"] for line in row["ocr_candidate_lines"]]
    assert rows and all(r["room_name_vocabulary_match"] is None and r["text"] == "NOTE 12 SEE SPEC" for r in rows)
    shared = run(pdf, 1, None, None, ocr_candidates=True, ocr_backend=MockOCRBackend(responder=_centre_line("NOTE 12 SEE SPEC")))
    assert all(row["ocr_candidate_lines"] == [] for row in shared["region_rows"])                  # not a room name: dropped
    none = run(pdf, 1, None, None, ocr_candidates=True, ocr_backend=MockOCRBackend(is_ready=False))
    assert all(row["ocr_candidate_lines"] == [] for row in none["region_rows"])


def test_a_rotated_sheet_keeps_the_native_frame_and_maps_candidate_readings_back_into_it(tmp_path):
    flat, turned = tmp_path / "flat.pdf", tmp_path / "turned.pdf"
    _plan(flat, with_text=False)
    _plan(turned, with_text=False, rotation=90)
    a = run(flat, 1, None, None, ocr_candidates=True, ocr_backend=MockOCRBackend(responder=_centre_line("BED 1")))
    b = run(turned, 1, tmp_path / "turned.png", None, ocr_candidates=True, ocr_backend=MockOCRBackend(responder=_centre_line("BED 1")))
    assert [r["polygon"] for r in a["region_rows"]] == [r["polygon"] for r in b["region_rows"]]    # same native frame
    assert sum(len(r["ocr_candidate_lines"]) for r in b["region_rows"]) == 2
    assert (tmp_path / "turned.png").exists()


def test_the_default_drawing_is_made_on_a_white_sheet_and_private_detail_adds_the_page(tmp_path):
    from PIL import Image

    pdf = tmp_path / "plan.pdf"
    _plan(pdf, title_block=True)
    shared_png, private_png = tmp_path / "shared.png", tmp_path / "private.png"
    run(pdf, 1, shared_png, None, dpi=72)
    run(pdf, 1, private_png, None, dpi=72, private_detail=True)
    point = (600, 450)                                                       # inside the black "title block"
    assert min(Image.open(shared_png).convert("RGB").getpixel(point)) >= 250
    assert max(Image.open(private_png).convert("RGB").getpixel(point)) <= 200


def test_the_cli_is_share_safe_unless_private_detail_is_asked_for(tmp_path, capsys):
    pdf = tmp_path / "plan.pdf"
    _plan(pdf)
    argv = sys.argv
    try:
        sys.argv = ["tool", "--pdf", str(pdf), "--page", "1"]
        assert main() == 0
        assert json.loads(capsys.readouterr().out)["share_safe"] is True
        sys.argv = ["tool", "--pdf", str(pdf), "--page", "1", "--private-detail"]
        assert main() == 0
        assert json.loads(capsys.readouterr().out)["share_safe"] is False
    finally:
        sys.argv = argv
