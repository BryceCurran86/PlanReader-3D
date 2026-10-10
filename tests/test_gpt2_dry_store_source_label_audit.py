"""Dry Store text discovery is never an authenticated room-area claim."""
from tools.diag_gpt2_maryborough_room_source_map import (
    _COMPILED,
    _ROOM_LABEL_PATTERNS,
)


def test_dry_store_is_explicit_source_native_label_candidate_only():
    assert "DRY STORE" in _ROOM_LABEL_PATTERNS
    assert _COMPILED["DRY STORE"].search("DRY STORE")
    assert _COMPILED["DRY STORE"].search("Dry   Store")
    assert _COMPILED["DRY STORE"].search("DRY\nSTORE")
    assert not _COMPILED["DRY STORE"].search("COLD STORE")


def test_dry_store_label_regex_does_not_parse_an_area_or_material():
    match = _COMPILED["DRY STORE"].search("DRY STORE")
    assert match is not None
    assert match.group(0) == "DRY STORE"
    # Every source-native match stays in LABEL CANDIDATE ONLY state.
    assert "area" not in _ROOM_LABEL_PATTERNS["DRY STORE"].lower()
