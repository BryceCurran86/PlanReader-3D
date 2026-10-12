"""Generic project source-closed handoff orchestration tests."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import fitz
import pytest

from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import seal_source_closed_run
from pb_source_floor_plan_page_scope import (
    SourceFloorPlanPageDecision,
    SourceFloorPlanPageScope,
)
from tools import run_source_closed_project_handoff as handoff


def _quantity(quantity_id: str, family: str) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=quantity_id,
        family=family,
        semantic_key=f"{family}:entity-1",
        value=1.0,
        unit="m2" if family != "opening_count" else "ea",
        input_entity_ids=(f"{family}-entity-1",),
        formula="test",
        formula_version="1",
        evidence_ids=(f"ev-{quantity_id}",),
        authority="documented_dimension",
        status="firm",
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        reason_codes=(),
        metadata={},
    )


def _run(
    *,
    project_id: str,
    source_sha256: str,
    family: str,
    quantity_id: str,
):
    quantity = _quantity(quantity_id, family)
    trace = CommercialTakeoffSourceTrace(
        workspace_id=1,
        project_id=project_id,
        document_id="doc-1",
        source_sha256=source_sha256,
        source_page="1",
        viewport_id="vp-1",
        revision_id="rev-1",
        current_revision_id="rev-1",
        evidence_ids=quantity.evidence_ids,
        canonical_entity_ids=quantity.input_entity_ids,
    )
    return seal_source_closed_run(
        (quantity,),
        project_id=project_id,
        traces_by_quantity_id={quantity.quantity_id: trace},
    )


def _three_page_pdf(path) -> None:
    doc = fitz.open()
    try:
        for _ in range(3):
            doc.new_page(width=200.0, height=100.0)
        doc.save(path)
    finally:
        doc.close()


def test_source_topology_pages_reuses_production_bound_title_scope(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    _three_page_pdf(pdf)
    scope = SourceFloorPlanPageScope(
        decisions=(
            SourceFloorPlanPageDecision(
                0,
                "not_floor_plan",
                "not_floor_plan_bound_title",
                "COVER SHEET",
                (),
            ),
            SourceFloorPlanPageDecision(
                1,
                "floor_plan",
                "floor_plan_bound_title",
                "FLOOR PLAN",
                ("floor_plan",),
            ),
            SourceFloorPlanPageDecision(
                2,
                "not_floor_plan",
                "not_floor_plan_bound_title",
                "ELEVATIONS",
                ("elevation",),
            ),
        ),
        selected_page_indices=(0, 1, 2),
        floor_plan_page_indices=(1,),
        other_drawing_page_indices=(0, 2),
    )
    monkeypatch.setattr(
        handoff,
        "source_floor_plan_topology_scope",
        lambda path, selected: scope,
    )

    topology, support, page_count = handoff._source_page_scopes(pdf)

    assert page_count == 3
    assert topology == (1,)
    # COVER SHEET and ELEVATIONS remain general evidence but are not
    # horizontal room-area support plans.
    assert support == ()


def test_source_topology_pages_preserves_full_scope_when_unrestricted(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    _three_page_pdf(pdf)
    scope = SourceFloorPlanPageScope(
        decisions=(
            SourceFloorPlanPageDecision(
                0,
                "unproven",
                "floor_plan_page_unproven",
            ),
            SourceFloorPlanPageDecision(
                1,
                "floor_plan",
                "floor_plan_bound_title",
                "FLOOR PLAN",
                ("floor_plan",),
            ),
            SourceFloorPlanPageDecision(
                2,
                "unproven",
                "floor_plan_page_unproven",
            ),
        ),
        selected_page_indices=(0, 1, 2),
        floor_plan_page_indices=(1,),
        other_drawing_page_indices=(),
    )
    assert scope.topology_page_indices() is None
    monkeypatch.setattr(
        handoff,
        "source_floor_plan_topology_scope",
        lambda path, selected: scope,
    )

    topology, support, page_count = handoff._source_page_scopes(pdf)

    assert page_count == 3
    assert topology == (0, 1, 2)
    assert support == ()


def test_project_handoff_combines_only_available_source_closed_families(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    source_sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    project_id = "project-a"

    floor_q = _quantity("q-floor", "floor_area")
    floor_finish_q = _quantity("q-floor-finish", "floor_finish_area")
    opening_q = _quantity("q-opening", "opening_area")
    count_q = _quantity("q-count", "opening_count")
    claim = SimpleNamespace(
        status=SimpleNamespace(value="corroborated"),
        reason_codes=("resolved",),
        canonical_walls=(1, 2),
        canonical_openings=(1,),
        canonical_rooms=(1,),
        canonical_floors=(1,),
        canonical_spaces=(1,),
        room_area_quantity_evidence=(),
        floor_finish_quantity_evidence=(floor_finish_q,),
        opening_quantity_evidence=(opening_q,),
        opening_count_quantity_evidence=(count_q,),
    )
    ceiling_result = SimpleNamespace()
    ceiling_q = _quantity("q-ceiling", "ceiling_lining")

    monkeypatch.setattr(handoff, "_source_page_scopes", lambda path: ((0,), (), 1))
    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        lambda *args, **kwargs: claim,
    )
    monkeypatch.setattr(
        handoff,
        "collect_live_ceiling_lining_claims",
        lambda *args, **kwargs: ceiling_result,
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_ceiling_area_quantities",
        lambda result: (ceiling_q,),
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_floor_area_quantities",
        lambda claim: (floor_q,),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_floor_area_run",
        lambda *args, **kwargs: _run(
            project_id=project_id,
            source_sha256=source_sha,
            family="floor_area",
            quantity_id="q-floor",
        ),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_floor_finish_area_run",
        lambda *args, **kwargs: _run(
            project_id=project_id,
            source_sha256=source_sha,
            family="floor_finish_area",
            quantity_id="q-floor-finish",
        ),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_opening_area_claim_run",
        lambda *args, **kwargs: _run(
            project_id=project_id,
            source_sha256=source_sha,
            family="opening_area",
            quantity_id="q-opening",
        ),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_opening_count_run",
        lambda *args, **kwargs: _run(
            project_id=project_id,
            source_sha256=source_sha,
            family="opening_count",
            quantity_id="q-count",
        ),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_ceiling_area_run",
        lambda *args, **kwargs: _run(
            project_id=project_id,
            source_sha256=source_sha,
            family="ceiling_lining",
            quantity_id="q-ceiling",
        ),
    )

    output = tmp_path / "out"
    summary = handoff.generate_project_handoff(
        pdf_path=pdf,
        project_id=project_id,
        workspace_id=1,
        output_dir=output,
    )

    assert summary["status"] == "sealed"
    assert summary["complete_project_handoff"] is True
    assert summary["source_sha256"] == source_sha
    assert summary["topology_pages"] == [1]
    assert summary["topology_mode"] == "live_authority_all_pages_fallback"
    assert summary["family_counts"] == {
        "floor_area": 1,
        "floor_finish_area": 1,
        "opening_area": 1,
        "opening_count": 1,
        "ceiling_area": 1,
    }
    assert summary["combined_quantity_count"] == 5
    assert (output / f"{project_id}.json").is_file()
    assert (output / "production_summary.json").is_file()
    assert sorted((output / "family_runs").glob("*.sealed.json"))


def test_project_handoff_without_vector_hints_delegates_topology_to_live_authority(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda path: ((0, 1, 2), (), 3))

    claim = SimpleNamespace(
        status=SimpleNamespace(value="abstained"),
        reason_codes=("live-authority-unavailable",),
        canonical_walls=(),
        canonical_openings=(),
        canonical_rooms=(),
        canonical_floors=(),
        canonical_spaces=(),
        room_area_quantity_evidence=(),
        opening_quantity_evidence=(),
        opening_count_quantity_evidence=(),
    )
    seen = {}

    def _collect(*args, **kwargs):
        seen.update(kwargs)
        return claim

    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        _collect,
    )
    monkeypatch.setattr(
        handoff,
        "collect_live_ceiling_lining_claims",
        lambda *args, **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_ceiling_area_quantities",
        lambda result: (),
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_floor_area_quantities",
        lambda claim: (),
    )

    summary = handoff.generate_project_handoff(
        pdf_path=pdf,
        project_id="project-a",
        workspace_id=1,
        output_dir=tmp_path / "out",
    )

    assert seen["pages"] == (0, 1, 2)
    assert seen["topology_pages"] is None
    assert seen["room_area_support_pages"] is None
    assert summary["status"] == "no_sealable_quantities"
    assert summary["topology_pages"] == [1, 2, 3]
    assert summary["room_area_support_pages"] == []
    assert summary["topology_mode"] == "live_authority_all_pages_fallback"
    assert summary["claim_reason_codes"] == ["live-authority-unavailable"]
    assert summary["combined_run_file"] is None


def test_project_handoff_keeps_full_surface_evidence_but_scopes_room_support(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    monkeypatch.setattr(
        handoff,
        "_source_page_scopes",
        lambda path: ((0,), (2,), 5),
    )

    claim = SimpleNamespace(
        status=SimpleNamespace(value="abstained"),
        reason_codes=("resolved-scope",),
        canonical_walls=(),
        canonical_openings=(),
        canonical_rooms=(),
        canonical_floors=(),
        canonical_spaces=(),
        room_area_quantity_evidence=(),
        opening_quantity_evidence=(),
        opening_count_quantity_evidence=(),
    )
    seen = {}
    ceiling_seen = {}

    def _collect(*args, **kwargs):
        seen.update(kwargs)
        return claim

    def _collect_ceiling(*args, **kwargs):
        ceiling_seen.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        _collect,
    )
    monkeypatch.setattr(
        handoff,
        "collect_live_ceiling_lining_claims",
        _collect_ceiling,
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_ceiling_area_quantities",
        lambda result: (),
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_floor_area_quantities",
        lambda claim: (),
    )

    summary = handoff.generate_project_handoff(
        pdf_path=pdf,
        project_id="project-a",
        workspace_id=1,
        output_dir=tmp_path / "out",
    )

    assert seen["pages"] == (0, 1, 2, 3, 4)
    assert seen["topology_pages"] == (0,)
    assert seen["room_area_support_pages"] == (2,)
    assert ceiling_seen["pages"] == (0, 1, 2, 3, 4)
    assert ceiling_seen["topology_pages"] == (0,)
    assert summary["topology_pages"] == [1]
    assert summary["room_area_support_pages"] == [3]
    assert summary["execution_pages"] == [1, 2, 3, 4, 5]
    assert summary["topology_mode"] == "source_classified_scope"


def test_surface_family_group_scopes_geometry_but_keeps_full_semantic_evidence(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    monkeypatch.setattr(
        handoff,
        "_source_page_scopes",
        lambda path: ((0,), (2,), 5),
    )

    claim = SimpleNamespace(
        status=SimpleNamespace(value="abstained"),
        reason_codes=("resolved-scope",),
        canonical_walls=(),
        canonical_openings=(),
        canonical_rooms=(),
        canonical_floors=(),
        canonical_spaces=(),
        room_area_quantity_evidence=(),
        floor_finish_quantity_evidence=(),
        opening_quantity_evidence=(),
        opening_count_quantity_evidence=(),
    )
    seen = {}
    ceiling_seen = {}

    def _collect(*args, **kwargs):
        seen.update(kwargs)
        return claim

    def _collect_ceiling(*args, **kwargs):
        ceiling_seen.update(kwargs)
        return SimpleNamespace()

    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        _collect,
    )
    monkeypatch.setattr(
        handoff,
        "collect_live_ceiling_lining_claims",
        _collect_ceiling,
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_ceiling_area_quantities",
        lambda result: (),
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_floor_area_quantities",
        lambda claim: (),
    )

    summary = handoff.generate_project_handoff(
        pdf_path=pdf,
        project_id="project-a",
        workspace_id=1,
        output_dir=tmp_path / "out",
        family_group="surfaces",
    )

    assert seen["pages"] == (0, 2)
    assert seen["topology_pages"] == (0,)
    assert seen["room_area_support_pages"] == (2,)
    assert seen["surface_semantic_pages"] == (0, 1, 2, 3, 4)
    assert ceiling_seen["pages"] == (0, 1, 2, 3, 4)
    assert summary["execution_pages"] == [1, 3]
    assert summary["semantic_execution_pages"] == [1, 2, 3, 4, 5]
    assert summary["topology_mode"] == "source_classified_scope"


def test_project_handoff_rejects_family_run_from_different_source(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    floor_q = _quantity("q-floor", "floor_area")
    claim = SimpleNamespace(
        status=SimpleNamespace(value="corroborated"),
        reason_codes=(),
        canonical_walls=(),
        canonical_openings=(),
        canonical_rooms=(1,),
        canonical_floors=(1,),
        canonical_spaces=(1,),
        room_area_quantity_evidence=(),
        opening_quantity_evidence=(),
        opening_count_quantity_evidence=(),
    )

    monkeypatch.setattr(handoff, "_source_page_scopes", lambda path: ((0,), (), 1))
    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        lambda *args, **kwargs: claim,
    )
    monkeypatch.setattr(
        handoff,
        "collect_live_ceiling_lining_claims",
        lambda *args, **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_ceiling_area_quantities",
        lambda result: (),
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_floor_area_quantities",
        lambda claim: (floor_q,),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_floor_area_run",
        lambda *args, **kwargs: _run(
            project_id="project-a",
            source_sha256="f" * 64,
            family="floor_area",
            quantity_id="q-floor",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="conflicting source SHA envelope",
    ):
        handoff.generate_project_handoff(
            pdf_path=pdf,
            project_id="project-a",
            workspace_id=1,
            output_dir=tmp_path / "out",
        )



def test_project_handoff_combined_filename_matches_suite_scoreboard_contract(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    source_sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    project_id = "project-a"
    floor_q = _quantity("q-floor", "floor_area")
    claim = SimpleNamespace(
        status=SimpleNamespace(value="corroborated"),
        reason_codes=(),
        canonical_walls=(),
        canonical_openings=(),
        canonical_rooms=(1,),
        canonical_floors=(1,),
        canonical_spaces=(1,),
        room_area_quantity_evidence=(),
        opening_quantity_evidence=(),
        opening_count_quantity_evidence=(),
    )

    monkeypatch.setattr(handoff, "_source_page_scopes", lambda path: ((0,), (), 1))
    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        lambda *args, **kwargs: claim,
    )
    monkeypatch.setattr(
        handoff,
        "collect_live_ceiling_lining_claims",
        lambda *args, **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_ceiling_area_quantities",
        lambda result: (),
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_floor_area_quantities",
        lambda claim: (floor_q,),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_floor_area_run",
        lambda *args, **kwargs: _run(
            project_id=project_id,
            source_sha256=source_sha,
            family="floor_area",
            quantity_id="q-floor",
        ),
    )

    output = tmp_path / "sealed"
    summary = handoff.generate_project_handoff(
        pdf_path=pdf,
        project_id=project_id,
        workspace_id=1,
        output_dir=output,
    )

    assert summary["combined_run_file"] == str(output / f"{project_id}.json")
    assert (output / f"{project_id}.json").is_file()
    assert not (output / f"{project_id}.sealed.json").exists()


def test_project_handoff_persists_production_failure_summary_before_reraise(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    output = tmp_path / "out"

    monkeypatch.setattr(handoff, "_source_page_scopes", lambda path: ((0, 1), (), 2))

    def _fail(*args, **kwargs):
        raise ValueError("raster opening primitive count exceeds safety bound")

    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        _fail,
    )

    with pytest.raises(
        ValueError,
        match="raster opening primitive count exceeds safety bound",
    ):
        handoff.generate_project_handoff(
            pdf_path=pdf,
            project_id="project-a",
            workspace_id=1,
            output_dir=output,
        )

    summary = __import__("json").loads(
        (output / "production_summary.json").read_text(encoding="utf-8")
    )
    assert summary["status"] == "production_failed"
    assert summary["topology_mode"] == "live_authority_all_pages_fallback"
    assert summary["production_error_type"] == "ValueError"
    assert summary["production_error_message"] == (
        "raster opening primitive count exceeds safety bound"
    )
    assert summary["claim_reason_codes"] == [
        "production_extraction_error:ValueError"
    ]
    assert summary["combined_run_file"] is None
    attempt = __import__("json").loads(
        (output / "source_attempt_preflight.json").read_text(encoding="utf-8")
    )
    assert attempt["status"] == "SOURCE_INPUT_RECORDED_UNSEALED"
    assert attempt["benchmark_score_granted"] is False
    assert attempt["complete_source_coverage_proven"] is False
    assert attempt["source_page_count"] == 2
    assert attempt["execution_page_numbers"] == [1, 2]
    assert attempt["sealed_run_file"] is None



def test_project_handoff_does_not_seal_upstream_room_area_as_final_family(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    upstream_room = _quantity("q-room", "room_area")
    claim = SimpleNamespace(
        status=SimpleNamespace(value="corroborated"),
        reason_codes=(),
        canonical_walls=(),
        canonical_openings=(),
        canonical_rooms=(1,),
        canonical_floors=(1,),
        canonical_spaces=(1,),
        room_area_quantity_evidence=(upstream_room,),
        opening_quantity_evidence=(),
        opening_count_quantity_evidence=(),
    )
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda path: ((0,), (), 1))
    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        lambda *args, **kwargs: claim,
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_floor_area_quantities",
        lambda claim: (),
    )
    monkeypatch.setattr(
        handoff,
        "collect_live_ceiling_lining_claims",
        lambda *args, **kwargs: SimpleNamespace(),
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_ceiling_area_quantities",
        lambda result: (),
    )

    summary = handoff.generate_project_handoff(
        pdf_path=pdf,
        project_id="project-a",
        workspace_id=1,
        output_dir=tmp_path / "out",
    )

    assert summary["family_counts"]["floor_area"] == 0
    assert "room_area" not in summary["family_counts"]
    assert summary["combined_quantity_count"] == 0
    assert summary["status"] == "no_sealable_quantities"



def test_core_family_group_uses_only_proven_topology_scope_and_skips_surfaces(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    source_sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    project_id = "project-core"

    opening_q = _quantity("q-opening", "opening_area")
    count_q = _quantity("q-count", "opening_count")
    claim = SimpleNamespace(
        status=SimpleNamespace(value="corroborated"),
        reason_codes=("core-resolved",),
        canonical_walls=(1,),
        canonical_openings=(1,),
        canonical_rooms=(),
        canonical_floors=(),
        canonical_spaces=(),
        room_area_quantity_evidence=(),
        opening_quantity_evidence=(opening_q,),
        opening_count_quantity_evidence=(count_q,),
    )
    seen = {}

    monkeypatch.setattr(
        handoff,
        "_source_page_scopes",
        lambda path: ((1,), (0, 2), 3),
    )

    def _collect(*args, **kwargs):
        seen.update(kwargs)
        return claim

    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        _collect,
    )

    def _surface_forbidden(*args, **kwargs):
        raise AssertionError("core handoff must not invoke surface publication")

    monkeypatch.setattr(
        handoff,
        "publish_live_floor_area_quantities",
        _surface_forbidden,
    )
    monkeypatch.setattr(
        handoff,
        "collect_live_ceiling_lining_claims",
        _surface_forbidden,
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_ceiling_area_quantities",
        _surface_forbidden,
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_opening_area_claim_run",
        lambda *args, **kwargs: _run(
            project_id=project_id,
            source_sha256=source_sha,
            family="opening_area",
            quantity_id="q-opening",
        ),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_opening_count_run",
        lambda *args, **kwargs: _run(
            project_id=project_id,
            source_sha256=source_sha,
            family="opening_count",
            quantity_id="q-count",
        ),
    )

    output = tmp_path / "out"
    summary = handoff.generate_project_handoff(
        pdf_path=pdf,
        project_id=project_id,
        workspace_id=1,
        output_dir=output,
        family_group="core",
    )

    assert seen["pages"] == (1,)
    assert seen["topology_pages"] == (1,)
    assert seen["room_area_support_pages"] is None
    assert summary["family_group"] == "core"
    assert summary["complete_project_handoff"] is False
    assert summary["execution_pages"] == [2]
    assert summary["family_counts"] == {
        "floor_area": 0,
        "floor_finish_area": 0,
        "opening_area": 1,
        "opening_count": 1,
        "ceiling_area": 0,
    }
    assert summary["combined_quantity_count"] == 2
    assert summary["status"] == "sealed"
    assert summary["combined_run_file"] == str(
        output / f"{project_id}.core.json"
    )
    assert (output / f"{project_id}.core.json").is_file()
    assert not (output / f"{project_id}.json").exists()


def test_invalid_family_group_fails_before_source_scope_resolution(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")

    def _unexpected(*args, **kwargs):
        raise AssertionError("source scope must not run for invalid family group")

    monkeypatch.setattr(handoff, "_source_page_scopes", _unexpected)

    with pytest.raises(
        ValueError,
        match="family_group must be one of",
    ):
        handoff.generate_project_handoff(
            pdf_path=pdf,
            project_id="project-a",
            workspace_id=1,
            output_dir=tmp_path / "out",
            family_group="not-a-group",
        )


@pytest.mark.parametrize("existing_artifact", [
    "project-a.json",
    "project-a.core.json",
    "project-a.surfaces.json",
    "family_runs/floor_area.sealed.json",
    "family_runs/floor_finish_area.sealed.json",
    "family_runs/opening_area.sealed.json",
    "family_runs/opening_count.sealed.json",
    "family_runs/ceiling_area.sealed.json",
    "family_runs/wall_finish_area.sealed.json",
    "project-a.future-family.json",
])
def test_old_signed_customer_handoff_cannot_survive_failed_rerun(
    tmp_path, monkeypatch, existing_artifact,
):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"one original source")
    output = tmp_path / "shared-output"
    signed = output / existing_artifact
    signed.parent.mkdir(parents=True, exist_ok=True)
    signed.write_bytes(b"prior authentic sealed output")
    monkeypatch.setattr(
        handoff, "_source_page_scopes",
        lambda *_: pytest.fail("old seal must be rejected before source production"),
    )
    with pytest.raises(FileExistsError, match="existing sealed handoff artifact"):
        handoff.generate_project_handoff(
            pdf_path=source, project_id="project-a", workspace_id=1,
            output_dir=output,
        )
    assert signed.read_bytes() == b"prior authentic sealed output"
    assert not (output / "source_attempt_preflight.json").exists()
    assert not (output / "production_summary.json").exists()


def test_broken_symlink_seal_is_not_treated_as_safe_empty_output(tmp_path, monkeypatch):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"one original source")
    output = tmp_path / "shared-output"
    output.mkdir()
    (output / "project-a.json").symlink_to(tmp_path / "missing-signed-receipt.json")
    monkeypatch.setattr(
        handoff, "_source_page_scopes",
        lambda *_: pytest.fail("symlink is not clean output"),
    )
    with pytest.raises(FileExistsError, match="existing sealed handoff artifact"):
        handoff.generate_project_handoff(
            pdf_path=source, project_id="project-a", workspace_id=1,
            output_dir=output,
        )


def test_preflight_only_failed_attempt_may_reuse_output_without_signed_evidence(
    tmp_path, monkeypatch,
):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"unsealed input")
    output = tmp_path / "shared-output"
    output.mkdir()
    (output / "source_attempt_preflight.json").write_text(
        '{"status":"OLD_UNSEALED_ATTEMPT"}', encoding="utf-8",
    )
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _: ((0,), (), 1))

    def _fail(*args, **kwargs):
        raise RuntimeError("source producer unavailable")

    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", _fail)
    with pytest.raises(RuntimeError, match="source producer unavailable"):
        handoff.generate_project_handoff(
            pdf_path=source, project_id="project-a", workspace_id=1,
            output_dir=output,
        )
    import json
    preflight = json.loads(
        (output / "source_attempt_preflight.json").read_text(encoding="utf-8")
    )
    summary = json.loads(
        (output / "production_summary.json").read_text(encoding="utf-8")
    )
    assert preflight["status"] == "SOURCE_INPUT_RECORDED_UNSEALED"
    assert preflight["benchmark_score_granted"] is False
    assert summary["status"] == "production_failed"
    assert not (output / "project-a.json").exists()


def test_interrupted_new_source_attempt_writes_unsealed_summary_first(tmp_path, monkeypatch):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"source-pdf-payload")
    output = tmp_path / "handoff-output"
    output.mkdir()
    # An earlier incomplete run left misleading summary metadata but no
    # actual signed files. It must not be carried into a newly killed run.
    (output / "production_summary.json").write_text(
        '{"status":"sealed","combined_run_file":"missing-old-run.json"}',
        encoding="utf-8",
    )
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _: ((0,), (), 1))

    def _interrupted(*args, **kwargs):
        raise KeyboardInterrupt("external interruption during producer")

    monkeypatch.setattr(
        handoff, "collect_live_physical_net_wall_claim", _interrupted,
    )
    with pytest.raises(KeyboardInterrupt, match="external interruption"):
        handoff.generate_project_handoff(
            pdf_path=source, project_id="project-a", workspace_id=1,
            output_dir=output,
        )
    import json
    summary = json.loads(
        (output / "production_summary.json").read_text(encoding="utf-8")
    )
    assert summary["status"] == "source_attempt_recorded_unsealed"
    assert summary["benchmark_score_granted"] is False
    assert summary["frozen_v2_reconciliation_complete"] is False
    assert summary["combined_run_file"] is None
    assert not (output / "project-a.json").exists()


@pytest.mark.parametrize("linked_name", [
    "source_attempt_preflight.json",
    "production_summary.json",
])
def test_unsealed_preflight_and_summary_symlinks_cannot_modify_original_pdf(
    tmp_path, monkeypatch, linked_name,
):
    source = tmp_path / "original.pdf"
    original_bytes = b"original immutable source bytes"
    source.write_bytes(original_bytes)
    output = tmp_path / "handoff-output"
    output.mkdir()
    poisoned = output / linked_name
    poisoned.symlink_to(source)
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _: ((0,), (), 1))

    def _failed_source(*args, **kwargs):
        raise RuntimeError("source production did not complete")

    monkeypatch.setattr(
        handoff, "collect_live_physical_net_wall_claim", _failed_source,
    )
    with pytest.raises(RuntimeError, match="source production did not complete"):
        handoff.generate_project_handoff(
            pdf_path=source, project_id="project-a", workspace_id=1,
            output_dir=output,
        )
    import json
    assert source.read_bytes() == original_bytes
    assert not poisoned.is_symlink()
    assert json.loads(
        (output / "source_attempt_preflight.json").read_text(encoding="utf-8")
    )["benchmark_score_granted"] is False
    assert json.loads(
        (output / "production_summary.json").read_text(encoding="utf-8")
    )["status"] == "production_failed"


def test_failed_atomic_summary_replacement_preserves_prior_summary_and_no_temp(
    tmp_path, monkeypatch,
):
    destination = tmp_path / "production_summary.json"
    destination.write_text('{"status":"old-unsealed"}', encoding="utf-8")

    def _cannot_replace(*args, **kwargs):
        raise OSError("simulated filesystem interruption")

    monkeypatch.setattr(handoff.os, "replace", _cannot_replace)
    with pytest.raises(OSError, match="simulated filesystem interruption"):
        handoff._write_json(destination, {"status": "new-unsealed"})
    assert destination.read_text(encoding="utf-8") == '{"status":"old-unsealed"}'
    assert sorted(path.name for path in tmp_path.iterdir()) == [
        "production_summary.json",
    ]


def test_signed_family_is_atomic_and_has_a_complete_source_envelope(tmp_path):
    import json
    run = _run(
        project_id="source-project", source_sha256="a" * 64,
        family="opening_area", quantity_id="q-atomic-opening",
    )
    path = handoff._write_run(tmp_path, "opening_area", run)
    assert path.is_file()
    assert json.loads(path.read_text(encoding="utf-8")) == json.loads(run.to_json())
    assert not list(path.parent.glob("*.tmp"))


@pytest.mark.parametrize("artifact_kind", ["family", "combined"])
def test_interrupted_signed_artifact_publish_never_leaves_truncated_customer_row(
    tmp_path, monkeypatch, artifact_kind,
):
    output = tmp_path / "handoff"
    destination = (
        output / "family_runs" / "opening_area.sealed.json"
        if artifact_kind == "family"
        else output / "source-project.json"
    )

    def _fail_replace(*args, **kwargs):
        raise OSError("simulated interruption while committing signed payload")

    monkeypatch.setattr(handoff.os, "replace", _fail_replace)
    with pytest.raises(OSError, match="simulated interruption"):
        if artifact_kind == "family":
            run = _run(
                project_id="source-project", source_sha256="a" * 64,
                family="opening_area", quantity_id="q-atomic-opening",
            )
            handoff._write_run(output, "opening_area", run)
        else:
            handoff._write_text_atomic(destination, '{"sealed":"not yet signed"}')
    assert not destination.exists()
    assert destination.parent.is_dir()
    assert sorted(destination.parent.iterdir()) == []


def test_parallel_source_handoff_is_rejected_before_touching_running_artifacts(
    tmp_path, monkeypatch,
):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"real source bytes unchanged")
    output = tmp_path / "handoff-output"
    output.mkdir()
    marker = output / ".source_closed_handoff.lock"
    marker.write_bytes(b"original active writer owns this directory")
    monkeypatch.setattr(
        handoff, "_source_page_scopes",
        lambda *_: pytest.fail("second writer must not launch source collector"),
    )
    with pytest.raises(FileExistsError):
        handoff.generate_project_handoff(
            pdf_path=source, project_id="project-a",
            workspace_id=1, output_dir=output,
        )
    assert marker.read_bytes() == b"original active writer owns this directory"
    assert source.read_bytes() == b"real source bytes unchanged"
    assert not (output / "production_summary.json").exists()
    assert not (output / "source_attempt_preflight.json").exists()


def test_exclusive_handoff_lock_is_cleaned_after_interrupted_source_collect(
    tmp_path, monkeypatch,
):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"original source")
    output = tmp_path / "out"
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _: ((0,), (), 1))
    def _interrupt(*args, **kwargs):
        assert (output / ".source_closed_handoff.lock").is_file()
        raise KeyboardInterrupt("source task interrupted")
    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", _interrupt)
    with pytest.raises(KeyboardInterrupt, match="source task interrupted"):
        handoff.generate_project_handoff(
            pdf_path=source, project_id="project-a",
            workspace_id=1, output_dir=output,
        )
    assert not (output / ".source_closed_handoff.lock").exists()
    assert not (output / "project-a.json").exists()


def test_stale_crash_lock_cannot_be_automatically_assumed_complete(
    tmp_path, monkeypatch,
):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"original source")
    output = tmp_path / "out"
    output.mkdir()
    stale = output / ".source_closed_handoff.lock"
    stale.write_bytes(b"interrupted source run: do not trust prior seals")
    with pytest.raises(FileExistsError):
        handoff.generate_project_handoff(
            pdf_path=source, project_id="project-a",
            workspace_id=1, output_dir=output,
        )
    assert stale.read_bytes() == b"interrupted source run: do not trust prior seals"


@pytest.mark.parametrize("invalid", [
    {"project_id": "../foreign"},
    {"project_id": "subdir/customer"},
    {"workspace_id": True},
    {"workspace_id": "2"},
    {"workspace_id": 0},
    {"family_group": "unknown-family"},
])
def test_invalid_handoff_arguments_never_create_output_directory_or_lock(
    tmp_path, monkeypatch, invalid,
):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"source-bytes")
    output = tmp_path / "never-create"
    def _should_not_execute(*args, **kwargs):
        pytest.fail("source-page classification must not run on invalid input")
    monkeypatch.setattr(handoff, "_source_page_scopes", _should_not_execute)
    inputs = dict(
        pdf_path=source, project_id="project-a", workspace_id=1,
        output_dir=output, family_group="all",
    )
    inputs.update(invalid)
    with pytest.raises(ValueError):
        handoff.generate_project_handoff(**inputs)
    assert not output.exists()
    assert not (tmp_path / "foreign").exists()


def test_missing_original_pdf_does_not_create_output_directory(tmp_path):
    output = tmp_path / "never-create"
    with pytest.raises(FileNotFoundError):
        handoff.generate_project_handoff(
            pdf_path=tmp_path / "missing.pdf",
            project_id="project-a", workspace_id=1, output_dir=output,
        )
    assert not output.exists()


@pytest.mark.parametrize("unsafe_path", ["output_dir", "family_runs"])
def test_signed_output_directory_symlink_cannot_redirect_customer_rows(
    tmp_path, monkeypatch, unsafe_path,
):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"authenticated-original-bytes")
    other_workspace = tmp_path / "foreign-workspace"
    other_workspace.mkdir()
    output = tmp_path / "intended-output"
    if unsafe_path == "output_dir":
        output.symlink_to(other_workspace, target_is_directory=True)
    else:
        output.mkdir()
        (output / "family_runs").symlink_to(
            other_workspace, target_is_directory=True,
        )
    def _do_not_run(*args, **kwargs):
        pytest.fail("symlinked customer seal output must be rejected before source read")
    monkeypatch.setattr(handoff, "_source_page_scopes", _do_not_run)
    with pytest.raises(FileExistsError, match="symlink"):
        handoff.generate_project_handoff(
            pdf_path=source, project_id="project-a", workspace_id=1,
            output_dir=output,
        )
    assert source.read_bytes() == b"authenticated-original-bytes"
    assert list(other_workspace.iterdir()) == []
    assert not (output / "source_attempt_preflight.json").exists()
    assert not (output / "production_summary.json").exists()
    assert not (output / ".source_closed_handoff.lock").exists()


def test_other_project_combined_seal_prevents_mixed_project_output(tmp_path, monkeypatch):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"unchanged source")
    output = tmp_path / "shared-output"
    output.mkdir()
    earlier = output / "other-customer.json"
    earlier.write_bytes(b"old independently source-signed combined run")

    def _should_not_run(*args, **kwargs):
        pytest.fail("an unrelated customer's signed output may not share this folder")
    monkeypatch.setattr(handoff, "_source_page_scopes", _should_not_run)
    with pytest.raises(FileExistsError, match="existing sealed handoff artifact"):
        handoff.generate_project_handoff(
            pdf_path=source, project_id="new-customer",
            workspace_id=1, output_dir=output,
        )
    assert earlier.read_bytes() == b"old independently source-signed combined run"
    assert source.read_bytes() == b"unchanged source"
    assert not (output / "source_attempt_preflight.json").exists()
    assert not (output / "production_summary.json").exists()
    assert not (output / ".source_closed_handoff.lock").exists()
