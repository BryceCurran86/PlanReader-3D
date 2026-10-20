"""Tests for producer-owned outlined and vector-font text recognition shadow authority (Item 26)."""
from __future__ import annotations

import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_outlined_vector_font_shadow import (
    GLYPH_BASELINE_ALIGNED,
    GLYPH_INK_CANDIDATE,
    GLYPH_KERNING_REGULAR,
    GLYPH_RUN_CORROBORATED,
    ISOLATED_PATH_NOT_RUN,
    NOT_GLYPH_INK,
    PATH_EXTENT_OVER_BOUND,
    SOURCE_OUTLINED_TEXT_RESOLVED,
    SOURCE_OUTLINED_TEXT_UNAVAILABLE,
    STRUCTURAL_STROKE_CONTACT_VETO,
    UNPROVEN,
    SourceOutlinedGlyphRunRecord,
    SourceOutlinedVectorFontAuthority,
    SourceOutlinedVectorFontProducer,
    SourceOutlinedVectorFontSelector,
    classify_outlined_text_ink,
)


def _seg(ident, x1, y1, x2, y2, *, path=None):
    return {
        "id": ident,
        "x1": float(x1),
        "y1": float(y1),
        "x2": float(x2),
        "y2": float(y2),
        "path_index": ident if path is None else path,
    }


def _make_letter(prefix, bx, by):
    # Small 3-segment character glyph (~2x6 pt)
    return [
        _seg(f"{prefix}.1", bx, by, bx + 1.0, by - 6.0, path=prefix),
        _seg(f"{prefix}.2", bx + 1.0, by - 6.0, bx + 2.0, by, path=prefix),
        _seg(f"{prefix}.3", bx + 0.5, by - 3.0, bx + 1.5, by - 3.0, path=prefix),
    ]


def test_sealing_raises_permission_error():
    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceOutlinedVectorFontProducer(object())

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceOutlinedVectorFontAuthority(object(), {})

    with pytest.raises(PermissionError, match="Direct instantiation forbidden"):
        SourceOutlinedGlyphRunRecord(
            record_id="rec-1",
            run_id="run-1",
            orientation="horizontal",
            glyph_count=5,
            bounding_box=(0.0, 0.0, 50.0, 10.0),
            segment_ids=("s1", "s2"),
            reason_codes=(),
        )


def test_synthetic_positive_outlined_glyph_run():
    # 5 character glyphs along baseline y=100.0, spaced with 3 pt gaps
    segs = []
    for i in range(5):
        segs.extend(_make_letter(f"L{i}", 100.0 + 6.0 * i, 100.0))

    clf = classify_outlined_text_ink(segs, page_width=500.0, page_height=500.0)
    assert clf["status"] == "CLASSIFICATION_COMPLETE"
    assert clf["total_source_segments"] == 15
    assert clf["glyph_candidate_segment_count"] == 15
    assert clf["would_remain_after_withholding"] == 0
    assert clf["glyph_run_count"] == 1

    run = clf["glyph_runs"][0]
    assert run["glyph_count"] == 5
    assert run["orientation"] == "horizontal"
    assert GLYPH_BASELINE_ALIGNED in run["reason_codes"]
    assert GLYPH_KERNING_REGULAR in run["reason_codes"]
    assert GLYPH_RUN_CORROBORATED in run["reason_codes"]

    for s in segs:
        assert clf["classifications"][s["id"]] == GLYPH_INK_CANDIDATE


def test_structural_long_stroke_contact_veto():
    # Glyph touching a 50 pt wall line
    wall_seg = _seg("wall_1", 100.0, 100.0, 150.0, 100.0, path="wall_path")
    glyph_segs = _make_letter("L_touch", 100.5, 100.5)

    all_segs = [wall_seg] + glyph_segs
    clf = classify_outlined_text_ink(all_segs, page_width=500.0, page_height=500.0)

    # Wall segment is not a glyph (extent over bound)
    assert clf["classifications"]["wall_1"] == NOT_GLYPH_INK
    assert PATH_EXTENT_OVER_BOUND in clf["reason_receipts"]["wall_1"]

    # Glyph touching wall is vetoed and classified UNPROVEN
    for s in glyph_segs:
        assert clf["classifications"][s["id"]] == UNPROVEN
        assert STRUCTURAL_STROKE_CONTACT_VETO in clf["reason_receipts"][s["id"]]


def test_oversized_path_classified_not_glyph():
    # Path with 30 pt segment: too large for text glyph
    large_seg = _seg("large_stroke", 0.0, 0.0, 30.0, 0.0, path="p_large")
    clf = classify_outlined_text_ink([large_seg], page_width=500.0, page_height=500.0)
    assert clf["classifications"]["large_stroke"] == NOT_GLYPH_INK
    assert PATH_EXTENT_OVER_BOUND in clf["reason_receipts"]["large_stroke"]


def test_isolated_glyph_path_not_in_run():
    # Only 1 letter (requires >= 3 for a run)
    segs = _make_letter("solo", 50.0, 50.0)
    clf = classify_outlined_text_ink(segs, page_width=500.0, page_height=500.0)
    assert clf["glyph_run_count"] == 0
    for s in segs:
        assert clf["classifications"][s["id"]] == UNPROVEN
        assert ISOLATED_PATH_NOT_RUN in clf["reason_receipts"][s["id"]]


def test_irregular_kerning_breaks_run():
    # 2 letters close together, 3rd letter far away (gap = 40 pt > 15 pt max gap)
    l1 = _make_letter("L1", 10.0, 50.0)
    l2 = _make_letter("L2", 15.0, 50.0)
    l3 = _make_letter("L3", 60.0, 50.0)  # far gap
    all_segs = l1 + l2 + l3

    clf = classify_outlined_text_ink(all_segs, page_width=500.0, page_height=500.0)
    # Neither cluster has >= 3 members, so no run formed
    assert clf["glyph_run_count"] == 0
    assert clf["glyph_candidate_segment_count"] == 0


def test_authority_resolution_and_selector():
    producer = SourceOutlinedVectorFontProducer.create()
    segs = []
    for i in range(4):
        segs.extend(_make_letter(f"L{i}", 200.0 + 8.0 * i, 300.0))

    producer.register_page_vector_segments(
        document_id="doc-q5446",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
        segments=segs,
        page_width=842.0,
        page_height=595.0,
    )
    authority = producer.authority()

    sel = SourceOutlinedVectorFontSelector(
        document_id="doc-q5446",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="1",
    )
    res = authority.resolve(sel)
    assert res.status == EvidenceResolutionStatus.CORROBORATED.value
    assert SOURCE_OUTLINED_TEXT_RESOLVED in res.reason_codes
    assert res.total_segments == 12
    assert res.withheld_segment_count == 12
    assert res.retained_segment_count == 0
    assert len(res.records) == 1
    assert res.records[0].glyph_count == 4
    assert res.records[0].status == EvidenceResolutionStatus.CANDIDATE.value
    assert res.records[0].commercial_projection_allowed is False
    assert res.records[0].takeoff_eligible is False

    # Unregistered selector
    sel_unreg = SourceOutlinedVectorFontSelector(
        document_id="doc-q5446",
        revision_id="rev-01",
        source_sha256="a" * 64,
        snapshot_id="snap-01",
        page_id="99",
    )
    res_unreg = authority.resolve(sel_unreg)
    assert res_unreg.status == EvidenceResolutionStatus.ABSTAINED.value
    assert SOURCE_OUTLINED_TEXT_UNAVAILABLE in res_unreg.reason_codes
