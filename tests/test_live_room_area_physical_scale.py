from __future__ import annotations

from pathlib import Path

from pb_geometry_takeoff_model import AuthorityStatus, MeasurementAuthorityType
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from tests.test_ceiling_lining_review_promotion_v1 import _source_pdf


def _write(tmp_path: Path, *, include_scale_bar: bool) -> Path:
    path = tmp_path / (
        "room-scale-bar.pdf" if include_scale_bar else "room-title-scale-only.pdf"
    )
    path.write_bytes(_source_pdf(include_scale_bar=include_scale_bar))
    return path


def test_native_graphic_scale_bar_produces_firm_live_room_and_floor_areas(tmp_path) -> None:
    claim = collect_live_physical_net_wall_claim(
        _write(tmp_path, include_scale_bar=True),
        pages=(0,),
    )

    firm = [
        quantity
        for quantity in claim.room_area_quantity_evidence
        if (
            not quantity.abstained
            and quantity.status == AuthorityStatus.FIRM.value
        )
    ]
    assert firm
    assert all(
        quantity.authority == MeasurementAuthorityType.PDF_SCALED.value
        for quantity in firm
    )
    assert all(quantity.value is not None and float(quantity.value) > 0.0 for quantity in firm)

    firm_ids = {quantity.quantity_id for quantity in firm}
    enriched = [
        floor
        for floor in claim.canonical_floors
        if floor.metric_area_quantity_id in firm_ids
    ]
    assert enriched
    assert all(floor.metric_area_m2 is not None for floor in enriched)
    assert all(
        floor.metric_area_authority == MeasurementAuthorityType.PDF_SCALED.value
        for floor in enriched
    )


def test_title_block_ratio_without_graphic_scale_bar_never_mints_metric_room_area(tmp_path) -> None:
    claim = collect_live_physical_net_wall_claim(
        _write(tmp_path, include_scale_bar=False),
        pages=(0,),
    )

    assert not any(
        not quantity.abstained
        and quantity.status == AuthorityStatus.FIRM.value
        and quantity.authority == MeasurementAuthorityType.PDF_SCALED.value
        for quantity in claim.room_area_quantity_evidence
    )
    assert all(
        floor.metric_area_quantity_id is None
        and floor.metric_area_m2 is None
        for floor in claim.canonical_floors
    )
