"""F.07 acceptance trace: original source and misleading-grid fail-closed cases."""
import hashlib
from pathlib import Path

import fitz
import pytest

from tools.diag_gpt2_semantic_frame_acceptance_shadow import (
    _contains, _first_gate, trace_accepted_semantic_frame_sources,
)

ORIGINAL = Path("documents/sources/Arch_Combined_Maryborough_Service_Station.pdf")
SOURCE_SHA = "b1be53531412005f42937c89d0cfce66fbbe608315016bbb56731029ffc9e007"


def test_external_title_is_never_promoted_from_a_positive_looking_grid():
    assert _first_gate(
        title_inside=False, repeated_rect_cells=False, line_grid_positive=True
    ) == "external_line_grid_may_be_building_or_table_no_content_owner"
    assert _first_gate(
        title_inside=False, repeated_rect_cells=True, line_grid_positive=True
    ) == "external_caption_needs_native_table_content_and_title_owner"
    assert _first_gate(
        title_inside=False, repeated_rect_cells=False, line_grid_positive=False
    ) == "external_semantic_title_without_positive_table_content"
    assert _first_gate(
        title_inside=True, repeated_rect_cells=False, line_grid_positive=False
    ) == "enclosed_title_still_needs_accepted_frame_source_role"


def test_title_frame_containment_is_geometric_only():
    assert _contains((0,0,100,200),(10,20,50,100))
    assert not _contains((0,0,100,200),(120,20,130,50))
    assert not _contains((0,0,100,200),(95,20,105,50))
    assert not _contains((0,0,100,200),(20,20,20,50))
    assert not _contains((0,0,float('nan'),200),(10,20,50,100))


def test_source_requires_valid_one_based_page_and_does_not_make_view():
    with pytest.raises(ValueError):
        trace_accepted_semantic_frame_sources(object(),page_number=0)
    with pytest.raises(ValueError):
        trace_accepted_semantic_frame_sources(object(),page_number=True)


def test_original_source_a120_semantic_frame_vs_rotated_ceiling_band():
    before = ORIGINAL.read_bytes()
    assert hashlib.sha256(before).hexdigest() == SOURCE_SHA
    with fitz.open(stream=before,filetype="pdf") as document:
        page = document[8]
        result = trace_accepted_semantic_frame_sources(page,page_number=9)
        assert result["reported_view_count"] >= 1
        assert result["original_source_title_anchor_count"] >= 1
        assert result["original_native_frame_rectangle_count"] >= 1
        assert not result["producer_viewports_mutated"]
        assert not result["newly_authorized_viewports"]
        assert not result["newly_authorized_schedule_table_frames"]
        assert not result["newly_authorized_customer_quantities"]
        rows = result["reported_semantic_frame_source_gate_rows"]
        assert rows
        for row in rows:
            assert not row["semantic_frame_owner_authenticated_by_this_trace"]
            assert not row["source_semantic_table_text_trusted_by_this_trace"]
            assert not row["source_ceiling_quantity_granted"]
        # The A120 source evidence is a negative case for accepting a
        # semantic schedule region by a building-grid line appearance.
        reported_schedule = [
            row for row in rows
            if row["reported_semantic_view_id"] == "view_p9_4"
        ]
        assert len(reported_schedule) == 1
        region = reported_schedule[0]
        if region["reported_status"] == "resolved":
            assert not region["reported_title_inside_frame"]
            assert region["reported_frame_native_bbox_pdf_pts"] is not None
            assert region["first_unclosed_external_table_owner_gate"] != (
                "enclosed_title_still_needs_accepted_frame_source_role"
            )
            assert all(
                not word["source_text_trusted"]
                for word in region["original_raw_words_inside_reported_frame"]
            )
        # The historic derived RCP (if still published by current main) must
        # retain its dependency rather than becoming physical room proof.
        for item in result["reported_rotated_separator_dependents"]:
            assert not item["source_positive_semantic_separator_owner_proven_here"]
    assert hashlib.sha256(ORIGINAL.read_bytes()).hexdigest() == SOURCE_SHA
