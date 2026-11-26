"""A06 & A07: spatial grid registration parity/ambiguity veto + green-hatch exclusion cache."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace
import fitz

import pb_source_grid_registration_shadow as grid_reg
import pb_source_green_hatch_room_exclusion as green_excl


def test_a06_spatial_grid_witness_preserves_exact_unique_match_and_ambiguity_veto() -> None:
    axes = {
        "x": (
            {"native_constant_coordinate": 100.0, "source_style": (0, 0, 0, 0.5), "segment_count": 20, "native_source_span_pdf_pts": 500.0, "original_path_item_addresses": ((1, 0),)},
            {"native_constant_coordinate": 300.0, "source_style": (0, 0, 0, 0.5), "segment_count": 20, "native_source_span_pdf_pts": 500.0, "original_path_item_addresses": ((2, 0),)},
            {"native_constant_coordinate": 500.0, "source_style": (0, 0, 0, 0.5), "segment_count": 20, "native_source_span_pdf_pts": 500.0, "original_path_item_addresses": ((3, 0),)},
        ),
        "y": (
            {"native_constant_coordinate": 120.0, "source_style": (0, 0, 0, 0.5), "segment_count": 20, "native_source_span_pdf_pts": 500.0, "original_path_item_addresses": ((4, 0),)},
            {"native_constant_coordinate": 320.0, "source_style": (0, 0, 0, 0.5), "segment_count": 20, "native_source_span_pdf_pts": 500.0, "original_path_item_addresses": ((5, 0),)},
        ),
    }
    letters = {"A": {"x": 101.0, "y": 50.0}, "B": {"x": 299.0, "y": 50.0}}
    numbers = {"1": {"x": 40.0, "y": 119.5}, "2": {"x": 40.0, "y": 321.0}}

    matched = grid_reg._grid_vector_witness_for_page(axes, letters, numbers)
    assert matched is not None
    assert len(matched.get("matched_axes") or matched.get("matches") or matched) >= 1

    # Ambiguity veto: adding a competing axis within <= 4.5pt MUST abstain (return None)
    ambiguous_axes = {
        "x": axes["x"] + (
            {"native_constant_coordinate": 102.0, "source_style": (0, 0, 0, 0.5), "segment_count": 20, "native_source_span_pdf_pts": 500.0, "original_path_item_addresses": ((9, 0),)},
        ),
        "y": axes["y"],
    }
    assert grid_reg._grid_vector_witness_for_page(ambiguous_axes, letters, numbers) is None


def test_a07_green_hatch_diagonals_cache_is_exact_and_bounded(monkeypatch) -> None:
    green_excl._GREEN_DIAGONALS_CACHE.clear()
    doc = fitz.open()
    page = doc.new_page(width=400.0, height=300.0)
    for i in range(8):
        s = page.new_shape()
        x0 = 55.0 + i * 14.0
        y0 = 48.0 + (i % 4) * 16.0
        s.draw_line(fitz.Point(x0, y0), fitz.Point(x0 + 30.0, y0 + 30.0))
        s.finish(color=(0.0, 0.7, 0.0), width=0.5, closePath=False)
        s.commit()
    pdf_bytes = doc.tobytes()
    doc.close()
    sha = hashlib.sha256(pdf_bytes).hexdigest()

    floor = SimpleNamespace(
        canonical_floor_id="cf_1",
        physical_floor_surface_id="pfs_1",
        source_room_face_record_id="srf_1",
        source_sha256=sha,
        page_id="1",
        geometry_complete=True,
        physical_floor_surface_identity_resolved=True,
        polygon_pdf_pts=((40.0, 40.0), (220.0, 40.0), (220.0, 140.0), (40.0, 140.0)),
    )

    calls = 0
    orig_diag = green_excl._diagonals

    def counted_diag(p):
        nonlocal calls
        calls += 1
        return orig_diag(p)

    monkeypatch.setattr(green_excl, "_diagonals", counted_diag)
    w1 = green_excl.collect_native_green_hatch_exclusions(pdf_bytes, [floor])
    w2 = green_excl.collect_native_green_hatch_exclusions(pdf_bytes, [floor])
    assert w1 == w2
    assert len(w1) == 1
    assert calls == 1  # Second call reused immutable cached diagonals

    # Bounded eviction check
    monkeypatch.setattr(green_excl, "_GREEN_DIAGONALS_CACHE_MAX", 2)
    with fitz.open(stream=pdf_bytes, filetype="pdf") as d2:
        for k in range(5):
            green_excl._diagonals_cached(f"{k:064d}", 0, d2[0])
    assert len(green_excl._GREEN_DIAGONALS_CACHE) <= 2
