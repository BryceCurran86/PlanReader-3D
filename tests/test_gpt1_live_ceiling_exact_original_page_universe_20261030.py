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
