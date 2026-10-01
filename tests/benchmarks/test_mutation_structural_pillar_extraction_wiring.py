"""tests/benchmarks/test_mutation_structural_pillar_extraction_wiring.py

Mutation/red-team suite for GenericPlanReaderExtractor's structural-support
authority boundary. Bay arithmetic and explicit count text remain evidence,
but only producer-owned physical StructuralMemberAuthority may publish live
support-member quantity. Every dimension/count value is synthetic and invented
for this test file.
"""
from __future__ import annotations

from pathlib import Path

import fitz
import pytest

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor


def _make_pillar_pdf(tmp_path: Path, *, include_keyword: bool, dims: list[str]) -> Path:
    doc = fitz.open()
    page = doc.new_page()
    lines = ["GROUND FLOOR PLAN", "SCALE 1:100", *dims]
    if include_keyword:
        lines.append("300 x 300mm CONCRETE COLUMNS TO VERANDAH")
    page.insert_text((72, 72), "\n".join(lines), fontsize=11)
    pdf_path = tmp_path / "synthetic_pillars.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def _extract(tmp_path: Path, **kwargs) -> dict:
    pdf_path = _make_pillar_pdf(tmp_path, **kwargs)
    extractor = GenericPlanReaderExtractor()
    preds = extractor.extract_from_pdf(pdf_path)
    return {p.tag: p for p in preds}


class TestStructuralColumnWiring:
    def test_keyword_plus_genuine_bay_chain_does_not_mint_member_quantity(
        self, tmp_path: Path
    ) -> None:
        # A real repeated bay pattern is useful evidence, but N+1 arithmetic
        # alone is not a physical-member census.
        pred_map = _extract(
            tmp_path, include_keyword=True,
            dims=["3,300", "3,350", "3,280", "3,320"],
        )
        assert "structural_columns" not in pred_map

    def test_keyword_without_a_genuine_bay_chain_emits_nothing(self, tmp_path: Path) -> None:
        # A single dimension, or genuinely dissimilar ones, is not a bay
        # chain -- the keyword alone must never be enough.
        pred_map = _extract(tmp_path, include_keyword=True, dims=["9,850"])
        assert "structural_columns" not in pred_map

    def test_genuine_bay_chain_without_the_keyword_emits_nothing(self, tmp_path: Path) -> None:
        # A repeated dimension pattern on its own (e.g. window spacing) is
        # not evidence of a structural support line without the keyword.
        pred_map = _extract(
            tmp_path, include_keyword=False,
            dims=["3,300", "3,350", "3,280", "3,320"],
        )
        assert "structural_columns" not in pred_map

    def test_ambiguous_multiple_candidate_runs_are_left_unresolved(self, tmp_path: Path) -> None:
        # Two distinct, unrelated repeated-dimension patterns on the same
        # page (e.g. a structural grid at ~3.3m and separately-repeated
        # ~2.1m spans) -- genuinely ambiguous which one is the support
        # line; must not guess by picking either.
        pred_map = _extract(
            tmp_path, include_keyword=True,
            dims=["3,300", "3,300", "3,300", "9,600", "2,100", "2,100"],
        )
        assert "structural_columns" not in pred_map

    def test_bay_count_evidence_stays_non_authoritative(self, tmp_path: Path) -> None:
        pred_map = _extract(
            tmp_path, include_keyword=True,
            dims=["4,000", "4,000", "4,000"],
        )
        assert "structural_columns" not in pred_map


def _make_physical_verandah_pdf(
    tmp_path: Path,
    *,
    centers: tuple[float, ...] = (160.0, 260.0, 360.0, 460.0),
    zone_text: str = "VERANDAH",
) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((72, 72), "GROUND FLOOR PLAN\nSCALE 1:100", fontsize=10)
    page.insert_text((275, 226), zone_text, fontsize=10)
    for x in (198.0, 298.0, 398.0):
        page.insert_text((x, 275), "2,500", fontsize=8)
    for x in centers:
        page.draw_rect(
            fitz.Rect(x - 2.0, 248.0, x + 2.0, 252.0),
            color=(0.4, 0.4, 0.4),
            fill=(0.8, 0.8, 0.8),
            width=0.5,
        )
    pdf_path = tmp_path / "physical_verandah_supports.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


class TestPhysicalVerandahSupportWiring:
    def test_complete_physical_support_row_publishes_verandah_pillars(
        self, tmp_path: Path
    ) -> None:
        pdf_path = _make_physical_verandah_pdf(tmp_path)
        extractor = GenericPlanReaderExtractor()
        pred_map = {
            prediction.tag: prediction
            for prediction in extractor.extract_from_pdf(pdf_path)
        }

        assert "verandah_pillars" in pred_map
        prediction = pred_map["verandah_pillars"]
        assert prediction.quantity == 4.0
        assert prediction.unit == "NO"
        assert prediction.metadata["derivation"] == (
            "physical_structural_member_authority"
        )
        assert prediction.metadata["structural_member_status"] == "corroborated"
        assert prediction.metadata["evidence_mode"] == "physical_symbol"
        assert len(prediction.metadata["support_symbol_ids"]) == 4
        assert len(prediction.metadata["physical_member_ids"]) == 4
        assert len(set(prediction.metadata["physical_member_ids"])) == 4
        assert len(prediction.metadata["source_sha256"]) == 64
        int(prediction.metadata["source_sha256"], 16)
        # No textual support keyword exists, so the older dimension+keyword
        # structural_columns path must remain locked.
        assert "structural_columns" not in pred_map

    @pytest.mark.parametrize(
        ("zone_text", "zone_type"),
        (
            ("ALFRESCO", "alfresco"),
            ("PORCH", "porch"),
            ("PATIO", "patio"),
        ),
    )
    def test_non_verandah_secondary_area_populates_coverage_trace_only(
        self, tmp_path: Path, zone_text: str, zone_type: str
    ) -> None:
        pdf_path = _make_physical_verandah_pdf(tmp_path, zone_text=zone_text)
        extractor = GenericPlanReaderExtractor()
        pred_map = {
            prediction.tag: prediction
            for prediction in extractor.extract_from_pdf(pdf_path)
        }

        assert "verandah_pillars" not in pred_map
        shadow = extractor.structural_member_coverage_shadow
        assert shadow["status"] == "corroborated"
        assert len(shadow["physical_member_ids"]) == 4
        assert shadow["quantity_evidence"]["value"] == pytest.approx(4.0)
        assert shadow["quantity_evidence"]["metadata"]["decision_scope_id"] == (
            f"secondary-area:{zone_type}:page:1"
        )
        assert shadow["coverage_registry_summary"] is not None

    def test_incomplete_physical_support_row_fails_closed(
        self, tmp_path: Path
    ) -> None:
        pdf_path = _make_physical_verandah_pdf(
            tmp_path,
            centers=(160.0, 260.0, 360.0),
        )
        extractor = GenericPlanReaderExtractor()
        pred_map = {
            prediction.tag: prediction
            for prediction in extractor.extract_from_pdf(pdf_path)
        }
        assert "verandah_pillars" not in pred_map


def _make_text_only_verandah_pdf(tmp_path: Path) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((72, 72), "GROUND FLOOR PLAN\nSCALE 1:100", fontsize=10)

    # Two independently reconstructed, matching dimension chains plus a
    # plausible support specification are intentionally sufficient for the
    # evidence module's text-specification mode, but not for live physical
    # structural-member quantity publication.
    for x in (198.0, 298.0, 398.0):
        page.insert_text((x, 220), "2,500", fontsize=8)
        page.insert_text((x, 270), "2,500", fontsize=8)
    page.insert_text((275, 245), "VERANDAH", fontsize=10)
    page.insert_text((255, 290), "100mm RHS Steel Poles", fontsize=8)

    pdf_path = tmp_path / "text_only_verandah_supports.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_text_only_secondary_support_evidence_cannot_publish_live_quantity(
    tmp_path: Path,
) -> None:
    pdf_path = _make_text_only_verandah_pdf(tmp_path)
    extractor = GenericPlanReaderExtractor()
    pred_map = {
        prediction.tag: prediction
        for prediction in extractor.extract_from_pdf(pdf_path)
    }
    assert "verandah_pillars" not in pred_map


def _make_explicit_structural_count_pdf(tmp_path: Path, text: str) -> Path:
    doc = fitz.open()
    page = doc.new_page(width=842, height=595)
    page.insert_text((72, 72), "GROUND FLOOR PLAN\nSCALE 1:100\n" + text, fontsize=10)
    pdf_path = tmp_path / "explicit_structural_count.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


@pytest.mark.parametrize(
    ("text", "blocked_tag"),
    (
        ("6 Nos CHS pillars to verandah", "verandah_pillars"),
        ("7 Nos masonry piers", "masonry_piers"),
    ),
)
def test_explicit_structural_count_text_cannot_mint_live_members(
    tmp_path: Path,
    text: str,
    blocked_tag: str,
) -> None:
    pdf_path = _make_explicit_structural_count_pdf(tmp_path, text)
    extractor = GenericPlanReaderExtractor()
    pred_map = {
        prediction.tag: prediction
        for prediction in extractor.extract_from_pdf(pdf_path)
    }
    assert blocked_tag not in pred_map
