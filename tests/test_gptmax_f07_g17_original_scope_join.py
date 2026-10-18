"""F07 plan view geometry cannot assert G17 instance type across snapshot roots."""
from copy import deepcopy
import pytest

from tools.diag_gptmax_f07_g17_original_scope_join import (
    original_f07_g17_source_join_shadow as audit,
)

SHA = "a" * 64
REV = "source_revision_test"


def fixtures():
    view = {
        "source_sha256": SHA, "revision_id": REV,
        "snapshot_id": "f07_root", "page_number": 3,
        "authoritative_plan_view_count": 1,
        "default_segmentation_unchanged": True,
        "published_snapshot_unchanged": True,
        "metric_authority_granted": False,
        "viewports": [{
            "view_id": "source_plan_view_test",
            "authoritative": True, "view_type": "floor_plan",
            "status": "derived", "bounding_box": [10, 10, 90, 90],
            "downstream_migration": {"ownership_id": "f07-proven"},
            "provenance": {"source_owned_plan_view_proven": True},
        }],
    }
    source = {
        "source_sha256": SHA, "snapshot_id": "opening_root",
        "production_activation_granted": False,
        "baseline_receipts": {
            "walls": [{
                "document_id": "doc1", "revision_id": REV,
                "source_sha256": SHA, "snapshot_id": "opening_root",
                "page_id": "3", "scope_complete": True,
            }],
            "canonical": [{
                "physical_opening_id": "p1", "snapshot_id": "opening_root",
                "source_sha256": SHA, "source_geometries": [[40, 40, 42, 40]],
            }],
            "hosts": [{
                "opening_identity_id": "p1", "host_wall_id": None,
                "record_id": None, "reason_codes": ["no_authenticated_host_wall_band"],
            }],
        },
        "baseline_source_audit": {
            "raster_candidate_closure": {
                "candidate_universe_complete": False,
                "raw_candidate_count": 2, "resolved_candidate_count": 0,
                "unresolved_candidate_ids": ["raw-inside", "raw-outside"],
            },
            "raw_registered_gaps": [{
                "raw_candidate_id": "raw-inside",
                "source_scope": {
                    "document_id": "doc1", "revision_id": REV,
                    "source_sha256": SHA, "snapshot_id": "opening_root", "page_id": "3",
                },
                "aperture_bbox_pt": [20, 20, 30, 30],
                "source_observation_ids": ["one", "two"],
            }, {
                "raw_candidate_id": "raw-outside",
                "source_scope": {
                    "document_id": "doc1", "revision_id": REV,
                    "source_sha256": SHA, "snapshot_id": "opening_root", "page_id": "3",
                },
                "aperture_bbox_pt": [20, 100, 30, 110],
                "source_observation_ids": ["three", "four"],
            }],
        },
    }
    return view, source


def run(pair):
    return audit(*pair, source_sha256=SHA, page_id="3")


def test_source_positive_view_and_unresolved_gap_does_not_grant_cross_root_physical_role():
    pair = fixtures()
    before = deepcopy(pair)
    r = run(pair)
    assert r["same_snapshot"] is False
    assert [x["relation"] for x in r["unresolved_raw"]] == [
        "GEOMETRICALLY_INSIDE_OTHER_SNAPSHOT_VIEW",
        "GEOMETRICALLY_DISJOINT_OTHER_SNAPSHOT_VIEW",
    ]
    assert len(r["original_hostless_openings"]) == 1
    assert r["original_hostless_openings"][0]["source_host_granted"] is False
    assert all(not v for v in r["authority_grants"].values())
    assert pair == before


def test_even_same_snapshot_must_not_upgrade_geometry_to_typed_opposition():
    view, opening = fixtures()
    view["snapshot_id"] = "opening_root"
    r = run((view, opening))
    assert r["same_snapshot"] is True
    assert all(not v for v in r["authority_grants"].values())


def test_crossing_source_gap_is_not_rejected_as_nonplan():
    view, opening = fixtures()
    opening["baseline_source_audit"]["raw_registered_gaps"][0]["aperture_bbox_pt"] = [8, 20, 12, 30]
    r = run((view, opening))
    assert r["unresolved_raw"][0]["relation"] == "INTERSECTS_OTHER_SNAPSHOT_VIEW_NO_ROLE_AUTHORITY"
    assert r["unresolved_raw"][0]["typed_nonplan_role_proven"] is False


@pytest.mark.parametrize("change", [
    lambda v, o: v.update(source_sha256="0" * 64),
    lambda v, o: o.update(source_sha256="0" * 64),
    lambda v, o: v.update(revision_id="foreign"),
    lambda v, o: v.update(authoritative_plan_view_count=2),
    lambda v, o: v["viewports"][0].update(authoritative=False),
    lambda v, o: v["viewports"][0].update(downstream_migration=None),
    lambda v, o: v["viewports"][0]["provenance"].update(source_owned_plan_view_proven=False),
    lambda v, o: v.update(published_snapshot_unchanged=False),
    lambda v, o: o["baseline_receipts"]["walls"][0].update(scope_complete=False),
    lambda v, o: o["baseline_source_audit"]["raster_candidate_closure"].update(candidate_universe_complete=True),
    lambda v, o: o["baseline_source_audit"]["raw_registered_gaps"][0]["source_scope"].update(snapshot_id="stale"),
    lambda v, o: o["baseline_receipts"]["hosts"][0].update(host_wall_id="fictional"),
    lambda v, o: o["baseline_receipts"]["canonical"][0].update(snapshot_id="stale"),
    lambda v, o: o["baseline_source_audit"]["raw_registered_gaps"][0].update(aperture_bbox_pt=[0, float("nan"), 1, 5]),
])
def test_corrupt_foreign_or_unearned_source_authority_abstains(change):
    v, o = fixtures()
    change(v, o)
    with pytest.raises((ValueError, KeyError)):
        run((v, o))


def test_raw_input_permutation_cannot_change_source_classification():
    v, o = fixtures()
    expected = run((v, o))
    o["baseline_source_audit"]["raw_registered_gaps"].reverse()
    assert run((v, o)) == expected


def test_duplicate_original_raw_id_is_rejected_not_overwritten():
    v, o = fixtures()
    o["baseline_source_audit"]["raw_registered_gaps"].append(
        deepcopy(o["baseline_source_audit"]["raw_registered_gaps"][0]))
    with pytest.raises(ValueError, match="inventory"):
        run((v, o))
