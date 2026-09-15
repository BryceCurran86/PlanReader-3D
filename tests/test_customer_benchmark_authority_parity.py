"""C14 attack tests: customer/benchmark shared SHADOW authority parity seam."""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Optional, Sequence

import fitz
import pytest

from pb_customer_benchmark_authority_parity import (
    SHADOW_AUTHORITY_BLOCKED,
    SHADOW_AUTHORITY_PROVISIONAL_LIVE_ONLY,
    collect_parity_shadow_for_pdf,
    decide_parity,
    publication_decision_for_prediction,
    takeoff_row_candidate_from_prediction,
)
from pb_geometry_takeoff_model import AuthorityStatus
from pb_legacy_extractor_adapter import LegacyExtractorAdapter
from pb_planreader_pdf_extractor import (
    ExtractedPrediction,
    extracted_prediction_publication_blocked,
    publishable_prediction_quantity,
)


def _pred(**overrides: Any) -> ExtractedPrediction:
    base: dict[str, Any] = {
        "tag": "D1",
        "trade_type": "doors",
        "description": "door",
        "quantity": 2.0,
        "unit": "NO",
        "confidence": 0.5,
        "source_page": 1,
        "dimensions": [900.0, 2100.0],
        "metadata": {},
    }
    base.update(overrides)
    return ExtractedPrediction(**base)


def test_blocked_none_quantity_diagnostic_without_takeoff_row() -> None:
    pred = _pred(
        quantity=None,
        confidence=0.0,
        dimensions=None,
        metadata={
            "publication_blocked": True,
            "reconciliation_status": "conflict_manual_review",
        },
    )
    decision = decide_parity(pred)
    assert decision.claim.publication_blocked is True
    assert decision.claim.quantity is None
    assert decision.claim.publishable_quantity is None
    assert decision.shadow_authority == SHADOW_AUTHORITY_BLOCKED
    assert decision.takeoff_row is None
    assert takeoff_row_candidate_from_prediction(pred) is None
    # Never invent zero
    assert 0 not in (decision.claim.quantity, decision.claim.publishable_quantity)
    assert 0.0 not in (decision.claim.quantity, decision.claim.publishable_quantity)


def test_extraction_failed_none_quantity_same_behavior() -> None:
    pred = _pred(
        quantity=None,
        confidence=0.0,
        dimensions=None,
        metadata={"extraction_status": "extraction_failed"},
    )
    decision = decide_parity(pred)
    assert decision.claim.publication_blocked is True
    assert decision.claim.quantity is None
    assert decision.takeoff_row is None
    assert decision.shadow_authority == SHADOW_AUTHORITY_BLOCKED


def test_measurable_conflict_retains_diagnostic_values_not_publishable() -> None:
    pred = _pred(
        quantity=3.0,
        metadata={
            "publication_blocked": True,
            "reconciliation_status": "conflict_manual_review",
            "scoped_claims": [
                {"tag": "D1", "quantity": 2.0, "source_page": 1},
                {"tag": "D1", "quantity": 3.0, "source_page": 2},
            ],
            "blocking_reason": "quantity_conflict",
        },
    )
    decision = decide_parity(pred)
    assert decision.claim.publication_blocked is True
    assert decision.claim.publishable_quantity is None
    assert decision.claim.quantity == 3.0
    assert decision.takeoff_row is not None
    assert decision.takeoff_row.value == 3.0
    assert decision.takeoff_row.authority_status == AuthorityStatus.BLOCKED.value
    assert decision.takeoff_row.is_publishable is False
    assert decision.takeoff_row.source_type == "blocked"


def test_confidence_one_blocked_remains_blocked() -> None:
    pred = _pred(
        quantity=None,
        confidence=1.0,
        metadata={
            "publication_blocked": True,
            "reconciliation_status": "conflict_manual_review",
        },
    )
    decision = decide_parity(pred)
    assert decision.shadow_authority == SHADOW_AUTHORITY_BLOCKED
    assert decision.claim.publishable_quantity is None
    assert decision.takeoff_row is None


def test_unblocked_live_prediction_never_becomes_firm() -> None:
    pred = _pred(quantity=4.0, confidence=0.99)
    decision = decide_parity(pred)
    assert decision.claim.publication_blocked is False
    assert decision.claim.publishable_quantity == 4.0
    assert decision.shadow_authority == SHADOW_AUTHORITY_PROVISIONAL_LIVE_ONLY
    assert decision.takeoff_row is not None
    assert decision.takeoff_row.authority_status != AuthorityStatus.FIRM.value
    assert decision.takeoff_row.is_publishable is False
    assert decision.takeoff_row.authority_status == AuthorityStatus.PROVISIONAL.value


def test_same_prediction_matches_extractor_publication_gates() -> None:
    cases = [
        _pred(quantity=None, metadata={"publication_blocked": True}),
        _pred(quantity=None, metadata={"extraction_status": "extraction_failed"}),
        _pred(
            quantity=2.0,
            metadata={"reconciliation_status": "conflict_manual_review"},
        ),
        _pred(quantity=5.0, confidence=0.7),
    ]
    for pred in cases:
        blocked, publishable = publication_decision_for_prediction(pred)
        assert blocked is extracted_prediction_publication_blocked(pred)
        assert publishable == publishable_prediction_quantity(pred)
        claim = decide_parity(pred).claim
        assert claim.publication_blocked is blocked
        assert claim.publishable_quantity == publishable


def test_parity_collector_does_not_mutate_pred_dict(tmp_path: Path) -> None:
    pdf = tmp_path / "plan.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((40, 40), "GROUND FLOOR PLAN\nSCALE 1:100\n")
    doc.save(pdf)
    doc.close()

    original = [
        _pred(tag="W1", trade_type="windows", quantity=2.0),
        _pred(
            tag="D2",
            quantity=None,
            metadata={"publication_blocked": True},
        ),
    ]
    frozen = copy.deepcopy([p.to_dict() for p in original])

    class _RecordingExtractor:
        def __init__(self) -> None:
            self.pred_dict = {p.tag: p for p in original}

        def extract_from_pdf(
            self, pdf_path: Path | str, pages: Optional[Sequence[int]] = None
        ) -> list[ExtractedPrediction]:
            return list(self.pred_dict.values())

    recorder = _RecordingExtractor()
    adapter = LegacyExtractorAdapter(extractor_factory=lambda: recorder)
    shadow = collect_parity_shadow_for_pdf(pdf, adapter=adapter)
    assert shadow["status"] == "collected"
    assert [p.to_dict() for p in original] == frozen
    assert recorder.pred_dict["W1"].quantity == 2.0
    assert recorder.pred_dict["D2"].quantity is None


def test_adding_conflict_cannot_strengthen_authority() -> None:
    clean = _pred(quantity=2.0, confidence=0.9)
    before = decide_parity(clean)
    assert before.shadow_authority == SHADOW_AUTHORITY_PROVISIONAL_LIVE_ONLY
    assert before.takeoff_row is not None
    assert before.takeoff_row.authority_status != AuthorityStatus.FIRM.value

    conflicted = _pred(
        quantity=2.0,
        confidence=0.9,
        metadata={
            "publication_blocked": True,
            "reconciliation_status": "conflict_manual_review",
        },
    )
    after = decide_parity(conflicted)
    assert after.shadow_authority == SHADOW_AUTHORITY_BLOCKED
    assert after.claim.publishable_quantity is None
    # Strengthening would mean FIRM or publishable; conflict must not do that
    if after.takeoff_row is not None:
        assert after.takeoff_row.authority_status == AuthorityStatus.BLOCKED.value
        assert after.takeoff_row.is_publishable is False


def test_removing_provenance_cannot_strengthen_authority() -> None:
    with_prov = _pred(
        quantity=2.0,
        metadata={"merge_source": "schedule", "scoped_claims": [{"tag": "D1"}]},
    )
    without_prov = _pred(quantity=2.0, metadata={})
    before = decide_parity(with_prov)
    after = decide_parity(without_prov)
    assert before.takeoff_row is not None
    assert after.takeoff_row is not None
    assert after.takeoff_row.authority_status != AuthorityStatus.FIRM.value
    assert after.takeoff_row.is_publishable is False
    # Removing provenance must not raise authority above prior shadow state
    rank = {
        AuthorityStatus.BLOCKED.value: 0,
        AuthorityStatus.PROVISIONAL.value: 1,
        AuthorityStatus.REVIEW_REQUIRED.value: 1,
        AuthorityStatus.FIRM.value: 2,
    }
    assert rank[after.takeoff_row.authority_status] <= rank[before.takeoff_row.authority_status]


def test_parity_module_does_not_import_streamlit_or_jobhub_publish() -> None:
    import ast
    import inspect

    import pb_customer_benchmark_authority_parity as mod

    tree = ast.parse(inspect.getsource(mod))
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    forbidden = (
        "streamlit",
        "pb_planreader_v133_app",
        "pb_planreader_3d_app",
        "pb_jobhub_publishing_pipeline",
        "pb_jobhub_publishing_contract",
        "pb_benchmark_accuracy_engine",
    )
    for name in imported:
        assert not any(name == f or name.startswith(f + ".") for f in forbidden)


def test_legacy_adapter_preserves_none_quantity_without_coercion() -> None:
    snap = LegacyExtractorAdapter.__annotations__  # noqa: F841 — touch module
    from pb_legacy_extractor_adapter import LegacyPredictionSnapshot

    snapshot = LegacyPredictionSnapshot.from_prediction(
        _pred(quantity=None, metadata={"publication_blocked": True})
    )
    assert snapshot.quantity is None
    assert snapshot.to_dict()["quantity"] is None
