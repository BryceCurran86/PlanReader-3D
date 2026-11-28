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
        family="room_area",
        unit="m2",
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
        unit="m2",
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


@pytest.mark.parametrize("failed_first", [False, True])
def test_failed_original_ceiling_viewport_revokes_complete_source_universe(
    tmp_path, monkeypatch, failed_first
):
    """One failed source-owned viewport cannot leave a sibling's customer m²."""
    from types import SimpleNamespace

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

    real_viewports = ceiling.authoritative_floor_plan_viewports
    real_run = ceiling.run_source_owned_ceiling_lining_shadow
    failures = []
    successes = []
    synthetic_suffix = "-source-viewport-failure"

    def source_viewports_with_failed_sibling(page, *, page_number):
        original = tuple(real_viewports(page, page_number=page_number))
        assert original
        good = original[0]
        bad = SimpleNamespace(
            view_id=good.view_id + synthetic_suffix,
            bounding_box=good.bounding_box,
            confidence=good.confidence,
        )
        return (bad, good) if failed_first else (good, bad)

    def fail_one_source_viewport(*args, **kwargs):
        viewport_id = kwargs["viewport"].viewport_id
        if viewport_id.endswith(synthetic_suffix):
            failures.append(viewport_id)
            raise RuntimeError("synthetic source-viewport producer failure")
        successes.append(viewport_id)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(
        ceiling, "authoritative_floor_plan_viewports",
        source_viewports_with_failed_sibling,
    )
    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow",
        fail_one_source_viewport,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert len(failures) == 2
    assert len(successes) == (0 if failed_first else 2)
    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.reason_codes == (
        ceiling.LIVE_CEILING_LINING_UNAVAILABLE,
        ceiling.LIVE_CEILING_LINING_SOURCE_VIEWPORT_FAILURE,
    )
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="synthetic-incomplete-ceiling-universe"
    ) == ()


def test_missing_original_ceiling_room_index_never_emits_unbacked_live_claim(
    tmp_path, monkeypatch
):
    """A real source-owned metric needs its physical canonical room geometry.

    Generated PDF only; this is not original Maryborough source acceptance.
    """
    from dataclasses import replace

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
    original_indices = []

    def lose_physical_room_index(*args, **kwargs):
        result = real_run(*args, **kwargs)
        original_index = result.pipeline.room_area_bridge.room_index
        assert original_index is not None
        original_indices.append(original_index)
        # Simulate a missing producer-owned physical room index AFTER the
        # original quantity passed its separate metric/material gate.
        # Keep upstream source quantities and their IDs untouched.
        return replace(
            result,
            pipeline=replace(
                result.pipeline,
                room_area_bridge=replace(
                    result.pipeline.room_area_bridge, room_index=None,
                ),
            ),
        )

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow",
        lose_physical_room_index,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert len(original_indices) == 2
    assert original_indices[0] == original_indices[1]
    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="synthetic-missing-ceiling-room",
    ) == ()


@pytest.mark.parametrize("missing_first", [False, True])
def test_missing_original_revision_snapshot_abstains_entire_ceiling_universe(
    tmp_path, monkeypatch, missing_first
):
    """A missing selected source snapshot cannot leave a sibling ceiling live.

    Uses a generated native PDF and a synthetic missing-snapshot sibling.
    This is NOT an original Maryborough source-positive measurement.
    """
    from types import SimpleNamespace

    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf_bytes = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(baseline.quantity_evidence) == 1

    real_viewports = ceiling.authoritative_floor_plan_viewports
    real_ingest = ceiling.SourceVisibilityProducer.ingest_native_pdf_bytes
    real_snapshot = ceiling.SourceVisibilityProducer.published_snapshot_for_revision
    real_run = ceiling.run_source_owned_ceiling_lining_shadow
    state = {"ingested": False, "snapshot_calls": 0, "inside_run": False}
    missing_receipts = []
    successful_source_runs = []
    observed_source_viewports = []

    def two_original_viewports(page, *, page_number):
        originals = tuple(real_viewports(page, page_number=page_number))
        assert originals
        good = originals[0]
        missing = SimpleNamespace(
            view_id=good.view_id + "-missing-published-snapshot",
            bounding_box=good.bounding_box,
            confidence=good.confidence,
        )
        observed_source_viewports.append(good)
        return (missing, good) if missing_first else (good, missing)

    def record_ingest(self, *args, **kwargs):
        state["ingested"] = False
        state["snapshot_calls"] = 0
        state["inside_run"] = False
        published = real_ingest(self, *args, **kwargs)
        state["ingested"] = True
        return published

    def one_missing_snapshot(self, revision_id):
        # The source-owned pipeline itself re-reads this snapshot during
        # legitimate evidence checks. Only intercept the collector boundary;
        # never corrupt an internal producer proof or count it as a viewport.
        if state["ingested"] and not state["inside_run"]:
            state["snapshot_calls"] += 1
            target_call = 1 if missing_first else 2
            if state["snapshot_calls"] == target_call:
                missing_receipts.append(revision_id)
                return None
        return real_snapshot(self, revision_id)

    def capture_real_source_run(*args, **kwargs):
        successful_source_runs.append(kwargs["viewport"].viewport_id)
        state["inside_run"] = True
        try:
            return real_run(*args, **kwargs)
        finally:
            state["inside_run"] = False

    monkeypatch.setattr(
        ceiling, "authoritative_floor_plan_viewports", two_original_viewports,
    )
    monkeypatch.setattr(
        ceiling.SourceVisibilityProducer, "ingest_native_pdf_bytes", record_ingest,
    )
    monkeypatch.setattr(
        ceiling.SourceVisibilityProducer,
        "published_snapshot_for_revision",
        one_missing_snapshot,
    )
    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow",
        capture_real_source_run,
    )

    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert len(missing_receipts) == 2
    assert missing_receipts[0] == missing_receipts[1]
    assert len(observed_source_viewports) == 2
    assert observed_source_viewports[0] == observed_source_viewports[1]
    assert len(successful_source_runs) == (0 if missing_first else 2)
    assert path.read_bytes() == original_pdf_bytes

    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.reason_codes == (
        ceiling.LIVE_CEILING_LINING_UNAVAILABLE,
        ceiling.LIVE_CEILING_LINING_SOURCE_SNAPSHOT_UNAVAILABLE,
    )
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="synthetic-missing-original-snapshot"
    ) == ()


@pytest.mark.parametrize(
    "tamper",
    [
        {"document_id": "foreign-document"},
        {"source_sha256": "f" * 64},
        {"revision_id": "foreign-revision"},
        {"current_revision_id": "foreign-revision"},
        {"selected_pages": (1,)},
        {"owned_page_numbers": (2,)},
        {"owned_viewport_ids": ("foreign-viewport",)},
        {"viewport_page_ownership": (("foreign-viewport", 1),)},
        {"project_id": "foreign-project"},
        {"evidence_snapshot_id": ""},
    ],
)
def test_original_ceiling_post_producer_context_cannot_switch_source_root(
    tmp_path, monkeypatch, tamper
):
    """A real generated-PDF producer result cannot be rebound to foreign scope.

    The wall producer is permitted to advance the snapshot ID, not to replace
    the source revision, original page, viewport or customer owner.
    """
    from dataclasses import replace

    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(baseline.quantity_evidence) == 1

    real_run = ceiling.run_source_owned_ceiling_lining_shadow
    original_results = []

    def substituted_source_root(*args, **kwargs):
        result = real_run(*args, **kwargs)
        original_results.append(result)
        altered_context = replace(result.effective_context, **tamper)
        return replace(result, effective_context=altered_context)

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow",
        substituted_source_root,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert len(original_results) == 2
    assert original_results[0] == original_results[1]
    assert path.read_bytes() == original_pdf
    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.reason_codes == (
        ceiling.LIVE_CEILING_LINING_UNAVAILABLE,
        ceiling.LIVE_CEILING_LINING_SOURCE_CONTEXT_MISMATCH,
    )
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="synthetic-foreign-ceiling-context"
    ) == ()


@pytest.mark.parametrize("foreign_first", [False, True])
def test_original_ceiling_context_substitution_revokes_earlier_valid_viewport(
    tmp_path, monkeypatch, foreign_first
):
    """An invalid later viewport revokes earlier source-backed provisional m²."""
    from types import SimpleNamespace
    from dataclasses import replace

    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1

    real_viewports = ceiling.authoritative_floor_plan_viewports
    real_run = ceiling.run_source_owned_ceiling_lining_shadow
    processed = []
    foreign_suffix = "-foreign-source-root"

    def two_viewports(page, *, page_number):
        real = tuple(real_viewports(page, page_number=page_number))
        assert real
        valid = real[0]
        foreign = SimpleNamespace(
            view_id=valid.view_id + foreign_suffix,
            bounding_box=valid.bounding_box,
            confidence=valid.confidence,
        )
        return (foreign, valid) if foreign_first else (valid, foreign)

    def foreign_source_result(*args, **kwargs):
        view_id = kwargs["viewport"].viewport_id
        processed.append(view_id)
        if view_id.endswith(foreign_suffix):
            return SimpleNamespace(
                effective_context=replace(
                    kwargs["context"], source_sha256="f" * 64,
                ),
                ceiling_quantities=(),
            )
        return real_run(*args, **kwargs)

    monkeypatch.setattr(
        ceiling, "authoritative_floor_plan_viewports", two_viewports,
    )
    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow", foreign_source_result,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert len(processed) == (2 if foreign_first else 4)
    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.reason_codes == (
        ceiling.LIVE_CEILING_LINING_UNAVAILABLE,
        ceiling.LIVE_CEILING_LINING_SOURCE_CONTEXT_MISMATCH,
    )
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="synthetic-cross-view-ceiling"
    ) == ()


@pytest.mark.parametrize(
    "forged",
    [
        None, True, False, 123, b"source-room-area-1",
        " source-room-area-1", "source-room-area-1 ", object(),
    ],
)
def test_original_ceiling_upstream_area_id_must_be_exact_typed_source_receipt(forged):
    """A coerced/padded area ID cannot mint a provisional canonical ceiling."""
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    quantity.metadata["upstream_area_quantity_id"] = forged
    before = dict(quantity.metadata)
    for _ in range(2):
        assert ceiling._claim_from_quantity(
            quantity=quantity, source_result=source,
            page_no=1, viewport_id="source-viewport-1",
        ) is None
        # Canonical construction must also stop at the earliest receipt gate,
        # before attempting to read any room polygon or issuer evidence.
        assert ceiling.canonical_ceiling_from_shadow_quantity(
            quantity=quantity, source_result=source,
            page_no=1, viewport_id="source-viewport-1",
        ) is None
    assert quantity.metadata == before


@pytest.mark.parametrize(
    "forged",
    [True, 123, b"source-room-area-1", " source-room-area-1", "source-room-area-1 "],
)
def test_original_ceiling_room_area_inventory_id_cannot_alias_source_receipt(forged):
    """An untyped FIRM area inventory ID cannot match an exact upstream ID."""
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    original_meta = dict(quantity.metadata)
    area = source.room_area_quantities[0]
    area.quantity_id = forged
    for _ in range(2):
        assert ceiling._claim_from_quantity(
            quantity=quantity, source_result=source,
            page_no=1, viewport_id="source-viewport-1",
        ) is None
    assert quantity.metadata == original_meta
    assert area.quantity_id == forged


@pytest.mark.parametrize(
    "polygon",
    [
        ((0, 0), (4, 0), (4, 2), (0, 2)),
        ((0, 2), (4, 2), (4, 0), (0, 0)),
        ((1000000, -1000000), (1000004, -1000000),
         (1000004, -999998), (1000000, -999998)),
        ((0, 0), (4, 0), (4, 2), (0, 2), (0, 0)),
        ((0, 0), (6, 0), (6, 5), (3, 2), (0, 5)),
        ((0, 5), (3, 2), (6, 5), (6, 0), (0, 0)),
        ((0, 0), (6, 0), (6, 5), (3, 2), (0, 5), (0, 0)),
        # Inclusive exact-integer boundary is safe; origin-relative fan area
        # stays finite without shifting or rescaling the source vertices.
        ((2**53 - 2, 0), (2**53, 0), (2**53, 2), (2**53 - 2, 2)),
    ],
)
def test_original_ceiling_source_room_polygon_preserves_finite_native_vertices(polygon):
    """Orientation, translation and an explicit closing vertex do not change authority."""
    original = tuple(polygon)
    first = ceiling._source_room_polygon_pdf_pts(polygon)
    second = ceiling._source_room_polygon_pdf_pts(polygon)
    assert first == second
    assert first == tuple((float(x), float(y)) for x, y in original)
    assert polygon == original


@pytest.mark.parametrize(
    "bad_polygon",
    [
        pytest.param(((0, 0), (1, 1), (2, 2)), id="collinear-ring"),
        pytest.param(((0, 0), (0, 0), (0, 0)), id="collapsed-ring"),
        pytest.param(((0, 0), (1, 0), (float("nan"), 1)), id="nan-coordinate"),
        pytest.param(((0, 0), (1, 0), (float("inf"), 1)), id="inf-coordinate"),
        pytest.param(((0, 0), (1, 0), (float("-inf"), 1)), id="negative-inf"),
        pytest.param(((0, 0), (1, 0), (True, 1)), id="boolean-alias"),
        pytest.param(((0, 0), (1, 0), ("1", 1)), id="text-alias"),
        pytest.param(((0, 0), (1, 0), (object(), 1)), id="object-alias"),
        pytest.param(((0, 0), (1, 0), (10**1000, 1)), id="integer-overflow"),
        pytest.param(
            ((2**53 + 1, 0), (2**53 + 4, 0),
             (2**53 + 4, 2), (2**53 + 1, 2)),
            id="positive-native-integer-coordinate-alias",
        ),
        pytest.param(
            ((-(2**53 + 1), 0), (-(2**53 + 4), 0),
             (-(2**53 + 4), 2), (-(2**53 + 1), 2)),
            id="negative-native-integer-coordinate-alias",
        ),
        pytest.param(
            ((float(2**53 + 2), 0), (float(2**53 + 4), 0),
             (float(2**53 + 4), 2), (float(2**53 + 2), 2)),
            id="oversized-native-float-coordinate",
        ),
        pytest.param(
            ((0, 0), (2, 0), (2, -float(2**53 + 2)),
             (0, -float(2**53 + 2))),
            id="oversized-negative-native-float-y-coordinate",
        ),
        pytest.param(((0, 0), (1e308, 0), (0, 1e308)), id="cross-product-overflow"),
        pytest.param(((0, 0), (1, 0), (1, 1, 1)), id="malformed-point"),
        pytest.param(
            ((0, 0), (4, 4), (0, 4), (4, 0), (4, 2)),
            id="crossed-ring-with-nonzero-signed-area",
        ),
        pytest.param(
            ((0, 0), (4, 0), (2, 0), (4, 3), (0, 3)),
            id="adjacent-backtracking-overlap",
        ),
        pytest.param(
            ((0, 0), (4, 0), (4, 4), (2, 0), (0, 4)),
            id="nonadjacent-edge-touch",
        ),
        pytest.param(
            ((0, 0), (4, 0), (4, 4), (0, 4), (4, 0)),
            id="nonclosing-duplicate-vertex",
        ),
    ],
)
def test_invalid_original_room_polygon_abstains_through_real_ceiling_issuer(
    tmp_path, monkeypatch, bad_polygon
):
    """A source-owned metric cannot turn a malformed room face into customer m².

    The real generated-PDF producer, ceiling quantity, room ID, finish, area and
    source context are unchanged. Only its room-index polygon receipt is
    replaced after production; this is not original-plan source acceptance.
    """
    from dataclasses import replace
    from types import SimpleNamespace

    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(baseline.quantity_evidence) == 1
    assert baseline.canonical_ceilings[0].geometry_complete is True
    real_run = ceiling.run_source_owned_ceiling_lining_shadow
    authentic_results = []

    def source_with_invalid_room_ring(*args, **kwargs):
        result = real_run(*args, **kwargs)
        authentic_results.append(result)
        index = result.pipeline.room_area_bridge.room_index
        assert index is not None
        room_id = baseline.canonical_ceilings[0].room_entity_id
        assert index.room(room_id) is not None
        # Keep the real source-owned room and all quantity evidence immutable.
        # The wrapper changes only the polygon returned at canonicalization.
        def room_lookup(candidate_id):
            room = index.room(candidate_id)
            if candidate_id == room_id and room is not None:
                return SimpleNamespace(polygon_pdf_pts=bad_polygon)
            return room

        altered_index = SimpleNamespace(index_id=index.index_id, room=room_lookup)
        altered_bridge = replace(
            result.pipeline.room_area_bridge, room_index=altered_index,
        )
        return replace(
            result,
            pipeline=replace(result.pipeline, room_area_bridge=altered_bridge),
        )

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow",
        source_with_invalid_room_ring,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert len(authentic_results) == 2
    assert authentic_results[0] == authentic_results[1]
    assert path.read_bytes() == original_pdf
    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="synthetic-invalid-source-ring",
    ) == ()


@pytest.mark.parametrize(
    "polygon",
    [
        ((0, 0), (6, 0), (6, 5), (3, 2), (0, 5)),
        ((0, 5), (3, 2), (6, 5), (6, 0), (0, 0)),
        ((0, 0), (6, 0), (6, 5), (3, 2), (0, 5), (0, 0)),
    ],
)
def test_simple_concave_original_room_ring_preserves_real_ceiling_issuer(
    tmp_path, monkeypatch, polygon
):
    """A valid concave source face is neither repaired nor silently rejected.

    This generated-PDF source-index substitution is a topology regression,
    not authenticated original-source area, finish, or customer proof.
    """
    from dataclasses import replace
    from types import SimpleNamespace

    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(publish_live_ceiling_area_quantities(baseline)) == 1
    real_run = ceiling.run_source_owned_ceiling_lining_shadow
    authentic_results = []

    def substitute_simple_ring(*args, **kwargs):
        result = real_run(*args, **kwargs)
        authentic_results.append(result)
        index = result.pipeline.room_area_bridge.room_index
        assert index is not None
        room_id = baseline.canonical_ceilings[0].room_entity_id

        def room_lookup(candidate_id):
            room = index.room(candidate_id)
            if candidate_id == room_id and room is not None:
                return SimpleNamespace(polygon_pdf_pts=polygon)
            return room

        altered_bridge = replace(
            result.pipeline.room_area_bridge,
            room_index=SimpleNamespace(index_id=index.index_id, room=room_lookup),
        )
        return replace(
            result, pipeline=replace(result.pipeline, room_area_bridge=altered_bridge),
        )

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow", substitute_simple_ring,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert len(authentic_results) == 2
    assert authentic_results[0] == authentic_results[1]
    assert path.read_bytes() == original_pdf
    assert len(first.claims) == 1
    assert len(first.canonical_ceilings) == 1
    assert len(first.quantity_evidence) == 1
    assert first.canonical_ceilings[0].geometry_complete is True
    assert first.canonical_ceilings[0].polygon_pdf_pts == tuple(
        (float(x), float(y)) for x, y in polygon
    )
    assert len(publish_live_ceiling_area_quantities(first)) == 1
    # Source geometry legitimately changes the customer's drawing bbox.
    # The exact quantity and row count, not a forged original bbox, persist.
    assert len(project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="synthetic-simple-ring",
    )) == len(project_live_ceiling_area_customer_rows(
        baseline, workspace_id=1, project_id="synthetic-simple-ring",
    ))


@pytest.mark.parametrize(
    "bad_axes",
    [
        ("axis-length ", "axis-width"),
        ("axis-length", " axis-width"),
        ("axis-length", ""),
        ("axis-length", "   "),
        ("axis-length", b"axis-width"),
        ("axis-length", 123),
        ("axis-length", None),
        ("axis-length", object()),
    ],
)
def test_documented_ceiling_axes_must_keep_exact_source_receipt_ids(bad_axes):
    """A FIRM documented area cannot repair malformed source axis identities."""
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    area = source.room_area_quantities[0]
    area.metadata["figured_dimension_ids"] = bad_axes
    original_area_metadata = dict(area.metadata)
    original_quantity_metadata = dict(quantity.metadata)
    for _ in range(2):
        assert ceiling._claim_from_quantity(
            quantity=quantity, source_result=source,
            page_no=1, viewport_id="source-viewport-1",
        ) is None
        assert ceiling.canonical_ceiling_from_shadow_quantity(
            quantity=quantity, source_result=source,
            page_no=1, viewport_id="source-viewport-1",
        ) is None
    assert area.metadata == original_area_metadata
    assert quantity.metadata == original_quantity_metadata


def test_exact_documented_ceiling_axes_preserve_valid_repeat_and_order():
    """Identical exact repeats do not fabricate a third figured axis."""
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    area = source.room_area_quantities[0]
    area.metadata["figured_dimension_ids"] = (
        "axis-width", "axis-length", "axis-width",
    )
    before = dict(area.metadata)
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
    assert first[-1] == ("axis-length", "axis-width")
    assert area.metadata == before


@pytest.mark.parametrize(
    "axis_ids",
    [
        ("axis-length", "axis-width"),
        ("axis-length ", "axis-width"),
        ("axis-length", " axis-width"),
        ("axis-length", ""),
    ],
)
def test_generated_pdf_documented_axis_receipts_gate_real_ceiling_customer(
    tmp_path, monkeypatch, axis_ids
):
    """The genuine PDF producer remains intact; only its FIRM axis receipt is varied.

    This is a generated-PDF regression, not a SHA-authenticated original source
    run and not evidence of a new FIRM or commercial quantity.
    """
    from dataclasses import replace

    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf_bytes = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    real_run = ceiling.run_source_owned_ceiling_lining_shadow
    authentic_results = []

    def substitute_only_documented_axis_receipt(*args, **kwargs):
        result = real_run(*args, **kwargs)
        authentic_results.append(result)
        eligible = tuple(
            q for q in result.ceiling_quantities
            if ceiling._claim_from_quantity(
                quantity=q, source_result=result,
                page_no=kwargs["page_no"],
                viewport_id=kwargs["viewport"].viewport_id,
            ) is not None
        )
        assert len(eligible) == 1
        original_quantity = eligible[0]
        area_id = original_quantity.metadata["upstream_area_quantity_id"]
        original_area = next(
            a for a in result.room_area_quantities if a.quantity_id == area_id
        )
        documented = replace(
            original_area,
            authority=ceiling.MeasurementAuthorityType.DOCUMENTED_DIMENSION.value,
            metadata={
                **original_area.metadata,
                "figured_dimension_ids": axis_ids,
            },
        )
        return replace(
            result,
            pipeline=replace(
                result.pipeline,
                authoritative_area_quantities=(documented,),
            ),
        )

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow",
        substitute_only_documented_axis_receipt,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert len(authentic_results) == 2
    assert authentic_results[0] == authentic_results[1]
    assert path.read_bytes() == original_pdf_bytes

    if axis_ids == ("axis-length", "axis-width"):
        assert len(first.claims) == 1
        assert len(first.canonical_ceilings) == 1
        assert first.canonical_ceilings[0].figured_dimension_ids == axis_ids
        assert len(publish_live_ceiling_area_quantities(first)) == 1
    else:
        assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
        assert first.claims == ()
        assert first.canonical_ceilings == ()
        assert first.quantity_evidence == ()
        assert publish_live_ceiling_area_quantities(first) == ()
        assert project_live_ceiling_area_customer_rows(
            first, workspace_id=1, project_id="generated-invalid-axes",
        ) == ()



@pytest.mark.parametrize(
    "forged_id",
    [
        " source-ceiling-1",
        "source-ceiling-1 ",
        " ",
        "",
        True,
        123,
        b"source-ceiling-1",
        None,
        object(),
    ],
)
def test_source_ceiling_quantity_identity_cannot_be_repaired_before_claim(forged_id):
    """The source's ceiling quantity ID is as strict as its upstream area ID."""
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    quantity.quantity_id = forged_id
    before = dict(quantity.metadata)
    for _ in range(2):
        assert ceiling._claim_from_quantity(
            quantity=quantity, source_result=source,
            page_no=1, viewport_id="source-viewport-1",
        ) is None
        assert not ceiling._exact_source_ceiling_quantity_id(forged_id)
    assert quantity.quantity_id is forged_id
    assert quantity.metadata == before


def test_exact_native_source_ceiling_quantity_id_preserves_provenance_and_replay():
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    before = dict(quantity.metadata)
    assert ceiling._exact_source_ceiling_quantity_id(quantity.quantity_id)
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
    assert first[3] == ("source-ceiling-1",)
    assert quantity.metadata == before


@pytest.mark.parametrize(
    "variant",
    ["exact", "leading", "trailing", "bytes", "boolean", "integer", "subclass"],
)
def test_generated_pdf_exact_ceiling_quantity_id_gates_real_issuer_and_customer(
    tmp_path, monkeypatch, variant
):
    """Only a source-owned ceiling ID changes; real producer and source stay intact.

    These are public generated-PDF regressions, NOT original-source proof.
    """
    from dataclasses import replace

    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    class SourceIdSubclass(str):
        pass

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    source_bytes = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(baseline.quantity_evidence) == 1
    assert len(publish_live_ceiling_area_quantities(baseline)) == 1
    real_run = ceiling.run_source_owned_ceiling_lining_shadow
    authentic_results = []

    def with_modified_ceiling_id(*args, **kwargs):
        result = real_run(*args, **kwargs)
        authentic_results.append(result)
        eligible = tuple(
            q for q in result.ceiling_quantities
            if ceiling._claim_from_quantity(
                quantity=q, source_result=result,
                page_no=kwargs["page_no"],
                viewport_id=kwargs["viewport"].viewport_id,
            ) is not None
        )
        assert len(eligible) == 1
        authentic = eligible[0]
        original_id = authentic.quantity_id
        altered_id = {
            "exact": original_id,
            "leading": " " + original_id,
            "trailing": original_id + " ",
            "bytes": original_id.encode(),
            "boolean": True,
            "integer": 123,
            "subclass": SourceIdSubclass(original_id),
        }[variant]
        altered = replace(authentic, quantity_id=altered_id)
        quantities = tuple(
            altered if item is authentic else item
            for item in result.ceiling_quantities
        )
        return replace(
            result,
            pipeline=replace(
                result.pipeline,
                ceiling_result=replace(
                    result.pipeline.ceiling_result, quantities=quantities,
                ),
            ),
        )

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow",
        with_modified_ceiling_id,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert len(authentic_results) == 2
    assert authentic_results[0] == authentic_results[1]
    assert path.read_bytes() == source_bytes
    if variant == "exact":
        assert first == baseline
        assert len(publish_live_ceiling_area_quantities(first)) == 1
    else:
        assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
        assert first.claims == ()
        assert first.canonical_ceilings == ()
        assert first.quantity_evidence == ()
        assert publish_live_ceiling_area_quantities(first) == ()
        assert project_live_ceiling_area_customer_rows(
            first, workspace_id=1, project_id="generated-invalid-ceiling-id",
        ) == ()

@pytest.mark.parametrize(
    "target,field,bad",
    [
        ("ceiling", "unit", "m"), ("ceiling", "unit", "count"),
        ("ceiling", "unit", "m²"), ("ceiling", "unit", b"m2"),
        ("ceiling", "unit", None), ("area", "unit", "m"),
        ("area", "unit", "count"), ("area", "unit", "m²"),
        ("area", "unit", b"m2"), ("area", "unit", None),
        ("area", "family", "wall_length"),
        ("area", "family", "ceiling_lining"),
        ("area", "family", b"room_area"), ("area", "family", None),
    ],
)
def test_ceiling_metric_receipt_requires_native_m2_and_room_area_family(
    target, field, bad
):
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    area = source.room_area_quantities[0]
    changed = quantity if target == "ceiling" else area
    setattr(changed, field, bad)
    original_quantity_metadata = dict(quantity.metadata)
    original_area_metadata = dict(area.metadata)
    for _ in range(2):
        assert ceiling._claim_from_quantity(
            quantity=quantity, source_result=source,
            page_no=1, viewport_id="source-viewport-1",
        ) is None
    assert getattr(changed, field) is bad
    assert quantity.metadata == original_quantity_metadata
    assert area.metadata == original_area_metadata


@pytest.mark.parametrize(
    "variant",
    ["native", "ceiling_length", "ceiling_count",
     "area_length", "area_count", "area_wrong_family"],
)
def test_generated_pdf_ceiling_metric_dimensionality_reaches_real_customer_gate(
    tmp_path, monkeypatch, variant
):
    from dataclasses import replace
    from pb_migration_provider_envelope import ProviderResult
    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(baseline.quantity_evidence) == 1
    assert len(publish_live_ceiling_area_quantities(baseline)) == 1
    real_run = ceiling.run_source_owned_ceiling_lining_shadow
    calls = []
    authentic_results = []

    def modified_receipt(*args, **kwargs):
        result = real_run(*args, **kwargs)
        authentic_results.append(result)
        eligible = tuple(
            q for q in result.ceiling_quantities
            if ceiling._claim_from_quantity(
                quantity=q, source_result=result,
                page_no=kwargs["page_no"],
                viewport_id=kwargs["viewport"].viewport_id,
            ) is not None
        )
        assert len(eligible) == 1
        authentic = eligible[0]
        if variant == "native":
            calls.append(variant)
            return result
        if variant.startswith("ceiling_"):
            bad_unit = "m" if variant == "ceiling_length" else "count"
            changed = replace(authentic, unit=bad_unit)
            rebuilt = ProviderResult.build(
                descriptor=result.pipeline.ceiling_result.descriptor,
                context=kwargs["context"],
                quantities=tuple(
                    changed if q is authentic else q
                    for q in result.ceiling_quantities
                ),
                entities=result.pipeline.ceiling_result.entities,
            )
            calls.append(variant)
            return replace(
                result,
                pipeline=replace(result.pipeline, ceiling_result=rebuilt),
            )
        upstream_id = baseline.canonical_ceilings[0].room_area_quantity_id
        matches = tuple(
            q for q in result.room_area_quantities if q.quantity_id == upstream_id
        )
        assert len(matches) == 1
        original_area = matches[0]
        changed_area = (
            replace(original_area, family="wall_length")
            if variant == "area_wrong_family"
            else replace(
                original_area,
                unit="m" if variant == "area_length" else "count",
            )
        )
        calls.append(variant)
        return replace(
            result,
            pipeline=replace(
                result.pipeline,
                authoritative_area_quantities=tuple(
                    changed_area if q is original_area else q
                    for q in result.room_area_quantities
                ),
            ),
        )

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow", modified_receipt,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert calls == [variant, variant]
    assert len(authentic_results) == 2
    assert authentic_results[0] == authentic_results[1]
    assert path.read_bytes() == original_pdf
    if variant == "native":
        assert first == baseline
        assert len(publish_live_ceiling_area_quantities(first)) == 1
    else:
        assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
        assert first.claims == ()
        assert first.canonical_ceilings == ()
        assert first.quantity_evidence == ()
        assert publish_live_ceiling_area_quantities(first) == ()
        assert project_live_ceiling_area_customer_rows(
            first, workspace_id=1, project_id="synthetic-ceiling-unit",
        ) == ()


class _OriginalViewportStringAlias:
    """An untrusted object must not authenticate by rendering as an ID."""

    def __str__(self):
        return "source-viewport-1"


class _OriginalViewportStrSubclass(str):
    pass


@pytest.mark.parametrize(
    "forged",
    [
        " source-viewport-1", "source-viewport-1 ",
        "foreign-viewport", "", None, 1, b"source-viewport-1",
        _OriginalViewportStringAlias(),
        _OriginalViewportStrSubclass("source-viewport-1"),
    ],
)
def test_source_ceiling_viewport_receipt_must_be_exact_native_identity(forged):
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    quantity.metadata["viewport_id"] = forged
    original_metadata = dict(quantity.metadata)
    for _ in range(2):
        assert ceiling._claim_from_quantity(
            quantity=quantity, source_result=source,
            page_no=1, viewport_id="source-viewport-1",
        ) is None
    assert quantity.metadata == original_metadata


def test_native_source_ceiling_viewport_receipt_preserves_claim_and_input():
    quantity, source = _source_owned_ceiling_quantity_with_page(1)
    original_metadata = dict(quantity.metadata)
    first = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    second = ceiling._claim_from_quantity(
        quantity=quantity, source_result=source,
        page_no=1, viewport_id="source-viewport-1",
    )
    assert first is not None and first == second
    assert quantity.metadata == original_metadata


@pytest.mark.parametrize("variant", ["native", "padded", "foreign", "empty"])
def test_generated_pdf_original_ceiling_viewport_alias_abstains_at_real_customer(
    tmp_path, monkeypatch, variant
):
    from dataclasses import replace
    from pb_migration_provider_envelope import ProviderResult
    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(baseline.quantity_evidence) == 1
    assert len(publish_live_ceiling_area_quantities(baseline)) == 1

    real_run = ceiling.run_source_owned_ceiling_lining_shadow
    authentic_results = []
    variants_seen = []

    def changed_original_viewport(*args, **kwargs):
        result = real_run(*args, **kwargs)
        authentic_results.append(result)
        eligible = tuple(
            q for q in result.ceiling_quantities
            if ceiling._claim_from_quantity(
                quantity=q, source_result=result,
                page_no=kwargs["page_no"],
                viewport_id=kwargs["viewport"].viewport_id,
            ) is not None
        )
        assert len(eligible) == 1
        if variant == "native":
            variants_seen.append(variant)
            return result
        authentic = eligible[0]
        original_id = authentic.metadata["viewport_id"]
        forged = {
            "padded": f" {original_id} ",
            "foreign": "foreign-original-viewport",
            "empty": "",
        }[variant]
        changed = replace(
            authentic,
            metadata={**authentic.metadata, "viewport_id": forged},
        )
        rebuilt = ProviderResult.build(
            descriptor=result.pipeline.ceiling_result.descriptor,
            context=kwargs["context"],
            quantities=tuple(
                changed if q is authentic else q
                for q in result.ceiling_quantities
            ),
            entities=result.pipeline.ceiling_result.entities,
        )
        variants_seen.append(variant)
        return replace(
            result,
            pipeline=replace(result.pipeline, ceiling_result=rebuilt),
        )

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow",
        changed_original_viewport,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert variants_seen == [variant, variant]
    assert len(authentic_results) == 2
    assert authentic_results[0] == authentic_results[1]
    assert path.read_bytes() == original_pdf
    if variant == "native":
        assert first == baseline
        assert len(publish_live_ceiling_area_quantities(first)) == 1
    else:
        assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
        assert first.claims == ()
        assert first.canonical_ceilings == ()
        assert first.quantity_evidence == ()
        assert publish_live_ceiling_area_quantities(first) == ()
        assert project_live_ceiling_area_customer_rows(
            first, workspace_id=1, project_id="synthetic-viewport-receipt",
        ) == ()


class _SourceF07ViewportStringSubclass(str):
    """A foreign string-like identity must not be accepted as source native."""


@pytest.mark.parametrize(
    "variant",
    ["blank", "none", "missing", "numeric", "padded", "string_subclass", "spoofed"],
)
@pytest.mark.parametrize("sibling_position", ["first", "last"])
def test_generated_original_f07_malformed_sibling_revokes_complete_ceiling_run(
    tmp_path, monkeypatch, variant, sibling_position
):
    """An invalid authoritative F.07 sibling cannot leave earlier claims live."""
    from types import SimpleNamespace
    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(publish_live_ceiling_area_quantities(baseline)) == 1
    original_viewports = ceiling.authoritative_floor_plan_viewports
    seen = []

    def with_untrusted_sibling(page, *, page_number):
        native = tuple(original_viewports(page, page_number=page_number))
        assert native
        authentic = native[0]
        valid_id = authentic.view_id

        class SpoofedViewport:
            def __str__(self):
                return valid_id

        bad_id = {
            "blank": "",
            "none": None,
            "missing": None,
            "numeric": 7,
            "padded": f" {valid_id} ",
            "string_subclass": _SourceF07ViewportStringSubclass(valid_id),
            "spoofed": SpoofedViewport(),
        }[variant]
        sibling = SimpleNamespace(
            view_id=bad_id,
            bounding_box=authentic.bounding_box,
            confidence=authentic.confidence,
        )
        if variant == "missing":
            del sibling.view_id
        seen.append((page_number, sibling_position))
        return (sibling, *native) if sibling_position == "first" else (*native, sibling)

    monkeypatch.setattr(
        ceiling, "authoritative_floor_plan_viewports", with_untrusted_sibling,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert seen == [(1, sibling_position), (1, sibling_position)]
    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.reason_codes == (
        ceiling.LIVE_CEILING_LINING_UNAVAILABLE,
        ceiling.LIVE_CEILING_LINING_SOURCE_VIEWPORT_FAILURE,
    )
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="synthetic-f07-viewport-sibling",
    ) == ()
    assert path.read_bytes() == original_pdf


def test_generated_original_f07_native_viewport_keeps_real_issuer_output(tmp_path):
    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert len(first.claims) == 1
    assert len(first.canonical_ceilings) == 1
    assert len(publish_live_ceiling_area_quantities(first)) == 1
    assert path.read_bytes() == original_pdf


@pytest.mark.parametrize(
    "native_bbox",
    [
        (0, 0, 10, 20),
        (0.0, -4.5, 10.0, 20.0),
        [0.0, 0.0, 10.0, 20.0],
        (0, 0, 1 << 53, 20),
    ],
)
def test_original_f07_native_bbox_is_exact_and_deterministic(native_bbox):
    original = tuple(native_bbox)
    first = ceiling._source_viewport_bbox(native_bbox)
    second = ceiling._source_viewport_bbox(native_bbox)
    assert first == second
    assert first == tuple(float(item) for item in original)
    assert tuple(native_bbox) == original


class _SourceF07FloatSubclass(float):
    """A source-coordinate alias must not be silently coerced."""


@pytest.mark.parametrize(
    "variant",
    [
        "none", "missing", "short", "long", "boolean", "string",
        "float_subclass", "nan", "infinity", "zero_width", "zero_height",
        "inverted_x", "inverted_y", "oversized_int", "oversized_float",
        "huge_int", "non_iterable",
    ],
)
@pytest.mark.parametrize("sibling_position", ["first", "last"])
def test_generated_original_f07_invalid_bbox_revokes_whole_ceiling_run(
    tmp_path, monkeypatch, variant, sibling_position
):
    """Malformed source bounds cannot leave a valid sibling's ceiling live."""
    from types import SimpleNamespace
    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(publish_live_ceiling_area_quantities(baseline)) == 1

    original_viewports = ceiling.authoritative_floor_plan_viewports
    seen = []

    def with_invalid_source_bbox(page, *, page_number):
        native = tuple(original_viewports(page, page_number=page_number))
        assert native
        authentic = native[0]
        x0, y0, x1, y1 = authentic.bounding_box
        bad_bbox = {
            "none": None,
            "missing": None,
            "short": (x0, y0, x1),
            "long": (x0, y0, x1, y1, y1),
            "boolean": (True, y0, x1, y1),
            "string": (str(x0), y0, x1, y1),
            "float_subclass": (_SourceF07FloatSubclass(x0), y0, x1, y1),
            "nan": (x0, y0, float("nan"), y1),
            "infinity": (x0, y0, float("inf"), y1),
            "zero_width": (x0, y0, x0, y1),
            "zero_height": (x0, y0, x1, y0),
            "inverted_x": (x1, y0, x0, y1),
            "inverted_y": (x0, y1, x1, y0),
            "oversized_int": (x0, y0, (1 << 53) + 1, y1),
            "oversized_float": (x0, y0, float(1 << 54), y1),
            "huge_int": (x0, y0, 10**1000, y1),
            "non_iterable": object(),
        }[variant]
        sibling = SimpleNamespace(
            view_id=f"{authentic.view_id}-untrusted-bbox",
            bounding_box=bad_bbox,
            confidence=authentic.confidence,
        )
        if variant == "missing":
            del sibling.bounding_box
        seen.append((page_number, sibling_position))
        return (sibling, *native) if sibling_position == "first" else (*native, sibling)

    monkeypatch.setattr(
        ceiling, "authoritative_floor_plan_viewports", with_invalid_source_bbox,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert seen == [(1, sibling_position), (1, sibling_position)]
    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.reason_codes == (
        ceiling.LIVE_CEILING_LINING_UNAVAILABLE,
        ceiling.LIVE_CEILING_LINING_SOURCE_VIEWPORT_FAILURE,
    )
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="synthetic-f07-bbox",
    ) == ()
    assert path.read_bytes() == original_pdf


def _original_upstream_scope_fixture():
    from types import SimpleNamespace
    metadata = {
        "source_sha256": "a" * 64,
        "revision_id": "source-revision",
        "viewport_id": "source-viewport",
        "page_no": 1,
    }
    return SimpleNamespace(metadata=metadata), metadata


@pytest.mark.parametrize("page", [1, "1"])
def test_exact_native_original_upstream_area_scope_preserved(page):
    area, metadata = _original_upstream_scope_fixture()
    metadata["page_no"] = page
    before = dict(metadata)
    scope = dict(
        source_sha256="a" * 64, revision_id="source-revision",
        viewport_id="source-viewport", page_no=1,
    )
    assert ceiling._upstream_room_area_scope(area, **scope) == "exact"
    assert ceiling._upstream_room_area_scope(area, **scope) == "exact"
    assert area.metadata == before


@pytest.mark.parametrize(
    "field,bad",
    [
        ("source_sha256", " " + "a" * 64),
        ("source_sha256", "a" * 64 + " "),
        ("revision_id", " source-revision"),
        ("revision_id", "source-revision "),
        ("viewport_id", " source-viewport"),
        ("viewport_id", "source-viewport "),
        ("page_no", True),
        ("page_no", 1.0),
        ("page_no", " 1"),
        ("page_no", "1 "),
    ],
)
def test_upstream_original_room_area_scope_alias_is_negative_evidence(field, bad):
    area, metadata = _original_upstream_scope_fixture()
    metadata[field] = bad
    before = dict(metadata)
    scope = dict(
        source_sha256="a" * 64, revision_id="source-revision",
        viewport_id="source-viewport", page_no=1,
    )
    assert ceiling._upstream_room_area_scope(area, **scope) == "alias"
    assert ceiling._upstream_room_area_scope(area, **scope) == "alias"
    assert area.metadata == before


def test_foreign_original_room_area_scope_is_not_aliased_into_this_viewport():
    area, metadata = _original_upstream_scope_fixture()
    metadata["source_sha256"] = "b" * 64
    assert ceiling._upstream_room_area_scope(
        area, source_sha256="a" * 64, revision_id="source-revision",
        viewport_id="source-viewport", page_no=1,
    ) == "foreign"


@pytest.mark.parametrize(
    "field,alias",
    [
        ("source_sha256", "padded"), ("revision_id", "padded"),
        ("viewport_id", "padded"), ("page_no", "bool"),
        ("page_no", "float"), ("page_no", "padded"),
    ],
)
def test_original_upstream_scope_alias_revokes_real_ceiling_issuer_and_customer(
    tmp_path, monkeypatch, field, alias
):
    """Generated source-only PDF, never original source-positive FIRM proof."""
    from types import SimpleNamespace
    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    original_run = ceiling.run_source_owned_ceiling_lining_shadow
    contexts = []

    def capture_context(*args, **kwargs):
        contexts.append(kwargs["context"])
        return original_run(*args, **kwargs)

    monkeypatch.setattr(ceiling, "run_source_owned_ceiling_lining_shadow", capture_context)
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert contexts
    context = contexts[0]
    metadata = {
        "source_sha256": context.source_sha256,
        "revision_id": context.current_revision_id,
        "viewport_id": context.owned_viewport_ids[0],
        "page_no": context.owned_page_numbers[0],
    }
    native = SimpleNamespace(metadata=dict(metadata))
    forwarded = []

    def capture_upstream_scope(*args, **kwargs):
        forwarded.append(kwargs.get("authoritative_area_quantities"))
        # Never allow the injected metadata-only fixture to mint FIRM area.
        safe_kwargs = dict(kwargs)
        safe_kwargs["authoritative_area_quantities"] = None
        return original_run(*args, **safe_kwargs)

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow", capture_upstream_scope
    )
    positive = ceiling.collect_live_ceiling_lining_claims(
        path, pages=(0,), authoritative_room_area_quantities=(native,)
    )
    assert len(positive.claims) == len(baseline.claims)
    assert forwarded == [(native,)]
    assert native.metadata == metadata

    corrupted = dict(metadata)
    if alias == "padded":
        corrupted[field] = " " + str(corrupted[field])
    elif alias == "bool":
        corrupted[field] = True
    elif alias == "float":
        corrupted[field] = float(corrupted[field])
    rival = SimpleNamespace(metadata=corrupted)
    before = dict(rival.metadata)
    forwarded.clear()
    first = ceiling.collect_live_ceiling_lining_claims(
        path, pages=(0,), authoritative_room_area_quantities=(native, rival)
    )
    second = ceiling.collect_live_ceiling_lining_claims(
        path, pages=(0,), authoritative_room_area_quantities=(rival, native)
    )
    assert first == second
    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert ceiling.LIVE_CEILING_LINING_UPSTREAM_AREA_SCOPE_ALIAS in first.reason_codes
    assert forwarded == []
    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="source-neutral-scope-alias"
    ) == ()
    assert native.metadata == metadata
    assert rival.metadata == before
    assert path.read_bytes() == original_pdf



@pytest.mark.parametrize("duplicate_bbox", ["same", "shifted"])
@pytest.mark.parametrize("sibling_position", ["first", "last"])
def test_original_f07_reused_page_viewport_identity_revokes_real_customer(
    tmp_path, monkeypatch, duplicate_bbox, sibling_position
):
    """One page-owned source viewport cannot count twice under one receipt."""
    from types import SimpleNamespace
    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(publish_live_ceiling_area_quantities(baseline)) == 1
    original_viewports = ceiling.authoritative_floor_plan_viewports
    original_run = ceiling.run_source_owned_ceiling_lining_shadow
    source_calls = []
    returned_viewports = []

    def repeated_source_viewport(page, *, page_number):
        native = tuple(original_viewports(page, page_number=page_number))
        assert len(native) == 1
        authentic = native[0]
        x0, y0, x1, y1 = authentic.bounding_box
        forged_bbox = (
            authentic.bounding_box if duplicate_bbox == "same"
            else (x0 + 1.0, y0, x1, y1)
        )
        repeated = SimpleNamespace(
            view_id=authentic.view_id,
            bounding_box=forged_bbox,
            confidence=authentic.confidence,
        )
        returned_viewports.append(repeated)
        return (
            (repeated, authentic)
            if sibling_position == "first"
            else (authentic, repeated)
        )

    def count_source_calls(*args, **kwargs):
        source_calls.append((kwargs["page_no"], kwargs["viewport"].viewport_id))
        return original_run(*args, **kwargs)

    monkeypatch.setattr(
        ceiling, "authoritative_floor_plan_viewports", repeated_source_viewport
    )
    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow", count_source_calls
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert len(returned_viewports) == 2
    assert len(source_calls) == 2  # one source run, never the duplicate, per replay
    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.reason_codes == (
        ceiling.LIVE_CEILING_LINING_UNAVAILABLE,
        ceiling.LIVE_CEILING_LINING_SOURCE_VIEWPORT_FAILURE,
    )
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="synthetic-duplicate-f07",
    ) == ()
    assert path.read_bytes() == original_pdf
    assert all(item.view_id == source_calls[0][1] for item in returned_viewports)


@pytest.mark.parametrize("reuse_on_other_page", [False, True])
def test_original_f07_identity_census_preserves_distinct_source_scopes(
    tmp_path, monkeypatch, reuse_on_other_page
):
    """Different viewport IDs, or the same ID on another page, are not aliases."""
    from types import SimpleNamespace

    path = _generated_two_page_pdf(tmp_path)
    original_pdf = path.read_bytes()
    scanned = []
    original_viewports = (
        SimpleNamespace(
            view_id="source-viewport-a", bounding_box=(10, 10, 200, 150),
            confidence=0.99,
        ),
        SimpleNamespace(
            view_id="source-viewport-b", bounding_box=(10, 10, 200, 150),
            confidence=0.99,
        ),
    )

    def distinct_source_scopes(page, *, page_number):
        scanned.append(page_number)
        if reuse_on_other_page:
            return (original_viewports[0],)
        return original_viewports if page_number == 1 else ()

    calls = []

    def no_quantity_shadow(*args, **kwargs):
        calls.append((kwargs["page_no"], kwargs["viewport"].viewport_id))
        return SimpleNamespace(
            effective_context=kwargs["context"], ceiling_quantities=(),
        )

    monkeypatch.setattr(
        ceiling, "authoritative_floor_plan_viewports", distinct_source_scopes
    )
    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow", no_quantity_shadow
    )
    first = ceiling.collect_live_ceiling_lining_claims(
        path, pages=(0, 1), topology_pages=(0, 1),
    )
    second = ceiling.collect_live_ceiling_lining_claims(
        path, pages=(0, 1), topology_pages=(0, 1),
    )
    assert first == second
    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.reason_codes == (ceiling.LIVE_CEILING_LINING_UNAVAILABLE,)
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert len(calls) == 4
    assert scanned == [1, 2, 1, 2]
    if reuse_on_other_page:
        assert calls == [
            (1, "source-viewport-a"), (2, "source-viewport-a"),
            (1, "source-viewport-a"), (2, "source-viewport-a"),
        ]
    else:
        assert calls == [
            (1, "source-viewport-a"), (1, "source-viewport-b"),
            (1, "source-viewport-a"), (1, "source-viewport-b"),
        ]
    assert path.read_bytes() == original_pdf


class _ForeignSourceConfidenceFloat(float):
    """A float subclass is not an exact source-producer receipt."""


@pytest.mark.parametrize("value", [0, 1, 0.0, 0.5, 1.0])
def test_original_f07_native_confidence_controls_preserve_value(value):
    assert ceiling._source_viewport_confidence(value) == float(value)


@pytest.mark.parametrize(
    "bad_confidence",
    [
        None, True, False, "0.9", b"0.9", float("nan"),
        float("inf"), float("-inf"), -0.01, 1.01,
        10**1000, object(), _ForeignSourceConfidenceFloat(0.9),
    ],
)
@pytest.mark.parametrize("bad_first", [True, False])
def test_original_f07_confidence_alias_revokes_real_ceiling_customer_universe(
    tmp_path, monkeypatch, bad_confidence, bad_first
):
    """Generated native PDF + real source producer; malformed sibling only."""
    from types import SimpleNamespace
    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(publish_live_ceiling_area_quantities(baseline)) == 1
    real_viewports = ceiling.authoritative_floor_plan_viewports
    real_run = ceiling.run_source_owned_ceiling_lining_shadow
    shadow_calls = []
    injected = []

    def with_malformed_confidence(page, *, page_number):
        native = tuple(real_viewports(page, page_number=page_number))
        assert len(native) == 1
        authentic = native[0]
        forged = SimpleNamespace(
            view_id=authentic.view_id + "-foreign-confidence",
            bounding_box=authentic.bounding_box,
            confidence=bad_confidence,
        )
        injected.append(forged)
        return (forged, authentic) if bad_first else (authentic, forged)

    def count_shadow(*args, **kwargs):
        shadow_calls.append(kwargs["viewport"].viewport_id)
        return real_run(*args, **kwargs)

    monkeypatch.setattr(
        ceiling, "authoritative_floor_plan_viewports", with_malformed_confidence,
    )
    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow", count_shadow,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.reason_codes == (
        ceiling.LIVE_CEILING_LINING_UNAVAILABLE,
        ceiling.LIVE_CEILING_LINING_SOURCE_VIEWPORT_FAILURE,
    )
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="generated-f07-confidence-alias",
    ) == ()
    assert len(injected) == 2
    assert all(item.confidence is bad_confidence for item in injected)
    assert len(shadow_calls) == (0 if bad_first else 2)
    assert path.read_bytes() == original_pdf


class _ForeignCeilingQuantityConfidenceFloat(float):
    """Float subclasses are not native source quantity receipts."""


@pytest.mark.parametrize("native_confidence", [0, 0.0, 0.5, 1, 1.0])
def test_original_ceiling_quantity_native_confidence_is_retained(native_confidence):
    assert ceiling._source_ceiling_quantity_confidence(
        native_confidence
    ) == float(native_confidence)


@pytest.mark.parametrize(
    "bad_confidence",
    [
        None, True, False, "0.5", b"0.5", float("nan"),
        float("inf"), float("-inf"), -0.01, 1.01,
        10**1000, object(), _ForeignCeilingQuantityConfidenceFloat(0.5),
    ],
)
@pytest.mark.parametrize("bad_first", [True, False])
def test_original_ceiling_quantity_confidence_alias_abstains_through_customer(
    tmp_path, monkeypatch, bad_confidence, bad_first
):
    """Original-neutral PDF and real producer; only a quantity receipt is forged."""
    from types import SimpleNamespace
    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(publish_live_ceiling_area_quantities(baseline)) == 1
    real_run = ceiling.run_source_owned_ceiling_lining_shadow
    injected = []
    source_calls = []

    class QuantityUniverse:
        def __init__(self, authentic, quantities):
            self.authentic = authentic
            self.ceiling_quantities = quantities

        def __getattr__(self, field):
            return getattr(self.authentic, field)

    def with_foreign_quantity_confidence(*args, **kwargs):
        result = real_run(*args, **kwargs)
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
        forged = SimpleNamespace(
            **{
                **vars(authentic),
                "quantity_id": authentic.quantity_id + "-foreign-confidence",
                "confidence": bad_confidence,
            }
        )
        injected.append((authentic, forged))
        source_calls.append(kwargs["viewport"].viewport_id)
        quantities = (
            (forged,) + tuple(result.ceiling_quantities)
            if bad_first
            else tuple(result.ceiling_quantities) + (forged,)
        )
        return QuantityUniverse(result, quantities)

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow",
        with_foreign_quantity_confidence,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.reason_codes == (
        ceiling.LIVE_CEILING_LINING_UNAVAILABLE,
        ceiling.LIVE_CEILING_LINING_SOURCE_QUANTITY_CONFIDENCE_FAILURE,
    )
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="generated-ceiling-quantity-confidence",
    ) == ()
    assert len(source_calls) == 2
    assert len(injected) == 2
    assert all(forged.confidence is bad_confidence for _, forged in injected)
    assert all(authentic.confidence == baseline.claims[0].confidence
               for authentic, _ in injected)
    assert path.read_bytes() == original_pdf


class _ForeignPositiveCeilingIdSubclass(str):
    """A string subclass is not a native source-owned quantity identity."""


@pytest.mark.parametrize("bad_id_kind", [
    "leading", "trailing", "bytes", "boolean", "integer", "subclass",
])
@pytest.mark.parametrize("bad_first", [True, False])
def test_positive_ceiling_idless_sibling_revokes_complete_original_quantity_universe(
    tmp_path, monkeypatch, bad_id_kind, bad_first
):
    """Real generated-PDF producer/issuer/customer; one bad sibling revokes all.

    The genuine source-owned ceiling and generated PDF are not changed. This
    is a source-neutral negative invariant, NOT original-source FIRM proof.
    """
    from dataclasses import replace
    from types import SimpleNamespace

    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )
    from pb_live_ceiling_area_customer_projection import (
        project_live_ceiling_area_customer_rows,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    assert len(baseline.canonical_ceilings) == 1
    assert len(publish_live_ceiling_area_quantities(baseline)) == 1

    original_run = ceiling.run_source_owned_ceiling_lining_shadow
    originals = []

    def add_unidentifiable_positive_source_sibling(*args, **kwargs):
        result = original_run(*args, **kwargs)
        eligible = tuple(
            quantity for quantity in result.ceiling_quantities
            if ceiling._claim_from_quantity(
                quantity=quantity, source_result=result,
                page_no=kwargs["page_no"],
                viewport_id=kwargs["viewport"].viewport_id,
            ) is not None
        )
        assert len(eligible) == 1
        authentic = eligible[0]
        original_id = authentic.quantity_id
        bad_id = {
            "leading": " " + original_id,
            "trailing": original_id + " ",
            "bytes": original_id.encode("utf-8"),
            "boolean": True,
            "integer": 42,
            "subclass": _ForeignPositiveCeilingIdSubclass(original_id),
        }[bad_id_kind]
        sibling = SimpleNamespace(**{
            **vars(authentic),
            "quantity_id": bad_id,
        })
        assert not ceiling._exact_source_ceiling_quantity_id(sibling.quantity_id)
        assert sibling.abstained is False
        assert sibling.value > 0
        originals.append((authentic, dict(authentic.metadata), sibling))
        quantities = (
            (sibling,) + tuple(result.ceiling_quantities)
            if bad_first
            else tuple(result.ceiling_quantities) + (sibling,)
        )
        return replace(
            result,
            pipeline=replace(
                result.pipeline,
                ceiling_result=replace(
                    result.pipeline.ceiling_result, quantities=quantities,
                ),
            ),
        )

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow",
        add_unidentifiable_positive_source_sibling,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second
    assert first.status is ceiling.EvidenceResolutionStatus.ABSTAINED
    assert first.reason_codes == (
        ceiling.LIVE_CEILING_LINING_UNAVAILABLE,
        ceiling.LIVE_CEILING_LINING_SOURCE_QUANTITY_ID_FAILURE,
    )
    assert first.claims == ()
    assert first.canonical_ceilings == ()
    assert first.quantity_evidence == ()
    assert publish_live_ceiling_area_quantities(first) == ()
    assert project_live_ceiling_area_customer_rows(
        first, workspace_id=1, project_id="generated-invalid-positive-id-sibling",
    ) == ()
    assert len(originals) == 2
    assert all(
        authentic.metadata == metadata and authentic.quantity_id == baseline.quantity_evidence[0].quantity_id
        and sibling.value == authentic.value
        for authentic, metadata, sibling in originals
    )
    assert path.read_bytes() == original_pdf


@pytest.mark.parametrize("bad_first", [True, False])
def test_abstained_idless_diagnostic_sibling_does_not_revoke_valid_ceiling(
    tmp_path, monkeypatch, bad_first
):
    """An already-abstained empty diagnostic is not a positive source claimant."""
    from dataclasses import replace
    from types import SimpleNamespace

    from pb_live_ceiling_area_quantity_publication import (
        publish_live_ceiling_area_quantities,
    )

    path = _generated_source_owned_ceiling_pdf(tmp_path)
    original_pdf = path.read_bytes()
    baseline = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert len(baseline.claims) == 1
    original_run = ceiling.run_source_owned_ceiling_lining_shadow

    def add_abstained_diagnostic(*args, **kwargs):
        result = original_run(*args, **kwargs)
        eligible = tuple(
            quantity for quantity in result.ceiling_quantities
            if ceiling._claim_from_quantity(
                quantity=quantity, source_result=result,
                page_no=kwargs["page_no"],
                viewport_id=kwargs["viewport"].viewport_id,
            ) is not None
        )
        assert len(eligible) == 1
        authentic = eligible[0]
        diagnostic = SimpleNamespace(**{
            **vars(authentic),
            "quantity_id": " " + authentic.quantity_id,
            "abstained": True,
            "value": None,
        })
        quantities = (
            (diagnostic,) + tuple(result.ceiling_quantities)
            if bad_first
            else tuple(result.ceiling_quantities) + (diagnostic,)
        )
        return replace(
            result,
            pipeline=replace(
                result.pipeline,
                ceiling_result=replace(
                    result.pipeline.ceiling_result, quantities=quantities,
                ),
            ),
        )

    monkeypatch.setattr(
        ceiling, "run_source_owned_ceiling_lining_shadow", add_abstained_diagnostic,
    )
    first = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    second = ceiling.collect_live_ceiling_lining_claims(path, pages=(0,))
    assert first == second == baseline
    assert len(publish_live_ceiling_area_quantities(first)) == 1
    assert path.read_bytes() == original_pdf
