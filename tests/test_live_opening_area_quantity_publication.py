from __future__ import annotations

from dataclasses import replace
from types import MappingProxyType

import pytest

from pb_live_opening_area_quantity_publication import (
    LIVE_OPENING_FIGURED_AREA_QUANTITY_AUTHORITY,
    LIVE_OPENING_GEOMETRY_AREA_QUANTITY_AUTHORITY,
    _opening_quantity,
    publish_live_opening_area_quantities,
)
from pb_live_physical_opening_void_composition import (
    LiveCanonicalOpeningObject,
    LivePhysicalOpeningVoidComposition,
)
from pb_migration_contracts import EvidenceResolutionStatus
from pb_quantity_takeoff_adapter import (
    CommercialMeasurementAuthority,
    CommercialTakeoffSourceTrace,
    quantity_evidence_to_takeoff_output_row,
)
from pb_source_closed_run_export import seal_source_closed_quantity


SHA = "a" * 64


def _opening(
    *,
    canonical_id: str = "opening-1",
    kind: str | None = "window",
    area_m2: float | None = 2.172,
    area_basis: str | None = "figured_opening_label",
    figured_area_record_id: str | None = "figured-1",
    opening_void_record_id: str | None = None,
) -> LiveCanonicalOpeningObject:
    evidence_ids = tuple(
        value
        for value in (
            canonical_id,
            "source-observation-1",
            figured_area_record_id,
            opening_void_record_id,
        )
        if value
    )
    return LiveCanonicalOpeningObject(
        canonical_opening_id=canonical_id,
        physical_opening_id=canonical_id,
        document_id="doc-1",
        revision_id="rev-1",
        source_sha256=SHA,
        snapshot_id="snap-1",
        page_id="3",
        viewport_id="vp-floor-1",
        semantic_class="physical_opening",
        structural_pattern="gap_corroborated_window_jamb_pair",
        representative_observation_id="source-observation-1",
        source_observation_ids=("source-observation-1",),
        source_lineage_root_ids=("source-root-1",),
        source_geometries=((0.0, 0.0, 1.0, 0.0),),
        host_wall_id="wall-1",
        host_binding_record_id="host-binding-1",
        host_frame_record_id="host-frame-1",
        wall_local_frame_id=None,
        profile_kind=None,
        coordinate_unit=None,
        u0=None,
        u1=None,
        z0=None,
        z1=None,
        width_m=None,
        height_m=None,
        area_m2=area_m2,
        area_basis=area_basis,
        figured_area_record_id=figured_area_record_id,
        opening_void_record_id=opening_void_record_id,
        opening_universe_record_id=None,
        width_record_id=None,
        height_record_id=None,
        vertical_placement_record_id=None,
        scale_record_id=None,
        schedule_binding_record_id=None,
        opening_kind=kind,
        type_mark=None,
        schedule_page_id=None,
        schedule_declared_width_mm=None,
        schedule_declared_height_mm=None,
        schedule_declared_count=None,
        schedule_count_explicit=False,
        schedule_row_observation_ids=(),
        tag_observation_id=None,
        evidence_ids=evidence_ids,
        geometry_complete=False,
    )


def _composition(*openings: LiveCanonicalOpeningObject):
    return LivePhysicalOpeningVoidComposition(
        revision_id="rev-1",
        status=EvidenceResolutionStatus.ABSTAINED,
        reason_codes=("partial",),
        traces=(),
        physical_opening_void_authorities=MappingProxyType({}),
        void_selectors=MappingProxyType({}),
        canonical_openings=tuple(openings),
    )


def test_figured_opening_area_becomes_identity_bound_quantity_evidence() -> None:
    opening = _opening()
    quantity = _opening_quantity(opening)
    assert quantity is not None
    assert quantity.family == "opening_area"
    assert quantity.semantic_key == "window_area:opening-1"
    assert quantity.value == pytest.approx(2.172)
    assert quantity.unit == "m2"
    assert quantity.input_entity_ids == ("opening-1",)
    assert quantity.authority == LIVE_OPENING_FIGURED_AREA_QUANTITY_AUTHORITY
    assert quantity.status == "corroborated"
    assert quantity.abstained is False
    assert "figured-1" in quantity.evidence_ids
    assert quantity.metadata["area_basis"] == "figured_opening_label"
    assert quantity.metadata["measurement_record_id"] == "figured-1"


def test_untyped_opening_never_publishes_trade_area() -> None:
    assert _opening_quantity(_opening(kind=None)) is None


def test_figured_area_requires_its_measurement_record_in_canonical_provenance() -> None:
    opening = replace(
        _opening(),
        evidence_ids=("opening-1", "source-observation-1"),
    )
    assert _opening_quantity(opening) is None


def test_resolved_geometry_area_requires_physical_void_evidence() -> None:
    opening = _opening(
        area_m2=1.827,
        area_basis="resolved_opening_geometry",
        figured_area_record_id=None,
        opening_void_record_id="void-1",
    )
    quantity = _opening_quantity(opening)
    assert quantity is not None
    assert quantity.value == pytest.approx(1.827)
    assert quantity.authority == LIVE_OPENING_GEOMETRY_AREA_QUANTITY_AUTHORITY
    assert quantity.metadata["measurement_record_id"] == "void-1"

    assert _opening_quantity(
        replace(opening, opening_void_record_id=None)
    ) is None


def test_publication_is_one_quantity_per_physical_opening_identity() -> None:
    quantities = publish_live_opening_area_quantities(
        _composition(
            _opening(canonical_id="opening-a"),
            _opening(canonical_id="opening-b", kind="door", area_m2=3.15),
        )
    )
    assert len(quantities) == 2
    assert {
        quantity.input_entity_ids[0] for quantity in quantities
    } == {"opening-a", "opening-b"}


def test_duplicate_physical_opening_identity_fails_closed() -> None:
    duplicate = _opening()
    with pytest.raises(ValueError, match="duplicate canonical opening identity"):
        publish_live_opening_area_quantities(
            _composition(duplicate, duplicate)
        )


def test_figured_opening_quantity_is_sealable_and_commercially_projectable() -> None:
    opening = _opening()
    quantity = _opening_quantity(opening)
    assert quantity is not None

    trace = CommercialTakeoffSourceTrace(
        workspace_id=1,
        project_id="project-fixture",
        document_id=opening.document_id,
        source_sha256=opening.source_sha256,
        source_page=opening.page_id,
        viewport_id=opening.viewport_id or "viewport-fixture",
        revision_id=opening.revision_id,
        current_revision_id=opening.revision_id,
        evidence_ids=tuple(quantity.evidence_ids),
        canonical_entity_ids=(opening.canonical_opening_id,),
    )
    authority = CommercialMeasurementAuthority(
        method="figured_dimension",
        figured_dimension_ids=(opening.figured_area_record_id,),
    )

    sealed = seal_source_closed_quantity(quantity, trace=trace)
    assert sealed.lineage_ok is True
    assert sealed.object_identity_refs == (opening.canonical_opening_id,)
    assert sealed.value == pytest.approx(2.172)
    assert sealed.unit == "m2"

    row = quantity_evidence_to_takeoff_output_row(
        quantity,
        trace=trace,
        authority=authority,
    )
    assert row is not None
    assert row["quantity"] == pytest.approx(2.172)
    assert row["quantity_id"] == quantity.quantity_id
    assert row["canonical_entity_ids"] == [opening.canonical_opening_id]
    assert row["measurement_method"] == "figured_dimension"
    assert row["figured_dimension_ids"] == [opening.figured_area_record_id]
    # Existing commercial governance remains intact: automated quantities
    # enter customer takeoff as review rows rather than bypassing approval.
    assert row["quantity_status"] == "To review"
