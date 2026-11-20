"""No figured window becomes a commercial opening from two numbers and a gap."""
from hashlib import sha256
from dataclasses import replace
import fitz
import pytest

from pb_source_native_figured_window_bridge_review import (
    _visible_window_figure_lines,
    _same_owned_aperture_band,
    inspect_original_window_figured_bridge_review,
)
from pb_source_window_footprint_continuity import WindowFootprintBridge


def _original_synthetic(*, label="1200 - 1810 ASW", second_label=None):
    doc=fitz.open()
    page=doc.new_page(width=300,height=150)
    page.draw_rect(fitz.Rect(10,50,20,53),fill=(0,0,0),color=(0,0,0),width=.5)
    page.draw_rect(fitz.Rect(100,50,110,53),fill=(0,0,0),color=(0,0,0),width=.5)
    page.draw_line((55,55),(65,56),color=(0,0,0))
    page.draw_line((55,55),(65,54),color=(0,0,0))
    page.insert_text((29,64),label,fontsize=8)
    if second_label is not None:
        page.insert_text((29,69),second_label,fontsize=8)
    b=doc.tobytes()
    doc.close()
    return b


def _review(original):
    return inspect_original_window_figured_bridge_review(
        original,page_index=0,expected_source_sha256=sha256(original).hexdigest(),
    )


def test_full_sha_native_pdf_unique_figured_window_remains_review_only():
    raw=_original_synthetic()
    result=_review(raw)
    assert result.native_window_bridge_count==1
    assert result.source_figured_two_axis_window_line_count==1
    assert len(result.unique_source_figured_window_bridges)==1
    witness=result.unique_source_figured_window_bridges[0]
    assert witness.unordered_figured_axes_mm==(1200.0,1810.0)
    assert witness.provisional_product_m2==pytest.approx(2.172)
    assert len(witness.figured_word_indices)==4
    assert witness.physical_wall_authenticated is False
    assert witness.metric_authorized is False
    assert witness.customer_quantity_authorized is False
    assert witness.frozen_benchmark_scored is False
    assert result.frozen_benchmark_scored is False


@pytest.mark.parametrize("label",["90","04","1200","910 ASW","18 - 09 ADH","1200 - 1810 ASD"])
def test_dimensions_numeric_legend_compact_or_door_label_cannot_mint_window(label):
    result=_review(_original_synthetic(label=label))
    assert not result.unique_source_figured_window_bridges
    assert result.customer_quantity_authorized is False


def test_wrong_original_sha_fails_before_page_inspection():
    raw=_original_synthetic()
    with pytest.raises(ValueError,match="sha256_mismatch"):
        inspect_original_window_figured_bridge_review(
            raw,page_index=0,expected_source_sha256="0"*64,
        )


@pytest.mark.parametrize("index",[True,-1,2])
def test_page_scope_must_be_an_original_positive_integer_index(index):
    raw=_original_synthetic()
    with pytest.raises(ValueError,match="page"):
        inspect_original_window_figured_bridge_review(
            raw,page_index=index,expected_source_sha256=sha256(raw).hexdigest(),
        )


def test_rotated_vertical_callout_must_align_full_source_span_not_nearest():
    bridge=WindowFootprintBridge(
        left_host_path_id=1,right_host_path_id=2,
        marker_path_ids=(3,4),label_text="ASW",
        bounds_pdf_pts=(143.1,292.4,145.6,335.2),axis="v",page_index=0,
    )
    assert _same_owned_aperture_band(
        bridge,(132.5,288.9,140.3,338.5),
    )
    assert not _same_owned_aperture_band(
        bridge,(50.0,288.9,57.8,338.5),
    )


def test_two_identical_figured_line_candidates_do_not_choose_a_winner():
    raw=_original_synthetic(second_label="1200 - 1810 ASW")
    result=_review(raw)
    # If native line grouping merges the repeated text into one malformed
    # line it abstains; if it yields two complete lines the bridge is
    # explicitly ambiguous and abstains. Never publish one by nearest rank.
    assert not result.unique_source_figured_window_bridges
    assert result.customer_quantity_authorized is False
