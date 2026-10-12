"""Focused actual-record membership proofs; no physical identity promotion."""
from copy import deepcopy
from dataclasses import replace
from hashlib import sha256

import pytest

from scripts import gptmax_exact_source_fragment_bundles as shadow
from test_gptmax_exact_endpoint_flank_shadow import record
from test_gptmax_full_foreground_run_source import pdf


def fixture(*, together=False):
    records = (record("source", [0., 0., 10., 0.]),)
    edges = [dict(edge_id=key, source_observation_ids=["source"],
        w2_fragment_geometry_pt=line, w3_retained=True, w3_removed=False,
        experimental_w4_candidate_ids=["reused-address"],
        w4_candidate_membership_available=True, w4_abstained_chain_record_ids=[])
        for key, line in (("a", [0., 0., 5., 0.]), ("b", [5., 0., 10., 0.]))]
    candidates = ([dict(candidate_id="reused-address", w2_edge_ids=["a", "b"],
        centerline_pt=[(0., 0.), (5., 0.), (10., 0.)])] if together else
        [dict(candidate_id="reused-address", w2_edge_ids=[e["edge_id"]],
            centerline_pt=[tuple(e["w2_fragment_geometry_pt"][:2]),
                           tuple(e["w2_fragment_geometry_pt"][2:])]) for e in edges])
    return dict(input_source_count=1, all_w2_edges=edges,
        all_experimental_w4_candidates=candidates, all_w4_abstained_chain_rows=[],
        source_parent_census=[dict(source_observation_id="source", w2_edge_ids=["a", "b"])]), records


def test_reused_address_does_not_prove_one_actual_record_owns_a_complete_span():
    args = fixture(); before = deepcopy(args)
    result = shadow.join_actual_source_bundles(*args)
    span, = result["source_span_rows"]
    assert span["exact_source_span_coverage"]["complete_actual_w3_retained_source_span_coverage"]
    assert span["common_candidate_ids"] == ["reused-address"]
    assert span["common_actual_assembly_record_ids"] == []
    assert span["status"] == "abstained"
    assert len({r["record_id"] for r in result["actual_assembly_records"]}) == 2
    assert args == before
    result["actual_assembly_records"][0]["centerline_pt"][0] = (999., 999.)
    assert args == before


def test_complete_actual_bundle_is_candidate_evidence_without_wall_or_host_authority():
    result = shadow.join_actual_source_bundles(*fixture(together=True))
    span, = result["source_span_rows"]
    assert len(span["common_actual_assembly_record_ids"]) == 1
    assert span["status"] == "candidate"
    for key in ("source_authenticated_by_join_alone", "combined_graph_edge_created",
            "physical_equivalence_proven", "structural_wall_role_proven",
            "host_publication_allowed", "opening_count_publication_allowed",
            "metric_quantity_publication_allowed"):
        assert result[key] is False
    assert result["benchmark_accuracy"] is None


def test_owned_fragment_gap_is_not_bridged_by_common_record_membership():
    graph, records = fixture(together=True)
    graph["all_w2_edges"][1]["w2_fragment_geometry_pt"][0] = 5.5
    span, = shadow.join_actual_source_bundles(graph, records)["source_span_rows"]
    assert span["exact_source_span_coverage"]["w3_uncovered_source_intervals_pt"] == [[5., 5.5]]
    assert span["status"] == "abstained"


def test_explicitly_abstained_fragment_retains_its_chain_and_never_borrows_record():
    graph, records = fixture()
    edge = graph["all_w2_edges"][1]
    edge.update(experimental_w4_candidate_ids=[], w4_candidate_membership_available=False,
        w4_abstained_chain_record_ids=["abstained-chain"])
    graph["all_experimental_w4_candidates"].pop()
    graph["all_w4_abstained_chain_rows"] = [dict(record_id="abstained-chain",
        actual_owned_w3_fragment_rows=[dict(edge_id="b", source_observation_ids=["source"],
            w2_fragment_geometry_pt=list(edge["w2_fragment_geometry_pt"]),
            primitive_lineage=dict(source_primitive_ids=["source"]))])]
    result = shadow.join_actual_source_bundles(graph, records)
    span, = result["source_span_rows"]
    assert result["actual_abstained_fragment_count"] == 1
    assert span["reason_codes"] == ["actual_source_span_assembly_abstained"]
    assert span["contributing_fragment_rows"][1]["abstained_chain_record_ids"] == ["abstained-chain"]


@pytest.mark.parametrize("damage", ["foreign_parent", "dual_record", "omitted_record", "false_address", "missing_census"])
def test_contradictory_or_incomplete_fragment_membership_rejects_the_join(damage):
    graph, records = fixture()
    if damage == "foreign_parent": graph["all_w2_edges"][0]["source_observation_ids"] = ["foreign"]
    elif damage == "dual_record": graph["all_experimental_w4_candidates"].append(deepcopy(graph["all_experimental_w4_candidates"][0]))
    elif damage == "omitted_record": graph["all_experimental_w4_candidates"].pop()
    elif damage == "false_address": graph["all_w2_edges"][0]["experimental_w4_candidate_ids"] = ["other"]
    else: graph["source_parent_census"] = []
    with pytest.raises(ValueError): shadow.join_actual_source_bundles(graph, records)


def test_parentless_actual_record_is_retained_as_unavailable_source_ownership():
    graph, records = fixture()
    graph["all_w2_edges"][1]["source_observation_ids"] = []
    graph["source_parent_census"][0]["w2_edge_ids"] = ["a"]
    result = shadow.join_actual_source_bundles(graph, records)
    bundle, = (b for b in result["actual_assembly_records"] if "b" in b["actual_w2_edge_ids"])
    assert bundle["parentless_fragment_ids"] == ["b"]
    assert bundle["all_fragment_source_parents_available"] is False
    assert bundle["status"] == "abstained" and bundle["source_observation_ids"] == []


def test_transform_and_order_changes_do_not_elect_an_alternative_or_mutate_inputs():
    graph, records = fixture(); expected = shadow.join_actual_source_bundles(graph, records)
    graph["all_w2_edges"].reverse(); graph["all_experimental_w4_candidates"].reverse()
    assert shadow.join_actual_source_bundles(graph, records) == expected
    def point(p): return (-3*p[1]+40., 3*p[0]+70.)
    for edge in graph["all_w2_edges"]:
        line = edge["w2_fragment_geometry_pt"]
        edge["w2_fragment_geometry_pt"] = [*point(line[:2]), *point(line[2:])]
    for candidate in graph["all_experimental_w4_candidates"]:
        candidate["centerline_pt"] = [point(p) for p in candidate["centerline_pt"]]
    transformed = tuple(replace(r, geometry=(*point(r.geometry[:2]), *point(r.geometry[2:]))) for r in records)
    span, = shadow.join_actual_source_bundles(graph, transformed)["source_span_rows"]
    assert span["common_candidate_ids"] == ["reused-address"]
    assert span["common_actual_assembly_record_ids"] == [] and span["status"] == "abstained"


def test_original_pdf_replay_retains_graph_and_production_and_rejects_wrong_bytes():
    b = pdf(); expected_sha = sha256(b).hexdigest()
    result = shadow.original_source_bundle_report(b, page_id="1", expected_source_sha=expected_sha)
    assert result["original_source_reauthenticated"] is True
    assert result["default_production_state_unchanged"] is True
    assert result["exact_candidate_abstention_partition_verified"] is True
    assert result["host_publication_allowed"] is False
    with pytest.raises(ValueError, match="SHA"):
        shadow.original_source_bundle_report(b+b"foreign", page_id="1", expected_source_sha=expected_sha)
