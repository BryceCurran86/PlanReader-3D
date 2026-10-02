from __future__ import annotations

import hashlib
import json

import pytest

from pb_migration_contracts import QuantityEvidence
from pb_quantity_takeoff_adapter import CommercialTakeoffSourceTrace
from pb_sealed_source_run_export import (
    SEALED_SOURCE_RUN_SCHEMA_VERSION,
    SealedSourceRunError,
    seal_quantity_evidence,
    seal_source_run,
)


SHA = "a" * 64


def _quantity(
    quantity_id: str = "qty-1",
    *,
    value: float | None = 10.0,
    abstained: bool = False,
    input_entity_ids: tuple[str, ...] = ("canonical-floor-1",),
    evidence_ids: tuple[str, ...] = ("ev-1",),
    metadata: dict | None = None,
) -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id=quantity_id,
        family="room_area",
        semantic_key=f"floor:{quantity_id}",
        value=value,
        unit="m2",
        input_entity_ids=input_entity_ids,
        formula="polygon_area",
        formula_version="1",
        evidence_ids=evidence_ids,
        authority="scaled_geometry",
        status="firm" if not abstained else "abstained",
        confidence=1.0,
        abstained=abstained,
        blocking_reasons=("source_open",) if abstained else (),
        metadata=metadata or {},
    )


def _trace(
    *,
    project_id: str = "project-a",
    canonical_entity_ids: tuple[str, ...] = ("canonical-floor-1",),
    evidence_ids: tuple[str, ...] = ("ev-1",),
    source_sha256: str = SHA,
    revision_id: str = "rev-a",
) -> CommercialTakeoffSourceTrace:
    return CommercialTakeoffSourceTrace(
        workspace_id=1,
        project_id=project_id,
        document_id="doc-a",
        source_sha256=source_sha256,
        source_page="A100 / p1",
        viewport_id="vp-a100",
        revision_id=revision_id,
        current_revision_id=revision_id,
        evidence_ids=evidence_ids,
        canonical_entity_ids=canonical_entity_ids,
    )


def _verify_fingerprint(payload: dict) -> None:
    claimed = payload["fingerprint"]
    clean = dict(payload)
    clean.pop("fingerprint")
    text = json.dumps(
        clean,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )
    assert claimed == hashlib.sha256(text.encode("utf-8")).hexdigest()


def test_sealed_quantity_is_benchmark_neutral_and_tamper_evident() -> None:
    sealed = seal_quantity_evidence(
        _quantity(),
        trace=_trace(),
        project_id="project-a",
    )

    assert sealed["schema_version"] == SEALED_SOURCE_RUN_SCHEMA_VERSION
    assert sealed["object_identity_refs"] == ["canonical-floor-1"]
    assert sealed["trace_canonical_entity_ids"] == ["canonical-floor-1"]
    assert sealed["evidence_ids"] == ["ev-1"]
    assert sealed["trace_evidence_ids"] == ["ev-1"]
    assert sealed["lineage_ok"] is True
    assert sealed["lineage_reason_codes"] == []
    assert "benchmark_item_id" not in sealed
    assert "expected_quantity" not in sealed
    _verify_fingerprint(sealed)


def test_abstention_stays_none_and_never_becomes_zero() -> None:
    sealed = seal_quantity_evidence(
        _quantity(value=None, abstained=True),
        trace=_trace(),
        project_id="project-a",
    )

    assert sealed["abstained"] is True
    assert sealed["value"] is None
    assert sealed["blocking_reasons"] == ["source_open"]
    _verify_fingerprint(sealed)


def test_missing_entity_and_evidence_trace_marks_lineage_conflict() -> None:
    sealed = seal_quantity_evidence(
        _quantity(
            input_entity_ids=("canonical-floor-1", "canonical-room-1"),
            evidence_ids=("ev-1", "ev-2"),
        ),
        trace=_trace(
            canonical_entity_ids=("canonical-floor-1",),
            evidence_ids=("ev-1",),
        ),
        project_id="project-a",
    )

    assert sealed["lineage_ok"] is False
    assert "trace_missing_quantity_entities:canonical-room-1" in sealed[
        "lineage_reason_codes"
    ]
    assert "trace_missing_quantity_evidence:ev-2" in sealed[
        "lineage_reason_codes"
    ]


def test_explicit_quantity_metadata_identity_mismatch_is_preserved_as_conflict() -> None:
    sealed = seal_quantity_evidence(
        _quantity(metadata={"document_id": "different-document"}),
        trace=_trace(),
        project_id="project-a",
    )

    assert sealed["lineage_ok"] is False
    assert "quantity_metadata_document_id_mismatch" in sealed[
        "lineage_reason_codes"
    ]


def test_run_is_deterministic_and_sorted_by_quantity_id() -> None:
    q2 = _quantity("qty-2")
    q1 = _quantity("qty-1")
    traces = {"qty-1": _trace(), "qty-2": _trace()}

    first = seal_source_run(
        run_id="run-a",
        project_id="project-a",
        quantities=(q2, q1),
        traces_by_quantity_id=traces,
    )
    second = seal_source_run(
        run_id="run-a",
        project_id="project-a",
        quantities=(q1, q2),
        traces_by_quantity_id=traces,
    )

    assert first == second
    assert [row["quantity_id"] for row in first["quantities"]] == [
        "qty-1",
        "qty-2",
    ]
    assert first["source_sha256s"] == [SHA]
    assert first["revision_ids"] == ["rev-a"]
    _verify_fingerprint(first)
    for row in first["quantities"]:
        _verify_fingerprint(row)


def test_project_mismatch_fails_closed() -> None:
    with pytest.raises(SealedSourceRunError, match="project_id"):
        seal_quantity_evidence(
            _quantity(),
            trace=_trace(project_id="other-project"),
            project_id="project-a",
        )


def test_missing_trace_fails_closed() -> None:
    with pytest.raises(SealedSourceRunError, match="missing source trace"):
        seal_source_run(
            run_id="run-a",
            project_id="project-a",
            quantities=(_quantity(),),
            traces_by_quantity_id={},
        )


def test_duplicate_quantity_ids_fail_closed() -> None:
    with pytest.raises(SealedSourceRunError, match="quantity_id values must be unique"):
        seal_source_run(
            run_id="run-a",
            project_id="project-a",
            quantities=(_quantity(), _quantity()),
            traces_by_quantity_id={"qty-1": _trace()},
        )


def test_empty_run_fails_closed() -> None:
    with pytest.raises(SealedSourceRunError, match="at least one quantity"):
        seal_source_run(
            run_id="run-a",
            project_id="project-a",
            quantities=(),
            traces_by_quantity_id={},
        )
