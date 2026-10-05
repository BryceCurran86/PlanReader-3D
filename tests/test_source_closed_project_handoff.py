"""Generic project source-closed handoff orchestration tests."""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_source_closed_run_export import seal_source_closed_run
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


def test_project_handoff_combines_only_available_source_closed_families(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    source_sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    project_id = "project-a"

    room_q = _quantity("q-room", "room_area")
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
        room_area_quantity_evidence=(room_q,),
        opening_quantity_evidence=(opening_q,),
        opening_count_quantity_evidence=(count_q,),
    )
    ceiling_candidate = SimpleNamespace(promoted_quantity=_quantity("q-ceiling", "ceiling_lining"))

    monkeypatch.setattr(handoff, "_source_topology_pages", lambda path: ((0,), 1))
    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        lambda *args, **kwargs: claim,
    )
    monkeypatch.setattr(
        handoff,
        "collect_ceiling_lining_review_candidates",
        lambda *args, **kwargs: (ceiling_candidate,),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_room_area_run",
        lambda *args, **kwargs: _run(
            project_id=project_id,
            source_sha256=source_sha,
            family="room_area",
            quantity_id="sealed-room",
        ),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_opening_area_claim_run",
        lambda *args, **kwargs: _run(
            project_id=project_id,
            source_sha256=source_sha,
            family="opening_area",
            quantity_id="sealed-opening",
        ),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_opening_count_run",
        lambda *args, **kwargs: _run(
            project_id=project_id,
            source_sha256=source_sha,
            family="opening_count",
            quantity_id="sealed-count",
        ),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_ceiling_review_run",
        lambda *args, **kwargs: _run(
            project_id=project_id,
            source_sha256=source_sha,
            family="ceiling_lining",
            quantity_id="sealed-ceiling",
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
    assert summary["source_sha256"] == source_sha
    assert summary["topology_pages"] == [1]
    assert summary["family_counts"] == {
        "room_area": 1,
        "opening_area": 1,
        "opening_count": 1,
        "ceiling_lining": 1,
    }
    assert summary["combined_quantity_count"] == 4
    assert (output / f"{project_id}.sealed.json").is_file()
    assert (output / "production_summary.json").is_file()
    assert sorted((output / "family_runs").glob("*.sealed.json"))


def test_project_handoff_no_source_topology_fails_closed_without_extraction(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    monkeypatch.setattr(handoff, "_source_topology_pages", lambda path: ((), 3))

    def _unexpected(*args, **kwargs):
        raise AssertionError("production extraction must not run without source topology")

    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        _unexpected,
    )

    summary = handoff.generate_project_handoff(
        pdf_path=pdf,
        project_id="project-a",
        workspace_id=1,
        output_dir=tmp_path / "out",
    )

    assert summary["status"] == "unavailable"
    assert summary["topology_pages"] == []
    assert summary["claim_reason_codes"] == [
        "no_source_authoritative_floor_plan_topology"
    ]
    assert summary["combined_run_file"] is None


def test_project_handoff_rejects_family_run_from_different_source(
    tmp_path,
    monkeypatch,
) -> None:
    pdf = tmp_path / "source.pdf"
    pdf.write_bytes(b"source-bytes")
    room_q = _quantity("q-room", "room_area")
    claim = SimpleNamespace(
        status=SimpleNamespace(value="corroborated"),
        reason_codes=(),
        canonical_walls=(),
        canonical_openings=(),
        canonical_rooms=(1,),
        canonical_floors=(1,),
        canonical_spaces=(1,),
        room_area_quantity_evidence=(room_q,),
        opening_quantity_evidence=(),
        opening_count_quantity_evidence=(),
    )

    monkeypatch.setattr(handoff, "_source_topology_pages", lambda path: ((0,), 1))
    monkeypatch.setattr(
        handoff,
        "collect_live_physical_net_wall_claim",
        lambda *args, **kwargs: claim,
    )
    monkeypatch.setattr(
        handoff,
        "collect_ceiling_lining_review_candidates",
        lambda *args, **kwargs: (),
    )
    monkeypatch.setattr(
        handoff,
        "seal_live_room_area_run",
        lambda *args, **kwargs: _run(
            project_id="project-a",
            source_sha256="f" * 64,
            family="room_area",
            quantity_id="sealed-room",
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="does not bind to input source SHA",
    ):
        handoff.generate_project_handoff(
            pdf_path=pdf,
            project_id="project-a",
            workspace_id=1,
            output_dir=tmp_path / "out",
        )
