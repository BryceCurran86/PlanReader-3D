"""Read-only, counts-only diagnostic for the opening aperture equivalence SHADOW.

Reads one original in place (SHA-checked) and one sealed source-closed run of it (from ``run_source_closed_project_handoff``),
asks the existing ``PhysicalOpeningAuthority`` for the pairwise partition of every pair of sealed opening-area records,
groups the records into aperture classes with the shadow rule, and reports counts only. It never changes a sealed run,
a customer row or a quantity.

    python -m tools.diag_opening_aperture_equivalence_shadow --pdf <original.pdf> --expected-source-sha256 <hex> \
        --sealed-run <au_..._.json> --plan-page 3 --output out.json [--identity-map <identity_map.json>]
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path

from pb_opening_aperture_equivalence_shadow import (
    DISTINCT, OVERLAPPING, UNPROVEN, ApertureRecord, PairVerdict, resolve_aperture_equivalence,
)


def run(pdf: Path, expected_sha: str, sealed_run: Path, plan_page: int, identity_map: Path | None = None) -> dict:
    from pb_live_physical_net_wall_integration import LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION
    from pb_live_wall_opening_authority_composition import compose_live_wall_opening_authority
    from pb_opening_label_dimension_authority import OpeningLabelDimensionProducer
    from pb_source_observation_authority import ObservationSelector
    from pb_source_visibility_authority import SourceVisibilityProducer

    payload = pdf.read_bytes()
    sha = hashlib.sha256(payload).hexdigest()
    if sha != expected_sha:
        raise SystemExit("original source SHA-256 mismatch")
    sealed = json.loads(sealed_run.read_text(encoding="utf-8"))
    if sha not in set(sealed.get("source_sha256s") or ()):
        raise SystemExit("sealed run does not belong to this original")
    quantities = [q for q in sealed["quantities"] if q.get("family") == "opening_area" and str(q.get("source_page")) == str(plan_page)]
    source = SourceVisibilityProducer(producer_method="live-physical-net-wall",
                                      producer_version=LIVE_PHYSICAL_NET_WALL_INTEGRATION_SCHEMA_VERSION,
                                      raster_paired_outer_faces_shadow=True)
    initial = source.ingest_native_pdf_bytes(document_id=f"live-source:{sha[:32]}", source_bytes=payload,
                                             source_locator="memory://aperture-equivalence.pdf", page_ids=(plan_page,))
    comp = compose_live_wall_opening_authority(source_visibility_producer=source, revision_id=initial.revision.revision_id,
                                               page_ids=(str(plan_page),))
    authority = comp.physical_opening_authority
    traces = {t.opening_identity_id: t for t in comp.opening_bindings}
    label_producer = OpeningLabelDimensionProducer.from_source_visibility_producer(source)
    records, selectors, missing = [], {}, 0
    for q in quantities:
        ref = q["object_identity_refs"][0]
        trace = traces.get(ref)
        if trace is None:
            missing += 1
            continue
        sel = comp.binding_selectors[ref]
        selector = ObservationSelector(document_id=sel.document_id, revision_id=sel.revision_id, source_sha256=sel.source_sha256,
                                       snapshot_id=sel.snapshot_id, observation_id=trace.representative_observation_id)
        evidence = getattr(label_producer.publish_scope(selector), "evidence", None)
        figure = tuple(sorted(evidence.source_text_observation_ids)) if evidence is not None else ()
        records.append(ApertureRecord(
            ref, f"{sel.document_id}|{sel.revision_id}|{sel.snapshot_id}|{sel.page_id}", figure, float(q["value"]),
            # the physical host is the group of member wall candidates the host binding rests on: the per-record host id is derived from
            # the record itself, so two records of one aperture never share it even when they rest on the very same walls
            "|".join(sorted(trace.member_wall_candidate_ids)) or None,
            (q["quantity_id"],)))
        selectors[ref] = selector
    verdicts, partitions = [], Counter()
    for left, right in itertools.combinations(sorted(selectors), 2):
        receipt = authority.partition_receipt(selectors[left], selectors[right])
        partitions[receipt.partition] += 1
        word = (DISTINCT if receipt.is_physically_distinct
                else OVERLAPPING if receipt.partition == "overlapping_extent" else UNPROVEN)
        verdicts.append(PairVerdict(left, right, word))
    classes = resolve_aperture_equivalence(records, verdicts, enabled=True)
    by_id = {r.record_id: r for r in records}
    overlap = Counter()
    for v in verdicts:
        if v.verdict != OVERLAPPING:
            continue
        a, b = by_id[v.left_id], by_id[v.right_id]
        overlap[("figure_same" if a.figure_key and a.figure_key == b.figure_key else "figure_differs_or_missing",
                 "area_same" if a.area_m2 == b.area_m2 else "area_differs",
                 "host_same" if a.host_key is not None and a.host_key == b.host_key else (
                     "host_missing_on_a_side" if a.host_key is None or b.host_key is None else "host_differs"))] += 1
    consolidated = [c for c in classes if c.is_consolidated]
    ambiguous = [c for c in classes if c.is_ambiguous]
    mapped_refs = set()
    if identity_map is not None:
        mapped_refs = {r for b in json.loads(identity_map.read_text(encoding="utf-8"))["bindings"]
                       for r in b["production_object_identity_refs"]}
    by_record = {m: c for c in classes for m in c.member_ids}
    return {
        "schema_version": "1.0.0", "source_sha256": sha, "sealed_run_id": sealed.get("run_id"), "shadow_only": True,
        "benchmark_score_granted": False, "plan_page": plan_page,
        "sealed_opening_area_quantities": len(quantities), "records_with_a_live_opening_trace": len(records), "records_without_one": missing,
        "pairs_compared": len(verdicts), "pair_partitions": dict(sorted(partitions.items())),
        "overlapping_pair_evidence": {" | ".join(k): n for k, n in sorted(overlap.items())},
        "classes": len(classes), "consolidated_classes": len(consolidated),
        "consolidated_class_size_histogram": dict(sorted(Counter(len(c.member_ids) for c in consolidated).items())),
        "records_in_consolidated_classes": sum(len(c.member_ids) for c in consolidated),
        "single_record_classes": sum(1 for c in classes if not c.is_ambiguous and len(c.member_ids) == 1),
        "ambiguous_classes": len(ambiguous), "ambiguous_records": sum(len(c.member_ids) for c in ambiguous),
        "ambiguous_reasons": dict(sorted(Counter(r for c in ambiguous for r in c.reason_codes).items())),
        "quantities_if_one_per_class": len(consolidated) + sum(1 for c in classes if not c.is_ambiguous and len(c.member_ids) == 1),
        "duplicate_rows_removed_if_consolidated": sum(len(c.member_ids) - 1 for c in consolidated),
        "identity_map_bindings_touched": {
            "records_bound_by_the_map": sum(1 for r in records if r.record_id in mapped_refs),
            "consolidated_classes_holding_two_or_more_mapped_records": sum(1 for c in consolidated if sum(1 for m in c.member_ids if m in mapped_refs) >= 2),
            "consolidated_classes_holding_a_mapped_and_an_unmapped_record": sum(
                1 for c in consolidated if any(m in mapped_refs for m in c.member_ids) and any(m not in mapped_refs for m in c.member_ids)),
            "consolidated_classes_of_unmapped_records_only": sum(1 for c in consolidated if not any(m in mapped_refs for m in c.member_ids)),
        } if identity_map is not None else None,
        "class_ids": [c.class_id[-12:] for c in classes],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, required=True)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--sealed-run", type=Path, required=True)
    parser.add_argument("--plan-page", type=int, required=True)
    parser.add_argument("--identity-map", type=Path, default=None)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.pdf, args.expected_source_sha256, args.sealed_run, args.plan_page, args.identity_map)
    args.output.write_text(json.dumps(report, indent=1, sort_keys=True), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("sealed_opening_area_quantities", "classes", "consolidated_classes", "ambiguous_classes")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
