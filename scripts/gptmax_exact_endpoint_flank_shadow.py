"""Compare default and exact W2 joins on identical original local source inputs.

Local scope is an experiment, never an authenticated floor-plan viewport or a
complete wall universe. No source fragment becomes a host or quantity here.
"""
from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
from hashlib import sha256
import json
import math
from pathlib import Path

from pb_physical_wall_candidate_authority import MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from pb_source_observation_authority import SourceObservationRecord
from pb_opening_host_binding_authority import _OpeningGeometry
from scripts.gptmax_full_foreground_flank_stages import _flank_stage_rows, _contacts
from tools.diag_gptmax_full_foreground_flank import full_foreground_flank_census
from tools.diag_gptmax_full_foreground_run_source import original_full_foreground_report, _trace_sources
from tools.diag_gptmax_raster_host_source_membership import original_raster_host_ancestry_census
from tools.diag_gptmax_required_flank_source import required_flank_source_census


def _line_box(line):
    if (not isinstance(line, (tuple, list)) or len(line) != 4
            or any(type(v) not in (int, float) for v in line)):
        raise ValueError("invalid local original source line")
    try:
        finite = all(math.isfinite(v) for v in line)
    except OverflowError:
        finite = False
    if not finite or tuple(line[:2]) == tuple(line[2:]):
        raise ValueError("nonfinite or degenerate local original source line")
    return min(line[0], line[2]), min(line[1], line[3]), max(line[0], line[2]), max(line[1], line[3])


def _local_records(records, source_ids):
    """Keep every full source primitive whose bounds touch the seed bounds.

    No cropping, nearest election, radius tuning or ancestor transfer. Bounds
    can retain unrelated lines; they cannot confer viewport/wall ownership.
    """
    records = tuple(records)
    if not records or len(records) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError("original input source primitive safety bound")
    index, boxes, scopes = {}, {}, set()
    for r in records:
        key = r.observation_id
        if not isinstance(key, str) or not key.strip() or key in index:
            raise ValueError("duplicate or missing original source identity")
        if (not isinstance(r.source_sha256, str) or len(r.source_sha256) != 64
                or not isinstance(r.page_id, str) or not r.page_id):
            raise ValueError("original source scope unavailable")
        index[key], boxes[key] = r, _line_box(r.geometry)
        scopes.add((r.source_sha256, r.page_id))
    if len(scopes) != 1:
        raise ValueError("foreign original source scope")
    seeds = tuple(source_ids)
    if (not seeds or len(set(seeds)) != len(seeds)
            or any(not isinstance(s, str) or not s.strip() for s in seeds)
            or not set(seeds) <= index.keys()):
        raise ValueError("unavailable original flank seed source")
    extent = (min(boxes[s][0] for s in seeds), min(boxes[s][1] for s in seeds),
        max(boxes[s][2] for s in seeds), max(boxes[s][3] for s in seeds))
    x0, y0, x1, y1 = extent
    local = tuple(index[key] for key in sorted(index)
        if boxes[key][0] <= x1 and boxes[key][2] >= x0
        and boxes[key][1] <= y1 and boxes[key][3] >= y0)
    if not set(seeds) <= {r.observation_id for r in local}:
        raise RuntimeError("local experiment lost its original seed")
    return local, extent


def source_interval_coverage(pixel):
    """Exact axis-aligned source coverage, not a merged edge or physical wall.

    Preserve every actual fragment address. Do not bridge a missing interval,
    absorb an offset line, borrow a parent or transfer W3-discarded ancestry.
    """
    source_id = pixel['source_observation_id']
    line = pixel['source_line_pt']
    _line_box(line)
    if line[1] == line[3]:
        axis, normal = 0, 1
    elif line[0] == line[2]:
        axis, normal = 1, 0
    else:
        raise ValueError('original pixel source is not axis-aligned')
    lo, hi = sorted((line[axis], line[axis+2]))
    intervals, retained, evidence, seen = [], [], [], set()
    for edge in sorted(pixel['actual_w2_edge_rows'], key=lambda e: e['edge_id']):
        key = edge['edge_id']
        if (not isinstance(key, str) or not key or key in seen
                or source_id not in edge['source_observation_ids']
                or type(edge['w3_retained']) is not bool):
            raise ValueError('invalid actual source fragment ownership')
        seen.add(key)
        coords = edge['w2_fragment_geometry_pt']
        _line_box(coords)
        if coords[normal] != line[normal] or coords[normal+2] != line[normal]:
            continue
        a, b = sorted((coords[axis], coords[axis+2]))
        a, b = max(a,lo), min(b,hi)
        if b <= a:
            continue
        intervals.append((a,b))
        if edge['w3_retained']: retained.append((a,b))
        evidence.append(dict(edge_id=key, original_axis_interval_pt=[a,b],
            w3_retained=edge['w3_retained']))
    def uncovered(spans):
        gaps, cursor = [], lo
        for a,b in sorted(spans):
            if a > cursor: gaps.append([cursor,a])
            cursor = max(cursor,b)
        if cursor < hi: gaps.append([cursor,hi])
        return gaps
    w2_gaps, w3_gaps = uncovered(intervals), uncovered(retained)
    return dict(original_axis_interval_pt=[lo,hi], exact_owned_fragment_intervals=evidence,
        w2_uncovered_source_intervals_pt=w2_gaps, w3_uncovered_source_intervals_pt=w3_gaps,
        complete_actual_w2_source_span_coverage=not w2_gaps,
        complete_actual_w3_retained_source_span_coverage=not w3_gaps,
        combined_graph_edge_created=False, physical_wall_authority=False,
        host_publication_allowed=False)


def annotate_source_span_coverage(rows, original, required):
    """Distinguish a single-fragment predicate from complete interval survival."""
    for row in rows:
        identity = row['opening_identity_id']
        source, = (r for r in original['opening_rows'] if r['opening_identity_id']==identity)
        requirement, = (r for r in required['opening_rows'] if r['opening_identity_id']==identity)
        opening = _OpeningGeometry(**source['original_aperture_coordinate_basis'])
        for flank in row['flanks']:
            required_flank, = (f for f in requirement['flanks'] if f['role']==flank['role'])
            for pixel in flank['source_run_rows']:
                coverage = source_interval_coverage(pixel)
                contact = _contacts(pixel['source_line_pt'], opening, required_flank)
                pixel['original_source_span_meets_required_flank_geometry'] = contact
                pixel['exact_source_span_coverage'] = coverage
                pixel['single_fragment_contact_failure_with_complete_retained_source_span'] = (
                    contact and coverage['complete_actual_w3_retained_source_span_coverage']
                    and not any(e['matches_original_required_flank_geometry']
                                for e in pixel['actual_w2_edge_rows']))


def compare_local_flank_graphs(joined, original, required, records):
    """Pure shadow experiment; input receipts must come from the fresh reader."""
    records = tuple(records)
    output = []
    for opening in sorted(joined['opening_rows'], key=lambda r: r['opening_identity_id']):
        identity = opening['opening_identity_id']
        seeds = sorted({p['source_observation_id'] for f in opening['flanks']
            for p in f['pixel_run_candidates']})
        if not seeds:
            raise ValueError("source-positive opening flank unavailable")
        local, extent = _local_records(records, seeds)
        scoped = dict(opening_rows=[opening])
        modes = {}
        for name, exact in (('default_snap_local_shadow', False), ('exact_endpoint_local_shadow', True)):
            graph = _trace_sources(local, exact_endpoint_shadow=exact)
            graph['scope_authority'] = 'local source bounds experiment only; no authenticated floor-plan viewport'
            rows = _flank_stage_rows(scoped, original, required, graph)
            annotate_source_span_coverage(rows, original, required)
            modes[name] = dict(opening_rows=rows, source_graph=graph,
                observed_geometry_barrier_counts=dict(sorted(Counter(
                    p['observed_geometry_barrier'] for r in rows for f in r['flanks']
                    for p in f['source_run_rows']).items())))
        output.append(dict(opening_identity_id=identity, original_seed_source_ids=seeds,
            experimental_source_extent_pt=extent, source_inputs=[asdict(r) for r in local],
            identical_local_source_inputs_for_both_modes=True, **modes,
            local_scope_is_authenticated_floor_plan_viewport=False,
            local_scope_matches_full_page_topology=False,
            physical_equivalence_proven=False, host_publication_allowed=False))
    return output


def exact_endpoint_source_report(source_bytes, *, page_id, expected_source_sha):
    if not isinstance(source_bytes, bytes) or sha256(source_bytes).hexdigest() != expected_source_sha:
        raise ValueError("immutable original PDF SHA mismatch")
    original = original_raster_host_ancestry_census(source_bytes,
        page_id=page_id, expected_source_sha=expected_source_sha)
    raw = json.dumps(original, sort_keys=True, allow_nan=False).encode()
    required = required_flank_source_census(original, expected_source_sha=expected_source_sha)
    required['input_report_sha256'] = sha256(raw).hexdigest()
    foreground = original_full_foreground_report(source_bytes,
        page_id=page_id, expected_source_sha=expected_source_sha, trace=False)
    joined = full_foreground_flank_census(raw, required, foreground,
        pdf_bytes=source_bytes, expected_source_sha=expected_source_sha)
    source_rows = [*foreground['ordinary_visible_source_records'],
        *(r['source_observation'] for r in foreground['authenticated_pixel_source_records'])]
    records = tuple(SourceObservationRecord(**r) for r in source_rows)
    rows = compare_local_flank_graphs(joined, original, required, records)
    # The same established source authority independently proves that running
    # the shadow experiment did not alter the production opening receipts.
    after = original_raster_host_ancestry_census(source_bytes,
        page_id=page_id, expected_source_sha=expected_source_sha)
    if original != after:
        raise RuntimeError("exact endpoint shadow changed original production source state")
    return dict(schema_version='1.0.0', source_sha256=expected_source_sha, page_id=page_id,
        original_source_reauthenticated=True, default_production_state_unchanged=True,
        original_source_report_sha256=sha256(raw).hexdigest(),
        original_opening_bindings=original['opening_bindings'], original_host_frames=original['host_frames'],
        source_primitive_safety_cap=MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        full_source_input_primitive_count=len(records), opening_rows=rows,
        physical_wall_authority=False, physical_equivalence_proven=False,
        source_parent_transfer_allowed=False, structural_source_universe_complete=False,
        host_publication_allowed=False, opening_count_publication_allowed=False,
        metric_quantity_publication_allowed=False, benchmark_accuracy=None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pdf', required=True, type=Path)
    parser.add_argument('--page-id', required=True)
    parser.add_argument('--expected-source-sha', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    result = exact_endpoint_source_report(args.pdf.read_bytes(), page_id=args.page_id,
        expected_source_sha=args.expected_source_sha)
    args.output.write_text(json.dumps(result, sort_keys=True, indent=2, allow_nan=False) + '\n')
    print(json.dumps(dict(openings=len(result['opening_rows']),
        default_production_state_unchanged=True, host_publication_allowed=False)))


if __name__ == '__main__':
    main()
