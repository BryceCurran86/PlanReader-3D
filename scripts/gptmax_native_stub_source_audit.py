"""Read-only original source witnesses for a proposed native nomination change.

Literal interior boundary geometry does not prove positive wall ink or a
solid physical wall, or authorize suppressing candidates, hosts or quantities.
"""
from __future__ import annotations

import argparse
import ast
from collections import defaultdict
from copy import deepcopy
from dataclasses import asdict
from hashlib import sha256
import json
from pathlib import Path
import subprocess

import pb_physical_opening_authority as opening
from pb_physical_wall_candidate_authority import _source_page_segments, MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS
from tools.diag_gptmax_full_foreground_run_source import _default_source


def _function_from_source(source):
    cls = next(n for n in ast.parse(source).body if isinstance(n, ast.ClassDef)
        and n.name == "PhysicalOpeningAuthority")
    return next(n for n in cls.body if isinstance(n, ast.FunctionDef)
        and n.name == "_visible_structural_candidates")


def _function_at_ref(ref):
    return _function_from_source(subprocess.check_output([
        "git", "show", ref + ":pb_physical_opening_authority.py"], text=True))


def audit_original_source(source_bytes, *, expected_source_sha, page_id, baseline_ref, candidate_ref):
    if type(source_bytes) is not bytes or sha256(source_bytes).hexdigest() != expected_source_sha:
        raise ValueError("original PDF source SHA mismatch")
    current = _function_from_source(Path(opening.__file__).read_text())
    baseline, proposed = _function_at_ref(baseline_ref), _function_at_ref(candidate_ref)
    if ast.dump(current, include_attributes=False) != ast.dump(baseline, include_attributes=False):
        raise ValueError("historical baseline strong discovery does not equal current main")
    candidate_node = deepcopy(proposed)
    candidate_node.decorator_list = []
    module = ast.fix_missing_locations(ast.Module(body=[candidate_node], type_ignores=[]))
    namespace = dict(vars(opening))
    exec(compile(module, "<repository-proposed-strong-nomination>", "exec"), namespace)
    class ProposedNomination(opening.PhysicalOpeningAuthority):
        _visible_structural_candidates = staticmethod(namespace["_visible_structural_candidates"])

    producer, published, visible_records = _default_source(source_bytes, expected_source_sha, page_id)
    if not visible_records or len(visible_records) > MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS:
        raise ValueError("original source input primitive safety bound")
    # This is the NATIVE candidate lane. The visibility reader also returns
    # independently typed raster segments; do not silently combine universes.
    records = tuple(r for r in visible_records if r.observation_kind == opening.NATIVE_PDF_VISIBLE_SEGMENT)
    if not records:
        raise ValueError("original native source observations unavailable")
    by_id = {r.observation_id: r for r in records}
    if len(by_id) != len(records):
        raise ValueError("duplicate original source identity")
    manifest = json.dumps([asdict(r) for r in records], sort_keys=True, default=lambda v:v.value)
    seed = records[0]
    before_strong = opening.PhysicalOpeningAuthority._visible_structural_candidates(seed, records)
    after_strong = ProposedNomination._visible_structural_candidates(seed, records)
    before = opening.PhysicalOpeningAuthority._visible_all_structural_candidates(seed, records)
    after = ProposedNomination._visible_all_structural_candidates(seed, records)
    old = {c.candidate_id:c for c in before}; new = {c.candidate_id:c for c in after}
    old_strong = {c.candidate_id:c for c in before_strong}
    new_strong = {c.candidate_id:c for c in after_strong}
    if len(old) != len(before) or len(new) != len(after):
        raise ValueError("duplicate source candidate address")
    segments, owned_ids, _, _ = _source_page_segments(source_producer=producer,
        published=published, source_bytes=source_bytes, page_id=page_id,
        decision_scope_id="native-stub-source-audit",
        resolved_visible_observations=tuple((r.observation_id,r) for r in visible_records))
    all_visible_by_id = {r.observation_id:r for r in visible_records}
    if len(all_visible_by_id) != len(visible_records) or set(owned_ids) != set(all_visible_by_id):
        raise ValueError("literal source descriptor universe mismatch")
    styles = defaultdict(list)
    for segment in segments:
        key = segment["source_observation_id"]
        record = all_visible_by_id.get(key)
        if (record is None or tuple(segment[k] for k in ("x1","y1","x2","y2")) != record.geometry):
            raise ValueError("literal source descriptor lacks exact original geometry")
        styles[key].append({k:deepcopy(segment[k]) for k in (
            "width","stroke","fill","layer","dashes","clip",
            "width_present","stroke_present","fill_present","layer_present",
            "dashes_present","clip_present") if k in segment})

    removed_strong = sorted(set(old_strong) - set(new_strong))
    removed_rows = []
    for candidate_id in removed_strong:
        candidate = old_strong[candidate_id]
        support = tuple(by_id[s] for s in candidate.source_observation_ids)
        witnesses = []
        for i, first in enumerate(support):
            for second in support[i+1:]:
                gap = opening._face_break(first, second)
                if gap is None:
                    continue
                first_line = opening._line_geometry(first)
                for source in records:
                    line = opening._line_geometry(source)
                    if (source.observation_id in {first.observation_id,second.observation_id}
                            or line is None or not opening._collinear(first_line,line)):
                        continue
                    lo, hi = sorted((opening._projection(line[:2],gap.direction),
                                     opening._projection(line[2:],gap.direction)))
                    tol = opening._COORD_EQ_ABS_TOL
                    if not (lo > gap.gap_start + tol and hi < gap.gap_end - tol and hi-lo > tol):
                        continue
                    descriptors = deepcopy(styles[source.observation_id])
                    white_fill_only = bool(descriptors) and all(
                        d.get("stroke_present") is False and d.get("fill_present") is True
                        and tuple(d.get("fill") or ()) == (1.,1.,1.) for d in descriptors)
                    witnesses.append(dict(face_source_observation_ids=[first.observation_id,second.observation_id],
                        proposed_gap_axis_interval_pt=[gap.gap_start,gap.gap_end],
                        source_observation=asdict(source), interior_source_axis_interval_pt=[lo,hi],
                        literal_source_graphic_descriptors=descriptors,
                        only_unstroked_white_fill_descriptors=white_fill_only,
                        original_source_geometry_reauthenticated=True,
                        positive_stroked_wall_ink_proven=False,solid_structural_wall_role_proven=False,
                        physical_nonexistence_proven=False,host_publication_allowed=False))
        removed_rows.append(dict(candidate=asdict(candidate),interior_source_witnesses=witnesses,
            all_interior_witnesses_are_unstroked_white_fill=bool(witnesses) and all(
                w["only_unstroked_white_fill_descriptors"] for w in witnesses),
            removal_is_source_authority_approved=False,host_publication_allowed=False))
    added_rows = []
    for candidate_id in sorted(set(new)-set(old)):
        candidate = new[candidate_id]
        parents = set(candidate.source_observation_ids)
        suppressed = sorted(k for k,c in old_strong.items() if parents <= set(c.source_observation_ids))
        added_rows.append(dict(candidate=asdict(candidate),
            original_strong_support_supersets=suppressed,
            removed_strong_support_supersets=[k for k in suppressed if k in removed_strong],
            source_observation_records=[asdict(by_id[s]) for s in candidate.source_observation_ids],
            host_publication_allowed=False))
    if json.dumps([asdict(r) for r in records], sort_keys=True, default=lambda v:v.value) != manifest:
        raise RuntimeError("audit mutated original source records")
    if producer.published_snapshot_for_revision(published.revision.revision_id) != published:
        raise RuntimeError("audit changed original source snapshot")
    return dict(source_sha256=expected_source_sha,page_id=page_id,
        tested_main_sha=subprocess.check_output(["git","rev-parse","HEAD"],text=True).strip(),
        baseline_ref=baseline_ref,candidate_ref=candidate_ref,
        current_main_strong_discovery_matches_archived_baseline=True,
        original_source_observations_reauthenticated=True,original_source_snapshot_unchanged=True,
        input_source_count=len(records),source_primitive_safety_cap=MAX_WALL_TOPOLOGY_SOURCE_SEGMENTS,
        nomination_source_kind=opening.NATIVE_PDF_VISIBLE_SEGMENT,
        independently_authenticated_ordinary_source_count=len(visible_records),
        source_manifest_sha256=sha256(manifest.encode()).hexdigest(),
        before_candidate_count=len(before),after_candidate_count=len(after),
        before_strong_count=len(before_strong),after_strong_count=len(after_strong),
        removed_candidate_ids=sorted(set(old)-set(new)),removed_strong_rows=removed_rows,
        added_candidate_rows=added_rows,solid_structural_wall_role_proven=False,
        original_source_parity_gate_passed=False,source_candidate_universe_complete=False,
        audit_stage="isolated_native_only_low_level_nomination_not_production_closure",
        physical_nonexistence_proven=False,host_publication_allowed=False,
        metric_quantity_publication_allowed=False,opening_count_publication_allowed=False,
        benchmark_accuracy=None)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--page-id", required=True)
    parser.add_argument("--baseline-ref", required=True)
    parser.add_argument("--candidate-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit_original_source(args.pdf.read_bytes(), expected_source_sha=args.expected_source_sha,
        page_id=args.page_id, baseline_ref=args.baseline_ref, candidate_ref=args.candidate_ref)
    args.output.write_text(json.dumps(result,indent=2,sort_keys=True,allow_nan=False,
        default=lambda v:v.value)+"\n")
    print(json.dumps(dict(before=result["before_candidate_count"],after=result["after_candidate_count"],
        removed_strong=len(result["removed_strong_rows"]),added=len(result["added_candidate_rows"]),
        source_parity_passed=False,host_publication_allowed=False)))


if __name__ == "__main__":
    main()
