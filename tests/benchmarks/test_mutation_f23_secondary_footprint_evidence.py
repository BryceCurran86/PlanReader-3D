"""Legacy F.23 horizontal-chain suite replaced by orthogonal-depth attacks.

See ``test_mutation_f23_orthogonal_depth.py`` for the governing synthetic
matrix (all four edges, thickness traps, witness requirements, etc.).

This module keeps a narrow regression that F.15's horizontal-chain extractor
API is untouched by the F.23 depth work.
"""
from __future__ import annotations

import inspect

import pb_dimension_chain_evidence_extractor as f15


def test_f15_horizontal_chain_extractor_module_untouched_by_f23_depth_work():
    src = inspect.getsource(f15.extract_dimension_chains_from_page)
    # F.15 remains the horizontal consumer; F.23 must not invert this contract.
    assert "horizontal" in src.lower()
    assert f15.__doc__ is not None
    assert "F.15" in f15.__doc__


def _simple_verandah_plan_pdf(tmp_path, name: str):
    import fitz
    doc = fitz.open()
    page = doc.new_page(width=640, height=460)
    page.insert_text((72, 72), "GROUND FLOOR PLAN", fontsize=11)
    page.insert_text((72, 96), "10,000", fontsize=11)
    page.insert_text((72, 120), "6,000", fontsize=11)
    page.insert_text((72, 144), "VERANDAH", fontsize=11)
    out = tmp_path / name
    doc.save(str(out))
    doc.close()
    return out


def _secondary_depth(*, status: str, width_m: float = 3.4):
    from pb_secondary_footprint_evidence import SecondaryFootprintEvidence
    return SecondaryFootprintEvidence(
        label_text="VERANDAH",
        width_m=width_m,
        view_id="view_p1_1",
        view_status=status,
        source_page=1,
        edge="bottom",
        chain_id="synthetic-depth",
        label_bbox=(50.0, 300.0, 120.0, 315.0),
        notes=("synthetic mutation evidence",),
        depth_orientation="vertical",
        binding_status="witness_bound",
    )


def test_derived_secondary_depth_does_not_redefine_live_floor_geometry(tmp_path, monkeypatch):
    from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
    from pb_viewport_segmentation import ViewportSegmentationStatus
    import pb_secondary_footprint_evidence as f23

    pdf = _simple_verandah_plan_pdf(tmp_path, "derived-secondary-depth.pdf")
    monkeypatch.setattr(
        f23,
        "resolve_secondary_footprint_width_m",
        lambda *args, **kwargs: _secondary_depth(
            status=ViewportSegmentationStatus.DERIVED.value,
            width_m=3.4,
        ),
    )

    preds = GenericPlanReaderExtractor().extract_from_pdf(
        pdf, collect_item35_shadow=False
    )
    floor = {p.tag: p for p in preds}["floor_screed"]

    assert floor.metadata["derived_footprint_area_m2"] == 60.0
    assert floor.metadata["structural_bed_area_m2"] == 60.0
    assert floor.metadata["component_areas"]["verandah_2"] == 0.0
    assert "Verandah (missing: width)" in floor.metadata["missing_components"]


def test_resolved_secondary_depth_can_extend_live_floor_geometry(tmp_path, monkeypatch):
    from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
    from pb_viewport_segmentation import ViewportSegmentationStatus
    import pb_secondary_footprint_evidence as f23

    pdf = _simple_verandah_plan_pdf(tmp_path, "resolved-secondary-depth.pdf")
    monkeypatch.setattr(
        f23,
        "resolve_secondary_footprint_width_m",
        lambda *args, **kwargs: _secondary_depth(
            status=ViewportSegmentationStatus.RESOLVED.value,
            width_m=3.4,
        ),
    )

    preds = GenericPlanReaderExtractor().extract_from_pdf(
        pdf, collect_item35_shadow=False
    )
    floor = {p.tag: p for p in preds}["floor_screed"]

    assert floor.metadata["derived_footprint_area_m2"] == 94.0
    assert floor.metadata["structural_bed_area_m2"] == 94.0
    assert floor.metadata["component_areas"]["verandah_2"] == 34.0
