"""Exact original ceiling source-page selection must fail closed before ingest.

These are generated, source-neutral PDF regressions, not original-plan proof.
"""
from __future__ import annotations

import fitz
import pytest

import pb_live_ceiling_lining_integration as ceiling


def _generated_two_page_pdf(tmp_path):
    doc = fitz.open()
    try:
        doc.new_page(width=300, height=200)
        doc.new_page(width=300, height=200)
        path = tmp_path / "synthetic-ceiling-pages.pdf"
        path.write_bytes(doc.tobytes(garbage=4, deflate=True))
        return path
    finally:
        doc.close()


def test_explicit_valid_ceiling_source_page_universe_is_sorted_and_idempotent():
    selected = [1, 0, 1]
    original = selected[:]
    assert ceiling._selected_page_indices(2, selected) == (0, 1)
    assert ceiling._selected_page_indices(2, selected) == (0, 1)
    assert selected == original
    assert ceiling._selected_page_indices(2, range(2)) == (0, 1)
    assert ceiling._selected_page_indices(2, ()) == ()
    assert ceiling._selected_page_indices(2, None) == (0, 1)


@pytest.mark.parametrize(
    "pages",
    [
        (0, True),
        (0, False),
        (0, 0.0),
        (0, 1.0),
        (0, "1"),
        (0, b"1"),
        (0, -1),
        (0, 2),
        (0, 10**1000),
        (0, float("nan")),
        (0, object()),
        ("0", "1"),
        "01",
        b"01",
        {0: 1},
        0,
        1.0,
    ],
)
def test_malformed_ceiling_source_page_universe_is_not_silently_repaired(pages):
    with pytest.raises(ValueError, match="original ceiling page selection"):
        ceiling._selected_page_indices(2, pages)


@pytest.mark.parametrize(
    "bad",
    [True, False, 0.0, 1.0, "1", b"1", -1, 2, 10**1000, float("nan"), object()],
)
@pytest.mark.parametrize("which", ["pages", "topology_pages"])
def test_invalid_source_or_topology_sibling_aborts_before_pdf_ingestion(
    tmp_path, monkeypatch, bad, which
):
    path = _generated_two_page_pdf(tmp_path)
    ingestions = []

    def forbid_ingest(*args, **kwargs):
        ingestions.append(kwargs)
        raise AssertionError("invalid page selection reached original PDF ingestion")

    monkeypatch.setattr(
        ceiling.SourceVisibilityProducer, "ingest_native_pdf_bytes", forbid_ingest
    )
    kwargs = (
        {"pages": (0, bad), "topology_pages": (0,)}
        if which == "pages"
        else {"pages": (0, 1), "topology_pages": (0, bad)}
    )
    with pytest.raises(ValueError, match="original ceiling page selection"):
        ceiling.collect_live_ceiling_lining_claims(path, **kwargs)
    assert ingestions == []


def test_valid_ceiling_page_and_topology_split_preserves_exact_source_scope(
    tmp_path, monkeypatch
):
    path = _generated_two_page_pdf(tmp_path)
    ingested = []
    scanned = []
    original_ingest = ceiling.SourceVisibilityProducer.ingest_native_pdf_bytes

    def capture_ingest(self, *args, **kwargs):
        ingested.append(tuple(kwargs.get("page_ids") or ()))
        return original_ingest(self, *args, **kwargs)

    def capture_viewports(page, *, page_number):
        scanned.append(page_number)
        return ()

    monkeypatch.setattr(
        ceiling.SourceVisibilityProducer, "ingest_native_pdf_bytes", capture_ingest
    )
    monkeypatch.setattr(
        ceiling, "authoritative_floor_plan_viewports", capture_viewports
    )
    selected = [1, 0, 1]
    topology = [1, 1]
    result = ceiling.collect_live_ceiling_lining_claims(
        path, pages=selected, topology_pages=topology
    )
    assert ingested == [("1", "2")]
    assert scanned == [2]
    assert result.claims == ()
    assert result.canonical_ceilings == ()
    assert selected == [1, 0, 1]
    assert topology == [1, 1]


def test_ceiling_topology_subset_conflict_aborts_before_ingestion(
    tmp_path, monkeypatch
):
    path = _generated_two_page_pdf(tmp_path)
    ingestions = []

    def forbid_ingest(*args, **kwargs):
        ingestions.append(kwargs)
        raise AssertionError("invalid topology subset reached original ingestion")

    monkeypatch.setattr(
        ceiling.SourceVisibilityProducer, "ingest_native_pdf_bytes", forbid_ingest
    )
    with pytest.raises(ValueError, match="topology_pages must be a subset"):
        ceiling.collect_live_ceiling_lining_claims(
            path, pages=(0,), topology_pages=(1,)
        )
    assert ingestions == []


def _source_owned_ceiling_quantity_with_page(page_token):
    """A valid source-owned documented two-axis ceiling proof, before page gate."""
    from types import SimpleNamespace

    room_id = "original-room-1"
    area = SimpleNamespace(
        quantity_id="source-room-area-1",
        abstained=False,
        value=13.27,
        status=ceiling.AuthorityStatus.FIRM.value,
        authority=ceiling.MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
        input_entity_ids=(room_id,),
        blocking_reasons=(),
        metadata={"figured_dimension_ids": ("axis-length", "axis-width")},
    )
    quantity = SimpleNamespace(
        family="ceiling_lining",
        abstained=False,
        value=13.27,
        status=ceiling.AuthorityStatus.PROVISIONAL.value,
        authority=ceiling.MeasurementAuthorityType.MODEL_DERIVED.value,
        blocking_reasons=(),
        input_entity_ids=(room_id,),
        quantity_id="source-ceiling-1",
        evidence_ids=("finish-1",),
        metadata={
            "shadow_only": True,
            "commercial_projection_allowed": False,
            "viewport_id": "source-viewport-1",
            "page_no": page_token,
            "finish_descriptor": "plasterboard",
            "finish_source_methods": (ceiling.SOURCE_CEILING_FINISH_METHOD,),
            "finish_evidence_ids": ("finish-1",),
            "upstream_area_quantity_id": area.quantity_id,
        },
    )
    return quantity, SimpleNamespace(room_area_quantities=(area,))


def test_valid_integer_ceiling_quantity_page_identity_preserves_source_claim():
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    original_meta = dict(quantity.metadata)
    first = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    second = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    assert first is not None
    assert first == second
    assert first[1] == "plasterboard"
    assert first[2] == 13.27
    assert first[-1] == ("axis-length", "axis-width")
    assert quantity.metadata == original_meta


@pytest.mark.parametrize(
    "bad_page",
    [
        None, True, False, 1.0, "1", b"1", float("nan"),
        float("inf"), object(), 10**1000, -1, 2,
    ],
)
def test_original_ceiling_quantity_page_aliases_abstain_without_crashing(bad_page):
    quantity, source = _source_owned_ceiling_quantity_with_page(bad_page)
    original_meta = dict(quantity.metadata)
    first = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    second = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    assert first is None
    assert second is None
    assert quantity.metadata == original_meta



@pytest.mark.parametrize("which", ["source_ceiling", "upstream_room"])
@pytest.mark.parametrize(
    "bad_metric",
    [
        True, False, "13.27", b"13.27", None, 0, -1.0,
        float("nan"), float("inf"), float("-inf"), 10**1000, object(),
    ],
)
def test_source_owned_ceiling_metric_alias_or_overflow_abstains_before_canonical(
    which, bad_metric
):
    """No invalid original m² can be coerced into a provisional ceiling claim."""
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    original_quantity_meta = dict(quantity.metadata)
    original_room_meta = dict(source.room_area_quantities[0].metadata)
    target = (
        quantity if which == "source_ceiling"
        else source.room_area_quantities[0]
    )
    target.value = bad_metric
    first = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    second = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    assert first is None
    assert second is None
    assert target.value is bad_metric
    assert quantity.metadata == original_quantity_meta
    assert source.room_area_quantities[0].metadata == original_room_meta


@pytest.mark.parametrize("valid_metric", [13, 13.27, 0.004])
def test_source_owned_native_positive_ceiling_metric_keeps_original_area(valid_metric):
    """Existing valid native metric inputs keep their quantity and source axes."""
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    quantity.value = valid_metric
    source.room_area_quantities[0].value = valid_metric
    first = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    second = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    assert first == second
    assert first is not None
    assert first[2] == float(valid_metric)
    assert first[-1] == ("axis-length", "axis-width")


def _generated_source_owned_ceiling_pdf(tmp_path):
    """Public-safe framed native PDF that exercises the real ceiling producer."""
    from pb_page_scale_calibration_authority import POINTS_PER_METRE_AT_1_1

    doc = fitz.open()
    try:
        page = doc.new_page(width=460, height=320)
        page.draw_rect(fitz.Rect(30, 25, 370, 230), color=(0, 0, 0), width=1)
        page.insert_text(fitz.Point(120, 48), "GROUND FLOOR PLAN", fontsize=8)
        for first, second in (
            ((70, 70), (330, 70)),
            ((330, 70), (330, 175)),
            ((330, 175), (70, 175)),
            ((70, 175), (70, 70)),
            ((200, 70), (200, 175)),
        ):
            page.draw_line(fitz.Point(*first), fitz.Point(*second),
                           color=(0, 0, 0), width=1)
        page.insert_text(fitz.Point(92, 122), "CEILING FINISH: CHIPBOARD",
                         fontsize=7)
        span = POINTS_PER_METRE_AT_1_1 / 100
        x0, x1, y = 95, 95 + span, 205
        shape = page.new_shape()
        shape.draw_line(fitz.Point(x0, y), fitz.Point(x1, y))
        shape.draw_line(fitz.Point(x0, y - 6), fitz.Point(x0, y + 6))
        shape.draw_line(fitz.Point(x1, y - 6), fitz.Point(x1, y + 6))
        shape.finish(width=1)
        shape.commit()
        page.insert_text(fitz.Point(x0 - 2, y + 18), "0", fontsize=7)
        page.insert_text(fitz.Point(x1 - 4, y + 18), "1m", fontsize=7)
        page.insert_text(fitz.Point(390, 285), "SCALE 1:100", fontsize=7)
        path = tmp_path / "source-owned-ceiling-quantity-replay.pdf"
        path.write_bytes(doc.tobytes(garbage=4, deflate=True))
        return path
    finally:
        doc.close()


@pytest.mark.parametrize(
    "replay",
    ["identical", "changed_first", "changed_last", "invalid_sibling"],
)
def test_original_ceiling_quantity_id_replays_never_double_count_or_choose_winner(
    tmp_path, monkeypatch, replay
):
    from dataclasses import replace

    from pb_migration_provider_envelope import ProviderResult

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(baseline.quantity_evidence) == 1
    assert baseline.claims[0].quantity_m2 > 0

    original_run = ceiling.run_source_owned_ceiling_lining_shadow
    untouched = []
    calls = []

    def replay_source_owned_quantity(*args, **kwargs):
        result = original_run(*args, **kwargs)
        # The real producer can retain ABSTAINED/partial siblings alongside
        # the single publishable source-owned ceiling.  One live claim does
        # not imply the entire provider quantity universe has one member.
        eligible = tuple(
            quantity for quantity in result.ceiling_quantities
            if ceiling._claim_from_quantity(
                quantity=quantity,
                source_result=result,
                page_no=kwargs["page_no"],
                viewport_id=kwargs["viewport"].viewport_id,
            ) is not None
        )
        assert len(eligible) == 1
        authentic = eligible[0]
        original_metadata = dict(authentic.metadata)
        altered = replace(
            authentic,
            confidence=(0.25 if authentic.confidence != 0.25 else 0.75),
        )
        if replay == "identical":
            quantities = (authentic, authentic)
        elif replay == "changed_first":
            quantities = (altered, authentic)
        elif replay == "changed_last":
            quantities = (authentic, altered)
        else:
            quantities = (authentic, replace(authentic, value=authentic.value + 1))
        rebuilt = ProviderResult.build(
            descriptor=result.pipeline.ceiling_result.descriptor,
            context=kwargs["context"],
            quantities=quantities,
            entities=result.pipeline.ceiling_result.entities,
        )
        untouched.append((authentic, original_metadata))
        calls.append(rebuilt.result_fingerprint)
        return replace(
            result,
            pipeline=replace(result.pipeline, ceiling_result=rebuilt),
        )

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow",
        replay_source_owned_quantity,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(calls) == 2
    assert first == second
    assert all(q.metadata == metadata for q, metadata in untouched)

    if replay == "identical":
        # Replaying the exact same original quantity is idempotent, not 2x m².
        assert first.claims == baseline.claims
        assert first.canonical_ceilings == baseline.canonical_ceilings
        assert first.quantity_evidence == baseline.quantity_evidence
    else:
        # Every record under a conflicted source ID must abstain together.
        assert first.claims == ()
        assert first.canonical_ceilings == ()
        assert first.quantity_evidence == ()
        assert ceiling.LIVE_CEILING_QUANTITY_IDENTITY_CONFLICT in first.reason_codes


@pytest.mark.parametrize("reverse_order", [False, True])
def test_distinct_source_ceiling_ids_cannot_publish_one_conflicted_canonical_room(
    tmp_path, monkeypatch, reverse_order
):
    """A canonical physical ceiling collision revokes both issuer claimants."""
    from dataclasses import replace

    from pb_migration_provider_envelope import ProviderResult

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(baseline.quantity_evidence) == 1

    original_run = ceiling.run_source_owned_ceiling_lining_shadow
    untouched = []
    calls = []

    def duplicate_physical_room(*args, **kwargs):
        result = original_run(*args, **kwargs)
        eligible = tuple(
            quantity for quantity in result.ceiling_quantities
            if ceiling._claim_from_quantity(
                quantity=quantity,
                source_result=result,
                page_no=kwargs["page_no"],
                viewport_id=kwargs["viewport"].viewport_id,
            ) is not None
        )
        assert len(eligible) == 1
        authentic = eligible[0]
        rival = replace(
            authentic,
            quantity_id=authentic.quantity_id + "-distinct-source-rival",
        )
        quantities = (rival, authentic) if reverse_order else (authentic, rival)
        rebuilt = ProviderResult.build(
            descriptor=result.pipeline.ceiling_result.descriptor,
            context=kwargs["context"],
            quantities=quantities,
            entities=result.pipeline.ceiling_result.entities,
        )
        untouched.append((authentic, dict(authentic.metadata)))
        calls.append(rebuilt.result_fingerprint)
        return replace(
            result,
            pipeline=replace(result.pipeline, ceiling_result=rebuilt),
        )

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow",
        duplicate_physical_room,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(calls) == 2
    assert first == second
    assert all(quantity.metadata == metadata for quantity, metadata in untouched)
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert ceiling.LIVE_CEILING_CANONICAL_IDENTITY_CONFLICT in first.reason_codes
    assert ceiling.LIVE_CEILING_QUANTITY_IDENTITY_CONFLICT not in first.reason_codes
    # Trace the real canonical issuer and customer consumer: neither may
    # promote a ceiling whose original physical canonical identity failed.
    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="source-neutral-ceiling-conflict"
    ) == ()


@pytest.mark.parametrize("container", [tuple, list])
def test_native_original_ceiling_finish_receipts_keep_source_claim(container):
    """The source producer's typed material methods and receipt IDs remain valid."""
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    quantity.metadata["finish_source_methods"] = container(
        (ceiling.SOURCE_CEILING_FINISH_METHOD, "another_producer_method")
    )
    quantity.metadata["finish_evidence_ids"] = container(("finish-1",))
    quantity.evidence_ids = container(("finish-1", "area-receipt"))
    before = dict(quantity.metadata)
    first = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    second = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    assert first is not None
    assert first == second
    assert first[1] == "plasterboard"
    assert first[5] == ("finish-1", "area-receipt")
    assert quantity.metadata == before


@pytest.mark.parametrize(
    "field,bad",
    [
        ("finish_descriptor", None),
        ("finish_descriptor", 123),
        ("finish_descriptor", b"plasterboard"),
        ("finish_descriptor", ""),
        ("finish_descriptor", " plasterboard"),
        ("finish_descriptor", "plasterboard "),
        ("finish_source_methods", ceiling.SOURCE_CEILING_FINISH_METHOD),
        ("finish_source_methods", b"producer_owned_pdf_text_integrity"),
        ("finish_source_methods", {ceiling.SOURCE_CEILING_FINISH_METHOD: True}),
        ("finish_source_methods", ()),
        ("finish_source_methods", (ceiling.SOURCE_CEILING_FINISH_METHOD, True)),
        ("finish_source_methods", (" " + ceiling.SOURCE_CEILING_FINISH_METHOD,)),
        ("finish_source_methods", (
            ceiling.SOURCE_CEILING_FINISH_METHOD,
            ceiling.SOURCE_CEILING_FINISH_METHOD,
        )),
        ("finish_source_methods", object()),
        ("finish_evidence_ids", "finish-1"),
        ("finish_evidence_ids", b"finish-1"),
        ("finish_evidence_ids", {"finish-1": True}),
        ("finish_evidence_ids", ()),
        ("finish_evidence_ids", ("finish-1", True)),
        ("finish_evidence_ids", (" finish-1",)),
        ("finish_evidence_ids", ("finish-1", "finish-1")),
        ("finish_evidence_ids", ("foreign-source-receipt",)),
        ("finish_evidence_ids", object()),
        ("source_evidence_ids", "finish-1"),
        ("source_evidence_ids", b"finish-1"),
        ("source_evidence_ids", ()),
        ("source_evidence_ids", ("finish-1", True)),
        ("source_evidence_ids", (" finish-1",)),
        ("source_evidence_ids", ("finish-1", "finish-1")),
        ("source_evidence_ids", object()),
    ],
)
def test_malformed_original_ceiling_finish_receipt_abstains_without_alias(
    field, bad
):
    """Malformed material provenance cannot be stringified into a ceiling claim."""
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    if field == "source_evidence_ids":
        quantity.evidence_ids = bad
    else:
        quantity.metadata[field] = bad
    before = dict(quantity.metadata)
    first = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    second = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    assert first is None
    assert second is None
    assert quantity.metadata == before
    if field == "source_evidence_ids":
        assert quantity.evidence_ids is bad


@pytest.mark.parametrize("overflow", [False, True])
def test_source_ceiling_finite_rows_cannot_overflow_descriptor_claim_or_customer(
    tmp_path, monkeypatch, overflow
):
    """Exercise real PDF collector aggregation with adversarial distinct source rows.

    This is generated-PDF/injected-provider safety proof, NOT an original
    source-positive ceiling measurement or permission to issue FIRM.
    """
    from dataclasses import replace

    from pb_migration_provider_envelope import ProviderResult
    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(baseline.quantity_evidence) == 1

    real_run = ceiling.run_source_owned_ceiling_lining_shadow
    real_claim = ceiling._claim_from_quantity
    source_snapshot = []

    def duplicate_source_ids(*args, **kwargs):
        result = real_run(*args, **kwargs)
        eligible = tuple(
            item for item in result.ceiling_quantities
            if real_claim(
                quantity=item, source_result=result,
                page_no=kwargs["page_no"],
                viewport_id=kwargs["viewport"].viewport_id,
            ) is not None
        )
        assert len(eligible) == 1
        authentic = eligible[0]
        rival = replace(
            authentic, quantity_id=authentic.quantity_id + "-distinct-synthetic-room",
        )
        source_snapshot.append((authentic, dict(authentic.metadata)))
        rebuilt = ProviderResult.build(
            descriptor=result.pipeline.ceiling_result.descriptor,
            context=kwargs["context"],
            quantities=(authentic, rival),
            entities=result.pipeline.ceiling_result.entities,
        )
        return replace(
            result, pipeline=replace(result.pipeline, ceiling_result=rebuilt),
        )

    def source_metric_boundary(*, quantity, source_result, page_no, viewport_id):
        resolved = real_claim(
            quantity=quantity, source_result=source_result,
            page_no=page_no, viewport_id=viewport_id,
        )
        if resolved is None:
            return None
        metric = 1e308 if overflow else resolved[2]
        # Simulate two DISTINCT original physical rooms after the upstream
        # geometry/metric gates; never treat these injected rooms as source proof.
        return (
            resolved[0], resolved[1], metric,
            (quantity.quantity_id,),
            ("adversarial-room:" + quantity.quantity_id,),
            resolved[5], resolved[6], resolved[7], resolved[8],
        )

    def synthetic_distinct_canonical(*, quantity, source_result, page_no, viewport_id):
        original = baseline.canonical_ceilings[0]
        metric = 1e308 if overflow else baseline.claims[0].quantity_m2
        return replace(
            original,
            canonical_ceiling_id=original.canonical_ceiling_id + "-" + quantity.quantity_id,
            room_entity_id="adversarial-room:" + quantity.quantity_id,
            ceiling_quantity_id=quantity.quantity_id,
            area_m2=metric,
        )

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow", duplicate_source_ids,
    )
    monkeypatch.setattr(ceiling, "_claim_from_quantity", source_metric_boundary)
    monkeypatch.setattr(
        ceiling, "canonical_ceiling_from_shadow_quantity",
        synthetic_distinct_canonical,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert len(source_snapshot) == 2
    assert all(item.metadata == before for item, before in source_snapshot)

    if overflow:
        # The pre-fix collector constructed a nonfinite m² claim from these
        # individually finite positive values. No downstream FIRM or customer
        # projection can be issued from this conflicted aggregate.
        assert first.claims == ()
        assert first.quantity_evidence == ()
        assert ceiling.LIVE_CEILING_LINING_METRIC_AGGREGATE_NONFINITE in first.reason_codes
        assert publish_live_ceiling_area_quantities(first) == ()
        assert project_live_ceiling_area_customer_rows(
            first, workspace_id=1, project_id="synthetic-ceiling-overflow"
        ) == ()
    else:
        # Finite source values retain the existing sum/claim-ID semantics.
        assert len(first.claims) == 1
        assert first.claims[0].quantity_m2 == 2 * baseline.claims[0].quantity_m2
        assert ceiling.LIVE_CEILING_LINING_METRIC_AGGREGATE_NONFINITE not in first.reason_codes
