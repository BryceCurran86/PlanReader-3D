"""Exact original floor-area measurement method survives real customer authority.

Generated native-PDF positive and adversarial original-token negatives. No
owner-private source or frozen benchmark is read; no new FIRM is minted.
"""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from pb_customer_output_verification import verify_sealed_customer_output
from pb_geometry_takeoff_model import MeasurementAuthorityType
from pb_live_floor_area_customer_projection import (
    _measurement_authority,
    project_live_floor_area_customer_rows,
)
from pb_live_floor_area_quantity_publication import publish_live_floor_area_quantities
from pb_live_floor_area_source_closed_export import (
    build_live_floor_area_source_traces,
    seal_live_floor_area_run,
)
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_quantity_takeoff_adapter import MissingCommercialAuthorityError
from tests.test_live_room_area_source_closed_export import _cross_view_room_area_pdf


class ImportedAuthority(str):
    """An imported string-like token is not the native original source enum."""


@pytest.fixture
def original_claim(tmp_path):
    path = tmp_path / "source-method-original-native.pdf"
    path.write_bytes(_cross_view_room_area_pdf())
    return collect_live_physical_net_wall_claim(
        path, pages=(0,), room_area_support_pages=(1,),
    )


def _original_room_quantity(claim):
    firm = tuple(
        quantity for quantity in claim.room_area_quantity_evidence
        if not quantity.abstained and quantity.value is not None
    )
    assert len(firm) == 1
    return firm[0]


def _source_floor(claim, source):
    return next(
        floor for floor in claim.canonical_floors
        if floor.metric_area_quantity_id == source.quantity_id
    )


def _replay_method(claim, method):
    source = _original_room_quantity(claim)
    floor = _source_floor(claim, source)
    altered = replace(source, authority=method)
    altered_floor = replace(floor, metric_area_authority=method)
    return replace(
        claim,
        room_area_quantity_evidence=tuple(
            altered if item.quantity_id == source.quantity_id else item
            for item in claim.room_area_quantity_evidence
        ),
        canonical_floors=tuple(
            altered_floor if item.canonical_floor_id == floor.canonical_floor_id else item
            for item in claim.canonical_floors
        ),
    )


def _customer(claim):
    return project_live_floor_area_customer_rows(
        claim, workspace_id=7, project_id="original-floor-method",
    )


def test_native_original_documented_floor_method_seals_and_replays_unchanged(original_claim):
    source = _original_room_quantity(original_claim)
    assert source.authority == MeasurementAuthorityType.DOCUMENTED_DIMENSION.value
    published = publish_live_floor_area_quantities(original_claim)
    assert len(published) == 1
    traces = build_live_floor_area_source_traces(
        original_claim, workspace_id=7, project_id="original-floor-method",
    )
    assert published[0].quantity_id in traces
    rows = _customer(original_claim)
    assert len(rows) == 1
    assert rows == _customer(original_claim)
    assert rows[0]["measurement_method"] == "figured_dimension"
    assert rows[0]["quantity"] == pytest.approx(published[0].value)
    sealed = seal_live_floor_area_run(
        original_claim, workspace_id=7, project_id="original-floor-method",
    )
    verified = verify_sealed_customer_output(sealed, rows)
    assert verified.verified_quantity_ids == (published[0].quantity_id,)


@pytest.mark.parametrize("method", (
    " documented_dimension",
    "documented_dimension ",
    ImportedAuthority("documented_dimension"),
))
def test_original_source_method_alias_cannot_reach_customer_as_figured(original_claim, method):
    forged = _replay_method(original_claim, method)
    original_source = _original_room_quantity(original_claim)
    # Before the final customer boundary, the real floor publisher and
    # source trace still accept this alias. Do not mislabel this a metric fix.
    published = publish_live_floor_area_quantities(forged)
    assert len(published) == 1
    assert published[0].authority == method
    traces = build_live_floor_area_source_traces(
        forged, workspace_id=7, project_id="original-floor-method",
    )
    assert published[0].quantity_id in traces
    before = (forged.room_area_quantity_evidence, forged.canonical_floors)
    with pytest.raises(
        MissingCommercialAuthorityError,
        match="commercial measurement authority is required",
    ):
        _customer(forged)
    assert (forged.room_area_quantity_evidence, forged.canonical_floors) == before
    assert _original_room_quantity(original_claim) == original_source


@pytest.mark.parametrize("method", (
    "documented/figured",
    "FIGURED_DIMENSION",
    "unverified_figured",
    "pdf-scaled",
    "scaled_geometry",
    "unscaled_geometry",
    " pdf_scaled",
    "pdf_scaled ",
    ImportedAuthority("pdf_scaled"),
    None,
    True,
    1,
))
def test_final_floor_customer_authority_never_guesses_from_aliases(original_claim, method):
    source = _original_room_quantity(original_claim)
    metadata = dict(source.metadata)
    metadata.update({
        "resolved_scale_id": "source-scale:1",
        "scale_status": "resolved",
        "scale_conflicts": (),
    })
    if method is None:
        # The real QuantityEvidence constructor already rejects an absent
        # authority. Exercise the final fail-closed guard separately without
        # weakening that upstream contract or inventing a FIRM quantity.
        with pytest.raises(ValueError, match="authority must be a non-empty string"):
            replace(source, authority=method, metadata=metadata)
        replay = SimpleNamespace(
            authority=method, metadata=metadata, quantity_id=source.quantity_id,
        )
    else:
        replay = replace(source, authority=method, metadata=metadata)
    # Direct final-gate test: invalid methods cannot borrow otherwise
    # well-formed dimension/scale metadata to mint a commercial authority.
    assert _measurement_authority(replay) is None


def test_exact_pdf_scaled_method_retains_existing_explicit_scale_checks(original_claim):
    source = _original_room_quantity(original_claim)
    scaled = replace(
        source,
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        metadata={
            **dict(source.metadata),
            "resolved_scale_id": "source-scale:1",
            "scale_status": "resolved",
            "scale_conflicts": (),
        },
    )
    authority = _measurement_authority(scaled)
    assert authority is not None
    assert authority.method == "scaled_geometry"
    assert authority.resolved_scale_id == "source-scale:1"
    conflicted = replace(
        scaled, metadata={**scaled.metadata, "scale_conflicts": ("rival-scale",)},
    )
    assert _measurement_authority(conflicted) is None


def test_abstained_original_area_cannot_become_customer_row(original_claim):
    source = _original_room_quantity(original_claim)
    abstained = replace(
        source, value=None, status="blocked", abstained=True,
        blocking_reasons=("original_metric_unavailable",),
    )
    claim = replace(
        original_claim,
        room_area_quantity_evidence=tuple(
            abstained if item.quantity_id == source.quantity_id else item
            for item in original_claim.room_area_quantity_evidence
        ),
    )
    assert _customer(claim) == ()
