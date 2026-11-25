"""Unit tests for Item 21: external glazing schedule vs aperture & elevation reconciliation."""

from __future__ import annotations

from pathlib import Path

from pb_source_external_glazing_reconciliation_shadow import (
    GlazingElevationWitness,
    GlazingLineageRef,
    GlazingScheduleRowWitness,
    PhysicalGlazingApertureWitness,
    reconcile_external_glazing_evidence_shadow,
)
from tools.audit_no_job_specific_shared_rules import audit_shared_source


def _lin(page: str = "page_01", vp: str = "vp_plan", rev: str = "rev_a") -> GlazingLineageRef:
    return GlazingLineageRef(
        document_id="doc_arch",
        revision_id=rev,
        source_sha256="d" * 64,
        page_id=page,
        viewport_id=vp,
    )


def _aperture(
    *,
    opening_id: str = "open_w01",
    mark: str | None = "W01",
    span_pts: float = 51.02,  # ~1800 mm at 35.2778 mm/pt
    mm_per_pt: float | None = 35.2778,
    host_wall_id: str = "wall_ext_01",
    is_corner_leg: bool = False,
    corner_total_span_mm: float | None = None,
) -> PhysicalGlazingApertureWitness:
    return PhysicalGlazingApertureWitness(
        opening_id=opening_id,
        lineage=_lin(),
        host_wall_id=host_wall_id,
        span_pts=span_pts,
        calibrated_mm_per_pt=mm_per_pt,
        printed_mark=mark,
        is_exterior_opening=True,
        is_corner_leg=is_corner_leg,
        corner_total_span_mm=corner_total_span_mm,
    )


def test_reconciles_matching_schedule_elevation_and_physical_aperture() -> None:
    sched = GlazingScheduleRowWitness(
        row_id="sched_w01",
        lineage=_lin(page="page_20", vp="vp_sched"),
        mark="W01",
        width_mm=1800.0,
        height_mm=1500.0,
        dimension_basis="frame_dimension",
    )
    elev = GlazingElevationWitness(
        elevation_witness_id="elev_north_w01",
        lineage=_lin(page="page_12", vp="vp_elev_n"),
        linked_mark="W01",
        linked_opening_id="open_w01",
        width_mm=1800.0,
        height_mm=1500.0,
        sill_height_mm=900.0,
        head_height_mm=2400.0,
        dimension_basis="frame_dimension",
    )
    res = reconcile_external_glazing_evidence_shadow(
        _aperture(), schedule_rows=(sched,), elevation_witnesses=(elev,)
    )
    assert res.reconciled is True
    assert res.abstained is False
    assert res.resolved_width_mm == 1800.0
    assert res.resolved_height_mm == 1500.0
    assert res.resolved_basis == "frame_dimension"
    assert res.aperture_geometry_used_as_area is False
    assert res.commercial_authority_granted is False
    assert res.blocking_reasons == ()


def test_conflicts_basis_mismatch_and_measure_on_site_fail_closed() -> None:
    # 1. Schedule width disagrees with physical aperture (1800 mm vs 2400 mm)
    sched_wide = GlazingScheduleRowWitness(
        row_id="sched_wide",
        lineage=_lin(page="page_20", vp="vp_sched"),
        mark="W01",
        width_mm=2400.0,
        height_mm=1500.0,
        dimension_basis="frame_dimension",
    )
    res_ap_conflict = reconcile_external_glazing_evidence_shadow(
        _aperture(), schedule_rows=(sched_wide,)
    )
    assert res_ap_conflict.abstained is True
    assert "schedule_vs_physical_aperture_width_conflict" in res_ap_conflict.blocking_reasons

    # 2. Schedule vs elevation height conflict (1500 vs 2100)
    sched_ok = GlazingScheduleRowWitness(
        row_id="sched_w01",
        lineage=_lin(page="page_20", vp="vp_sched"),
        mark="W01",
        width_mm=1800.0,
        height_mm=1500.0,
        dimension_basis="frame_dimension",
    )
    elev_conflict = GlazingElevationWitness(
        elevation_witness_id="elev_bad_h",
        lineage=_lin(page="page_12", vp="vp_elev"),
        linked_mark="W01",
        linked_opening_id="open_w01",
        width_mm=1800.0,
        height_mm=2100.0,
        dimension_basis="frame_dimension",
    )
    res_h = reconcile_external_glazing_evidence_shadow(
        _aperture(), schedule_rows=(sched_ok,), elevation_witnesses=(elev_conflict,)
    )
    assert res_h.abstained is True
    assert "schedule_vs_elevation_height_conflict" in res_h.blocking_reasons

    # 3. Basis mismatch (frame_dimension vs glass_sight_size) must NOT silently equate
    elev_sight = GlazingElevationWitness(
        elevation_witness_id="elev_sight",
        lineage=_lin(page="page_12", vp="vp_elev"),
        linked_mark="W01",
        linked_opening_id="open_w01",
        width_mm=1800.0,
        height_mm=1500.0,
        dimension_basis="glass_sight_size",
    )
    res_basis = reconcile_external_glazing_evidence_shadow(
        _aperture(), schedule_rows=(sched_ok,), elevation_witnesses=(elev_sight,)
    )
    assert res_basis.abstained is True
    assert "glazing_dimension_basis_mismatch" in res_basis.blocking_reasons

    # 4. Measure on site disclaimer abstains cleanly
    sched_mos = GlazingScheduleRowWitness(
        row_id="sched_mos",
        lineage=_lin(page="page_20", vp="vp_sched"),
        mark="W01",
        width_mm=1800.0,
        height_mm=1500.0,
        dimension_basis="frame_dimension",
        notes="Custom front glazing - measure on site",
    )
    res_mos = reconcile_external_glazing_evidence_shadow(
        _aperture(), schedule_rows=(sched_mos,)
    )
    assert res_mos.abstained is True
    assert "glazing_measure_on_site_abstention" in res_mos.blocking_reasons

    # 5. Aperture geometry alone cannot invent glazing dimensions
    res_bare = reconcile_external_glazing_evidence_shadow(_aperture())
    assert res_bare.abstained is True
    assert "aperture_geometry_alone_cannot_supply_glazing_dimensions" in res_bare.blocking_reasons


def test_shared_source_audit_is_clean() -> None:
    p = Path(__file__).resolve().parent.parent / "pb_source_external_glazing_reconciliation_shadow.py"
    assert audit_shared_source(p.read_text(encoding="utf-8"), filename=p.name) == ()
