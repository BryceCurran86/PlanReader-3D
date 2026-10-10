"""Evidence-only original source report census and malformed input negatives."""
from copy import deepcopy

import pytest

from tools.diag_gptmax_source_host_first_gate import source_first_gate_census


SHA = "a" * 64


def report():
    first = {
        "wall_candidate_id": "shared-w4-id",
        "wall_candidate": {
            "candidate_id": "shared-w4-id",
            "face_a_segment_ids": ["split-1"],
            "face_b_segment_ids": None,
            "end_node_ids": ["junction-one", "junction-middle"],
        },
        "physical_identity": {
            "wall_candidate_id": "shared-w4-id",
            "edge_ids": ["split-2"],
        },
    }
    second = deepcopy(first)
    second["wall_candidate"]["face_a_segment_ids"] = ["split-2"]
    second["wall_candidate"]["end_node_ids"] = ["junction-middle", "junction-two"]
    return {
        "source_sha256": SHA,
        "revision_id": "source_revision_from_pdf",
        "snapshot_id": "source_snapshot_from_revision",
        "source_decode_coverage": {
            "document_id": "producer-source-document",
            "revision_id": "source_revision_from_pdf",
        },
        "selected_geometry_page_ids": ["3"],
        "primitive_safety_cap": 20_000,
        "source_owned_wall_scope_results": [{
            "page_id": "3",
            "decision_scope_id": "wall-source:page-3",
            "source_sha256": SHA,
            "document_id": "producer-source-document",
            "revision_id": "source_revision_from_pdf",
            "snapshot_id": "source_snapshot_from_revision",
            "records": [first, second],
        }],
        "opening_bindings": [
            {
                "page_id": "3", "opening_identity_id": "real-opening-1",
                "host_wall_id": None,
                "reason_codes": [
                    "no_authenticated_host_wall_band",
                    "raster_source_band_left_source_primitive_unmapped",
                ],
            },
            {
                "page_id": "3", "opening_identity_id": "real-opening-2",
                "host_wall_id": "real-proven-original-host",
                "reason_codes": ["opening_host_binding_resolved"],
            },
        ],
        "host_frames": [],
        "summary": {
            "physical_existence_claims": 2, "host_bindings": 1, "host_frames": 0,
        },
    }


def test_original_source_first_gate_is_observational_not_host_or_count_proof():
    prior = report()
    untouched = deepcopy(prior)
    census = source_first_gate_census(prior, expected_source_sha=SHA)
    assert prior == untouched
    assert census["source_summary_verified"] == {
        "physical_existence_claims": 2, "host_bindings": 1, "host_frames": 0
    }
    assert census["unhosted_first_gate_counts"] == {
        "left_original_raster_source_primitive_unmapped": 1
    }
    assert len(census["unhosted_original_openings"]) == 1
    assert len(census["w4_candidate_address_collisions"]) == 1
    assert len(census["physical_identity_sidecar_edge_mismatches"]) == 1
    assert census["physical_identity_sidecar_edge_mismatches"][0]["w4_source_edge_ids"] == ["split-1"]
    assert census["host_publication_allowed"] is False
    assert census["opening_count_publication_allowed"] is False
    assert census["metric_quantity_publication_allowed"] is False
    assert census["benchmark_accuracy"] is None
    assert census["original_pdf_bytes_reauthenticated_by_this_report"] is False


@pytest.mark.parametrize("mutate", [
    lambda x: x.update(source_sha256="unauthenticated"),
    lambda x: x.update(primitive_safety_cap=40_000),
    lambda x: x["summary"].update(host_bindings=2),
    lambda x: x["opening_bindings"].append(deepcopy(x["opening_bindings"][0])),
    lambda x: x["source_owned_wall_scope_results"][0].update(source_sha256="b" * 64),
    lambda x: x["source_owned_wall_scope_results"][0].update(page_id="99"),
    lambda x: x["source_owned_wall_scope_results"][0]["records"][0]["wall_candidate"].update(candidate_id="foreign-wall"),
    lambda x: x["source_owned_wall_scope_results"][0]["records"][0]["physical_identity"].update(wall_candidate_id="foreign-wall"),
])
def test_untrusted_or_corrupt_original_report_never_claims_source_authority(mutate):
    data = report()
    mutate(data)
    with pytest.raises(ValueError):
        source_first_gate_census(data, expected_source_sha=SHA)


def test_missing_a_source_sha_is_explicitly_rejected():
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        source_first_gate_census(report(), expected_source_sha="b" * 64)


def test_generic_multiple_source_viewport_scopes_preserve_page_ownership():
    sample = report()
    secondary = deepcopy(sample["source_owned_wall_scope_results"][0])
    secondary["decision_scope_id"] = "wall-source:page-3:source-viewport-2"
    secondary["records"] = []
    sample["source_owned_wall_scope_results"].append(secondary)
    census = source_first_gate_census(sample)
    assert len(census["source_wall_scope_census"]) == 2
    assert census["source_summary_verified"]["host_bindings"] == 1


def test_source_report_does_not_invent_hosts_for_unclassified_absence():
    sample = report()
    sample["opening_bindings"][0]["reason_codes"] = ["no_authenticated_host_wall_band"]
    census = source_first_gate_census(sample)
    assert census["unhosted_first_gate_counts"] == {"source_host_wall_band_unproven": 1}
    assert census["unhosted_original_openings"][0]["opening_identity_id"] == "real-opening-1"
    assert not any(item.get("host_wall_id") for item in census["unhosted_original_openings"])


def test_original_producer_host_status_is_never_inferred_from_missing_records():
    sample = report()
    sample["opening_bindings"].clear()
    sample["host_frames"].clear()
    sample["summary"] = {
        "physical_existence_claims": 0, "host_bindings": 0, "host_frames": 0
    }
    census = source_first_gate_census(sample)
    assert census["unhosted_first_gate_counts"] == {}
    assert census["host_publication_allowed"] is False


def test_two_authentic_missing_flank_gates_never_choose_first_by_side():
    sample = report()
    sample["opening_bindings"][0]["reason_codes"] = [
        "no_authenticated_host_wall_band",
        "raster_source_band_right_source_primitive_unmapped",
        "raster_source_band_left_source_primitive_unmapped",
    ]
    census = source_first_gate_census(sample)
    assert census["unhosted_first_gate_counts"] == {
        "multiple_source_host_gates_unresolved": 1
    }
    row = census["unhosted_original_openings"][0]
    assert row["all_specific_observed_gates"] == [
        "left_original_raster_source_primitive_unmapped",
        "right_original_raster_source_primitive_unmapped",
    ]
    assert row["first_observed_host_gate"] == "multiple_source_host_gates_unresolved"
    assert census["host_publication_allowed"] is False


@pytest.mark.parametrize("broken", ["host_not_dict", "scope_not_dict", "frame_not_dict"])
def test_invalid_receipt_types_fail_closed_as_value_error(broken):
    sample = report()
    if broken == "host_not_dict":
        sample["opening_bindings"][0] = None
    elif broken == "scope_not_dict":
        sample["source_owned_wall_scope_results"][0] = None
    else:
        sample["host_frames"] = [None]
    with pytest.raises(ValueError, match="receipts unavailable"):
        source_first_gate_census(sample)


@pytest.mark.parametrize("reasons,expected", [
    (["ambiguous_physical_wall_equivalence_for_host"],
     "physical_wall_equivalence_ambiguous_for_host"),
    (["opening_two_face_wall_lineage_ambiguous",
      "ambiguous_physical_wall_equivalence_for_host"],
     "physical_wall_equivalence_ambiguous_for_host"),
    (["complete_authenticated_host_wall_universe_required",
      "physical_wall_candidate_scope_unavailable",
      "no_local_host_wall_candidates"],
     "source_wall_scope_boundary_or_completeness_unproven"),
    (["complete_authenticated_host_wall_universe_required",
      "physical_wall_candidate_scope_cropped_at_viewport_boundary",
      "ambiguous_physical_wall_equivalence_for_host"],
     "source_wall_scope_boundary_or_completeness_unproven"),
])
def test_source_host_gate_classification_does_not_hide_upstream_authority_failures(
    reasons, expected
):
    sample = report()
    sample["opening_bindings"][0]["reason_codes"] = reasons
    census = source_first_gate_census(sample)
    assert census["unhosted_first_gate_counts"] == {expected: 1}
    assert not census["physical_wall_equivalence_proven"]
    assert not census["host_publication_allowed"]


@pytest.mark.parametrize("mutate", [
    lambda x: x.update(snapshot_id="foreign-snapshot"),
    lambda x: x.update(revision_id="foreign-revision"),
    lambda x: x["source_decode_coverage"].update(
        revision_id="foreign-source-revision"),
    lambda x: x["source_owned_wall_scope_results"][0].update(
        snapshot_id="foreign-source-snapshot"),
    lambda x: x["source_owned_wall_scope_results"][0].update(
        document_id="different-document"),
    lambda x: x["source_owned_wall_scope_results"][0].update(
        revision_id="different-revision"),
])
def test_source_report_never_mixes_a_foreign_snapshot_or_revision(mutate):
    original = report()
    mutate(original)
    with pytest.raises(ValueError, match="revision|snapshot|document"):
        source_first_gate_census(original, expected_source_sha=SHA)
