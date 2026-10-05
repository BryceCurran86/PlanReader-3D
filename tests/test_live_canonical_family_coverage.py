from __future__ import annotations

import copy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import patch

import pytest

import pb_auto_geometry_v1219 as auto
from pb_live_canonical_coverage_registry import collect_live_canonical_coverage
from pb_live_canonical_floor_surface import compose_live_canonical_floor_surfaces
from pb_live_canonical_roof_projection import project_source_gable_roof
from pb_live_canonical_room_composition import compose_live_canonical_rooms
from pb_live_canonical_slab_projection import project_resolved_slab_entity
from pb_live_canonical_structural_member_projection import project_structural_member_resolution
from pb_live_canonical_wall_finish_surface import project_wall_finish_bindings
from pb_live_physical_net_wall_integration import collect_live_physical_net_wall_claim
from pb_migration_contracts import EvidenceResolutionStatus
from pb_structural_member_quantity import build_structural_member_count_quantity
from pb_takeoff_output_authority import TakeoffOutputRow
from pb_takeoff_coverage_audit_adapter import (
    RUNTIME_COVERAGE_FAMILIES,
    build_runtime_coverage_publication,
)
from tests.test_ag09_customer_coverage_runtime import _summary
from tests.test_live_canonical_roof_projection import _measurement
from tests.test_live_canonical_room_composition import _source
from tests.test_live_canonical_slab_projection import _boundary, _resolved_slab
from tests.test_live_canonical_structural_member_projection import _resolved
from tests.test_live_canonical_wall_finish_surface import _binding, _wall
from tests.test_live_physical_opening_void_composition import _complete_void_pdf


def _rooms():
    source, wall_opening = _source(page_partitions=(True,))
    return compose_live_canonical_rooms(
        source_visibility_producer=source, wall_opening_composition=wall_opening,
    )


def test_all_nine_unavailable_families_have_null_counts_not_zero():
    report = build_runtime_coverage_publication(())
    assert tuple(report["family_reports"]) == RUNTIME_COVERAGE_FAMILIES
    for family in report["family_reports"].values():
        assert family["classification"] == "UNAVAILABLE"
        assert set(family["stage_counts"].values()) == {None}
        assert family["expected_family_completeness"] == "UNKNOWN"


@pytest.mark.parametrize("category,family", [
    ("wall", "wall"), ("opening", "opening"), ("door", "door_window"),
    ("window", "door_window"), ("room", "room"), ("floor", "floor_slab"),
    ("slab", "floor_slab"), ("ceiling", "ceiling"), ("roof", "roof"),
    ("finish_surface", "finish_surface"), ("column", "structural_member"),
    ("beam", "structural_member"),
])
def test_explicit_registry_category_connects_only_its_family(category, family):
    summary = _summary()
    # Synthetic producer-owned manifest/snapshot for each contract category.
    summary = replace(
        summary,
        manifest=replace(summary.manifest, expected_object_universe_keys=(("physical_wall", category),)),
        object_universe_snapshots=(replace(summary.object_universe_snapshots[0], category=category),),
        object_records=(replace(summary.object_records[0], object_type=category),),
    )
    report = build_runtime_coverage_publication((summary,), published_takeoff_rows=[
        {"source_reference": "physical:qty-live-1"},
    ])
    assert report["family_reports"][family]["classification"] == "CONNECTED"
    assert report["family_reports"][family]["stage_counts"]["PUBLISHED"] == 1
    assert all(value["status"] == "unavailable" for key, value in report["family_reports"].items() if key != family)


def test_missing_customer_row_exposes_partial_publication_dropout():
    report = build_runtime_coverage_publication((_summary(),))
    family = report["family_reports"]["wall"]
    assert family["classification"] == "PARTIAL"
    assert family["stage_counts"]["QUANTIFIED"] == 1
    assert family["stage_counts"]["PUBLISHED"] == 0
    assert "customer_takeoff_row_not_found" in family["reason_codes"]


def test_conflicting_registry_paths_survive_runtime_collection_and_are_not_counted_twice():
    original = _summary()
    competing = replace(original, object_records=(replace(original.object_records[0], geometry_ids=("other-geometry",)),))
    app = SimpleNamespace(coverage_registry_summaries_live=[original, competing, original])
    summaries = auto._runtime_coverage_registry_summaries(app)
    assert len(summaries) == 2
    report = build_runtime_coverage_publication(summaries)
    assert len(report["registry_reports"]) == 2
    assert report["family_reports"]["wall"]["classification"] == "WRONG / DUPLICATE PATH"
    assert set(report["family_reports"]["wall"]["stage_counts"].values()) == {None}


def test_aliases_of_identical_snapshot_are_one_runtime_path():
    summary = _summary()
    report = build_runtime_coverage_publication((summary, summary))
    assert len(report["registry_reports"]) == 1
    assert report["stage_counts"]["AUTHENTICATED"] == 1


@pytest.mark.parametrize("defect", ["abstained", "stale_revision", "unadmitted_input", "unverified_status"])
def test_invalid_original_quantity_never_reaches_quantified_or_published(defect):
    resolution = _resolved(with_geometry=True)
    members = project_structural_member_resolution(resolution).objects
    quantity = build_structural_member_count_quantity(resolution)
    if defect == "abstained":
        quantity = replace(quantity, value=None, abstained=True, status="abstained", blocking_reasons=("missing_source",))
    elif defect == "stale_revision":
        quantity = replace(quantity, metadata={**quantity.metadata, "revision_id": "wrong-revision"})
    elif defect == "unadmitted_input":
        quantity = replace(quantity, input_entity_ids=(*quantity.input_entity_ids, "missing-physical-member"))
    else:
        quantity = replace(quantity, status="provisional")
    summaries, gaps = collect_live_canonical_coverage(
        objects=members, quantities=(quantity,), output_rows=(TakeoffOutputRow(
            quantity_id=quantity.quantity_id, description="stale row", value=2.0, unit=quantity.unit,
            is_publishable=False,
        ),), registry_run_scope="hostile-original-quantity",
    )
    report = build_runtime_coverage_publication(summaries, family_gaps=gaps, published_takeoff_rows=[
        {"quantity_id": quantity.quantity_id, "quantity": 2.0, "unit": quantity.unit},
    ])
    family = report["family_reports"]["structural_member"]
    assert family["classification"] == "PARTIAL"
    assert family["stage_counts"]["CANONICALIZED"] == len(members)
    assert family["stage_counts"]["QUANTIFIED"] == family["stage_counts"]["PUBLISHED"] == 0
    assert all(record.quantity_ids == (quantity.quantity_id,) for summary in summaries for record in summary.object_records)


@pytest.mark.parametrize("published_value,published_unit,published", [
    (2.0, "NO", True), (2.01, "NO", False), (2.0, "m²", False), (None, "NO", False),
])
def test_aggregate_quantity_publication_requires_original_value_and_unit(published_value, published_unit, published):
    resolution = _resolved(with_geometry=True)
    members = project_structural_member_resolution(resolution).objects
    quantity = build_structural_member_count_quantity(resolution)
    assert quantity.value == 2.0 and quantity.unit == "NO"
    summaries, _ = collect_live_canonical_coverage(
        objects=members, quantities=(quantity,), output_rows=(TakeoffOutputRow(
            quantity_id=quantity.quantity_id, description="member count", value=quantity.value,
            unit=quantity.unit, is_publishable=False,
        ),), registry_run_scope="original-aggregate",
    )
    # Each member has an aggregate dependency; a missing per-member allocation
    # does not erase the verified total or invent an allocation.
    assert all(record.quantity_contribution[quantity.quantity_id] is None
               for summary in summaries for record in summary.object_records)
    report = build_runtime_coverage_publication(summaries, published_takeoff_rows=[
        {"quantity_id": quantity.quantity_id, "quantity": published_value, "unit": published_unit},
    ])
    counts = report["family_reports"]["structural_member"]["stage_counts"]
    assert counts["QUANTIFIED"] == 2
    assert counts["PUBLISHED"] == (2 if published else 0)


def test_abstained_dependency_cannot_publish_on_behalf_of_valid_sibling_dependency():
    resolution = _resolved(with_geometry=True)
    members = project_structural_member_resolution(resolution).objects
    valid = build_structural_member_count_quantity(resolution)
    invalid = replace(valid, quantity_id="quantity:abstained:sibling", value=None,
                      abstained=True, status="abstained", blocking_reasons=("missing_source",))
    summaries, _ = collect_live_canonical_coverage(
        objects=members, quantities=(valid, invalid), output_rows=(TakeoffOutputRow(
            quantity_id=invalid.quantity_id, description="abstained sibling", value=2.0,
            unit=invalid.unit, is_publishable=False,
        ),), registry_run_scope="mixed-quantity-dependencies",
    )
    report = build_runtime_coverage_publication(summaries, published_takeoff_rows=[
        {"quantity_id": invalid.quantity_id, "quantity": 2.0, "unit": invalid.unit},
    ])
    counts = report["family_reports"]["structural_member"]["stage_counts"]
    assert counts["QUANTIFIED"] == 2
    assert counts["PUBLISHED"] == 0


@pytest.mark.parametrize("status,verified", [
    ("firm", True), ("corroborated", True), ("provisional", False),
    ("review_required", False), ("user_approved", False), ("blocked", False),
    ("unknown", False), ("FIRM", False),
])
def test_quantity_stage_respects_the_existing_exact_status_vocabularies(status, verified):
    resolution = _resolved(with_geometry=True)
    members = project_structural_member_resolution(resolution).objects
    quantity = replace(build_structural_member_count_quantity(resolution), status=status)
    summaries, _ = collect_live_canonical_coverage(
        objects=members, quantities=(quantity,), output_rows=(), registry_run_scope="status-contract",
    )
    report = build_runtime_coverage_publication(summaries)
    counts = report["family_reports"]["structural_member"]["stage_counts"]
    assert counts["QUANTIFIED"] == (len(members) if verified else 0)
    assert counts["PUBLISHED"] == 0


def test_source_authenticated_rooms_are_partial_without_metric_quantity_and_inputs_stay_unchanged():
    rooms = _rooms().rooms
    before = copy.deepcopy([room.to_dict() for room in rooms])
    summaries, gaps = collect_live_canonical_coverage(objects=rooms, registry_run_scope="test")
    reverse, reverse_gaps = collect_live_canonical_coverage(objects=tuple(reversed(rooms)), registry_run_scope="test")
    assert [s.to_dict() for s in summaries] == [s.to_dict() for s in reverse]
    assert gaps == reverse_gaps == {}
    assert [room.to_dict() for room in rooms] == before
    report = build_runtime_coverage_publication(summaries)
    assert report["family_reports"]["room"]["classification"] == "PARTIAL"
    assert report["family_reports"]["room"]["stage_counts"] == {
        "DETECTED": 2, "AUTHENTICATED": 2, "CANONICALIZED": 2,
        "QUANTIFIED": 0, "PUBLISHED": 0,
    }
    assert all(not record.quantity_ids for summary in summaries for record in summary.object_records)


def test_floor_footprint_does_not_manufacture_physical_floor_identity():
    floors = compose_live_canonical_floor_surfaces(_rooms()).floors
    summaries, gaps = collect_live_canonical_coverage(objects=floors, registry_run_scope="test")
    assert summaries and all(not summary.object_records for summary in summaries)
    report = build_runtime_coverage_publication(summaries, family_gaps=gaps)
    family = report["family_reports"]["floor_slab"]
    assert family["classification"] == "UNAVAILABLE"
    assert set(family["stage_counts"].values()) == {None}
    assert "producer_physical_identity_unresolved" in family["reason_codes"]
    assert all(not floor.physical_floor_surface_identity_resolved for floor in floors)


def test_structural_registry_reuses_original_count_quantity_and_canonical_member_ids():
    resolution = _resolved(with_geometry=True)
    members = project_structural_member_resolution(resolution).objects
    quantity = build_structural_member_count_quantity(resolution)
    before = quantity.to_dict()
    summaries, gaps = collect_live_canonical_coverage(
        objects=members, quantities=(quantity,), registry_run_scope="test",
    )
    assert gaps == {}
    assert quantity.to_dict() == before
    records = summaries[0].object_records
    assert {record.object_id for record in records} == {member.physical_member_id for member in members}
    assert all(record.quantity_ids == (quantity.quantity_id,) for record in records)
    assert all(record.geometry_ids == (record.object_id,) for record in records)
    report = build_runtime_coverage_publication(summaries)
    assert report["family_reports"]["structural_member"]["stage_counts"]["QUANTIFIED"] == 2
    assert report["family_reports"]["structural_member"]["stage_counts"]["PUBLISHED"] == 0


def test_current_customer_row_closes_publication_after_pre_row_extractor_snapshot():
    resolution = _resolved(with_geometry=True)
    members = project_structural_member_resolution(resolution).objects
    quantity = build_structural_member_count_quantity(resolution)
    summaries, gaps = collect_live_canonical_coverage(
        objects=members,
        quantities=(quantity,),
        registry_run_scope="pre-row-extractor-snapshot",
    )

    assert all(
        not record.takeoff_row_ids
        for summary in summaries
        for record in summary.object_records
    )

    report = build_runtime_coverage_publication(
        summaries,
        family_gaps=gaps,
        published_takeoff_rows=[
            {
                "source_reference": (
                    f"PB Auto geometry · structural_quantity:{quantity.quantity_id}"
                ),
                "quantity": quantity.value,
                "unit": quantity.unit,
            }
        ],
    )
    family = report["family_reports"]["structural_member"]
    assert family["classification"] == "PARTIAL"
    assert family["stage_counts"]["QUANTIFIED"] == len(members)
    assert family["stage_counts"]["PUBLISHED"] == len(members)
    assert all(
        obj["highest_stage_reached"] == "PUBLISHED"
        for registry in report["registry_reports"]
        for obj in registry["object_reports"]
    )


@pytest.mark.parametrize(
    "published_quantity,published_unit",
    [
        (2.01, "NO"),
        (2.0, "m²"),
        (None, "NO"),
    ],
)
def test_current_customer_row_cannot_publish_when_value_or_unit_changes(
    published_quantity,
    published_unit,
):
    resolution = _resolved(with_geometry=True)
    members = project_structural_member_resolution(resolution).objects
    quantity = build_structural_member_count_quantity(resolution)
    summaries, gaps = collect_live_canonical_coverage(
        objects=members,
        quantities=(quantity,),
        registry_run_scope="customer-row-mismatch",
    )
    report = build_runtime_coverage_publication(
        summaries,
        family_gaps=gaps,
        published_takeoff_rows=[
            {
                "source_reference": (
                    f"PB Auto geometry · structural_quantity:{quantity.quantity_id}"
                ),
                "quantity": published_quantity,
                "unit": published_unit,
            }
        ],
    )
    counts = report["family_reports"]["structural_member"]["stage_counts"]
    assert counts["QUANTIFIED"] == len(members)
    assert counts["PUBLISHED"] == 0


def test_known_takeoff_row_lineage_conflict_still_blocks_runtime_reconciliation():
    summary = _summary()
    record = replace(
        summary.object_records[0],
        takeoff_row_ids=(),
        reason_codes=(
            *summary.object_records[0].reason_codes,
            "takeoff_row_geometry_lineage_conflict:qty-live-1",
        ),
    )
    hostile = replace(summary, object_records=(record,))
    report = build_runtime_coverage_publication(
        (hostile,),
        published_takeoff_rows=[
            {
                "source_reference": "physical:qty-live-1",
                "quantity": 12.5,
                "unit": "m²",
            }
        ],
    )
    family = report["family_reports"]["wall"]
    assert family["stage_counts"]["QUANTIFIED"] == 1
    assert family["stage_counts"]["PUBLISHED"] == 0


def test_finish_surface_remains_partial_without_proven_finish_extent_or_quantity():
    surfaces = project_wall_finish_bindings(canonical_walls=(_wall(),), bindings=(_binding(),)).surfaces
    summaries, gaps = collect_live_canonical_coverage(objects=surfaces, registry_run_scope="test")
    report = build_runtime_coverage_publication(summaries, family_gaps=gaps)
    assert report["family_reports"]["finish_surface"]["classification"] == "PARTIAL"
    assert all(not record.quantity_ids for summary in summaries for record in summary.object_records)
    assert all(surface.commercial_quantity_authority is False for surface in surfaces)


def test_lineage_incomplete_roof_and_slab_are_unavailable_without_invented_revision():
    roof = project_source_gable_roof(_measurement()).object
    slab = project_resolved_slab_entity(slab=_resolved_slab(), boundary=_boundary()).object
    summaries, gaps = collect_live_canonical_coverage(objects=(roof, slab), registry_run_scope="test")
    assert summaries == ()
    assert gaps == {"roof": ["producer_source_lineage_unavailable"], "slab": ["producer_source_lineage_unavailable"]}
    report = build_runtime_coverage_publication(summaries, family_gaps=gaps)
    assert report["family_reports"]["roof"]["classification"] == "UNAVAILABLE"
    assert report["family_reports"]["floor_slab"]["classification"] == "UNAVAILABLE"


def test_canonical_dict_and_duplicate_physical_identity_are_rejected():
    rooms = _rooms().rooms
    with pytest.raises(TypeError):
        collect_live_canonical_coverage(objects=(rooms[0].to_dict(),), registry_run_scope="test")
    with pytest.raises(ValueError, match="duplicate producer physical identity"):
        collect_live_canonical_coverage(objects=(rooms[0], rooms[0]), registry_run_scope="test")


def test_real_upload_authority_exposes_wall_opening_dropout_without_default_height(tmp_path):
    path = tmp_path / "source.pdf"
    path.write_bytes(_complete_void_pdf())
    claim = collect_live_physical_net_wall_claim(path, pages=(0,))
    assert claim.status is not EvidenceResolutionStatus.CORROBORATED
    app = SimpleNamespace(lquery=lambda *_: [{"id": 1, "path": str(path)}])
    with patch("pb_live_physical_net_wall_integration.collect_live_physical_net_wall_claim", return_value=claim):
        rows = auto._try_physical_net_wall_rows(app, 1, [{"document_id": 1, "page_no": 1}], [])
    assert rows is None
    summaries = auto._runtime_coverage_registry_summaries(app, 1)
    assert summaries
    coverage = app._ag09_family_coverage_by_workspace[1]
    report = build_runtime_coverage_publication(summaries, family_gaps=coverage["family_gaps"])
    assert report["family_reports"]["wall"]["classification"] == "PARTIAL"
    assert report["family_reports"]["opening"]["classification"] == "PARTIAL"
    assert report["family_reports"]["wall"]["stage_counts"]["QUANTIFIED"] == 0
    assert report["family_reports"]["opening"]["stage_counts"]["PUBLISHED"] == 0
    assert auto._runtime_coverage_registry_summaries(app, 2) == []
