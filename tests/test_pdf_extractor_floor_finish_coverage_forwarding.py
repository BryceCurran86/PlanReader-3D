"""Original extractor routing only; synthetic claims are not original-plan proof."""
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace

import fitz
import pytest

import pb_live_canonical_coverage_registry as coverage
import pb_live_ceiling_lining_integration as ceiling
import pb_live_physical_net_wall_integration as physical
import pb_page_registration_v1225 as registration
from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_floor_finish_area_source_closed_export import seal_live_floor_finish_area_run
from pb_live_floor_finish_customer_projection import project_live_floor_finish_customer_rows
from pb_migration_contracts import EvidenceResolutionStatus
from pb_planreader_pdf_extractor import GenericPlanReaderExtractor
from tests.test_live_floor_finish_area_source_closed_export import _claim


@pytest.mark.parametrize("inventory", ["valid", "blocked", "duplicate", "empty"])
def test_extractor_forwards_exact_original_finish_inventory_once(tmp_path, monkeypatch, inventory):
    # Independently exercise the existing typed issuer/seal/customer fixture.
    claim = _claim()
    sealed = seal_live_floor_finish_area_run(claim, workspace_id=1, project_id="routing")
    rows = project_live_floor_finish_customer_rows(claim, workspace_id=1, project_id="routing")
    assert verify_sealed_customer_output(sealed, rows).valid_quantity_count == 1
    original = claim.floor_finish_quantity_evidence[0]
    if inventory == "blocked":
        original = replace(original, value=None, abstained=True, status="abstained",
                           blocking_reasons=("source_finish_unavailable",))
    finishes = () if inventory == "empty" else (original,) * (2 if inventory == "duplicate" else 1)
    separate_ceiling = replace(original, quantity_id="independent-ceiling-quantity",
                               family="ceiling_lining")
    claim = replace(claim, floor_finish_quantity_evidence=finishes,
                    ceiling_lining_quantity_evidence=(separate_ceiling,))
    before = deepcopy(claim)
    path = tmp_path / "routing.pdf"
    with fitz.open() as doc:
        page = doc.new_page(width=600, height=800)
        page.insert_text((40, 50), "FLOOR PLAN")
        page.insert_text((40, 80), "SYNTHETIC ROUTING FIXTURE - NO ORIGINAL MEASUREMENT CLAIM")
        page.draw_rect(fitz.Rect(40, 120, 450, 600))
        doc.save(path)

    received_claim_options = []
    def collect(*args, **kwargs):
        received_claim_options.append(dict(kwargs))
        return claim
    monkeypatch.setattr(physical, "collect_live_physical_net_wall_claim", collect)
    monkeypatch.setattr(registration, "weighted_page_type",
                        lambda *args, **kwargs: ("Floor Plan", 100, ()))
    monkeypatch.setattr(GenericPlanReaderExtractor, "is_drawing_page", lambda *args: True)
    monkeypatch.setattr(GenericPlanReaderExtractor, "_ocr_text_for_page", lambda *args: "")
    monkeypatch.setattr(ceiling, "collect_live_ceiling_lining_claims",
                        lambda *args, **kwargs: SimpleNamespace(
                            canonical_ceilings=(), claims=(), reason_codes=(),
                            status=EvidenceResolutionStatus.ABSTAINED,
                            quantity_evidence=(separate_ceiling,)))
    captured = []
    def observe(**kwargs):
        captured.append(kwargs)
        return (), {}
    monkeypatch.setattr(coverage, "collect_live_canonical_coverage", observe)

    extractor = GenericPlanReaderExtractor()
    extractor.extract_from_pdf(path, collect_item35_shadow=False)
    assert len(received_claim_options) == len(captured) == 1
    assert "source_native_finish_text_shadow" not in received_claim_options[0]
    quantities = captured[0]["quantities"]
    forwarded = tuple(q for q in quantities if q.family == "floor_finish_area")
    assert len(forwarded) == len(finishes)
    assert all(actual is expected for actual, expected in zip(forwarded, finishes))
    assert sum(q is separate_ceiling for q in quantities) == 1
    assert claim == before
    assert extractor.coverage_family_gaps_live == {}
