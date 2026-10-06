from __future__ import annotations

import fitz
import pytest
import pb_opening_label_dimension_authority as label_dimension_module

from pb_migration_contracts import EvidenceResolutionStatus
from pb_opening_label_dimension_authority import (
    OPENING_LABEL_DIMENSION_AMBIGUOUS,
    OPENING_LABEL_DIMENSION_RESOLVED,
    OPENING_LABEL_DIMENSION_TEXT_UNAVAILABLE,
    OpeningLabelDimensionProducer,
    _parseable_opening_label_fragments,
    parse_opening_label_dimensions,
)
from pb_physical_opening_authority import PHYSICAL_OPENING_EXISTS, PhysicalOpeningExistenceRecord
from pb_source_observation_authority import ObservationSelector
from pb_source_visibility_authority import SourceVisibilityProducer


def test_parser_accepts_full_metric_opening_labels_without_resolving_axis_order() -> None:
    window = parse_opening_label_dimensions("1,200 - 1,810 asw")
    assert window is not None
    assert window.dimension_values_mm == (1200.0, 1810.0)
    assert window.semantic_kind is None
    assert window.suffix_text.lower() == "asw"
    assert window.area_m2 == pytest.approx(2.172)
    assert window.compact_hundreds_used is False

    door = parse_opening_label_dimensions("2,100 - 4,800 Panel Lift Door")
    assert door is not None
    assert door.dimension_values_mm == (2100.0, 4800.0)
    assert door.semantic_kind is None
    assert "door" in door.suffix_text.lower()
    assert door.area_m2 == pytest.approx(10.08)


def test_parser_accepts_typed_compact_hundred_mm_notation_only() -> None:
    door = parse_opening_label_dimensions("21 - 15 - asd")
    assert door is not None
    assert door.dimension_values_mm == ()
    assert door.semantic_kind is None
    assert door.suffix_text.lower().endswith("asd")
    assert door.compact_hundreds_present is True
    assert door.compact_hundreds_used is False
    assert door.area_m2 is None

    window = parse_opening_label_dimensions("18 - 09 adh")
    assert window is not None
    assert window.dimension_values_mm == ()
    assert window.semantic_kind is None
    assert window.suffix_text.lower() == "adh"
    assert window.compact_hundreds_present is True
    assert window.compact_hundreds_used is False
    assert window.area_m2 is None

    # Untyped two-digit arithmetic/text cannot silently become dimensions.
    assert parse_opening_label_dimensions("21 - 15") is None

def test_parser_supports_unseparated_four_digit_compact_syntax_without_semantics() -> None:
    compact = parse_opening_label_dimensions("1218 SGW")
    assert compact is not None
    assert compact.dimension_tokens == ("12", "18")
    assert compact.dimension_values_mm == ()
    assert compact.compact_hundreds_present is True
    assert compact.compact_hundreds_used is False
    assert compact.semantic_kind is None
    assert compact.suffix_text == "SGW"
    assert compact.area_m2 is None

    # Bare NNNN remains an ambiguous/single metric token. The parser does not
    # silently reinterpret every four-digit number as HHWW.
    bare = parse_opening_label_dimensions("1218")
    assert bare is not None
    assert bare.dimension_tokens == ("1218",)
    assert bare.dimension_values_mm == (1218.0,)
    assert bare.compact_hundreds_present is False
    assert bare.area_m2 is None


def test_four_digit_compact_parser_is_deterministic_and_descriptor_agnostic() -> None:
    first = parse_opening_label_dimensions("2127 STACKER")
    second = parse_opening_label_dimensions("2127 STACKER")
    unknown = parse_opening_label_dimensions("2127 UNKNOWN")

    assert first == second
    assert first is not None
    assert first.dimension_tokens == ("21", "27")
    assert first.semantic_kind is None
    assert first.suffix_text == "STACKER"

    # Syntax can be recognized without granting semantic authority.
    assert unknown is not None
    assert unknown.dimension_tokens == ("21", "27")
    assert unknown.semantic_kind is None
    assert unknown.dimension_values_mm == ()


def _word_row(order: int, text: str, x0: float):
    width = max(4.0, len(text) * 4.0)
    return (order, f"obs-{order}", text, (x0, 10.0, x0 + width, 18.0))


def test_native_line_with_two_adjacent_opening_callouts_is_split_without_merging() -> None:
    rows = (
        _word_row(0, "1,800", 0.0),
        _word_row(1, "-", 28.0),
        _word_row(2, "610", 34.0),
        _word_row(3, "1,200", 70.0),
        _word_row(4, "-", 98.0),
        _word_row(5, "1,810", 104.0),
        _word_row(6, "asw", 134.0),
    )
    fragments = _parseable_opening_label_fragments(rows)
    assert [fragment.text for fragment in fragments] == [
        "1,800 - 610",
        "1,200 - 1,810 asw",
    ]


def test_longer_syntax_span_outranks_its_contained_subparse() -> None:
    rows = (
        _word_row(0, "1,200", 0.0),
        _word_row(1, "-", 28.0),
        _word_row(2, "1,810", 34.0),
        _word_row(3, "asw", 64.0),
    )
    fragments = _parseable_opening_label_fragments(rows)
    assert len(fragments) == 1
    assert fragments[0].text == "1,200 - 1,810 asw"


def test_fragment_selection_preserves_equal_rank_ties_deterministically() -> None:
    from pb_opening_label_dimension_authority import (
        _TrustedTextLine,
        _select_fragment_candidates,
    )

    first = _TrustedTextLine(("obs-a",), "first", (0.0, 0.0, 10.0, 10.0))
    second = _TrustedTextLine(("obs-b",), "second", (5.0, 0.0, 15.0, 10.0))
    candidates = (
        ((2, 3), 0, 3, first),
        ((2, 3), 2, 5, second),
    )
    forward = _select_fragment_candidates(candidates)
    reverse = _select_fragment_candidates(tuple(reversed(candidates)))
    assert tuple(item.text for item in forward) == ("first", "second")
    assert tuple(item.text for item in reverse) == ("first", "second")


def test_fragment_rank_ignores_semantic_kind_and_uses_syntax_span_only() -> None:
    from pb_opening_label_dimension_authority import (
        _TrustedTextLine,
        _select_fragment_candidates,
    )

    shorter = _TrustedTextLine(("obs-a",), "1200 - 1810", (0.0, 0.0, 10.0, 10.0))
    longer = _TrustedTextLine(
        ("obs-a", "obs-b"), "1200 - 1810 asw", (0.0, 0.0, 12.0, 10.0)
    )
    selected = _select_fragment_candidates(
        (((2, 3), 0, 3, shorter), ((2, 4), 0, 4, longer))
    )
    assert tuple(item.text for item in selected) == ("1200 - 1810 asw",)

def test_dimension_pair_delimiter_prevents_single_token_subparse() -> None:
    rows = (
        _word_row(0, "1,800", 0.0),
        _word_row(1, "-", 28.0),
    )
    assert _parseable_opening_label_fragments(rows) == ()


def test_pair_callout_outranks_single_dimension_subparses() -> None:
    rows = (
        _word_row(0, "2,100", 0.0),
        _word_row(1, "x", 28.0),
        _word_row(2, "1,030", 34.0),
    )
    fragments = _parseable_opening_label_fragments(rows)
    assert len(fragments) == 1
    assert fragments[0].text == "2,100 x 1,030"


def test_compact_door_and_metric_window_callouts_can_share_one_native_line() -> None:
    rows = (
        _word_row(0, "21", 0.0),
        _word_row(1, "-", 12.0),
        _word_row(2, "15", 18.0),
        _word_row(3, "-", 30.0),
        _word_row(4, "asd", 36.0),
        _word_row(5, "600", 58.0),
        _word_row(6, "-", 74.0),
        _word_row(7, "1,510", 80.0),
        _word_row(8, "asw", 108.0),
    )
    fragments = _parseable_opening_label_fragments(rows)
    assert [fragment.text for fragment in fragments] == [
        "21 - 15 - asd",
        "600 - 1,510 asw",
    ]


def test_non_opening_text_fragments_are_not_created_from_native_line() -> None:
    rows = (
        _word_row(0, "900x1200", 0.0),
        _word_row(1, "CLEAR", 40.0),
        _word_row(2, "04", 75.0),
        _word_row(3, "-", 87.0),
        _word_row(4, "06", 93.0),
        _word_row(5, "Niche", 108.0),
        _word_row(6, "Scale", 145.0),
        _word_row(7, "1:100", 170.0),
    )
    assert _parseable_opening_label_fragments(rows) == ()


def test_parser_rejects_dangling_single_dimension_separator_fragments() -> None:
    assert parse_opening_label_dimensions("1,800 -") is None
    assert parse_opening_label_dimensions("2,100 x") is None
    assert parse_opening_label_dimensions("2,100 ×") is None


def test_parser_retains_suffix_syntax_without_resolving_semantic_kind() -> None:
    coded_window = parse_opening_label_dimensions("1,200 - 1,810 asw")
    assert coded_window is not None
    assert coded_window.semantic_kind is None
    assert coded_window.suffix_text.lower() == "asw"

    coded_door = parse_opening_label_dimensions("1,200 vsd")
    assert coded_door is not None
    assert coded_door.semantic_kind is None
    assert coded_door.suffix_text.lower() == "vsd"

    explicit_door = parse_opening_label_dimensions(
        "2,100 - 4,800 Panel Lift Door"
    )
    assert explicit_door is not None
    assert explicit_door.semantic_kind is None
    assert "panel lift door" in explicit_door.suffix_text.lower()

def test_parser_keeps_single_dimension_separate_and_rejects_clear_zone_text() -> None:
    sliding = parse_opening_label_dimensions("1,200 vsd")
    assert sliding is not None
    assert sliding.dimension_values_mm == (1200.0,)
    assert sliding.semantic_kind is None
    assert sliding.suffix_text.lower() == "vsd"
    assert sliding.area_m2 is None

    assert parse_opening_label_dimensions("900x1200 CLEAR") is None
    assert parse_opening_label_dimensions("04 - 06 Niche") is None
    assert parse_opening_label_dimensions("Scale 1:100") is None


def _pdf(
    *,
    labels: tuple[tuple[float, float, str], ...],
) -> bytes:
    doc = fitz.open()
    try:
        page = doc.new_page(width=320.0, height=220.0)
        for first, second in (
            ((20.0, 100.0), (100.0, 100.0)),
            ((140.0, 100.0), (220.0, 100.0)),
            ((20.0, 110.0), (100.0, 110.0)),
            ((140.0, 110.0), (220.0, 110.0)),
            ((100.0, 100.0), (100.0, 110.0)),
            ((140.0, 100.0), (140.0, 110.0)),
        ):
            page.draw_line(fitz.Point(*first), fitz.Point(*second), width=1.0)
        for x, y, text in labels:
            page.insert_text(fitz.Point(x, y), text, fontsize=7.0)
        return bytes(doc.tobytes(garbage=4, deflate=True))
    finally:
        doc.close()


def _ingest(payload: bytes, name: str):
    source = SourceVisibilityProducer(
        producer_method="opening-label-dimension-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id="opening-label:" + name,
        source_bytes=payload,
        source_locator="fixture:" + name,
    )
    return source, published


def _selector(published, observation_id: str) -> ObservationSelector:
    return ObservationSelector(
        document_id=published.revision.document_id,
        revision_id=published.revision.revision_id,
        source_sha256=published.revision.source_sha256,
        snapshot_id=published.snapshot.snapshot_id,
        observation_id=observation_id,
    )


def _opening_selector(source, published) -> ObservationSelector:
    physical = source.physical_opening_authority()
    found = {}
    for observation_id in published.visible_observation_ids:
        selector = _selector(published, observation_id)
        result = physical.prove_existence(selector)
        if (
            result.status is EvidenceResolutionStatus.CORROBORATED
            and result.proposition == PHYSICAL_OPENING_EXISTS
            and result.existence_record is not None
        ):
            found[result.existence_record.record_id] = selector
    assert len(found) == 1
    return next(iter(found.values()))


def test_producer_binds_one_figured_pair_by_gap_projection_not_nearest_choice() -> None:
    source, published = _ingest(
        _pdf(labels=((88.0, 124.0, "900 - 1200 asw"),)),
        "positive",
    )
    selector = _opening_selector(source, published)
    producer = OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    result = producer.publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.reason_codes == (OPENING_LABEL_DIMENSION_RESOLVED,)
    assert result.evidence is not None
    assert result.evidence.dimension_values_mm == (900.0, 1200.0)
    assert result.evidence.semantic_kind == "window"
    assert result.evidence.area_m2 == pytest.approx(1.08)
    assert result.evidence.axis_order_resolved is False
    assert result.evidence.source_text_observation_ids


def test_compact_expansion_requires_authenticated_owned_opening() -> None:
    from pb_opening_label_dimension_authority import (
        _resolve_owned_dimension_values_mm,
    )

    parsed = parse_opening_label_dimensions("18 - 09 adh")
    assert parsed is not None
    assert parsed.dimension_values_mm == ()
    assert _resolve_owned_dimension_values_mm(
        parsed, opening_record_id="", semantic_kind="window"
    ) is None
    assert _resolve_owned_dimension_values_mm(
        parsed, opening_record_id="owned-opening", semantic_kind=None
    ) is None
    resolved = _resolve_owned_dimension_values_mm(
        parsed, opening_record_id="owned-opening", semantic_kind="window"
    )
    assert resolved == ((1800.0, 900.0), True)

    compact_window = parse_opening_label_dimensions("1218 SGW")
    assert compact_window is not None
    # An explicit generic opening descriptor can unlock compact units only
    # after a physical opening is independently authenticated.
    assert _resolve_owned_dimension_values_mm(
        compact_window,
        opening_record_id="",
        semantic_kind="window",
    ) is None
    assert _resolve_owned_dimension_values_mm(
        compact_window,
        opening_record_id="owned-opening",
        semantic_kind="window",
    ) == ((1200.0, 1800.0), True)

    unknown = parse_opening_label_dimensions("1218 UNKNOWN")
    assert unknown is not None
    assert _resolve_owned_dimension_values_mm(
        unknown,
        opening_record_id="owned-opening",
        semantic_kind="window",
    ) is None


def test_producer_expands_compact_dimensions_only_after_physical_ownership() -> None:
    source, published = _ingest(
        _pdf(labels=((88.0, 124.0, "18 - 09 adh"),)),
        "compact-owned",
    )
    selector = _opening_selector(source, published)
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.dimension_values_mm == (1800.0, 900.0)
    assert result.evidence.semantic_kind == "window"
    assert result.evidence.area_m2 == pytest.approx(1.62)
    assert result.evidence.opening_record_id
    assert result.evidence.source_text_observation_ids

@pytest.mark.parametrize(
    ("label", "expected_kind", "expected_values", "expected_area"),
    (
        ("1218 SGW", "window", (1200.0, 1800.0), 2.16),
        ("0630 FG", "window", (600.0, 3000.0), 1.8),
        ("2124 CORNER STACK", "door", (2100.0, 2400.0), 5.04),
        ("2148 PANEL LIFT", "door", (2100.0, 4800.0), 10.08),
    ),
)
def test_owned_generic_compact_descriptors_unlock_source_dimensions_without_legend(
    label: str,
    expected_kind: str,
    expected_values: tuple[float, float],
    expected_area: float,
) -> None:
    source, published = _ingest(
        _pdf(labels=((88.0, 124.0, label),)),
        "compact-owned-generic-" + label.lower().replace(" ", "-"),
    )
    selector = _opening_selector(source, published)
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.semantic_kind == expected_kind
    assert result.evidence.dimension_values_mm == expected_values
    assert result.evidence.area_m2 == pytest.approx(expected_area)
    assert result.evidence.opening_record_id
    assert result.evidence.source_text_observation_ids


def test_owned_legend_semantics_unlock_four_digit_compact_dimensions() -> None:
    payload = _pdf(
        labels=(
            (105.0, 124.0, "1218 SGW"),
            (20.0, 180.0, "LEGEND"),
            (20.0, 195.0, "SGW SLIDING GLASS WINDOW"),
        )
    )
    source, published = _ingest(payload, "compact-four-digit-owned")
    selector = _opening_selector(source, published)
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.semantic_kind == "window"
    assert result.evidence.dimension_values_mm == (1200.0, 1800.0)
    assert result.evidence.area_m2 == pytest.approx(2.16)
    assert result.evidence.opening_record_id
    assert result.evidence.source_text_observation_ids


def test_unowned_or_unauthenticated_four_digit_suffix_cannot_unlock_dimensions() -> None:
    source, published = _ingest(
        _pdf(labels=((105.0, 124.0, "1218 UNKNOWN"),)),
        "compact-four-digit-unknown",
    )
    selector = _opening_selector(source, published)
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None


def test_producer_stitches_one_source_callout_split_over_adjacent_native_lines() -> None:
    source, published = _ingest(
        _pdf(
            labels=(
                (108.0, 120.0, "1,800 -"),
                (108.0, 128.0, "910 asw"),
            )
        ),
        "split-callout",
    )
    selector = _opening_selector(source, published)
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.dimension_values_mm == (1800.0, 910.0)
    assert result.evidence.semantic_kind == "window"
    assert result.evidence.area_m2 == pytest.approx(1.638)
    assert len(result.evidence.source_text_observation_ids) >= 2


def test_producer_stitches_semantic_modifier_from_adjacent_native_line() -> None:
    source, published = _ingest(
        _pdf(
            labels=(
                (108.0, 120.0, "1,800 - 610"),
                (108.0, 128.0, "asw obs"),
            )
        ),
        "split-semantic-modifier",
    )
    selector = _opening_selector(source, published)
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.CORROBORATED
    assert result.evidence is not None
    assert result.evidence.dimension_values_mm == (1800.0, 610.0)
    assert result.evidence.semantic_kind == "window"
    assert result.evidence.area_m2 == pytest.approx(1.098)


def test_remote_lines_with_complementary_syntax_do_not_stitch() -> None:
    source, published = _ingest(
        _pdf(
            labels=(
                (108.0, 120.0, "1,800 -"),
                (108.0, 180.0, "910 asw"),
            )
        ),
        "split-remote",
    )
    selector = _opening_selector(source, published)
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
    assert OPENING_LABEL_DIMENSION_TEXT_UNAVAILABLE in result.reason_codes


def test_split_niche_annotation_does_not_become_opening_dimension() -> None:
    source, published = _ingest(
        _pdf(
            labels=(
                (108.0, 120.0, "04 - 06"),
                (108.0, 128.0, "Niche"),
            )
        ),
        "split-niche",
    )
    selector = _opening_selector(source, published)
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None


def test_two_distinct_eligible_callouts_conflict_instead_of_picking_closest() -> None:
    source, published = _ingest(
        _pdf(
            labels=(
                (88.0, 121.0, "900 - 1200 asw"),
                (88.0, 130.0, "1000 - 1200 asw"),
            )
        ),
        "ambiguous",
    )
    selector = _opening_selector(source, published)
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.CONFLICT
    assert result.evidence is None
    assert OPENING_LABEL_DIMENSION_AMBIGUOUS in result.reason_codes


def test_spatially_remote_label_cannot_bind_even_when_text_is_plausible() -> None:
    source, published = _ingest(
        _pdf(labels=((235.0, 124.0, "900 - 1200 asw"),)),
        "remote",
    )
    selector = _opening_selector(source, published)
    result = OpeningLabelDimensionProducer.from_source_visibility_producer(
        source
    ).publish_scope(selector)

    assert result.status is EvidenceResolutionStatus.ABSTAINED
    assert result.evidence is None
    assert OPENING_LABEL_DIMENSION_TEXT_UNAVAILABLE in result.reason_codes



def test_trusted_text_line_cache_reuses_page_snapshot_and_fails_closed_after_snapshot_change(monkeypatch) -> None:
    from types import SimpleNamespace

    source = SourceVisibilityProducer(
        producer_method="dimension-text-cache",
        producer_version="1",
    )
    producer = OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    opening = PhysicalOpeningExistenceRecord(
        record_id="opening:1",
        source_observation_ids=("source:1",),
        source_lineage_root_ids=("source:1",),
        document_id="doc",
        revision_id="rev",
        source_sha256="sha",
        snapshot_id="snap",
        page_id="3",
        viewport_id="page:3",
        semantic_class="opening",
        status=EvidenceResolutionStatus.CORROBORATED,
        proposition=PHYSICAL_OPENING_EXISTS,
        structural_pattern="jamb_bounded_two_face_interruption",
        diagnostic_confidence=1.0,
        blocking_reasons=(),
        structural_reason_codes=(),
        producer_method="test",
        producer_version="1",
        producer_generation=1,
    )

    state = {"snapshot_id": "snap"}
    monkeypatch.setattr(
        source,
        "published_snapshot_for_revision",
        lambda _revision_id: SimpleNamespace(
            snapshot=SimpleNamespace(snapshot_id=state["snapshot_id"])
        ),
    )

    trusted_line = label_dimension_module._TrustedTextLine(
        observation_ids=("text:1",),
        text="900 - 1200 asw",
        bbox=(10.0, 20.0, 30.0, 40.0),
    )
    calls = 0

    def build_lines(_source, _opening):
        nonlocal calls
        calls += 1
        return (trusted_line,)

    monkeypatch.setattr(label_dimension_module, "_trusted_text_lines", build_lines)

    assert producer._trusted_text_lines_for_opening(opening) == (trusted_line,)
    assert producer._trusted_text_lines_for_opening(opening) == (trusted_line,)
    assert calls == 1

    # Cache hits must never bypass current source lineage. Once the producer's
    # current snapshot changes, the historical opening fails closed.
    state["snapshot_id"] = "new-snapshot"
    assert producer._trusted_text_lines_for_opening(opening) == ()
    assert calls == 1
