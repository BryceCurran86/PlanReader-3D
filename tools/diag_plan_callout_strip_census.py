"""Read-only census: which plan callouts have a source-corroborated glazing-strip candidate?

Runs the shadow `pb_source_plan_glazing_strip_callout_shadow` on a PDF through the real producers and
writes counts, statuses, reason codes and strip geometry. It writes no word text other than the callout marks
the caller's pattern selected, no file name and no drawing content. Nothing here is a receipt, a quantity or a
score, and the PDF is read from a path the caller supplies (a private drawing is never copied, committed or
uploaded by this tool).
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import sys
from pathlib import Path
from typing import Optional, Sequence

import pb_source_plan_glazing_strip_callout_shadow as shadow
from pb_source_visibility_authority import SourceVisibilityProducer


def census(
    pdf_path: Path, *, plan_page: int, elevation_page: int, callout_mark_pattern: str, panel_token: str,
    coordinate_quantum_pt: float, dimension_quantum_mm: float, native_finish_text_shadow: bool,
    claimant_occupancy: bool = False,
) -> dict:
    raw = Path(pdf_path).read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    source = SourceVisibilityProducer(
        producer_method="plan-callout-strip-census", producer_version="1",
        source_native_finish_text_shadow=bool(native_finish_text_shadow))
    published = source.ingest_native_pdf_bytes(
        document_id=f"census:{sha[:32]}", source_bytes=raw, source_locator="memory://census.pdf",
        page_ids=(plan_page, elevation_page))
    result = shadow.audit_plan_callout_to_glazing_strip_from_source(
        source, revision_id=published.revision.revision_id, plan_page_id=plan_page, elevation_page_id=elevation_page,
        callout_mark_pattern=callout_mark_pattern, panel_token=panel_token,
        coordinate_quantum_pt=coordinate_quantum_pt, dimension_quantum_mm=dimension_quantum_mm,
        claimant_occupancy=bool(claimant_occupancy))
    strips = {s.strip_id: s for s in result.strips}
    rows = []
    for c in result.correspondences:
        strip = strips.get(c.strip_id)
        rows.append({
            "mark": c.tag_mark,
            "status": c.status.value,
            "reason_codes": list(c.reason_codes),
            "failed_or_unevaluated": [f"{name}:{state}" for name, state in c.conditions if state != shadow.PASSED],
            "strip": None if strip is None else {
                "axis": strip.axis, "panels": strip.panel_count,
                "extent_pt": round(strip.frame_along[1] - strip.frame_along[0], 2)},
            "count_matching_strips": len(c.count_matching_strip_ids),
            "scale_consistent_strips": len(c.scale_consistent_strip_ids),
            "position_strips": len(c.position_strip_ids),
            "other_callout_claimants": len(c.rival_callout_ids),
            "rival_callout_ids": list(c.rival_callout_ids),
            "separated_claimants": [{
                "word_observation_id": x.word_observation_id, "entry": x.entry, "entry_id": x.entry_id,
                "occupied_record_id": x.occupied_record_id,
                "occupied_observation_ids": list(x.occupied_observation_ids)} for x in c.separated_claimants],
            "plan_viewport_id": c.plan_viewport_id,
            "numbers": {k: round(v, 6) for k, v in c.numbers},
        })
    return {
        "schema_version": result.schema_version,
        "document_id": result.ownership.document_id,
        "revision_id": result.ownership.revision_id,
        "snapshot_id": result.ownership.snapshot_id,
        "source_sha256": result.ownership.source_sha256,
        "plan_page": plan_page, "elevation_page": elevation_page,
        "native_finish_text_shadow": bool(native_finish_text_shadow),
        "claimant_occupancy": bool(claimant_occupancy),
        "page_reason_codes": list(result.page_reason_codes),
        "untrusted_plan_words": result.untrusted_plan_word_count,
        "strips": len(result.strips),
        "strips_by_panel_count": dict(sorted(collections.Counter(s.panel_count for s in result.strips).items())),
        "callouts": len(rows),
        "status_counts": dict(sorted(collections.Counter(r["status"] for r in rows).items())),
        "grants": {name: getattr(result, name) for name in shadow._GRANT_FLAGS},
        "callout_exclusions": [{
            "record_id": e.record_id, "word_observation_id": e.word_observation_id,
            "bbox_pt": list(e.bbox), "reason_codes": list(e.reason_codes),
            "label_trusted": e.label_trusted, "visible_ink_ids": list(e.visible_ink_ids),
            "unverified_native_primitive_refs": list(e.native_primitive_refs),
        } for e in result.callout_exclusions],
        "rows": rows,
    }


def main(argv: Optional[Sequence[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path)
    parser.add_argument("--plan-page", type=int, required=True)
    parser.add_argument("--elevation-page", type=int, required=True)
    parser.add_argument("--callout-mark-pattern", required=True, help="regex a native word must fully match")
    parser.add_argument("--panel-token", required=True, help="the native word that marks one elevation panel")
    parser.add_argument("--coordinate-quantum-pt", type=float, required=True,
                        help="the page's coordinate lattice spacing, measured from the source")
    parser.add_argument("--dimension-quantum-mm", type=float, required=True,
                        help="the print step of the elevation's figured dimensions")
    parser.add_argument("--native-finish-text-shadow", action="store_true",
                        help="enable the producer's opt-in native-text proofs")
    parser.add_argument("--claimant-occupancy", action="store_true",
                        help="also separate claimants anchored in another corroborated opening (retained, never dropped)")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    report = census(
        args.pdf, plan_page=args.plan_page, elevation_page=args.elevation_page,
        callout_mark_pattern=args.callout_mark_pattern, panel_token=args.panel_token,
        coordinate_quantum_pt=args.coordinate_quantum_pt, dimension_quantum_mm=args.dimension_quantum_mm,
        native_finish_text_shadow=args.native_finish_text_shadow, claimant_occupancy=args.claimant_occupancy)
    text = json.dumps(report, indent=1, sort_keys=True)
    if args.out is not None:
        args.out.write_text(text + "\n", encoding="utf-8")
    else:
        sys.stdout.write(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
