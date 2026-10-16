"""Unbound architect-declared area components, never geometric FIRM quantities.

All examples are synthetic and project-neutral. Source pages and native text
blocks still require independently authenticated PDF glyph/clip ownership.
"""
from __future__ import annotations

from dataclasses import replace

import pytest

from pb_explicit_floor_area_evidence import (
    DECLARED_FLOOR_AREA_AUTHORITY,
    DECLARED_FLOOR_AREA_BINDING,
    extract_declared_component_floor_areas,
    extract_explicit_floor_area_evidence,
)


SOURCE_SHA = "a" * 64


def _parse(text: str, block: str = "native-block-1"):
    return extract_declared_component_floor_areas(
        text,
        source_page=3,
        source_block_id=block,
        source_sha256=SOURCE_SHA,
        revision_id="source-revision-1",
    )


def test_two_separate_original_component_rows_have_distinct_unbound_claims():
    rows = _parse("UPPER LIVING AREA:\n\n42.75m²\nGARAGE AREA:   18.50m2")
    assert [(row.label, row.area_m2) for row in rows] == [
        ("UPPER LIVING", 42.75),
        ("GARAGE", 18.50),
    ]
    assert {row.authority for row in rows} == {DECLARED_FLOOR_AREA_AUTHORITY}
    assert {row.binding for row in rows} == {DECLARED_FLOOR_AREA_BINDING}
    assert all(row.source_block_id == "native-block-1" for row in rows)
    assert all(row.source_sha256 == SOURCE_SHA for row in rows)


@pytest.mark.parametrize("unit", ["m²", "m2", "sqm", "sq m", "sq. m"])
def test_declared_metric_units_can_be_preserved_without_granting_authority(unit):
    row, = _parse(f"COURTYARD AREA: 5.125{unit}")
    assert row.area_m2 == 5.125
    assert row.binding == "unbound"


def test_aggregate_total_never_becomes_a_component_quantity():
    data = (
        "UPPER LIVING AREA: 42.75 m²\n"
        "GARAGE AREA: 18.50 m²\n"
        "TOTAL FLOOR AREA: 61.25 m²"
    )
    rows = _parse(data)
    assert len(rows) == 2
    assert all("TOTAL" not in row.label.upper() for row in rows)
    aggregate = extract_explicit_floor_area_evidence(
        "FLOOR PLAN\nTOTAL FLOOR AREA: 61.25m²",
        source_page=3,
        source_sha256=SOURCE_SHA,
    )
    assert aggregate is not None
    assert aggregate.area_m2 == 61.25
    assert aggregate.binding == "unbound"


@pytest.mark.parametrize("text", [
    "BEDROOM 10.0m2",
    "BALCONY AREA: 10.0 sq ft",
    "BALCONY AREA: 10.0",
    "BALCONY AREA: -10.0m²",
    "BALCONY AREA: 0.0m²",
    "BALCONY AREA:\nOTHER TEXT\n10.0m2",
    "BALCONY AREA: 3.0e5m2",
    "BALCONY AREA: True m²",
])
def test_unbound_parser_cannot_guess_area_or_unit(text):
    assert _parse(text) == ()


def test_duplicate_named_components_never_select_first_or_last_source_value():
    text = "GARAGE AREA: 18.50m²\nPORCH AREA: 2.25m²\nGARAGE AREA: 21.0m²"
    rows = _parse(text)
    assert [(row.label, row.area_m2) for row in rows] == [("PORCH", 2.25)]
    assert [(row.label, row.area_m2) for row in _parse("\n".join(reversed(text.splitlines())))] == [
        ("PORCH", 2.25)
    ]


def test_even_identical_repeated_label_does_not_imply_one_physical_zone():
    assert _parse("GARAGE AREA: 18.5m²\nGARAGE AREA: 18.5m²") == ()


def test_split_source_blocks_do_not_get_fused_across_native_boundaries():
    assert _parse("GARAGE AREA:") == ()
    assert _parse("18.50m²", block="native-block-2") == ()


def test_unrelated_schedule_or_untrusted_word_can_never_claim_firm_from_parser():
    rows = _parse("OFFICE AREA:\n2.75m²")
    assert len(rows) == 1
    assert not hasattr(rows[0], "quantity_id")
    assert not hasattr(rows[0], "input_entity_ids")
    assert not hasattr(rows[0], "canonical_floor_id")
    assert rows[0].binding == "unbound"


def test_source_row_order_preserves_set_of_independent_claims_and_no_mutation():
    lines = ["PORCH AREA: 2.5m²", "UPPER LIVING AREA: 42.5m²", "GARAGE AREA: 18.5m²"]
    before = tuple(lines)
    first = _parse("\n".join(lines))
    second = _parse("\n".join(reversed(lines)))
    assert {(row.label, row.area_m2) for row in first} == {
        (row.label, row.area_m2) for row in second
    }
    assert tuple(lines) == before


@pytest.mark.parametrize("bad", ["", "bad", "a" * 63, "G" * 64, True, 12])
def test_invalid_source_sha_cannot_be_stamped_as_source_identity(bad):
    with pytest.raises(ValueError):
        extract_declared_component_floor_areas(
            "LOFT AREA: 12.5m²",
            source_page=3, source_block_id="original-block", source_sha256=bad
        )


@pytest.mark.parametrize("bad", ["", " padded ", 13, True, None])
def test_original_block_address_must_be_explicit_and_canonical(bad):
    with pytest.raises(ValueError):
        extract_declared_component_floor_areas(
            "LOFT AREA: 12.5m²",
            source_page=3, source_block_id=bad
        )


def test_repeated_reads_are_deterministic_and_only_copy_source_fields():
    original = "ATTIC AREA:\n12.375m²"
    first = _parse(original)
    second = _parse(original)
    assert first == second
    assert first[0].source_page == 3
    assert first[0].revision_id == "source-revision-1"
    assert first[0].raw_evidence == "ATTIC AREA: 12.375m²"
