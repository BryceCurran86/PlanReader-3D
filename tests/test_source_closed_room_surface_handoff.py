"""Partial room-surface source-closed handoff tests."""
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
from tools import run_source_closed_room_surface_handoff as handoff


def _pdf(path, pages: int = 4) -> None:
    doc = fitz.open()
    try:
        for _ in range(pages):
            doc.new_page(width=200, height=100)
        doc.save(path)
    finally:
        doc.close()


def _quantity(quantity_id: str, family: str) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=quantity_id,
        family=family,
        semantic_key=f"{family}:physical-floor-1",
        value=8.64,
        unit="m2",
        input_entity_ids=("physical-floor-1",),
        formula="test",
        formula_version="1",
        evidence_ids=(f"ev-{quantity_id}",),
        authority="documented_dimension",
        status="firm",
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        metadata={},
    )


def _run(project_id: str, source_sha: str, family: str):
    quantity = _quantity(f"qty-{family}", family)
    trace = CommercialTakeoffSourceTrace(
        workspace_id=1,
        project_id=project_id,
        document_id="doc-1",
        source_sha256=source_sha,
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


def test_positive_room_surface_scope_uses_only_floor_and_cross_view_types(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    _pdf(pdf, 6)
    scope = SourceFloorPlanPageScope(
        decisions=(
            SourceFloorPlanPageDecision(
                0, "not_floor_plan", "title", "COVER", ()
            ),
            SourceFloorPlanPageDecision(
                1, "floor_plan", "title", "FLOOR PLAN", ("floor_plan",)
            ),
            SourceFloorPlanPageDecision(
                2, "not_floor_plan", "title", "INTERNAL ELEVATIONS", ("elevation",)
            ),
            SourceFloorPlanPageDecision(
                3, "not_floor_plan", "title", "BUILDING SECTION", ("section",)
            ),
            SourceFloorPlanPageDecision(
                4, "not_floor_plan", "title", "DOOR SCHEDULE", ("schedule",)
            ),
            SourceFloorPlanPageDecision(
                5, "unproven", "unproven"
            ),
        ),
        selected_page_indices=(0, 1, 2, 3, 4, 5),
        floor_plan_page_indices=(1,),
        other_drawing_page_indices=(0, 2, 3, 4),
    )
    monkeypatch.setattr(
        handoff,
        "source_floor_plan_topology_scope",
        lambda path, selected: scope,
    )

    floor, support, count = handoff._positive_room_surface_scope(pdf)

    assert count == 6
    assert floor == (1,)
    assert support == (2, 3)


def test_room_surface_handoff_seals_only_floor_and_ceiling_partial_scope(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    source_sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    project_id = "project-a"
    floor_quantity = _quantity("floor-1", "floor_area")
    room_area = _quantity("room-area-1", "room_area")
    claim = SimpleNamespace(
        status=SimpleNamespace(value="corroborated"),
        reason_codes=("resolved",),
        room_area_quantity_evidence=(room_area,),
    )
    ceiling_candidate = SimpleNamespace(
        promoted_quantity=_quantity("ceiling-1", "ceiling_lining")
    )
    seen = {}

    monkeypatch.setattr(
        handoff,
        "_positive_room_surface_scope",
        lambda path: ((0,), (2, 3), 4),
    )

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
        "publish_live_floor_area_quantities",
        lambda claim: (floor_quantity,),
    )
    monkeypatch.setattr(
        handoff,
        "collect_ceiling_lining_review_candidates",
        lambda *args, **kwargs: (ceiling_candidate,),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_floor_area_run",
        lambda *args, **kwargs: _run(
            project_id, source_sha, "floor_area"
        ),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_ceiling_review_run",
        lambda *args, **kwargs: _run(
            project_id, source_sha, "ceiling_lining"
        ),
    )

    output = tmp_path / "out"
    summary = handoff.generate_room_surface_handoff(
        pdf_path=pdf,
        project_id=project_id,
        workspace_id=1,
        output_dir=output,
    )

    assert seen["pages"] == (0,)
    assert seen["topology_pages"] == (0,)
    assert seen["room_area_support_pages"] == (2, 3)
    assert summary["handoff_scope"] == "partial_room_surfaces"
    assert summary["scope_complete_for_project"] is False
    assert summary["floor_plan_pages"] == [1]
    assert summary["room_support_pages"] == [3, 4]
    assert summary["family_counts"] == {
        "floor_area": 1,
        "ceiling_lining": 1,
    }
    assert summary["status"] == "sealed_partial_family_scope"
    assert summary["combined_quantity_count"] == 2
    assert (output / f"{project_id}.room_surfaces.json").is_file()


def test_room_surface_handoff_without_positive_floor_plan_abstains(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    monkeypatch.setattr(
        handoff,
        "_positive_room_surface_scope",
        lambda path: ((), (1,), 2),
    )

    def _unexpected(*args, **kwargs):
        raise AssertionError("production extraction must not run")

    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        _unexpected,
    )

    summary = handoff.generate_room_surface_handoff(
        pdf_path=pdf,
        project_id="project-a",
        workspace_id=1,
        output_dir=tmp_path / "out",
    )

    assert summary["status"] == "unavailable"
    assert summary["claim_reason_codes"] == [
        "no_positively_classified_floor_plan_page"
    ]
    assert summary["combined_run_file"] is None
    assert summary["scope_complete_for_project"] is False


def test_room_surface_handoff_persists_failure_summary(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    output = tmp_path / "out"
    monkeypatch.setattr(
        handoff,
        "_positive_room_surface_scope",
        lambda path: ((0,), (1,), 2),
    )

    def _blocked(*args, **kwargs):
        raise RuntimeError("source authority blocked")

    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        _blocked,
    )

    with pytest.raises(RuntimeError, match="source authority blocked"):
        handoff.generate_room_surface_handoff(
            pdf_path=pdf,
            project_id="project-a",
            workspace_id=1,
            output_dir=output,
        )

    import json
    payload = json.loads(
        (output / "room_surface_summary.json").read_text(encoding="utf-8")
    )
    assert payload["status"] == "production_failed"
    assert payload["production_error_type"] == "RuntimeError"
    assert payload["scope_complete_for_project"] is False
