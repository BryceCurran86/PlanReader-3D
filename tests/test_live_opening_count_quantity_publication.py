from __future__ import annotations

from dataclasses import replace
from copy import copy
from types import SimpleNamespace
from unittest.mock import patch

import json
import fitz
import pytest

import pb_auto_geometry_v1219 as auto
from pb_customer_output_verification import verify_sealed_customer_output
from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
from pb_live_opening_count_source_closed_export import (
    build_live_opening_count_source_traces,
    seal_live_opening_count_run,
)
from pb_live_physical_net_wall_integration import (
    collect_live_physical_net_wall_claim,
)
from pb_source_closed_run_export import SourceClosedRunConflictError
from pb_takeoff_coverage_audit_adapter import build_runtime_coverage_publication
from tests.test_live_physical_opening_void_composition import _complete_void_pdf


def _floor_plan_with_schedule_quantity(
    *,
    tag: str = "W1",
    quantity: int | None,
) -> bytes:
    payload = _complete_void_pdf(tag=tag)
    doc = fitz.open(stream=payload, filetype="pdf")
    try:
        page = doc[0]
        # View classification is source-owned; make the synthetic source an
        # explicit floor plan rather than relying on a viewport-name heuristic.
        page.insert_text(fitz.Point(20.0, 24.0), "FLOOR PLAN")
        if quantity is not None:
            # Extend the existing synthetic opening schedule with a real
            # explicit quantity column. The historical default count=1 is not
            # sufficient for the positive commercial path.
            page.insert_text(fitz.Point(680.0, 500.0), "QTY")
            page.insert_text(fitz.Point(680.0, 530.0), str(int(quantity)))
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def test_explicit_schedule_quantity_reaches_live_opening_count_quantity_and_registry(
    tmp_path,
) -> None:
    path = tmp_path / "counted-opening.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))

    claim = collect_live_physical_net_wall_claim(path, pages=(0,))

    assert len(claim.canonical_openings) == 1
    opening = claim.canonical_openings[0]
    assert opening.opening_kind == "window"
    assert opening.type_mark == "W1"

    assert len(claim.opening_count_quantity_evidence) == 1, {
        "claim_reasons": claim.reason_codes,
        "opening": claim.canonical_openings[0].to_dict() if claim.canonical_openings else None,
    }
    quantity = claim.opening_count_quantity_evidence[0]
    assert quantity.family == "opening_count"
    assert quantity.semantic_key == "opening_count:W1"
    assert quantity.value == 1.0
    assert quantity.unit == "ea"
    assert quantity.input_entity_ids == (opening.canonical_opening_id,)
    assert quantity.metadata["schedule_corroborated"] is True
    assert quantity.metadata["opening_mark"] == "W1"

    summaries, gaps = collect_live_canonical_coverage(
        objects=claim.canonical_openings,
        quantities=claim.opening_count_quantity_evidence,
        registry_run_scope="live-opening-count-regression",
    )
    assert summaries
    # Other lifecycle diagnostics may remain for the shared door/window identity
    # family; the count bridge only needs to prove an explicit quantity link.
    records = [
        record
        for summary in summaries
        for record in summary.object_records
        if record.object_id == opening.canonical_opening_id
    ]
    assert len(records) == 1
    assert quantity.quantity_id in records[0].quantity_ids

    report = build_runtime_coverage_publication(summaries, family_gaps=gaps)
    opening_family = report["family_reports"]["opening"]
    assert opening_family["stage_counts"]["QUANTIFIED"] == 1
    assert "explicit_quantity_link_unavailable" not in opening_family["reason_codes"]


def test_explicit_schedule_count_reaches_customer_runtime_row_even_without_wall_quantity(
    tmp_path,
) -> None:
    path = tmp_path / "counted-opening-customer.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert claim.opening_count_quantity_evidence, {
        "claim_reasons": claim.reason_codes,
        "opening": claim.canonical_openings[0].to_dict() if claim.canonical_openings else None,
    }
    count_quantity = claim.opening_count_quantity_evidence[0]

    app = SimpleNamespace(
        lquery=lambda *_args, **_kwargs: [{"id": 1, "path": str(path)}]
    )
    with patch(
        "pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim",
        return_value=claim,
    ):
        wall_rows = auto._try_physical_net_wall_rows(
            app,
            1,
            [{
                "document_id": 1,
                "page_no": 1,
                "selected": 1,
                "page_type": "floor plan",
            }],
            [],
        )

    # The wall fixture has no independent wall-height authority; opening
    # commercial output must not be gated on a successful net-wall row.
    assert wall_rows is None
    opening_rows = app._live_opening_takeoff_rows_by_workspace[1]
    count_rows = [
        dict(zip(auto.TAKEOFF_ROW_FIELDS, row))
        for row in opening_rows
        if count_quantity.quantity_id in str(
            dict(zip(auto.TAKEOFF_ROW_FIELDS, row))["source_reference"]
        )
    ]
    assert len(count_rows) == 1
    row = count_rows[0]
    assert row["section"] == "Openings"
    assert row["element"] == "Window count"
    assert row["location"] == "W1"
    assert row["quantity"] == 1.0
    assert row["unit"] == "ea"
    assert row["quantity_status"] == "To review"
    assert row["inclusion_status"] == "PROVISIONAL"
    provenance = json.loads(row["notes"])
    assert provenance["adapter"] == "commercial_takeoff"
    assert provenance["quantity"]["quantity_id"] == count_quantity.quantity_id
    assert provenance["measurement_authority"]["method"] == "direct_evidence"
    assert provenance["source_trace"]["canonical_entity_ids"] == list(
        count_quantity.input_entity_ids
    )

    sealed = seal_live_opening_count_run(
        claim,
        workspace_id=1,
        project_id="customer-workspace:1",
    )
    verified = verify_sealed_customer_output(sealed, [row])
    assert verified.valid_quantity_count == 1
    assert verified.customer_row_count == 1
    assert verified.verified_quantity_ids == (count_quantity.quantity_id,)


def test_implicit_schedule_default_never_becomes_live_commercial_count(
    tmp_path,
) -> None:
    path = tmp_path / "implicit-count-opening.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=None))

    claim = collect_live_physical_net_wall_claim(path, pages=(0,))

    assert claim.canonical_openings
    assert claim.opening_count_quantity_evidence == ()



def test_authenticated_opening_count_seals_exact_member_lineage(tmp_path) -> None:
    path = tmp_path / "counted-opening-sealed.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert len(claim.opening_count_quantity_evidence) == 1
    assert len(claim.canonical_openings) == 1
    quantity = claim.opening_count_quantity_evidence[0]
    opening = claim.canonical_openings[0]

    traces = build_live_opening_count_source_traces(
        claim,
        workspace_id=7,
        project_id="source-project",
    )
    trace = traces[quantity.quantity_id]
    assert trace.project_id == "source-project"
    assert trace.canonical_entity_ids == quantity.input_entity_ids
    assert set(quantity.evidence_ids).issubset(set(trace.evidence_ids))
    assert trace.metadata["aggregate_source_trace"] is False
    assert tuple(trace.metadata["member_opening_ids"]) == tuple(
        sorted(quantity.input_entity_ids)
    )
    assert trace.metadata["opening_mark"] == "W1"
    assert trace.source_page == opening.page_id
    assert trace.viewport_id == opening.viewport_id

    sealed = seal_live_opening_count_run(
        claim,
        workspace_id=7,
        project_id="source-project",
    )
    assert len(sealed.quantities) == 1
    row = sealed.quantities[0]
    assert row.quantity_id == quantity.quantity_id
    assert row.object_identity_refs == quantity.input_entity_ids
    assert row.value == 1.0
    assert row.unit == "ea"
    assert row.lineage_ok is True


def test_authenticated_opening_count_sealed_run_is_deterministic(tmp_path) -> None:
    path = tmp_path / "counted-opening-deterministic.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))

    first = seal_live_opening_count_run(
        claim,
        workspace_id=7,
        project_id="source-project",
    )
    second = seal_live_opening_count_run(
        claim,
        workspace_id=7,
        project_id="source-project",
    )

    assert first.run_id == second.run_id
    assert first.fingerprint == second.fingerprint
    assert first.to_json() == second.to_json()


def test_opening_count_sealing_rejects_unknown_physical_member(tmp_path) -> None:
    path = tmp_path / "counted-opening-unknown-member.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    quantity = claim.opening_count_quantity_evidence[0]
    damaged = replace(
        quantity,
        input_entity_ids=("unknown-physical-opening",),
    )
    damaged_claim = replace(
        claim,
        opening_count_quantity_evidence=(damaged,),
    )

    with pytest.raises(
        SourceClosedRunConflictError,
        match="unknown physical identity",
    ):
        seal_live_opening_count_run(
            damaged_claim,
            workspace_id=7,
            project_id="source-project",
        )


def test_opening_count_sealing_rejects_missing_member_evidence(tmp_path) -> None:
    path = tmp_path / "counted-opening-missing-evidence.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    quantity = claim.opening_count_quantity_evidence[0]
    opening = claim.canonical_openings[0]
    physical_ids = set(opening.source_observation_ids)
    assert physical_ids
    damaged = replace(
        quantity,
        evidence_ids=tuple(
            value
            for value in quantity.evidence_ids
            if value not in physical_ids
        ),
    )
    damaged_claim = replace(
        claim,
        opening_count_quantity_evidence=(damaged,),
    )

    with pytest.raises(
        SourceClosedRunConflictError,
        match="omits physical member evidence",
    ):
        seal_live_opening_count_run(
            damaged_claim,
            workspace_id=7,
            project_id="source-project",
        )


@pytest.mark.parametrize("corruption", (
    "blank_member", "whitespace_member", "untyped_member",
    "boolean_count", "fractional_count", "empty_quantity_receipt", "duplicate_quantity_receipt",
))
def test_count_sealing_never_drops_corrupt_original_member_or_quantity_evidence(
    tmp_path, corruption,
):
    path = tmp_path / f"opening-count-integrity-{corruption}.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert len(claim.opening_count_quantity_evidence) == 1
    original = claim.opening_count_quantity_evidence[0]
    opening_id = original.input_entity_ids[0]
    forged = copy(original)
    if corruption in {"blank_member", "whitespace_member", "untyped_member"}:
        bad = {"blank_member": "", "whitespace_member": "   ", "untyped_member": 42}[corruption]
        object.__setattr__(forged, "input_entity_ids", (opening_id, bad))
    elif corruption == "boolean_count":
        object.__setattr__(forged, "value", True)
    elif corruption == "fractional_count":
        object.__setattr__(forged, "value", 1.0000000005)
    elif corruption == "empty_quantity_receipt":
        object.__setattr__(forged, "evidence_ids", ())
    else:
        object.__setattr__(forged, "evidence_ids", (*original.evidence_ids, original.evidence_ids[0]))
    with pytest.raises(SourceClosedRunConflictError):
        build_live_opening_count_source_traces(
            replace(claim, opening_count_quantity_evidence=(forged,)),
            workspace_id=7, project_id="source-project",
        )
    assert len(build_live_opening_count_source_traces(
        claim, workspace_id=7, project_id="source-project",
    )) == 1


@pytest.mark.parametrize("bad_sources", (
    (), ("",), ("   ",), ("source-A", "source-A"), (42,),
))
def test_count_sealing_requires_real_original_observation_ids_per_physical_member(
    tmp_path, bad_sources,
):
    path = tmp_path / "count-source-observation-replay.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert len(claim.canonical_openings) == 1
    corrupted = replace(claim.canonical_openings[0], source_observation_ids=bad_sources)
    with pytest.raises(SourceClosedRunConflictError, match="original source observation"):
        build_live_opening_count_source_traces(
            replace(claim, canonical_openings=(corrupted,)),
            workspace_id=7, project_id="source-project",
        )


@pytest.mark.parametrize("field,forged_value", (
    ("unit", "m2"),
    ("unit", "each"),
    ("status", "provisional"),
    ("status", "conflict"),
    ("authority", "model_derived"),
))
def test_opening_count_source_seal_requires_producer_owned_commercial_units_and_status(
    tmp_path, field, forged_value,
):
    from copy import copy
    path = tmp_path / "count-commercial-source-trace.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    source = claim.opening_count_quantity_evidence[0]
    forged = copy(source)
    object.__setattr__(forged, field, forged_value)
    with pytest.raises(SourceClosedRunConflictError, match="commercial measurement authority"):
        build_live_opening_count_source_traces(
            replace(claim, opening_count_quantity_evidence=(forged,)),
            workspace_id=7, project_id="source-project",
        )
    assert len(build_live_opening_count_source_traces(
        claim, workspace_id=7, project_id="source-project",
    )) == 1


def test_opening_count_source_seal_requires_explicit_commercial_publication_permission(
    tmp_path,
):
    path = tmp_path / "count-commercial-permission.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    source = claim.opening_count_quantity_evidence[0]
    for permission in (False, None, "true"):
        forged = replace(
            source,
            metadata={
                **dict(source.metadata),
                "commercial_projection_allowed": permission,
            },
        )
        with pytest.raises(SourceClosedRunConflictError, match="commercial measurement authority"):
            build_live_opening_count_source_traces(
                replace(claim, opening_count_quantity_evidence=(forged,)),
                workspace_id=7, project_id="source-project",
            )



@pytest.mark.parametrize("bad_member", [" recorded-opening", "recorded-opening "])
def test_count_source_member_identity_cannot_be_silently_trimmed(tmp_path, bad_member):
    path = tmp_path / "count-source-member-whitespace.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert len(claim.opening_count_quantity_evidence) == 1
    source = claim.opening_count_quantity_evidence[0]
    forged = replace(source, input_entity_ids=(bad_member,))
    with pytest.raises(SourceClosedRunConflictError, match="unique physical member identities"):
        build_live_opening_count_source_traces(
            replace(claim, opening_count_quantity_evidence=(forged,)),
            workspace_id=7, project_id="source-project",
        )


def test_blocked_duplicate_count_id_cannot_disappear_before_sealing(tmp_path):
    path = tmp_path / "count-source-blocked-duplicate.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    source = claim.opening_count_quantity_evidence[0]
    forged_blocked = replace(
        source,
        value=None,
        status="blocked",
        abstained=True,
        blocking_reasons=("incomplete_opening_candidate_universe",),
    )
    conflicting = replace(
        claim,
        opening_count_quantity_evidence=(source, forged_blocked),
    )
    with pytest.raises(SourceClosedRunConflictError, match="duplicate or invalid opening-count quantity id"):
        seal_live_opening_count_run(
            conflicting, workspace_id=7, project_id="source-project",
        )

    # The unchanged original explicit count is still sealable.
    assert len(seal_live_opening_count_run(
        claim, workspace_id=7, project_id="source-project",
    ).quantities) == 1


def test_replayed_physical_count_member_identity_is_not_cast_from_boolean(tmp_path):
    path = tmp_path / "count-source-physical-bool.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    forged = replace(claim.canonical_openings[0], physical_opening_id=True)
    with pytest.raises(SourceClosedRunConflictError, match="exact original canonical/physical identities"):
        build_live_opening_count_source_traces(
            replace(claim, canonical_openings=(forged,)),
            workspace_id=7, project_id="source-project",
        )


@pytest.mark.parametrize(("field", "invalid"), (
    ("physical_opening_universe_complete", "true"),
    ("physical_opening_universe_complete", 1),
    ("physical_opening_universe_complete", [True]),
    ("structural_enumeration_complete", False),
    ("page_ids", ("2",)),
    ("page_ids", ("1", "1")),
    ("page_ids", (None,)),
    ("physical_opening_record_ids", ("foreign-opening",)),
    ("physical_opening_record_ids", ("   ",)),
    ("physical_opening_record_ids", ("same", "same")),
))
def test_original_complete_count_universe_must_match_exact_source_page_and_members(
    field, invalid,
):
    """Never invent a complete count from a replayed or truncated source universe."""
    from pb_live_opening_count_quantity_publication import (
        publish_live_authenticated_opening_count_quantities,
    )
    from pb_live_wall_opening_authority_composition import (
        compose_live_wall_opening_authority,
    )
    from pb_source_visibility_authority import SourceVisibilityProducer

    source = SourceVisibilityProducer(
        producer_method="count-closed-source-scope-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="count-closed-source-scope-test",
        source_bytes=_floor_plan_with_schedule_quantity(quantity=1),
        source_locator="memory://count-closed-source-scope-test.pdf",
    )
    composition = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    semantic = composition.semantic_enumeration_result
    assert semantic.record is not None
    forged = copy(semantic.record)
    object.__setattr__(forged, field, invalid)
    altered = replace(
        composition,
        semantic_enumeration_result=replace(semantic, record=forged),
    )
    assert publish_live_authenticated_opening_count_quantities(
        source_visibility_producer=source,
        wall_opening_composition=altered,
    ) == ()


@pytest.mark.parametrize("tamper", [
    {"semantic_key": "opening_count:W2"},
    {"semantic_key": "opening_count"},
    {"semantic_key": "opening_count:W1 "},
    {"formula": "sum_opening_projections"},
    {"formula_version": "foreign-version"},
    {"authority": "model_derived"},
    {"status": "provisional"},
    {"unit": "m2"},
])
def test_source_count_final_publication_requires_exact_signed_mark_semantics(tamper):
    from pb_live_opening_count_quantity_publication import (
        _source_count_quantity_ready_for_publication,
    )
    from pb_migration_contracts import QuantityEvidence
    from pb_generic_opening_count_authority import GENERIC_OPENING_COUNT_SCHEMA_VERSION

    clean = QuantityEvidence(
        quantity_id="original-source-count",
        family="opening_count",
        semantic_key="opening_count:W1",
        value=1.0,
        unit="ea",
        input_entity_ids=("physical-opening-1",),
        formula="sum_of_authenticated_physical_opening_instances",
        formula_version=GENERIC_OPENING_COUNT_SCHEMA_VERSION,
        evidence_ids=("original-physical-observation", "original-schedule-row"),
        authority="pdf_scaled",
        status="firm",
        confidence=1.0,
        abstained=False,
        blocking_reasons=(),
        metadata={"opening_mark": "W1", "schedule_corroborated": True},
    )
    assert _source_count_quantity_ready_for_publication(
        clean, opening_mark="W1",
    )
    assert not _source_count_quantity_ready_for_publication(
        replace(clean, **tamper), opening_mark="W1",
    )
    assert not _source_count_quantity_ready_for_publication(
        clean, opening_mark="W2",
    )
    assert not _source_count_quantity_ready_for_publication(
        replace(clean, metadata={"opening_mark": "W2", "schedule_corroborated": True}),
        opening_mark="W1",
    )


def test_original_source_count_keeps_mark_and_signed_quantity_id_at_final_bridge(tmp_path):
    from pb_live_opening_count_quantity_publication import (
        _source_count_quantity_ready_for_publication,
    )
    from pb_migration_contracts import stable_contract_id

    path = tmp_path / "count-final-signed-lineage.pdf"
    path.write_bytes(_floor_plan_with_schedule_quantity(quantity=1, tag="W1"))
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert len(claim.opening_count_quantity_evidence) == 1
    q = claim.opening_count_quantity_evidence[0]
    assert _source_count_quantity_ready_for_publication(q, opening_mark="W1")
    assert q.quantity_id == stable_contract_id(
        "qty_opening_count",
        {
            "family": "opening_count",
            "semantic_key": "opening_count:W1",
            "document_id": claim.canonical_openings[0].document_id,
            "revision_id": claim.canonical_openings[0].revision_id,
            "source_sha256": claim.canonical_openings[0].source_sha256,
            "snapshot_id": claim.canonical_openings[0].snapshot_id,
            "count": 1,
            "matched_ids": tuple(q.input_entity_ids),
        },
    )
    assert q.input_entity_ids == (claim.canonical_openings[0].canonical_opening_id,)
