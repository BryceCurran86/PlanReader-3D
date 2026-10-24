"""Imported explanation packets cannot claim closure by a Boolean alone."""
from copy import deepcopy

import pytest

import pb_opening_source_review_shadow as review


def packet():
    scope = dict(document_id="doc", revision_id="rev", source_sha256="a"*64,
                 snapshot_id="snapshot", page_id="1")
    def row(oid, parents):
        return {**scope, "observation_id":oid, "observation_kind":"source_line",
                "source_primitive_ref":"native:"+oid, "geometry":[0.,0.,10.,0.],
                "derivation_parent_ids":parents}
    return {"packet_id":"packet-original", "opening_identity_id":"physical-opening", "page_id":"1",
            "physical_opening":{**scope,"record_id":"physical-opening","source_observation_ids":["root"]},
            "source_lineage":{"roots":["root"], "source_proof_closed":True,
                "unresolved_parent_ids":[], "observations":[row("root", ["parent"]),row("parent", [])]}}


def result(alternate, original=None):
    return review.compare_opening_source_correspondence(
        (packet() if original is None else original,), (alternate,))[0]


@pytest.mark.parametrize("damage", ["missing-parent", "cycle", "self-cycle", "duplicate-parent",
    "unreachable-record", "missing-root", "contradictory-root", "wrong-opening", "wrong-page",
    "foreign-scope", "invalid-geometry", "bool-coordinate", "missing-kind", "malformed-links",
    "malformed-row", "wrong-selector", "unknown-unresolved-roster"])
def test_claimed_closed_packet_rechecks_the_complete_parent_graph(damage):
    p = packet()
    lineage = p["source_lineage"]
    root, parent = lineage["observations"]
    if damage == "missing-parent": lineage["observations"].pop()
    elif damage == "cycle": parent["derivation_parent_ids"] = ["root"]
    elif damage == "self-cycle": parent["derivation_parent_ids"] = ["parent"]
    elif damage == "duplicate-parent": root["derivation_parent_ids"] *= 2
    elif damage == "unreachable-record":
        extra = deepcopy(parent);extra["observation_id"]="unrelated";lineage["observations"].append(extra)
    elif damage == "missing-root": lineage["roots"] = ["missing"]
    elif damage == "contradictory-root": p["physical_opening"]["source_observation_ids"] = ["parent"]
    elif damage == "wrong-opening": p["opening_identity_id"] = "other-opening"
    elif damage == "wrong-page": p["page_id"] = "2"
    elif damage == "foreign-scope": parent["snapshot_id"] = "foreign"
    elif damage == "invalid-geometry": parent["geometry"][0] = float("nan")
    elif damage == "bool-coordinate": parent["geometry"][0] = True
    elif damage == "missing-kind": parent.pop("observation_kind")
    elif damage == "malformed-links": root["derivation_parent_ids"] = "parent"
    elif damage == "malformed-row": lineage["observations"][1] = None
    elif damage == "wrong-selector": p["selector"] = {"document_id":"foreign"}
    elif damage == "unknown-unresolved-roster": lineage["unresolved_parent_ids"] = None
    r = result(p)
    assert r["source_support_packet_complete"] is False
    assert r["exact_source_support_original_ids"] == []
    assert r["source_support_blockers"]
    assert r["physical_identity_alias_granted"] is False


def test_same_root_with_changed_transitive_source_is_not_exact_support():
    p = packet()
    p["source_lineage"]["observations"][1]["source_primitive_ref"] = "native:different-parent"
    r = result(p)
    assert r["source_support_packet_complete"] is True
    assert r["exact_source_support_original_ids"] == []


def test_parent_order_and_explanation_aliases_do_not_create_extra_occurrences():
    original = packet()
    p = deepcopy(original)
    p["source_lineage"]["observations"].reverse()
    before = deepcopy((original,p))
    alias = deepcopy(original);alias["packet_id"]="same-physical-explanation"
    r = review.compare_opening_source_correspondence((original,alias),(p,))[0]
    assert r["exact_source_support_original_ids"] == ["physical-opening"]
    assert (original,p) == before
    assert result(p)["source_support_packet_complete"] is True


def test_closed_graph_budget_counts_links_before_source_fingerprinting(monkeypatch):
    p = packet()
    monkeypatch.setattr(review, "MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS", 2)
    r = result(p)
    assert not r["source_support_packet_complete"]
    assert r["source_support_blockers"] == ["source_parent_evidence_budget_exceeded"]


def test_deep_acyclic_source_graph_needs_no_recursion_or_missing_parent_shortcut():
    p = packet()
    template = p["source_lineage"]["observations"][1]
    nodes = []
    for i in range(1200):
        row = deepcopy(template)
        row["observation_id"] = f"node-{i}"
        row["source_primitive_ref"] = f"native:node-{i}"
        row["derivation_parent_ids"] = [f"node-{i+1}"] if i < 1199 else []
        nodes.append(row)
    p["source_lineage"]["observations"] = nodes
    p["source_lineage"]["roots"] = ["node-0"]
    p["physical_opening"]["source_observation_ids"] = ["node-0"]
    r = result(p,p)
    assert r["source_support_packet_complete"] is True
    assert r["exact_source_support_original_ids"] == ["physical-opening"]
