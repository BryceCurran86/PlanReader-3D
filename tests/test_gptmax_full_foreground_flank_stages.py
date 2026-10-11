"""Local geometry survival must not borrow a discarded source or elect an owner."""
from copy import deepcopy
from hashlib import sha256
import json

import pytest

from scripts.gptmax_full_foreground_flank_stages import _flank_stage_rows, _fresh_source_reports
from tools.diag_gptmax_full_foreground_run_source import original_full_foreground_report
from tools.diag_gptmax_raster_host_source_membership import original_raster_host_ancestry_census
from test_gptmax_full_foreground_run_source import pdf


def _fixture():
    original = {"opening_rows": [{"opening_identity_id": "original-opening",
        "original_aperture_coordinate_basis": {"origin": [20., 20.], "axis": [1., 0.],
            "normal": [0., 1.], "length": 10., "thickness": 2.}}]}
    required = {"opening_rows": [{"opening_identity_id": "original-opening", "flanks": [
        {"role": "left", "axis_span_pt": [-4., 0.], "normal_span_pt": [-1., 1.],
         "end_axis_coordinate_pt": 0.}]}]}
    joined = {"opening_rows": [{"opening_identity_id": "original-opening", "flanks": [
        {"role": "left", "first_unproved_authority": "ORIGINAL_VISIBLE_STRUCTURAL_WALL_LINE",
         "pixel_run_candidates": [{"source_observation_id": "original-pixel", "source_line_pt": [16., 20., 20., 20.]}]}]}]}
    graph = {"source_parent_census": [{"source_observation_id": "original-pixel", "w2_edge_ids": ["lost", "kept"], "snap_collapsed_fragment_ids": []}],
        "all_snap_collapsed_fragments": [],
        "all_w2_edges": [
            {"edge_id": "lost", "w2_fragment_geometry_pt": [16., 20., 20., 20.],
             "w3_retained": False, "w3_removed": True, "experimental_w4_candidate_ids": []},
            {"edge_id": "kept", "w2_fragment_geometry_pt": [16., 20.5, 20., 20.5],
             "w3_retained": True, "w3_removed": False, "experimental_w4_candidate_ids": ["wall"]}],
        "all_experimental_w4_candidates": [{"candidate_id": "wall", "w2_edge_ids": ["kept"], "centerline_pt": [[16., 20.5], [20., 20.5]], "physical_host_authority": False}]}
    return joined, original, required, graph


def _row(args):
    return _flank_stage_rows(*args)[0]["flanks"][0]["source_run_rows"][0]


def test_separate_retained_and_removed_edges_never_transfer_source_or_host():
    args = _fixture()
    before = deepcopy(args)
    row = _row(args)
    assert row["observed_geometry_barrier"] == "W4_LOCAL_CANDIDATES_AWAIT_WALL_ROLE_AND_EQUIVALENCE"
    edges = {e["edge_id"]: e for e in row["actual_w2_edge_rows"]}
    assert not edges["lost"]["experimental_w4_records"]
    assert edges["kept"]["experimental_w4_records"]
    assert all(e["source_parent_transfer_allowed"] is False and e["physical_host_authority"] is False for e in edges.values())
    assert row["first_unproved_authority"] == "ORIGINAL_VISIBLE_STRUCTURAL_WALL_LINE"
    assert row["physical_equivalence_proven"] is False and row["host_publication_allowed"] is False
    assert args == before


def test_reused_candidate_address_preserves_both_actual_wall_records():
    args = _fixture()
    args[3]["all_experimental_w4_candidates"].append({
        "candidate_id": "wall", "w2_edge_ids": ["unrelated"], "centerline_pt": [[16., 19.5], [20., 19.5]], "physical_host_authority": False})
    row = _row(args)
    assert row["observed_geometry_barrier"] == "W4_CANDIDATE_ADDRESS_COLLISION"
    edge = next(e for e in row["actual_w2_edge_rows"] if e["edge_id"] == "kept")
    assert edge["w4_candidate_address_ambiguous"] is True
    assert len(edge["experimental_w4_records"]) == 2
    assert not row["host_publication_allowed"]


@pytest.mark.parametrize("case, expected", [
    ("removed", "W3_NODE_PAIR_DEDUP_REMOVED_REQUIRED_FLANK"),
    ("foreign_local", "W2_NO_SURVIVING_REQUIRED_FLANK_FRAGMENT"),
    ("no_owner", "W4_LOCAL_SOURCE_OWNER_UNAVAILABLE"),
    ("unmapped", "W2_SOURCE_PARENT_UNMAPPED")])
def test_original_geometry_barrier_is_reported_before_any_host_claim(case, expected):
    args = _fixture()
    graph = args[3]
    if case == "removed":
        graph["all_w2_edges"][1].update(w3_retained=False, w3_removed=True, experimental_w4_candidate_ids=[])
    elif case == "foreign_local":
        for e in graph["all_w2_edges"]: e["w2_fragment_geometry_pt"] = [160., 20., 200., 20.]
    elif case == "no_owner": graph["all_w2_edges"][1]["experimental_w4_candidate_ids"] = []
    else: graph["source_parent_census"][0]["w2_edge_ids"] = []
    row = _row(args)
    assert row["observed_geometry_barrier"] == expected
    assert not row["host_publication_allowed"]


def test_snap_collapsed_source_survives_as_explicit_negative_geometry_evidence():
    args = _fixture()
    graph = args[3]
    graph["source_parent_census"][0].update(w2_edge_ids=[], snap_collapsed_fragment_ids=["collapsed"])
    graph["all_snap_collapsed_fragments"] = [{"fragment_id": "collapsed",
        "source_fragment_geometry_pt": [16., 20., 20., 20.],
        "source_observation_ids": ["original-pixel"], "reason": "snap_collapsed"}]
    row = _row(args)
    assert row["actual_snap_collapsed_rows"][0]["matches_original_required_flank_geometry"]
    assert row["observed_geometry_barrier"] == "W2_NO_SURVIVING_REQUIRED_FLANK_FRAGMENT"
    assert not row["actual_w2_edge_rows"]


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotated_translated_source_geometry_has_same_failure_stage(rotation):
    import math
    args = _fixture()
    angle = math.radians(rotation)
    c, s = round(math.cos(angle)), round(math.sin(angle))
    def point(p): return [c*p[0]-s*p[1]+55, s*p[0]+c*p[1]+34]
    def vector(p): return [c*p[0]-s*p[1], s*p[0]+c*p[1]]
    basis = args[1]["opening_rows"][0]["original_aperture_coordinate_basis"]
    basis["origin"] = point(basis["origin"])
    basis["axis"], basis["normal"] = vector(basis["axis"]), vector(basis["normal"])
    for edge in args[3]["all_w2_edges"]:
        line = edge["w2_fragment_geometry_pt"]
        edge["w2_fragment_geometry_pt"] = point(line[:2]) + point(line[2:])
    assert _row(args)["observed_geometry_barrier"] == "W4_LOCAL_CANDIDATES_AWAIT_WALL_ROLE_AND_EQUIVALENCE"


def test_input_order_and_unrelated_geometry_do_not_change_local_source_stage():
    args = _fixture()
    expected = _row(args)
    args[3]["all_w2_edges"].reverse()
    args[3]["source_parent_census"][0]["w2_edge_ids"].reverse()
    args[3]["all_w2_edges"].append({"edge_id": "other", "w2_fragment_geometry_pt": [0., 0., 2., 2.],
        "w3_retained": True, "w3_removed": False, "experimental_w4_candidate_ids": []})
    assert _row(args) == expected


@pytest.fixture(scope="module")
def fresh_reports():
    data = pdf()
    digest = sha256(data).hexdigest()
    original = original_raster_host_ancestry_census(data, page_id="1", expected_source_sha=digest)
    foreground = original_full_foreground_report(data, page_id="1", expected_source_sha=digest, trace=True)
    return data, original, foreground, digest


def test_real_pdf_reports_are_independently_reproduced_before_reading_graph(fresh_reports):
    data, original, foreground, digest = fresh_reports
    a, b = _fresh_source_reports(data, original, foreground, digest)
    assert json.dumps(a, sort_keys=True) == json.dumps(original, sort_keys=True)
    assert json.dumps(b, sort_keys=True) == json.dumps(foreground, sort_keys=True)


@pytest.mark.parametrize("damage", ["source", "g17", "pixel", "parent", "edge", "wall"])
def test_forged_pixel_lineage_or_topology_is_rejected_even_with_same_sha(fresh_reports, damage):
    data, original, foreground, digest = deepcopy(fresh_reports)
    if damage == "source": data = b"foreign PDF"
    elif damage == "g17": original["source_original_host_count"] += 1
    elif damage == "pixel":
        record = foreground["authenticated_pixel_source_records"][0]["source_observation"]
        geometry = list(record["geometry"])
        geometry[0] += .00000001
        record["geometry"] = geometry
    elif damage == "parent": foreground["experimental_w2_w4"]["source_parent_census"][0]["source_observation_id"] = "borrowed"
    elif damage == "edge": foreground["experimental_w2_w4"]["all_w2_edges"][0]["w3_retained"] = False
    else: foreground["experimental_w2_w4"]["all_experimental_w4_candidates"][0]["candidate_id"] = "borrowed"
    with pytest.raises(ValueError):
        _fresh_source_reports(data, original, foreground, digest)
