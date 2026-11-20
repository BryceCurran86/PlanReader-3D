"""Source-native preview may display original figured window witnesses, never bill them."""
from types import SimpleNamespace
from pathlib import Path

import pytest

import pb_new_source_trace_preview as preview
from pb_source_native_figured_window_bridge_review import NativeFiguredWindowBridgeReview
from tests.test_new_source_trace_preview import _floor_plan


def test_native_source_preview_includes_authentic_review_only_figured_window_receipts(tmp_path, monkeypatch):
    captured = []
    def review(source_bytes, *, page_index, expected_source_sha256):
        assert source_bytes[:4] == b"%PDF"
        assert page_index == 0
        assert len(expected_source_sha256) == 64
        captured.append(expected_source_sha256)
        witness=NativeFiguredWindowBridgeReview(
            receipt_id="source-figure-review-1",
            source_sha256=expected_source_sha256,
            page_index=page_index,
            native_host_path_ids=(23,26),
            native_window_marker_path_ids=(31,32),
            figured_word_indices=(4,5,6,7),
            unordered_figured_axes_mm=(1200.,1810.),
            provisional_product_m2=2.172,
        )
        return SimpleNamespace(
            unique_source_figured_window_bridges=(witness,),
            ambiguous_lines_or_bridges=0,
        )
    monkeypatch.setattr(preview, "inspect_original_window_figured_bridge_review",review)
    summary,_=preview.source_native_trace_preview(_floor_plan(tmp_path),0)
    assert captured==[summary["source_sha256"]]
    assert summary["source_figured_window_review_status"]=="source_window_figures_review_only"
    assert summary["source_figured_window_unique_review_count"]==1
    assert len(summary["source_figured_window_review_receipts"])==1
    receipt=summary["source_figured_window_review_receipts"][0]
    assert receipt["source_host_native_path_ids"]==[23,26]
    assert receipt["figured_word_indices"]==[4,5,6,7]
    assert receipt["unordered_figured_axes_mm"]==[1200.,1810.]
    assert receipt["physical_wall_authenticated"] is False
    assert receipt["measurement_authorized"] is False
    assert receipt["customer_quantity_authorized"] is False
    assert receipt["frozen_benchmark_scored"] is False
    assert summary["source_figured_window_review_commercial_authority"] is False
    assert summary["quantity_authorized"] is False
    assert summary["commercial_publishable"] is False


def test_figured_source_window_review_error_abstains_without_affecting_actual_preview(tmp_path,monkeypatch):
    def review(*args,**kwargs):
        raise ValueError("original source figure unavailable")
    monkeypatch.setattr(preview, "inspect_original_window_figured_bridge_review",review)
    summary,_=preview.source_native_trace_preview(_floor_plan(tmp_path),0)
    assert summary["source_figured_window_review_status"]=="source_figured_window_review_unavailable:ValueError"
    assert summary["source_figured_window_review_receipts"]==[]
    assert summary["source_figured_window_unique_review_count"]==0
    assert summary["source_figured_window_review_commercial_authority"] is False
    assert summary["legacy_envelope_used"] is False
    assert summary["quantity_authorized"] is False
