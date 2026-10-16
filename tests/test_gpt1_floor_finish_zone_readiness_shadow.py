"""Ten source-negative contract tests for an explicitly non-publishing shadow."""
import copy
import random

import pytest

from tools.gpt1_floor_finish_zone_readiness_shadow import (
    check_source_scope, check_unique_source_edges, check_page_view_ownership,
    check_explicit_correspondence, check_closed_source_loop,
    check_simple_source_polygon, check_zones_inside_floor,
    check_zones_nonoverlapping, check_finish_occurrence_ownership,
    check_metric_partition, inspect_candidate_finish_zone_bundle,
)


SHA = "a" * 64  # Synthetic only, never a user's source receipt.
SCOPE = dict(document_id="doc_synth", revision_id="rev_synth", source_sha256=SHA,
             snapshot_id="snapshot_synth", decision_scope_id="scope_synth")


def _edge(eid, p, q, page="7", view="floor"):
    return {**SCOPE, "id": eid, "source_observation_id": "obs_" + eid,
            "primitive_id": "prim_" + eid, "source_parent_id": "parent_" + eid,
            "page_id": page, "viewport_id": view, "p0": list(p), "p1": list(q)}


def _rect(prefix, x0, y0, x1, y1, page, view):
    pts = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    return [_edge(f"{prefix}{i}", pts[i], pts[(i+1) % 4], page, view) for i in range(4)]


def _owner(edges, *, page, view, **extra):
    return {**SCOPE, "page_id": page, "viewport_id": view,
            "edge_ids": [e["id"] for e in edges], **extra}


def _source_bundle():
    floor = _rect("f", 0, 0, 10, 10, "7", "floor")
    proj = _rect("p", 0, 0, 10, 10, "11", "finish")
    zone_a = _rect("a", 0, 0, 5, 10, "11", "finish")
    zone_b = _rect("b", 5, 0, 10, 10, "11", "finish")
    zones = [
        _owner(z, page="11", view="finish", zone_id=name,
               occurrence_record_id="occ_" + name,
               definition_record_id="definition_" + name,
               occurrence_evidence_id="material_evidence_" + name,
               metric_area_evidence_id="area_evidence_" + name,
               metric_area_m2="50")
        for z, name in ((zone_a, "a"), (zone_b, "b"))
    ]
    pairs = [{**SCOPE, "floor_edge_id": f["id"], "projection_edge_id": p["id"],
              "source_correspondence_receipt_id": "pair_" + str(i)}
             for i, (f, p) in enumerate(zip(floor, proj))]
    return {"scope": dict(SCOPE),
            "floor": _owner(floor, page="7", view="floor", physical_floor_id="floor_1",
                            canonical_floor_id="canonical_1", metric_area_m2="100",
                            metric_area_evidence_id="true_area_id"),
            "floor_projection": _owner(proj, page="11", view="finish"),
            "zones": zones, "source_correspondences": pairs,
            "edges": [*floor, *proj, *zone_a, *zone_b]}


def _check(bundle):
    return inspect_candidate_finish_zone_bundle(bundle)


def _change_edge(bundle, eid, **kv):
    edge = next(e for e in bundle["edges"] if e["id"] == eid)
    edge.update(kv)


def _index(bundle):
    return {e["id"]: e for e in bundle["edges"]}


def test_01_exact_source_lineage_positive_stale_and_conflict():
    b = _source_bundle()
    assert not check_source_scope(b["scope"], (*b["edges"], *b["zones"], b["floor"], b["floor_projection"], *b["source_correspondences"]))
    b["zones"][0]["snapshot_id"] = "foreign_snapshot"
    assert check_source_scope(b["scope"], b["zones"]) == ("source_scope_conflict",)
    b["scope"]["source_sha256"] = "NOT_SHA"
    assert check_source_scope(b["scope"], ()) == ("source_scope_incomplete",)


def test_02_original_unique_path_parents_positive_duplicate_and_bool_geometry():
    b = _source_bundle()
    assert not check_unique_source_edges(b["edges"])
    b["edges"][2]["primitive_id"] = b["edges"][0]["primitive_id"]
    assert check_unique_source_edges(b["edges"]) == ("source_edge_duplicate",)
    b = _source_bundle()
    b["edges"][0]["p1"] = [True, 0]
    assert check_unique_source_edges(b["edges"]) == ("source_edge_geometry_invalid",)


def test_03_original_viewport_positive_and_foreign_edge_negative():
    b = _source_bundle()
    assert not check_page_view_ownership(b["edges"], b["floor"], b["floor_projection"], b["zones"])
    _change_edge(b, "a2", viewport_id="legend")
    assert check_page_view_ownership(b["edges"], b["floor"], b["floor_projection"], b["zones"]) == ("source_viewport_edge_conflict",)


def test_04_cross_page_correspondence_not_a_translation_and_no_first_tie():
    b = _source_bundle()
    assert not check_explicit_correspondence(b["floor"], b["floor_projection"], b["source_correspondences"])
    b["source_correspondences"][2]["floor_edge_id"] = "f0"
    assert check_explicit_correspondence(b["floor"], b["floor_projection"], b["source_correspondences"]) == ("cross_sheet_correspondence_ambiguous",)
    b = _source_bundle()
    b["source_correspondences"] = []
    assert check_explicit_correspondence(b["floor"], b["floor_projection"], []) == ("cross_sheet_correspondence_unavailable",)


def test_05_real_loop_closed_and_split_invariant_but_missing_gap_blocks():
    b = _source_bundle()
    edges = _index(b)
    assert not check_closed_source_loop(b["floor"]["edge_ids"], edges)
    edge = edges["f0"]
    q = edge["p1"]
    edge["p1"] = [5, 0]
    new = _edge("f0_split", [5, 0], q)
    b["edges"].append(new)
    b["floor"]["edge_ids"].append("f0_split")
    assert not check_closed_source_loop(b["floor"]["edge_ids"], _index(b))
    new["p0"] = [5.001, 0]
    assert check_closed_source_loop(b["floor"]["edge_ids"], _index(b)) == ("source_loop_unclosed_or_branching",)


def test_06_crossed_or_zero_area_source_lines_are_not_physical_rings():
    b = _source_bundle()
    edges = _index(b)
    assert not check_simple_source_polygon(b["floor"]["edge_ids"], edges)
    # A topologically closed bow-tie is NOT a valid area.
    pts = [(0, 0), (10, 10), (0, 10), (10, 0)]
    crossed = [_edge(f"cross{i}", pts[i], pts[(i+1)%4]) for i in range(4)]
    ix = {e["id"]: e for e in crossed}
    assert check_closed_source_loop(list(ix), ix) == ()
    assert check_simple_source_polygon(list(ix), ix) == ("source_polygon_self_crossing_or_degenerate",)


def test_07_area_region_containment_requires_actual_source_perimeter():
    b = _source_bundle()
    assert not check_zones_inside_floor(b["floor_projection"], b["zones"], _index(b))
    for eid, key in [("b0", "p1"), ("b1", "p0"), ("b1", "p1"), ("b2", "p0")]:
        _index(b)[eid][key][0] += 0.3
    assert check_zones_inside_floor(b["floor_projection"], b["zones"], _index(b)) == ("finish_zone_outside_floor",)


def test_08_shared_material_boundary_ok_positive_interior_overlap_blocks():
    b = _source_bundle()
    assert not check_zones_nonoverlapping(b["zones"], _index(b))
    for eid, key in [("b0", "p0"), ("b3", "p0"), ("b3", "p1"), ("b2", "p1")]:
        _index(b)[eid][key][0] -= 1
    assert check_zones_nonoverlapping(b["zones"], _index(b)) == ("finish_zone_interiors_overlap",)


def test_09_material_occurrence_one_owner_only_and_legend_unissued_negative():
    b = _source_bundle()
    assert not check_finish_occurrence_ownership(b["zones"])
    b["zones"][1]["occurrence_record_id"] = b["zones"][0]["occurrence_record_id"]
    assert check_finish_occurrence_ownership(b["zones"]) == ("finish_occurrence_multiple_owners",)
    b["zones"][0]["definition_record_id"] = ""
    assert check_finish_occurrence_ownership(b["zones"]) == ("finish_occurrence_or_definition_unavailable",)


def test_10_source_polygon_partition_and_independent_metric_receipts():
    b = _source_bundle()
    assert not check_metric_partition(b["floor"], b["floor_projection"], b["zones"], _index(b))
    b["zones"][0]["metric_area_m2"] = "49.99"
    assert check_metric_partition(b["floor"], b["floor_projection"], b["zones"], _index(b)) == ("zone_metric_partition_incomplete_or_conflicting",)
    b["zones"][0]["metric_area_m2"] = "50"
    for eid, key in [("a0", "p1"), ("a1", "p0"), ("a1", "p1"), ("a2", "p0")]:
        _index(b)[eid][key][0] -= .1
    assert check_metric_partition(b["floor"], b["floor_projection"], b["zones"], _index(b)) == ("source_finish_partition_gap_or_excess",)


def test_full_positive_is_candidate_not_firm_and_never_mutates_input():
    b = _source_bundle()
    old = copy.deepcopy(b)
    out = _check(b)
    assert out == _check(copy.deepcopy(b))
    assert b == old
    assert out["status"] == "candidate"
    assert out["authority_granted"] is False and out["quantity_granted"] is False
    assert out["reason_codes"] == ()


def test_metamorphic_translate_rotate_scale_and_input_order_invariance():
    b = _source_bundle()
    for scale, rotate, offset in ((1, False, (29, -100)), (1, True, (0, 0)), (2, False, (200, 500))):
        example = copy.deepcopy(b)
        for e in example["edges"]:
            for key in ("p0", "p1"):
                x, y = e[key]
                if rotate:
                    x, y = -y, x
                e[key] = [x * scale + offset[0], y * scale + offset[1]]
        random.Random(17).shuffle(example["edges"])
        random.Random(5).shuffle(example["zones"])
        random.Random(9).shuffle(example["source_correspondences"])
        assert _check(example)["status"] == "candidate"
        assert _check(example)["authority_granted"] is False


def test_unrelated_content_and_viewport_expansion_do_not_promote_area():
    b = _source_bundle()
    extra = _edge("unrelated", (900, 900), (901, 900), "99", "detail")
    b["edges"].append(extra)
    assert _check(b)["status"] == "candidate"
    b["zones"][0]["viewport_id"] = "new_larger_viewport"
    out = _check(b)
    assert "source_viewport_edge_conflict" in out["reason_codes"]
    assert out["quantity_granted"] is False


def test_raster_legend_or_single_mark_never_mints_a_source_zone():
    b = _source_bundle()
    b["zones"][0]["edge_ids"] = []
    b["zones"][0]["occurrence_record_id"] = "legend_mark"
    out = _check(b)
    assert out["status"] == "abstained"
    assert out["authority_granted"] is False


def test_multiple_owners_never_select_nearest():
    b = _source_bundle()
    b["source_correspondences"].append({**b["source_correspondences"][0],
                                            "source_correspondence_receipt_id": "competing"})
    out = _check(b)
    assert "cross_sheet_correspondence_ambiguous" in out["reason_codes"]
    assert out["status"] != "candidate"


@pytest.mark.parametrize("invalid", [None, 17, {}, {"floor": None}, {"floor": {}, "floor_projection": {}, "zones": None}])
def test_malformed_shadow_bundle_fail_closed_without_exception(invalid):
    out = inspect_candidate_finish_zone_bundle(invalid)
    assert out["status"] == "abstained"
    assert out["quantity_granted"] is False


def test_source_observation_ids_cannot_be_reused_by_distinct_edges():
    b = _source_bundle()
    b["edges"][1]["source_observation_id"] = b["edges"][0]["source_observation_id"]
    assert check_unique_source_edges(b["edges"]) == ("source_edge_duplicate",)
    assert _check(b)["quantity_granted"] is False


def test_missing_page_or_malformed_edge_refs_abstain_not_first_match():
    b = _source_bundle()
    del b["edges"][0]["page_id"]
    assert check_unique_source_edges(b["edges"]) == ("source_edge_witness_incomplete",)
    b = _source_bundle()
    b["zones"][0]["edge_ids"] = "a0"
    out = _check(b)
    assert out["authority_granted"] is False
    assert "source_edge_list_invalid" in out["reason_codes"]