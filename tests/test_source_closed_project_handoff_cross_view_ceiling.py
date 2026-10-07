"""Handoff routing tests for cross-view ceiling quantities."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import fitz

from pb_migration_contracts import QuantityEvidence
import tools.run_source_closed_project_handoff as handoff


def _pdf(path: Path) -> str:
    doc = fitz.open()
    doc.new_page(width=100.0, height=100.0)
    payload = doc.tobytes()
    doc.close()
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _ceiling_quantity() -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="qty-ceiling-1",
        family="ceiling_lining",
        semantic_key="ceiling_lining:ceiling-1:GRID:ceiling_grid",
        value=9.05352,
        unit="m2",
        input_entity_ids=("ceiling-1",),
        formula="authenticated_cross_view_room_area_with_source_ceiling_finish",
        formula_version="1.0.0",
        evidence_ids=("ev-1",),
        authority="documented_dimension",
        status="firm",
        confidence=1.0,
        abstained=False,
        reason_codes=("authenticated_cross_view_ceiling_lining_area",),
        metadata={"row_role": "ceiling_area"},
    )


def test_project_handoff_prefers_cross_view_ceiling_without_replaying_old_pipeline(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    source_sha = _pdf(pdf)
    quantity = _ceiling_quantity()
    claim = SimpleNamespace(
        status=SimpleNamespace(value="corroborated"),
        reason_codes=("resolved",),
        canonical_walls=(),
        canonical_openings=(),
        canonical_rooms=(),
        canonical_floors=(),
        canonical_spaces=(),
        floor_finish_quantity_evidence=(),
        room_area_quantity_evidence=(),
        ceiling_lining_quantity_evidence=(quantity,),
    )

    monkeypatch.setattr(
        handoff,
        "_source_page_scopes",
        lambda _path: ((), (), 1),
    )
    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        lambda *_args, **_kwargs: claim,
    )
    monkeypatch.setattr(
        handoff,
        "publish_live_floor_area_quantities",
        lambda _claim: (),
    )

    def _old_ceiling_must_not_run(*_args, **_kwargs):
        raise AssertionError("legacy ceiling extractor replayed unexpectedly")

    monkeypatch.setattr(
        handoff,
        "collect_live_ceiling_lining_claims",
        _old_ceiling_must_not_run,
    )

    sealed_family = SimpleNamespace(
        run_id="run-ceiling",
        source_sha256s=(source_sha,),
        quantities=(SimpleNamespace(quantity_id=quantity.quantity_id),),
        to_json=lambda: "{}",
    )
    called = {"cross_view": 0}

    def _seal_cross_view(_claim, *, workspace_id, project_id):
        assert _claim is claim
        assert workspace_id == 1
        assert project_id == "project-1"
        called["cross_view"] += 1
        return sealed_family

    monkeypatch.setattr(
        handoff,
        "seal_live_ceiling_lining_run",
        _seal_cross_view,
    )
    monkeypatch.setattr(
        handoff,
        "combine_source_closed_runs",
        lambda runs, *, project_id: SimpleNamespace(
            run_id="combined-run",
            source_sha256s=(source_sha,),
            quantities=tuple(
                row
                for run in runs
                for row in run.quantities
            ),
            to_json=lambda: "{}",
        ),
    )

    summary = handoff.generate_project_handoff(
        pdf_path=pdf,
        project_id="project-1",
        workspace_id=1,
        output_dir=tmp_path / "out",
        family_group="surfaces",
    )

    assert called["cross_view"] == 1
    assert summary["family_counts"]["ceiling_area"] == 1
    assert (
        summary["ceiling_authority_path"]
        == "cross_view_room_area_plus_rcp_finish"
    )
    assert summary["combined_quantity_count"] == 1
    assert summary["status"] == "sealed"
