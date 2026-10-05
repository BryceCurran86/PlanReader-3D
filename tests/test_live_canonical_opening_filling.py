from __future__ import annotations

from dataclasses import replace

from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
from pb_live_canonical_opening_filling import (
    LiveCanonicalDoorObject,
    LiveCanonicalWindowObject,
    project_live_canonical_opening_fillings,
)
from pb_live_physical_opening_void_composition import compose_live_physical_opening_voids
from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
from pb_migration_contracts import EvidenceResolutionStatus
from pb_source_visibility_authority import SourceVisibilityProducer
from pb_takeoff_coverage_audit_adapter import build_runtime_coverage_publication
from tests.test_live_physical_opening_void_composition import _complete_void_pdf


def _opening(tag: str):
    source = SourceVisibilityProducer(
        producer_method="canonical-opening-filling-test",
        producer_version="1",
    )
    published = source.ingest_native_pdf_bytes(
        document_id=f"filling-{tag}",
        source_bytes=_complete_void_pdf(tag=tag),
        source_locator=f"memory://filling-{tag}.pdf",
    )
    wall_opening = compose_live_wall_opening_authority(
        source_visibility_producer=source,
        revision_id=published.revision.revision_id,
        page_ids=("1",),
    )
    composition = compose_live_physical_opening_voids(
        source_visibility_producer=source,
        wall_opening_composition=wall_opening,
    )
    assert len(composition.canonical_openings) == 1
    return composition.canonical_openings[0]


def test_resolved_window_mints_distinct_filling_identity_from_host_void() -> None:
    opening = _opening("W1")
    projection = project_live_canonical_opening_fillings((opening,))

    assert projection.status is EvidenceResolutionStatus.CORROBORATED
    assert projection.doors == ()
    assert len(projection.windows) == 1
    window = projection.windows[0]
    assert type(window) is LiveCanonicalWindowObject
    assert window.filling_kind == "window"
    assert window.physical_opening_id == opening.physical_opening_id
    assert window.physical_filling_id != opening.physical_opening_id
    assert window.canonical_filling_id == window.physical_filling_id
    assert window.evidence_ids == opening.evidence_ids
    assert window.geometry_complete is False
    assert window.commercial_quantity_authority is False


def test_resolved_door_mints_distinct_filling_identity() -> None:
    opening = _opening("D1")
    projection = project_live_canonical_opening_fillings((opening,))

    assert projection.status is EvidenceResolutionStatus.CORROBORATED
    assert projection.windows == ()
    assert len(projection.doors) == 1
    door = projection.doors[0]
    assert type(door) is LiveCanonicalDoorObject
    assert door.filling_kind == "door"
    assert door.physical_opening_id == opening.physical_opening_id
    assert door.physical_filling_id != opening.physical_opening_id


def test_filling_identity_is_stable_across_evidence_lineage_churn() -> None:
    opening = _opening("W1")
    first = project_live_canonical_opening_fillings((opening,)).windows[0]
    changed = replace(
        opening,
        physical_opening_id="different-evidence-record-id",
        canonical_opening_id="different-canonical-evidence-id",
        revision_id="revision-2",
        source_sha256="f" * 64,
        snapshot_id="snapshot-2",
        representative_observation_id="other-observation",
        evidence_ids=("different-evidence",),
    )
    second = project_live_canonical_opening_fillings((changed,)).windows[0]

    assert first.physical_filling_id == second.physical_filling_id
    assert first.canonical_filling_id == second.canonical_filling_id


def test_filling_identity_is_geometry_order_and_line_direction_invariant() -> None:
    opening = _opening("W1")
    first = project_live_canonical_opening_fillings((opening,)).windows[0]
    # For four-value line records, reverse both collection order and endpoint
    # direction without changing physical geometry.
    reversed_geometries = tuple(
        (
            geometry[2],
            geometry[3],
            geometry[0],
            geometry[1],
        )
        if len(geometry) == 4
        else geometry
        for geometry in reversed(opening.source_geometries)
    )
    second_opening = replace(opening, source_geometries=reversed_geometries)
    second = project_live_canonical_opening_fillings((second_opening,)).windows[0]

    assert first.physical_filling_id == second.physical_filling_id


def test_missing_host_wall_does_not_mint_filling_identity() -> None:
    opening = replace(_opening("W1"), host_wall_id=None)
    projection = project_live_canonical_opening_fillings((opening,))

    assert projection.status is EvidenceResolutionStatus.ABSTAINED
    assert projection.windows == ()
    assert projection.unresolved_opening_ids == (opening.physical_opening_id,)


def test_nonfinite_source_geometry_does_not_mint_filling_identity() -> None:
    opening = replace(
        _opening("W1"),
        source_geometries=((0.0, 0.0, float("nan"), 1.0),),
    )
    projection = project_live_canonical_opening_fillings((opening,))

    assert projection.status is EvidenceResolutionStatus.ABSTAINED
    assert projection.windows == ()


def test_unresolved_kind_does_not_mint_filling_identity() -> None:
    opening = replace(_opening("W1"), opening_kind=None)
    projection = project_live_canonical_opening_fillings((opening,))

    assert projection.status is EvidenceResolutionStatus.ABSTAINED
    assert projection.doors == ()
    assert projection.windows == ()
    assert projection.unresolved_opening_ids == (opening.physical_opening_id,)


def test_door_window_coverage_is_partial_not_duplicate_opening_path() -> None:
    opening = _opening("W1")
    projection = project_live_canonical_opening_fillings((opening,))
    window = projection.windows[0]

    summaries, gaps = collect_live_canonical_coverage(
        objects=(opening, window),
        registry_run_scope="opening-plus-filling",
    )
    assert "door_window" not in gaps

    report = build_runtime_coverage_publication(summaries, family_gaps=gaps)
    assert report["family_reports"]["opening"]["classification"] == "PARTIAL"
    family = report["family_reports"]["door_window"]
    assert family["classification"] == "PARTIAL"
    assert family["stage_counts"] == {
        "DETECTED": 1,
        "AUTHENTICATED": 1,
        "CANONICALIZED": 1,
        "QUANTIFIED": 0,
        "PUBLISHED": 0,
    }
