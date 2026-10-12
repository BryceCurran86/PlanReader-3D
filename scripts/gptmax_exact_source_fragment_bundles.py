"""Join actual source-owned W4 records without treating addresses as wall identity.

All output is descriptive shadow evidence. The pure join does not authenticate
PDF bytes, promote wall roles, combine graph edges or publish opening hosts.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
import math
from pathlib import Path

from pb_migration_contracts import EvidenceResolutionStatus, stable_contract_id
from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_source_observation_authority import SourceObservationRecord
from scripts.gptmax_exact_endpoint_flank_shadow import source_interval_coverage
from scripts.gptmax_source_graphic_state_shadow import encoded, original_graphic_state_report
from tools.diag_gptmax_full_foreground_run_source import original_full_foreground_report


def _identity(value):
    if type(value) is not str or not value or value.strip() != value:
        raise ValueError("missing or malformed actual source identity")
    return value


def _identities(values):
    if not isinstance(values, (list, tuple)):
        raise ValueError("actual source membership must be explicit")
    result = tuple(_identity(v) for v in values)
    if len(set(result)) != len(result):
        raise ValueError("duplicate actual source membership")
    return result


def _geometry(values, size):
    if (not isinstance(values, (tuple, list)) or len(values) != size
            or any(type(v) not in (int, float) for v in values)):
        raise ValueError("malformed actual source geometry")
    try:
        finite = all(math.isfinite(v) for v in values)
    except OverflowError:
        finite = False
    if not finite:
        raise ValueError("nonfinite actual source geometry")
    return tuple(values)


def join_actual_source_bundles(graph, records):
    """Retain an exact candidate/abstention partition and all source spans.

    Record addresses name existing assembly memberships; they are not new
    physical-wall or canonical IDs. Reused candidate addresses remain unchanged.
    """
    records = tuple(records)
    if not records or len(records) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError("source primitive safety bound")
    original = {}
    scopes = set()
    for record in records:
        if type(record) is not SourceObservationRecord:
            raise ValueError("original source observation record required")
        key = _identity(record.observation_id)
        if key in original:
            raise ValueError("duplicate original source observation")
        line = _geometry(record.geometry, 4)
        if line[:2] == line[2:]:
            raise ValueError("degenerate original source observation")
        scope = (_identity(record.source_sha256), _identity(record.page_id))
        if len(scope[0]) != 64 or any(c not in "0123456789abcdef" for c in scope[0]):
            raise ValueError("malformed original source SHA")
        for field in (record.document_id, record.revision_id, record.snapshot_id):
            _identity(field)
        scopes.add(scope)
        original[key] = record
    if len(scopes) != 1:
        raise ValueError("foreign original source scope")
    source_sha, page_id = next(iter(scopes))
    if type(graph.get("input_source_count")) is not int or graph["input_source_count"] != len(records):
        raise ValueError("incomplete actual graph source inventory")

    edges, by_parent = {}, defaultdict(list)
    for edge in graph["all_w2_edges"]:
        key = _identity(edge["edge_id"])
        parents = _identities(edge["source_observation_ids"])
        if key in edges or not set(parents) <= original.keys():
            raise ValueError("duplicate or foreign actual fragment ownership")
        _geometry(edge["w2_fragment_geometry_pt"], 4)
        if (type(edge["w3_retained"]) is not bool or type(edge["w3_removed"]) is not bool
                or edge["w3_retained"] == edge["w3_removed"]):
            raise ValueError("contradictory actual W3 fragment disposition")
        edges[key] = edge
        for parent in parents:
            by_parent[parent].append(edge)

    owners, bundles = {}, []
    address_counts = defaultdict(int)
    for candidate in graph["all_experimental_w4_candidates"]:
        address = _identity(candidate["candidate_id"])
        members = sorted(_identities(candidate["w2_edge_ids"]))
        if not members or any(e not in edges or not edges[e]["w3_retained"] for e in members):
            raise ValueError("assembly contains unavailable actual retained fragment")
        points = candidate["centerline_pt"]
        if not isinstance(points, (tuple, list)) or len(points) < 2:
            raise ValueError("actual assembly centerline unavailable")
        geometry = [_geometry(p, 2) for p in points]
        parents = sorted({p for e in members for p in edges[e]["source_observation_ids"]})
        parentless = [e for e in members if not edges[e]["source_observation_ids"]]
        record_id = stable_contract_id("source_fragment_bundle", dict(
            source_sha256=source_sha, page_id=page_id, candidate_id=address,
            w2_edge_ids=members, centerline_pt=geometry, source_observation_ids=parents), digest_chars=32)
        if any(e in owners for e in members):
            raise ValueError("actual retained fragment has competing assembly records")
        for edge_id in members:
            owners[edge_id] = (record_id, address)
        address_counts[address] += 1
        bundles.append(dict(record_id=record_id, candidate_id=address,
            actual_w2_edge_ids=members, source_observation_ids=parents,
            centerline_pt=deepcopy(points), parentless_fragment_ids=parentless,
            all_fragment_source_parents_available=not parentless,
            status=(EvidenceResolutionStatus.ABSTAINED.value if parentless else
                EvidenceResolutionStatus.CANDIDATE.value),
            physical_equivalence_proven=False, structural_wall_role_proven=False,
            host_publication_allowed=False))

    abstained, abstained_records = {}, set()
    for chain in graph["all_w4_abstained_chain_rows"]:
        record_id = _identity(chain["record_id"])
        if record_id in abstained_records:
            raise ValueError("duplicate actual abstained chain identity")
        abstained_records.add(record_id)
        fragments = chain["actual_owned_w3_fragment_rows"]
        if not fragments:
            raise ValueError("actual abstained chain fragment inventory unavailable")
        for fragment in fragments:
            key = _identity(fragment["edge_id"])
            edge = edges.get(key)
            parents = _identities(fragment["source_observation_ids"])
            if (edge is None or not edge["w3_retained"] or key in owners or key in abstained
                    or fragment["w2_fragment_geometry_pt"] != edge["w2_fragment_geometry_pt"]
                    or set(parents) != set(edge["source_observation_ids"])
                    or set(_identities(fragment["primitive_lineage"]["source_primitive_ids"])) != set(parents)):
                raise ValueError("unowned or contradictory actual abstained fragment")
            abstained[key] = record_id
    retained = {e for e, row in edges.items() if row["w3_retained"]}
    if set(owners) | set(abstained) != retained:
        raise ValueError("actual assemblies do not partition retained source fragments")
    for key, edge in edges.items():
        expected = [owners[key][1]] if key in owners else []
        if (list(_identities(edge["experimental_w4_candidate_ids"])) != expected
                or type(edge.get("w4_candidate_membership_available")) is not bool
                or edge["w4_candidate_membership_available"] != (key not in abstained)
                or list(_identities(edge["w4_abstained_chain_record_ids"])) != (
                    [abstained[key]] if key in abstained else [])):
            raise ValueError("actual fragment address and record membership disagree")

    census = graph["source_parent_census"]
    if len(census) != len(records):
        raise ValueError("incomplete actual source-parent census")
    seen = set()
    for row in census:
        key = _identity(row["source_observation_id"])
        if (key in seen or key not in original
                or set(_identities(row["w2_edge_ids"])) != {e["edge_id"] for e in by_parent[key]}):
            raise ValueError("contradictory actual source-parent census")
        seen.add(key)

    spans = []
    for source_id, record in sorted(original.items()):
        line = record.geometry
        base = dict(source_observation_id=source_id, original_source_line_pt=list(line),
            source_parent_ownership_available=True, physical_equivalence_proven=False,
            structural_wall_role_proven=False, host_publication_allowed=False)
        if line[0] != line[2] and line[1] != line[3]:
            spans.append(dict(base, status=EvidenceResolutionStatus.ABSTAINED.value,
                reason_codes=["exact_axis_aligned_source_span_unavailable"],
                exact_source_span_coverage=None, common_actual_assembly_record_ids=[],
                common_candidate_ids=[], contributing_fragment_rows=[]))
            continue
        coverage = source_interval_coverage(dict(source_observation_id=source_id,
            source_line_pt=line, actual_w2_edge_rows=by_parent[source_id]))
        contributors = []
        common_records, common_addresses = None, None
        for interval in coverage["exact_owned_fragment_intervals"]:
            if not interval["w3_retained"]:
                continue
            edge_id = interval["edge_id"]
            owned = owners.get(edge_id)
            record_ids = {owned[0]} if owned else set()
            addresses = {owned[1]} if owned else set()
            common_records = record_ids if common_records is None else common_records & record_ids
            common_addresses = addresses if common_addresses is None else common_addresses & addresses
            contributors.append(dict(interval, actual_assembly_record_ids=sorted(record_ids),
                candidate_ids=sorted(addresses), abstained_chain_record_ids=(
                    [abstained[edge_id]] if edge_id in abstained else [])))
        complete = coverage["complete_actual_w3_retained_source_span_coverage"]
        if not complete:
            reason = "actual_retained_source_span_incomplete"
        elif any(r["abstained_chain_record_ids"] for r in contributors):
            reason = "actual_source_span_assembly_abstained"
        elif not common_records:
            reason = "source_span_crosses_actual_assembly_records"
        else:
            reason = "actual_source_span_bundle_observed_no_physical_authority"
        spans.append(dict(base, status=EvidenceResolutionStatus.CANDIDATE.value if
            complete and common_records else EvidenceResolutionStatus.ABSTAINED.value,
            reason_codes=[reason], exact_source_span_coverage=coverage,
            common_actual_assembly_record_ids=sorted(common_records or ()),
            common_candidate_ids=sorted(common_addresses or ()),
            contributing_fragment_rows=contributors))
    return dict(source_sha256=source_sha, page_id=page_id,
        source_primitive_safety_cap=MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        input_source_count=len(records), actual_retained_fragment_count=len(retained),
        actual_abstained_fragment_count=len(abstained), actual_assembly_records=sorted(
            bundles, key=lambda r:r["record_id"]), source_span_rows=spans,
        reused_candidate_addresses=sorted(k for k, n in address_counts.items() if n > 1),
        exact_candidate_abstention_partition_verified=True,
        source_authenticated_by_join_alone=False, combined_graph_edge_created=False,
        physical_equivalence_proven=False, structural_wall_role_proven=False,
        host_publication_allowed=False, opening_count_publication_allowed=False,
        metric_quantity_publication_allowed=False, benchmark_accuracy=None)


def original_source_bundle_report(source_bytes, *, page_id, expected_source_sha):
    graphic = original_graphic_state_report(source_bytes, page_id=page_id,
        expected_source_sha=expected_source_sha)
    foreground = original_full_foreground_report(source_bytes, page_id=page_id,
        expected_source_sha=expected_source_sha, trace=False)
    records = tuple(SourceObservationRecord(**r) for r in [
        *foreground["ordinary_visible_source_records"],
        *(r["source_observation"] for r in foreground["authenticated_pixel_source_records"])])
    if sha256(encoded([asdict(r) for r in records])).hexdigest() != graphic["input_source_manifest_sha256"]:
        raise ValueError("independent original source manifests disagree")
    graph = graphic["source_graph"]
    before = encoded(graph)
    result = join_actual_source_bundles(graph, records)
    if before != encoded(graph):
        raise RuntimeError("fragment bundle join changed actual source graph")
    result.update(original_source_reauthenticated=True,
        default_production_state_unchanged=graphic["default_production_state_unchanged"],
        original_production_summary=graphic["original_production_summary"],
        original_production_receipts_sha256=graphic["original_production_receipts_sha256"],
        exact_unmodified_graph_sha256=graphic["exact_unmodified_graph_sha256"],
        input_source_manifest_sha256=graphic["input_source_manifest_sha256"])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = original_source_bundle_report(args.pdf.read_bytes(), page_id=args.page_id,
        expected_source_sha=args.expected_source_sha)
    args.output.write_bytes(encoded(result) + b"\n")
    print(json.dumps(dict(source_inputs=result["input_source_count"],
        actual_assembly_records=len(result["actual_assembly_records"]),
        reused_candidate_addresses=len(result["reused_candidate_addresses"]),
        unchanged_production=result["default_production_state_unchanged"],
        host_publication_allowed=False)))


if __name__ == "__main__":
    main()
