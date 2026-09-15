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
    diagnostic_claim_quantity_id,
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


def test_same_tag_same_page_distinct_evidence_keeps_distinct_shadow_ids() -> None:
    """Same tag + page must never collapse distinct physical/extractor claims."""
    # Attack 1: same tag + page + different bbox → different shadow IDs.
    left = _pred(
        tag="D1",
        quantity=1.0,
        source_page=1,
        bounding_box=[10.0, 20.0, 30.0, 40.0],
        metadata={},
    )
    right = _pred(
        tag="D1",
        quantity=1.0,
        source_page=1,
        bounding_box=[100.0, 200.0, 130.0, 240.0],
        metadata={},
    )
    left_id = diagnostic_claim_quantity_id(left)
    right_id = diagnostic_claim_quantity_id(right)
    assert left_id != right_id
    assert "parity-shadow:D1:1" not in (left_id, right_id)

    # Attack 2: same tag + page + different raw evidence reference → different IDs.
    ref_a = _pred(
        tag="D1",
        quantity=1.0,
        source_page=1,
        bounding_box=None,
        metadata={"raw_evidence_ref": "door_instance_a"},
    )
    ref_b = _pred(
        tag="D1",
        quantity=1.0,
        source_page=1,
        bounding_box=None,
        metadata={"raw_evidence_ref": "door_instance_b"},
    )
    assert diagnostic_claim_quantity_id(ref_a) != diagnostic_claim_quantity_id(ref_b)

    # Attack 3: same complete diagnostic claim replayed twice → identical ID.
    assert diagnostic_claim_quantity_id(left) == diagnostic_claim_quantity_id(
        _pred(
            tag="D1",
            quantity=1.0,
            source_page=1,
            bounding_box=[10.0, 20.0, 30.0, 40.0],
            metadata={},
        )
    )

    # Distinct scoped-claim provenance also must not collapse.
    scoped_a = _pred(
        tag="W1",
        trade_type="windows",
        quantity=2.0,
        source_page=3,
        bounding_box=None,
        metadata={
            "scoped_claims": [{"tag": "W1", "quantity": 2.0, "source_page": 3, "ref": "a"}],
        },
    )
    scoped_b = _pred(
        tag="W1",
        trade_type="windows",
        quantity=2.0,
        source_page=3,
        bounding_box=None,
        metadata={
            "scoped_claims": [{"tag": "W1", "quantity": 2.0, "source_page": 3, "ref": "b"}],
        },
    )
    assert diagnostic_claim_quantity_id(scoped_a) != diagnostic_claim_quantity_id(scoped_b)


def test_confidence_alone_does_not_establish_identity_or_authority() -> None:
    """Attack 4: confidence changes alone must not establish physical identity."""
    low = _pred(
        tag="D1",
        quantity=1.0,
        source_page=1,
        bounding_box=[10.0, 20.0, 30.0, 40.0],
        confidence=0.1,
        metadata={"raw_evidence_ref": "same_ref"},
    )
    high = _pred(
        tag="D1",
        quantity=1.0,
        source_page=1,
        bounding_box=[10.0, 20.0, 30.0, 40.0],
        confidence=0.99,
        metadata={"raw_evidence_ref": "same_ref"},
    )
    assert diagnostic_claim_quantity_id(low) == diagnostic_claim_quantity_id(high)
    # Higher confidence still cannot create FIRM / publishable authority.
    high_row = takeoff_row_candidate_from_prediction(high)
    assert high_row is not None
    assert high_row.authority_status != AuthorityStatus.FIRM.value
    assert high_row.is_publishable is False


def test_unresolved_evidence_does_not_prove_physical_equivalence() -> None:
    """Attack 5: same tag/dimensions/page without evidence identity → no PROVEN_SAME."""
    from pb_planreader_pdf_extractor import _predictions_are_proven_same_type_claim

    a = _pred(
        tag="D1",
        quantity=1.0,
        source_page=1,
        dimensions=[900.0, 2100.0],
        bounding_box=None,
        metadata={},  # no raw_evidence_ref
    )
    b = _pred(
        tag="D1",
        quantity=1.0,
        source_page=1,
        dimensions=[900.0, 2100.0],
        bounding_box=None,
        metadata={},
    )
    assert _predictions_are_proven_same_type_claim(a, b) is False
    # Equal diagnostic IDs (content-addressed) must not be treated as physical proof.
    assert diagnostic_claim_quantity_id(a) == diagnostic_claim_quantity_id(b)
    # Parity seam still does not emit FIRM for either claim.
    for pred in (a, b):
        row = takeoff_row_candidate_from_prediction(pred)
        assert row is not None
        assert row.authority_status != AuthorityStatus.FIRM.value
        assert row.is_publishable is False


def test_distinct_same_tag_projections_remain_non_firm_non_publishable() -> None:
    """Attack 6: distinct same-tag/page projections remain non-FIRM / non-publishable."""
    left = _pred(
        tag="D1",
        quantity=1.0,
        source_page=1,
        bounding_box=[10.0, 20.0, 30.0, 40.0],
        metadata={"raw_evidence_ref": "a"},
    )
    right = _pred(
        tag="D1",
        quantity=1.0,
        source_page=1,
        bounding_box=[100.0, 200.0, 130.0, 240.0],
        metadata={"raw_evidence_ref": "b"},
    )
    left_row = takeoff_row_candidate_from_prediction(left)
    right_row = takeoff_row_candidate_from_prediction(right)
    assert left_row is not None and right_row is not None
    assert left_row.quantity_id != right_row.quantity_id
    for row in (left_row, right_row):
        assert row.authority_status != AuthorityStatus.FIRM.value
        assert row.is_publishable is False
        assert row.authority_status == AuthorityStatus.PROVISIONAL.value


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
