"""Focused fail-closed proposed-wall impact and cost regression tests."""
import pytest

from pb_vr_wall_assembly_dependencies import (
    NewWallDesign, WallAssemblySpecification, calculate_new_wall_construction_package,
)
from pb_vr_wall_change_impact import (
    ProposedWallRateBook, ProposedWallUnitRate, ProposedRelatedPage,
    ProposedRelatedPageCensus, preview_proposed_wall_impact,
)

SHA = "a" * 64


def fixture_package():
    wall = NewWallDesign(
        workspace_id="w1", source_sha256=SHA, snapshot_id="snapshot1",
        base_model_revision=2, proposal_id="new-wall-1", level_id="ground",
        start_pt=(0, 0), end_pt=(4, 0), height_m=2.4,
    )
    assembly = WallAssemblySpecification(
        specification_id="profile1", framing_system="timber",
        plate_runs=2, stud_spacing_m=0.6, noggin_rows=1,
        bracing_system="sheet", bracing_area_m2=4,
        lining_system="board", lining_face_ids=("left", "right"),
        skirting_system="mdf", skirting_face_ids=("left", "right"),
    )
    return calculate_new_wall_construction_package(wall, assembly)


def args(package, **extra):
    defaults = dict(
        package=package, tenant_id="tenant1", workspace_id="w1",
        source_sha256=SHA, assembly_profile_id="profile1",
        rate_book=None, page_census=None,
    )
    defaults.update(extra)
    return defaults


def census(sha=SHA, complete=True):
    return ProposedRelatedPageCensus(
        source_sha256=sha, complete=complete,
        pages=(ProposedRelatedPage(0, "A101", "witness101", True),
               ProposedRelatedPage(1, "A201", "witness201", True)),
    )


def book(package):
    rates = tuple(ProposedWallUnitRate(
        rate_id=f"rate{i}", trade=line.trade, element=line.element,
        unit=line.unit, unit_cost="12.345",
        source_evidence_id=f"evidence{i}",
    ) for i, line in enumerate({
        (x.trade, x.element, x.unit): x for x in package.quantities
    }.values()))
    return ProposedWallRateBook("tenant1", "w1", "profile1", "rate-v1", "AUD", rates)


def test_missing_providers_block_without_guessing_zero():
    result = preview_proposed_wall_impact(**args(fixture_package()))
    assert result["pricedComplete"] is False
    assert result["relatedPagesVerified"] is False
    assert result["wallCreated"] is False
    assert result["relatedPagesRevised"] is False
    assert result["quoteReady"] is False
    assert "authenticated_company_ratebook_unavailable" in result["constructionHolds"]
    assert "related_page_registration_incomplete" in result["constructionHolds"]


def test_trusted_rates_and_pages_create_deterministic_receipt_only():
    pkg = fixture_package()
    kwargs = args(pkg, rate_book=book(pkg), page_census=census())
    a = preview_proposed_wall_impact(**kwargs)
    b = preview_proposed_wall_impact(**kwargs)
    assert a["impactReceiptSha256"] == b["impactReceiptSha256"]
    assert a["pricedComplete"] is True
    assert a["relatedPagesVerified"] is True
    assert a["currency"] == "AUD"
    assert a["pricedSubtotalOnly"] != "0.00"
    assert len(a["affectedPages"]) == 2
    assert a["commercialPublicationAllowed"] is False
    assert a["persisted"] is False


def test_stale_source_or_tenant_ratebook_rejected():
    pkg = fixture_package()
    with pytest.raises(ValueError, match="foreign_or_untrusted_page_census"):
        preview_proposed_wall_impact(**args(pkg, page_census=census("b" * 64)))
    with pytest.raises(ValueError, match="foreign_or_untrusted_ratebook"):
        preview_proposed_wall_impact(**args(pkg, tenant_id="other", rate_book=book(pkg)))


def test_incomplete_page_coverage_never_claims_revision_ready():
    pkg = fixture_package()
    result = preview_proposed_wall_impact(**args(
        pkg, rate_book=book(pkg), page_census=census(complete=False)))
    assert result["relatedPagesVerified"] is False
    assert "related_page_registration_incomplete" in result["constructionHolds"]


def test_duplicate_rates_and_page_registrations_rejected():
    rate = ProposedWallUnitRate("r", "carpentry", "plates", "lm", "5", "source1")
    with pytest.raises(ValueError, match="ambiguous"):
        ProposedWallRateBook("tenant1", "w1", "profile1", "rev1", "AUD", (rate, rate))
    p = ProposedRelatedPage(0, "A101", "proof1", True)
    with pytest.raises(ValueError, match="duplicate"):
        ProposedRelatedPageCensus(SHA, True, (p, p))


def test_nonfinite_or_negative_money_rejected():
    with pytest.raises(ValueError, match="unit_cost_invalid"):
        ProposedWallUnitRate("r", "carpentry", "plates", "lm", "NaN", "source1")
    with pytest.raises(ValueError, match="unit_cost_invalid"):
        ProposedWallUnitRate("r", "carpentry", "plates", "lm", "-1", "source1")
