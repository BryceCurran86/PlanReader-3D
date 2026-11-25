"""Unit tests for Item 26: RCP ceiling material/height bubble association shadow."""

from __future__ import annotations

from pathlib import Path

from pb_source_rcp_bubble_height_material_shadow import (
    RcpCeilingZonePolygon,
    RcpLineageRef,
    RcpMaterialHeightBubble,
    associate_rcp_bubbles_to_ceiling_zones_shadow,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source


def _lin(vp: str = "vp_rcp") -> RcpLineageRef:
    return RcpLineageRef(
        document_id="doc_rcp",
        revision_id="rev_01",
        source_sha256="9" * 64,
        page_id="page_09",
        viewport_id=vp,
    )


def test_preserves_distinct_heights_across_rooms_bulkhead_and_raked_zone() -> None:
    lin = _lin()
    z_main = RcpCeilingZonePolygon(
        zone_id="zone_sales",
        lineage=lin,
        polygon_pdf_pts=((0.0, 0.0), (200.0, 0.0), (200.0, 120.0), (0.0, 120.0)),
    )
    z_bulkhead = RcpCeilingZonePolygon(
        zone_id="zone_sales_bulkhead",
        lineage=lin,
        polygon_pdf_pts=((140.0, 10.0), (190.0, 10.0), (190.0, 50.0), (140.0, 50.0)),
        parent_zone_id="zone_sales",
        is_bulkhead_subzone=True,
    )
    z_prep = RcpCeilingZonePolygon(
        zone_id="zone_prep",
        lineage=lin,
        polygon_pdf_pts=((210.0, 0.0), (320.0, 0.0), (320.0, 120.0), (210.0, 120.0)),
    )
    z_entry = RcpCeilingZonePolygon(
        zone_id="zone_entry_raked",
        lineage=lin,
        polygon_pdf_pts=((0.0, 130.0), (120.0, 130.0), (120.0, 200.0), (0.0, 200.0)),
    )

    bubbles = (
        RcpMaterialHeightBubble("b_sales", lin, (50.0, 60.0), ("GRID", "CH 3000")),
        RcpMaterialHeightBubble("b_bh", lin, (165.0, 30.0), ("FPB", "2400 AFFL")),
        # Explicit leader pointing from outside into zone_prep
        RcpMaterialHeightBubble("b_prep", lin, (350.0, 60.0), ("WFPB", "2700"), leader_target_pt=(260.0, 60.0)),
        # Raked ceiling height range preserved without flattening
        RcpMaterialHeightBubble("b_raked", lin, (60.0, 165.0), ("CL02", "RAKED 2700-3400")),
        # Legend bubble MUST be excluded from plan zones
        RcpMaterialHeightBubble("b_legend", lin, (50.0, 60.0), ("CL01", "2400"), in_legend_region=True),
        # Cross-viewport bubble MUST be rejected
        RcpMaterialHeightBubble("b_other_vp", _lin(vp="vp_inset"), (50.0, 60.0), ("CL01", "2500")),
    )

    report = associate_rcp_bubbles_to_ceiling_zones_shadow((z_main, z_bulkhead, z_prep, z_entry), bubbles)
    by_zone = {a.zone_id: a for a in report.associations}

    assert by_zone["zone_sales"].resolved is True
    assert by_zone["zone_sales"].material_code == "GRID"
    assert by_zone["zone_sales"].height_mm == 3000

    assert by_zone["zone_sales_bulkhead"].resolved is True
    assert by_zone["zone_sales_bulkhead"].material_code == "FPB"
    assert by_zone["zone_sales_bulkhead"].height_mm == 2400

    assert by_zone["zone_prep"].resolved is True
    assert by_zone["zone_prep"].material_code == "WFPB"
    assert by_zone["zone_prep"].height_mm == 2700
    assert by_zone["zone_prep"].ownership_mode == "explicit_leader"

    assert by_zone["zone_entry_raked"].resolved is True
    assert by_zone["zone_entry_raked"].height_mm is None
    assert by_zone["zone_entry_raked"].raked_height_range_mm == (2700, 3400)

    # All three distinct flat heights strictly preserved (no averaging/flattening!)
    assert report.distinct_heights_preserved_mm == (2400, 2700, 3000)
    assert report.explicit_distinct_heights_preserved is True
    assert report.cross_zone_height_flattening_forbidden is True
    assert report.commercial_authority_granted is False
    assert report.rejection_reasons_by_bubble["b_legend"] == "legend_bubble_excluded_from_plan_zones"
    assert report.rejection_reasons_by_bubble["b_other_vp"] == "cross_viewport_or_lineage_bubble_rejected"


def test_conflicting_heights_in_same_undivided_zone_and_outside_proximity_abstain() -> None:
    lin = _lin()
    z_one = RcpCeilingZonePolygon(
        zone_id="zone_office",
        lineage=lin,
        polygon_pdf_pts=((0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)),
    )
    bubbles = (
        RcpMaterialHeightBubble("b1", lin, (25.0, 50.0), ("FPB", "2700")),
        RcpMaterialHeightBubble("b2", lin, (75.0, 50.0), ("FPB", "3000")),
        RcpMaterialHeightBubble("b_outside", lin, (125.0, 50.0), ("FPB", "2700")),
    )
    report = associate_rcp_bubbles_to_ceiling_zones_shadow((z_one,), bubbles)
    assoc = report.associations[0]
    assert assoc.resolved is False
    assert assoc.abstained is True
    assert assoc.height_mm is None
    assert "conflicting_heights_same_undivided_zone" in assoc.blocking_reasons
    assert report.rejection_reasons_by_bubble["b_outside"] == "unowned_outside_zone_proximity_forbidden"


def test_shared_source_audit_is_clean() -> None:
    p = Path(__file__).resolve().parent.parent / "pb_source_rcp_bubble_height_material_shadow.py"
    assert audit_shared_source(p.read_text(encoding="utf-8"), filename=p.name) == ()
