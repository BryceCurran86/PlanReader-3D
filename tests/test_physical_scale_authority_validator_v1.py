"""Physical scale authority V1 validator foundation.

TEST-ONLY / EXPECTED-RED / SELF-AUTHORED / NOT FROZEN / DO NOT MERGE.

Current production-safe scale helpers must remain fail-closed.  The future sealed
physical-scale authority is intentionally absent until a real source-native FIRM
scale producer exists.
"""
from __future__ import annotations

from dataclasses import fields, is_dataclass
import importlib
import importlib.util
import inspect

import pytest

from pb_geometry_takeoff_model import AuthorityStatus, ScaleCalibration
from pb_page_scale_calibration_authority import (
    ScaleCalibrationStatus,
    ScaleSourceType,
    measurement_authority_for_page_scale,
)
from pb_viewport_scale_binding import bind_viewport_scale
from pb_viewport_segmentation import (
    SegmentedViewport,
    ViewportBoundarySource,
    ViewportSegmentationStatus,
)


MODULE_NAME = "pb_physical_scale_authority"
HAS_PHYSICAL_SCALE_AUTHORITY = importlib.util.find_spec(MODULE_NAME) is not None
EXPECTED_RED = pytest.mark.xfail(
    condition=not HAS_PHYSICAL_SCALE_AUTHORITY,
    strict=True,
    reason="producer-owned source-native FIRM physical scale authority is intentionally absent",
)

_FORBIDDEN_PUBLIC = {
    "px_per_m", "points_per_m", "points_per_mm", "mm_per_point",
    "conversion_factor", "ratio", "scale_ratio", "denominator", "scale_text",
    "calibration", "scale_calibration", "viewport_scale_binding", "is_verified",
    "status", "measurement_authority", "firm", "confidence", "source_type",
    "complete", "claimed_complete", "count", "fingerprint", "nearest", "first",
    "radius", "graphic_scale_bar", "bar_start", "bar_end", "labelled_length",
}


def test_title_block_only_scale_remains_provisional_not_firm() -> None:
    calibration = ScaleCalibration(
        page_no=1,
        ratio_str="1:100",
        px_per_m=28.346456692913385,
        method="TITLE_BLOCK",
        is_verified=True,
        confidence=1.0,
        source_type=ScaleSourceType.TITLE_BLOCK.value,
        status=ScaleCalibrationStatus.VALID.value,
        revision_id="rev-1",
    )
    assert measurement_authority_for_page_scale(calibration) == AuthorityStatus.PROVISIONAL.value


def test_viewport_text_scale_is_not_promoted_to_firm() -> None:
    viewport = SegmentedViewport(
        view_id="vp-1",
        page_number=1,
        view_type="floor_plan",
        label="GROUND FLOOR PLAN SCALE 1:100",
        title_bbox=(10.0, 10.0, 150.0, 25.0),
        bounding_box=(0.0, 0.0, 500.0, 500.0),
        status=ViewportSegmentationStatus.RESOLVED.value,
        boundary_source=ViewportBoundarySource.VECTOR_FRAME.value,
        confidence=1.0,
        scale_raw="SCALE 1:100",
        scale_denominator=100.0,
    )
    binding = bind_viewport_scale(
        viewport,
        page_no=1,
        revision_id="rev-1",
        sheet_label="A101",
        source_sha256="sha-1",
    )
    assert binding.measurement_authority != AuthorityStatus.FIRM.value
    assert binding.abstained is True
    assert "scale_not_firm" in binding.blocking_reasons


def test_plain_scale_calibration_is_constructible_and_therefore_not_a_sealed_source_proposition() -> None:
    calibration = ScaleCalibration(
        page_no=99,
        ratio_str="1:1",
        px_per_m=999999.0,
        method="CALLER",
        is_verified=True,
        confidence=1.0,
        source_type=ScaleSourceType.SCALE_BAR.value,
        status=ScaleCalibrationStatus.VALID.value,
    )
    assert calibration.is_usable_for_firm_measurement() is True
    # This test documents the seam: future physical-void authority must not accept
    # this ordinary data object as producer authentication.
    assert is_dataclass(calibration)


@EXPECTED_RED
def test_future_physical_scale_api_is_sealed_and_selector_only() -> None:
    mod = importlib.import_module(MODULE_NAME)
    required = {
        "PhysicalScaleSelector",
        "PhysicalScaleEvidence",
        "PhysicalScaleResult",
        "PhysicalScaleAuthority",
        "PhysicalScaleProducer",
    }
    assert required <= set(dir(mod))
    assert is_dataclass(mod.PhysicalScaleSelector)
    selector_fields = {field.name for field in fields(mod.PhysicalScaleSelector)}
    assert not (selector_fields & _FORBIDDEN_PUBLIC)
    for callable_obj in (
        mod.PhysicalScaleProducer.publish_scope,
        mod.PhysicalScaleAuthority.resolve,
    ):
        assert not (set(inspect.signature(callable_obj).parameters) & _FORBIDDEN_PUBLIC)


@EXPECTED_RED
def test_future_scale_producer_does_not_accept_caller_calibration_or_ratio_truth() -> None:
    mod = importlib.import_module(MODULE_NAME)
    params = set(inspect.signature(mod.PhysicalScaleProducer.publish_scope).parameters)
    assert params <= {
        "self", "selector",
    }
    assert not (params & _FORBIDDEN_PUBLIC)


@EXPECTED_RED
def test_future_scale_authority_requires_source_native_positive_capability() -> None:
    mod = importlib.import_module(MODULE_NAME)
    capabilities = mod.PhysicalScaleProducer.capabilities()
    assert capabilities["source_native_firm_scale"] is False
    assert capabilities["title_block_text_can_mint_firm"] is False
    assert capabilities["caller_calibration_can_mint_firm"] is False
