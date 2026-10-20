import pytest
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_legend_symbol_taxonomy_shadow import (
    SourceLegendSymbolTaxonomyShadowAuthority,
    PlanLegendSymbolTaxonomyReceipt,
    LegendCategory,
    SCHEMA_VERSION,
)


def test_legend_viewport_registration_and_quarantine():
    authority = SourceLegendSymbolTaxonomyShadowAuthority()

    v = authority.register_legend_viewport(
        sheet_id="E101",
        bbox=(700.0, 50.0, 820.0, 400.0),
        category=LegendCategory.ELECTRICAL_SYMBOLS,
        symbols=[
            ("GPO", "General Power Outlet 10A Double", (710.0, 60.0, 730.0, 80.0)),
            ("LED", "Recessed LED Downlight 12W", (710.0, 90.0, 730.0, 110.0)),
        ],
    )

    assert v.sheet_id == "E101"
    assert v.category == LegendCategory.ELECTRICAL_SYMBOLS
    assert v.symbol_count == 2
    assert v.symbols[0].symbol_code == "GPO"

    # Quarantine checks
    assert authority.is_point_quarantined_in_legend((750.0, 200.0), [v]) is True
    assert authority.is_point_quarantined_in_legend((300.0, 200.0), [v]) is False


def test_compile_taxonomy_receipt():
    authority = SourceLegendSymbolTaxonomyShadowAuthority()

    v1 = authority.register_legend_viewport(
        sheet_id="A101",
        bbox=(600.0, 0.0, 800.0, 300.0),
        category=LegendCategory.WALL_TYPES,
        symbols=[
            ("W1", "External Cavity Brick", (610.0, 10.0, 630.0, 30.0)),
            ("W2", "Internal 90mm Stud Partition", (610.0, 40.0, 630.0, 60.0)),
        ],
    )

    receipt = authority.compile_taxonomy_receipt(
        document_id="DOC_LEGEND",
        revision_id="REV_1",
        source_sha256="99881122" * 8,
        viewports=[v1],
    )

    assert isinstance(receipt, PlanLegendSymbolTaxonomyReceipt)
    assert receipt.total_legend_boxes_count == 1
    assert receipt.total_registered_symbols == 2
    assert receipt.status == EvidenceResolutionStatus.CORROBORATED
    assert receipt.commercial_projection_allowed is False
    assert receipt.takeoff_eligible is False
    assert receipt.schema_version == SCHEMA_VERSION

    d = receipt.to_dict()
    assert d["document_id"] == "DOC_LEGEND"
    assert len(d["viewports"]) == 1


def test_empty_receipt_abstained():
    authority = SourceLegendSymbolTaxonomyShadowAuthority()

    receipt = authority.compile_taxonomy_receipt(
        document_id="DOC_EMPTY",
        revision_id="REV_0",
        source_sha256="00000000" * 8,
        viewports=[],
    )

    assert receipt.total_legend_boxes_count == 0
    assert receipt.status == EvidenceResolutionStatus.ABSTAINED


def test_receipt_seal_protection():
    with pytest.raises(TypeError, match="producer-owned"):
        PlanLegendSymbolTaxonomyReceipt(
            receipt_id="FORGED",
            document_id="DOC",
            revision_id="REV",
            source_sha256="abc",
            total_legend_boxes_count=0,
            total_registered_symbols=0,
            viewports=(),
            status=EvidenceResolutionStatus.ABSTAINED,
        )
