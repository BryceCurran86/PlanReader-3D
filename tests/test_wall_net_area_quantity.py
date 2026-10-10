from __future__ import annotations

from dataclasses import replace
import pytest

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_migration_contracts import (
    DocumentEvidence,
    EntityEvidence,
    EvidenceAtom,
    EvidenceResolutionStatus,
    QuantityEvidence,
    ViewportEvidence,
    ViewportResolutionStatus,
)
from pb_migration_provider_envelope import ProviderContext
from pb_wall_net_area_quantity import build_net_wall_area_quantity


def _ctx() -> ProviderContext:
    return ProviderContext(
        run_id="run",
        workspace_id="ws",
        project_id="p",
        document_id="doc",
        source_sha256="a" * 64,
        revision_id="R1",
        current_revision_id="R1",
        selected_pages=(0,),
        owned_viewport_ids=("VP-1",),
        evidence_snapshot_id="snap",
        canonical_graph_snapshot_id="graph",
        owned_page_numbers=(1,),
        viewport_page_ownership=(("VP-1", 1),),
    )


def _viewport() -> ViewportEvidence:
    return ViewportEvidence(
        viewport_id="VP-1",
        document_id="doc",
        page_id="page-1",
        bbox=(0.0, 0.0, 100.0, 100.0),
        view_type="plan",
        status=ViewportResolutionStatus.RESOLVED,
        confidence=1.0,
    )


def _gross(value=12.0) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="qty-gross",
        family="wall_gross_area",
        semantic_key="wall_gross_area:WALL-1",
        value=value,
        unit="m2",
        input_entity_ids=("WALL-1",),
        formula="length*height",
        formula_version="1",
        evidence_ids=("ev-wall",),
        authority="derived_from_firm_measurements",
        status=AuthorityStatus.FIRM.value,
        confidence=0.95,
        metadata={
            "source_sha256": "a" * 64,
            "revision_id": "R1",
            "viewport_id": "VP-1",
            "page_id": "page-1",
            "evidence_snapshot_id": "snap",
            "canonical_graph_snapshot_id": "graph",
        },
    )


def _deduction(opening_id: str, value: float) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=f"qty-ded-{opening_id}",
        family="opening_deduction_area",
        semantic_key=f"opening_deduction:{opening_id}",
        value=value,
        unit="m2",
        input_entity_ids=(opening_id, "WALL-1"),
        formula="width*height",
        formula_version="1",
        evidence_ids=(f"ev-{opening_id}-w", f"ev-{opening_id}-h"),
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        status=AuthorityStatus.FIRM.value,
        confidence=0.9,
        metadata={
            "source_sha256": "a" * 64,
            "revision_id": "R1",
            "evidence_snapshot_id": "snap",
            "canonical_graph_snapshot_id": "graph",
            "viewport_id": "VP-1",
            "page_id": "page-1",
            "wall_id": "WALL-1",
        },
    )


def _complete(ids: tuple[str, ...]) -> EvidenceAtom:
    return EvidenceAtom(
        evidence_id="ev-opening-set",
        document_id="doc",
        page_id="page-1",
        viewport_id="VP-1",
        kind="opening_set_complete",
        method="caller_reconciliation",
        confidence=0.99,
        status=EvidenceResolutionStatus.CORROBORATED,
        metadata={
            "wall_id": "WALL-1",
            "target_entity_id": "WALL-1",
            "opening_ids": list(ids),
            "source_sha256": "a" * 64,
            "revision_id": "R1",
            "evidence_snapshot_id": "snap",
            "canonical_graph_snapshot_id": "graph",
        },
    )


def _wall_entity(extra_ids=()) -> EntityEvidence:
    return EntityEvidence(
        candidate_entity_id="WALL-1",
        candidate_type="wall",
        evidence_ids=("ev-wall", "ev-opening-set", *tuple(extra_ids)),
        status=EvidenceResolutionStatus.CORROBORATED,
        confidence=0.95,
    )


def _doc(*extra: str) -> DocumentEvidence:
    return DocumentEvidence(
        document_id="doc",
        source_sha256="a" * 64,
        page_count=1,
        page_ids=("page-1",),
        evidence_ids=("ev-wall", "ev-opening-set", *extra),
    )


def _build(*, deductions=(), completion=None, unresolved=(), gross=None):
    completion_ids = (completion.evidence_id,) if completion is not None else ()
    deduction_ids = tuple(e for d in deductions for e in d.evidence_ids)
    entity_ids = tuple(dict.fromkeys(("ev-wall", *completion_ids, *deduction_ids)))
    document_ids = tuple(dict.fromkeys((*completion_ids, *deduction_ids)))
    return build_net_wall_area_quantity(
        wall_id="WALL-1",
        gross_wall_area=gross or _gross(),
        opening_deductions=tuple(deductions),
        opening_set_complete_evidence=completion,
        context=_ctx(),
        document=DocumentEvidence(
            document_id="doc",
            source_sha256="a" * 64,
            page_count=1,
            page_ids=("page-1",),
            evidence_ids=entity_ids,
        ),
        viewport=_viewport(),
        wall_entity=EntityEvidence(
            candidate_entity_id="WALL-1",
            candidate_type="wall",
            evidence_ids=entity_ids,
            status=EvidenceResolutionStatus.CORROBORATED,
            confidence=0.95,
        ),
        unresolved_opening_host_ids=tuple(unresolved),
    )


def test_caller_declared_complete_opening_set_cannot_publish_net_firm() -> None:
    d1 = _deduction("OP-1", 1.89)
    result = _build(deductions=(d1,), completion=_complete(("OP-1",)))
    assert result.abstained
    assert result.value is None
    assert result.status == AuthorityStatus.BLOCKED.value
    assert "opening_universe_completeness_not_authenticated" in result.blocking_reasons


def test_unresolved_w7_host_blocks_net_area_even_with_other_evidence() -> None:
    d1 = _deduction("OP-1", 1.0)
    result = _build(
        deductions=(d1,),
        completion=_complete(("OP-1",)),
        unresolved=("openinghost-ambiguous",),
    )
    assert result.abstained
    assert "unresolved_opening_hosts_present" in result.blocking_reasons


def test_empty_detector_result_is_not_proof_of_no_openings() -> None:
    result = _build(completion=None)
    assert result.abstained
    assert "opening_set_completeness_not_evidenced" in result.blocking_reasons


def test_self_certified_zero_opening_set_cannot_equal_gross() -> None:
    result = _build(completion=_complete(()))
    assert result.abstained
    assert result.value is None
    assert "opening_universe_completeness_not_authenticated" in result.blocking_reasons


def test_declared_opening_set_must_exactly_match_deductions() -> None:
    d1 = _deduction("OP-1", 1.0)
    result = _build(deductions=(d1,), completion=_complete(("OP-1", "OP-2")))
    assert result.abstained
    assert "opening_deduction_set_not_complete" in result.blocking_reasons
    assert "opening_universe_completeness_not_authenticated" in result.blocking_reasons


def test_deduction_cannot_exceed_gross() -> None:
    d1 = _deduction("OP-1", 13.0)
    result = _build(deductions=(d1,), completion=_complete(("OP-1",)))
    assert result.abstained
    assert "opening_deductions_exceed_gross_area" in result.blocking_reasons


def test_duplicate_physical_opening_deduction_is_blocked() -> None:
    d1 = _deduction("OP-1", 1.0)
    result = _build(deductions=(d1, d1), completion=_complete(("OP-1",)))
    assert result.abstained
    assert "duplicate_opening_deduction_identity" in result.blocking_reasons


def test_stale_completion_snapshot_is_diagnosed() -> None:
    ev = _complete(("OP-1",))
    stale = EvidenceAtom(
        evidence_id=ev.evidence_id,
        document_id=ev.document_id,
        page_id=ev.page_id,
        viewport_id=ev.viewport_id,
        kind=ev.kind,
        method=ev.method,
        confidence=ev.confidence,
        status=ev.status,
        metadata={**dict(ev.metadata), "evidence_snapshot_id": "old"},
    )
    result = _build(deductions=(_deduction("OP-1", 1.0),), completion=stale)
    assert result.abstained
    assert "opening_set_completion_evidence_snapshot_mismatch" in result.blocking_reasons


def test_deterministic_replay() -> None:
    d1 = _deduction("OP-1", 1.2)
    first = _build(deductions=(d1,), completion=_complete(("OP-1",)))
    replay = _build(deductions=(d1,), completion=_complete(("OP-1",)))
    assert first.to_dict() == replay.to_dict()


@pytest.mark.parametrize("value", (float("nan"), float("inf"), -0.01))
def test_invalid_opening_deduction_is_rejected_by_quantity_contract(
    value: float,
) -> None:
    # QuantityEvidence is sealed before any downstream wall arithmetic.
    with pytest.raises(ValueError, match="quantity value must be finite"):
        _deduction("OP-1", value)


@pytest.mark.parametrize("value", (float("nan"), float("inf"), -2.0))
def test_invalid_gross_area_is_rejected_by_quantity_contract(
    value: float,
) -> None:
    with pytest.raises(ValueError, match="quantity value must be finite"):
        _gross(value)


def test_zero_gross_area_stays_blocked_at_net_wall_measurement_gate() -> None:
    # Zero is representable in the generic quantity contract, but not an
    # admissible measured wall gross area from which net m² can be minted.
    result = _build(
        deductions=(_deduction("OP-1", 1.0),),
        completion=_complete(("OP-1",)),
        gross=_gross(0.0),
    )
    assert result.abstained and result.value is None
    assert "gross_wall_area_value_invalid" in result.blocking_reasons


@pytest.mark.parametrize(
    ("target", "expected"),
    (
        ("gross", "invalid_gross_wall_area_unit"),
        ("deduction", "invalid_opening_deduction_unit"),
    ),
)
def test_incorrect_area_units_are_rejected_at_net_wall_boundary(
    target: str, expected: str,
) -> None:
    deduction = _deduction("OP-1", 1.0)
    gross = _gross()
    if target == "gross":
        gross = replace(gross, unit="ft2")
    else:
        deduction = replace(deduction, unit="ft2")
    result = _build(
        gross=gross, deductions=(deduction,),
        completion=_complete(("OP-1",)),
    )
    assert result.abstained and result.value is None
    assert expected in result.blocking_reasons


@pytest.mark.parametrize(
    ("metadata_key", "expected"),
    (
        ("source_sha256", "opening_deduction_source_sha_mismatch"),
        ("revision_id", "opening_deduction_revision_mismatch"),
        ("evidence_snapshot_id", "opening_deduction_evidence_snapshot_mismatch"),
        ("canonical_graph_snapshot_id", "opening_deduction_graph_snapshot_mismatch"),
        ("viewport_id", "opening_deduction_viewport_mismatch"),
    ),
)
def test_foreign_opening_deduction_provenance_stays_abstained(
    metadata_key: str, expected: str,
) -> None:
    deduction = _deduction("OP-1", 1.0)
    copied = replace(
        deduction,
        metadata={**dict(deduction.metadata), metadata_key: "foreign-owner"},
    )
    result = _build(
        deductions=(copied,), completion=_complete(("OP-1",)),
    )
    assert result.abstained and result.value is None
    assert expected in result.blocking_reasons


def test_two_quantity_ids_for_one_physical_opening_are_not_double_deducted() -> None:
    source = _deduction("OP-1", 1.25)
    replay = replace(source, quantity_id="different-quantity-id")
    result = _build(
        deductions=(source, replay), completion=_complete(("OP-1",)),
    )
    assert result.abstained
    assert result.value is None
    assert "duplicate_opening_deduction_identity" in result.blocking_reasons
