"""Exact original floor-area measurement method survives real customer authority.

Generated native-PDF positive and adversarial original-token negatives. No
owner-private source or frozen benchmark is read; no new FIRM is minted.
"""
from dataclasses import replace
from types import SimpleNamespace

import fitz
import pytest

from pb_hosted_opening_instance_adapter import authoritative_floor_plan_viewports
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
from tests.test_live_room_area_source_closed_export import (
    _cross_view_room_area_pdf,
    _framed_cross_view_room_area_pdf,
)


class ImportedAuthority(str):
    """An imported string-like token is not the native original source enum."""


@pytest.fixture
def original_claim(tmp_path):
    path = tmp_path / "source-method-original-native.pdf"
    path.write_bytes(_cross_view_room_area_pdf())
    return collect_live_physical_net_wall_claim(
        path, pages=(0,), room_area_support_pages=(1,),
    )


@pytest.fixture
def framed_original_claim(tmp_path):
    """A real generated-PDF floor-plan viewport, never a fabricated scale."""
    path = tmp_path / "framed-source-method-native.pdf"
    path.write_bytes(_framed_cross_view_room_area_pdf())
    with fitz.open(path) as document:
        native_viewports = tuple(
            view for view in authoritative_floor_plan_viewports(
                document[0], page_number=1,
            )
            if view.bounding_box is not None
        )
    assert len(native_viewports) == 1
    native_viewport_id = str(native_viewports[0].view_id)
    assert native_viewport_id

    claim = collect_live_physical_net_wall_claim(
        path, pages=(0,), room_area_support_pages=(1,),
    )
    source = _original_room_quantity(claim)
    floor = _source_floor(claim, source)
    rooms = tuple(
        room for room in claim.canonical_rooms
        if room.canonical_room_id == floor.room_entity_id
    )
    assert len(rooms) == 1
    room = rooms[0]
    # The original documented-area producer independently recognizes the
    # native floor-plan viewport. Canonical room/floor objects can predate
    # this fallback binding; attach ONLY that independently observed ID for
    # this synthetic scaled-contract test, never a guessed viewport or scale.
    assert source.metadata["viewport_id"] == native_viewport_id
    assert room.viewport_id in (None, native_viewport_id)
    assert floor.viewport_id in (None, native_viewport_id)
    assert room.source_sha256 == floor.source_sha256
    assert room.revision_id == floor.revision_id
    assert room.page_id == floor.page_id
    return replace(
        claim,
        canonical_rooms=tuple(
            replace(item, viewport_id=native_viewport_id)
            if item.canonical_room_id == room.canonical_room_id else item
            for item in claim.canonical_rooms
        ),
        canonical_floors=tuple(
            replace(item, viewport_id=native_viewport_id)
            if item.canonical_floor_id == floor.canonical_floor_id else item
            for item in claim.canonical_floors
        ),
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
            "scale_fingerprint": "scale-fingerprint:1",
        },
    )
    authority = _measurement_authority(scaled)
    assert authority is not None
    assert authority.method == "scaled_geometry"
    assert authority.resolved_scale_id == "source-scale:1"
    assert authority.metadata["scale_fingerprint"] == "scale-fingerprint:1"
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


@pytest.mark.parametrize("fingerprint", (
    " scale-fingerprint:1",
    "scale-fingerprint:1 ",
    "",
    ImportedAuthority("scale-fingerprint:1"),
    True,
    1,
    ("scale-fingerprint:1",),
))
def test_scaled_original_fingerprint_alias_cannot_be_repaired_at_customer(original_claim, fingerprint):
    source = _original_room_quantity(original_claim)
    metadata = {
        **dict(source.metadata),
        "resolved_scale_id": "source-scale:1",
        "scale_status": "resolved",
        "scale_conflicts": (),
        "scale_fingerprint": fingerprint,
    }
    # Final gate sees original typed source metadata before any serializer
    # could repair a str subclass, boolean or iterable into a plausible ID.
    original = dict(metadata)
    replay = SimpleNamespace(
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        metadata=metadata,
        quantity_id=source.quantity_id,
    )
    assert _measurement_authority(replay) is None
    assert metadata == original


def test_scaled_original_fingerprint_remains_optional_when_absent(original_claim):
    source = _original_room_quantity(original_claim)
    metadata = {
        **dict(source.metadata),
        "resolved_scale_id": "source-scale:1",
        "scale_status": "resolved",
        "scale_conflicts": (),
    }
    metadata.pop("scale_fingerprint", None)
    scaled = replace(source, authority=MeasurementAuthorityType.PDF_SCALED.value, metadata=metadata)
    authority = _measurement_authority(scaled)
    assert authority is not None
    assert authority.metadata["scale_fingerprint"] == ""


def _synthetic_scaled_source_identity_claim(original_claim):
    """Construct an ID-consistent scaled contract for a native PDF ring.

    This exercises the ID/lineage guard, NOT a claim of a trusted source scale
    or an owner-original metric/FIRM quantity.
    """
    import hashlib
    from pb_migration_contracts import canonical_contract_json, stable_contract_id
    from pb_room_area_quantity import _canonical_ring

    source = _original_room_quantity(original_claim)
    floor = _source_floor(original_claim, source)
    rooms = tuple(
        room for room in original_claim.canonical_rooms
        if room.canonical_room_id == floor.room_entity_id
    )
    assert len(rooms) == 1
    room = rooms[0]
    ring = _canonical_ring(room.polygon_pdf_pts)
    assert ring
    fingerprint = "synthetic-scale-binding-receipt:1"
    ring_signature = hashlib.sha256(
        canonical_contract_json(ring).encode("utf-8")
    ).hexdigest()
    # The input is a documented cross-view area: its measurement-support
    # metadata is NOT a PDF-scaled room producer's source receipt. Rebuild the
    # synthetic scaled receipt from the independently owned canonical room,
    # without changing the production source-lineage guard to fit this test.
    assert room.source_sha256 == floor.source_sha256
    assert room.revision_id == floor.revision_id
    assert room.viewport_id == floor.viewport_id
    assert room.page_id == floor.page_id
    assert type(room.viewport_id) is str and room.viewport_id
    metadata = {
        **dict(source.metadata),
        "source_sha256": room.source_sha256,
        "revision_id": room.revision_id,
        "viewport_id": room.viewport_id,
        "page_no": int(room.page_id),
        "scale_fingerprint": fingerprint,
        "ring_signature": ring_signature,
        "resolved_scale_id": "synthetic-scale:1",
        "scale_status": "resolved",
        "scale_conflicts": (),
        "figured_dimension_ids": (),
    }
    source_id = stable_contract_id("qty", {
        "family": "room_area",
        "room_id": source.input_entity_ids[0],
        "value_m2": source.value,
        "scale_fingerprint": fingerprint,
        "ring": ring,
        "source_sha256": metadata["source_sha256"],
        "revision_id": metadata["revision_id"],
        "viewport_id": metadata["viewport_id"],
    })
    scaled = replace(
        source,
        quantity_id=source_id,
        authority=MeasurementAuthorityType.PDF_SCALED.value,
        formula="shoelace_polygon_area / trusted_px_per_m^2",
        metadata=metadata,
    )
    scaled_floor = replace(
        floor, metric_area_quantity_id=source_id,
        metric_area_authority=MeasurementAuthorityType.PDF_SCALED.value,
    )
    claim = replace(
        original_claim,
        room_area_quantity_evidence=tuple(
            scaled if item.quantity_id == source.quantity_id else item
            for item in original_claim.room_area_quantity_evidence
        ),
        canonical_floors=tuple(
            scaled_floor if item.canonical_floor_id == floor.canonical_floor_id else item
            for item in original_claim.canonical_floors
        ),
    )
    return claim


def test_id_consistent_synthetic_scaled_source_reaches_sealed_customer(framed_original_claim):
    claim = _synthetic_scaled_source_identity_claim(framed_original_claim)
    published = publish_live_floor_area_quantities(claim)
    assert len(published) == 1
    rows = _customer(claim)
    assert len(rows) == 1
    assert rows[0]["measurement_method"] == "scaled_geometry"
    assert rows == _customer(claim)
    sealed = seal_live_floor_area_run(
        claim, workspace_id=7, project_id="original-floor-method",
    )
    assert verify_sealed_customer_output(
        sealed, rows,
    ).verified_quantity_ids == (published[0].quantity_id,)


@pytest.mark.parametrize("field,new_value", (
    ("scale_fingerprint", "synthetic-scale-binding-receipt:2"),
    ("ring_signature", "f" * 64),
))
def test_different_clean_original_scaled_receipt_cannot_borrow_original_id(
    framed_original_claim, field, new_value,
):
    from pb_source_closed_run_export import SourceClosedRunConflictError

    claim = _synthetic_scaled_source_identity_claim(framed_original_claim)
    original = _original_room_quantity(claim)
    forged = replace(
        original, metadata={**dict(original.metadata), field: new_value},
    )
    replay = replace(
        claim,
        room_area_quantity_evidence=tuple(
            forged if item.quantity_id == original.quantity_id else item
            for item in claim.room_area_quantity_evidence
        ),
    )
    # The actual floor publisher and trace accept the unchanged numeric
    # source ID; only the final independent producer-ID proof rejects it.
    assert len(publish_live_floor_area_quantities(replay)) == 1
    assert len(build_live_floor_area_source_traces(
        replay, workspace_id=7, project_id="original-floor-method",
    )) == 1
    before = (replay.room_area_quantity_evidence, replay.canonical_floors)
    with pytest.raises(SourceClosedRunConflictError, match="scaled floor original"):
        _customer(replay)
    assert (replay.room_area_quantity_evidence, replay.canonical_floors) == before
    assert _customer(claim) == _customer(claim)


def test_scaled_customer_requires_reconstructible_original_room_source(framed_original_claim):
    from pb_source_closed_run_export import SourceClosedRunConflictError

    claim = _synthetic_scaled_source_identity_claim(framed_original_claim)
    original = _original_room_quantity(claim)
    missing = replace(
        original,
        metadata={key: value for key, value in original.metadata.items()
                  if key != "ring_signature"},
    )
    replay = replace(
        claim,
        room_area_quantity_evidence=tuple(
            missing if item.quantity_id == original.quantity_id else item
            for item in claim.room_area_quantity_evidence
        ),
    )
    with pytest.raises(SourceClosedRunConflictError, match="room-ring receipt"):
        _customer(replay)
