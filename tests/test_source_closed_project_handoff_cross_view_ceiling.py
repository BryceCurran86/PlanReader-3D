"""Handoff routing tests for mixed cross-view + legacy ceiling authority."""
from __future__ import annotations

import hashlib
from pathlib import Path
from types import SimpleNamespace

import fitz

from pb_live_ceiling_lining_integration import LiveCeilingLiningResult
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
import tools.run_source_closed_project_handoff as handoff


def _pdf(path: Path) -> str:
    doc = fitz.open()
    doc.new_page(width=100.0, height=100.0)
    payload = doc.tobytes()
    doc.close()
    path.write_bytes(payload)
    return hashlib.sha256(payload).hexdigest()


def _firm_quantity(quantity_id: str, ceiling_id: str) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=quantity_id,
        family="ceiling_lining",
        semantic_key=f"ceiling_lining:{ceiling_id}",
        value=9.05352,
        unit="m2",
        input_entity_ids=(ceiling_id,),
        formula="test",
        formula_version="1",
        evidence_ids=(f"ev-{quantity_id}",),
        authority="documented_dimension",
        status="firm",
        confidence=1.0,
        abstained=False,
        metadata={"row_role": "ceiling_area"},
    )


def _shadow_quantity(quantity_id: str, room_id: str) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=quantity_id,
        family="ceiling_lining",
        semantic_key=f"ceiling_lining:{room_id}",
        value=9.05352,
        unit="m2",
        input_entity_ids=(room_id,),
        formula="shadow",
        formula_version="1",
        evidence_ids=(f"ev-{quantity_id}",),
        authority="model_derived",
        status="provisional",
        confidence=1.0,
        abstained=False,
        metadata={
            "shadow_only": True,
            "commercial_projection_allowed": False,
        },
    )


def test_project_handoff_preserves_nonoverlapping_legacy_ceiling(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    source_sha = _pdf(pdf)

    new_quantity = _firm_quantity("qty-new", "ceiling-new")
    legacy_quantity = _firm_quantity("qty-legacy", "ceiling-legacy")
    new_canonical = SimpleNamespace(
        canonical_ceiling_id="ceiling-new",
        source_room_index_id="room-index-overlap",
    )
    claim = SimpleNamespace(
        status=SimpleNamespace(value="corroborated"),
        reason_codes=("resolved",),
        canonical_walls=(),
        canonical_openings=(),
        canonical_rooms=(),
        canonical_floors=(),
        canonical_ceilings=(new_canonical,),
        canonical_spaces=(),
        floor_finish_quantity_evidence=(),
        room_area_quantity_evidence=(),
        ceiling_lining_quantity_evidence=(new_quantity,),
    )

    overlap_ceiling = SimpleNamespace(
        canonical_ceiling_id="legacy-overlap",
        source_room_index_id="room-index-overlap",
        ceiling_quantity_id="shadow-overlap",
    )
    unrelated_ceiling = SimpleNamespace(
        canonical_ceiling_id="legacy-unrelated",
        source_room_index_id="room-index-other",
        ceiling_quantity_id="shadow-other",
    )
    legacy_result = LiveCeilingLiningResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("resolved",),
        claims=(),
        canonical_ceilings=(overlap_ceiling, unrelated_ceiling),
        quantity_evidence=(
            _shadow_quantity("shadow-overlap", "room-overlap"),
            _shadow_quantity("shadow-other", "room-other"),
        ),
    )

    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _path: ((), (), 1))
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
    monkeypatch.setattr(
        handoff,
        "collect_live_ceiling_lining_claims",
        lambda *_args, **_kwargs: legacy_result,
    )

    seen = {"publisher_calls": 0, "new_seals": 0, "legacy_seals": 0}

    def _publish_legacy(result):
        seen["publisher_calls"] += 1
        assert tuple(
            ceiling.source_room_index_id
            for ceiling in result.canonical_ceilings
        ) == ("room-index-other",)
        assert tuple(
            quantity.quantity_id
            for quantity in result.quantity_evidence
        ) == ("shadow-other",)
        return (legacy_quantity,)

    monkeypatch.setattr(
        handoff,
        "publish_live_ceiling_area_quantities",
        _publish_legacy,
    )

    def _run(run_id, quantity):
        return SimpleNamespace(
            run_id=run_id,
            source_sha256s=(source_sha,),
            quantities=(SimpleNamespace(quantity_id=quantity.quantity_id),),
            to_json=lambda: "{}",
        )

    def _seal_new(_claim, *, workspace_id, project_id):
        assert _claim is claim
        assert workspace_id == 1
        assert project_id == "project-1"
        seen["new_seals"] += 1
        return _run("run-new", new_quantity)

    def _seal_legacy(result, *, workspace_id, project_id):
        assert tuple(
            ceiling.source_room_index_id
            for ceiling in result.canonical_ceilings
        ) == ("room-index-other",)
        assert workspace_id == 1
        assert project_id == "project-1"
        seen["legacy_seals"] += 1
        return _run("run-legacy", legacy_quantity)

    monkeypatch.setattr(handoff, "seal_live_ceiling_lining_run", _seal_new)
    monkeypatch.setattr(handoff, "seal_live_ceiling_area_run", _seal_legacy)

    def _combine(runs, *, project_id):
        assert project_id == "project-1"
        rows = tuple(row for run in runs for row in run.quantities)
        return SimpleNamespace(
            run_id=f"combined-{len(rows)}",
            source_sha256s=(source_sha,),
            quantities=rows,
            to_json=lambda: "{}",
        )

    monkeypatch.setattr(handoff, "combine_source_closed_runs", _combine)

    summary = handoff.generate_project_handoff(
        pdf_path=pdf,
        project_id="project-1",
        workspace_id=1,
        output_dir=tmp_path / "out",
        family_group="surfaces",
    )

    assert seen == {
        "publisher_calls": 1,
        "new_seals": 1,
        "legacy_seals": 1,
    }
    assert summary["canonical_counts"]["ceilings"] == 1
    assert summary["family_counts"]["ceiling_area"] == 2
    assert (
        summary["ceiling_authority_path"]
        == "cross_view_rcp_plus_legacy_nonoverlap"
    )
    assert summary["combined_quantity_count"] == 2
    assert summary["status"] == "sealed"
