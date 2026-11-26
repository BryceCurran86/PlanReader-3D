"""Priority 1 residual: lossless vector-primitive provenance enrichment.

Gold-free. Proves additive path_index / clip ternary / native page-coordinate
retention through extract_native_page → lineage source records, without
inventing geometry or changing live ExtractedPrediction tags.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any, Dict, List
from unittest.mock import MagicMock

import fitz

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from pb_vector_geometry_v130 import (
    _ClipAssociationTable,
    _resolve_clip_fields,
    extract_native_page,
)
from pb_wall_room_topology_primitive_lineage import (
    LINEAGE_KEY,
    lineage_from_source_segments,
    source_record_from_segment,
)
from pb_wall_room_topology_stage_a import build_wall_graph_for_viewport


def _page_with_clip_line() -> fitz.Page:
    doc = fitz.open()
    page = doc.new_page(width=200, height=200)
    page.draw_line((60, 60), (140, 140), color=(0, 0, 0), width=2)
    xrefs = page.get_contents()
    data = doc.xref_stream(xrefs[0])
    doc.update_stream(xrefs[0], b"q\n50 50 100 100 re\nW\nn\n" + data + b"\nQ\n")
    # Keep doc alive via page.parent
    page._p1_doc = doc  # type: ignore[attr-defined]
    return page


def _record_fingerprint(record: Dict[str, Any]) -> str:
    return json.dumps(record, sort_keys=True, default=str, separators=(",", ":"))


def test_extract_native_page_emits_structured_path_indices_without_changing_ids() -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.draw_line((10, 10), (90, 10), color=(0, 0, 0), width=1.5)
    page.draw_rect(fitz.Rect(20, 20, 80, 80), color=(0, 0, 1), width=1.0)
    native = extract_native_page(page)
    doc.close()

    assert native["segment_count"] == len(native["segments"])
    line = next(seg for seg in native["segments"] if seg["kind"] == "line")
    assert line["id"] == "d0i0"
    assert line["path_index"] == 0
    assert line["item_index"] == 0
    assert "edge_index" not in line
    assert line["width_present"] is True
    assert line["stroke_present"] is True

    rect_edges = [seg for seg in native["segments"] if seg["kind"] == "rect_edge"]
    assert len(rect_edges) == 4
    for edge in rect_edges:
        assert edge["id"].startswith("d1i0e")
        assert edge["path_index"] == 1
        assert edge["item_index"] == 0
        assert edge["edge_index"] in {0, 1, 2, 3}


def test_a1_matched_seqno_known_no_active_clip() -> None:
    doc = fitz.open()
    page = doc.new_page()
    page.draw_line((10, 10), (50, 10), color=(0, 0, 0), width=1)
    native = extract_native_page(page)
    doc.close()
    seg = native["segments"][0]
    assert seg["clip_known"] is True
    assert seg["clip_present"] is False
    assert seg["clip"] is None
    record = source_record_from_segment(seg)
    assert record["clip_known"] is True
    assert record["clip_present"] is False


def test_a1_active_rectangular_clip() -> None:
    page = _page_with_clip_line()
    native = extract_native_page(page)
    assert len(native["segments"]) == 1
    seg = native["segments"][0]
    assert seg["clip_known"] is True
    assert seg["clip_present"] is True
    assert seg["clip"] is not None
    assert len(seg["clip"]) == 4
    # Clip association must not invent geometry endpoints.
    assert (seg["x1"], seg["y1"], seg["x2"], seg["y2"]) == (60.0, 60.0, 140.0, 140.0)
    record = source_record_from_segment(seg)
    assert record["clip_known"] is True
    assert record["clip_present"] is True


def test_a1_extended_drawing_api_unavailable() -> None:
    page = MagicMock()
    page.rect = fitz.Rect(0, 0, 100, 100)

    def _get_drawings(*args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        if kwargs.get("extended"):
            raise RuntimeError("extended drawings unavailable")
        return [
            {
                "width": 1.0,
                "color": (0, 0, 0),
                "fill": None,
                "layer": "",
                "dashes": "[] 0",
                "seqno": 7,
                "items": [("l", fitz.Point(0, 0), fitz.Point(40, 0))],
            }
        ]

    page.get_drawings.side_effect = _get_drawings
    page.get_text.return_value = []
    native = extract_native_page(page)
    seg = native["segments"][0]
    assert seg["id"] == "d0i0"
    assert seg["clip_known"] is False
    assert seg["clip_present"] is False
    assert seg["clip"] is None
    # Unknown must never become evidence of unclipped.
    record = source_record_from_segment(seg)
    assert record["clip_known"] is False
    assert record["clip_present"] is False


def test_a1_missing_seqno() -> None:
    page = MagicMock()
    page.rect = fitz.Rect(0, 0, 100, 100)

    def _get_drawings(*args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        if kwargs.get("extended"):
            return [
                {
                    "type": "s",
                    "level": 0,
                    "seqno": 1,
                    "items": [],
                }
            ]
        return [
            {
                "width": 1.0,
                "color": (0, 0, 0),
                "fill": None,
                "layer": "",
                "dashes": "[] 0",
                # seqno intentionally absent
                "items": [("l", fitz.Point(0, 0), fitz.Point(40, 0))],
            }
        ]

    page.get_drawings.side_effect = _get_drawings
    page.get_text.return_value = []
    native = extract_native_page(page)
    seg = native["segments"][0]
    assert seg["clip_known"] is False
    assert seg["clip_present"] is False
    assert seg["clip"] is None


def test_a1_unmatched_seqno() -> None:
    page = MagicMock()
    page.rect = fitz.Rect(0, 0, 100, 100)

    def _get_drawings(*args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        if kwargs.get("extended"):
            return [
                {
                    "type": "s",
                    "level": 0,
                    "seqno": 99,
                    "items": [],
                }
            ]
        return [
            {
                "width": 1.0,
                "color": (0, 0, 0),
                "fill": None,
                "layer": "",
                "dashes": "[] 0",
                "seqno": 3,
                "items": [("l", fitz.Point(0, 0), fitz.Point(40, 0))],
            }
        ]

    page.get_drawings.side_effect = _get_drawings
    page.get_text.return_value = []
    native = extract_native_page(page)
    seg = native["segments"][0]
    assert seg["clip_known"] is False
    assert seg["clip_present"] is False
    assert seg["clip"] is None


def test_a1_clip_states_serialize_to_different_provenance_records() -> None:
    known_none = source_record_from_segment(
        {
            "id": "d0i0",
            "kind": "line",
            "x1": 0.0,
            "y1": 0.0,
            "x2": 10.0,
            "y2": 0.0,
            "clip": None,
            "clip_present": False,
            "clip_known": True,
            "path_index": 0,
            "item_index": 0,
        }
    )
    active = source_record_from_segment(
        {
            "id": "d0i0",
            "kind": "line",
            "x1": 0.0,
            "y1": 0.0,
            "x2": 10.0,
            "y2": 0.0,
            "clip": [0.0, 0.0, 50.0, 50.0],
            "clip_present": True,
            "clip_known": True,
            "path_index": 0,
            "item_index": 0,
        }
    )
    unknown = source_record_from_segment(
        {
            "id": "d0i0",
            "kind": "line",
            "x1": 0.0,
            "y1": 0.0,
            "x2": 10.0,
            "y2": 0.0,
            "clip": None,
            "clip_present": False,
            "clip_known": False,
            "path_index": 0,
            "item_index": 0,
        }
    )
    fingerprints = {
        _record_fingerprint(known_none),
        _record_fingerprint(active),
        _record_fingerprint(unknown),
    }
    assert len(fingerprints) == 3
    # known-no-clip must not equal unknown
    assert known_none["clip_known"] is True
    assert unknown["clip_known"] is False
    assert known_none["clip_present"] is False
    assert unknown["clip_present"] is False


def test_resolve_clip_fields_table_contract() -> None:
    table = _ClipAssociationTable(
        available=True,
        by_seqno={1: None, 2: (0.0, 0.0, 10.0, 10.0)},
    )
    assert _resolve_clip_fields(clip_table=table, seq_key=1) == (True, False, None)
    assert _resolve_clip_fields(clip_table=table, seq_key=2) == (
        True,
        True,
        (0.0, 0.0, 10.0, 10.0),
    )
    assert _resolve_clip_fields(clip_table=table, seq_key=3) == (False, False, None)
    assert _resolve_clip_fields(clip_table=table, seq_key=None) == (False, False, None)
    unavailable = _ClipAssociationTable(available=False, by_seqno={})
    assert _resolve_clip_fields(clip_table=unavailable, seq_key=1) == (False, False, None)


def test_a2_non_finite_page_coords_are_not_claimed_present() -> None:
    base = {
        "id": "d0i0",
        "kind": "line",
        "path_index": 0,
        "item_index": 0,
        "clip_known": True,
        "clip_present": False,
        "clip": None,
    }
    cases = [
        {"x1": math.nan, "y1": 0.0, "x2": 10.0, "y2": 0.0},
        {"x1": 0.0, "y1": math.inf, "x2": 10.0, "y2": 0.0},
        {"x1": 0.0, "y1": 0.0, "x2": -math.inf, "y2": 0.0},
        {"x1": math.nan, "y1": math.inf, "x2": -math.inf, "y2": math.nan},
    ]
    for coords in cases:
        record = source_record_from_segment({**base, **coords})
        assert record["page_coords_present"] is False
        # Must not silently coerce non-finite geometry to zero.
        for field, raw in coords.items():
            assert field in record
            if math.isnan(raw):
                assert math.isnan(record[field])
            else:
                assert record[field] == raw


def test_a2_extract_native_page_skips_non_finite_line_geometry() -> None:
    page = MagicMock()
    page.rect = fitz.Rect(0, 0, 100, 100)

    class _BadPoint:
        def __init__(self, x: float, y: float) -> None:
            self.x = x
            self.y = y

    def _get_drawings(*args: Any, **kwargs: Any) -> List[Dict[str, Any]]:
        if kwargs.get("extended"):
            return [{"type": "s", "level": 0, "seqno": 0, "items": []}]
        return [
            {
                "width": 1.0,
                "color": (0, 0, 0),
                "fill": None,
                "layer": "",
                "dashes": "[] 0",
                "seqno": 0,
                "items": [
                    ("l", _BadPoint(math.nan, 0.0), _BadPoint(10.0, 0.0)),
                    ("l", _BadPoint(0.0, math.inf), _BadPoint(10.0, 0.0)),
                    ("l", _BadPoint(0.0, 0.0), _BadPoint(-math.inf, 0.0)),
                    ("l", _BadPoint(0.0, 0.0), _BadPoint(40.0, 0.0)),
                ],
            }
        ]

    page.get_drawings.side_effect = _get_drawings
    page.get_text.return_value = []
    native = extract_native_page(page)
    assert len(native["segments"]) == 1
    seg = native["segments"][0]
    assert seg["id"] == "d0i3"
    assert all(math.isfinite(seg[f]) for f in ("x1", "y1", "x2", "y2"))


def test_a3_presence_flags_follow_pymupdf_key_contract() -> None:
    """A3 audit: stroke/fill/width/dashes/layer keys are always on drawings.

    PyMuPDF ``get_drawings()`` emits those keys on every dict observed in the
    contract probe. Known absence is ``None`` (or ``\"\"`` for layer); there is
    no separate upstream “not supplied” state requiring new ``*_known`` flags.
    Clip remains the fallible association that needs ``clip_known``.
    """
    doc = fitz.open()
    page = doc.new_page()
    page.draw_line((10, 10), (50, 10), color=(0, 0, 0), width=1.5)
    page.draw_rect(fitz.Rect(30, 30, 40, 40), color=None, fill=(1, 0, 0), width=0)
    drawings = page.get_drawings()
    required = {"color", "fill", "width", "dashes", "layer"}
    for drawing in drawings:
        assert required.issubset(drawing.keys())
    native = extract_native_page(page)
    doc.close()
    stroke_seg = next(s for s in native["segments"] if s["kind"] == "line")
    assert stroke_seg["stroke_present"] is True
    assert stroke_seg["fill_present"] is False
    assert stroke_seg["width_present"] is True
    assert "clip_known" in stroke_seg
    fill_edges = [s for s in native["segments"] if s["kind"] == "rect_edge"]
    assert fill_edges
    assert fill_edges[0]["stroke_present"] is False
    assert fill_edges[0]["fill_present"] is True


def test_source_record_retains_path_indices_page_coords_and_clip_status() -> None:
    page = _page_with_clip_line()
    seg = extract_native_page(page)["segments"][0]
    record = source_record_from_segment(seg)
    assert record["path_index"] == seg["path_index"]
    assert record["item_index"] == seg["item_index"]
    assert record["page_coords_present"] is True
    assert (record["x1"], record["y1"], record["x2"], record["y2"]) == (
        seg["x1"],
        seg["y1"],
        seg["x2"],
        seg["y2"],
    )
    assert record["clip_present"] is True
    assert record["clip_known"] is True
    lineage = lineage_from_source_segments([seg])
    assert lineage["attribute_status"]["clip"] == "agreed"
    assert "clip" in lineage["attribute_status"]


def test_conflicting_clips_mark_attribute_conflict() -> None:
    a = {
        "id": "d0i0",
        "kind": "line",
        "x1": 0.0,
        "y1": 0.0,
        "x2": 10.0,
        "y2": 0.0,
        "clip": [0.0, 0.0, 50.0, 50.0],
        "clip_present": True,
        "clip_known": True,
        "path_index": 0,
        "item_index": 0,
    }
    b = {
        "id": "d1i0",
        "kind": "line",
        "x1": 0.0,
        "y1": 0.0,
        "x2": 10.0,
        "y2": 0.0,
        "clip": [10.0, 10.0, 60.0, 60.0],
        "clip_present": True,
        "clip_known": True,
        "path_index": 1,
        "item_index": 0,
    }
    lineage = lineage_from_source_segments([a, b])
    assert lineage["attribute_status"]["clip"] == "conflict"
    assert "clip" in lineage["attribute_conflicts"]


def test_w2_lineage_preserves_native_path_index_through_split_snap() -> None:
    doc = fitz.open()
    page = doc.new_page(width=300, height=300)
    # Crossing lines force the splitter to emit fragments.
    page.draw_line((20, 100), (220, 100), color=(0, 0, 0), width=1)
    page.draw_line((120, 20), (120, 220), color=(0, 0, 0), width=1)
    native = extract_native_page(page)
    doc.close()

    graph = build_wall_graph_for_viewport(native["segments"])
    edges = list(graph.get("edges") or [])
    assert edges
    for edge in edges:
        lineage = edge.get(LINEAGE_KEY) or {}
        records = lineage.get("source_records") or []
        assert records
        for record in records:
            assert "path_index" in record
            assert record.get("page_coords_present") is True


def test_live_extractor_predictions_unchanged_by_additive_provenance(tmp_path: Path) -> None:
    pdf_path = tmp_path / "p1-live.pdf"
    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.insert_text((40, 40), "SCALE 1:100 FLOOR PLAN")
    page.draw_rect(fitz.Rect(50, 80, 250, 280), color=(0, 0, 0), width=1)
    doc.save(pdf_path)
    doc.close()

    # Additive provenance must not introduce lineage or change prediction tags.
    extractor = GenericPlanReaderExtractor()
    preds = extractor.extract_from_pdf(str(pdf_path))
    tags = sorted(p.tag for p in preds)
    for pred in preds:
        payload = pred.to_dict()
        assert "primitive_lineage" not in payload
        assert "primitive_lineage" not in (payload.get("metadata") or {})
    # Re-run is deterministic for the live path.
    preds2 = extractor.extract_from_pdf(str(pdf_path))
    assert sorted(p.tag for p in preds2) == tags
    assert [p.to_dict() for p in preds2] == [p.to_dict() for p in preds]


import copy
from typing import Any
import pytest
from pb_source_visibility_authority import classify_native_segment_visibility
from pb_vector_geometry_v130 import _ClipAssociation, _clip_scissor_by_seqno

# PDF ``0 0 100 100 re`` clip on a 300x300 page, in top-left page coordinates.
_CLOSED_CLIP = "q 0 0 100 100 re W n 10 10 m 50 50 l S Q"
_CLOSED_CLIP_RECT = [0.0, 200.0, 100.0, 300.0]
_GROUP_LINE = "200 200 m 250 250 l S"


def _transparency_page(content: str, *, form: str = "", gstate: str = "<< >>") -> fitz.Page:
    """One 300x300 page with a transparency-group form /Fm1 and ExtGState /GS1."""
    objects = (
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 300] /Contents 4 0 R"
        " /Resources << /XObject << /Fm1 5 0 R >> /ExtGState << /GS1 6 0 R >> >> >>",
        f"<< /Length {len(content)} >>\nstream\n{content}\nendstream",
        "<< /Type /XObject /Subtype /Form /BBox [0 0 300 300]"
        f" /Group << /S /Transparency >> /Length {len(form)} >>\nstream\n{form}\nendstream",
        gstate,
    )
    pdf = b"%PDF-1.7\n"
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf += f"{number} 0 obj\n{body}\nendobj\n".encode("ascii")
    xref = f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
    xref += "".join(f"{offset:010d} 00000 n \n" for offset in offsets)
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{len(pdf)}\n%%EOF\n"
    doc = fitz.open(stream=pdf + xref.encode("ascii") + trailer.encode("ascii"), filetype="pdf")
    page = doc[0]
    page._p1_doc = doc  # type: ignore[attr-defined]
    return page


def _segments_by_id(page: fitz.Page) -> Dict[str, Dict[str, Any]]:
    return {seg["id"]: seg for seg in extract_native_page(page)["segments"]}


def test_group_after_closed_sibling_clip_does_not_inherit_it() -> None:
    page = _transparency_page(f"{_CLOSED_CLIP} /Fm1 Do", form=_GROUP_LINE)
    segments = _segments_by_id(page)

    assert sorted(segments) == ["d0i0", "d1i0"]
    assert segments["d0i0"]["clip_exact_rect"] == _CLOSED_CLIP_RECT
    grouped = segments["d1i0"]
    assert (grouped["path_index"], grouped["item_index"]) == (1, 0)
    assert (grouped["x1"], grouped["y1"], grouped["x2"], grouped["y2"]) == (200.0, 100.0, 250.0, 50.0)
    # Only the group form's own BBox clip is active once the sibling scope closed.
    assert grouped["clip_known"] is True
    assert grouped["clip_present"] is True
    assert grouped["clip_shape_known"] is True
    assert grouped["clip_exact_rect"] == [0.0, 0.0, 300.0, 300.0]
    assert classify_native_segment_visibility(grouped).visible is True
    assert extract_native_page(page) == extract_native_page(page)


def test_group_inside_open_clip_still_inherits_it() -> None:
    page = _transparency_page("q 0 0 100 100 re W n 10 10 m 50 50 l S /Fm1 Do Q", form=_GROUP_LINE)
    grouped = _segments_by_id(page)["d1i0"]

    assert grouped["clip_present"] is True
    assert grouped["clip_exact_rect"] == _CLOSED_CLIP_RECT
    assert classify_native_segment_visibility(grouped).visible is False


def test_blend_mode_group_after_closed_clip_is_known_unclipped() -> None:
    page = _transparency_page(f"{_CLOSED_CLIP} q /GS1 gs {_GROUP_LINE} Q", gstate="<< /BM /Multiply >>")
    grouped = _segments_by_id(page)["d1i0"]

    assert grouped["clip_known"] is True
    assert grouped["clip_present"] is False
    assert grouped["clip"] is None
    assert grouped["clip_exact_rect"] is None
    assert classify_native_segment_visibility(grouped).visible is True


def test_real_clip_opened_inside_group_still_applies() -> None:
    form = "q 150 150 100 100 re W n 120 120 m 250 250 l S Q"
    page = _transparency_page(f"{_CLOSED_CLIP} /Fm1 Do", form=form)
    grouped = _segments_by_id(page)["d1i0"]

    assert grouped["clip_present"] is True
    assert grouped["clip_exact_rect"] == [150.0, 50.0, 250.0, 150.0]
    decision = classify_native_segment_visibility(grouped)
    assert decision.visible is False
    assert decision.reason_codes == (VISIBILITY_RECTANGULAR_CLIP_EXCLUDES_SEGMENT,)


class _ExtendedDrawingsPage:
    def __init__(self, drawings: List[Dict[str, Any]]) -> None:
        self._drawings = drawings

    def get_drawings(self, *, extended: bool = False) -> List[Dict[str, Any]]:
        assert extended is True
        return self._drawings


def _clip_entry(level: int, rect: fitz.Rect) -> Dict[str, Any]:
    return {"type": "clip", "level": level, "scissor": rect, "items": (("re", rect, 1),)}


def test_clip_association_levels_include_non_clip_group_hierarchy() -> None:
    clip = fitz.Rect(20, 100, 120, 140)
    exact = (20.0, 100.0, 120.0, 140.0)
    drawings = [
        {"type": "group", "level": 0},
        _clip_entry(1, clip),
        {"type": "s", "level": 2, "seqno": 10},
        {"type": "group", "level": 1},
        {"type": "s", "level": 2, "seqno": 11},
        _clip_entry(2, clip),
        {"type": "s", "level": 3, "seqno": 12},
    ]
    snapshot = copy.deepcopy(drawings)
    table = _clip_scissor_by_seqno(_ExtendedDrawingsPage(drawings))

    assert drawings == snapshot
    assert table.available is True
    clipped = _ClipAssociation(
        clip_present=True, scissor=exact, exact_shape_known=True, exact_rect=exact
    )
    assert table.by_seqno == {
        10: clipped,
        11: _ClipAssociation(
            clip_present=False, scissor=None, exact_shape_known=True, exact_rect=None
        ),
        12: clipped,
    }


@pytest.mark.parametrize("level", [None, "1", -1])
def test_group_without_usable_level_does_not_close_clip_scope(level: Any) -> None:
    clip = fitz.Rect(20, 100, 120, 140)
    table = _clip_scissor_by_seqno(
        _ExtendedDrawingsPage(
            [
                {"type": "group", "level": 0},
                _clip_entry(1, clip),
                {"type": "group", "level": level},
                {"type": "s", "level": 2, "seqno": 21},
            ]
        )
    )

    assert table.by_seqno[21].clip_present is True
    assert table.by_seqno[21].exact_rect == (20.0, 100.0, 120.0, 140.0)


