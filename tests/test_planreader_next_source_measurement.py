"""End-to-end proof on freshly generated vector PDFs, not private/gold drawings."""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import fitz
import pytest

from planreader_next import SourceConflict, inspect_page, load_native_page, measure_page


@pytest.fixture()
def drawing(tmp_path):
    path = tmp_path / "rectangular-room-native.pdf"
    pdf = fitz.open()
    page = pdf.new_page(width=550, height=450)
    page.draw_rect(fitz.Rect(120, 120, 320, 120 + 200 * 3297 / 4025))
    page.insert_text((205, 111), "4025", fontsize=10)
    page.insert_text((96, 206), "3297", fontsize=10)
    page.insert_text((170, 185), "FOOD", fontsize=11)
    page.insert_text((180, 219), "FT3", fontsize=11)
    page.insert_text((260, 109), "8888", fontsize=10)
    page.insert_text((400, 280), "FT2", fontsize=10)
    pdf.save(path)
    pdf.close()
    native = load_native_page(path, 0)
    words = {w.text: w.ref for w in native.words}
    selection = {
        "project_id": "sample-source-not-benchmark",
        "revision_id": "r1",
        "source_sha256": native.source_sha256,
        "page_index": 0,
        "rooms": [{
            "room_id": "real-native-rect-1",
            "rectangle_ref": native.rectangles[0].ref,
            "boundary_basis": "internal_finished_wall_face",
            "width_word_ref": words["4025"],
            "height_word_ref": words["3297"],
            "room_label_word_ref": words["FOOD"],
            "finish_word_ref": words["FT3"],
        }],
    }
    return path, native, selection, words


def _row(drawing):
    path, native, selection, words = drawing
    return dict(selection["rooms"][0])


def test_actual_native_pdf_to_exact_floor_finish_quantity(drawing):
    path, native, selection, words = drawing
    before = hashlib.sha256(path.read_bytes()).hexdigest()
    result = measure_page(native, selection)
    assert result["abstentions"] == []
    assert len(result["quantities"]) == 1
    row = result["quantities"][0]
    assert row["quantity"] == "13.270425"
    assert row["unit"] == "m2"
    assert row["room_label"] == "FOOD"
    assert row["finish_code"] == "FT3"
    assert row["status"] == "MEASURED_DRAFT_REVIEW_REQUIRED"
    assert row["commercial_publishable"] is False
    assert row["benchmark_credit"] is False
    assert hashlib.sha256(path.read_bytes()).hexdigest() == before


def test_reuses_existing_proven_native_pdf_extractor(drawing):
    path, native, selection, words = drawing
    inventory = inspect_page(native)
    assert inventory["source_sha256"] == hashlib.sha256(path.read_bytes()).hexdigest()
    assert inventory["rectangles"][0]["ref"].startswith("rect:p")
    assert {x["text"] for x in inventory["words"]} >= {"4025", "3297", "FT3", "FOOD"}


@pytest.mark.parametrize("key,value,reason", [
    ("boundary_basis", "outer_wall", "internal_finished_face_not_confirmed"),
    ("height_word_ref", "not-owned", "native_word_receipt_missing"),
])
def test_missing_or_wrong_source_abstains(drawing, key, value, reason):
    path, native, selection, words = drawing
    selection["rooms"][0][key] = value
    result = measure_page(native, selection)
    assert result["quantities"] == []
    assert result["abstentions"] == [{"room_id": "real-native-rect-1", "reason_code": reason}]


def test_painted_finish_from_outside_room_cannot_be_borrowed(drawing):
    path, native, selection, words = drawing
    selection["rooms"][0]["finish_word_ref"] = words["FT2"]
    result = measure_page(native, selection)
    assert result["quantities"] == []
    assert result["abstentions"][0]["reason_code"] == "room_or_finish_not_inside_selected_face"


def test_figure_product_cannot_override_axis_geometry(drawing):
    path, native, selection, words = drawing
    selection["rooms"][0]["width_word_ref"] = words["8888"]
    result = measure_page(native, selection)
    assert result["quantities"] == []
    assert result["abstentions"][0]["reason_code"] == "figured_axes_do_not_match_native_face_shape"


def test_caller_injected_numeric_area_cannot_authorize_value(drawing):
    path, native, selection, words = drawing
    selection["rooms"][0].update({"width_mm": 9000, "height_mm": 9000, "area_m2": 81})
    assert measure_page(native, selection)["quantities"][0]["quantity"] == "13.270425"


def test_stale_or_different_document_is_rejected(drawing):
    path, native, selection, words = drawing
    selection["source_sha256"] = "0" * 64
    with pytest.raises(SourceConflict, match="source_sha256_mismatch"):
        measure_page(native, selection)


def test_duplicate_room_cannot_be_double_sold(drawing):
    path, native, selection, words = drawing
    repeated = _row(drawing)
    repeated["room_id"] = "another-label-same-physical-face"
    selection["rooms"].append(repeated)
    with pytest.raises(SourceConflict, match="duplicate_room_or_physical_face"):
        measure_page(native, selection)


def test_dimension_receipts_cannot_be_reused_for_two_axes(drawing):
    path, native, selection, words = drawing
    selection["rooms"][0]["height_word_ref"] = words["4025"]
    result = measure_page(native, selection)
    assert result["quantities"] == []
    assert result["abstentions"][0]["reason_code"] == "source_word_receipt_reused"


def test_run_as_standalone_module_and_output_create_only(drawing, tmp_path):
    path, native, selection, words = drawing
    selected = tmp_path / "reviewed-selection.json"
    selected.write_text(json.dumps(selection), encoding="utf-8")
    output = tmp_path / "takeoff-draft.json"
    cmd = [sys.executable, "-m", "planreader_next", "measure",
           "--pdf", str(path), "--selection", str(selected), "--output", str(output)]
    root = Path(__file__).resolve().parents[1]
    first = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False)
    assert first.returncode == 0, first.stderr
    assert json.loads(output.read_text(encoding="utf-8"))["quantities"][0]["quantity"] == "13.270425"
    second = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False)
    assert second.returncode == 2
    assert "FileExistsError" in second.stderr


def test_suggest_from_clean_native_pdf_then_confirm_boundary(tmp_path):
    from planreader_next import suggest_room_bindings
    pdf_path = tmp_path / "native-room.pdf"
    document = fitz.open()
    page = document.new_page(width=500, height=450)
    page.draw_rect(fitz.Rect(120, 120, 320, 120 + 200 * 3297 / 4025))
    page.insert_text((205, 111), "4025", fontsize=10)
    page.insert_text((96, 206), "3297", fontsize=10)
    page.insert_text((170, 185), "FOOD", fontsize=11)
    page.insert_text((180, 219), "FT3", fontsize=11)
    document.save(pdf_path)
    document.close()
    page_evidence = load_native_page(pdf_path, 0)
    proposed = suggest_room_bindings(page_evidence)
    assert proposed["human_internal_finished_face_review_required"]
    assert len(proposed["rooms"]) == 1
    assert proposed["abstentions"] == []
    selected = dict(proposed, project_id="demonstration", revision_id="r1")
    assert measure_page(page_evidence, selected)["quantities"] == []
    assert measure_page(page_evidence, selected)["abstentions"][0]["reason_code"] == "internal_finished_face_not_confirmed"
    # Only a human who checks the wall-face basis may produce a measured draft.
    selected["rooms"][0]["boundary_basis"] = "internal_finished_wall_face"
    result = measure_page(page_evidence, selected)
    assert result["quantities"][0]["quantity"] == "13.270425"
    assert result["quantities"][0]["commercial_publishable"] is False


def test_suggestion_never_guesses_between_two_plausible_dimensions(drawing):
    from planreader_next import suggest_room_bindings
    path, native, selection, words = drawing
    result = suggest_room_bindings(native)
    assert result["rooms"] == []
    assert any(x["reason_code"] == "figured_axis_ambiguous_or_missing" for x in result["abstentions"])


def test_suggestion_does_not_use_frozen_truth_to_guess_a_room(tmp_path):
    from planreader_next import suggest_room_bindings
    pdf_path = tmp_path / "blank.pdf"
    doc = fitz.open()
    pg = doc.new_page()
    pg.draw_rect(fitz.Rect(100, 100, 300, 200))
    doc.save(pdf_path)
    doc.close()
    native = load_native_page(pdf_path, 0)
    assert suggest_room_bindings(native)["rooms"] == []
