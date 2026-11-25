"""Tests for schedule-mark-to-instance lineage and dimension-basis separation (Items 14-15)."""
from __future__ import annotations

from pathlib import Path
import pytest

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_schedule_v171 import ScheduleEntry
import pb_schedule_instance_quantity_lineage_shadow as sil
from tools.audit_no_job_specific_shared_rules import audit_shared_source

_SHA_A = "1" * 64
_SHA_B = "2" * 64


def _sched_row(
    mark: str,
    *,
    width_mm: int | None = 920,
    height_mm: int | None = 2040,
    basis: str = "leaf",
    basis_source: str = "grid:leaf",
    page_id: str = "28",
    viewport_id: str = "vp-sched-1",
    obs_ids: tuple[str, ...] = ("obs-sched-1",),
    doc_id: str = "doc-1",
    rev_id: str = "rev-A",
    sha: str = _SHA_A,
    schedule_count: int | None = None,
    schedule_count_explicit: bool = False,
) -> sil.ScheduleMarkRowCandidate:
    return sil.ScheduleMarkRowCandidate(
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        schedule_page_id=page_id,
        schedule_viewport_id=viewport_id,
        row_observation_ids=obs_ids,
        type_mark=mark,
        width_mm=width_mm,
        height_mm=height_mm,
        dimension_basis=basis,
        basis_source=basis_source,
        schedule_count=schedule_count,
        schedule_count_explicit=schedule_count_explicit,
    )


def _instance(
    instance_id: str,
    *,
    mark: str | None = "D01",
    tag_obs: str | None = "obs-tag-1",
    page_id: str = "7",
    viewport_id: str = "vp-plan-main",
    doc_id: str = "doc-1",
    rev_id: str = "rev-A",
    sha: str = _SHA_A,
    plan_width_mm: int | None = None,
    plan_height_mm: int | None = None,
    plan_basis: str = "unknown",
    plan_dim_ev: str | None = None,
) -> sil.PhysicalOpeningInstanceCandidate:
    return sil.PhysicalOpeningInstanceCandidate(
        instance_id=instance_id,
        document_id=doc_id,
        revision_id=rev_id,
        source_sha256=sha,
        plan_page_id=page_id,
        plan_viewport_id=viewport_id,
        physical_evidence_ids=(f"phys-{instance_id}",),
        plan_tag_mark=mark,
        plan_tag_observation_id=tag_obs,
        plan_width_mm=plan_width_mm,
        plan_height_mm=plan_height_mm,
        plan_dimension_basis=plan_basis,
        plan_dimension_evidence_id=plan_dim_ev,
    )


def test_distinguishes_leaf_frame_rough_opening_and_installed_quantity_cleanly() -> None:
    rows = [
        _sched_row("D01", width_mm=920, height_mm=2040, basis="leaf", obs_ids=("obs-d01",)),
        _sched_row("W01", width_mm=1200, height_mm=1500, basis="frame", obs_ids=("obs-w01",)),
        _sched_row("D02", width_mm=950, height_mm=2070, basis="rough_opening", obs_ids=("obs-d02",)),
    ]
    instances = [
        _instance("inst-d01-a", mark="D01", page_id="7", viewport_id="vp-ground"),
        _instance("inst-d01-b", mark="D1", page_id="8", viewport_id="vp-level1"),
        _instance("inst-w01", mark="W01", page_id="7", viewport_id="vp-ground"),
        _instance("inst-d02", mark="D02", page_id="7", viewport_id="vp-ground"),
    ]
    report = sil.resolve_schedule_instance_quantity_lineage(
        schedule_rows=rows, physical_instances=instances,
    )
    assert report.commercial_authority_granted is False
    assert report.unmatched_schedule_marks == ()
    by_id = {rec.instance_id: rec for rec in report.installed_openings}

    # Two physical instances sharing D01/D1 each get installed_count=1 and distinct plan page/viewport lineage
    for iid, expected_page, expected_vp in (
        ("inst-d01-a", "7", "vp-ground"),
        ("inst-d01-b", "8", "vp-level1"),
    ):
        rec = by_id[iid]
        assert rec.status == EvidenceResolutionStatus.CORROBORATED
        assert rec.quantity_class == sil.CLASS_INSTALLED_OPENING_QUANTITY
        assert rec.installed_count == 1
        assert rec.canonical_mark == "D1"
        assert rec.plan_page_id == expected_page
        assert rec.plan_viewport_id == expected_vp
        assert rec.schedule_page_id == "28"
        assert rec.schedule_viewport_id == "vp-sched-1"
        assert rec.leaf_dimension is not None
        assert rec.leaf_dimension.dimension_class == sil.CLASS_LEAF_DIMENSION
        assert (rec.leaf_dimension.width_mm, rec.leaf_dimension.height_mm) == (920, 2040)
        assert rec.leaf_dimension.frame_adjustment_applied is False
        assert rec.frame_dimension is None
        assert rec.rough_opening_dimension is None
        assert rec.wall_void_deduction_eligible is False
        assert rec.commercial_authority_granted is False

    # Frame basis populates ONLY frame_dimension, never rough_opening or leaf
    w01 = by_id["inst-w01"]
    assert w01.status == EvidenceResolutionStatus.CORROBORATED
    assert w01.frame_dimension is not None
    assert w01.frame_dimension.dimension_class == sil.CLASS_FRAME_DIMENSION
    assert (w01.frame_dimension.width_mm, w01.frame_dimension.height_mm) == (1200, 1500)
    assert w01.leaf_dimension is None
    assert w01.rough_opening_dimension is None
    assert w01.wall_void_deduction_eligible is False

    # Only complete rough_opening basis marks wall_void_deduction_eligible=True
    d02 = by_id["inst-d02"]
    assert d02.status == EvidenceResolutionStatus.CORROBORATED
    assert d02.rough_opening_dimension is not None
    assert d02.rough_opening_dimension.dimension_class == sil.CLASS_ROUGH_OPENING_DIMENSION
    assert (d02.rough_opening_dimension.width_mm, d02.rough_opening_dimension.height_mm) == (950, 2070)
    assert d02.wall_void_deduction_eligible is True
    assert d02.commercial_authority_granted is False


def test_preserves_distinct_plan_frame_and_schedule_leaf_without_silent_conversion() -> None:
    rows = [_sched_row("D05", width_mm=820, height_mm=2040, basis="leaf")]
    instances = [
        _instance(
            "inst-d05",
            mark="D05",
            plan_width_mm=870,
            plan_height_mm=2080,
            plan_basis="frame",
            plan_dim_ev="plan-fig-870x2080",
        )
    ]
    report = sil.resolve_schedule_instance_quantity_lineage(
        schedule_rows=rows, physical_instances=instances,
    )
    rec = report.installed_openings[0]
    assert rec.status == EvidenceResolutionStatus.CORROBORATED
    assert rec.leaf_dimension is not None and (rec.leaf_dimension.width_mm, rec.leaf_dimension.height_mm) == (820, 2040)
    assert rec.frame_dimension is not None and (rec.frame_dimension.width_mm, rec.frame_dimension.height_mm) == (870, 2080)
    assert rec.rough_opening_dimension is None
    assert rec.wall_void_deduction_eligible is False
    assert "distinct_dimension_bases_preserved_separately" in rec.reason_codes


def test_same_basis_plan_vs_schedule_conflict_fails_closed() -> None:
    rows = [_sched_row("D05", width_mm=920, height_mm=2040, basis="rough_opening")]
    instances = [
        _instance(
            "inst-d05",
            mark="D05",
            plan_width_mm=820,
            plan_height_mm=2040,
            plan_basis="rough_opening",
            plan_dim_ev="plan-ro-820",
        )
    ]
    report = sil.resolve_schedule_instance_quantity_lineage(
        schedule_rows=rows, physical_instances=instances,
    )
    rec = report.installed_openings[0]
    assert rec.status == EvidenceResolutionStatus.CONFLICT
    assert "same_basis_dimension_conflict" in rec.reason_codes
    assert rec.rough_opening_dimension is None
    assert rec.wall_void_deduction_eligible is False


def test_cross_revision_and_sha_mismatch_never_bind() -> None:
    rows = [
        _sched_row("D01", rev_id="rev-B", sha=_SHA_A, obs_ids=("obs-rev-b",)),
        _sched_row("D02", rev_id="rev-A", sha=_SHA_B, obs_ids=("obs-sha-b",)),
    ]
    instances = [
        _instance("inst-1", mark="D01", rev_id="rev-A", sha=_SHA_A),
        _instance("inst-2", mark="D02", rev_id="rev-A", sha=_SHA_A),
    ]
    report = sil.resolve_schedule_instance_quantity_lineage(
        schedule_rows=rows, physical_instances=instances,
    )
    assert all(rec.status == EvidenceResolutionStatus.ABSTAINED for rec in report.installed_openings)
    assert all(rec.schedule_page_id is None and rec.schedule_viewport_id is None for rec in report.installed_openings)
    assert len(report.unmatched_schedule_marks) == 2
    assert all(u.installed_count == 0 for u in report.unmatched_schedule_marks)


def test_duplicate_canonical_schedule_mark_conflicts_fail_closed() -> None:
    rows = [
        _sched_row("D1", width_mm=820, height_mm=2040, page_id="28", obs_ids=("obs-1",)),
        _sched_row("D01", width_mm=820, height_mm=2040, page_id="29", obs_ids=("obs-2",)),
    ]
    instances = [_instance("inst-1", mark="D01")]
    report = sil.resolve_schedule_instance_quantity_lineage(
        schedule_rows=rows, physical_instances=instances,
    )
    rec = report.installed_openings[0]
    assert rec.status == EvidenceResolutionStatus.CONFLICT
    assert "conflicting_duplicate_schedule_mark" in rec.reason_codes
    assert rec.leaf_dimension is None


def test_unlabelled_instance_and_schedule_only_rows_never_fabricate_counts() -> None:
    rows = [
        _sched_row("D01", schedule_count=5, schedule_count_explicit=True, obs_ids=("obs-d01",)),
        _sched_row("D99", schedule_count=3, schedule_count_explicit=True, obs_ids=("obs-d99",)),
    ]
    instances = [
        _instance("inst-1", mark="D01"),
        _instance("inst-unlabelled", mark=None, tag_obs=None),
    ]
    report = sil.resolve_schedule_instance_quantity_lineage(
        schedule_rows=rows, physical_instances=instances,
    )
    by_id = {rec.instance_id: rec for rec in report.installed_openings}
    # Schedule count=5 NEVER overrides physical instance installed_count=1; discrepancy is recorded
    assert by_id["inst-1"].installed_count == 1
    assert by_id["inst-1"].schedule_declared_count_note == 5
    # Unlabelled instance stays ABSTAINED and never receives D01 or D99
    assert by_id["inst-unlabelled"].status == EvidenceResolutionStatus.ABSTAINED
    assert by_id["inst-unlabelled"].canonical_mark is None
    assert by_id["inst-unlabelled"].schedule_page_id is None
    # Schedule-only D99 produces 0 installed instances
    assert len(report.unmatched_schedule_marks) == 1
    assert report.unmatched_schedule_marks[0].canonical_mark == "D99"
    assert report.unmatched_schedule_marks[0].installed_count == 0
    # Discrepancies recorded for both D1 (declared 5 vs 1) and D99 (declared 3 vs 0)
    disc_by_mark = {d.canonical_mark: (d.schedule_declared_count, d.physical_instance_count) for d in report.count_discrepancies}
    assert disc_by_mark == {"D1": (5, 1), "D99": (3, 0)}


def test_blank_schedule_dimensions_and_schedule_entry_adapter_and_determinism() -> None:
    entry = ScheduleEntry(
        type_mark="D18",
        width_mm=None,
        height_mm=None,
        page_no=28,
        parse_source="source_grid_nested_header",
        dimension_basis="leaf",
        basis_source="grid:leaf",
    )
    row = sil.ScheduleMarkRowCandidate.from_schedule_entry(
        entry,
        document_id="doc-1",
        revision_id="rev-A",
        source_sha256=_SHA_A,
        schedule_page_id="28",
        schedule_viewport_id="vp-sched-a",
        row_observation_ids=("obs-d18",),
    )
    inst1 = _instance("inst-b", mark="D18", page_id="7", viewport_id="vp-2")
    inst2 = _instance("inst-a", mark="D18", page_id="7", viewport_id="vp-1")

    r1 = sil.resolve_schedule_instance_quantity_lineage(schedule_rows=[row], physical_instances=[inst1, inst2])
    r2 = sil.resolve_schedule_instance_quantity_lineage(schedule_rows=[row], physical_instances=[inst2, inst1])
    assert r1 == r2
    assert all(rec.status == EvidenceResolutionStatus.ABSTAINED for rec in r1.installed_openings)
    assert all("schedule_dimensions_abstained_or_blank" in rec.reason_codes for rec in r1.installed_openings)
    assert all(rec.schedule_page_id == "28" and rec.schedule_viewport_id == "vp-sched-a" for rec in r1.installed_openings)


def test_duplicate_physical_instance_id_raises_and_zero_project_literals() -> None:
    inst = _instance("dup-1", mark="D01")
    with pytest.raises(ValueError, match="duplicate_physical_opening_instance_id"):
        sil.resolve_schedule_instance_quantity_lineage(schedule_rows=[], physical_instances=[inst, inst])

    mod_path = Path(sil.__file__)
    assert audit_shared_source(mod_path.read_text(encoding="utf-8"), filename=mod_path.name) == ()
