"""Dimension inventory -> native item-face associations remain shadow-only."""
from dataclasses import replace
from decimal import Decimal

import fitz
import pytest

from planreader_next import associate_dimension_inventory_to_native_faces
from planreader_next.dimension_index import inventory_page_dimensions
from planreader_next.engine import SourceConflict, load_native_page


@pytest.fixture
def example(tmp_path):
    path = tmp_path / "source-connected-room.pdf"
    doc = fitz.open()
    pg = doc.new_page(width=400, height=320)
    pg.draw_rect(fitz.Rect(100, 80, 200, 160), color=(0, 0, 0), width=.4)
    # Two independent printed dimension lines, with hash/extension source ink
    # actually touching the physical room face at both endpoint stations.
    pg.draw_line(fitz.Point(90, 165.5), fitz.Point(210, 165.5))
    pg.draw_line(fitz.Point(100, 160), fitz.Point(100, 165.5))
    pg.draw_line(fitz.Point(200, 160), fitz.Point(200, 165.5))
    pg.insert_text((142, 176), "3600", fontsize=8)
    pg.draw_line(fitz.Point(206, 70), fitz.Point(206, 170))
    pg.draw_line(fitz.Point(200, 80), fitz.Point(206, 80))
    pg.draw_line(fitz.Point(200, 160), fitz.Point(206, 160))
    pg.insert_text((210, 116), "2400", fontsize=8)
    # A remote parallel wall with the same endpoints, outside any legitimate
    # 36pt source dimension-to-face bridge.
    pg.draw_line(fitz.Point(100, 20), fitz.Point(200, 20))
    # Near enough to look plausible, but its face is NOT reached by the
    # source dimension's 160..165.5 end ticks.
    pg.draw_line(fitz.Point(100, 150), fitz.Point(200, 150))
    doc.save(path)
    doc.close()
    page = load_native_page(path, 0)
    index = inventory_page_dimensions(page)
    faces = [
        seg for seg in page.segments
        if seg.kind in ("line", "rect_edge")
    ]
    south = next(seg for seg in faces if (
        abs(seg.y1 - 160) < .1 and abs(seg.y2 - 160) < .1
        and {round(seg.x1), round(seg.x2)} == {100, 200}
    ))
    east = next(seg for seg in faces if (
        abs(seg.x1 - 200) < .1 and abs(seg.x2 - 200) < .1
        and {round(seg.y1), round(seg.y2)} == {80, 160}
    ))
    remote = next(seg for seg in faces if (
        abs(seg.y1 - 20) < .1 and abs(seg.y2 - 20) < .1
    ))
    near_unconnected = next(seg for seg in faces if (
        abs(seg.y1 - 150) < .1 and abs(seg.y2 - 150) < .1
    ))
    words = {w.text: w.ref for w in page.words}
    return page, index, south, east, remote, near_unconnected, words


def _candidate(item_id, ref, kind="room_finished_face"):
    return {"item_id": item_id, "item_kind": kind, "face_segment_ref": ref}


def test_two_printed_dimensions_bind_exact_native_faces_but_never_publish(example):
    page, index, south, east, _remote, _near, words = example
    assert len(index.unique_geometry()) == 2
    out = associate_dimension_inventory_to_native_faces(page, index, [
        _candidate("room/south", south.ref),
        _candidate("room/east", east.ref),
    ])
    assert out["abstentions"] == []
    assert len(out["shadow_face_bindings"]) == 2
    by_word = {row["dimension_word_ref"]: row for row in out["shadow_face_bindings"]}
    width = by_word[words["3600"]]
    height = by_word[words["2400"]]
    assert width["face_segment_ref"] == south.ref
    assert width["printed_length_mm"] == "3600"
    assert width["orientation"] == "horizontal"
    assert len(width["connector_segment_refs"]) == 2
    assert height["face_segment_ref"] == east.ref
    assert height["printed_length_mm"] == "2400"
    assert height["orientation"] == "vertical"
    assert len(height["connector_segment_refs"]) == 2
    assert not out["commercial_publishable"] and out["official_score"] is None
    assert all(not row["physical_item_authenticated"] for row in out["shadow_face_bindings"])


def test_nearby_number_cannot_claim_remote_face_or_unconnected_item(example):
    page, index, _south, _east, remote, near, words = example
    out = associate_dimension_inventory_to_native_faces(page, index, [
        _candidate("remote-not-actual-face", remote.ref),
        _candidate("near-but-not-connected", near.ref),
    ])
    assert out["shadow_face_bindings"] == []
    assert {row["dimension_word_ref"] for row in out["abstentions"]} == {
        words["3600"], words["2400"]
    }
    assert all(row["reason_code"] == "no_source_connected_item_face" for row in out["abstentions"])


def test_competing_item_owners_fail_closed(example):
    page, index, south, east, _remote, _near, words = example
    out = associate_dimension_inventory_to_native_faces(page, index, [
        _candidate("living", south.ref),
        _candidate("kitchen", south.ref),
        _candidate("room/east", east.ref),
    ])
    assert len(out["shadow_face_bindings"]) == 1
    assert out["shadow_face_bindings"][0]["dimension_word_ref"] == words["2400"]
    assert {"dimension_word_ref": words["3600"], "reason_code": "physical_face_owner_ambiguous"} in out["abstentions"]


def test_nonexistent_face_and_wrong_source_inventory_refused(example):
    page, index, _south, _east, _remote, _near, _words = example
    with pytest.raises(SourceConflict, match="item_face_source_receipt_invalid"):
        associate_dimension_inventory_to_native_faces(page, index, [
            _candidate("invented", "seg:not-on-page"),
        ])
    with pytest.raises(SourceConflict, match="dimension_inventory_source_mismatch"):
        associate_dimension_inventory_to_native_faces(
            page, replace(index, source_sha256="0" * 64), [],
        )


def test_role_must_be_explicit_and_cannot_issue_a_quantity(example):
    page, index, south, _east, _remote, _near, _words = example
    with pytest.raises(SourceConflict, match="item_face_source_receipt_invalid"):
        associate_dimension_inventory_to_native_faces(page, index, [
            _candidate("room", south.ref, "automatic_room_area"),
        ])
    result = associate_dimension_inventory_to_native_faces(page, index, [
        _candidate("door-frame-not-yet-scheduled", south.ref, "opening_frame"),
    ])
    assert len(result["shadow_face_bindings"]) == 1
    assert result["shadow_face_bindings"][0]["item_kind_claimed"] == "opening_frame"
    assert result["shadow_face_bindings"][0]["commercial_publishable"] is False
    assert "quantity_m2" not in result["shadow_face_bindings"][0]


def test_shadow_association_cli_refuses_output_overwrite(example, tmp_path):
    import json
    import subprocess
    import sys
    from pathlib import Path

    page, index, south, east, _remote, _near, _words = example
    face_path = tmp_path / "reviewed-source-face-candidates.json"
    face_path.write_text(json.dumps({
        "source_sha256": page.source_sha256,
        "page_index": page.page_index,
        "item_faces": [
            _candidate("room/south", south.ref),
            _candidate("room/east", east.ref),
        ],
    }), encoding="utf8")
    output = tmp_path / "shadow-associations.json"
    cmd = [
        sys.executable, "-m", "planreader_next", "match-dimensions",
        "--pdf", str(tmp_path / "source-connected-room.pdf"),
        "--page", "0", "--faces", str(face_path), "--output", str(output),
    ]
    root = Path(__file__).resolve().parents[1]
    first = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False)
    assert first.returncode == 0, first.stderr
    result = json.loads(output.read_text(encoding="utf8"))
    assert len(result["shadow_face_bindings"]) == 2
    assert result["commercial_publishable"] is False
    second = subprocess.run(cmd, cwd=root, text=True, capture_output=True, check=False)
    assert second.returncode == 2
    assert "FileExistsError" in second.stderr
