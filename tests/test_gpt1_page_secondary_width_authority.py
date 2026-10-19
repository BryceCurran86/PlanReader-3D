"""Original-source numeric width witness ambiguity, not benchmark quantities."""
import pytest

from pb_gpt1_page_secondary_width_authority import (
    bind_page_secondary_width,
    resolve_original_page_secondary_width_text,
)


@pytest.mark.parametrize("note, expected", [
    ("2000mm wide verandah", 2.0),
    ("2m wide veranda", 2.0),
    ("verandah 2.000m", 2.0),
    ("2,000mm wide verandah", 2.0),
    ("2,5m wide verandah", 2.5),
])
def test_explicit_metric_page_note(note: str, expected: float) -> None:
    resolution = resolve_original_page_secondary_width_text(note)
    assert resolution.status == "one_explicit_dimension"
    assert resolution.width_m == pytest.approx(expected)


def test_two_original_different_widths_are_conflict_not_first_or_largest() -> None:
    result = resolve_original_page_secondary_width_text(
        "2m wide verandah\n2.5m wide verandah"
    )
    assert result.status == "conflicting_dimensions"
    assert result.width_m is None


def test_independent_spatial_and_text_witness_must_agree() -> None:
    assert bind_page_secondary_width(
        "2m wide verandah", 2.0,
    ).status == "corroborated"
    conflict = bind_page_secondary_width("2m wide verandah", 3.0)
    assert conflict.status == "spatial_text_dimension_conflict"
    assert conflict.width_m is None


def test_invalid_and_unfigured_verandah_cannot_become_metric_width() -> None:
    assert resolve_original_page_secondary_width_text(
        "VERANDAH WIDTH TO BE CONFIRMED"
    ).width_m is None
    assert resolve_original_page_secondary_width_text(
        "999999mm wide verandah"
    ).width_m is None
    assert resolve_original_page_secondary_width_text(
        "2 wide verandah"
    ).width_m is None
    assert bind_page_secondary_width("verandah", float("nan")).width_m is None
    assert bind_page_secondary_width("verandah", True).width_m is None


def test_mutual_repeated_same_original_width_is_allowed_without_double_count() -> None:
    result = resolve_original_page_secondary_width_text(
        "2m wide verandah\nverandah 2000mm"
    )
    assert result.width_m == pytest.approx(2.0)
    assert len(result.witnessed_widths_m) == 1
