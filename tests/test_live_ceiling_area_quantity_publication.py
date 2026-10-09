from __future__ import annotations

from dataclasses import replace

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
import pb_live_ceiling_area_source_closed_export as ceiling_export
from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_ceiling_area_customer_projection import (
    project_live_ceiling_area_customer_rows,
)
from pb_live_ceiling_area_quantity_publication import (
    LIVE_CEILING_AREA_QUANTITY_RESOLVED,
    publish_live_ceiling_area_quantities,
)
from pb_live_ceiling_lining_integration import (
    LiveCanonicalCeilingSurfaceObject,
    LiveCeilingLiningResult,
)
from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
from pb_migration_contracts import EvidenceResolutionStatus, QuantityEvidence
from pb_takeoff_coverage_audit_adapter import build_runtime_coverage_publication


SOURCE_SHA = "a" * 64


def _shadow_quantity() -> QuantityEvidence:
    return QuantityEvidence(
        quantity_id="qty-shadow-ceiling-1",
        family="ceiling_lining",
        semantic_key="ceiling_lining:room-1",
        value=13.270425,
        unit="m2",
        input_entity_ids=("room-1",),
        formula="reuse_same_scope_authoritative_area_with_explicit_ceiling_finish",
        formula_version="1",
        evidence_ids=("ev-dim-h", "ev-dim-v", "ev-finish"),
        authority=MeasurementAuthorityType.MODEL_DERIVED.value,
        status=AuthorityStatus.PROVISIONAL.value,
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        metadata={
            "source_sha256": SOURCE_SHA,
            "revision_id": "rev-1",
            "page_no": 1,
            "viewport_id": "vp-1",
            "upstream_area_quantity_id": "qty-room-area-1",
            "shadow_only": True,
            "commercial_projection_allowed": False,
        },
    )


def _ceiling(
    *,
    authority: str = MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
    physical_scale_record_id: str = "",
    figured_dimension_ids: tuple[str, ...] = ("dim-h", "dim-v"),
) -> LiveCanonicalCeilingSurfaceObject:
    return LiveCanonicalCeilingSurfaceObject(
        canonical_ceiling_id="canonical-ceiling-1",
        document_id="doc-1",
        snapshot_id="snapshot-1",
        room_entity_id="room-1",
        source_page=1,
        viewport_id="vp-1",
        source_sha256=SOURCE_SHA,
        revision_id="rev-1",
        polygon_pdf_pts=((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)),
        area_m2=13.270425,
        finish_descriptor="plasterboard",
        room_area_quantity_id="qty-room-area-1",
        ceiling_quantity_id="qty-shadow-ceiling-1",
        source_room_index_id="room-index-1",
        evidence_ids=("ev-dim-h", "ev-dim-v", "ev-finish"),
        physical_scale_record_id=physical_scale_record_id,
        measurement_authority=authority,
        figured_dimension_ids=figured_dimension_ids,
    )


def _result(ceiling=None, shadow=None) -> LiveCeilingLiningResult:
    return LiveCeilingLiningResult(
        status=EvidenceResolutionStatus.CORROBORATED,
        reason_codes=("live_ceiling_lining_resolved",),
        claims=(),
        canonical_ceilings=((ceiling or _ceiling()),),
        quantity_evidence=((shadow or _shadow_quantity()),),
    )


def test_documented_dimension_canonical_ceiling_publishes_firm_without_scale() -> None:
    quantities = publish_live_ceiling_area_quantities(_result())

    assert len(quantities) == 1
    quantity = quantities[0]
    assert quantity.family == "ceiling_lining"
    assert quantity.value == 13.270425
    assert quantity.unit == "m2"
    assert quantity.input_entity_ids == ("canonical-ceiling-1",)
    assert quantity.authority == MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
    assert quantity.status == AuthorityStatus.FIRM.value
    assert quantity.abstained is False
    assert quantity.reason_codes == (LIVE_CEILING_AREA_QUANTITY_RESOLVED,)
    assert quantity.metadata["figured_dimension_ids"] == ("dim-h", "dim-v")
    assert quantity.metadata["resolved_scale_id"] is None
    assert quantity.metadata["commercial_projection_allowed"] is False
    assert quantity.metadata["quantity_handoff_only"] is True


def test_ceiling_quantity_requires_nonempty_source_and_canonical_receipts() -> None:
    # An empty set previously passed the lineage-subset check vacuously.
    shadow = replace(_shadow_quantity(), evidence_ids=())
    assert publish_live_ceiling_area_quantities(_result(shadow=shadow)) == ()

    ceiling = replace(_ceiling(), evidence_ids=())
    assert publish_live_ceiling_area_quantities(_result(ceiling=ceiling)) == ()


def test_ceiling_quantity_rejects_invalid_source_confidence() -> None:
    for confidence in (float("nan"), float("inf"), float("-inf"), -0.01, 1.01):
        shadow = replace(_shadow_quantity(), confidence=confidence)
        assert publish_live_ceiling_area_quantities(_result(shadow=shadow)) == ()


def test_scaled_canonical_ceiling_requires_physical_scale_record() -> None:
    missing = _ceiling(
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        physical_scale_record_id="",
        figured_dimension_ids=(),
    )
    assert publish_live_ceiling_area_quantities(_result(ceiling=missing)) == ()

    resolved = replace(
        missing,
        physical_scale_record_id="physical-scale-1",
    )
    quantities = publish_live_ceiling_area_quantities(_result(ceiling=resolved))
    assert len(quantities) == 1
    quantity = quantities[0]
    assert quantity.authority == MeasurementAuthorityType.PDF_SCALED.value
    assert quantity.status == AuthorityStatus.FIRM.value
    assert quantity.metadata["resolved_scale_id"] == "physical-scale-1"
    assert quantity.metadata["figured_dimension_ids"] == ()


def test_documented_dimension_requires_figured_dimension_lineage() -> None:
    ceiling = _ceiling(figured_dimension_ids=())
    assert publish_live_ceiling_area_quantities(_result(ceiling=ceiling)) == ()


def test_shadow_quantity_must_match_exact_upstream_area_identity() -> None:
    shadow = _shadow_quantity()
    shadow = replace(
        shadow,
        metadata={
            **dict(shadow.metadata),
            "upstream_area_quantity_id": "other-room-area",
        },
    )
    assert publish_live_ceiling_area_quantities(_result(shadow=shadow)) == ()


def test_review_or_promoted_quantity_cannot_replace_shadow_lineage() -> None:
    shadow = replace(
        _shadow_quantity(),
        status=AuthorityStatus.REVIEW_REQUIRED.value,
        authority=MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        metadata={
            **dict(_shadow_quantity().metadata),
            "shadow_only": False,
            "commercial_projection_allowed": True,
        },
    )
    assert publish_live_ceiling_area_quantities(_result(shadow=shadow)) == ()


def test_quantity_identity_is_deterministic() -> None:
    first = publish_live_ceiling_area_quantities(_result())
    second = publish_live_ceiling_area_quantities(_result())

    assert len(first) == len(second) == 1
    assert first[0].to_dict() == second[0].to_dict()
    assert first[0].quantity_id == second[0].quantity_id


def test_canonical_ceiling_seals_on_exact_canonical_identity() -> None:
    result = _result()
    quantity = publish_live_ceiling_area_quantities(result)[0]

    traces = ceiling_export.build_live_ceiling_area_source_traces(
        result,
        workspace_id=7,
        project_id="source-project",
    )
    trace = traces[quantity.quantity_id]
    assert trace.canonical_entity_ids == ("canonical-ceiling-1",)
    assert trace.source_sha256 == SOURCE_SHA
    assert trace.revision_id == "rev-1"
    assert trace.current_revision_id == "rev-1"
    assert trace.viewport_id == "vp-1"
    assert trace.source_page == "1"
    assert set(quantity.evidence_ids).issubset(set(trace.evidence_ids))

    run = ceiling_export.seal_live_ceiling_area_run(
        result,
        workspace_id=7,
        project_id="source-project",
    )
    assert len(run.quantities) == 1
    row = run.quantities[0]
    assert row.quantity_id == quantity.quantity_id
    assert row.family == "ceiling_lining"
    assert row.value == 13.270425
    assert row.object_identity_refs == ("canonical-ceiling-1",)
    assert row.trace_canonical_entity_ids == ("canonical-ceiling-1",)
    assert row.lineage_ok is True


def test_canonical_ceiling_sealing_is_deterministic() -> None:
    result = _result()
    first = ceiling_export.seal_live_ceiling_area_run(
        result,
        workspace_id=7,
        project_id="source-project",
    )
    second = ceiling_export.seal_live_ceiling_area_run(
        result,
        workspace_id=7,
        project_id="source-project",
    )

    assert first.run_id == second.run_id
    assert first.fingerprint == second.fingerprint
    assert first.to_json() == second.to_json()


def test_canonical_ceiling_sealing_rejects_trace_identity_mismatch() -> None:
    bad = replace(
        _ceiling(),
        canonical_ceiling_id="canonical-ceiling-other",
    )
    result = _result(ceiling=bad)

    assert publish_live_ceiling_area_quantities(result)[0].input_entity_ids == (
        "canonical-ceiling-other",
    )


def test_canonical_ceiling_reaches_quantified_without_customer_row() -> None:
    result = _result()
    quantities = publish_live_ceiling_area_quantities(result)
    summaries, gaps = collect_live_canonical_coverage(
        objects=result.canonical_ceilings,
        quantities=quantities,
        output_rows=(),
        registry_run_scope="canonical-ceiling-quantity",
    )

    assert gaps == {}
    assert len(summaries) == 1
    record = summaries[0].object_records[0]
    assert record.object_id == "canonical-ceiling-1"
    assert record.quantity_ids == (quantities[0].quantity_id,)

    report = build_runtime_coverage_publication(
        summaries,
        family_gaps=gaps,
    )
    family = report["family_reports"]["ceiling"]
    assert family["stage_counts"] == {
        "DETECTED": 1,
        "AUTHENTICATED": 1,
        "CANONICALIZED": 1,
        "QUANTIFIED": 1,
        "PUBLISHED": 0,
    }


def test_legacy_canonical_ceiling_seal_reaches_one_persisted_customer_row() -> None:
    result = _result()
    run = ceiling_export.seal_live_ceiling_area_run(
        result,
        workspace_id=7,
        project_id="source-project",
    )
    rows = project_live_ceiling_area_customer_rows(
        result,
        workspace_id=7,
        project_id="source-project",
    )

    assert len(run.quantities) == len(rows) == 1
    row = rows[0]
    assert row["quantity_id"] == run.quantities[0].quantity_id
    assert row["quantity_family"] == "ceiling_lining"
    assert row["quantity_status"] == "To review"
    assert row["origin"] == "AI"
    assert row["row_role"] == "ceiling_area"
    assert row["finish_system"] == "plasterboard"
    assert row["measurement_method"] == "figured_dimension"
    assert row["figured_dimension_ids"] == ["dim-h", "dim-v"]

    live_report = verify_sealed_customer_output(run, rows)
    assert live_report.valid_quantity_count == 1
    assert live_report.customer_row_count == 1

    persisted = {
        "workspace_id": row["workspace_id"],
        "section": row["section"],
        "element": row["element"],
        "location": row["location"],
        "substrate": row["substrate"],
        "finish_system": row["finish_system"],
        "quantity": row["quantity"],
        "unit": "m²",
        "quantity_status": row["quantity_status"],
        "source_page": row["source_page"],
        "source_reference": "PB Auto Geometry v1.2.19 · " + row["source_reference"],
        "inclusion_status": row["inclusion_status"],
        "confidence": "Documented",
        "notes": row["notes"],
        "row_role": row["row_role"],
    }
    persisted_report = verify_sealed_customer_output(run, [persisted])
    assert persisted_report.verified_quantity_ids == (
        run.quantities[0].quantity_id,
    )


def test_scaled_legacy_ceiling_customer_projection_preserves_scale_authority() -> None:
    ceiling = _ceiling(
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        physical_scale_record_id="physical-scale-1",
        figured_dimension_ids=(),
    )
    result = _result(ceiling=ceiling)
    run = ceiling_export.seal_live_ceiling_area_run(
        result,
        workspace_id=7,
        project_id="source-project",
    )
    rows = project_live_ceiling_area_customer_rows(
        result,
        workspace_id=7,
        project_id="source-project",
    )

    assert len(run.quantities) == len(rows) == 1
    row = rows[0]
    assert row["quantity_id"] == run.quantities[0].quantity_id
    assert row["measurement_method"] == "scaled_geometry"
    assert row["resolved_scale_id"] == "physical-scale-1"
    assert row["scale_status"] == "resolved"
    assert row["scale_conflicts"] == []

    report = verify_sealed_customer_output(run, rows)
    assert report.verified_quantity_ids == (run.quantities[0].quantity_id,)


def test_exact_shadow_quantity_replay_is_idempotent() -> None:
    shadow = _shadow_quantity()
    result = replace(
        _result(),
        quantity_evidence=(shadow, shadow),
    )
    assert publish_live_ceiling_area_quantities(result) == (
        publish_live_ceiling_area_quantities(_result())
    )


def test_conflicting_shadow_quantity_id_never_publishes_ceiling_area() -> None:
    shadow = _shadow_quantity()
    conflicting = (
        replace(shadow, value=14.0),
        replace(
            shadow,
            metadata={**shadow.metadata, "viewport_id": "conflicting-viewport"},
        ),
        replace(shadow, evidence_ids=("ev-dim-h", "ev-different", "ev-finish")),
    )
    for other in conflicting:
        for values in (
            (shadow, other),
            (other, shadow),
            (shadow, other, shadow),
        ):
            result = replace(_result(), quantity_evidence=values)
            assert publish_live_ceiling_area_quantities(result) == ()



def test_duplicate_canonical_ceiling_cannot_hide_in_abstained_candidate() -> None:
    firm = _ceiling()
    unsupported = replace(
        firm,
        metric_area_complete=False,
        area_m2=0.0,
    )
    assert len(publish_live_ceiling_area_quantities(_result(ceiling=firm))) == 1
    assert publish_live_ceiling_area_quantities(_result(ceiling=unsupported)) == ()
    result = replace(
        _result(),
        canonical_ceilings=(firm, unsupported),
    )
    import pytest
    with pytest.raises(ValueError, match="duplicate canonical ceiling identity"):
        publish_live_ceiling_area_quantities(result)


def test_duplicate_unmeasured_ceiling_id_is_still_quarantined() -> None:
    unresolved = replace(_ceiling(), metric_area_complete=False, area_m2=0.0)
    result = replace(
        _result(),
        canonical_ceilings=(unresolved, unresolved),
    )
    import pytest
    with pytest.raises(ValueError, match="duplicate canonical ceiling identity"):
        publish_live_ceiling_area_quantities(result)


def test_distinct_unresolved_ceiling_does_not_suppress_firm_ceiling() -> None:
    firm = _ceiling()
    unrelated = replace(
        _ceiling(),
        canonical_ceiling_id="canonical-ceiling-unmeasured",
        ceiling_quantity_id="shadow-unavailable",
        metric_area_complete=False,
        area_m2=0.0,
    )
    result = replace(_result(), canonical_ceilings=(firm, unrelated))
    quantities = publish_live_ceiling_area_quantities(result)
    assert len(quantities) == 1
    assert quantities[0].input_entity_ids == (firm.canonical_ceiling_id,)


def test_provisional_ceiling_source_unit_must_be_square_metres() -> None:
    non_metric = replace(_shadow_quantity(), unit="ft2")
    result = _result(shadow=non_metric)
    assert publish_live_ceiling_area_quantities(result) == ()
