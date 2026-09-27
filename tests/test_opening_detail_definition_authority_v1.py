from __future__ import annotations

from pb_source_execution_callout_authority import _Word
from pb_opening_detail_definition_authority import (
    _candidate,
    _claim_norm,
    _dimension_candidates,
    _norm,
)


def _word(obs: str, text: str, seq: int, x: float = 0.0) -> _Word:
    return _Word(
        observation_id=obs,
        receipt_id=f"receipt-{obs}",
        source_partition_id="partition",
        raw_text=text,
        geometry=(x, 0.0, x + 10.0, 10.0),
        sequence_start=seq,
        sequence_end=seq,
    )


def test_window_detail_definition_requires_one_dimension_and_window_family() -> None:
    cluster = (
        _word("w", "2,900mm", 1),
        _word("x", "x", 2),
        _word("h", "900mm", 3),
        _word("mat", "steel", 4),
        _word("sub", "casement", 5),
        _word("fam", "windows", 6),
    )
    result = _candidate(cluster)
    assert result is not None
    assert result["family"] == "window"
    assert result["subtype"] == "casement"
    assert result["material"] == "steel"
    assert result["width_mm"] == 2900
    assert result["height_mm"] == 900


def test_door_detail_definition_is_type_metadata_not_count() -> None:
    cluster = (
        _word("w", "1,000mm", 1),
        _word("x", "x", 2),
        _word("h", "2,100mm", 3),
        _word("mat", "timber", 4),
        _word("sub", "batten", 5),
        _word("fam", "door", 6),
        _word("countish", "3", 7),
        _word("nos", "nos.", 8),
        _word("hinges", "hinges", 9),
    )
    result = _candidate(cluster)
    assert result is not None
    assert result["family"] == "door"
    assert result["width_mm"] == 1000
    assert result["height_mm"] == 2100
    # Hinge count is not an opening count and does not participate.
    assert {w.observation_id for w in result["required_words"]} == {
        "w", "x", "h", "mat", "sub", "fam"
    }


def test_dimensions_without_opening_family_do_not_create_definition() -> None:
    assert _candidate((
        _word("w", "2900mm", 1),
        _word("x", "x", 2),
        _word("h", "900mm", 3),
        _word("steel", "steel", 4),
    )) is None


def test_opening_family_without_dimensions_does_not_create_definition() -> None:
    assert _candidate((
        _word("steel", "steel", 1),
        _word("casement", "casement", 2),
        _word("window", "window", 3),
    )) is None


def test_competing_window_and_door_semantics_abstain() -> None:
    assert _candidate((
        _word("w", "2900mm", 1),
        _word("x", "x", 2),
        _word("h", "900mm", 3),
        _word("window", "window", 4),
        _word("door", "door", 5),
    )) is None


def test_two_dimension_propositions_in_one_execution_run_abstain() -> None:
    assert _candidate((
        _word("w1", "2900mm", 1),
        _word("x1", "x", 2),
        _word("h1", "900mm", 3),
        _word("window", "window", 4),
        _word("w2", "3000mm", 5),
        _word("x2", "x", 6),
        _word("h2", "900mm", 7),
    )) is None


def test_conflicting_materials_abstain() -> None:
    assert _candidate((
        _word("w", "2900mm", 1),
        _word("x", "x", 2),
        _word("h", "900mm", 3),
        _word("window", "window", 4),
        _word("steel", "steel", 5),
        _word("timber", "timber", 6),
    )) is None


def test_conflicting_subtypes_abstain() -> None:
    assert _candidate((
        _word("w", "2900mm", 1),
        _word("x", "x", 2),
        _word("h", "900mm", 3),
        _word("window", "window", 4),
        _word("casement", "casement", 5),
        _word("sliding", "sliding", 6),
    )) is None


def test_plausibility_bounds_reject_non_opening_dimension_chain() -> None:
    assert _dimension_candidates((
        _word("w", "10150mm", 1),
        _word("x", "x", 2),
        _word("h", "9850mm", 3),
    )) == ()


def test_duplicate_identical_detail_definitions_are_semantically_equal_not_instances() -> None:
    left = _candidate((
        _word("lw", "2900mm", 1),
        _word("lx", "x", 2),
        _word("lh", "900mm", 3),
        _word("ls", "steel", 4),
        _word("lc", "casement", 5),
        _word("lf", "windows", 6),
    ))
    right = _candidate((
        _word("rw", "2900mm", 10),
        _word("rx", "x", 11),
        _word("rh", "900mm", 12),
        _word("rs", "steel", 13),
        _word("rc", "casement", 14),
        _word("rf", "windows", 15),
    ))
    assert left is not None and right is not None
    assert {
        key:left[key]
        for key in ("family","subtype","material","width_mm","height_mm")
    } == {
        key:right[key]
        for key in ("family","subtype","material","width_mm","height_mm")
    }


def test_text_claim_normalization_keeps_raster_corroboration_exact() -> None:
    # Raster corroboration may normalize punctuation/case/thousands separators
    # only; it may not reinterpret the native source token.
    assert _claim_norm("2,900mm") == _claim_norm("2900MM")
    assert _claim_norm("windows.") == _claim_norm("WINDOWS")
    assert _claim_norm("2,900mm") != _claim_norm("3,000mm")
    assert _claim_norm("windows") != _claim_norm("doors")
