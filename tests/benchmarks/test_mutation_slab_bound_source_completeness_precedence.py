"""Source-complete slab-bound quantities beat larger partial source estimates."""
from __future__ import annotations

from types import SimpleNamespace
import math

import pytest

from pb_planreader_pdf_extractor import GenericPlanReaderExtractor as Extractor


def _row(quantity, complete, **metadata):
    return SimpleNamespace(
        quantity=quantity,
        metadata={"commercial_area_authorized": complete, **metadata},
    )


@pytest.mark.parametrize("quantity_family", [
    "substructure_bed_dpm", "substructure_a142_mesh",
    "substructure_surface_bed", "damp_proof_course",
])
def test_complete_smaller_source_can_replace_partial_larger_quantity(quantity_family):
    del quantity_family
    existing = _row(96.0, False)
    assert Extractor._should_replace_slab_bound_quantity(
        existing, 60.0, {"commercial_area_authorized": True}
    ) is True


@pytest.mark.parametrize("quantity_family", [
    "substructure_bed_dpm", "substructure_a142_mesh",
    "substructure_surface_bed", "damp_proof_course",
])
def test_partial_larger_source_must_not_replace_complete_quantity(quantity_family):
    del quantity_family
    existing = _row(60.0, True)
    assert Extractor._should_replace_slab_bound_quantity(
        existing, 96.0, {"commercial_area_authorized": False}
    ) is False


def test_equal_proof_keeps_existing_highest_legacy_positive_selection():
    assert Extractor._should_replace_slab_bound_quantity(
        _row(60.0, True), 70.0, {"commercial_area_authorized": True}
    ) is True
    assert Extractor._should_replace_slab_bound_quantity(
        _row(70.0, True), 60.0, {"commercial_area_authorized": True}
    ) is False
    assert Extractor._should_replace_slab_bound_quantity(
        _row(60.0, False), 70.0, {"commercial_area_authorized": False}
    ) is True


def test_declared_floor_area_metadata_does_not_establish_completeness():
    declared = {"declared_floor_area_m2": 999.0, "declared_floor_area_binding": "unbound"}
    assert Extractor._should_replace_slab_bound_quantity(_row(90.0, False), 100.0, declared)
    assert not Extractor._should_replace_slab_bound_quantity(_row(100.0, False), 90.0, declared)


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), -math.inf, 0.0, -1.0, True, None, "unresolved"])
def test_invalid_candidate_cannot_displace_evidenced_structural_area(invalid):
    assert Extractor._should_replace_slab_bound_quantity(
        _row(60.0, True), invalid, {"commercial_area_authorized": True}
    ) is False


def test_already_invalid_numeric_record_does_not_mint_a_replacement_by_order():
    assert Extractor._should_replace_slab_bound_quantity(
        _row(float("nan"), False), 90.0, {"commercial_area_authorized": True}
    ) is False
