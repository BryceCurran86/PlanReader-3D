from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace as S

import pytest

from tools import run_source_closed_project_handoff as handoff


def _plan_scope(*, positive: bool):
    return S(decisions=(
        S(page_index=0, classification="floor_plan" if positive else "unproven"),
        S(page_index=1, classification="not_floor_plan"),
    ))


@pytest.mark.parametrize("wrong", [None, True, -1, 3, "0"])
def test_source_scoped_floor_area_requires_exact_original_page(monkeypatch, tmp_path, wrong):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"synthetic original immutable bytes")
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _path: ((0, 1), (), 3))
    import pb_source_floor_plan_page_scope as classifier
    monkeypatch.setattr(classifier, "source_floor_plan_topology_scope",
                        lambda _path, _pages: _plan_scope(positive=True))
    destination = tmp_path / "out"
    if wrong is None:
        # Missing page restriction is allowed: default production behaviour.
        assert handoff._validate_source_handoff_inputs(
            source, "test_project", 1, "floor_area"
        ) == "floor_area"
        return
    with pytest.raises((ValueError, RuntimeError)):
        handoff._generate_project_handoff_locked(
            pdf_path=source, project_id="test_project", workspace_id=1,
            output_dir=destination, family_group="floor_area",
            source_plan_page_index=wrong,
        )
    assert not (destination / "family_runs").exists()


def test_unproven_original_floor_plan_page_never_seals(monkeypatch, tmp_path):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"source-owned immutable bytes")
    import pb_source_floor_plan_page_scope as classifier
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _path: ((0, 1), (), 3))
    monkeypatch.setattr(classifier, "source_floor_plan_topology_scope",
                        lambda _path, _pages: _plan_scope(positive=False))
    destination = tmp_path / "out"
    with pytest.raises(RuntimeError, match="source_positive_floor_plan_page_required"):
        handoff._generate_project_handoff_locked(
            pdf_path=source, project_id="test_project", workspace_id=1,
            output_dir=destination, family_group="floor_area",
            source_plan_page_index=0,
        )
    assert not (destination / "family_runs").exists()


def test_source_positive_page_runs_only_its_own_floor_area_without_finish_or_ceiling(
    monkeypatch, tmp_path,
):
    source = tmp_path / "original.pdf"
    source.write_bytes(b"source-owned immutable bytes")
    import pb_source_floor_plan_page_scope as classifier
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _path: ((0, 1), (), 3))
    monkeypatch.setattr(classifier, "source_floor_plan_topology_scope",
                        lambda _path, _pages: _plan_scope(positive=True))
    seen = []

    def collect(_pdf, **kwargs):
        seen.append(kwargs)
        return S(status="partial", reason_codes=(),
                 canonical_walls=(), canonical_openings=(),
                 canonical_rooms=(), canonical_floors=(),
                 canonical_ceilings=(), canonical_spaces=(),
                 room_area_quantity_evidence=(), floor_area_quantity_evidence=())

    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim", collect)
    # This test isolates page-scope handoff control. The real floor publisher
    # correctly requires a sealed LivePhysicalNetWallClaim, not this fake.
    monkeypatch.setattr(handoff, "publish_live_floor_area_quantities", lambda _: ())
    destination = tmp_path / "scoped-output"
    result = handoff._generate_project_handoff_locked(
        pdf_path=source, project_id="test_project", workspace_id=1,
        output_dir=destination, family_group="floor_area",
        source_plan_page_index=0,
    )
    assert len(seen) == 1
    assert tuple(seen[0]["pages"]) == (0,)
    assert tuple(seen[0]["topology_pages"]) == (0,)
    assert tuple(seen[0]["surface_semantic_pages"]) == (0,)
    assert result["topology_pages"] == [1]
    assert result["execution_pages"] == [1]
    assert result["source_positive_partial_page"] == 1
    assert result["complete_project_handoff"] is False
    assert result["family_counts"]["floor_area"] == 0
    assert result["family_counts"]["floor_finish_area"] == 0
    assert result["family_counts"]["ceiling_area"] == 0
    assert result["combined_quantity_count"] == 0
    assert result["status"] == "no_sealable_quantities"
    assert result["benchmark_score_granted"] is False
    assert not (destination / "family_runs").exists()


@pytest.mark.parametrize("family_group", ["all", "surfaces"])
def test_partial_plan_cannot_pretend_to_cover_all_source_families(
    monkeypatch, tmp_path, family_group,
):
    original = tmp_path / "original.pdf"
    original.write_bytes(b"synthetic immutable source")
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _: ((0, 1), (), 3))
    with pytest.raises(ValueError, match="partial original floor-plan scope requires"):
        handoff._generate_project_handoff_locked(
            pdf_path=original,
            project_id="test_project",
            workspace_id=1,
            output_dir=tmp_path / "partial",
            family_group=family_group,
            source_plan_page_index=0,
        )
    assert not (tmp_path / "partial" / "production_summary.json").exists()


@pytest.mark.parametrize("customer_id_matches", [True, False])
def test_scoped_firm_floor_requires_exact_verified_customer_bijection_before_any_seal(
    monkeypatch, tmp_path, customer_id_matches,
):
    import hashlib
    import json
    from pb_migration_contracts import QuantityEvidence
    from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
    from pb_source_closed_run_export import seal_source_closed_run
    import pb_source_floor_plan_page_scope as classifier

    pdf = tmp_path / "original.pdf"
    pdf.write_bytes(b"immutable original source bytes")
    sha = hashlib.sha256(pdf.read_bytes()).hexdigest()
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _: ((0, 1), (), 3))
    monkeypatch.setattr(classifier, "source_floor_plan_topology_scope",
                        lambda _path, _pages: _plan_scope(positive=True))
    claim = S(
        status=S(value="corroborated"), reason_codes=(),
        canonical_walls=(), canonical_openings=(), canonical_rooms=(),
        canonical_floors=(), canonical_ceilings=(), canonical_spaces=(),
    )
    monkeypatch.setattr(handoff, "collect_live_physical_net_wall_claim",
                        lambda *args, **kwargs: claim)
    q = QuantityEvidence(
        quantity_id="q-firm-floor",
        family="floor_area", semantic_key="floor_area:physical-1",
        value=12.4, unit="m2", input_entity_ids=("physical-floor-1",),
        formula="source independent figured dimensions",
        formula_version="1", evidence_ids=("observation-1",),
        authority="documented_dimension", status="firm",
        confidence=1.0, abstained=False, blocking_reasons=(),
        reason_codes=(), metadata={},
    )
    trace = CommercialTakeoffSourceTrace(
        workspace_id=1, project_id="project_a",
        document_id="doc", source_sha256=sha,
        source_page="1", viewport_id="vp-1",
        revision_id="rev", current_revision_id="rev",
        evidence_ids=q.evidence_ids, canonical_entity_ids=q.input_entity_ids,
    )
    sealed = seal_source_closed_run(
        (q,), project_id="project_a",
        traces_by_quantity_id={q.quantity_id: trace},
    )
    monkeypatch.setattr(handoff, "publish_live_floor_area_quantities",
                        lambda _claim: (q,))
    monkeypatch.setattr(handoff, "seal_live_floor_area_run",
                        lambda *a, **kw: sealed)
    projected = ({"quantity_id": q.quantity_id},)
    monkeypatch.setattr(handoff, "project_live_floor_area_customer_rows",
                        lambda *a, **kw: projected)
    seen = []

    def verified(run, rows):
        seen.append((run, rows))
        return S(
            verified_quantity_ids=("q-firm-floor",) if customer_id_matches else ("other",),
            customer_row_count=1,
        )

    monkeypatch.setattr(handoff, "verify_sealed_customer_output", verified)
    output = tmp_path / "produced"
    if customer_id_matches:
        result = handoff._generate_project_handoff_locked(
            pdf_path=pdf, project_id="project_a", workspace_id=1,
            output_dir=output, family_group="floor_area",
            source_plan_page_index=0,
        )
        assert len(seen)==1 and seen[0][1]==projected
        assert result["status"]=="sealed"
        assert result["complete_project_handoff"] is False
        assert result["customer_rows_verified"] is True
        assert result["verified_customer_row_count"]==1
        assert json.loads((output/"verified_customer_rows.json").read_text())==list(projected)
        assert (output/"family_runs"/"floor_area.sealed.json").is_file()
    else:
        with pytest.raises(RuntimeError, match="floor-area sealed customer identities disagree"):
            handoff._generate_project_handoff_locked(
                pdf_path=pdf, project_id="project_a", workspace_id=1,
                output_dir=output, family_group="floor_area",
                source_plan_page_index=0,
            )
        summary=json.loads((output/"production_summary.json").read_text())
        assert summary["status"]=="floor_area_customer_projection_unverified"
        assert summary["customer_rows_verified"] is False
        assert not (output/"family_runs"/"floor_area.sealed.json").exists()
        assert not (output/"verified_customer_rows.json").exists()


@pytest.mark.parametrize("opening_customer_matches", [True, False])
def test_source_scoped_opening_customer_mismatch_does_not_publish_a_signed_family(
    monkeypatch, tmp_path, opening_customer_matches,
):
    import hashlib, json
    from pb_migration_contracts import QuantityEvidence
    from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
    from pb_source_closed_run_export import seal_source_closed_run
    import pb_source_floor_plan_page_scope as classifier

    pdf=tmp_path/"original.pdf"
    pdf.write_bytes(b"original physical opening bytes")
    sha=hashlib.sha256(pdf.read_bytes()).hexdigest()
    monkeypatch.setattr(handoff, "_source_page_scopes", lambda _: ((0,1), (), 3))
    monkeypatch.setattr(classifier, "source_floor_plan_topology_scope",
                        lambda _p,_pages: _plan_scope(positive=True))
    q=QuantityEvidence(
        quantity_id="q-original-opening",family="opening_area",
        semantic_key="opening_area:physical-1",
        value=1.8,unit="m2",
        input_entity_ids=("canonical-opening-1",),
        formula="source-owned figured dimensions",
        formula_version="1",evidence_ids=("dimension-1",),
        authority="documented_dimension",status="corroborated",
        confidence=1.0,abstained=False,blocking_reasons=(),
        reason_codes=(),metadata={},
    )
    claim=S(status=S(value="corroborated"),reason_codes=(),
            canonical_walls=(),canonical_openings=(),canonical_rooms=(),
            canonical_floors=(),canonical_spaces=(),canonical_ceilings=(),
            opening_quantity_evidence=(q,),opening_count_quantity_evidence=())
    trace=CommercialTakeoffSourceTrace(
        workspace_id=1,project_id="test_project",document_id="doc",
        source_sha256=sha,source_page="1",viewport_id="viewport",
        revision_id="rev",current_revision_id="rev",
        evidence_ids=q.evidence_ids,canonical_entity_ids=q.input_entity_ids,
    )
    sealed=seal_source_closed_run(
        (q,),project_id="test_project",
        traces_by_quantity_id={q.quantity_id:trace},
    )
    monkeypatch.setattr(handoff,"collect_live_physical_net_wall_claim",
                        lambda *a,**kw:claim)
    monkeypatch.setattr(handoff,"seal_live_opening_area_claim_run",
                        lambda *a,**kw:sealed)
    rows=({"quantity_id":q.quantity_id},)
    monkeypatch.setattr(handoff,"project_live_opening_customer_rows",
                        lambda *a,**kw:rows)
    monkeypatch.setattr(handoff,"verify_sealed_customer_output",
                        lambda *_: S(
                            verified_quantity_ids=("q-original-opening",)
                                if opening_customer_matches else ("different-opening",),
                            customer_row_count=1))
    output=tmp_path/"out"
    if opening_customer_matches:
        summary=handoff._generate_project_handoff_locked(
            pdf_path=pdf,project_id="test_project",workspace_id=1,
            output_dir=output,family_group="core",
            source_plan_page_index=0,
        )
        assert summary["status"]=="sealed"
        assert summary["customer_rows_verified"] is True
        assert summary["verified_customer_row_count"]==1
        assert json.loads((output/"verified_customer_rows.json").read_text())==list(rows)
        assert (output/"family_runs"/"opening_area.sealed.json").is_file()
    else:
        with pytest.raises(RuntimeError,match="sealed customer identities disagree"):
            handoff._generate_project_handoff_locked(
                pdf_path=pdf,project_id="test_project",workspace_id=1,
                output_dir=output,family_group="core",
                source_plan_page_index=0,
            )
        summary=json.loads((output/"production_summary.json").read_text())
        assert summary["status"]=="opening_customer_projection_unverified"
        assert not (output/"verified_customer_rows.json").exists()
        assert not (output/"family_runs"/"opening_area.sealed.json").exists()
